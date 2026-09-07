import zlib
from math import ceil, floor

from ..cos.objects import PdfDictionary
from ..exceptions import PdfFilterError
from ._base import PdfFilter


class FlateFilter(PdfFilter):
    """Filter for zlib/deflate compression (see ISO 32000-2:2020 § 7.4.4 "LZWDecode and
    FlateDecode Filters").
    
    This filter supports predictors which can increase predictability of data and hence
    improve compression. 2 predictor groups are supported by the spec: the PNG filters 
    defined in § 9. Filtering of the PNG spec and TIFF Predictor 2 defined in the TIFF 
    6.0 spec and which is currently unimplemented.

    The predictor is specified by means of the Predictor key in ``params`` (default: 1).
    If the Predictor is not 1, the following parameters can be provided: 
    
    - **Colors**: Amount of color components per sample. Can be any value greater \
        than 1 (default: 1).
    - **BitsPerComponent**: Bit length of each of the color components. \
        Possible values are: 1, 2, 4, 8 (default), and 16.
    - **Columns**: Amount of samples per row. Can be any value greater than 1 \
        (default: 1).

    Given these values, the length of a sample in bytes is given by 
        ``Length(Sample) = ceil((Colors * BitsPerComponent) / 8)`` 
    and the length of a row is given by 
        ``Length(Row) = Length(Sample) * Columns``
    """

    def decode(self, contents: bytes, *, params: PdfDictionary[str, int] | None = None) -> bytes:  # pyright: ignore[reportIncompatibleMethodOverride]
        if params is None:
            params = PdfDictionary()

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

    def encode(self, contents: bytes, *, params: PdfDictionary[str, int] | None = None) -> bytes:  # pyright: ignore[reportIncompatibleMethodOverride]
        if params is None:
            params = PdfDictionary()

        if (predictor := params.get("Predictor", 1)) == 1:
            return zlib.compress(contents)

        cols = params.get("Columns", 1)
        colors = params.get("Colors", 1)
        bpc = params.get("BitsPerComponent", 8)

        if predictor == 2:
            raise PdfFilterError("FlateDecode: TIFF Predictor 2 not supported.")
        elif 10 <= predictor <= 15:
            return zlib.compress(
                self._apply_png_prediction(bytearray(contents), predictor - 10, cols, colors, bpc)
            )
        else:
            raise PdfFilterError(f"FlateDecode: Predictor {predictor} not supported.")

    def _predict_paeth(self, a: int, b: int, c: int) -> int:
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

    def _process_png_row(
        self,
        encode: bool,
        row: bytearray,
        filter_type: int,
        previous: bytearray,
        sample_length: int,
    ) -> bytearray:
        for c in range(len(row)):
            # (Fig. 19 in the PNG spec)
            # cur_byte is x, byte_left is a, byte_up is b, byte_up_left is c
            cur_byte = row[c]
            byte_left = row[c - sample_length] if c >= sample_length else 0
            byte_up = previous[c]
            byte_up_left = previous[c - sample_length] if c >= sample_length else 0

            if filter_type == 0:  # None
                char = cur_byte
            elif filter_type == 1:  # Sub
                char = cur_byte - byte_left if encode else cur_byte + byte_left
            elif filter_type == 2:  # Up
                char = cur_byte - byte_up if encode else cur_byte + byte_up
            elif filter_type == 3:  # Average
                avg = floor((byte_left + byte_up) / 2)
                char = cur_byte - avg if encode else cur_byte + avg
            elif filter_type == 4:  # Paeth
                paeth = self._predict_paeth(byte_left, byte_up, byte_up_left)
                char = cur_byte - paeth if encode else cur_byte + paeth
            else:
                raise PdfFilterError(
                    f"FlateDecode [png]: Row uses unsupported filter {filter_type}"
                )

            row[c] = char % 256 if filter_type else char

        return row

    def _undo_png_prediction(
        self, filtered: bytearray, cols: int, colors: int, bpc: int
    ) -> bytearray:
        sample_length = ceil(colors * bpc / 8)
        row_length = sample_length * cols

        previous = bytearray([0] * row_length)
        output = bytearray()

        # 1 + row_length because the first byte is the filter type
        for r in range(0, len(filtered), 1 + row_length):
            filter_type = filtered[r]
            decoded = self._process_png_row(
                False,
                filtered[r + 1 : r + 1 + row_length],
                filter_type,
                previous,
                sample_length,
            )
            output.extend(decoded)
            previous = decoded.copy()

        return output

    def _apply_png_prediction(
        self, to_filter: bytearray, filter_type: int, cols: int, colors: int, bpc: int
    ) -> bytearray:
        sample_length = ceil(colors * bpc / 8)
        row_length = sample_length * cols

        previous = bytearray([0] * row_length)
        output = bytearray()

        for r in range(0, len(to_filter), row_length):
            row = to_filter[r : r + row_length]
            if 0 <= filter_type <= 4:
                encoded = self._process_png_row(True, row, filter_type, previous, sample_length)
                output.extend(filter_type.to_bytes(1, "big") + encoded)
            elif filter_type == 5:  # Optimum
                # TODO: we will default optimum to be paeth for now
                # TODO: implement actual heuristic
                encoded = self._process_png_row(True, row, 4, previous, sample_length)
                output.extend((4).to_bytes(1, "big") + row)
            else:
                raise PdfFilterError(
                    f"FlateDecode [png]: Row uses unsupported filter {filter_type}"
                )

            previous = to_filter[r : r + row_length].copy()

        return output
