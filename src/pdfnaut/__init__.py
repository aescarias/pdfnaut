"""
PDFnaut is a Python library for reading and writing PDFs at a low level.
"""

from .parsers import PdfParser
from .serializer import PdfSerializer
from .document import PdfDocument

__all__ = ("PdfParser", "PdfSerializer", "PdfDocument")

__name__ = "pdfnaut"
__version__ = "0.2.0"
__description__ = "Explore PDFs with ease"
__license__ = "Apache 2.0"
