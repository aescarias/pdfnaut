from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, cast

from typing_extensions import Self

from ...exceptions import PdfFilterError
from ...filters import SUPPORTED_FILTERS
from .base import PdfName, PdfNull, PdfObject
from .containers import PdfArray, PdfDictionary


@dataclass
class PdfStream:
    """A sequence of bytes that may be of unlimited length. Objects with a large
    amount of data like images or fonts are usually represented by streams
    (``§ 7.3.8 Stream objects``)."""

    details: PdfDictionary[str, PdfObject]
    """The stream extent dictionary (``§ 7.3.8.2 Stream extent``)."""

    raw: bytes = field(repr=False)
    """The raw data which is assumed to be encoded."""

    _crypt_params: dict[str, Any] = field(default_factory=dict, repr=False)
    """Parameters specific to the Crypt filter."""

    def decode(self) -> bytes:
        """Returns the decoded contents of the stream. If no filter is defined,
        it returns the original contents.

        Raises :class:`.pdfnaut.exceptions.PdfFilterError` if a filter is unsupported.
        """

        filters = cast("PdfName | PdfArray[PdfName] | None", self.details.get("Filter"))
        params = cast("PdfDictionary | PdfArray[PdfDictionary]", self.details.get("DecodeParms"))

        if filters is None:
            return self.raw

        if isinstance(filters, PdfName):
            filters = PdfArray([filters])

        if not isinstance(params, PdfArray):
            params = PdfArray([params])

        output = self.raw

        for filt, params in zip(filters, params):
            if filt.value not in SUPPORTED_FILTERS:
                raise PdfFilterError(f"{filt.value.decode()}: Filter is unsupported.")

            if isinstance(params, PdfNull) or params is None:
                params = PdfDictionary[str, PdfObject]()

            if filt.value == b"Crypt" and self._crypt_params.get("Handler"):
                params.update(self._crypt_params)

            output = SUPPORTED_FILTERS[filt.value]().decode(self.raw, params=params)

        return output

    @classmethod
    def create(
        cls,
        raw: bytes,
        details: PdfDictionary | None = None,
        crypt_params: PdfDictionary | None = None,
    ) -> Self:
        """Creates a stream from unencoded data ``raw`` applying the filter(s) specified in
        ``details``. The length of the encoded output will automatically be appended
        to ``details``.

        Raises :class:`.pdfnaut.exceptions.PdfFilterError` if a filter is unsupported.
        """

        if details is None:
            details = PdfDictionary()

        filters = cast("PdfName | PdfArray[PdfName] | None", details.get("Filter"))
        params = cast("PdfDictionary | PdfArray[PdfDictionary]", details.get("DecodeParms"))

        if filters is None:
            details["Length"] = len(raw)
            return cls(details, raw)

        if crypt_params is None:
            crypt_params = PdfDictionary()

        if isinstance(filters, PdfName):
            filters = PdfArray([filters])

        if not isinstance(params, PdfArray):
            params = PdfArray([params])

        # Filters are applied from last to first
        for filt, params in zip(reversed(filters), reversed(params)):
            if filt.value not in SUPPORTED_FILTERS:
                raise PdfFilterError(f"{filt.value.decode()}: Filter is unsupported.")

            if isinstance(params, PdfNull) or params is None:
                params = PdfDictionary()

            if filt.value == b"Crypt" and crypt_params.get("Handler"):
                params.update(crypt_params)

            raw = SUPPORTED_FILTERS[filt.value]().encode(raw, params=params)

        details["Length"] = len(raw)
        return cls(details, raw, cast(dict[str, Any], crypt_params.data))

    def modify(self, raw: bytes) -> None:
        """Modifies this stream in place by encoding the ``raw`` data according to
        the parameters specified in the stream's extent."""

        filters = cast("PdfName | PdfArray[PdfName] | None", self.details.get("Filter"))
        params = cast("PdfDictionary | PdfArray[PdfDictionary]", self.details.get("DecodeParms"))

        if filters is None:
            self.raw = raw
            self.details["Length"] = len(self.raw)
            return

        if isinstance(filters, PdfName):
            filters = PdfArray([filters])

        if not isinstance(params, PdfArray):
            params = PdfArray([params])

        # Filters are applied from last to first
        for filt, params in zip(reversed(filters), reversed(params)):
            if filt.value not in SUPPORTED_FILTERS:
                raise PdfFilterError(f"{filt.value.decode()}: Filter is unsupported.")

            if isinstance(params, PdfNull) or params is None:
                params = PdfDictionary()

            if filt.value == b"Crypt" and self._crypt_params.get("Handler"):
                params.update(self._crypt_params)

            raw = SUPPORTED_FILTERS[filt.value]().encode(raw, params=params)

        self.raw = raw
        self.details["Length"] = len(self.raw)

    def __hash__(self) -> int:
        if self._crypt_params is not None:
            params = PdfDictionary(self._crypt_params)
        else:
            params = None

        return hash((self.__class__, hash(self.details), self.raw, params))
