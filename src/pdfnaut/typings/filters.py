from __future__ import annotations

from typing import TypedDict, TYPE_CHECKING

from ..objects.base import PdfIndirectRef, PdfName

if TYPE_CHECKING:
    from pdfnaut.security_handler import StandardSecurityHandler
    from typing_extensions import Required


class LZWFlateParams(TypedDict, total=False):
    Predictor: int
    Colors: int
    BitsPerComponent: int
    Columns: int
    EarlyChange: int # lzw only


class CryptFilterParams(TypedDict, total=False):
    Type: PdfName
    Name: PdfName
    # These are internal parameters received by pdfnaut
    _Handler: Required[StandardSecurityHandler]
    _IndirectRef: Required[PdfIndirectRef]
    _EncryptionKey: Required[bytes]

