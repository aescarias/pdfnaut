"""Low-level utilities for parsing PDFs"""

import re
from typing import Any

from .types import (
    PdfXrefEntry, PdfXrefSubsection, PdfXrefTable, 
    PdfHexString, PdfName, PdfNull, PdfComment,
    PdfIndirectRef, PdfStream, PdfObject
)

DELIMITERS = b"()<>[]{}/%"
WHITESPACE = b"\x00\t\n\x0c\r "
# as defined in 7.3.4.2 Literal Strings, Table 3
STRING_ESCAPE = {
    b"\\n":  b"\n",
    b"\\r":  b"\r",
    b"\\t":  b"\t",
    b"\\b":  b"\b",
    b"\\f":  b"\f",
    b"\\(":  b"(",
    b"\\)":  b")",
    b"\\\\": b"\\"
}


class PdfParseError(Exception):
    """Raised if unable to continue parsing the PDF"""
    pass


class SimpleObjectParser:
    """A parser designed to consume objects that do not depend on cross reference 
    tables. This will not parse indirect objects or streams because those do 
    depend on XRef and are effectively not sequentially parsable.
    
    Because of this limitation, this parser is not made to parse an entire
    PDF document, but only objects part of it. It is used by :class:`PdfParser`
    for this purpose."""
    def __init__(self, data: bytes) -> None:
        self.data = data
        self.position = 0
    
    @property
    def current(self) -> bytes:
        """The character at this current position"""
        return self.data[self.position:self.position + 1]
    
    def at_end(self) -> bool:
        """Checks whether the parser has reached the end of data"""
        return self.position >= len(self.data)

    def advance(self, n: int = 1) -> None:
        """Advance ``n`` steps through the parser"""
        if not self.at_end():
            self.position += n

    def advance_if_next(self, keyword: bytes) -> bool:
        """Checks if ``keyword`` starts at the current position. If so, returns True and advances through the keyword."""
        if self.current + self.peek(len(keyword) - 1) == keyword:
            self.advance(len(keyword))
            return True
        return False
    
    def advance_whitespace(self) -> None:
        """Advances through whitespace"""
        while self.current in WHITESPACE:
            self.advance()

    def next_eol(self) -> tuple[int, str]:
        """Returns a tuple containing the position where the next End-Of-Line 
        Marker occurs and the EOL marker itself. If none is found, ``(-1, "")``
        is returned.
         
        The spec defines the EOL marker as either ``\\r`` (except in some cases), 
        ``\\n`` or ``\\r\\n``.
        """
        carriage = self.data.find(b"\r", self.position)
        newline = self.data.find(b"\n", self.position)

        # If both a carriage and newline were found
        if carriage != -1 and newline != -1:
            first = min(carriage, newline)
            if self.data[first:first + 1] == b"\r" and carriage + 1 == newline:
                return first, "\r\n"

            return first, chr(self.data[first])
        elif carriage != -1:
            return carriage, "\r"
        elif newline != -1:
            return newline, "\n" 
        # if newline != -1:
        #     if self.data[newline - 1:newline] == b"\r":
        #         return newline - 1, "\r\n"
        #     return newline, "\n"
        
        # if carriage != -1:
        #     return carriage, "\r"
        
        return (-1, "")

    def peek(self, n: int = 1) -> bytes:
        """Peeks ``n`` bytes into the parser without advancing"""
        return self.data[self.position + 1:self.position + 1 + n]
    
    @property
    def current_to_eol(self) -> bytes:
        """A substring starting from the current character and ending at the 
        next end of line (included)"""
        pos, eol = self.next_eol()
        line = self.data[self.position:pos + len(eol)]
        if pos == -1:
            line = self.data[self.position:]
        return line

    def next_token(self) -> PdfObject | PdfComment | None:
        """Parses and returns the next token"""
        while not self.at_end():
            if self.advance_if_next(b"true"):
                return True
            elif self.advance_if_next(b"false"):
                return False
            elif self.advance_if_next(b"null"):
                return PdfNull()
            elif (mat := re.match(rb"(?P<num>\d+)\s+(?P<gen>\d+)\s+R", self.current_to_eol)):
                return self.parse_indirect_reference(mat)
            elif self.current.isdigit() or self.current in b"+-":
                return self.parse_numeric() 
            elif self.current == b"[":
                return self.parse_array()
            elif self.current == b"/":
                return self.parse_name()
            elif self.current + self.peek() == b"<<":
                return self.parse_dictionary()
            elif self.current == b"<":
                return self.parse_hex_string()
            elif self.current == b"(":
                return self.parse_literal_string()
            elif self.current == b"%":
                return self.parse_comment()

            return None        

    def parse_numeric(self) -> int | float:
        """Parses a numeric object.
        
        PDFs have two types of numbers: integers (40, -30) and real numbers (3.14).
        The range and precision of numbers depends on the machine used to process the PDF.
        Errors may occur if values exceed these imposed limits.
        """
        number = self.current # either a digit or a sign prefix
        self.advance()

        while not self.at_end():
            if not self.current.isdigit() and self.current != b".":
                break
            number += self.current
            self.advance()

        # is this a float?
        if b"." in number:
            return float(number)
        return int(number)
    
    def parse_name(self) -> PdfName:
        """Parses a name.
        
        It is a uniquely defined atomic symbol introduced by a slash. The sequence
        of characters after the slash (/) and before any delimiter or whitespace
        is the name. (/ is a valid name)
        """
        self.advance() # past the /

        atom = b""        
        while not self.at_end() and self.current not in DELIMITERS + WHITESPACE:
            # Escape character logic
            if self.current == b"#":
                self.advance()
                # consume and add the 2 digit code to the atom
                atom += chr(int(self.current + self.peek(), 16)).encode()
                self.advance(2)
                continue

            atom += self.current
            self.advance()
        
        return PdfName(atom)
    
    def parse_hex_string(self) -> PdfHexString:
        """Parses a hexadecimal string.
        
        They are useful for including arbitrary binary data in a PDF. It is a sequence
        of hexadecimal characters where every 2 characters is a byte. If the sequence
        is uneven, the last character is assumed 0.
        """
        self.advance(1) # adv. past the <

        content = b""
        while not self.at_end():
            if self.current == b">":
                self.advance()
                break

            content += self.current
            self.advance()

        return PdfHexString(content)

    def parse_dictionary(self) -> dict[str, Any]:
        """Parses a dictionary object."""
        self.advance(2) # adv. past the <<

        kv_pairs: list[PdfObject | PdfComment] = []

        while not self.at_end():
            if self.current + self.peek() == b">>":
                self.advance(2)
                break

            if (tok := self.next_token()) is not None:
                kv_pairs.append(tok)

            # Only advance when no token matches. The individual object 
            # parsers already advance and this avoids advancing past delimiters.
            if tok is None:
                self.advance()
        
        return {
            kv_pairs[i].value.decode(): kv_pairs[i + 1] # type: ignore
            for i in range(0, len(kv_pairs), 2)
        } 

    def parse_array(self) -> list[Any]:
        """Parses an array"""
        self.advance() # past the [ 
        items: list[Any] = []

        while not self.at_end():
            if (tok := self.next_token()) is not None:
                items.append(tok)
            
            if self.current == b"]":
                self.advance()
                break

            if tok is None:
                self.advance()

        return items
    
    def parse_indirect_reference(self, mat: re.Match[bytes]) -> PdfIndirectRef:
        """Parses an indirect reference."""
        self.advance(mat.end()) # consume the reference
        self.advance_whitespace()
        
        return PdfIndirectRef(
            int(mat.group("num")), 
            int(mat.group("gen"))
        )

    def parse_literal_string(self) -> bytes:
        """Parses a literal string."""
        self.advance() # past the (
        
        string = b""
        # this is used to handle parenthesis pairs which do not require escaping 
        paren_depth = 1

        while not self.at_end() and paren_depth >= 1:
            # escape character logic
            if self.current == b"\\":
                value = STRING_ESCAPE.get(self.current + self.peek())
                if value is not None:
                    string += value
                    self.advance(2) # past the escape code
                    continue

                # The next checks are for escape codes that need additional handling
                pos, eol = self.next_eol()
                # Is the next character a newline?
                if self.position + 1 == pos:
                    # A single \ indicates that the string is continued
                    self.advance(1 + len(eol))
                # Is this an octal character code?
                elif self.peek(1).isdigit():
                    self.advance() # past the /
                    code = b""
                    # The sequence can be at most 3 digits
                    while not self.at_end() and len(code) < 3 and self.current.isdigit():
                        code += self.current
                        self.advance()
                    # Convert the code from octal into a codepoint and append
                    string += chr(int(code, 8)).encode()

            if self.current == b"(":
                paren_depth += 1
            elif self.current == b")":
                paren_depth -= 1
            
            # This avoids appending the delimiting paren
            if paren_depth != 0:
                string += self.current
            self.advance()

        return string

    def parse_comment(self) -> PdfComment:
        """Parses a PDF comment"""
        self.advance() # past the %
        line = self.current_to_eol
        self.advance(len(line))
        return PdfComment(line.strip(b"\r\n"))
    

class PdfParser:
    """A parser that can completely parse a PDF document.
    
    It consumes the PDF's cross-reference tables and trailers. It merges the tables
    into a single one and provides an interface to individually parse
    each indirect object using ``SimpleObjectParser``."""

    def __init__(self, data: bytes) -> None:
        self._simple_parser = SimpleObjectParser(data)
        self._trailers: list[dict[str, Any]] = []

        self.update_xrefs: list[PdfXrefTable] = []
        """A list of all XRef tables in the document (the most recent first)"""

        # The below values are expected to be filled
        self.trailer: dict[str, Any] = {}
        """The most recent trailer in the PDF document"""

        self.xref: PdfXrefTable = PdfXrefTable([])
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

        # Get the most recent XRef
        self._simple_parser.position = start_xref
        xref = self.parse_xref_table()
        self._simple_parser.advance_whitespace()

        # Get the trailer to locate further XRefs
        trailer = self.parse_trailer()
        self.update_xrefs.append(xref)
        self._trailers.append(trailer)

        if "Prev" in trailer:
            # Recursion!
            self._simple_parser.position = 0
            self.parse(trailer["Prev"])
        else:
            self.xref = self.get_merged_xrefs()
            self.trailer = self._trailers[0]

    def parse_header(self) -> str:
        """Parse the %PDF-n.m header."""
        header = self._simple_parser.parse_comment()
        mat = re.match(rb"PDF-(?P<major>\d+).(?P<minor>\d+)", header.value)
        if mat:
            return f"{mat.group('major').decode()}.{mat.group('minor').decode()}"

        raise PdfParseError("Expected PDF header.")
    
    def get_merged_xrefs(self) -> PdfXrefTable:
        """Combines all update XRef tables in the document into a single table 
        with a single section containing all entries"""
        entry_map: dict[int, PdfXrefEntry] = {}

        for xref in self.update_xrefs[::-1]:
            for section in xref.sections:
                for idx, entry in enumerate(section.entries):
                    entry_map[section.first_obj_number + idx] = entry

        final_entries: list[PdfXrefEntry] = [None] * len(entry_map) # type: ignore
        for num, entry in entry_map.items():
            final_entries[num] = entry

        return PdfXrefTable([
            PdfXrefSubsection(0, self._trailers[0]["Size"], final_entries)
        ])

    def parse_xref_table(self) -> PdfXrefTable:
        # TODO: The startxref can also point to a compressed XRef object
        # TODO: We don't support those yet.
        if self._simple_parser.current + self._simple_parser.peek(3) != b"xref":
            if re.match(rb"(?P<num>\d+)\s+(?P<gen>\d+)\s+obj", self._simple_parser.current_to_eol):
                raise NotImplementedError("'startxref' offset pointing to \\XRef object unsupported.")
            raise PdfParseError("XRef offset not at start of 'xref' keyword")
        
        self._simple_parser.advance(4)
        self._simple_parser.advance_whitespace()

        xref = PdfXrefTable([])

        while not self._simple_parser.at_end():
            # subsection
            subsection = re.match(rb"(?P<first_obj>\d+)\s(?P<count>\d+)", 
                                self._simple_parser.current_to_eol)
            if subsection is None:
                break
            self._simple_parser.advance(subsection.end())
            self._simple_parser.advance_whitespace()

            # xref entries
            entries: list[PdfXrefEntry] = []
            for i in range(int(subsection.group("count"))):
                entry = re.match(rb"(?P<offset>\d{10}) (?P<gen>\d{5}) (?P<status>f|n)", 
                    self._simple_parser.current + self._simple_parser.peek(19))
                if entry is None:
                    raise PdfParseError(f"Expected valid XRef entry at row {i + 1}")
                
                entries.append(PdfXrefEntry(
                    int(entry.group("offset")),
                    int(entry.group("gen")),
                    entry.group("status") == b"n"
                ))
                self._simple_parser.advance(20)
            
            xref.sections.append(PdfXrefSubsection(
                int(subsection.group("first_obj")),
                int(subsection.group("count")),
                entries
            ))
            
        return xref

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
    
    def parse_trailer(self) -> dict[str, Any]:
        """Parse the PDF's trailer which is used to quickly locate crossrefs 
        and other special objects"""
        self._simple_parser.advance(7) # advance through the 'trailer' keyword
        self._simple_parser.advance_whitespace()
        
        # next token is a dictionary
        trailer = self._simple_parser.parse_dictionary()
        return trailer
    
    def parse_indirect_object(self, xref_entry: PdfXrefEntry) -> PdfObject | PdfStream | None:
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
    
    def resolve_reference(self, reference: PdfIndirectRef):
        """Resolves a reference into the indirect object it points to."""
        root_entry = self.xref.sections[0].entries[reference.object_number]
        if reference.generation == root_entry.generation:
            return self.parse_indirect_object(root_entry)
    
    def parse_stream(self, xref_entry: PdfXrefEntry, extent_length: int) -> bytes:
        """Parses a PDF stream of length ``extent_length``"""
        self._simple_parser.advance(6) # past the stream

        # If the current character is LF or CRLF (but not just CR), skip.
        pos, eol = self._simple_parser.next_eol()
        if pos == self._simple_parser.position and eol != "\r":
            self._simple_parser.advance(len(eol))

        contents = self._simple_parser.data[self._simple_parser.position:
                                            self._simple_parser.position + extent_length]
        self._simple_parser.advance(len(contents))

        # Same check as earlier
        pos, eol = self._simple_parser.next_eol()
        if pos == self._simple_parser.position and eol != "\r":
            self._simple_parser.advance(len(eol))

        # Get the offset of the next XRef entry
        index_after = self.xref.sections[0].entries.index(xref_entry)
        next_entry_hold = filter(
            lambda e: e.offset > xref_entry.offset, 
            self.xref.sections[0].entries[index_after + 1:]
        )

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
