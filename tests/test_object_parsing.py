# Unit tests for tokenizing the COS syntax in PDFs.

from __future__ import annotations

import datetime
from typing import cast

from pdfnaut import PdfTokenizer
from pdfnaut.common.dates import encode_iso8824, parse_iso8601, parse_iso8824
from pdfnaut.cos.objects import (
    PdfArray,
    PdfComment,
    PdfDictionary,
    PdfHexString,
    PdfName,
    PdfNull,
    PdfReference,
)


def test_null_and_boolean() -> None:
    lexer = PdfTokenizer(b"null true false")
    tokens = list(lexer)

    assert isinstance(tokens[0], PdfNull)
    assert tokens[1] is True and tokens[2] is False


def test_numeric() -> None:
    lexer = PdfTokenizer(b"-1 +25 46 -32.591 +52.871 3.1451")
    tokens = list(lexer)

    assert tokens == [-1, 25, 46, -32.591, 52.871, 3.1451]


def test_name_object() -> None:
    lexer = PdfTokenizer(b"/Type /SomeR@ndomK*y /Lime#20Green / /F#23")
    tokens = list(lexer)
    assert tokens == [
        PdfName(b"Type"),
        PdfName(b"SomeR@ndomK*y"),
        PdfName(b"Lime Green"),
        PdfName(b""),
        PdfName(b"F#"),
    ]


def test_literal_string() -> None:
    # Basic string
    lexer = PdfTokenizer(b"(The quick brown fox jumps over the lazy dog.)")
    assert lexer.get_next_token() == b"The quick brown fox jumps over the lazy dog."

    # String with nested parentheses
    lexer = PdfTokenizer(b"(This is a string with a (few) nested ((parentheses)))")
    assert lexer.get_next_token() == b"This is a string with a (few) nested ((parentheses))"

    # String continued in next line
    lexer = PdfTokenizer(b"(This is a string that is \r\n" b"continued on the next line)")
    assert lexer.get_next_token() == b"This is a string that is \r\ncontinued on the next line"

    # String ending with a \ at the EOL and followed next line
    lexer = PdfTokenizer(b"(This is a string \\\r\nwith no newlines.)")
    assert lexer.get_next_token() == b"This is a string with no newlines."

    # String with escape characters
    lexer = PdfTokenizer(b"(This is a string with a \\t tab character and a \\053 plus.))")
    assert lexer.get_next_token() == b"This is a string with a \t tab character and a + plus."


def test_hex_string() -> None:
    lexer = PdfTokenizer(b"<A5B2FF><6868ADE>")
    tokens = cast("list[PdfHexString]", list(lexer))

    assert tokens[0].raw == b"A5B2FF" and tokens[1].raw == b"6868ADE0"


def test_dictionary() -> None:
    lexer = PdfTokenizer(b"""<< /Type /Catalog /Metadata 2 0 R /Pages 3 0 R >>""")
    assert lexer.get_next_token() == PdfDictionary(
        {"Type": PdfName(b"Catalog"), "Metadata": PdfReference(2, 0), "Pages": PdfReference(3, 0)}
    )


def test_comment_and_eol() -> None:
    lexer = PdfTokenizer(b"% This is a comment\r\n" b"12 % This is another comment\r" b"25\n")
    assert isinstance(com := next(lexer), PdfComment) and com.value == b" This is a comment"
    assert next(lexer) == 12
    assert isinstance(com := next(lexer), PdfComment) and com.value == b" This is another comment"
    assert next(lexer) == 25

    lexer = PdfTokenizer(b"% This is a comment ending with \\r\r")
    assert (
        isinstance(com := lexer.get_next_token(), PdfComment)
        and com.value == b" This is a comment ending with \\r"
    )


def test_array() -> None:
    # Simple array
    lexer = PdfTokenizer(b"[45 <</Size 40>> (42)]")
    assert lexer.get_next_token() == PdfArray([45, {"Size": 40}, b"42"])

    # Nested array
    lexer = PdfTokenizer(b"[/XYZ [45 32 76] /Great]")
    assert lexer.get_next_token() == PdfArray([PdfName(b"XYZ"), [45, 32, 76], PdfName(b"Great")])


def test_indirect_reference() -> None:
    lexer = PdfTokenizer(b"2 0 R")
    assert lexer.get_next_token() == PdfReference(2, 0)


def test_iso8824() -> None:
    # Some examples from the spec
    assert parse_iso8824("D:199812231952-08'00") == datetime.datetime(
        1998, 12, 23, 19, 52, 0, tzinfo=datetime.timezone(datetime.timedelta(hours=-8, minutes=0))
    )
    assert parse_iso8824("D:20010727133720") == datetime.datetime(
        2001, 7, 27, 13, 37, 20, tzinfo=datetime.timezone.utc
    )

    # Possible pre-2.0 date string
    assert parse_iso8824("D:2024'") == datetime.datetime(
        2024, 1, 1, 0, tzinfo=datetime.timezone.utc
    )

    # Encoding
    assert encode_iso8824(datetime.datetime(2001, 7, 27, 13, 37, 20)) == "D:20010727133720Z"


def test_iso8601() -> None:
    # Only year
    assert parse_iso8601("2025") == datetime.datetime(
        2025, 1, 1, 0, 0, tzinfo=datetime.timezone.utc
    )
    # Date
    assert parse_iso8601("2025-02-01") == datetime.datetime(
        2025, 2, 1, 0, 0, tzinfo=datetime.timezone.utc
    )
    # Date and time without seconds
    assert parse_iso8601("2025-02-01T12:31") == datetime.datetime(
        2025, 2, 1, 12, 31, tzinfo=datetime.timezone.utc
    )
    # Date and time with seconds
    assert parse_iso8601("2025-02-01T12:31:17") == datetime.datetime(
        2025, 2, 1, 12, 31, 17, tzinfo=datetime.timezone.utc
    )
    # Date and time with seconds and fraction unit
    assert parse_iso8601("2025-02-01T12:31:17.20") == datetime.datetime(
        2025, 2, 1, 12, 31, 17, 200_000, tzinfo=datetime.timezone.utc
    )
    # Date and time with seconds, fraction unit, and timezone
    tzd = datetime.timezone(datetime.timedelta(hours=-6, minutes=0))
    assert parse_iso8601("2025-02-01T12:31:17.20-06:00") == datetime.datetime(
        2025, 2, 1, 12, 31, 17, 200_000, tzd
    )
