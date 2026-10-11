from typing_extensions import Self

from ..exceptions import PdfParseError
from .lexer import PdfLexer, PdfToken, TokenType
from .objects import (
    ObjectGetter,
    PdfArray,
    PdfDictionary,
    PdfHexString,
    PdfName,
    PdfNull,
    PdfObject,
    PdfReference,
)


class PdfObjectParser:
    """A parser intended to consume tokens from a PDF lexer and produce PDF direct objects.

    Direct objects include everything except stream objects, which are read by the PDF
    document parser.
    """

    def __init__(self, lexer: PdfLexer, resolver: ObjectGetter | None = None) -> None:
        """Initializes a PDF object parser.

        Args:
            lexer: A :class:`PdfLexer` object from which to consume items.
            resolver: A callable taking PDF references and resolving them to
              PDF objects.
        """
        self.lexer = lexer
        self.resolver = resolver

    def __iter__(self) -> Self:
        return self

    def __next__(self) -> PdfObject:
        obj = self.next_object()
        if obj is None:
            raise StopIteration

        return obj

    def next_object(self) -> PdfObject | None:
        """Consumes the next PDF object from the lexer."""

        while self.lexer.peek_token().type is TokenType.COMMENT:
            self.lexer.next_token()

        token = self.lexer.peek_token()
        if token.type is TokenType.DICT_START:
            return self._parse_dictionary()
        if token.type is TokenType.ARRAY_START:
            return self._parse_array()

        self.lexer.next_token()
        if token.type is TokenType.EOF:
            return None
        if token.type is TokenType.TRUE:
            return True
        if token.type is TokenType.FALSE:
            return False
        if token.type is TokenType.NULL:
            return PdfNull()
        if token.type is TokenType.NAME:
            return PdfName(token.value)
        if token.type is TokenType.LIT_STRING:
            return token.value
        if token.type is TokenType.HEX_STRING:
            return PdfHexString(token.value)
        if token.type is TokenType.INTEGER:
            return self._parse_integer_or_reference(token)
        if token.type is TokenType.REAL:
            return float(token.value)

        raise PdfParseError(f"unexpected token {token!r}")

    def _parse_dictionary(self) -> PdfDictionary:
        """Parses a PDF dictionary."""

        token = self.lexer.peek_token()
        if token.type is not TokenType.DICT_START:
            raise PdfParseError("expected PDF dictionary at this point")

        self.lexer.next_token()

        values = PdfDictionary()

        while True:
            token = self.lexer.peek_token()
            if token.type is TokenType.DICT_END:
                self.lexer.next_token()
                return values

            key = self.next_object()
            if key is None:
                raise PdfParseError("unterminated dictionary")

            if not isinstance(key, PdfName):
                raise PdfParseError(f"expected dictionary key to be name object, got {key!r}")

            if key.value.decode() in values:
                raise PdfParseError(f"duplicate key {key} found")

            next_token = self.lexer.peek_token()
            if next_token.type is TokenType.DICT_END or next_token.type is TokenType.EOF:
                raise PdfParseError(f"expected value after key {key}")

            value = self.next_object()
            assert value is not None

            values[key.value.decode()] = value

    def _parse_array(self) -> PdfArray:
        """Parses a PDF array."""

        token = self.lexer.peek_token()
        if token.type is not TokenType.ARRAY_START:
            raise PdfParseError("expected PDF array at this point")

        self.lexer.next_token()

        values = PdfArray()

        while True:
            token = self.lexer.peek_token()
            if token.type is TokenType.ARRAY_END:
                self.lexer.next_token()
                return values

            if (value := self.next_object()) is not None:
                values.append(value)
            else:
                raise PdfParseError("unterminated array")

    def _parse_integer_or_reference(self, first_token: PdfToken) -> int | PdfReference:
        """Parses either an integer or an indirect reference (``1 0 R``) from the lexer."""

        # simple sanity check
        if first_token.type is not TokenType.INTEGER:
            raise PdfParseError("expected integer at this point")

        first_obj = int(first_token.value)

        second_token = self.lexer.peek_token()
        if second_token.type is not TokenType.INTEGER:
            return first_obj

        third_token = self.lexer.peek_token(1)
        if third_token.type is not TokenType.WORD or third_token.value != b"R":
            return first_obj

        # At this point, we have determined that we have a reference candidate,
        # that is, INTEGER INTEGER WORD.
        #
        # For this candidate to be a valid reference (ISO 32000-2:2020 § 7.3.10):
        #  - The word must be the value "R".
        #  - The object number must be positive. It must not contain leading zeros
        #    and must not contain the + sign.
        #  - The generation number must be non-negative. Similar to object numbers,
        #    it shall not contain the + or - sign. Leading zeros are not allowed,
        #    though single digit zero is.

        self.lexer.next_token()  # consume second integer
        self.lexer.next_token()  # consume R

        if first_token.value.startswith((b"+", b"-", b"0")):
            raise PdfParseError(f"invalid object number {first_token.value!r}")

        if second_token.value != b"0" and second_token.value.startswith((b"+", b"-", b"0")):
            raise PdfParseError(f"invalid generation number {second_token.value!r}")

        reference = PdfReference(
            object_number=int(first_token.value), generation=int(second_token.value)
        )

        if self.resolver is not None:
            return reference.with_resolver(self.resolver)

        return reference
