from __future__ import annotations

from typing import TYPE_CHECKING, Literal, TypedDict

from ..objects.base import PdfIndirectRef, PdfName

if TYPE_CHECKING:
    from typing_extensions import Required

    from pdfnaut.security_handler import StandardSecurityHandler


class LZWFlateParams(TypedDict, total=False):
    Predictor: int
    """A predictor algorithm to apply when encoding the data. (default=1)"""
    Colors: int
    """The amount of color components per sample."""
    BitsPerComponent: int
    """The amount of bits per each color component."""
    Columns: int
    """The amount of samples in each row."""
    EarlyChange: int # lzw only
    """(LZW) An indication of when to increase the code length."""


class CryptFilterParams(TypedDict, total=False):
    Type: PdfName[Literal[b"CryptFilterDecodeParms"]]
    """Shall be 'CryptFilterDecodeParms'"""
    Name: PdfName
    """The crypt filter to use when decrypting this stream."""
    # These are internal parameters received by pdfnaut
    _Handler: Required[StandardSecurityHandler]
    _IndirectRef: Required[PdfIndirectRef]
    _EncryptionKey: Required[bytes]

