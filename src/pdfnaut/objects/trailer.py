from __future__ import annotations

import enum
from typing import cast

from ..cos.objects.base import PdfHexString, PdfName, parse_text_string
from ..cos.objects.containers import PdfDictionary
from ..cos.objects.date import PdfDate


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

    def __init__(self, mapping: PdfDictionary) -> None:
        super().__init__(mapping)

        self.mapping = mapping

    @property
    def title(self) -> str | None:
        """The document's title."""
        if (title := cast("PdfHexString | bytes", self.get("Title"))) is not None:
            return parse_text_string(title)

    @property
    def author(self) -> str | None:
        """The name of the person who created the document."""
        if (author := cast("PdfHexString | bytes", self.get("Author"))) is not None:
            return parse_text_string(author)

    @property
    def subject(self) -> str | None:
        """The subject of the document."""
        if (subject := cast("PdfHexString | bytes", self.get("Subject"))) is not None:
            return parse_text_string(subject)

    @property
    def keywords(self) -> str | None:
        """Keywords associated with the document."""
        if (keywords := cast("PdfHexString | bytes", self.get("Keywords"))) is not None:
            return parse_text_string(keywords)

    @property
    def creator(self) -> str | None:
        """If the document was converted to PDF from another format, the name of the PDF
        processor that created the original document from which it was converted."""
        if (creator := cast("PdfHexString | bytes", self.get("Creator"))) is not None:
            return parse_text_string(creator)

    @property
    def producer(self) -> str | None:
        """If the document was converted to PDF from another format, the name of the PDF
        processor that converted it to PDF."""
        if (producer := cast("PdfHexString | bytes", self.get("Producer"))) is not None:
            return parse_text_string(producer)

    @property
    def creation_date_raw(self) -> str | None:
        """The date and time the document was created, in human-readable form."""
        if (creation_date := cast("PdfHexString | bytes", self.get("CreationDate"))) is not None:
            return parse_text_string(creation_date)

    @property
    def modify_date_raw(self) -> str | None:
        """The date and time the document was most recently modified, in human-readable form."""
        if (mod_date := cast("PdfHexString | bytes", self.get("ModDate"))) is not None:
            return parse_text_string(mod_date)

    @property
    def creation_date(self) -> PdfDate | None:
        """The date and time the document was created, in human-readable form."""
        if self.creation_date_raw:
            return PdfDate.from_pdf(self.creation_date_raw)

    @property
    def modify_date(self) -> PdfDate | None:
        """The date and time the document was most recently modified, in human-readable form."""
        if self.modify_date_raw:
            return PdfDate.from_pdf(self.modify_date_raw)

    @property
    def trapped(self) -> TrappedState:
        """A value indicating whether the document has been modified to include
        trapping information (``§ 14.11.6 Trapping support``)."""
        trapped_state = cast(PdfName | None, self.get("Trapped"))
        if trapped_state is None:
            return TrappedState.Unknown

        if trapped_state.value == b"True":
            return TrappedState.Yes
        elif trapped_state.value == b"False":
            return TrappedState.No

        return TrappedState.Unknown

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({super().__repr__()})"
