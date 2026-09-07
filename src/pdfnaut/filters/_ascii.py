"""Implementation of the ASCII filters ASCIIHexDecode and ASCII85Decode.

ASCII filters are used to encode binary data into printable ASCII representations.
ASCII filters exist as a result of early versions of PDF (1.0 and 1.1) being text
formats. ASCII filters are generally used to aid inspection of PDF documents
without requiring a specialized binary editor.
"""

import binascii
import logging
from base64 import a85decode, a85encode, b16decode, b16encode

from ..cos.objects import PdfDictionary
from ..cos.tokenizer import WHITESPACE
from ..exceptions import PdfFilterError
from ._base import PdfFilter

LOGGER = logging.getLogger(__name__)


class ASCIIHexFilter(PdfFilter):
    """Filter for hexadecimal strings. EOD is '>'.

    See ISO 32000-2:2020 § 7.4.2 "ASCIIHexDecode Filter" for details.

    This filter does not take any parameters. ``params`` will be ignored.
    """

    EOD = b">"

    def decode(self, contents: bytes, *, params: PdfDictionary | None = None) -> bytes:
        eod = contents.find(ASCIIHexFilter.EOD)
        if eod == -1:
            LOGGER.warning("ASCIIHex: EOD marker not present, verify output")
            eod = len(contents)

        hex_data = bytearray(ch for ch in contents[:eod] if ch not in WHITESPACE)
        if len(hex_data) % 2 != 0:
            hex_data += b"0"

        try:
            return b16decode(hex_data, casefold=True)
        except binascii.Error as exc:
            raise PdfFilterError("ASCIIHex: invalid hex data") from exc

    def encode(self, contents: bytes, *, params: PdfDictionary | None = None) -> bytes:
        return b16encode(contents) + ASCIIHexFilter.EOD


class ASCII85Filter(PdfFilter):
    """Filter for Adobe's ASCII85 implementation. EOD is '~>'.

    See ISO 32000-2:2020 § 7.4.3 "ASCII85Decode Filter" for details.

    This filter does not take any parameters. ``params`` will be ignored.
    """

    def decode(self, contents: bytes, *, params: PdfDictionary | None = None) -> bytes:
        return a85decode(contents, ignorechars=WHITESPACE, adobe=True)

    def encode(self, contents: bytes, *, params: PdfDictionary | None = None) -> bytes:
        # we do not need the starting delimiter with PDFs
        return a85encode(contents, adobe=True)[2:]
