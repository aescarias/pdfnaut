from typing import Protocol


class CryptProvider(Protocol):
    key: bytes

    def __init__(self, key: bytes) -> None:
        self.key = key
    
    def encrypt(self, contents: bytes) -> bytes: ...
    def decrypt(self, contents: bytes) -> bytes: ...


class IdentityProvider(CryptProvider):
    """The Identity provider does nothing - same input, same output"""
    def encrypt(self, contents: bytes) -> bytes:
        return contents

    def decrypt(self, contents: bytes) -> bytes:
        return contents
