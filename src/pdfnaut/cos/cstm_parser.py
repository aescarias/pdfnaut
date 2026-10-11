from typing import cast

from typing_extensions import Buffer, Self

from pdfnaut.cos.lexer import WHITESPACE, PdfLexer, TokenType
from pdfnaut.cos.object_parser import PdfObjectParser
from pdfnaut.cos.objects.base import Operand
from pdfnaut.exceptions import PdfParseError

from .objects import PdfArray, PdfDictionary, PdfInlineImage, PdfName, PdfOperator

ContentStreamItem = PdfOperator | PdfInlineImage


class ContentStreamParser:
    """A parser designed to consume operators from a PDF content stream.

    This parser returns either :class:`PdfOperator` or :class:`PdfInlineImage`
    objects.
    """

    def __init__(self, contents: Buffer) -> None:
        """Initializes a content stream parser.

        Args:
            contents: An object supporting the buffer protocol, such as
                :class:`bytes` or :class:`memoryview`.
        """

        self.lexer = PdfLexer(contents)
        self.object_parser = PdfObjectParser(self.lexer)

    def __iter__(self) -> Self:
        return self

    def __next__(self) -> ContentStreamItem:
        operator = self.next_operator()
        if operator is None:
            raise StopIteration

        return operator

    def next_operator(self) -> ContentStreamItem | None:
        """Consumes the next content stream operator from the stream.

        Returns either :class:`PdfOperator` or :class:`PdfInlineImage` objects,
        or None when no more operators are available.
        """
        operands: list[Operand] = []

        while True:
            token = self.lexer.peek_token()

            if token.type is TokenType.EOF:
                if operands:
                    raise PdfParseError("expected operator")
                return

            if token.type is TokenType.COMMENT:
                self.lexer.next_token()
                continue

            if token.type is TokenType.WORD:
                if token.value == b"BI":
                    return self._parse_inline_image()

                self.lexer.next_token()
                return PdfOperator(name=token.value, args=operands)

            obj = self.object_parser.next_object()
            assert obj is not None

            operands.append(cast(Operand, obj))

    def _parse_inline_image(self) -> PdfInlineImage:
        """Parses an inline image within a content stream."""

        current_tok = self.lexer.peek_token()
        if current_tok.type != TokenType.WORD or current_tok.value != b"BI":
            raise PdfParseError("expected BI operator for inline image")

        self.lexer.next_token()

        details = self._parse_inline_image_dict()

        # Abbreviated names are preferred according to
        # https://github.com/pdf-association/pdf-issues/issues/3
        filter_names = details.get("F", details.get("Filter"))
        if filter_names is None:
            filter_names = PdfArray()

        if isinstance(filter_names, PdfName):
            filter_names = PdfArray([filter_names])

        filter_names = cast(PdfArray[PdfName], filter_names)

        # If the next character is whitespace, consume it.
        if (ch := self.lexer.peek()) and ch in WHITESPACE:
            self.lexer.consume()

        # However, if the filter is ASCIIHex or ASCII85, consume all of the whitespace
        # (including comments).
        checking_filters = (b"A85", b"AHx", b"ASCIIHexDecode", b"ASCII85Decode")

        if any(fn.value in checking_filters for fn in filter_names):
            self.lexer.skip_whitespace()
            if self.lexer.matches(b"%"):
                self.lexer._read_comment()

        # check for PDF 2.0 /L and /Length; use if available, otherwise scan for EI.
        length = details.get("L", details.get("Length"))
        if length is not None and (length := cast(int, length)) >= 0:
            image_data = self.lexer.consume(length)
            self.lexer.skip_next_eol(no_cr=True)

            if (tok := self.lexer.peek(2)) != b"EI":
                raise PdfParseError(f"expected end of inline image 'EI', got {tok!r}")
        else:
            # Currently this is fairly fragile and does not consider EI occurring naturally.
            # TODO: There are better heuristics available for inline image length detection.
            image_data = bytearray()
            while self.lexer.peek(2) != b"EI":
                image_data.extend(self.lexer.consume())

        self.lexer.consume(2)  # consume the "EI" operator
        return PdfInlineImage(details, bytes(image_data))

    def _parse_inline_image_dict(self) -> PdfDictionary:
        """Parses the inline image dictionary."""
        values = PdfDictionary()

        while True:
            token = self.lexer.peek_token()
            if token.type is TokenType.COMMENT:
                self.lexer.next_token()
                continue

            if token.type is TokenType.WORD and token.value == b"ID":
                self.lexer.next_token()
                return values

            key = self.object_parser.next_object()
            if key is None:
                raise PdfParseError("unterminated dictionary")

            if not isinstance(key, PdfName):
                raise PdfParseError(f"expected dictionary key to be name object, got {key!r}")

            if key.value.decode() in values:
                raise PdfParseError(f"duplicate key {key} found")

            next_token = self.lexer.peek_token()
            if (
                next_token.type is TokenType.WORD and next_token.value == b"ID"
            ) or next_token.type is TokenType.EOF:
                raise PdfParseError(f"expected value after key {key}")

            value = self.object_parser.next_object()
            assert value is not None

            values[key.value.decode()] = value
