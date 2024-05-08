from __future__ import annotations

from typing import TypedDict, TYPE_CHECKING

from pdfnaut.objects import PdfName, PdfHexString

if TYPE_CHECKING:
    from typing_extensions import Required


class Encrypt(TypedDict, total=False):
    Filter: Required[PdfName]
    SubFilter: PdfName
    V: int
    Length: int
    CF: dict[str, EncrCryptFilter]
    StmF: PdfName
    StrF: PdfName
    EFF: PdfName


class EncrCryptFilter(TypedDict, total=False):
    Type: PdfName
    CFM: PdfName
    AuthEvent: PdfName
    Length: int


class StandardEncrypt(Encrypt, total=False):
    R: Required[int]
    O: Required[bytes | PdfHexString]
    U: Required[bytes | PdfHexString]
    P: Required[int]
    EncryptMetadata: bool    
