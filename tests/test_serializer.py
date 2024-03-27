# Unit Tests for serializing the COS syntax seen in PDFs
#
# The main assumption made is that EOLs are CRLF by default.

from __future__ import annotations

from pdfnaut.objects import (PdfName, PdfIndirectRef, PdfHexString, PdfNull,
                             PdfComment, PdfStream, FreeXRefEntry, InUseXRefEntry,)
from pdfnaut.serializer import serialize, PdfSerializer


def test_comment() -> None:
    assert serialize(PdfComment(b"Comment")) == b"%Comment"


def test_null_and_boolean() -> None:
    assert serialize(True) == b"true"
    assert serialize(False) == b"false"
    assert serialize(PdfNull()) == b"null"


def test_numeric() -> None:
    assert serialize(-1) == b"-1"
    assert serialize(-5.402) == b"-5.402"
    assert serialize(46) == b"46"
    assert serialize(3.1415) == b"3.1415"


def test_name_object() -> None:
    assert serialize(PdfName(b"Type")) == b"/Type"
    assert serialize(PdfName(b"Lime Green")) == b"/Lime#20Green"
    assert serialize(PdfName(b"F#")) == b"/F#23"


def test_literal_string() -> None:
    # Basic string
    assert serialize(b"The quick brown fox") == b"(The quick brown fox)"

    # Nested parenthesis
    assert serialize(b"(Hello world)") == b"((Hello world))"
    assert serialize(b"(Hello again))") == b"((Hello again)\\))"

    # Escape characters
    assert (
        serialize(b"This is a string with a \t character and a + sign.")
        == b"(This is a string with a \\t character and a + sign.)"
    )

    # keep_ascii
    assert serialize(b"Espa\xf1ol", params={"keep_ascii": True}) == b"(Espa\\361ol)"


def test_hex_string() -> None:
    assert serialize(PdfHexString(b"A5B2FF")) == b"<A5B2FF>"


def test_dictionary() -> None:
    assert serialize(
        {
            "Type": PdfName(b"Catalog"),
            "Metadata": PdfIndirectRef(2, 0),
            "Pages": PdfIndirectRef(3, 0),
        }
    ) == b"<</Type /Catalog /Metadata 2 0 R /Pages 3 0 R>>"


def test_array() -> None:
    assert serialize([45, {"Size": 40}, b"data"]) == b"[45 <</Size 40>> (data)]"
    assert serialize([PdfName(b"XYZ"), 45, 32, 76]) == b"[/XYZ 45 32 76]"


def test_stream() -> None:
    stream = PdfStream({"Length": 11}, b"Hello World")
    assert serialize(stream, params={"eol": b"\r\n"}) == b"<</Length 11>>\r\nstream\r\nHello World\r\nendstream"


def test_serialize_document() -> None:
    serializer = PdfSerializer()
    serializer.write_header("1.7")
    assert serializer.content.startswith(b"%PDF-1.7\r\n")
    before_object = len(serializer.content)

    object_start = serializer.write_object((1, 0), {"A": b"BC", "D": 10.24})
    assert before_object == object_start
    assert serializer.content.endswith(b"1 0 obj\r\n<</A (BC) /D 10.24>>\r\nendobj\r\n")

    table = serializer.generate_standard_xref_table(
        [("f", 0, 65535, 0), ("n", 1, 0, object_start)]
    )
    assert (
        len(table.sections)
        and table.sections[0].first_obj_number == 0
        and table.sections[0].count == 2
        and isinstance(table.sections[0].entries[0], FreeXRefEntry)
        and isinstance(table.sections[0].entries[1], InUseXRefEntry)
    )
    
    before_xref = len(serializer.content)
    startxref = serializer.write_standard_xref_table(table)
    assert before_xref == startxref
     
    serializer.write_trailer({"Size": 2}, startxref)
    assert serializer.content.endswith(b"trailer\r\n<</Size 2>>\r\n" + 
                                       b"startxref\r\n" + str(startxref).encode() + 
                                       b"\r\n")
    serializer.write_eof()
    assert serializer.content.endswith(b"%%EOF\r\n")
