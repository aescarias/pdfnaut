# PyCryptodome
from Crypto.Cipher import AES, ARC4
from Crypto.Util import Padding

from .base import CryptProvider


class DomeARC4Provider(CryptProvider):
    def encrypt(self, contents: bytes) -> bytes:
        return ARC4.new(self.key).encrypt(contents)

    def decrypt(self, contents: bytes) -> bytes:
        return ARC4.new(self.key).decrypt(contents)


class DomeAES128Provider(CryptProvider):
    def encrypt(self, contents: bytes) -> bytes:
        padded = Padding.pad(contents, 16, style="pkcs7")

        encryptor = AES.new(self.key, AES.MODE_CBC)
        return bytes(encryptor.iv) + encryptor.encrypt(padded)

    def decrypt(self, contents: bytes) -> bytes:
        iv = contents[:16]
        encrypted = contents[16:]

        decrypted = AES.new(self.key, AES.MODE_CBC, iv).decrypt(encrypted)
        # last byte of decrypted indicates amount of trailing padding
        return decrypted[: -decrypted[-1]]
