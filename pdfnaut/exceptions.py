class PdfParseError(Exception):
    """The parser was unable to continue parsing the PDF"""
    pass


class PdfFilterError(Exception):
    """A filter is unable to decode a stream or the filter is simply unsupported"""
    pass
