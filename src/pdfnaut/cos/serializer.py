from __future__ import annotations

from collections import defaultdict
from typing import Any, Literal, cast

from ..cos.objects.base import PdfComment, PdfHexString, PdfName, PdfNull, PdfObject, PdfReference
from ..cos.objects.containers import PdfArray, PdfDictionary
from ..cos.objects.stream import PdfStream
from ..cos.objects.xref import (
    CompressedXRefEntry,
    FreeXRefEntry,
    InUseXRefEntry,
    PdfXRefEntry,
    PdfXRefSection,
    PdfXRefSubsection,
)
from ..exceptions import PdfWriteError
from .tokenizer import STRING_ESCAPE


def serialize_comment(comment: PdfComment) -> bytes:
    return b"%" + comment.value


def serialize_null(_) -> bytes:
    return b"null"


def serialize_bool(boolean: bool) -> bytes:
    return b"true" if boolean else b"false"


def serialize_literal_string(byte_str: bytes, *, keep_ascii: bool = False) -> bytes:
    output = bytearray()
    escape = {v: k for k, v in STRING_ESCAPE.items()}

    # this is for handling unbalanced parentheses which must be escaped
    paren_stack = []
    unbalanced = []

    for pos, char in enumerate(byte_str):
        char = char.to_bytes(1, "big")
        if (esc := escape.get(char)) is not None and char not in b"()":
            output += esc
        elif keep_ascii and not char.isascii():
            # \ddd notation
            output += rf"\{ord(char):0>3o}".encode()
        else:
            output += char

        # Balanced parentheses require no special treatment
        if char == b"(":
            paren_stack.append(pos)
        elif char == b")":
            if paren_stack:
                paren_stack.pop()
            else:
                unbalanced.append(pos)

    unbalanced.extend(paren_stack)
    for pos in unbalanced:
        output.insert(pos, ord("\\"))

    return b"(" + output + b")"


def serialize_name(name: PdfName) -> bytes:
    output = b"/"

    for char in name.value:
        char = char.to_bytes(1, "big")
        if char.isalnum():
            output += char
        else:
            output += rf"#{ord(char):x}".encode()

    return output


def serialize_hex_string(string: PdfHexString) -> bytes:
    return b"<" + string.raw + b">"


def serialize_indirect_ref(reference: PdfReference) -> bytes:
    return f"{reference.object_number} {reference.generation} R".encode()


def serialize_numeric(number: int | float) -> bytes:
    return str(number).encode()


def serialize_array(array: PdfArray) -> bytes:
    return b"[" + b" ".join(serialize(item) for item in array.data) + b"]"


def serialize_dictionary(dictionary: PdfDictionary) -> bytes:
    items = []
    for key, val in dictionary.data.items():
        items.append(serialize(PdfName(key.encode())))
        items.append(serialize(val))

    return b"<<" + b" ".join(items) + b">>"


def serialize_stream(stream: PdfStream, *, eol: bytes) -> bytes:
    output = serialize_dictionary(stream.details) + eol
    output += b"stream" + eol
    output += stream.raw + eol
    output += b"endstream"

    return output


def serialize(
    object_: PdfObject | PdfStream | PdfComment, *, params: dict[str, Any] | None = None
) -> bytes:
    if params is None:
        params = {}

    if isinstance(object_, PdfComment):
        return serialize_comment(object_)
    elif isinstance(object_, PdfName):
        return serialize_name(object_)
    elif isinstance(object_, bytes):
        return serialize_literal_string(object_, keep_ascii=params.get("keep_ascii", False))
    elif isinstance(object_, bool):
        return serialize_bool(object_)
    elif isinstance(object_, PdfNull):
        return serialize_null(object_)
    elif isinstance(object_, PdfHexString):
        return serialize_hex_string(object_)
    elif isinstance(object_, PdfReference):
        return serialize_indirect_ref(object_)
    elif isinstance(object_, (int, float)):
        return serialize_numeric(object_)
    elif isinstance(object_, PdfArray):
        return serialize_array(object_)
    elif isinstance(object_, PdfDictionary):
        return serialize_dictionary(object_)
    elif isinstance(object_, PdfStream):
        return serialize_stream(object_, eol=params["eol"])

    raise PdfWriteError(f"Cannot serialize type {type(object_)}")


class PdfSerializer:
    """A serializer that is able to produce a valid PDF document.

    Arguments:
        eol (bytes, optional):
            The end-of-line to be used when serializing (CR, LF, or CRLF). Defaults to CRLF.
    """

    def __init__(self, *, eol: Literal[b"\r\n", b"\r", b"\n"] = b"\r\n") -> None:
        self.content = b""
        self.eol = eol

        self.objects: dict[tuple[int, int], PdfObject | PdfStream] = {}

    def write_header(self, version: str, *, with_binary_marker: bool = True) -> None:
        """Appends the PDF file header to the document (see § 7.5.2, "File Header").

        Arguments:
            version (str):
                A string representing the version of the PDF file.

            with_binary_marker (bool, optional):
                Whether to also append the recommended binary marker. Defaults to True.
        """

        comment = PdfComment(f"PDF-{version}".encode())
        self.content += serialize_comment(comment) + self.eol
        if with_binary_marker:
            marker = PdfComment(b"\xee\xe1\xf5\xf4")
            self.content += serialize_comment(marker) + self.eol

    def write_object(
        self, reference: PdfReference | tuple[int, int], contents: PdfObject | PdfStream
    ) -> int:
        """Appends an indirect object to the document.

        Arguments:
            reference (PdfReference | tuple[int, int]):
                The object number and generation to which the object should be assigned.

            contents (PdfObject | PdfStream):
                The contents to associate with the reference.

        Returns:
            The offset where the indirect object starts.
        """
        if isinstance(reference, tuple):
            reference = PdfReference(*reference)

        offset = len(self.content)
        self.content += f"{reference.object_number} {reference.generation} obj".encode() + self.eol
        self.content += serialize(contents, params={"eol": self.eol}) + self.eol
        self.content += b"endobj" + self.eol

        return offset

    def generate_xref_section(
        self, rows: list[tuple[int, PdfXRefEntry]]
    ) -> list[PdfXRefSubsection]:
        """Generates a cross-reference section from a list of ``rows``.

        Each row consists of a two-element tuple containing the object number of the
        XRef entry and the entry itself. The object numbers will determine the amount
        of subsections created and the entries within them.

        The output is a list of XRef subsections that can be then serialized by either
        :meth:`.write_standard_xref_section` or :meth:`.write_compressed_xref_section`.
        """
        rows = sorted(rows, key=lambda entry: entry[0])
        subsections: defaultdict[int, list[tuple[int, PdfXRefEntry]]] = defaultdict(list)

        first_obj_num = rows[0][0]

        for entry in rows:
            subsections[first_obj_num].append(entry)
            if len(subsections[first_obj_num]) <= 1:
                continue

            first_key, _ = subsections[first_obj_num][-1]
            second_key, _ = subsections[first_obj_num][-2]

            if first_key != second_key and abs(first_key - second_key) != 1:
                # The keys should belong in different subsections. Move the last key to a
                # different subsection and set that subsection for the rest of entries.
                last = subsections[first_obj_num].pop()
                first_obj_num = last[0]
                subsections[first_obj_num].append(last)

        return [
            PdfXRefSubsection(obj_num, len(entries), [ent for _, ent in entries])
            for obj_num, entries in subsections.items()
        ]

    def write_standard_xref_section(self, subsections: list[PdfXRefSubsection]) -> int:
        """Appends a standard XRef section (see § 7.5.4, "Cross-Reference Table") to the document.
        Returns the ``startxref`` offset that should be written to the document."""
        startxref = len(self.content)
        self.content += b"xref" + self.eol

        for subsection in subsections:
            self.content += f"{subsection.first_obj_number} {subsection.count}".encode() + self.eol

            for entry in subsection.entries:
                if isinstance(entry, InUseXRefEntry):
                    self.content += f"{entry.offset:0>10} {entry.generation:0>5} n".encode()
                elif isinstance(entry, FreeXRefEntry):
                    self.content += (
                        f"{entry.next_free_object:0>10} {entry.gen_if_used_again:0>5} f".encode()
                    )
                else:
                    raise PdfWriteError(
                        "Cannot write a compressed XRef entry within a standard XRef section."
                    )

                self.content += self.eol

        return startxref

    def write_compressed_xref_section(self, section: PdfXRefSection) -> int:
        """Appends a compressed XRef stream (see § 7.5.8, "Cross-Reference Streams") from
        ``section`` (to use as part of the extent) to the document.

        Returns the ``startxref`` offset that should be written to the document."""

        indices: PdfArray[PdfArray[int]] = PdfArray()
        table_rows: list[list[int]] = []

        for subsection in section.subsections:
            indices.append(PdfArray([subsection.first_obj_number, subsection.count]))

            for entry in subsection.entries:
                if isinstance(entry, FreeXRefEntry):
                    table_rows.append([0, entry.next_free_object, entry.gen_if_used_again])
                elif isinstance(entry, InUseXRefEntry):
                    table_rows.append([1, entry.offset, entry.generation])
                elif isinstance(entry, CompressedXRefEntry):
                    table_rows.append([2, entry.objstm_number, entry.index_within])

        widths = [
            (max(cast(list[int], column)).bit_length() + 7) // 8 or 1 for column in zip(*table_rows)
        ]
        contents = b""
        for row in table_rows:
            contents += b"".join(item.to_bytes(widths[idx], "big") for idx, item in enumerate(row))

        stream = PdfStream(
            PdfDictionary(
                Type=PdfName(b"XRef"),
                W=PdfArray(widths),
                Index=PdfArray(sum(indices, start=PdfArray())),
                Length=len(contents),
                **section.trailer.data,
            ),
            contents,
        )

        highest_objnum = sum(max(indices, key=sum))
        return self.write_object((highest_objnum, 0), stream)

    def write_trailer(
        self, trailer: PdfDictionary | None = None, startxref: int | None = None
    ) -> None:
        """Appends a standard ``trailer`` to the document (see § 7.5.5, "File Trailer")
        alongside the ``startxref`` offset.

        Both arguments are optional, indicating their presence in the appended output.
        If the XRef section written previously was an XRef stream, the trailer has
        already been written and should be ``None``.
        """
        if trailer is not None:
            self.content += b"trailer" + self.eol
            self.content += serialize_dictionary(trailer) + self.eol

        if startxref is not None:
            self.content += b"startxref" + self.eol
            self.content += str(startxref).encode() + self.eol

    def write_eof(self) -> None:
        """Appends the End-Of-File marker to the document."""
        self.content += b"%%EOF" + self.eol
