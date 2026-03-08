from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Literal, cast

from typing_extensions import Self

from pdfnaut.cos.objects import PdfArray, PdfHexString, PdfName, PdfNull, PdfObject, PdfReference

if TYPE_CHECKING:
    from pdfnaut.objects import Page

DestinationKind = Literal["XYZ", "Fit", "FitH", "FitV", "FitR", "FitB", "FitBH", "FitBV"]


def nullify(*objs: PdfObject | None) -> list[PdfObject]:
    return [obj if obj is not None else PdfNull() for obj in objs]


class Destination(PdfArray):
    """A explicit destination points to a page within a PDF document with a specified
    location and zoom factor.

    See ISO 32000-2:2020 § 12.3.2 "Destinations" for details.
    """

    @classmethod
    def xyz(
        cls,
        page: Page,
        left: int | float | None = None,
        top: int | float | None = None,
        zoom: int | float | None = None,
    ) -> Self:
        """Creates a coordinate destination to ``page`` with the coordinates (``left``, ``top``)
        positioned at the upper-left corner of the window and the contents of the page magnified
        by the specified ``zoom`` factor.

        Omitting these parameters means that the current value shall remain unchanged.
        """
        if page.indirect_ref is None:
            raise ValueError("page must be in document")

        return cls([page.indirect_ref, PdfName(b"XYZ"), *nullify(left, top, zoom)])

    @classmethod
    def fit(cls, page: Page) -> Self:
        """Creates a destination to ``page`` with its contents magnified enough to fit
        the entire page within the window."""
        if page.indirect_ref is None:
            raise ValueError("page must be in document")

        return cls([page.indirect_ref, PdfName(b"Fit")])

    @classmethod
    def fit_horizontal(cls, page: Page, top: int | float | None = None) -> Self:
        """Creates a destination to ``page`` with its contents magnified enough to fit the
        entire page within the window horizontally and the top edge of the window positioned
        at the vertical coordinate ``top``."""
        if page.indirect_ref is None:
            raise ValueError("page must be in document")

        return cls([page.indirect_ref, PdfName(b"FitH"), *nullify(top)])

    @classmethod
    def fit_vertical(cls, page: Page, left: int | float | None = None) -> Self:
        """Creates a destination to ``page`` with its contents magnified enough to fit the
        entire page within the window vertically and the left edge of the window positioned
        at the horizontal coordinate ``left``."""
        if page.indirect_ref is None:
            raise ValueError("page must be in document")

        return cls([page.indirect_ref, PdfName(b"FitV"), *nullify(left)])

    @classmethod
    def fit_rectangle(
        cls,
        page: Page,
        left: int | float,
        bottom: int | float,
        right: int | float,
        top: int | float,
    ) -> Self:
        """Creates a destination to ``page`` with its contents magnified enough to fit the
        rectangle formed by the coordinates ``left``, ``bottom``, ``right``, and ``top``.
        """
        if page.indirect_ref is None:
            raise ValueError("page must be in document")

        return cls([page.indirect_ref, PdfName(b"FitR"), left, bottom, right, top])

    @classmethod
    def fit_bbox(cls, page: Page) -> Self:
        """Creates a destination to ``page`` with its contents magnified enough to fit the
        page bounding box."""
        if page.indirect_ref is None:
            raise ValueError("page must be in document")

        return cls([page.indirect_ref, PdfName(b"FitB")])

    @classmethod
    def fit_bbox_horizontal(cls, page: Page, top: int | float | None = None) -> Self:
        """Creates a destination to ``page`` with its contents magnified enough to fit the
        entire bounding box of the page within the window horizontally and the top edge of
        the window positioned at the vertical coordinate ``top``."""
        if page.indirect_ref is None:
            raise ValueError("page must be in document")

        return cls([page.indirect_ref, PdfName(b"FitBH"), *nullify(top)])

    @classmethod
    def fit_bbox_vertical(cls, page: Page, left: int | float | None = None) -> Self:
        """Creates a destination to ``page`` with its contents magnified enough to fit the
        entire bounding box of the page within the window vertically and the left edge of
        the window positioned at the horizontal coordinate ``left``."""
        if page.indirect_ref is None:
            raise ValueError("page must be in document")

        return cls([page.indirect_ref, PdfName(b"FitBV"), *nullify(left)])

    @property
    def page(self) -> Page:
        """The page the destination jumps to."""
        page_ref = cast(PdfReference, self.data[0])
        return Page.from_dict(page_ref.get(), indirect_ref=page_ref)

    @property
    def kind(self) -> DestinationKind:
        """The kind of destination."""
        name = cast(PdfName, self[1]).value.decode()
        return cast(DestinationKind, name)

    @property
    def args(self) -> Sequence[PdfObject]:
        """The arguments provided to the destination, such as coordinates or the zoom factor."""
        return self[2:]


NamedDestination = PdfName | PdfHexString | bytes
DestType = NamedDestination | Destination
