# Unit tests for the Simple Object Parser

from __future__ import annotations

from typing import cast

from pdfnaut.parsers import SimpleObjectParser
from pdfnaut.objects import PdfName, PdfIndirectRef, PdfHexString, PdfNull, PdfComment


def test_null_and_boolean() -> None:
    parser = SimpleObjectParser(b"null true false")
    tokens = list(parser)

    assert isinstance(tokens[0], PdfNull)
    assert tokens[1] is True and tokens[2] is False

def test_numeric() -> None:
    parser = SimpleObjectParser(b"-1 +25 46 -32.591 +52.871 3.1451")
    tokens = list(parser)

    assert tokens == [-1, 25, 46, -32.591, 52.871, 3.1451]

def test_name_object() -> None:
    parser = SimpleObjectParser(b"/Type /SomeR@ndomK*y /Lime#20Green / /F#23")
    tokens = list(parser)
    assert tokens == [ PdfName(b"Type"), PdfName(b"SomeR@ndomK*y"), PdfName(b"Lime Green"), 
                       PdfName(b""), PdfName(b"F#") ]

def test_literal_string() -> None:
    # Basic string
    parser = SimpleObjectParser(b"(The quick brown fox jumps over the lazy dog.)")
    assert parser.next_token() == b"The quick brown fox jumps over the lazy dog."

    # String with nested parentheses
    parser = SimpleObjectParser(b"(This is a string with a (few) nested ((parentheses)))")
    assert parser.next_token() == b"This is a string with a (few) nested ((parentheses))"

    # String continued in next line
    parser = SimpleObjectParser(b"(This is a string that is \r\n"
                                b"continued on the next line)")
    assert parser.next_token() == b"This is a string that is \r\ncontinued on the next line"

    # String ending with a \ at the EOL and followed next line
    parser = SimpleObjectParser(b"(This is a string \\\r\nwith no newlines.)")
    assert parser.next_token() == b"This is a string with no newlines."

    # String with escape characters
    parser = SimpleObjectParser(b"(This is a string with a \\t tab character and a \\053 plus.))")
    assert parser.next_token() == b"This is a string with a \t tab character and a + plus."

def test_hex_string() -> None:
    parser = SimpleObjectParser(b"<A5B2FF><6868ADE>")
    tokens = cast("list[PdfHexString]", list(parser))

    assert tokens[0].raw == b"A5B2FF" and tokens[1].raw == b"6868ADE0" 

def test_dictionary() -> None:
    parser = SimpleObjectParser(b"""<< /Type /Catalog /Metadata 2 0 R /Pages 3 0 R >>""")
    assert parser.next_token() == { 
        "Type": PdfName(b"Catalog"), 
        "Metadata": PdfIndirectRef(2, 0), 
        "Pages": PdfIndirectRef(3, 0) 
    }

def test_comment() -> None:
    # This also counts as an EOL test
    parser = SimpleObjectParser(b"% This is a comment\r\n"
                                b"12 % This is another comment\r"
                                b"25\n")
    assert isinstance(com := next(parser), PdfComment) \
        and com.value == b" This is a comment"
    assert next(parser) == 12
    assert isinstance(com := next(parser), PdfComment) and \
        com.value == b" This is another comment"
    assert next(parser) == 25

    parser = SimpleObjectParser(b"% This is a comment ending with \\r\r")
    assert isinstance(com := parser.next_token(), PdfComment) \
        and com.value == b" This is a comment ending with \\r"

def test_array() -> None:
    # Simple array
    parser = SimpleObjectParser(b"[45 <</Size 40>> (42)]") 
    assert parser.next_token() == [45, { "Size": 40 }, b"42"]
    
    # Nested array
    parser = SimpleObjectParser(b"[/XYZ [45 32 76] /Great]")
    assert parser.next_token() == [PdfName(b"XYZ"), [45, 32, 76], PdfName(b"Great")]
