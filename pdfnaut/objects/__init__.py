from .base import PdfComment, PdfHexString, PdfIndirectRef, PdfName, PdfNull, PdfStream
from .xref import PdfXrefEntry, PdfXrefSubsection, PdfXrefTable

from typing import List, Union, Any, Dict

PdfObject = Union[
    bool, int, float, bytes, 
    List[Any], Dict[str, Any], 
    PdfHexString, PdfName, 
    PdfIndirectRef, PdfNull
]
