from __future__ import annotations

# NOTE: There's presumably some issues with how some Python 3.9 releases handle
#       inheriting from a Protocol subclass. The fix was merged in 3.10.
#       This is why this backport is used.
#       https://github.com/python/cpython/issues/89284
from typing_extensions import Protocol


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
