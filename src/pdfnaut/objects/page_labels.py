import enum
from collections.abc import Generator
from itertools import tee, zip_longest
from typing import TYPE_CHECKING, cast

from typing_extensions import Self

from pdfnaut.common._utils import decimal_to_letter, decimal_to_roman
from pdfnaut.common.dictmodels import dictmodel, field
from pdfnaut.cos.helpers import ensure, is_null_like
from pdfnaut.cos.objects.base import PdfName, PdfObject
from pdfnaut.cos.objects.containers import PdfArray, PdfDictionary
from pdfnaut.cos.objects.trees import NumberTree

if TYPE_CHECKING:
    from pdfnaut.document import PdfDocument


class PageNumberingStyle(str, enum.Enum):
    """The page numbering style."""

    DECIMAL_ARABIC = "D"
    """Decimal Arabic numerals (1, 2, 3, 4, 5, ...)."""

    UPPERCASE_ROMAN = "R"
    """Uppercase Roman numerals (I, II, III, IV, V, ...)."""

    LOWERCASE_ROMAN = "r"
    """Lowercase Roman numerals (i, ii, iii, iv, v, ...)."""

    UPPERCASE_LETTER = "A"
    """Uppercase letters / bijective base-26 (A, B, C, ..., Z, AA, AB, ...)."""

    LOWERCASE_LETTER = "a"
    """Lowercase letters / bijective base-26 (a, b, c, ..., z, aa, ab, ...)."""

    def __str__(self) -> str:
        return self.value


@dictmodel
class PageLabelRange(PdfDictionary):
    """A page labelling range describing how page labels are displayed for a consecutive
    range of pages. See ISO 32000-2:2020 § 12.4.2 "Page labels and indices" for details."""

    @staticmethod
    def _get_numbering(style_name: PdfName) -> PageNumberingStyle | str:
        name = cast(PdfName, style_name).value.decode()

        if name in list(PageNumberingStyle):
            return PageNumberingStyle(name)

        return name

    @staticmethod
    def _set_numbering(style: PageNumberingStyle | str | None) -> PdfName | None:
        if style is None:
            return

        return PdfName(style.encode())

    style: PageNumberingStyle | str | None = field(
        "S", default=None, encoder=_set_numbering, decoder=_get_numbering
    )
    """The numbering style to be used for the numeric portion of each page label.
    
    If none, the numeric portion shall be omitted.
    """

    prefix: str | None = field("P", default=None)
    """The label prefix for page labels in this range."""

    start: int = field("St", default=1)
    """The integer value of the numeric portion for the first page label in the range.
    This value shall be greater than or equal to 1."""

    @classmethod
    def from_dict(cls, mapping: PdfDictionary) -> Self:
        label = cls()
        label.data = mapping.data
        return label

    def get_label(self, index: int) -> str:
        """Returns the page label, within this range, corresponding to zero-based
        page index ``index``."""

        number = self.start + index
        label = self.prefix or ""

        if self.style == PageNumberingStyle.DECIMAL_ARABIC:
            label += str(number)
        elif self.style == PageNumberingStyle.UPPERCASE_ROMAN:
            label += decimal_to_roman(number)
        elif self.style == PageNumberingStyle.LOWERCASE_ROMAN:
            label += decimal_to_roman(number).lower()
        elif self.style == PageNumberingStyle.UPPERCASE_LETTER:
            label += decimal_to_letter(number)
        elif self.style == PageNumberingStyle.LOWERCASE_LETTER:
            label += decimal_to_letter(number).lower()

        return label


class PageLabelManager(NumberTree[PageLabelRange]):
    """A page label manager for a document."""

    def __init__(self, data: PdfDictionary, *, pdf: "PdfDocument") -> None:
        super().__init__()
        self._raw = data
        self._pdf = pdf

    def __repr__(self) -> str:
        return f"<PageLabelManager {list(k for k, _ in self.walk())}>"

    def new(self) -> None:
        """Clears the current page label tree."""
        self._pdf.catalog["PageLabels"] = self._raw = PdfDictionary()

    def _into_output_value(self, value: PdfObject) -> PageLabelRange:
        value = ensure(value, PdfDictionary)
        return PageLabelRange.from_dict(value)

    def _into_input_value(self, value: PageLabelRange) -> PdfObject:
        return PdfDictionary(value.data)

    def _set_items(self, items: PdfArray[PdfObject] | None) -> None:
        labels = self._pdf.catalog.get("PageLabels")
        if is_null_like(labels):
            self.new()

        return super()._set_items(items)

    def get_label_for(self, page: int) -> str:
        """Returns the page label corresponding to zero-based page index ``index``."""
        if page < 0 or page >= len(self._pdf.pages):
            raise IndexError("page index out of range")

        for start_index, label_range in reversed(list(self.items())):
            if page >= start_index:
                return label_range.get_label(page - start_index)

        raise ValueError(f"no label for page index {page}")

    def get_all(self) -> Generator[str]:
        """Yields a list of all page labels in the document."""

        # pairwise where last item is (n, None)
        a, b = tee(self.items())
        next(b, None)
        labels = zip_longest(a, b)

        for cur_label, next_label in labels:
            if next_label is None:
                next_label = (-1, None)

            start_index, label_range = cur_label
            end_index, _ = next_label

            if end_index == -1:
                end_index = len(self._pdf.pages)

            for index in range(end_index - start_index):
                yield label_range.get_label(index)
