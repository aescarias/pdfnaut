"""Filters used when decoding (decompressing) streams. 

See ``§ 7.4 Filters`` in the PDF spec for details."""
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
    def decode(self, contents: bytes, *, params: dict[str, Any] | None = None) -> bytes:
        if contents[-1:] != b">":
            raise PdfFilterError("ASCIIHex: EOD not at end of stream.")

        hexdata = bytearray(ch for ch in contents[:-1] if ch not in WHITESPACE)
        return b16decode(hexdata, casefold=True)


class ASCII85Filter(PdfFilter):
    def decode(self, contents: bytes, *, params: dict[str, Any] | None = None) -> bytes:
        return a85decode(contents, ignorechars=WHITESPACE, adobe=True)


class FlateFilter(PdfFilter):
    def decode(self, contents: bytes, *, params: dict[str, Any] | None = None) -> bytes:
        if params is None:
            params = {}

        uncomp = zlib.decompress(contents, 0)

        # No predictor applied, return uncompressed.
        if (predictor := params.get("Predictor", 1)) == 1:
            return uncomp
    
        # A note on samples: A sample is understood as a "column" part of a row.
        #    - Columns determines the amount of samples per row.
        #    - Colors determines the amount of color components per sample.
        #    - Bits/comp. (bpc) determines the bit length of each of these components.
        # So the length of a column in bytes is understood as:
        #      len(sample) = ceil((colors * bpc) / 8)
        # (A ceiling is applied in case the output is floating-point)
        # And hence the length of a row is understood as:
        #      len(column) = len(sample) * cols
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


# 7.4.10 Crypt Filter
# TODO: Please test
class CryptFetchFilter(PdfFilter):
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
    b"Crypt": CryptFetchFilter
}
