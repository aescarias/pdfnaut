from __future__ import annotations

from hashlib import md5
from typing import Literal, Union

from pdfnaut.exceptions import MissingCryptProviderError

from ..common.utils import ensure_bytes
from ..cos.objects import PdfDictionary, PdfHexString, PdfName, PdfReference, PdfStream
from .providers import CRYPT_PROVIDERS, CryptProvider

CryptMethod = Literal["Identity", "ARC4", "AESV2"]
Encryptable = Union[PdfStream, PdfHexString, bytes]

PASSWORD_PADDING = b"(\xbfN^Nu\x8aAd\x00NV\xff\xfa\x01\x08..\x00\xb6\xd0h>\x80/\x0c\xa9\xfedSiz"


def pad_password(password: bytes) -> bytes:
    """Pads or truncates the input ``password`` to exactly 32 bytes. 
    
    - If ``password`` is longer than 32 bytes, it shall be truncated. 
    - If ``password`` is shorter than 32 bytes, it shall be padded by appending data \
    from :const:`.PASSWORD_PADDING` as needed.
    """
    return password[:32] + PASSWORD_PADDING[: 32 - len(password)]


class StandardSecurityHandler:
    """An implementation of § 7.6.4 "Standard security handler"

    The standard security handler includes access permissions and allows up to 2 passwords:
    the owner password which has all permissions and the user password which should only
    have the permissions specified by the document.
    """

    def __init__(self, encryption: PdfDictionary, ids: list[PdfHexString | bytes]) -> None:
        """
        Arguments:
            encryption (PdfDictionary):
                The standard encryption dictionary specified in the document's trailer.
                (see § 7.6.4, "Standard encryption dictionary")

            ids (PdfArray[PdfHexString | bytes]).
                The ID array specified in the document's trailer.
        """
        self.encryption = encryption
        self.ids = ids

    @property
    def key_length(self) -> int:
        """The length of the encryption key in bytes."""
        return self.encryption.get("Length", 40) // 8

    def compute_encryption_key(self, password: bytes) -> bytes:
        """Computes an encryption key from ``password`` according to § 7.6.4.3.2,
        "Algorithm 2: Computing a file encryption key in order to encrypt a document
        (revision 4 and earlier)"."""

        # a) Pad or truncate the password string to exactly 32 bytes.
        padded_password = pad_password(password)

        # b) Initialize the MD5 hash function with the padded string.
        psw_hash = md5(padded_password)

        # c) Pass the value of the O entry in the Encrypt dictionary.
        psw_hash.update(ensure_bytes(self.encryption["O"]))

        # d) Pass the value of the P entry as a 32-bit unsigned integer.
        #    P may be negative, so it's wrapped into unsigned beforehand.
        perms = (self.encryption["P"] + 2**32) % 2**32
        psw_hash.update(perms.to_bytes(4, "little"))

        # e) Pass the first element of the file identifier array.
        psw_hash.update(ensure_bytes(self.ids[0]))

        # f) If the handler is revision 4 or greater, and the metadata is not being
        #    encrypted, pass 4 bytes to the hash function.
        if self.encryption["R"] >= 4 and not self.encryption.get("EncryptMetadata", True):
            psw_hash.update(b"\xff\xff\xff\xff")

        # g) Finish the hash.
        # h) If the handler is revision 3 or greater, for 50 times, take the output from
        #    the previous MD5 hash and pass the first "key length" bytes of the output
        #    as input to a new MD5 hash.
        if self.encryption["R"] >= 3:
            for _ in range(50):
                psw_hash = md5(psw_hash.digest()[: self.key_length])

        # i) Truncate the final hash to "key length" bytes and return.
        return psw_hash.digest()[: self.key_length]

    def compute_owner_password(self, owner_password: bytes, user_password: bytes) -> bytes:
        """Computes the O (``owner_password``) value in the Encrypt dictionary according
        to § 7.6.4.4.2, "Algorithm 3: Computing the encryption dictionary's O-entry value
        (revision 4 and earlier)".

        As a fallback in case there is no owner password, a ``user_password`` must also
        be specified.
        """

        # a) Pad or truncate the password string to exactly 32 bytes. The password string
        #    is the owner password, or in case there is none, the user password.
        padded = pad_password(owner_password or user_password)

        # b) Initialize the MD5 hash function with the result as input.
        owner_digest = md5(padded).digest()

        # c) If the handler is revision 3 or greater, for 50 times, pass the result
        #    of the output digest as the input of a new MD5 hash.
        if self.encryption["R"] >= 3:
            for _ in range(50):
                owner_digest = md5(owner_digest).digest()

        # d) Create the RC4 file encryption key by truncating the result to "key length".
        owner_cipher = owner_digest[: self.key_length]

        # e) Pad or truncate the user password string.
        padded_user_psw = pad_password(user_password)

        # f) Encrypt the result of (e) using ARC4 with the key generated in (d)
        arc4 = self._get_provider("ARC4")
        owner_crypt = arc4(owner_cipher).encrypt(padded_user_psw)

        # g) If the handler is revision 3 or greater, for 19 times, take the output from
        #    the previous invocation of the ARC4 function and pass it as input to a new
        #    invocation; use a file encryption key generated by taking each byte of the
        #    encryption key obtained in step (d) and performing an XOR operation between
        #    that byte and the single-byte value of the iteration counter.
        if self.encryption["R"] >= 3:
            for i in range(1, 20):
                owner_crypt = arc4(bytearray(b ^ i for b in owner_cipher)).encrypt(owner_crypt)

        # h) Return the resulting owner password.
        return owner_crypt

    def compute_user_password(self, password: bytes) -> bytes:
        """Computes the U (user password) value in the Encrypt dictionary according to
        the algorithms for revision 2 (Algorithm 4 in § 7.6.4.4.3) and revisions 3 and 4
        (Algorithm 5 in § 7.6.4.4.4).
        """

        arc4 = self._get_provider("ARC4")

        # a) Create a file encryption key based on the user password.
        #    This applies for both algorithms.
        encr_key = self.compute_encryption_key(password)

        if self.encryption["R"] == 2:
            # b) Encrypt the 32 byte padding string with RC4 using the key from step (a)
            padding_crypt = arc4(encr_key).encrypt(PASSWORD_PADDING)

            # c) We are done!
            return padding_crypt
        else:
            # b) Initialize the MD5 hash function with the 32-byte padding string.
            # c) Pass the first element of the file identifier array and finish.
            padded_id_hash = md5(PASSWORD_PADDING + ensure_bytes(self.ids[0]))

            # d) Encrypt the digest from (c) using ARC4 with the key from (a)
            user_cipher = arc4(encr_key).encrypt(padded_id_hash.digest())

            # e) Same process as step (g) from 7.6.4.4.2, but with the user password instead.
            for i in range(1, 20):
                user_cipher = arc4(bytearray(b ^ i for b in encr_key)).encrypt(user_cipher)

            # f) Pad the string and return.
            return pad_password(user_cipher)

    def authenticate_user_password(self, password: bytes) -> tuple[bytes, bool]:
        """Authenticates the provided user ``password`` according to § 7.6.4.4.5,
        "Algorithm 6: Authenticating the user password (Security handlers of revision
        4 and earlier)".

        Returns a tuple of two values: the encryption key that should decrypt the
        document and whether authentication was successful.
        """

        arc4 = self._get_provider("ARC4")

        # a) Perform everything but the last step from Algorithms 4 and 5.
        # Algorithms 4 and 5, step (a)
        encryption_key = self.compute_encryption_key(password)
        stored_password = ensure_bytes(self.encryption["U"])

        if self.encryption["R"] == 2:
            # Algorithm 4, step (b)
            user_cipher = arc4(encryption_key).encrypt(PASSWORD_PADDING)

            # b) If the result of step (a) is equal to the value of the encryption
            #    dictionary's U entry, the password supplied is the correct user
            #    password and the file encryption key from (a) shall be used to
            #    decrypt the document.

            return (encryption_key, True) if stored_password == user_cipher else (b"", False)
        else:
            # Algorithm 5, steps (b) and (c)
            padded_id_hash = md5(PASSWORD_PADDING + ensure_bytes(self.ids[0]))
            # Algorithm 5, step (d)
            user_cipher = arc4(encryption_key).encrypt(padded_id_hash.digest())

            # Algorithm 5, step (e)
            for i in range(1, 20):
                user_cipher = arc4(bytearray(b ^ i for b in encryption_key)).encrypt(user_cipher)

            # b) For the comparison, both values -- the stored password and the
            #    computed one -- shall be truncated to 16 bytes.
            return (
                (encryption_key, True) if stored_password[:16] == user_cipher[:16] else (b"", False)
            )

    def authenticate_owner_password(self, password: bytes) -> tuple[bytes, bool]:
        """Authenticates the provided owner ``password`` (or user ``password`` if none)
        according to § 7.6.4.4.6, "Algorithm 7: Authenticating the owner password
        (Security handlers of revision 4 and earlier)".

        Returns a tuple of two values: the encryption key that should decrypt the
        document and whether authentication was successful.
        """
        # a) Perform steps (a) to (d) from Algorithm 3 to compute a file encryption key
        #    from the supplied password string.
        padded_password = pad_password(password)
        digest = md5(padded_password).digest()
        if self.encryption["R"] >= 3:
            for _ in range(50):
                digest = md5(digest).digest()

        cipher_key = digest[: self.key_length]

        user_cipher = ensure_bytes(self.encryption["O"])
        arc4 = self._get_provider("ARC4")

        if self.encryption["R"] == 2:
            # b) If the handler is revision 2, decrypt the O value from the encryption
            #    dictionary using the computed encryption key as the key.
            user_cipher = arc4(cipher_key).decrypt(user_cipher)
        else:
            # b) If the handler is revision 3 or greater, for 20 times, decrypt the
            #    encryption dictionary's O entry (first iteration) or the output from the
            #    previous iteration (subsequent iterations), using an ARC4 function with a
            #    key generated by taking the original key from step (a) and performing an
            #    XOR between each byte of the key and the single byte value of the
            #    iteration counter (from 19 to 0).
            for i in range(19, -1, -1):
                user_cipher = arc4(bytearray(b ^ i for b in cipher_key)).encrypt(user_cipher)

        # c) The result of step (b) is presumably the user password. If authentication of
        #    the user password succeeds, the supplied password is the owner password.
        return self.authenticate_user_password(user_cipher)

    def compute_object_crypt(
        self,
        encryption_key: bytes,
        contents: Encryptable,
        reference: PdfReference,
        *,
        crypt_filter: PdfDictionary | None = None,
    ) -> tuple[CryptMethod, bytes, bytes]:
        """Computes all parameters needed to encrypt or decrypt ``contents`` according to
        § 7.6.3.2, "Algorithm 1: Encryption of data using the RC4 and AES algorithms".

        This algorithm is only applicable for Encrypt versions 1 through 4 (deprecated in
        PDF 2.0). Version 5 uses a simpler algorithm described in § 7.6.3.2.

        Arguments:
            encryption_key (bytes):
                An encryption key generated by the algorithm implemented in
                :meth:`.compute_encryption_key`.

            contents (PdfStream | PdfHexString | bytes):
                The contents to encrypt/decrypt. The type of object will determine what
                crypt filter will be used for decryption (StmF for streams, StrF for
                hex and literal strings).

            reference (PdfReference):
                The reference of either the object itself (in the case of a stream) or
                the object containing it (in the case of a string).

            crypt_filter (PdfDictionary, optional, keyword only):
                The specific crypt filter to be referenced when decrypting the document.
                If not specified, the default for this type of ``contents`` will be used.

        Returns a tuple of 3 values specifying, in order, the crypt method to apply
        (AES-CBC or ARC4), the key to use with this method, and the data to encrypt or
        decrypt.
        """
        # a) Obtain the object number and generation number from the object identifier of
        #    the contents to encrypt. This is satisfied by the "reference" argument.
        # b) For all strings and streams without crypt filter specifier; treating
        #    treating the object number and generation number as binary integers,
        #    extend the original "key length" file encryption key by 5 bytes by
        #    appending the low-order 3 bytes of the object number and the low-order 2
        #    bytes of the generation number, in that order, low-order byte first.
        generation = reference.generation.to_bytes(4, "little")
        object_number = reference.object_number.to_bytes(4, "little")
        extended_key = encryption_key + object_number[:3] + generation[:2]

        # b) If using the AES algorithm, extend the file encryption key an additional
        # 4 bytes by adding the value "sAlT".
        method = (
            self._get_cfm_method(crypt_filter) if crypt_filter else self._get_crypt_method(contents)
        )
        if method == "AESV2":
            extended_key += bytes([0x73, 0x41, 0x6C, 0x54])

        # c) Initialise the MD5 hash function with the result of step (b) as input.
        # d) Use the first "key length" + 5 bytes, up to a maximum of 16 bytes,
        #    as the key of the encryption algorithm.
        crypt_key = md5(extended_key).digest()[: self.key_length + 5][:16]

        if isinstance(contents, PdfStream):
            data = contents.raw
        elif isinstance(contents, PdfHexString):
            data = contents.value
        elif isinstance(contents, bytes):
            data = contents
        else:
            raise TypeError("'contents' argument must be a PDF stream or string.")

        return (method, crypt_key, data)

    def encrypt_object(
        self,
        encryption_key: bytes,
        contents: Encryptable,
        reference: PdfReference,
        *,
        crypt_filter: PdfDictionary | None = None,
    ) -> bytes:
        """Encrypts the specified ``contents`` according to § 7.6.3.2. For details on
        parameters, see :meth:`.compute_object_crypt`."""

        crypt_method, key, decrypted = self.compute_object_crypt(
            encryption_key, contents, reference, crypt_filter=crypt_filter
        )

        return self._get_provider(crypt_method)(key).encrypt(decrypted)

    def decrypt_object(
        self,
        encryption_key: bytes,
        contents: Encryptable,
        reference: PdfReference,
        *,
        crypt_filter: PdfDictionary | None = None,
    ) -> bytes:
        """Decrypts the specified ``contents`` according to § 7.6.3.2. For details on
        parameters, see :meth:`.compute_object_crypt`."""

        crypt_method, key, encrypted = self.compute_object_crypt(
            encryption_key, contents, reference, crypt_filter=crypt_filter
        )

        return self._get_provider(crypt_method)(key).decrypt(encrypted)

    def _get_provider(self, name: str) -> type[CryptProvider]:
        provider = CRYPT_PROVIDERS.get(name)
        if provider is None:
            raise MissingCryptProviderError(
                f"No crypt provider available for {name!r}. You must register one or "
                f"install a compatible module."
            )

        return provider

    def _get_crypt_method(self, contents: Encryptable) -> CryptMethod:
        if self.encryption.get("V", 0) != 4:
            # ARC4 is assumed given that can only be specified if V = 4. It is definitely
            # not Identity because the document wouldn't be encrypted in that case.
            return "ARC4"

        if isinstance(contents, PdfStream):
            cf_name = self.encryption.get("StmF", PdfName(b"Identity"))
        elif isinstance(contents, (bytes, PdfHexString)):
            cf_name = self.encryption.get("StrF", PdfName(b"Identity"))
        else:
            raise TypeError("'contents' argument must be a PDF stream or string.")

        if cf_name.value == b"Identity":
            return "Identity"  # No processing needed

        crypt_filters = self.encryption.get("CF", {})
        crypter = crypt_filters.get(cf_name.value.decode(), {})

        return self._get_cfm_method(crypter)

    def _get_cfm_method(self, crypt_filter: PdfDictionary) -> CryptMethod:
        cf_name = crypt_filter.get("CFM", PdfName(b"Identity"))

        if cf_name.value == b"Identity":
            return "Identity"
        elif cf_name.value == b"AESV2":
            return "AESV2"
        elif cf_name.value == b"V2":
            return "ARC4"

        raise ValueError(f"Unknown crypt filter for Standard security handler: {cf_name.value!r}")
