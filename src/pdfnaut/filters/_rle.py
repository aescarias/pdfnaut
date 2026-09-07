import logging
from itertools import groupby

from ..common._utils import batched
from ..cos.objects import PdfDictionary
from ._base import PdfFilter

LOGGER = logging.getLogger(__name__)


class RunLengthFilter(PdfFilter):
    """Filter for a form of byte-oriented run-length encoding (RLE) scheme resembling
    the Apple PackBits format (see ISO 32000-2:2020 § 7.4.5 "RunLengthDecode Filter").
    
    In this filter, data is formatted as a sequence of runs. Each run starts with a length 
    byte and is followed by 1 to 128 bytes of data.
    
    - If the length byte is in the range 0 to 127, the following ``length byte + 1`` \
        bytes shall be copied exactly.
    - If the length byte is in the range 129 to 255, the following byte shall be copied \
        ``257 - length`` bytes.
    - A length byte of 128 means EOD.

    Implementation note: encoding is performed using a threshold determined by the
    average of the lengths of each run. Values under such threshold are copied.
    Values over such threshold are repeated.

    This filter does not take any parameters. ``params`` will be ignored.
    """

    EOD = 128

    def decode(self, contents: bytes, *, params: PdfDictionary | None = None) -> bytes:
        pos = 0
        output = bytearray()

        while pos < len(contents):
            len_byte = contents[pos]
            pos += 1

            if 0 <= len_byte <= 127:
                output.extend(contents[pos : pos + len_byte + 1])
                pos += len_byte + 1
            elif 129 <= len_byte <= 255:
                output.extend(contents[pos] for _ in range(257 - len_byte))
                pos += 1
            elif len_byte == RunLengthFilter.EOD:
                break
        else:
            LOGGER.warning("RunLength: EOD marker not present, verify output")

        return bytes(output)

    def _encode_repeat_runs(self, runs: list[bytes]) -> bytes:
        output = bytearray()

        for run in runs:
            for batch in batched(run, 128):
                if not batch:
                    continue

                batch_len = len(batch)

                if batch_len < 2:
                    # 257 - 1 is 256 which wouldn't fit in a byte
                    # so simply use the "copying" method for this batch
                    len_byte = (batch_len - 1).to_bytes(1, "big")
                    data = b"".join(item.to_bytes(1, "big") for item in batch)
                    output.extend(len_byte + data)
                    continue

                # repeat the first char at desire
                len_byte = (257 - batch_len).to_bytes(1, "big")
                output.extend(len_byte + run[:1])

        return bytes(output)

    def _encode_copy_run(self, run: bytes) -> bytes:
        output = bytearray()

        for batch in batched(run, 128):
            if not batch:
                continue

            length_byte = (len(batch) - 1).to_bytes(1, "big")
            copy_bytes = b"".join(item.to_bytes(1, "big") for item in batch)

            output.extend(length_byte + copy_bytes)

        return bytes(output)

    def encode(self, contents: bytes, *, params: PdfDictionary | None = None) -> bytes:
        # perform typical rle first than decode it.
        runs = [(len(list(group)), val.to_bytes(1, "big")) for val, group in groupby(contents)]
        decoded_runs = (length * val for length, val in runs)

        # grouping runs by len helps merge runs together if the "copying" method is selected.
        runs_by_len = [(key, list(run)) for key, run in groupby(decoded_runs, key=len)]

        # values above this threshold are encoded using the "repeating" method.
        # values below are encoded using the "copying" method.
        # this is the first heuristic that came to mind and it seems to work decently.
        run_length_threshold = sum(length for length, _ in runs) / len(runs)

        final_output = bytearray()

        for run_length, runs in runs_by_len:
            if run_length > run_length_threshold:
                # above this threshold we use the "repeating" method
                final_output.extend(self._encode_repeat_runs(runs))
            else:
                # below this threshold, use the "copying" method
                # merge the runs first though
                final_output.extend(self._encode_copy_run(b"".join(runs)))

        final_output.append(RunLengthFilter.EOD)
        return bytes(final_output)
