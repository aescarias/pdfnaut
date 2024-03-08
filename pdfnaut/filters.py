"""Filters used when decoding (decompressing) streams. 

See ``§ 7.4 Filters`` in the PDF spec for details."""
from __future__ import annotations

import zlib
from typing import Any, Protocol, cast
from math import floor, ceil
from base64 import b16decode, a85decode

from .parsers.simple import WHITESPACE
from .exceptions import PdfFilterError
from .objects.base import PdfName, PdfIndirectRef


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
            return bytes(self._undo_tiff_prediction(bytearray(uncomp), cols, colors, bpc))
        elif 10 <= predictor <= 15:
            return bytes(self._undo_png_prediction(bytearray(uncomp), cols, colors, bpc))
        else:
            raise PdfFilterError(f"FlateDecode: Predictor {predictor} unsupported.")

    def _undo_png_prediction(self, filtered: bytearray, cols: int, colors: int, bpc: int) -> bytearray:
        sample_length = ceil(colors * bpc / 8)
        row_length = sample_length * cols

        previous = bytearray([0] * row_length) 
        output = bytearray()

        # 1 + row_length because the first byte is the filter type
        for r in range(0, len(filtered), 1 + row_length):
            filter_type = filtered[r]
            row = filtered[r + 1:r + 1 + row_length]

            for c in range(0, len(row), sample_length):
                # cur_sample is x, sample_left is a, sample_up is b, sample_up_left is c
                cur_sample = int.from_bytes(row[c:c + sample_length])
                sample_left = int.from_bytes(row[c - sample_length:c]) if c != 0 else 0
                sample_up = int.from_bytes(previous[c:c + sample_length])
                sample_up_left = int.from_bytes(previous[c - sample_length:c]) if c != 0 else 0

                if filter_type == 0: # None
                    char = cur_sample
                elif filter_type == 1: # Sub
                    char = cur_sample + sample_left
                elif filter_type == 2: # Up
                    char = cur_sample + sample_up
                elif filter_type == 3: # Average
                    char = cur_sample + floor((sample_left + sample_up) / 2)
                elif filter_type == 4: # Paeth
                    char = cur_sample + predict_paeth(sample_left, sample_up, sample_up_left)
                else:
                    raise PdfFilterError(f"FlateDecode: Row uses unsupported filter {filter_type}")

                row[c:c + sample_length] = (char % 256).to_bytes(sample_length)

            output.extend(row)
            previous = row.copy()

        return output
    
    def _undo_tiff_prediction(self, filtered: bytearray, cols: int, colors: int, bpc: int) -> bytearray:
        sample_length = ceil(colors * bpc / 8)
        row_length = sample_length * cols

        output = bytearray()

        for r in range(0, len(filtered), row_length):
            row = filtered[r:r + row_length]

            for c in range(0, len(row), sample_length):
                cur_sample = int.from_bytes(row[c:c + sample_length])
                sample_left = int.from_bytes(row[c - sample_length:c]) if c != 0 else 0

                char = cur_sample - sample_left
                row[c:c + sample_length] = (char % 256).to_bytes(sample_length)

            output.extend(row)

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
