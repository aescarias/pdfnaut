class PdfParseError(Exception):
    """Raised if unable to continue parsing the PDF"""
    pass


class PdfFilterError(Exception):
    """Raised if a filter is unable to decode a stream"""
    pass
