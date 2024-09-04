from __future__ import annotations

from dataclasses import dataclass, field
from typing import cast

from .base import PdfName, PdfNull, PdfObject
from .containers import PdfDictionary, PdfArray
from ...filters import SUPPORTED_FILTERS
from ...exceptions import PdfFilterError


@dataclass
class PdfStream:
    """A sequence of bytes that may be of unlimited length. Objects with a large 
    amount of data like images or fonts are usually represented by streams 
    (``§ 7.3.8 Stream objects``)."""

    details: PdfDictionary[str, PdfObject]
    """The stream extent dictionary (``§ 7.3.8.2 Stream extent``)."""
    
    raw: bytes = field(repr=False)
    """The raw data which is assumed to be encoded."""
    
    _crypt_params: PdfDictionary = field(default_factory=PdfDictionary, repr=False)
    """Parameters specific to the Crypt filter"""

    def decode(self) -> bytes:
        """Returns the decoded contents of the stream. If no filter is defined, 
        it returns the original contents.
        
        Raises :class:`.pdfnaut.exceptions.PdfFilterError` if a filter is unsupported."""

        filters = cast("PdfName | PdfArray[PdfName] | None", self.details.get("Filter"))
        params = cast("PdfDictionary | PdfArray[PdfDictionary]", 
                      self.details.get("DecodeParms"))
        
        if filters is None:
            return self.raw
        
        if isinstance(filters, PdfName):
            filters = PdfArray([filters])

        if not isinstance(params, PdfArray):
            params = PdfArray([params])

        output = self.raw

        for filt, params in zip(filters, params):
            if filt.value not in SUPPORTED_FILTERS:
                raise PdfFilterError(f"{filt.value.decode()}: Filter is unsupported.")
            
            if isinstance(params, PdfNull) or params is None:
                params = PdfDictionary[str, PdfObject]()
            
            if filt.value == b"Crypt" and self._crypt_params.get("Handler"):
                params.update(self._crypt_params)
            
            output = SUPPORTED_FILTERS[filt.value]().decode(self.raw, params=params)

        return output
