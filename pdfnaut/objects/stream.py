from __future__ import annotations

from typing import Any
from dataclasses import dataclass, field

from .base import PdfName, PdfNull
from ..filters import SUPPORTED_FILTERS
from ..exceptions import PdfFilterError


@dataclass
class PdfStream:
    """A stream object in a PDF"""
    details: dict[str, Any]
    raw: bytes = field(repr=False)

    def decompress(self) -> bytes:
        """Returns the contents of the stream decompressed.
        
        If no filter is defined, it returns the original contents.
        
        Raises :class:`PdfFilterError` if a filter is unsupported."""
        filters = self.details.get("Filter")
        params = self.details.get("DecodeParms")
        
        if filters is None:
            return self.raw
        
        if isinstance(filters, PdfName):
            filters = [filters]

        if not isinstance(params, list):
            params = [params]
                
        output = self.raw
        for filt, params in zip(filters, params):
            if filt.value not in SUPPORTED_FILTERS:
                raise PdfFilterError(f"{filt.value.decode()}: Filter is unsupported.")
            
            if isinstance(params, PdfNull):
                params = {}
                
            output = SUPPORTED_FILTERS[filt.value]().decode(self.raw, params=params)

        return output
