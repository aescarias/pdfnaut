# Unit tests for parsing COS objects.
from __future__ import annotations

from pdfnaut.cos.lexer import PdfLexer
from pdfnaut.cos.object_parser import PdfObjectParser
from pdfnaut.cos.objects import (
    PdfArray,
    PdfDictionary,
    PdfHexString,
    PdfName,
    PdfNull,
    PdfObject,
    PdfReference,
)


def _parse_objects(data: bytes) -> list[PdfObject]:
    lexer = PdfLexer(data)
    parser = PdfObjectParser(lexer)

    return list(parser)


def test_null_and_boolean() -> None:
    objects = _parse_objects(b"null true false")
    assert isinstance(objects[0], PdfNull)
    assert objects[1:] == [True, False]


def test_numeric() -> None:
    objects = _parse_objects(b"-1 +25 46 -32.591 +52.871 3.1451 -.302 3. .25")
    assert objects == [-1, 25, 46, -32.591, 52.871, 3.1451, -0.302, 3.0, 0.25]


def test_name_object() -> None:
    objects = _parse_objects(b"/Type /SomeR@ndomK*y /Lime#20Green / /F#23")
    assert objects == [
        PdfName(b"Type"),
        PdfName(b"SomeR@ndomK*y"),
        PdfName(b"Lime Green"),
        PdfName(b""),
        PdfName(b"F#"),
    ]


def test_literal_string() -> None:
    # Basic string
    assert _parse_objects(b"(The quick brown fox jumps over the lazy dog.)") == [
        b"The quick brown fox jumps over the lazy dog."
    ]

    # String with nested parentheses
    assert _parse_objects(b"(This is a string with a (few) nested ((parentheses)))") == [
        b"This is a string with a (few) nested ((parentheses))"
    ]

    # String continued in next line
    assert _parse_objects(b"(This is a string that is \r\ncontinued on the next line)") == [
        b"This is a string that is \ncontinued on the next line"
    ]

    # String ending with a \ at the EOL and followed next line
    assert _parse_objects(b"(This is a string \\\r\nwith no newlines.)") == [
        b"This is a string with no newlines."
    ]

    # String with escape characters
    assert _parse_objects(b"(This is a string with a \\t tab character and a \\053 plus.)") == [
        b"This is a string with a \t tab character and a + plus."
    ]

    # String with contiguous octal sequences
    assert _parse_objects(b"(\\110\\151\\41)") == [b"Hi!"]

    # String with invalid octal sequences
    assert _parse_objects(b"(\\318 then \\387 and then \\981)") == [b"\318 then \387 and then 981"]


def test_hex_string() -> None:
    # test hex strings with no whitespace
    tokens = _parse_objects(b"<A5B2FF><6868ADE>")
    assert tokens == [PdfHexString(b"A5B2FF"), PdfHexString(b"6868ADE0")]

    # test that whitespace is ignored when parsing hex strings
    hex_str = _parse_objects(b"<58 50>")[0]
    assert hex_str == PdfHexString(b"5850")

    # test that zero is appended to hex string if odd
    hex_str = _parse_objects(b"<58 5c e>")[0]
    assert hex_str == PdfHexString(b"585ce0")

    # test the empty string
    hex_str = _parse_objects(b"<>")[0]
    assert hex_str == PdfHexString(b"")


def test_dictionary() -> None:
    assert _parse_objects(b"""<< /Type /Catalog /Metadata 2 0 R /Pages 3 0 R >>""") == [
        PdfDictionary(
            {
                "Type": PdfName(b"Catalog"),
                "Metadata": PdfReference(2, 0),
                "Pages": PdfReference(3, 0),
            }
        )
    ]


def test_array() -> None:
    # Simple array
    assert _parse_objects(b"[45 <</Size 40>> (42)]") == [PdfArray([45, {"Size": 40}, b"42"])]

    # Nested array
    assert _parse_objects(b"[/XYZ [45 32 76] /Great]") == [
        PdfArray([PdfName(b"XYZ"), [45, 32, 76], PdfName(b"Great")])
    ]


def test_indirect_reference() -> None:
    assert _parse_objects(b"2 0 R") == [PdfReference(2, 0)]
