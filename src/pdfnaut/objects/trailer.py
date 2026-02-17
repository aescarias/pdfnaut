import datetime
from typing import Literal

from typing_extensions import Self

from ..common.dictmodels import dictmodel, field
from ..cos.objects.containers import PdfDictionary

TrappedState = Literal["True", "False", "Unknown"]


@dictmodel()
class Info(PdfDictionary):
    """Document-level metadata representing the structure described in § 14.3.3,
    "Document information dictionary".

    Since PDF 2.0, most of its keys have been deprecated in favor of their equivalents
    in the document-level metadata stream. The only keys not deprecated are the
    CreationDate and ModDate keys.
    """

    title: str | None = None
    """The document's title."""

    author: str | None = None
    """The name of the person who created the document."""

    subject: str | None = None
    """The subject or topic of the document."""

    keywords: str | None = None
    """Keywords associated with the document."""

    creator: str | None = None
    """If the document was converted to PDF from another format (ex. DOCX), the name of 
    the PDF processor that created the original document from which it was converted 
    (ex. Microsoft Word)."""

    producer: str | None = None
    """If the document was converted to PDF from another format (ex. PostScript), the name of 
    the PDF processor that converted it to PDF (ex. Adobe Distiller)."""

    creation_date_raw: str | None = field("CreationDate", init=False, default=None)
    """The date and time the document was created, as a text string."""

    modify_date_raw: str | None = field("ModDate", init=False, default=None)
    """The date and time the document was most recently modified, as a text string."""

    creation_date: datetime.datetime | None = field(default=None)
    """The date and time the document was created, in human-readable form."""

    modify_date: datetime.datetime | None = field("ModDate", default=None)
    """The date and time the document was most recently modified, in human-readable form."""

    trapped: TrappedState | None = None
    """A value reporting whether the document has been modified to include trapping 
    information (see § 14.11.6, "Trapping support")."""

    @classmethod
    def from_dict(cls, mapping: PdfDictionary) -> Self:
        dictionary = cls()
        dictionary.data = mapping.data

        return dictionary
