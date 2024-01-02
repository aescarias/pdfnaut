import re
from typing import Any
from io import BytesIO

from ..objects.base import PdfNull, PdfIndirectRef, PdfObject
from ..objects.stream import PdfStream
from ..objects.xref import (
    PdfXRefEntry, PdfXRefSubsection, PdfXRefTable, PdfXRefEntry, FreeXRefEntry,
    CompressedXRefEntry, InUseXRefEntry
)

from ..exceptions import PdfParseError
from .simple import SimpleObjectParser


class PdfParser:
    """A parser that can completely parse a PDF document.
    
    It consumes the PDF's cross-reference tables and trailers. It merges the tables
    into a single one and provides an interface to individually parse
    each indirect object using :class:`SimpleObjectParser`."""

    def __init__(self, data: bytes) -> None:
        self._simple_parser = SimpleObjectParser(data)
        self._trailers: list[dict[str, Any]] = []

        self.update_xrefs: list[PdfXRefTable] = []
        """A list of all XRef tables in the document (the most recent first)"""

        # The below values are expected to be filled
        self.trailer: dict[str, Any] = {}
        """The most recent trailer in the PDF document"""

        self.xref: PdfXRefTable = PdfXRefTable([])
        """A cross-reference table with a single section that combines all 
        entries in each update XRef."""

        self.version = self.parse_header()
        """The document's PDF version as seen in the header."""

    def parse(self, start_xref: int | None = None) -> None:
        """Parses the entire document.
        
        It parses the most recent XRef table and trailer. If this trailer points 
        to a previous XRef, this function is called again with a ``start_xref``
        offset until no more XRefs are found.

        Arguments:
            start_xref (int, optional):
                An offset occurring before the ``startxref`` keyword.
        """
        # Get where the last (most recent) XRef is
        if start_xref is None:
            start_xref = self.lookup_xref_start()

        # Get the most recent XRef and trailer
        self._simple_parser.position = start_xref
        xref, trailer = self.parse_xref_and_trailer()

        self.update_xrefs.append(xref)
        self._trailers.append(trailer)

        if "Prev" in trailer:
            # More XRefs were found. Recursion!
            self._simple_parser.position = 0
            self.parse(trailer["Prev"])
        else:
            # That's it. Merge them together.
            self.xref = self.get_merged_xrefs()
            self.trailer = self._trailers[0]

    def parse_header(self) -> str:
        """Parse the %PDF-n.m header."""
        header = self._simple_parser.parse_comment()
        mat = re.match(rb"PDF-(?P<major>\d+).(?P<minor>\d+)", header.value)
        if mat:
            return f"{mat.group('major').decode()}.{mat.group('minor').decode()}"

        raise PdfParseError("Expected PDF header.")
    
    def get_merged_xrefs(self) -> PdfXRefTable:
        """Combines all update XRef tables in the document into a single table 
        with a single section containing all entries"""
        entry_map: dict[int, PdfXRefEntry] = {}

        for xref in self.update_xrefs[::-1]:
            for section in xref.sections:
                for idx, entry in enumerate(section.entries):
                    entry_map[section.first_obj_number + idx] = entry

        final_entries: list[PdfXRefEntry] = [None] * len(entry_map) # type: ignore
        for num, entry in entry_map.items():
            final_entries[num] = entry

        return PdfXRefTable([
            PdfXRefSubsection(0, self._trailers[0]["Size"], final_entries)
        ])

    def lookup_xref_start(self) -> int:
        """Scans through the PDF until it finds the XRef offset then returns it"""
        contents = bytearray()

        # The PDF spec tells us we need to parse from the end of the file
        # and the XRef comes first
        self._simple_parser.position = len(self._simple_parser.data) - 1

        while self._simple_parser.position > 0:
            contents.insert(0, ord(self._simple_parser.current))
            if contents.startswith(b"startxref"):
                break
            self._simple_parser.position -= 1
        
        if not contents.startswith(b"startxref"):
            raise PdfParseError("Cannot locate XRef table. 'startxref' offset missing.")
        
        # advance through the startxref, we know it's there.
        self._simple_parser.advance(9)
        self._simple_parser.advance_whitespace()

        return int(self._simple_parser.parse_numeric()) # startxref

    def parse_xref_and_trailer(self) -> tuple[PdfXRefTable, dict[str, Any]]:
        """Parses both the cross-reference table and the PDF trailer."""
        if self._simple_parser.current + self._simple_parser.peek(3) == b"xref":
            xref = self.parse_simple_xref()
            self._simple_parser.advance_whitespace()
            trailer = self.parse_simple_trailer()
            return xref, trailer
        elif re.match(rb"(?P<num>\d+)\s+(?P<gen>\d+)\s+obj", self._simple_parser.current_to_eol):
            return self.parse_compressed_xref()
        else:
            raise PdfParseError("XRef offset does not point to XRef table.")
        
    def parse_simple_trailer(self) -> dict[str, Any]:
        """Parses the PDF's trailer which is used to quickly locate other cross reference 
        tables and special objects"""
        self._simple_parser.advance(7) # past the 'trailer' keyword
        self._simple_parser.advance_whitespace()
        
        # next token is a dictionary
        trailer = self._simple_parser.parse_dictionary()
        return trailer

    def parse_simple_xref(self) -> PdfXRefTable:
        """Parses an uncompressed XRef table of the format specified in `§ 7.5.4 Cross-Reference Table`"""
        self._simple_parser.advance(4)
        self._simple_parser.advance_whitespace()

        table = PdfXRefTable([])

        while not self._simple_parser.at_end():
            # subsection
            subsection = re.match(rb"(?P<first_obj>\d+)\s(?P<count>\d+)", 
                                self._simple_parser.current_to_eol)
            if subsection is None:
                break
            self._simple_parser.advance(subsection.end())
            self._simple_parser.advance_whitespace()

            # xref entries
            entries: list[PdfXRefEntry] = []
            for i in range(int(subsection.group("count"))):
                entry = re.match(rb"(?P<offset>\d{10}) (?P<gen>\d{5}) (?P<status>f|n)", 
                    self._simple_parser.current + self._simple_parser.peek(19))
                if entry is None:
                    raise PdfParseError(f"Expected valid XRef entry at row {i + 1}")
                
                offset = int(entry.group("offset"))
                generation = int(entry.group("gen"))

                if entry.group("status") == b"n":
                    entries.append(InUseXRefEntry(offset, generation))
                else:
                    entries.append(FreeXRefEntry(offset, generation))

                self._simple_parser.advance(20)
            
            table.sections.append(PdfXRefSubsection(
                int(subsection.group("first_obj")),
                int(subsection.group("count")),
                entries
            ))
            
        return table

    def parse_compressed_xref(self) -> tuple[PdfXRefTable, dict[str, Any]]:
        """Parses a compressed cross-reference stream which includes both the table 
        and information from the PDF trailer."""
        xref_stream = self.parse_indirect_object(
            InUseXRefEntry(self._simple_parser.position, 0))
        assert isinstance(xref_stream, PdfStream)

        contents = BytesIO(xref_stream.decompress())

        xref_widths = xref_stream.details["W"]
        xref_indices = xref_stream.details.get("Index", [0, xref_stream.details["Size"]])

        table = PdfXRefTable([])

        for i in range(0, len(xref_indices), 2):
            section = PdfXRefSubsection(first_obj_number=xref_indices[i], 
                                        count=xref_indices[i + 1], 
                                        entries=[])
            
            for _ in range(section.count):
                field_type = int.from_bytes(contents.read(xref_widths[0]) or b'\x01')
                second = int.from_bytes(contents.read(xref_widths[1]))
                third = int.from_bytes(contents.read(xref_widths[2]))
                
                if field_type == 0:
                    section.entries.append(FreeXRefEntry(next_free_object=second, 
                                                         gen_if_used_again=third))
                elif field_type == 1:
                    section.entries.append(InUseXRefEntry(offset=second, generation=third))
                elif field_type == 2:
                    section.entries.append(CompressedXRefEntry(objstm_number=second, 
                                                               index_within=third))

            table.sections.append(section)

        return table, xref_stream.details

    def parse_indirect_object(self, xref_entry: InUseXRefEntry) -> PdfObject | PdfStream | None:
        """Parses an indirect object not within an object stream."""
        self._simple_parser.position = xref_entry.offset
        mat = re.match(rb"(?P<num>\d+)\s+(?P<gen>\d+)\s+obj", 
                       self._simple_parser.current_to_eol)
        if not mat:
            raise PdfParseError("Not an indirect object")
        
        self._simple_parser.advance(mat.end())
        self._simple_parser.advance_whitespace()

        tok: dict[str, Any] = self._simple_parser.next_token() # type: ignore
        self._simple_parser.advance_whitespace()

        # uh oh, a stream?
        if self._simple_parser.current + self._simple_parser.peek(5) == b"stream":   
            length = tok["Length"]
            if isinstance(length, PdfIndirectRef):
                _current = self._simple_parser.position
                length = self.resolve_reference(length)
                self._simple_parser.position = _current 
            if not isinstance(length, int):
                raise ValueError(f"Expected \\Length in stream extent to be of type Integer but got {type(length)} instead")

            return PdfStream(tok, self.parse_stream(xref_entry, length))
        return tok

    def parse_stream(self, xref_entry: InUseXRefEntry, extent: int) -> bytes:
        """Parses a PDF stream of length ``extent``"""
        self._simple_parser.advance(6) # past the 'stream'

        # If the current character is LF or CRLF (but not just CR), skip.
        pos, eol = self._simple_parser.next_eol()
        if pos == self._simple_parser.position and eol != "\r":
            self._simple_parser.advance(len(eol))

        contents = self._simple_parser.data[self._simple_parser.position:
                                            self._simple_parser.position + extent]
        self._simple_parser.advance(len(contents))

        # Same check as earlier
        pos, eol = self._simple_parser.next_eol()
        if pos == self._simple_parser.position and eol != "\r":
            self._simple_parser.advance(len(eol))

        # Get the offset of the next XRef entry
        if self.xref.sections:
            index_after = self.xref.sections[0].entries.index(xref_entry)
            next_entry_hold = filter(
                lambda e: isinstance(e, InUseXRefEntry) and e.offset > xref_entry.offset, 
                self.xref.sections[0].entries[index_after + 1:]
            )
        else:
            next_entry_hold = iter([])

        # Check if we have consumed the appropriate bytes
        # Have we gone way beyond?
        try:
            if self._simple_parser.position >= next(next_entry_hold).offset:
                raise ValueError("\\Length key in stream extent parses beyond object.")
        except StopIteration:
            pass
        # Have we not reached the end?
        if not self._simple_parser.advance_if_next(b"endstream"):
            raise ValueError("\\Length key in stream extent does not match end of stream.")
        
        return contents

    def resolve_reference(self, reference: PdfIndirectRef):
        """Resolves a reference into the indirect object it points to."""
        root_entry = self.xref.sections[0].entries[reference.object_number]
        
        if isinstance(root_entry, InUseXRefEntry):
            return self.parse_indirect_object(root_entry)
        elif isinstance(root_entry, CompressedXRefEntry):
            # Get the object stream it's part of
            objstm_entry = self.xref.sections[0].entries[root_entry.objstm_number]
            objstm = self.parse_indirect_object(objstm_entry)
            assert isinstance(objstm, PdfStream)

            seq = SimpleObjectParser(objstm.decompress()[objstm.details["First"]:] or b"")
            
            for idx, token in enumerate(seq):
                if idx == root_entry.index_within:
                    return token
        
        return PdfNull()
