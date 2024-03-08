from hashlib import md5
from typing import Any, Union, Protocol, cast

from .objects import PdfHexString, PdfIndirectRef, PdfName, PdfStream


class CryptProvider(Protocol):
    key: bytes

    def __init__(self, key: bytes) -> None:
        self.key = key
    
    def encrypt(self, contents: bytes) -> bytes: ...
    def decrypt(self, contents: bytes) -> bytes: ...


try:
    from Crypto.Cipher import ARC4, AES
    from Crypto.Util import Padding

    class _DomeARC4Provider(CryptProvider):
        def decrypt(self, contents: bytes) -> bytes:
            return ARC4.new(self.key).decrypt(contents)
        
        def encrypt(self, contents: bytes) -> bytes:
            return ARC4.new(self.key).encrypt(contents)
        
    class _DomeAESCBCProvider(CryptProvider):
        def decrypt(self, contents: bytes) -> bytes:
            iv = contents[:16]
            encrypted = contents[16:]

            decrypted = AES.new(self.key, AES.MODE_CBC, iv).decrypt(encrypted)
            # last byte of decrypted indicates amount of trailing padding
            return decrypted[:-decrypted[-1]]
        
        def encrypt(self, contents: bytes) -> bytes:
            padded = Padding.pad(contents, 16, style="pkcs7")

            encryptor = AES.new(self.key, AES.MODE_CBC)
            return encryptor.iv + encryptor.encrypt(padded)
        
    CRYPT_PROVIDERS = { "ARC4": _DomeARC4Provider, "AES_CBC": _DomeAESCBCProvider }
except ImportError:
    CRYPT_PROVIDERS = { "ARC4": None, "AES_CBC": None }


PASSWORD_PADDING = b'(\xbfN^Nu\x8aAd\x00NV\xff\xfa\x01\x08..\x00\xb6\xd0h>\x80/\x0c\xa9\xfedSiz'


class StandardSecurityHandler:
    def __init__(self, encryption: dict[str, Any], ids: list[PdfHexString]) -> None:
        self.encryption = encryption
        self.ids = ids

    @property
    def key_length(self) -> int:
        return self.encryption.get("Length", 40) // 8

    def compute_encryption_key(self, password: bytes) -> bytes:  
        """Computes an encryption key as defined in ``§ 7.6.3.3 Encryption Key Algorithm`` > 
        ``Algorithm 2: Computing an encryption key`` in the PDF spec."""      
        padded_password = password[:32] + PASSWORD_PADDING[:32 - len(password)]

        psw_hash = md5(padded_password)
        psw_hash.update(_O.value if isinstance(_O := self.encryption["O"], PdfHexString) else _O)
        psw_hash.update(self.encryption["P"].to_bytes(4, "little", signed=True))
        psw_hash.update(self.ids[0].value)

        if self.encryption.get("V", 0) >= 4 and not self.encryption.get("EncryptMetadata", True):
            psw_hash.update(b"\xff\xff\xff\xff")

        if self.encryption["R"] >= 3:
            for _ in range(50):
                psw_hash = md5(psw_hash.digest()[:self.key_length])

        return psw_hash.digest()[:self.key_length]
    
    def authenticate_user_password(self, password: bytes) -> tuple[bytes, bool]:  
        """Authenticates the provided user ``password`` according to Algorithm 4, 5, and 6 in 
        ``§ 7.6.3.4 Password Algorithms`` of the PDF spec.
        
        Returns:
            If the password was correct, a tuple of two values: the encryption key that should 
            decrypt the document and True. Otherwise, ``(b"", False)`` is returned."""
        encryption_key = self.compute_encryption_key(password)
        stored_password = _U.value if isinstance(_U := self.encryption["U"], PdfHexString) else _U
        
        make_provider = self._get_provider("ARC4")

        # Algorithm 4
        if self.encryption["R"] == 2:
            user_cipher = make_provider(encryption_key).encrypt(PASSWORD_PADDING)
        
            return (encryption_key, True) if stored_password == user_cipher else (b"", False)
        # Algorithm 5
        else:
            padded_id_hash = md5(PASSWORD_PADDING + self.ids[0].value)
            user_cipher = make_provider(encryption_key).encrypt(padded_id_hash.digest())

            for i in range(1, 20):
                user_cipher = make_provider(bytearray(b ^ i for b in encryption_key)).encrypt(user_cipher)

            return (encryption_key, True) if stored_password[:16] == user_cipher[:16] else (b"", False)

    def authenticate_owner_password(self, password: bytes) -> tuple[bytes, bool]:
        """Authenticates the provided owner ``password`` (or user password if none) 
        according to Algorithms 3 and 7 in ``§ 7.6.3.4 Password Algorithms`` of the PDF spec.
        
        Returns:
            If the password was correct, a tuple of two values: the encryption key that should 
            decrypt the document and True. Otherwise, ``(b"", False)`` is returned."""
        # (a) to (d) in Algorithm 3
        padded_password = password[:32] + PASSWORD_PADDING[:32 - len(password)]
        digest = md5(padded_password).digest()
        if self.encryption["R"] >= 3:
            for _ in range(50):
                digest = md5(digest).digest()

        cipher_key = digest[:self.key_length]
        user_cipher = _O.value if isinstance(_O := self.encryption["O"], PdfHexString) else _O

        make_provider = self._get_provider("ARC4")
        # Algorithm 7
        if self.encryption["R"] == 2:
            user_cipher = make_provider(user_cipher).decrypt(user_cipher)
        else:
            for i in range(19, -1, -1):
                user_cipher = make_provider(bytearray(b ^ i for b in cipher_key)).encrypt(user_cipher)

        return self.authenticate_user_password(user_cipher)

    _Encryptable = Union[PdfStream, PdfHexString, bytes]
    def decrypt_object(self, encryption_key: bytes, contents: _Encryptable, reference: PdfIndirectRef, *, crypt_filter: dict[str, Any] | None = None) -> bytes:
        """Decrypts the specified `contents` object according to Algorithm 1 in ``§ 7.6.2 General Encryption Algorithm``
        
        Arguments:
            encryption_key (bytes):
                An encryption key generated by :meth:``.compute_encryption_key``

            contents (`PdfStream | PdfHexString | bytes`):
                The contents to decrypt. The type of object to decrypt will determine what crypt filter
                will be used for decryption (StmF for streams, StrF for hex and literal strings).

            reference (`PdfIndirectRef`):
                The reference of either the object itself (in the case of a stream) or the object 
                containing it (in the case of a string)

            crypt_filter (`dict[str, Any]`, optional):
                The specific crypt filter to be referenced when decrypting the document.
                If not specified, the default for this type of ``contents`` will be used.

        Returns:
            A decrypted bytes representation of ``contents``
        """
        generation = reference.generation.to_bytes(4, "little")
        object_number = reference.object_number.to_bytes(4, "little")

        extended_key = encryption_key + object_number[:3] + generation[:2]

        is_aes = self._is_aes_filter(crypt_filter or {}) or self._aes_applies_for(contents)
        if is_aes:
            extended_key += bytes([0x73, 0x41, 0x6C, 0x54])

        decryption_key = md5(extended_key).digest()[:self.key_length][:16]

        if isinstance(contents, PdfStream):
            encrypted = contents.raw
        elif isinstance(contents, PdfHexString):
            encrypted = contents.value
        elif isinstance(contents, bytes):
            encrypted = contents
        else:
            raise TypeError("contents arg not a stream or string object")

        if is_aes:
            return self._get_provider("AES_CBC")(decryption_key).decrypt(encrypted)
        return self._get_provider("ARC4")(decryption_key).decrypt(encrypted)

    def _get_provider(self, name: str) -> type[CryptProvider]:
        provider = CRYPT_PROVIDERS.get(name)
        if provider is None:
            raise NotImplementedError(f"Missing crypt provider for {name}. Register in CRYPT_PROVIDERS or install a compatible module.")
        return provider

    def _aes_applies_for(self, contents: _Encryptable) -> bool:
        if self.encryption["V"] != 4:
            return False
        
        if isinstance(contents, PdfStream):
            cf_name = cast(PdfName, self.encryption.get("StmF", PdfName(b"Identity")))
        elif isinstance(contents, (bytes, PdfHexString)):
            cf_name = cast(PdfName, self.encryption.get("StrF", PdfName(b"Identity")))
        else:
            raise TypeError("contents arg not a stream or string object")
        
        if cf_name.value == b"Identity":
            return False
            
        crypt_filters = cast("dict[str, Any]", self.encryption.get("CF", {}))
        
        crypter = crypt_filters.get(cf_name.value.decode(), {})
        return self._is_aes_filter(crypter)
    
    def _is_aes_filter(self, crypt_filter: dict[str, Any]) -> bool:
        return crypt_filter.get("CFM", PdfName(b"Identity")).value == b"AESV2"
