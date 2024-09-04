from __future__ import annotations


class PdfParseError(Exception):
    """The parser was unable to continue parsing the PDF"""

    pass


class PdfFilterError(PdfParseError):
    """A filter was unable to decode a stream or is not supported"""

    pass


class PdfResolutionError(Exception):
    """The document was unable to resolve a reference because no resolution method
    is available."""

    pass


class PdfWriteError(Exception):
    """The writer was unable to serialize an object"""

    pass
