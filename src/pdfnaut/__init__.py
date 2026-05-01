"""
pdfnaut is a Python library for reading and writing PDFs.
"""

from __future__ import annotations

from .common.metadata import MetadataCopyDirection
from .cos import PdfParser, PdfSerializer, PdfTokenizer
from .document import PdfDocument

__all__ = ("PdfParser", "PdfTokenizer", "PdfSerializer", "PdfDocument", "MetadataCopyDirection")

__name__ = "pdfnaut"
__version__ = "0.11.1"
__description__ = "Explore PDFs with ease"
__license__ = "Apache-2.0"
