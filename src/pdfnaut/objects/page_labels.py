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
        """Returns the page label, within this range, corresponding to relative
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


class PageLabelTree(NumberTree[PageLabelRange]):
    """A page label tree for a document."""

    def __init__(self, data: PdfDictionary, *, pdf: "PdfDocument") -> None:
        """Initializes a page label tree.

        Arguments:
            data: The :class:`PdfDictionary` object defining the page label tree.
            pdf: The :class:`PdfDocument` object associated with the page label tree.
        """
        super().__init__()
        self._raw = data
        self._pdf = pdf

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} {list(k for k, _ in self.walk())}>"

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
        """Returns the page label corresponding to zero-based page index ``index``.

        Consistent with :meth:`.get_all`, :meth:`.get_label_for` will return the
        page label in decimal Arabic numbering if the document specifies no page
        labels.

        Raises:
            IndexError:
                the page index is out of bounds.

            ValueError:
                the document has page labels but does not define them for all
                pages in the document, as required by the PDF spec.
        """

        if page < 0 or page >= len(self._pdf.pages):
            raise IndexError("page index out of range")

        if not self.items():
            default_range = PageLabelRange(style=PageNumberingStyle.DECIMAL_ARABIC)
            return default_range.get_label(page)

        for start_index, label_range in reversed(list(self.items())):
            if page >= start_index:
                return label_range.get_label(page - start_index)

        raise ValueError(f"no label for page index {page}")

    def get_ranges(self) -> Generator[tuple[PageLabelRange, int, int]]:
        """Yields a list of all page label ranges in the document.

        Yielded are tuples of ``(range, start, end)`` which, in order, include the
        page labelling range, the start page index (inclusive), and the end page
        index (exclusive).
        """

        # pairwise where last item is (n, None)
        a, b = tee(self.items())

        first_label = next(b, None)
        if first_label is None:
            return

        labels = zip_longest(a, b)

        for cur_label, next_label in labels:
            if next_label is None:
                next_label = (-1, None)

            start_index, label_range = cur_label
            end_index, _ = next_label

            if end_index == -1:
                end_index = len(self._pdf.pages)

            yield (label_range, start_index, end_index)

    def get_all(self) -> Generator[str]:
        """Yields a list of all page labels in the document.

        :meth:`.get_all` returns a page label for each of the document's pages.
        If the document does not specify page labels, :meth:`.get_all` will return
        page labels in decimal Arabic numbering (1, 2, 3, 4, 5, ...).
        """

        if not self.items():
            default_range = PageLabelRange(style=PageNumberingStyle.DECIMAL_ARABIC)
            for page_idx in range(len(self._pdf.pages)):
                yield default_range.get_label(page_idx)

            return

        for label_range, start, end in self.get_ranges():
            for index in range(end - start):
                yield label_range.get_label(index)

    def get_labels_in_range(self, start: int) -> Generator[str]:
        """Yields a list of all page labels within the page labelling range defined
        at ``start``.

        Raises :exc:`ValueError` if no page labelling range was defined at ``start``.
        """

        for label_range, range_start, range_end in self.get_ranges():
            if range_start != start:
                continue

            for index in range(range_end - range_start):
                yield label_range.get_label(index)
            return

        raise ValueError(f"no page label range defined at {start}")
