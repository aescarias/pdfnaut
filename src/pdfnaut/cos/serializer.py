from __future__ import annotations

from collections import defaultdict
from typing import Any, Literal, Mapping

from ..exceptions import PdfWriteError
from ..objects.base import (PdfComment, PdfIndirectRef, PdfObject, PdfNull, PdfName,
                           PdfHexString)
from ..objects.stream import PdfStream
from ..objects.xref import (CompressedXRefEntry, FreeXRefEntry, InUseXRefEntry, 
                            PdfXRefSubsection, PdfXRefTable)
from ..typings.document import Trailer
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
        char = char.to_bytes(1)
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


def serialize_name(name: PdfName[bytes]) -> bytes:
    output = b"/"

    for char in name.value:
        char = char.to_bytes(1)
        if char.isalnum():
            output += char
        else:
            output += rf"#{ord(char):x}".encode()

    return output


def serialize_hex_string(string: PdfHexString) -> bytes:
    return b"<" + string.raw + b">"


def serialize_indirect_ref(reference: PdfIndirectRef) -> bytes:
    return f"{reference.object_number} {reference.generation} R".encode()


def serialize_numeric(number: int | float) -> bytes:
    return str(number).encode()


def serialize_array(array: list[Any]) -> bytes:
    return b"[" + b" ".join(serialize(item) for item in array) + b"]"


def serialize_dictionary(mapping: Mapping[str, Any]) -> bytes:
    items = []
    for k, v in mapping.items():
        items.append(serialize(PdfName(k.encode())))
        items.append(serialize(v))

    return b"<<" + b" ".join(items) + b">>"


def serialize_stream(stream: PdfStream, *, eol: bytes) -> bytes:
    output = serialize_dictionary(stream.details) + eol
    output += b"stream" + eol
    output += stream.raw + eol
    output += b"endstream"

    return output


def serialize(object_: PdfObject | PdfStream | PdfComment, *, 
              params: dict[str, Any] | None = None) -> bytes:
    if params is None:
        params = {}

    if isinstance(object_, PdfComment):
        return serialize_comment(object_)
    elif isinstance(object_, PdfName):
        return serialize_name(object_)
    elif isinstance(object_, bytes):
        return serialize_literal_string(object_, 
                                        keep_ascii=params.get("keep_ascii", False))
    elif isinstance(object_, bool):
        return serialize_bool(object_)
    elif isinstance(object_, PdfNull):
        return serialize_null(object_)
    elif isinstance(object_, PdfHexString):
        return serialize_hex_string(object_)
    elif isinstance(object_, PdfIndirectRef):
        return serialize_indirect_ref(object_)
    elif isinstance(object_, (int, float)):
        return serialize_numeric(object_)
    elif isinstance(object_, list):
        return serialize_array(object_)
    elif isinstance(object_, dict):
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
        """Appends the PDF file header to the document (``§ 7.5.2 File Header``).

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

    def write_object(self, reference: PdfIndirectRef | tuple[int, int],
                     contents: PdfObject | PdfStream) -> int:
        """Appends an indirect object to the document.

        Arguments:
            reference (:class:`PdfIndirectRef` | :class:`tuple[int, int]`):
                The object number and generation to which the object should be assigned.

            contents (:class:`PdfObject` | :class:`PdfStream`):
                The contents to associate with the reference.

        Returns:
            The offset where the indirect object starts.
        """
        if isinstance(reference, tuple):
            reference = PdfIndirectRef(*reference)

        offset = len(self.content)
        self.content += (
            f"{reference.object_number} {reference.generation} obj".encode() + self.eol
        )
        self.content += serialize(contents, params={"eol": self.eol}) + self.eol
        self.content += b"endobj" + self.eol

        return offset

    def generate_xref_table(self, rows: list[tuple[str, int, int, int]]) -> PdfXRefTable:
        """Generates a cross-reference table from a list of ``rows``.

        Each row is a tuple of 4 values: 
            - a string indicating the type: either "f" (free), "n" (in use), or "c" (compressed)
            - the object number
            - the next two values differ depending on the type:
                - if type is "f", the next free object and the generation if used again
                - if type is "n", the object's offset and generation
                - if type is "c", the object number of the object stream and the index of the \
                object within the stream.

        Returns:
            An XRef table that can be serialized by either :meth:`.write_standard_xref_table`
            or :meth:`.write_compressed_xref_table`.
        """
        table = PdfXRefTable([])
        rows = sorted(rows, key=lambda sl: sl[1])  # sl[1] = object number

        subsections = defaultdict(list)
        first_obj_num = rows[0][1]

        for entry in rows:
            subsections[first_obj_num].append(entry)
            if len(subsections[first_obj_num]) <= 1:
                continue

            _, first_key, *_ = subsections[first_obj_num][-1]
            _, second_key, *_ = subsections[first_obj_num][-2]

            if first_key != second_key and abs(first_key - second_key) != 1:
                # last = subsections[first_key].pop()
                last = subsections[first_obj_num].pop()
                first_obj_num = last[1]
                subsections[first_obj_num].append(last)

        for first_obj_num, raw_entries in subsections.items():
            entries = []
            for typ_, _obj_num, first_val, second_val in raw_entries:
                if typ_ == "f":
                    entries.append(FreeXRefEntry(first_val, second_val))
                elif typ_ == "c":
                    entries.append(CompressedXRefEntry(first_val, second_val))
                else:
                    entries.append(InUseXRefEntry(first_val, second_val))

            table.sections.append(
                PdfXRefSubsection(first_obj_num, len(entries), entries)
            )

        return table

    def write_standard_xref_table(self, table: PdfXRefTable) -> int:
        """Appends a standard XRef table (``§ 7.5.4 Cross-Reference Table``) to the document.
        Returns the ``startxref`` offset that should be written to the document."""
        startxref = len(self.content)
        self.content += b"xref" + self.eol

        for section in table.sections:
            self.content += f"{section.first_obj_number} {section.count}".encode() + self.eol
            for entry in section.entries:
                if isinstance(entry, InUseXRefEntry):
                    self.content += f"{entry.offset:0>10} {entry.generation:0>5} n".encode()
                elif isinstance(entry, FreeXRefEntry):
                    self.content += f"{entry.next_free_object:0>10} {entry.gen_if_used_again:0>5} f".encode()
                else:
                    raise PdfWriteError("Cannot write compressed XRef entry within standard table")
                self.content += self.eol               
        return startxref

    def write_compressed_xref_table(self, table: PdfXRefTable, trailer: Trailer) -> int:
        """Appends a compressed XRef stream (``§ 7.5.8 Cross-Reference Streams``) from 
        ``table`` and ``trailer`` (to use as part of the extent) to the document.
        Returns the ``startxref`` offset that should be written to the document."""
        indices = []
        table_rows: list[list[int]] = []

        for section in table.sections:
            indices.append([section.first_obj_number, section.count])

            for entry in section.entries:
                if isinstance(entry, FreeXRefEntry):
                    table_rows.append([0, entry.next_free_object, entry.gen_if_used_again])
                elif isinstance(entry, InUseXRefEntry):
                    table_rows.append([1, entry.offset, entry.generation])
                elif isinstance(entry, CompressedXRefEntry):
                    table_rows.append([2, entry.objstm_number, entry.index_within])

        widths = [(max(column).bit_length() + 7) // 8 or 1 for column in zip(*table_rows)]
        contents = b""
        for row in table_rows:
            contents += b"".join(item.to_bytes(widths[idx], "big") 
                                 for idx, item in enumerate(row))

        stream = PdfStream(
            {
                "Type": PdfName(b"XRef"), 
                "W": widths, 
                "Index": sum(indices, start=[]), 
                "Length": len(contents), 
                **trailer
            },
            contents
        )

        highest_objnum = sum(max(indices, key=sum))
        return self.write_object((highest_objnum, 0), stream)

    def write_trailer(self, trailer: Trailer | None = None, startxref: int | None = None) -> None:
        """Appends a standard ``trailer`` to the document (``§ 7.5.5 File Trailer``) 
        alongside the ``startxref`` offset.

        Both arguments are optional, indicating their presence in the appended output
        (the trailer could have been written previously, hence this option).
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
