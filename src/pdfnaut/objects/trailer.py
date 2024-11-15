from __future__ import annotations

import datetime
import enum

from typing_extensions import Self

from .fields import DateField, EnumField, PdfDictionary, TextStringField


class TrappedState(enum.Enum):
    No = 0
    """Document has not been trapped"""
    Yes = 1
    """Document has been already trapped"""
    Unknown = 2
    """Unknown whether document is trapped partly, fully, or at all"""


class Info(PdfDictionary):
    """The document information dictionary (``§ 14.3.3 Document information dictionary``).

    It represents document-level metadata and is stored in the trailer. Since PDF 2.0,
    most of its function has been superseded by a document-level Metadata stream, with
    exception of the CreationDate and ModDate keys.
    """

    title = TextStringField("Title")
    """The document's title"""

    author = TextStringField("Author")
    """The name of the person who created the document."""

    subject = TextStringField("Subject")
    """The subject or topic of the document."""

    keywords = TextStringField("Keywords")
    """Keywords associated with the document."""

    creator = TextStringField("Creator")
    """If the document was converted to PDF from another format (ex: DOCX), the name of 
    the PDF processor that created the original document from which it was converted 
    (ex: Microsoft Word)."""

    producer = TextStringField("Producer")
    """If the document was converted to PDF from another format (ex: PostScript), the name of 
    the PDF processor that converted it to PDF (ex: Adobe Distiller)."""

    creation_date_raw = TextStringField("CreationDate")
    """The date and time the document was created, as a text string."""

    modify_date_raw = TextStringField("ModDate")
    """The date and time the document was most recently modified, as a text string."""

    creation_date = DateField("CreationDate")
    """The date and time the document was created, in human-readable form."""

    modify_date = DateField("ModDate")
    """The date and time the document was most recently modified, in human-readable form."""

    trapped = EnumField(
        "Trapped",
        {"True": TrappedState.Yes, "False": TrappedState.No, "Unknown": TrappedState.Unknown},
        TrappedState.Unknown,
    )
    """A value indicating whether the document has been modified to include trapping 
    information (``§ 14.11.6 Trapping support``)."""

    @classmethod
    def from_dict(cls, mapping: PdfDictionary) -> Self:
        dictionary = cls()
        dictionary.update()
        dictionary.data = mapping.data

        return dictionary

    def __init__(
        self,
        title: str | None = None,
        author: str | None = None,
        subject: str | None = None,
        keywords: str | None = None,
        creator: str | None = None,
        producer: str | None = None,
        creation_date: datetime.datetime | None = None,
        modify_date: datetime.datetime | None = None,
        trapped: TrappedState | None = None,
    ) -> None:
        super().__init__()

        # TODO: I'll rework this to be dataclassy some day.
        self._attrs = {
            "title": title,
            "author": author,
            "subject": subject,
            "keywords": keywords,
            "creator": creator,
            "producer": producer,
            "creation_date": creation_date,
            "modify_date": modify_date,
            "trapped": trapped,
        }

        for name, value in self._attrs.items():
            if value is not None:
                setattr(self, name, value)

    def __repr__(self) -> str:
        attributes = ", ".join(
            f"{attr}={value!r}"
            for attr in self._attrs
            if (value := getattr(self, attr, None)) is not None
        )

        return f"{self.__class__.__name__}({attributes})"
