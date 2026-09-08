"""Implementation of the FlateDecode filter."""

import zlib

from ..cos.objects import PdfDictionary
from ..exceptions import PdfFilterError
from . import _predictors
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

        columns = params.get("Columns", 1)
        colors = params.get("Colors", 1)
        bpc = params.get("BitsPerComponent", 8)

        if predictor == 2:
            raise PdfFilterError("FlateDecode: TIFF Predictor 2 not supported.")
        elif 10 <= predictor <= 15:
            return bytes(
                _predictors.undo_png_prediction(
                    bytearray(uncomp), columns=columns, colors=colors, bpc=bpc
                )
            )
        else:
            raise PdfFilterError(f"FlateDecode: Predictor {predictor} not supported.")

    def encode(self, contents: bytes, *, params: PdfDictionary[str, int] | None = None) -> bytes:  # pyright: ignore[reportIncompatibleMethodOverride]
        if params is None:
            params = PdfDictionary()

        if (predictor := params.get("Predictor", 1)) == 1:
            return zlib.compress(contents)

        columns = params.get("Columns", 1)
        colors = params.get("Colors", 1)
        bpc = params.get("BitsPerComponent", 8)

        if predictor == 2:
            raise PdfFilterError("FlateDecode: TIFF Predictor 2 not supported.")
        elif 10 <= predictor <= 15:
            return zlib.compress(
                _predictors.apply_png_prediction(
                    bytearray(contents),
                    _predictors.PNGPredictor(predictor - 10),
                    columns=columns,
                    colors=colors,
                    bpc=bpc,
                )
            )
        else:
            raise PdfFilterError(f"FlateDecode: Predictor {predictor} not supported.")
