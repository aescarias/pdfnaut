# pyca/cryptography
from __future__ import annotations

import os

from cryptography.hazmat.decrepit.ciphers.algorithms import ARC4
from cryptography.hazmat.primitives.ciphers import Cipher, modes
from cryptography.hazmat.primitives.ciphers.algorithms import AES
from cryptography.hazmat.primitives.padding import PKCS7

from .base import CryptProvider


class PycaARC4Provider(CryptProvider):
    def encrypt(self, contents: bytes) -> bytes:
        arc4 = Cipher(ARC4(self.key), mode=None)
        return arc4.encryptor().update(contents)

    def decrypt(self, contents: bytes) -> bytes:
        arc4 = Cipher(ARC4(self.key), mode=None)
        return arc4.decryptor().update(contents)


class PycaAES128Provider(CryptProvider):
    def encrypt(self, contents: bytes) -> bytes:
        padded = PKCS7(16).padder().update(contents)
        iv = os.urandom(16)

        aes = Cipher(AES(self.key), mode=modes.CBC(iv))
        return iv + aes.encryptor().update(padded)

    def decrypt(self, contents: bytes) -> bytes:
        iv = contents[:16]
        encrypted = contents[16:]

        aes = Cipher(AES(self.key), mode=modes.CBC(iv))
        decrypted = aes.decryptor().update(encrypted)
        # last byte of decrypted indicates amount of trailing padding
        return decrypted[: -decrypted[-1]]
