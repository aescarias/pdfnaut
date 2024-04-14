"""
PDFnaut is a Python library for reading and writing PDFs at a low level.
"""

from .parsers import PdfParser
from .serializer import PdfSerializer

__all__ = ("PdfParser", "PdfSerializer")

__name__ = "pdfnaut"
__version__ = "0.1.1"
__description__ = "Explore PDFs with ease"
__license__ = "Apache 2.0"
