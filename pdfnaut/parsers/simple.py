"""Low-level utilities for parsing PDFs"""
import re
from typing import Any

from ..objects.base import PdfHexString, PdfName, PdfNull, PdfComment, PdfIndirectRef, PdfObject

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


class SimpleObjectParser:
    """A parser designed to consume objects that do not depend on cross reference 
    tables. It is used by :class:`PdfParser` for this purpose.
    
    This parser will not parse indirect objects or streams because those do depend on XRef 
    and are effectively not sequentially parsable. Because of this limitation, it is not 
    intended for parsing the entire document, but rather its simpler objects."""

    def __init__(self, data: bytes) -> None:
        self.data = data
        self.position = 0
    
    def __iter__(self):
        return self
    
    def __next__(self) -> PdfObject | PdfComment:
        while not self.at_end():
            if (tok := self.next_token()) is not None:
                return tok
            self.advance()
        raise StopIteration
    
    @property
    def current(self) -> bytes:
        """The character at the current position"""
        return self.data[self.position:self.position + 1]

    def at_end(self) -> bool:
        """Checks whether the parser has reached the end of the data"""
        return self.position >= len(self.data)

    def advance(self, n: int = 1) -> None:
        """Advances ``n`` steps through the parser"""
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

        return (-1, "")

    def peek(self, n: int = 1) -> bytes:
        """Peeks ``n`` bytes into the parser without advancing"""
        return self.data[self.position + 1:self.position + 1 + n]
    
    @property
    def current_to_eol(self) -> bytes:
        """A substring starting from the current character and ending at the 
        next end of line marker (included)"""
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
        is uneven, the last character is assumed to be 0.
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
        
        return PdfIndirectRef(int(mat.group("num")), int(mat.group("gen")))

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
                    self.advance() # past the \
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
        """Parses a PDF comment. These have no syntactical meaning but we still parse them anyway."""
        self.advance() # past the %
        line = self.current_to_eol
        self.advance(len(line))
        return PdfComment(line.strip(b"\r\n"))
    