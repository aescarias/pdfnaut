from __future__ import annotations

from hashlib import md5
from typing import Union, Protocol, Literal

from .typings.encryption import EncrCryptFilter, StandardEncrypt
from .objects import PdfHexString, PdfIndirectRef, PdfName, PdfStream


class CryptProvider(Protocol):
    key: bytes

    def __init__(self, key: bytes) -> None:
        self.key = key
    
    def encrypt(self, contents: bytes) -> bytes: ...
    def decrypt(self, contents: bytes) -> bytes: ...


class _IdentityProvider(CryptProvider):
    def encrypt(self, contents: bytes) -> bytes:
        return contents

    def decrypt(self, contents: bytes) -> bytes:
        return contents

try:
    from Crypto.Cipher import ARC4, AES
    from Crypto.Util import Padding

    class _DomeARC4Provider(CryptProvider):
        def decrypt(self, contents: bytes) -> bytes:
            return ARC4.new(self.key).decrypt(contents)
        
        def encrypt(self, contents: bytes) -> bytes:
            return ARC4.new(self.key).encrypt(contents)
        
    class _DomeAES128Provider(CryptProvider):
        def decrypt(self, contents: bytes) -> bytes:
            iv = contents[:16]
            encrypted = contents[16:]

            decrypted = AES.new(self.key, AES.MODE_CBC, iv).decrypt(encrypted)
            # last byte of decrypted indicates amount of trailing padding
            return decrypted[:-decrypted[-1]]
        
        def encrypt(self, contents: bytes) -> bytes:
            padded = Padding.pad(contents, 16, style="pkcs7")

            encryptor = AES.new(self.key, AES.MODE_CBC)
            return bytes(encryptor.iv) + encryptor.encrypt(padded)
    

    CRYPT_PROVIDERS = { "ARC4": _DomeARC4Provider, "AESV2": _DomeAES128Provider, 
                        "Identity": _IdentityProvider }
except ImportError:
    CRYPT_PROVIDERS = { "ARC4": None, "AESV2": None, "Identity": _IdentityProvider }


PASSWORD_PADDING = b'(\xbfN^Nu\x8aAd\x00NV\xff\xfa\x01\x08..\x00\xb6\xd0h>\x80/\x0c\xa9\xfedSiz'

def pad_password(password: bytes) -> bytes:
    return password[:32] + PASSWORD_PADDING[:32 - len(password)]

def get_value_from_bytes(contents: PdfHexString | bytes) -> bytes:
    return contents.value if isinstance(contents, PdfHexString) else contents


class StandardSecurityHandler:
    def __init__(self, encryption: StandardEncrypt, ids: list[PdfHexString | bytes]) -> None:
        self.encryption = encryption
        self.ids = ids

    @property
    def key_length(self) -> int:
        return self.encryption.get("Length", 40) // 8

    def compute_encryption_key(self, password: bytes) -> bytes:  
        """Computes an encryption key as defined in ``§ 7.6.3.3 Encryption Key Algorithm > 
        Algorithm 2: Computing an encryption key`` in the PDF spec."""      
        padded_password = pad_password(password)

        psw_hash = md5(padded_password)
        psw_hash.update(get_value_from_bytes(self.encryption["O"]))
        psw_hash.update(self.encryption["P"].to_bytes(4, "little", signed=True))
        psw_hash.update(get_value_from_bytes(self.ids[0]))

        if self.encryption.get("V", 0) >= 4 and not self.encryption.get("EncryptMetadata", True):
            psw_hash.update(b"\xff\xff\xff\xff")

        if self.encryption["R"] >= 3:
            for _ in range(50):
                psw_hash = md5(psw_hash.digest()[:self.key_length])

        return psw_hash.digest()[:self.key_length]
    
    def compute_owner_password(self, owner_password: bytes, user_password: bytes) -> bytes:
        """Computes the O (owner password) value in the Encrypt dictionary
        as defined in ``§ 7.6.3.3 Encryption Key Algorithm > Algorithm 3``"""   

        padded = pad_password(owner_password or user_password)
        owner_digest = md5(padded).digest()
        if self.encryption["R"] >= 3:
            for _ in range(50):
                owner_digest = md5(owner_digest).digest()

        owner_cipher = owner_digest[:self.key_length]
        
        padded_user_psw = pad_password(user_password)
        arc4 = self._get_provider("ARC4")
        owner_crypt = arc4(owner_cipher).encrypt(padded_user_psw)

        if self.encryption["R"] >= 3:
            for i in range(1, 20):
                owner_crypt = arc4(bytearray(b ^ i for b in owner_cipher)).encrypt(owner_crypt)

        return owner_crypt
    
    def compute_user_password(self, password: bytes) -> bytes:
        """Computes the U (owner password) value in the Encrypt dictionary
        as defined in ``§ 7.6.3.3 Encryption Key Algorithm > Algorithms 4 and 5``"""   

        encr_key = self.compute_encryption_key(password)
        arc4 = self._get_provider("ARC4")
        if self.encryption["R"] == 2:
            padding_crypt = arc4(encr_key).encrypt(PASSWORD_PADDING)
            return padding_crypt
        else: # rev 3
            padded_id_hash = md5(PASSWORD_PADDING + get_value_from_bytes(self.ids[0]))
            user_cipher = arc4(encr_key).encrypt(padded_id_hash.digest())

            for i in range(1, 20):
                user_cipher = arc4(bytearray(b ^ i for b in encr_key)).encrypt(user_cipher)

            return pad_password(user_cipher)
         
    def authenticate_user_password(self, password: bytes) -> tuple[bytes, bool]:  
        """Authenticates the provided user ``password`` according to Algorithm 4, 5, and 6 in 
        ``§ 7.6.3.4 Password Algorithms`` of the PDF spec.
        
        Returns:
            If the password was correct, a tuple of two values: the encryption key that should 
            decrypt the document and True. Otherwise, ``(b"", False)`` is returned."""
        encryption_key = self.compute_encryption_key(password)
        stored_password = get_value_from_bytes(self.encryption["U"])
        
        make_provider = self._get_provider("ARC4")

        # Algorithm 4
        if self.encryption["R"] == 2:
            user_cipher = make_provider(encryption_key).encrypt(PASSWORD_PADDING)
        
            return (encryption_key, True) if stored_password == user_cipher else (b"", False)
        # Algorithm 5
        else:
            padded_id_hash = md5(PASSWORD_PADDING + get_value_from_bytes(self.ids[0]))
            user_cipher = make_provider(encryption_key).encrypt(padded_id_hash.digest())

            for i in range(1, 20):
                user_cipher = make_provider(bytearray(b ^ i for b in encryption_key)).encrypt(user_cipher)

            return (encryption_key, True) if stored_password[:16] == user_cipher[:16] else (b"", False)

    def authenticate_owner_password(self, password: bytes) -> tuple[bytes, bool]:
        """Authenticates the provided owner ``password`` (or user password if none) 
        according to Algorithms 3 and 7 in ``§ 7.6.3.4 Password Algorithms`` of the PDF spec.
        
        Returns:
            If the password was correct, a tuple of two values: the encryption key that should 
            decrypt the document and True. Otherwise, ``(b"", False)`` is returned.
        """
        # (a) to (d) in Algorithm 3
        padded_password = pad_password(password)
        digest = md5(padded_password).digest()
        if self.encryption["R"] >= 3:
            for _ in range(50):
                digest = md5(digest).digest()

        cipher_key = digest[:self.key_length]
        user_cipher = get_value_from_bytes(self.encryption["O"])
        
        make_provider = self._get_provider("ARC4")
        # Algorithm 7
        if self.encryption["R"] == 2:
            user_cipher = make_provider(user_cipher).decrypt(user_cipher)
        else:
            for i in range(19, -1, -1):
                user_cipher = make_provider(bytearray(b ^ i for b in cipher_key)).encrypt(user_cipher)

        return self.authenticate_user_password(user_cipher)

    _Encryptable = Union[PdfStream, PdfHexString, bytes]
    def compute_object_crypt(self, encryption_key: bytes, contents: _Encryptable, 
                             reference: PdfIndirectRef, *, 
                             crypt_filter: EncrCryptFilter | None = None) -> tuple[CryptMethod, bytes, bytes]:
        """Computes all needed parameters to encrypt or decrypt ``contents`` according to 
        Algorithm 1 in ``§ 7.6.2 General Encryption Algorithm``
        
        Arguments:
            encryption_key (bytes):
                An encryption key generated by :meth:`.compute_encryption_key`

            contents (`PdfStream | PdfHexString | bytes`):
                The contents to encrypt/decrypt. The type of object will determine what 
                crypt filter will be used for decryption (StmF for streams, StrF for 
                hex and literal strings).

            reference (`PdfIndirectRef`):
                The reference of either the object itself (in the case of a stream) or 
                the object containing it (in the case of a string)

            crypt_filter (`dict[str, Any]`, optional):
                The specific crypt filter to be referenced when decrypting the document.
                If not specified, the default for this type of ``contents`` will be used.

        Returns:
            A tuple of 3 values: the crypt method to apply (AES CBC or ARC4), 
            the key to use with this method, and the data to encrypt/decrypt.
        """
        generation = reference.generation.to_bytes(4, "little")
        object_number = reference.object_number.to_bytes(4, "little")

        extended_key = encryption_key + object_number[:3] + generation[:2]

        method = self._get_cfm_method(crypt_filter) if crypt_filter else self._get_crypt_method(contents)
        if method == "AESV2":
            extended_key += bytes([0x73, 0x41, 0x6C, 0x54])

        crypt_key = md5(extended_key).digest()[:self.key_length + 5][:16]

        if isinstance(contents, PdfStream):
            data = contents.raw
        elif isinstance(contents, PdfHexString):
            data = contents.value
        elif isinstance(contents, bytes):
            data = contents
        else:
            raise TypeError("contents arg not a stream or string object")

        return (method, crypt_key, data)

    def encrypt_object(self, encryption_key: bytes, contents: _Encryptable, 
                       reference: PdfIndirectRef, *, 
                       crypt_filter: EncrCryptFilter | None = None) -> bytes:
        """Encrypts the specified ``contents`` according to Algorithm 1 in 
        ``§ 7.6.2 General Encryption Algorithm``.
        
        For details on arguments, please see :meth:`.compute_object_crypt`"""
        
        crypt_method, key, decrypted = self.compute_object_crypt(encryption_key, 
                                                                 contents, reference, 
                                                                 crypt_filter=crypt_filter)

        return self._get_provider(crypt_method)(key).encrypt(decrypted)

    def decrypt_object(self, encryption_key: bytes, contents: _Encryptable, 
                       reference: PdfIndirectRef, *, 
                       crypt_filter: EncrCryptFilter | None = None) -> bytes:
        """Decrypts the specified ``contents`` according to Algorithm 1 in 
        ``§ 7.6.2 General Encryption Algorithm``.
        
        For details on arguments, please see :meth:`.compute_object_crypt`"""
        
        crypt_method, key, encrypted = self.compute_object_crypt(encryption_key, 
                                                                 contents, reference,
                                                                 crypt_filter=crypt_filter)

        return self._get_provider(crypt_method)(key).decrypt(encrypted)

    def _get_provider(self, name: str) -> type[CryptProvider]:
        provider = CRYPT_PROVIDERS.get(name)
        if provider is None:
            raise NotImplementedError(f"Missing crypt provider for {name}. Register in CRYPT_PROVIDERS or install a compatible module.")
        return provider

    CryptMethod = Literal["Identity", "ARC4", "AESV2"]
    def _get_crypt_method(self, contents: _Encryptable) -> CryptMethod:
        if self.encryption.get("V", 0) != 4:
            # ARC4 is assumed given that can only be specified if V = 4. It is definitely
            # not Identity because the document wouldn't be encrypted in that case.
            return "ARC4"            

        if isinstance(contents, PdfStream):
            cf_name = self.encryption.get("StmF", PdfName(b"Identity"))
        elif isinstance(contents, (bytes, PdfHexString)):
            cf_name = self.encryption.get("StrF", PdfName(b"Identity"))
        else:
            raise TypeError("contents arg not a stream or string object")

        if cf_name.value == b"Identity":
            return "Identity" # No processing needed
        
        crypt_filters = self.encryption.get("CF", {})
        crypter = crypt_filters.get(cf_name.value.decode(), {})
        
        return self._get_cfm_method(crypter)

    def _get_cfm_method(self, crypt_filter: EncrCryptFilter) -> CryptMethod:
        cf_name = crypt_filter.get("CFM", PdfName(b"Identity"))
        if cf_name.value == b"Identity":
            return "Identity"
        elif cf_name.value == b"AESV2":
            return "AESV2"
        elif cf_name.value == b"V2":
            return "ARC4"

        raise NotImplementedError(f"{cf_name} not a supported crypt filter for the Standard security handler")
