from __future__ import annotations

from typing import Any
from dataclasses import dataclass, field

from .base import PdfName
from ..filters import SUPPORTED_FILTERS


@dataclass
class PdfStream:
    """A stream object in a PDF"""
    details: dict[str, Any]
    raw: bytes = field(repr=False)

    def decompress(self) -> bytes:
        """Returns the contents of the stream decompressed.
        
        If a filter is not defined, it returns the original contents.
        If a filter is unsupported, it raises an exception."""
        filters = self.details.get("Filter")
        
        if filters is None:
            return self.raw
        
        if isinstance(filters, PdfName):
            filters = [filters]

        data = self.raw
        for filt in filters:
            if filt.value not in SUPPORTED_FILTERS:
                raise NotImplementedError(f"Filter {filt.value} is unsupported.")
            
            data = SUPPORTED_FILTERS[filt.value]().decode(
                contents=self.raw, params=self.details.get("DecodeParms", {}))

        return data
    
