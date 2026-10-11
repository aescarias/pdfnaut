# Unit tests for tokenizing the COS syntax in PDFs.

from __future__ import annotations

import pytest

from pdfnaut.cos.cstm_parser import ContentStreamParser
from pdfnaut.cos.lexer import PdfLexer, PdfToken, TokenType
from pdfnaut.cos.objects import PdfArray, PdfDictionary, PdfInlineImage, PdfName, PdfOperator
from pdfnaut.exceptions import PdfParseError


def test_null_and_bool_tokens() -> None:
    lexer = PdfLexer(b"null true false")
    assert list(lexer) == [
        PdfToken(TokenType.NULL, b"null"),
        PdfToken(TokenType.TRUE, b"true"),
        PdfToken(TokenType.FALSE, b"false"),
    ]


def test_number_tokens() -> None:
    lexer = PdfLexer(b"-1 +25 46 -32.591 +52.871 3.1451 -.302 3. .25")
    assert list(lexer) == [
        PdfToken(TokenType.INTEGER, b"-1"),
        PdfToken(TokenType.INTEGER, b"+25"),
        PdfToken(TokenType.INTEGER, b"46"),
        PdfToken(TokenType.REAL, b"-32.591"),
        PdfToken(TokenType.REAL, b"+52.871"),
        PdfToken(TokenType.REAL, b"3.1451"),
        PdfToken(TokenType.REAL, b"-.302"),
        PdfToken(TokenType.REAL, b"3."),
        PdfToken(TokenType.REAL, b".25"),
    ]


def test_name_tokens() -> None:
    lexer = PdfLexer(b"/Type /SomeR@ndomK*y /Lime#20Green / /F#23")
    assert list(lexer) == [
        PdfToken(TokenType.NAME, b"Type"),
        PdfToken(TokenType.NAME, b"SomeR@ndomK*y"),
        PdfToken(TokenType.NAME, b"Lime Green"),
        PdfToken(TokenType.NAME, b""),
        PdfToken(TokenType.NAME, b"F#"),
    ]


def test_literal_string() -> None:
    # Basic string
    lexer = PdfLexer(b"(The quick brown fox jumps over the lazy dog.)")
    assert lexer.next_token() == PdfToken(
        TokenType.LIT_STRING, b"The quick brown fox jumps over the lazy dog."
    )

    # String with nested parentheses
    lexer = PdfLexer(b"(This is a string with a (few) nested ((parentheses)))")
    assert lexer.next_token() == PdfToken(
        TokenType.LIT_STRING, b"This is a string with a (few) nested ((parentheses))"
    )

    # String continued in next line
    # Also check that EOLs are translated to LF.
    lexer = PdfLexer(b"(This is a string that is \r\ncontinued on the next line)")
    assert lexer.next_token() == PdfToken(
        TokenType.LIT_STRING, b"This is a string that is \ncontinued on the next line"
    )

    # String ending with a \ at the EOL and followed next line
    lexer = PdfLexer(b"(This is a string \\\r\nwith no newlines.)")
    assert lexer.next_token() == PdfToken(
        TokenType.LIT_STRING, b"This is a string with no newlines."
    )

    # String with escape characters
    lexer = PdfLexer(b"(This is a string with a \\t tab character and a \\053 plus.))")
    assert lexer.next_token() == PdfToken(
        TokenType.LIT_STRING, b"This is a string with a \t tab character and a + plus."
    )

    # String with contiguous octal sequences
    lexer = PdfLexer(b"(\\110\\151\\41)")
    assert lexer.next_token() == PdfToken(TokenType.LIT_STRING, b"Hi!")

    # String with invalid octal sequences
    lexer = PdfLexer(b"(\\318 then \\387 and then \\981)")
    assert lexer.next_token() == PdfToken(TokenType.LIT_STRING, b"\318 then \387 and then 981")


def test_hex_string() -> None:
    # test hex strings with no whitespace
    lexer = PdfLexer(b"<A5B2FF><6868ADE>")
    assert list(lexer) == [
        PdfToken(TokenType.HEX_STRING, b"A5B2FF"),
        PdfToken(TokenType.HEX_STRING, b"6868ADE0"),
    ]

    # test that whitespace is ignored when parsing hex strings
    lexer = PdfLexer(b"<58 50>")
    assert next(lexer) == PdfToken(TokenType.HEX_STRING, b"5850")

    # test that zero is appended to hex string if odd
    lexer = PdfLexer(b"<58 5c e>")
    assert next(lexer) == PdfToken(TokenType.HEX_STRING, b"585ce0")

    # test the empty string
    lexer = PdfLexer(b"<>")
    assert next(lexer) == PdfToken(TokenType.HEX_STRING, b"")

    # test that invalid characters raise an exception
    with pytest.raises(PdfParseError):
        PdfLexer(b"<AB XX DE>").next_token()

    # test that comments are not allowed
    # https://github.com/pdf-association/pdf-issues/issues/731
    with pytest.raises(PdfParseError):
        PdfLexer(b"<%abcdef\nAB>").next_token()


def test_dictionary_tokens() -> None:
    lexer = PdfLexer(b"""<< /Type /Catalog >>""")
    assert list(lexer) == [
        PdfToken(TokenType.DICT_START, b"<<"),
        PdfToken(TokenType.NAME, b"Type"),
        PdfToken(TokenType.NAME, b"Catalog"),
        PdfToken(TokenType.DICT_END, b">>"),
    ]


def test_comment_and_eol() -> None:
    lexer = PdfLexer(b"% This is a comment\r\n12 % This is another comment\r25\n")
    assert list(lexer) == [
        PdfToken(TokenType.COMMENT, b" This is a comment"),
        PdfToken(TokenType.INTEGER, b"12"),
        PdfToken(TokenType.COMMENT, b" This is another comment"),
        PdfToken(TokenType.INTEGER, b"25"),
    ]

    lexer = PdfLexer(b"% This is a comment ending with \\r\r")
    assert next(lexer) == PdfToken(TokenType.COMMENT, b" This is a comment ending with \\r")


def test_array_tokens() -> None:
    lexer = PdfLexer(b"[/XYZ [45 32 76] /Great]")
    assert list(lexer) == [
        PdfToken(TokenType.ARRAY_START, b"["),
        PdfToken(TokenType.NAME, b"XYZ"),
        PdfToken(TokenType.ARRAY_START, b"["),
        PdfToken(TokenType.INTEGER, b"45"),
        PdfToken(TokenType.INTEGER, b"32"),
        PdfToken(TokenType.INTEGER, b"76"),
        PdfToken(TokenType.ARRAY_END, b"]"),
        PdfToken(TokenType.NAME, b"Great"),
        PdfToken(TokenType.ARRAY_END, b"]"),
    ]


def test_content_stream() -> None:
    # test that we aren't parsing the references
    lexer = ContentStreamParser(b"1 0 0 RG 0 w")
    assert list(lexer) == [PdfOperator(b"RG", [1, 0, 0]), PdfOperator(b"w", [0])]

    # test without padding
    lexer = ContentStreamParser(b"/F29 12 Tf 100 740 Td[(Lorem)-447(ipsum)-446(text.)]TJ")

    assert list(lexer) == [
        PdfOperator(b"Tf", [PdfName(b"F29"), 12]),
        PdfOperator(b"Td", [100, 740]),
        PdfOperator(b"TJ", [PdfArray([b"Lorem", -447, b"ipsum", -446, b"text."])]),
    ]

    # test that we are parsing other objects
    lexer = ContentStreamParser(b"/F1 12 Tf 72 712 Td (A stream with an indirect length) Tj")
    assert list(lexer) == [
        PdfOperator(b"Tf", [PdfName(b"F1"), 12]),
        PdfOperator(b"Td", [72, 712]),
        PdfOperator(b"Tj", [b"A stream with an indirect length"]),
    ]

    # test that we are parsing an inline image
    lexer = ContentStreamParser(b"""\
BI              % Begin inline image object
    /W 17 /H 17 % Width and height in samples
    /CS /RGB    % Color space
    /BPC 8      % Bits per component
    /F [/A85]   % Filters
ID              % Begin image data
E,8rmAS?!uA7]d(AoD]4Bl.9kAH~>
EI              % End inline image object
    """)

    assert list(lexer) == [
        PdfInlineImage(
            PdfDictionary(W=17, H=17, CS=PdfName(b"RGB"), BPC=8, F=PdfArray([PdfName(b"A85")])),
            b"E,8rmAS?!uA7]d(AoD]4Bl.9kAH~>\n",
        )
    ]
