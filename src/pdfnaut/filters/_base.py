"""Base classes and utilities for processing stream filters."""

from typing import Protocol

from ..cos.objects import PdfDictionary


class PdfFilter(Protocol):
    """A stream filter as defined in ISO 32000-2:2020 § 7.4 "Filters"."""

    def decode(self, contents: bytes, *, params: PdfDictionary | None = None) -> bytes: ...
    def encode(self, contents: bytes, *, params: PdfDictionary | None = None) -> bytes: ...
