import enum
from collections import deque
from dataclasses import dataclass
from io import SEEK_CUR, SEEK_END, SEEK_SET
from typing import Literal

from typing_extensions import Buffer, Self

from pdfnaut.exceptions import PdfParseError

# § 7.2.3 "Character set" Table 1 -- Whitespace characters
WHITESPACE = b"\x00\t\n\f\r "

# § 7.2.3 "Character set" Table 2 -- Delimiter characters
# Curly braces are omitted because those are only valid delimiters in Type 4
# PostScript calculator functions (see § 7.10.5).
DELIMITERS = b"()<>[]/%"

# § 7.3.4.2 "Literal strings" Table 3 -- Escape sequences in literal strings
ESCAPE_MAP = {
    b"n": b"\n",
    b"r": b"\r",
    b"t": b"\t",
    b"b": b"\b",
    b"f": b"\f",
    b"(": b"(",
    b")": b")",
    b"\\": b"\\",
}


class TokenType(enum.Enum):
    """The type of PDF token returned by :class:`PDFLexer`."""

    EOF = enum.auto()
    COMMENT = enum.auto()

    NULL = enum.auto()
    TRUE = enum.auto()
    FALSE = enum.auto()

    INTEGER = enum.auto()
    REAL = enum.auto()

    NAME = enum.auto()
    HEX_STRING = enum.auto()
    LIT_STRING = enum.auto()

    ARRAY_START = enum.auto()
    ARRAY_END = enum.auto()

    DICT_START = enum.auto()
    DICT_END = enum.auto()

    WORD = enum.auto()


@dataclass(frozen=True)
class PdfToken:
    """A PDF token, representing either primitive objects or delimiters."""

    type: TokenType
    """The token type."""

    value: bytes
    """The value of the token.

    For literal strings and names, this is the value after escaping. For hexadecimal
    strings, this is the value after padding.
    """


def is_octal_digit(ch: bytes) -> bool:
    """Reports whether a character is an octal digit."""
    return bool(ch) and b"0" <= ch <= b"7"


def is_decimal_digit(ch: bytes) -> bool:
    """Reports whether a character is an ASCII digit (0-9)."""
    return bool(ch) and b"0" <= ch <= b"9"


def is_hex_digit(ch: bytes) -> bool:
    """Reports whether a character is a hexadecimal digit."""
    return ch in b"0123456789abcdefABCDEF"


def is_start_of_pdf_number(ch: bytes) -> bool:
    """Reports whether a character represents the beginning of a PDF number.

    A PDF number starts with either a decimal digit, a trailing period, or
    a plus (+) or minus (-) sign.
    """
    return ch in b".+-" or is_decimal_digit(ch)


def is_continuation_of_pdf_number(ch: bytes) -> bool:
    """Reports whether a character represents a continuation of a PDF number.

    A PDF number contains either an embedded period or a decimal digit.
    """
    return ch == b"." or is_decimal_digit(ch)


def is_pdf_token_boundary(ch: bytes) -> bool:
    """Reports whether a character constitutes a token boundary.

    A token boundary is either a delimiter character or whitespace.
    """
    return ch in WHITESPACE + DELIMITERS


def is_pdf_word(ch: bytes) -> bool:
    """Reports whether a character constitutes a valid PDF word.

    A PDF "word" consists of a sequence of ASCII letters as well as the special
    characters ``*``, ``'``, and ``"``. A word covers both booleans, the null
    object, PDF keywords such as ``obj`` and ``R``, as well as content stream
    operators such as ``RG`` and ``T*``.
    """
    return bool(ch) and (ch in b"*'\"" or b"a" <= ch <= b"z" or b"A" <= ch <= b"Z")


_Whence = Literal[0, 1, 2]


class PdfLexer:
    """A lexer operating on a PDF document, designed for random access and
    intended to produce PDF tokens for building PDF objects."""

    def __init__(self, contents: Buffer) -> None:
        """Initializes a PDF lexer.

        Args:
            contents: An object supporting the buffer protocol, such as
                :class:`bytes` or :class:`memoryview`.
        """
        self._contents = contents
        self._view: memoryview[int] = (
            contents if isinstance(contents, memoryview) else memoryview(contents)
        )
        self._pos = 0
        self._lookahead = deque[PdfToken](maxlen=10)

    def __iter__(self) -> Self:
        return self

    def __next__(self) -> PdfToken:
        token = self.next_token()
        if token.type is TokenType.EOF:
            raise StopIteration

        return token

    def seek(self, offset: int, whence: _Whence = 0) -> int:
        """Changes the cursor position to the given byte ``offset``,
        interpreted relative to the position indicated by ``whence``

        Args:
            offset:
                The offset to move to, relative to ``whence``.

            whence:
                A value indicating the base position. Valid values are:

                - 0 (SEEK_SET): Start of the stream (default); offset is non-negative.
                - 1 (SEEK_CUR): Current stream position; offset may be negative.
                - 2 (SEEK_END): End of the stream; offset should be negative.

        Returns:
            The new absolute position of the cursor.
        """
        old_pos = self._pos

        if whence == SEEK_SET:
            self._pos = offset
        elif whence == SEEK_CUR:
            self._pos += offset
        elif whence == SEEK_END:
            self._pos = max(0, len(self._view) + offset)

        # do not clear the lookahead buffer if the cursor hasn't moved.
        if old_pos != self._pos:
            self._lookahead.clear()

        return self._pos

    def tell(self) -> int:
        """Returns the current position of the cursor."""
        return self.seek(0, SEEK_CUR)

    def consume(self, n: int = 1, /) -> bytes:
        """Consumes N characters from the buffer (default is 1)."""
        data = self.peek(n)
        self._pos += len(data)

        return data

    def peek_line(self) -> bytes:
        """Peeks one PDF line from the buffer."""
        start = self._pos
        line = self.consume_line()
        self._pos = start

        return line

    def consume_line(self) -> bytes:
        """Consumes one PDF line from the buffer."""
        start = self._pos
        end = start

        while end < len(self._view) and self._view[end] not in b"\r\n":
            end += 1

        self._pos = end

        # at this point, we should have either CR, LF or CRLF
        self.skip_next_eol()

        return bytes(self._view[start : self._pos])

    def peek(self, n: int = 1, /) -> bytes:
        """Reads N characters from the buffer without advancing (default is 1)."""
        return bytes(self._view[self._pos : self._pos + n])

    def skip(self, n: int = 1, /) -> None:
        """Advances N characters in the buffer (default is 1)."""
        self._pos += n

    def matches(self, keyword: bytes, /) -> bool:
        """Reports whether a keyword is matched against the current position
        of the buffer."""
        return self.peek(len(keyword)) == keyword

    def match(self, keyword: bytes, error: str) -> None:
        """Attempts to match ``keyword`` at the current position. If no match
        is found, raises :exc:`PdfParseError` with ``error`` as the error message.
        """
        if not self.match_and_skip(keyword):
            raise PdfParseError(error)

    def match_and_skip(self, keyword: bytes, /) -> bool:
        """Matches a keyword against the current position of the buffer.
        Consumes the keyword if matched; otherwise, does nothing.

        Returns whether a match was successful.
        """
        if self.matches(keyword):
            self.consume(len(keyword))
            return True

        return False

    def skip_whitespace(self) -> None:
        """Skips all PDF whitespace from the current position until no more are found."""
        while (ch := self.peek()) and ch in WHITESPACE:
            self.consume()

    def skip_next_eol(self, *, no_cr: bool = False) -> None:
        """Skips the next EOL marker if any."""

        matched = self.match_and_skip(b"\r\n")
        if no_cr and self.matches(b"\r"):
            return

        if not matched and (ch := self.peek()) and ch in b"\r\n":
            self.skip()

    def read_token(self, type_: TokenType, value: bytes | None = None) -> PdfToken:
        """Attempts to match a token of the provided type at the current position.

        If ``value`` is provided, the token must also match the value exactly.
        This is mostly useful for word tokens.
        """

        token = self.next_token()
        if token.type is not type_:
            raise PdfParseError(f"expected token of type {type_.name}, got {type_.name}")

        if value is not None and token.value != value:
            raise PdfParseError(
                f"expected {type_.name} token with value {value}, got {token.value}"
            )

        return token

    def peek_token(self, depth: int = 0) -> PdfToken:
        """Returns a PDF token from the lookahead buffer at depth ``depth``.

        ``depth`` is zero-based. This lexer supports peeking the next 10 tokens.
        """
        if depth < 0 or depth >= 10:
            raise ValueError("depth must be in range [0, 9]")

        while len(self._lookahead) <= depth:
            self._lookahead.append(self._read_next_token())

        return self._lookahead[depth]

    def next_token(self) -> PdfToken:
        """Consumes a PDF token from the current buffer.

        Returns a :class:`PDFToken` object. When no more bytes are available,
        a token of type EOF is returned.
        """

        if self._lookahead:
            return self._lookahead.popleft()

        return self._read_next_token()

    def _read_next_token(self) -> PdfToken:
        """Reads the next token directly from the input buffer."""
        self.skip_whitespace()

        ch = self.peek()
        if not ch:
            return PdfToken(TokenType.EOF, b"")

        if is_start_of_pdf_number(ch):
            return self._read_number()
        elif self.matches(b"/"):
            return self._read_name()
        elif self.matches(b"%"):
            return self._read_comment()
        elif self.match_and_skip(b"["):
            return PdfToken(TokenType.ARRAY_START, b"[")
        elif self.match_and_skip(b"]"):
            return PdfToken(TokenType.ARRAY_END, b"]")
        elif self.match_and_skip(b"<<"):
            return PdfToken(TokenType.DICT_START, b"<<")
        elif self.match_and_skip(b">>"):
            return PdfToken(TokenType.DICT_END, b">>")
        elif self.matches(b"<"):
            return self._read_hex_string()
        elif self.matches(b"("):
            return self._read_literal_string()
        elif is_pdf_word(ch):
            return self._read_word()

        raise PdfParseError(f"invalid token beginning with {ch}")

    def _read_number(self) -> PdfToken:
        """Reads a PDF number (integer or real) from the buffer."""

        if not is_start_of_pdf_number(self.peek()):
            raise PdfParseError("expected PDF number at this point")

        number = bytearray(self.consume())

        while (ch := self.peek()) and is_continuation_of_pdf_number(ch):
            if ch == b"." and ch in number:
                # Error if a period appears more than once in a number.
                raise PdfParseError("invalid PDF number")

            number += self.consume()

        # The plus, minus, and period sign are sometimes used as delimiters,
        # even though they aren't according to Table 2 of § 7.2.3. This check
        # is here to explicitly error in this case.
        if not is_pdf_token_boundary(self.peek()):
            raise PdfParseError("PDF number must be followed by boundary")

        if b"." in number:
            return PdfToken(TokenType.REAL, bytes(number))

        return PdfToken(TokenType.INTEGER, bytes(number))

    def _read_comment(self) -> PdfToken:
        """Reads a PDF comment from the current position."""
        if not self.match_and_skip(b"%"):
            raise PdfParseError("expected PDF comment at this point")

        comment = self.consume_line()
        comment = comment.removesuffix(b"\n").removesuffix(b"\r")

        return PdfToken(TokenType.COMMENT, comment)

    def _read_word(self) -> PdfToken:
        """Reads a PDF word such as a boolean, the null object, or PDF operators."""
        word = bytearray()
        while (ch := self.peek()) and not is_pdf_token_boundary(ch):
            word += self.consume()

        word = bytes(word)
        if word == b"true":
            return PdfToken(TokenType.TRUE, b"true")
        elif word == b"false":
            return PdfToken(TokenType.FALSE, b"false")
        elif word == b"null":
            return PdfToken(TokenType.NULL, b"null")

        return PdfToken(TokenType.WORD, word)

    def _read_name(self) -> PdfToken:
        """Reads a PDF name from the buffer."""

        if not self.match_and_skip(b"/"):
            raise PdfParseError("expected PDF name at this point")

        name = bytearray()
        while (ch := self.peek()) and not is_pdf_token_boundary(ch):
            if self.match_and_skip(b"#"):
                # escape sequence
                escape = self.consume(2)
                try:
                    name.append(int(escape, 16))
                except ValueError:
                    # The PDF specification does not mention what to do when
                    # encountering an invalid escape sequence. Some libraries
                    # ignore the escape sequence, but for now, we will simply
                    # throw an error.
                    raise PdfParseError(f"invalid escape sequence {escape} in name")
            else:
                name += self.consume()

        return PdfToken(TokenType.NAME, bytes(name))

    def _read_hex_string(self) -> PdfToken:
        """Reads a PDF hexadecimal string from the buffer."""

        if not self.match_and_skip(b"<"):
            raise PdfParseError("expected PDF hex string at this point")

        contents = bytearray()
        while not self.matches(b">"):
            # whitespace is ignored in hex strings
            self.skip_whitespace()

            ch = self.peek()
            if not ch:
                raise PdfParseError("unterminated hex string")

            if not is_hex_digit(ch) and ch != b">":
                raise PdfParseError(f"invalid hex digit {ch}")

            if ch != b">":
                contents.extend(self.consume())

        if not self.match_and_skip(b">"):
            raise PdfParseError("unterminated hex string")

        # § 7.3.4.3 - If the final digit of a hexadecimal string is missing,
        # the final digit shall be assumed to be 0.
        if len(contents) % 2 != 0:
            contents.extend(b"0")

        return PdfToken(TokenType.HEX_STRING, bytes(contents))

    def _read_literal_string(self) -> PdfToken:
        """Reads a PDF literal string from the buffer."""
        if not self.match_and_skip(b"("):
            raise PdfParseError("expected PDF literal string at this point")

        contents = bytearray()
        paren_depth = 1

        while self.peek() and paren_depth >= 1:
            if self.match_and_skip(b"\\"):
                # match single-char escapes
                escape = ESCAPE_MAP.get(self.peek())

                if escape is not None:
                    # § 7.3.4.2 - If the character following the backslash is not
                    # one in the table, the backslash shall be ignored.
                    contents.extend(escape)
                    self.consume()
                    continue

                # match newline sequence
                crlf_matched = self.match_and_skip(b"\r\n")
                if not crlf_matched and (pk := self.peek()) and pk in b"\r\n":
                    self.consume()
                    continue
                elif crlf_matched:
                    continue

                # match octal code (8 bit at most)
                octal = bytearray()
                while is_octal_digit(self.peek()) and len(octal) < 3:
                    octal.extend(self.consume())

                if octal:
                    # § 7.3.4.2 - High-order overflow shall be ignored, that is,
                    # wrap the octal value to fit within a byte.
                    contents.append(int(octal, 8) % 256)
                    continue

            if self.matches(b"("):
                paren_depth += 1
            elif self.matches(b")"):
                paren_depth -= 1

            # § 7.3.4.2 - An end-of-line marker appearing within a literal string
            # without a preceding backslash shall be treated as a NEWLINE (\n),
            # regardless of the EOL marker that was actually matched.
            crlf_matched = self.match_and_skip(b"\r\n")
            if crlf_matched:
                contents.extend(b"\n")
                continue
            elif (pk := self.peek()) and pk in b"\r\n":
                self.consume()
                contents.extend(b"\n")
                continue

            # This check avoids appending the delimiting parenthesis.
            if paren_depth != 0:
                contents.extend(self.peek())

            self.consume()

        if paren_depth != 0:
            raise PdfParseError("unterminated literal string")

        return PdfToken(TokenType.LIT_STRING, bytes(contents))
