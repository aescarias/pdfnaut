"""Implementation of the predictors used by the Flate and LZW filters to increase
sample predictability and improve compression.

ISO 32000-2:2020 § 7.4.4.4 "LZW and Flate predictor functions" describes two
predictor groups supported by the PDF standard:

- TIFF Predictor 2 "Horizontal differencing" defined in section 14 "Differencing
  Predictor" of the Adobe TIFF Revision 6.0 specification.
- The PNG filters defined in section 9 "Filtering" of the PNG Specification.

It shall be noted that PNG calls "filters" what PDF calls "predictors". PDF uses
the latter term to avoid confusion with stream filters.
"""

from enum import IntEnum
from math import ceil, floor
from typing import Literal

from pdfnaut.exceptions import PdfFilterError


class PNGPredictor(IntEnum):
    """The PNG predictor (filter) to be applied."""

    NONE = 0
    """PNG None"""

    SUB = 1
    """PNG Sub"""

    UP = 2
    """PNG Up"""

    AVERAGE = 3
    """PNG Average"""

    PAETH = 4
    """PNG Paeth"""

    OPTIMUM = 5
    """Not a predictor type by itself, but rather instructs the prediction process
    to select the best filter for each row."""


def predict_paeth(a: int, b: int, c: int) -> int:
    """Returns the predictor for a byte X using its three neighboring pixels
    ``a``, ``b``, and ``c`` as shown in Figure 20 of the PNG spec and according
    to the algorithm in section 9.4 "Filter type 4: Paeth" of the PNG spec.
    """
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


def process_png_row(
    row: bytearray,
    mode: Literal["filter", "recon"],
    predictor: PNGPredictor,
    previous: bytearray,
    sample_length: int,
) -> bytearray:
    """Filters or reconstructs a PNG row according to the section 9 "Filtering" of
    the PNG spec. Returns the processed row.

    Arguments:
        row:
            The row to be filtered or reconstructed.

        mode:
            The mode in which the row will be processed. Either "filter" to perform
            filtering or "recon" to perform reconstruction of a predicted row.

        predictor:
            The predictor to be applied or reconstructed (see :class:`PNGPredictor`).
            All predictors are allowed, except optimum.

        previous:
            The previous PNG row or scan line, used during prediction.

        sample_length:
            The length in bytes of each sample or pixel within the current and
            previous PNG rows.
    """
    if predictor == PNGPredictor.OPTIMUM:
        raise ValueError("predictor cannot be optimum")

    output_row = bytearray(row)

    for b in range(len(row)):
        # in Figure 19 of the PNG spec: cur_byte is x, byte_left is a,
        # byte_up is b, and byte_up_left is c
        if mode == "filter":
            cur_byte = row[b]
            byte_left = row[b - sample_length] if b >= sample_length else 0
        else:
            cur_byte = output_row[b]
            byte_left = output_row[b - sample_length] if b >= sample_length else 0

        byte_up = previous[b]
        byte_up_left = previous[b - sample_length] if b >= sample_length else 0

        if predictor == PNGPredictor.NONE:
            byte = cur_byte
        elif predictor == PNGPredictor.SUB:
            byte = cur_byte - byte_left if mode == "filter" else cur_byte + byte_left
        elif predictor == PNGPredictor.UP:
            byte = cur_byte - byte_up if mode == "filter" else cur_byte + byte_up
        elif predictor == PNGPredictor.AVERAGE:
            avg = floor((byte_left + byte_up) / 2)
            byte = cur_byte - avg if mode == "filter" else cur_byte + avg
        elif predictor == PNGPredictor.PAETH:
            paeth = predict_paeth(byte_left, byte_up, byte_up_left)
            byte = cur_byte - paeth if mode == "filter" else cur_byte + paeth

        output_row[b] = byte % 256 if predictor != PNGPredictor.NONE else byte

    return output_row


def undo_png_prediction(filtered: bytearray, *, columns: int, colors: int, bpc: int) -> bytearray:
    """Performs PNG reconstruction of a series of rows prefixed by a predictor byte.
    Returns the decoded rows.

    Args:
        filtered:
            The series of rows to be reconstructed.

        columns:
            The number of samples in each row.

        colors:
            The number of interleaved color components per sample.

        bpc:
            The number of bits per each color component in a sample.

    .. note::
        The ``columns``, ``colors``, and ``bpc`` arguments are used to determine
        the sample length and row length of the provided rows.
    """
    sample_length = ceil(colors * bpc / 8)
    row_length = sample_length * columns

    # the previous scan line is first initialized with null bytes.
    previous = bytearray(row_length)
    output = bytearray()

    # 1 + row_length because the first byte is the predictor type.
    for r in range(0, len(filtered), 1 + row_length):
        try:
            filter_type = PNGPredictor(filtered[r])
        except ValueError:
            raise PdfFilterError(
                f"encountered unknown filter type {filtered[r]} while processing predicted row"
            )

        row = filtered[r + 1 : r + 1 + row_length]
        decoded = process_png_row(row, "recon", filter_type, previous, sample_length)
        output.extend(decoded)

        previous = decoded.copy()

    return output


def apply_png_prediction(
    to_filter: bytearray, predictor: PNGPredictor, *, columns: int, colors: int, bpc: int
) -> bytearray:
    """Performs PNG filtering on a series of rows. Returns the encoded rows.

    Arguments:
        to_filter:
            The series of rows to be filtered.

        predictor:
            The predictor to apply on all rows of the provided sequence
            (see :class:`PNGPredictor`).

        columns:
            The number of samples in each row.

        colors:
            The number of interleaved color components per sample.

        bpc:
            The number of bits per each color component in a sample.

    .. note::
        The ``columns``, ``colors``, and ``bpc`` arguments are used to determine
        the sample length and row length of the provided rows.
    """
    sample_length = ceil(colors * bpc / 8)
    row_length = sample_length * columns

    # the previous scan line is first initialized with null bytes.
    previous = bytearray(row_length)
    output = bytearray()

    # TODO: Paeth is currently used in place of an optimum selection algorithm.
    if predictor == PNGPredictor.OPTIMUM:
        predictor = PNGPredictor.PAETH

    for r in range(0, len(to_filter), row_length):
        row = to_filter[r : r + row_length]

        encoded = process_png_row(row, "filter", predictor, previous, sample_length)
        output.extend([predictor, *encoded])

        previous = row.copy()

    return output
