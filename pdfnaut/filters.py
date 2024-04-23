from __future__ import annotations

import zlib
from typing import Any, Protocol, cast
from math import floor, ceil
from base64 import b16decode, a85decode

from .parsers.simple import WHITESPACE
from .exceptions import PdfFilterError
from .objects.base import PdfName


def predict_paeth(a: int, b: int, c: int) -> int:
    """Runs Paeth prediction on a, b, and c as defined and implemented by 
    ``§ 9. Filtering`` in the PNG spec."""
    p = a + b - c
    pa = abs(p - a)
    pb = abs(p - b)
    pc = abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    elif pb <= pc:
        return b
    else:
        return c


class PdfFilter(Protocol):
    def decode(self, contents: bytes, *, params: dict[str, Any] | None = None) -> bytes:
        ...


class ASCIIHexFilter(PdfFilter):
    """Filter for hexadecimal strings (``§ 7.4.2 ASCIIHexDecode Filter``). EOD is ``>``.
    
    This filter does not take any parameters. ``params`` will be ignored.
    """

    def decode(self, contents: bytes, *, params: dict[str, Any] | None = None) -> bytes:
        if contents[-1:] != b">":
            raise PdfFilterError("ASCIIHex: EOD not at end of stream.")

        hexdata = bytearray(ch for ch in contents[:-1] if ch not in WHITESPACE)
        return b16decode(hexdata, casefold=True)


class ASCII85Filter(PdfFilter):
    """Filter for Adobe's ASCII85 implementation (``§ 7.4.3 ASCII85Decode Filter``).
    EOD is ``~>``.
    
    This filter does not take any parameters. ``params`` will be ignored.
    """

    def decode(self, contents: bytes, *, params: dict[str, Any] | None = None) -> bytes:
        return a85decode(contents, ignorechars=WHITESPACE, adobe=True)


class RunLengthFilter(PdfFilter):
    """Filter for a form of Run-Length Encoding or RLE (``§ 7.4.5 RunLengthDecode Filter``)
    
    In this filter, data is formatted as a sequence of runs. Each run starts with a length 
    byte and is followed by 1 to 128 bytes of data.
    
    - If the length byte is in the range 0 to 127, the following ``length byte + 1`` \
        bytes shall be copied exactly.
    - If the length byte is in the range 129 to 255, the following byte shall be copied \
        ``257 - length`` bytes.
    - A length byte of 128 means EOD.

    This filter does not take any parameters. ``params`` will be ignored.
    """

    def decode(self, contents: bytes, *, params: dict[str, Any] | None = None) -> bytes:    
        idx = 0
        output = bytes()
        
        while idx < len(contents):
            lenbyte = contents[idx]
            idx += 1

            if 0 <= lenbyte <= 127:
                output += contents[idx:idx + lenbyte + 1]
                idx += lenbyte + 1
            elif 129 <= lenbyte <= 255:
                output += bytes(contents[idx] for _ in range(257 - lenbyte))
                idx += 1
            elif lenbyte == 128:
                break
        
        return output


class FlateFilter(PdfFilter):
    """Filter for zlib/deflate compression (``§ 7.4.4 LZWDecode and FlateDecode Filters``).
    
    This filter supports predictors which can increase predictability of data and hence
    improve compression. 2 predictor groups are supported: the PNG filters specified in 
    ``§ 9. Filtering`` in the PNG spec and TIFF Predictor 2 specified in the TIFF 6.0 spec.

    The predictor is specified by means of the Predictor key in ``params`` (default: 1).
    If specified, the following parameters can be provided: 
    
    - **Colors**: Amount of color components per sample. Any value greater than 1 (default=1).
    - **BitsPerComponent**: Bit length of each of the color components. Values: 1, 2, 4, 8 (default), 16.
    - **Columns**: Amount of samples per row. Any value greater than 1 (default=1).

    Given these values, the length of a sample in bytes is obtained by 
        ``Length(Sample) = ceil((Colors * BitsPerComponent) / 8)`` 
    and the length of a row is obtained by 
        ``Length(Row) = Length(Sample) * Columns``
    """

    def decode(self, contents: bytes, *, params: dict[str, Any] | None = None) -> bytes:
        if params is None:
            params = {}

        uncomp = zlib.decompress(contents, 0)

        # No predictor applied, return uncompressed.
        if (predictor := params.get("Predictor", 1)) == 1:
            return uncomp

        cols = params.get("Columns", 1)
        colors = params.get("Colors", 1)
        bpc = params.get("BitsPerComponent", 8)

        if predictor == 2:
            raise PdfFilterError("FlateDecode: TIFF Predictor 2 not supported.")
        elif 10 <= predictor <= 15:
            return bytes(self._undo_png_prediction(bytearray(uncomp), cols, colors, bpc))
        else:
            raise PdfFilterError(f"FlateDecode: Predictor {predictor} not supported.")

    def _undo_png_prediction(self, filtered: bytearray, cols: int, colors: int, bpc: int) -> bytearray:
        sample_length = ceil(colors * bpc / 8)
        row_length = sample_length * cols

        previous = bytearray([0] * row_length) 
        output = bytearray()

        # 1 + row_length because the first byte is the filter type
        for r in range(0, len(filtered), 1 + row_length):
            filter_type = filtered[r]
            row = filtered[r + 1:r + 1 + row_length]

            for c in range(len(row)):
                # (Fig. 19) cur_byte is x, byte_left is a, byte_up is b, byte_up_left is c
                cur_byte = row[c]
                byte_left = row[c - sample_length] if c >= sample_length else 0
                byte_up = previous[c]
                byte_up_left = previous[c - sample_length] if c >= sample_length else 0

                if filter_type == 0: # None
                    char = cur_byte
                elif filter_type == 1: # Sub
                    char = cur_byte + byte_left
                elif filter_type == 2: # Up
                    char = cur_byte + byte_up
                elif filter_type == 3: # Average
                    char = cur_byte + floor((byte_left + byte_up) / 2)
                elif filter_type == 4: # Paeth
                    char = cur_byte + predict_paeth(byte_left, byte_up, byte_up_left)
                else:
                    raise PdfFilterError(f"FlateDecode [png]: Row uses unsupported filter {filter_type}")
                
                row[c] = char % 256 if filter_type else char
            
            output.extend(row)
            previous = row.copy()

        return output


# TODO: Please test
class CryptFetchFilter(PdfFilter):
    """Filter for encrypted streams (``§ 7.4.10 Crypt Filter``)
    
    This filter takes two optional parameters: ``Type``, which defines the decode parameters
    as being for this filter; and ``Name``, which defines what filter should be used to 
    decrypt the stream.

    This filter requires 3 additional parameters. These parameters are for exclusive 
    within ``pdfnaut`` and should not be written to the document.
    
    - **Handler**: An instance of the security handler.
    - **EncryptionKey**: The encryption key generated from the security handler.
    - **IndirectRef**: The indirect reference of the object to decrypt.
    """
    def decode(self, contents: bytes, *, params: dict[str, Any] | None = None) -> bytes:
        if params is None:
            params = {}
        
        cf_name = cast("PdfName | None", params.get("Name"))
        if cf_name is None or cf_name.value == b"Identity":
            return contents

        crypt_filter = params["Handler"].encryption.get("CF", {}).get(
            cf_name.value.decode(), params["Handler"].encryption.get("StmF")
        )

        return params["Handler"].decrypt_object(params["EncryptionKey"],
            contents, params["IndirectRef"], crypt_filter=crypt_filter)


SUPPORTED_FILTERS: dict[bytes, type[PdfFilter]] = {
    b"FlateDecode": FlateFilter,
    b"ASCII85Decode": ASCII85Filter,
    b"ASCIIHexDecode": ASCIIHexFilter,
    b"RunLengthDecode": RunLengthFilter,
    b"Crypt": CryptFetchFilter
}
