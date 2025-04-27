from __future__ import annotations

import re
from collections.abc import Callable
from typing import cast

from .objects import (
    ObjectGetter,
    PdfArray,
    PdfComment,
    PdfDictionary,
    PdfHexString,
    PdfInlineImage,
    PdfName,
    PdfNull,
    PdfObject,
    PdfOperator,
    PdfReference,
)

# as defined in § 7.2.3 Character Set, Table 1 & Table 2
DELIMITERS = b"()<>[]{}/%"
WHITESPACE = b"\x00\t\n\x0c\r "
EOL_CR = b"\r"
EOL_LF = b"\n"
EOL_CRLF = b"\r\n"

# as defined in § 7.3.4.2 Literal Strings, Table 3
STRING_ESCAPE = {
    b"\\n": b"\n",
    b"\\r": b"\r",
    b"\\t": b"\t",
    b"\\b": b"\b",
    b"\\f": b"\f",
    b"\\(": b"(",
    b"\\)": b")",
    b"\\\\": b"\\",
}


class ContentStreamTokenizer:
    """A tokenizer designed to consume the contents within a content stream.

    This tokenizer relies on :class:`PdfTokenizer` to parse common tokens
    but has special handling for the operators inside a content stream.
    """

    def __init__(self, contents: bytes) -> None:
        self.contents = contents
        self.tokenizer = PdfTokenizer(contents)

    def __iter__(self):
        return self

    def __next__(self) -> PdfOperator | PdfComment:
        while not self.tokenizer.done:
            if (operator := self.get_next_token()) is not None and isinstance(
                operator, PdfOperator
            ):
                return operator

        raise StopIteration

    def get_next_token(self) -> PdfOperator | PdfComment | None:
        if self.tokenizer.done:
            return

        operands = []
        while not self.tokenizer.done:
            if (tok := self.tokenizer.get_next_token(parse_references=False)) is not None:
                if isinstance(tok, PdfComment):
                    return tok

                operands.append(tok)
            elif (pk := self.tokenizer.peek()).isalpha() or pk in b"'\"":
                name = self.tokenizer.consume_while(lambda ch: ch not in DELIMITERS + WHITESPACE)

                if name == b"BI":
                    # inline images must be handled specially so as to not
                    # confuse the parser.
                    return self.parse_inline_image()

                return PdfOperator(name, operands)

            self.tokenizer.skip()

    def parse_inline_image(self) -> PdfOperator:
        """Parses an inline image.

        Inline images are an alternative to image XObjects designed
        for embedding small images in a content stream.
        """

        mapping = self.tokenizer.parse_dictionary_until(b"ID")

        # Abbreviated names are preferred: https://github.com/pdf-association/pdf-issues/issues/3
        filter_names = mapping.get("F", mapping.get("Filter"))
        if isinstance(filter_names, PdfName):
            filter_names = PdfArray([filter_names])

        filter_names = cast("PdfArray[PdfName] | None", filter_names)

        # We must skip one character unless the filter used is ASCIIHex or ASCII85.
        checking_filters = (b"A85", b"AHx", b"ASCIIHexDecode", b"ASCII85Decode")
        if filter_names is None or all(fn.value not in checking_filters for fn in filter_names):
            self.tokenizer.consume()

        # TODO: handle pdf 2.0's /L & /Length for inline images
        image_data = self.tokenizer.consume_while(lambda _: not self.tokenizer.peek(2) == b"EI")

        return PdfOperator(self.tokenizer.consume(2), [PdfInlineImage(mapping, image_data)])


class PdfTokenizer:
    """A tokenizer designed to consume individual objects that do not depend on a cross
    reference table. It is used by :class:`~pdfnaut.cos.parser.PdfParser` for this purpose.

    This tokenizer consumes basic objects such as arrays and dictionaries. Indirect objects
    and streams depend on an XRef table and hence are not sequentially parsable. It is not
    intended to parse these items but rather the objects stored within them.

    Arguments:
        data (bytes):
            The contents to be parsed.
    """

    def __init__(self, data: bytes) -> None:
        self.data = data
        self.position = 0
        self.resolver: ObjectGetter | None = None

    def __iter__(self):
        return self

    def __next__(self) -> PdfObject | PdfComment | PdfOperator:
        while not self.done:
            if (tok := self.get_next_token()) is not None:
                return tok
            self.skip()
        raise StopIteration

    # * Scanning
    @property
    def done(self) -> bool:
        """Whether the parser has reached the end of data."""
        return self.position >= len(self.data)

    def skip(self, n: int = 1) -> None:
        """Skips/advances ``n`` characters in the tokenizer."""
        if not self.done:
            self.position += n

    def peek(self, n: int = 1) -> bytes:
        """Peeks ``n`` characters into ``data`` without advancing through the tokenizer."""
        return self.data[self.position : self.position + n]

    def peek_line(self) -> bytes:
        """Peeks from the current position until an EOL marker is found (not included
        in the output)."""
        start_pos = self.position
        line = self.consume_while(lambda _: not self.peek(2).startswith((EOL_CRLF, EOL_CR, EOL_LF)))
        self.position = start_pos
        return line

    def consume(self, n: int = 1) -> bytes:
        """Consumes and returns ``n`` characters."""
        consumed = self.peek(n)
        self.skip(len(consumed))

        return consumed

    def matches(self, keyword: bytes) -> bool:
        """Checks whether ``keyword`` starts at the current position."""
        return self.peek(len(keyword)) == keyword

    def _get_reference_if_matched(self) -> re.Match[bytes] | None:
        """Returns the Regex match if an indirect reference is at the current position
        otherwise None."""
        if not self.peek().isdigit():
            return

        return re.match(rb"^(?P<num>\d+)\s+(?P<gen>\d+)\s+R", self.peek_line())

    def _is_octal(self, byte: bytes) -> bool:
        """Returns whether ``byte`` is a valid octal number (0-7)."""
        return b"0" <= byte <= b"7"

    def skip_if_matches(self, keyword: bytes) -> bool:
        """Advances ``len(keyword)`` characters if ``keyword`` starts at the current
        position. Returns whether the match was successful."""
        if self.matches(keyword):
            self.skip(len(keyword))
            return True
        return False

    def skip_whitespace(self) -> None:
        """Advances through PDF whitespace."""
        self.skip_while(lambda ch: ch in WHITESPACE)

    def skip_next_eol(self, no_cr: bool = False) -> None:
        """Skips the next EOL marker if matched. If ``no_cr`` is True, CR (``\\r``) as is
        will not be treated as a newline."""
        matched = self.skip_if_matches(EOL_CRLF)
        if no_cr and self.matches(EOL_CR):
            return

        if not matched and self.peek() in EOL_CRLF:
            self.skip()

    def skip_while(self, callback: Callable[[bytes], bool], *, limit: int = -1) -> int:
        """Skips while ``callback`` returns True for an input character. If specified,
        it will only skip ``limit`` characters. Returns how many characters were skipped."""
        if limit == -1:
            limit = len(self.data)

        start = self.position
        while not self.done and callback(self.peek()) and self.position - start < limit:
            self.position += 1
        return self.position - start

    def consume_while(self, callback: Callable[[bytes], bool], *, limit: int = -1) -> bytes:
        """Consumes while ``callback`` returns True for an input character. If specified,
        it will only consume up to ``limit`` characters."""
        if limit == -1:
            limit = len(self.data)

        consumed = b""
        while not self.done and callback(self.peek()) and len(consumed) < limit:
            consumed += self.consume()
        return consumed

    def get_next_token(self, *, parse_references: bool = True) -> PdfObject | PdfComment | None:
        """Parses and returns the token at the current position.

        Arguments:
            parse_references (bool, optional, keyword only):
                Whether to parse indirect references. This is intended for
                content streams where indirect references are disallowed.
        """
        if self.done:
            return

        if self.skip_if_matches(b"true"):
            return True
        elif self.skip_if_matches(b"false"):
            return False
        elif self.skip_if_matches(b"null"):
            return PdfNull()
        elif parse_references and (mat := self._get_reference_if_matched()):
            return self.parse_indirect_reference(mat)
        elif self.peek().isdigit() or self.peek() in b".+-":
            return self.parse_numeric()
        elif self.matches(b"["):
            return self.parse_array()
        elif self.matches(b"/"):
            return self.parse_name()
        elif self.matches(b"<<"):
            return self.parse_dictionary_until()
        elif self.matches(b"<"):
            return self.parse_hex_string()
        elif self.matches(b"("):
            return self.parse_literal_string()
        elif self.matches(b"%"):
            return self.parse_comment()

    def parse_numeric(self) -> int | float:
        """Parses a numeric object.

        PDF has two types of numbers: integers (40, -30) and real numbers (3.14). The range
        and precision of these numbers may depend on the machine used to process the PDF.
        """
        prefix_or_digit = self.consume()  # either a digit, a dot, or a sign prefix
        number = prefix_or_digit + self.consume_while(lambda ch: ch.isdigit() or ch == b".")

        # is this a float (a real number)?
        if b"." in number:
            return float(number)
        return int(number)

    def parse_name(self) -> PdfName:
        """Parses a name -- a uniquely defined atomic symbol introduced with a slash
        and ending before a delimiter or whitespace."""
        self.skip()  # past the /

        atom = b""
        while not self.done and self.peek() not in DELIMITERS + WHITESPACE:
            if self.matches(b"#"):
                # escape sequence matched
                self.skip()

                atom += int(self.consume(2), 16).to_bytes(1, "little")
                continue

            atom += self.consume()

        return PdfName(atom)

    def parse_hex_string(self) -> PdfHexString:
        """Parses a hexadecimal string. Hexadecimal strings usually include arbitrary binary
        data. If the sequence is uneven, the last character is assumed to be 0."""
        self.skip()  # adv. past the <

        content = self.consume_while(lambda ch: ch != b">")
        self.skip()  # adv. past the >

        return PdfHexString(content)

    def parse_dictionary_until(self, delimiter: bytes = b">>") -> PdfDictionary:
        """Parses a dictionary object.

        In a PDF, dictionary keys are name objects and dictionary values are any
        object or reference. This parser maps name objects to strings in this
        context.

        The 'delimiter' parameter specifies where this dictionary should end.
        The common ending (and default value) is ">>" for dictionary objects.
        However, this also accommodates for inline images which have the ID
        operator that can be used as a delimiter.
        """
        self.skip(2)  # adv. past the <<

        kv_pairs: list[PdfObject] = []

        while not self.done and not self.matches(delimiter):
            if (token := self.get_next_token()) is not None:
                kv_pairs.append(cast(PdfObject, token))

            # Only advance when no token matches. The individual object
            # parsers already advance and this avoids advancing past delimiters.
            if token is None:
                self.skip()

        self.skip(2)  # adv. past the >>

        return PdfDictionary(
            {
                cast(PdfName, kv_pairs[i]).value.decode(): kv_pairs[i + 1]
                for i in range(0, len(kv_pairs), 2)
            }
        )

    def parse_array(self) -> PdfArray:
        """Parses an array. Arrays are heterogenous in PDF so they are mapped to Python lists."""
        self.skip()  # past the [

        items = PdfArray[PdfObject]()

        while not self.done and not self.matches(b"]"):
            if (token := self.get_next_token()) is not None:
                items.append(cast(PdfObject, token))

            if token is None:
                self.skip()

        self.skip()  # past the ]

        return items

    def parse_indirect_reference(self, mat: re.Match[bytes]) -> PdfReference:
        """Parses an indirect reference. Indirect references allow locating an object in a PDF."""
        self.skip(mat.end())  # consume the reference
        self.skip_whitespace()

        reference = PdfReference(int(mat.group("num")), int(mat.group("gen")))
        if self.resolver:
            reference._resolver = self.resolver

        return reference

    def parse_literal_string(self) -> bytes:
        """Parses a literal string.

        Literal strings may be composed entirely of ASCII or may include arbitrary
        binary data. They may also include escape sequences and octal values (``\\ddd``).
        """
        self.skip()  # past the (

        string = b""
        # balanced parentheses do not require escaping
        paren_depth = 1

        while not self.done and paren_depth >= 1:
            if self.matches(b"\\"):
                # Is this a default escape? (Table 3 § 7.3.4.2)
                escape = STRING_ESCAPE.get(self.peek(2))

                if escape is not None:
                    string += escape
                    self.skip(2)  # past the escape code
                    continue

                # Otherwise, match a newline or a \ddd sequence
                self.skip(1)

                matched = self.skip_if_matches(EOL_CRLF)
                if not matched and self.peek() in EOL_CRLF:
                    self.skip()
                elif self._is_octal(self.peek()):
                    octal_code = self.consume_while(self._is_octal, limit=3)
                    # the octal value will be 8 bit at most
                    string += int(octal_code, 8).to_bytes(1, "little")
                    continue

            if self.matches(b"("):
                paren_depth += 1
            elif self.matches(b")"):
                paren_depth -= 1

            # This avoids appending the delimiting paren
            if paren_depth != 0:
                string += self.peek()

            self.skip()

        return string

    def parse_comment(self) -> PdfComment:
        """Parses a PDF comment. Comments have no syntactical meaning."""
        self.skip()  # past the %

        line = self.consume_while(lambda ch: ch not in EOL_CRLF)
        self.skip_whitespace()

        return PdfComment(line)
