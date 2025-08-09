from __future__ import annotations

from typing import Literal, Union, cast

from typing_extensions import Self

from pdfnaut.cos.parser import PdfParser
from pdfnaut.objects.annotations import AnnotationList

from ..common.dictmodels import dictmodel, field
from ..cos.objects.base import PdfName, PdfReference
from ..cos.objects.containers import PdfArray, PdfDictionary
from ..cos.objects.stream import PdfStream
from ..cos.tokenizer import ContentStreamTokenizer

TabOrder = Literal["R", "C", "S", "A", "W"]


@dictmodel(init=False)
class Page(PdfDictionary):
    """A page in a PDF document (see § 7.7.3.3, "Page objects").

    Arguments:
        size (tuple[float, float]):
            The width and height of the physical medium in which the page should
            be printed or displayed. Values shall be provided in multiples of
            1/72 of an inch.

        pdf (PdfParser, optional):
            The PDF document that this page belongs to.

            In typical usage, this value need not be specified.
            pdfnaut will take care of populating it.

        indirect_ref (PdfReference, optional):
            The indirect reference that this page object is referred to by.

            As with ``pdf``, this value need not be specified in typical usage.
    """

    mediabox: PdfArray[float] = field("MediaBox")
    """A rectangle defining the boundaries of the physical medium in which the page
    should be printed or displayed."""

    cropbox: Union[PdfArray[float], None] = field("CropBox", default=None)
    """A rectangle defining the visible region of the page.
    
    If none, the cropbox is the same as the mediabox.
    """

    bleedbox: Union[PdfArray[float], None] = field("BleedBox", default=None)
    """A rectangle defining the region to which the contents of the page shall be 
    clipped when output in a production environment.
    
    If none, the bleedbox is the same as the cropbox.
    """

    trimbox: Union[PdfArray[float], None] = field("TrimBox", default=None)
    """A rectangle defining the intended dimensions of the finished page after trimming.

    If none, the trimbox is the same as the cropbox.
    """

    artbox: Union[PdfArray[float], None] = field("ArtBox", default=None)
    """A rectangle defining the extent of the page's meaningful content as intended 
    by the page's creator.
    
    If none, the artbox is the same as the cropbox.
    """

    resources: Union[PdfDictionary, None] = None
    """Resources required by the page contents.

    If the page requires no resources, this should return an empty resource
    dictionary. If the page inherits its resources from an ancestor,
    this should return None.
    """

    tab_order: Union[TabOrder, None] = field("Tabs", default=None)
    """(optional; PDF 1.5) The tab order to be used for annotations on the page.
    If present, it shall be one of the following values:

    - R: Row order
    - C: Column order
    - S: Logical structure order
    - A: Annotations array order (PDF 2.0)
    - W: Widget order (PDF 2.0)
    """

    user_unit: float = 1
    """The size of a user space unit, in multiples of 1/72 of an inch (by default, 1)."""

    rotation: int = field("Rotate", default=0)
    """The number of degrees by which the page shall be visually rotated clockwise.
    The value is a multiple of 90 (by default, 0)."""

    metadata: Union[PdfStream, None] = None
    """A metadata stream, generally written in XMP, containing information about this page."""

    @classmethod
    def from_dict(
        cls,
        mapping: PdfDictionary,
        pdf: PdfParser | None = None,
        indirect_ref: PdfReference | None = None,
    ) -> Self:
        dictionary = cls(size=(0, 0), pdf=pdf, indirect_ref=indirect_ref)
        dictionary.data = mapping.data

        return dictionary

    def __init__(
        self,
        size: tuple[float, float],
        *,
        pdf: PdfParser | None = None,
        indirect_ref: PdfReference | None = None,
    ) -> None:
        super().__init__()

        self.pdf = pdf
        self.indirect_ref = indirect_ref

        self["Type"] = PdfName(b"Page")
        self["MediaBox"] = PdfArray([0, 0, *size])

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} mediabox={self.mediabox!r} rotation={self.rotation!r}>"

    @property
    def content_stream(self) -> ContentStreamTokenizer | None:
        """An iterator over the instructions producing the contents of this page."""
        if "Contents" not in self:
            return

        contents = cast("PdfStream | PdfArray[PdfStream]", self["Contents"])

        if isinstance(contents, PdfArray):
            # when Contents is an array, it shall be concatenated into a single
            # content stream with at least one whitespace character in between.
            return ContentStreamTokenizer(b"\n".join(stm.decode() for stm in contents))

        return ContentStreamTokenizer(contents.decode())

    @property
    def annotations(self) -> AnnotationList | None:
        """All annotations associated with this page represented as instances of
        :class:`.Annotation` (see see § 12.5, "Annotations" in the PDF spec for details).

        If a page does not specify a list of annotations, this field is none.
        """

        if "Annots" not in self:
            return

        annots = cast(PdfArray, self["Annots"])
        return AnnotationList(annots, pdf=self.pdf)
