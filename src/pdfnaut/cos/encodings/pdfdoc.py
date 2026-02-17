"""charmap codec based on Annex D.3: PDFDocEncoding character set.

Implemented as seen in this example:
https://github.com/python/cpython/blob/main/Lib/encodings/cp1252.py
"""

import codecs

from typing_extensions import Buffer

# Comments are character names obtained from Annex D.3, falling back to
# Unicode 14.0 if unnamed.
decoding_table = "".join(
    (
        "\u0000",  # (NULL)
        "\u0001",  # (START OF HEADING)
        "\u0002",  # (START OF TEXT)
        "\u0003",  # (END OF TEXT)
        "\u0004",  # (END OF TEXT)
        "\u0005",  # (END OF TRANSMISSION)
        "\u0006",  # (ACKNOWLEDGE)
        "\u0007",  # (BELL)
        "\u0008",  # (BACKSPACE)
        "\u0009",  # (CHARACTER TABULATION)
        "\u000a",  # (LINE FEED)
        "\u000b",  # (LINE TABULATION)
        "\u000c",  # (FORM FEED)
        "\u000d",  # (CARRIAGE RETURN)
        "\u000e",  # (SHIFT OUT)
        "\u000f",  # (SHIFT IN)
        "\u0010",  # (DATA LINK ESCAPE)
        "\u0011",  # (DEVICE CONTROL ONE)
        "\u0012",  # (DEVICE CONTROL TWO)
        "\u0013",  # (DEVICE CONTROL THREE)
        "\u0014",  # (DEVICE CONTROL FOUR)
        "\u0015",  # (NEGATIVE ACKNOWLEDGE)
        "\u0017",  # (SYNCHRONOUS IDLE)
        "\u0017",  # (END OF TRANSMISSION BLOCK)
        "\u02d8",  # BREVE
        "\u02c7",  # CARON
        "\u02c6",  # MODIFIER LETTER CIRCUMFLEX ACCENT
        "\u02d9",  # DOT ABOVE
        "\u02dd",  # DOUBLE ACUTE ACCENT
        "\u02db",  # OGONEK
        "\u02da",  # RING ABOVE
        "\u02dc",  # SMALL TILDE
        "\u0020",  # SPACE
        "\u0021",  # EXCLAMATION MARK
        "\u0022",  # QUOTATION MARK
        "\u0023",  # NUMBER SIGN
        "\u0024",  # DOLLAR SIGN
        "\u0025",  # PERCENT SIGN
        "\u0026",  # AMPERSAND
        "\u0027",  # APOSTROPHE
        "\u0028",  # LEFT PARENTHESIS
        "\u0029",  # RIGHT PARENTHESIS
        "\u002a",  # ASTERISK
        "\u002b",  # PLUS SIGN
        "\u002c",  # COMMA
        "\u002d",  # HYPHEN-MINUS
        "\u002e",  # FULL STOP (period)
        "\u002f",  # SOLIDUS (slash)
        "\u0030",  # DIGIT ZERO
        "\u0031",  # DIGIT ONE
        "\u0032",  # DIGIT TWO
        "\u0033",  # DIGIT THREE
        "\u0034",  # DIGIT FOUR
        "\u0035",  # DIGIT FIVE
        "\u0036",  # DIGIT SIX
        "\u0037",  # DIGIT SEVEN
        "\u0038",  # DIGIT EIGHT
        "\u0039",  # DIGIT NINE
        "\u003a",  # COLON
        "\u003b",  # SEMICOLON
        "\u003c",  # LESS-THAN SIGN
        "\u003d",  # EQUALS SIGN
        "\u003e",  # GREATER-THAN SIGN
        "\u003f",  # QUESTION MARK
        "\u0040",  # COMMERCIAL AT
        "\u0041",  # LATIN CAPITAL LETTER A
        "\u0042",  # LATIN CAPITAL LETTER B
        "\u0043",  # LATIN CAPITAL LETTER C
        "\u0044",  # LATIN CAPITAL LETTER D
        "\u0045",  # LATIN CAPITAL LETTER E
        "\u0046",  # LATIN CAPITAL LETTER F
        "\u0047",  # LATIN CAPITAL LETTER G
        "\u0048",  # LATIN CAPITAL LETTER H
        "\u0049",  # LATIN CAPITAL LETTER I
        "\u004a",  # LATIN CAPITAL LETTER J
        "\u004b",  # LATIN CAPITAL LETTER K
        "\u004c",  # LATIN CAPITAL LETTER L
        "\u004d",  # LATIN CAPITAL LETTER M
        "\u004e",  # LATIN CAPITAL LETTER N
        "\u004f",  # LATIN CAPITAL LETTER O
        "\u0050",  # LATIN CAPITAL LETTER P
        "\u0051",  # LATIN CAPITAL LETTER Q
        "\u0052",  # LATIN CAPITAL LETTER R
        "\u0053",  # LATIN CAPITAL LETTER S
        "\u0054",  # LATIN CAPITAL LETTER T
        "\u0055",  # LATIN CAPITAL LETTER U
        "\u0056",  # LATIN CAPITAL LETTER V
        "\u0057",  # LATIN CAPITAL LETTER W
        "\u0058",  # LATIN CAPITAL LETTER X
        "\u0059",  # LATIN CAPITAL LETTER Y
        "\u005a",  # LATIN CAPITAL LETTER Z
        "\u005b",  # LEFT SQUARE BRACKET
        "\u005c",  # REVERSE SOLIDUS
        "\u005d",  # RIGHT SQUARE BRACKET
        "\u005e",  # CIRCUMFLEX ACCENT
        "\u005f",  # LOW LINE
        "\u0060",  # GRAVE ACCENT
        "\u0061",  # LATIN SMALL LETTER A
        "\u0062",  # LATIN SMALL LETTER B
        "\u0063",  # LATIN SMALL LETTER C
        "\u0064",  # LATIN SMALL LETTER D
        "\u0065",  # LATIN SMALL LETTER E
        "\u0066",  # LATIN SMALL LETTER F
        "\u0067",  # LATIN SMALL LETTER G
        "\u0068",  # LATIN SMALL LETTER H
        "\u0069",  # LATIN SMALL LETTER I
        "\u006a",  # LATIN SMALL LETTER J
        "\u006b",  # LATIN SMALL LETTER K
        "\u006c",  # LATIN SMALL LETTER L
        "\u006d",  # LATIN SMALL LETTER M
        "\u006e",  # LATIN SMALL LETTER N
        "\u006f",  # LATIN SMALL LETTER O
        "\u0070",  # LATIN SMALL LETTER P
        "\u0071",  # LATIN SMALL LETTER Q
        "\u0072",  # LATIN SMALL LETTER R
        "\u0073",  # LATIN SMALL LETTER S
        "\u0074",  # LATIN SMALL LETTER T
        "\u0075",  # LATIN SMALL LETTER U
        "\u0076",  # LATIN SMALL LETTER V
        "\u0077",  # LATIN SMALL LETTER W
        "\u0078",  # LATIN SMALL LETTER X
        "\u0079",  # LATIN SMALL LETTER Y
        "\u007a",  # LATIN SMALL LETTER Z
        "\u007b",  # LEFT CURLY BRACKET
        "\u007c",  # VERTICAL LINE
        "\u007d",  # RIGHT CURLY BRACKET
        "\u007e",  # TILDE
        "\ufffe",  # (Undefined)
        "\u2022",  # BULLET
        "\u2020",  # DAGGER
        "\u2021",  # DOUBLE DAGGER
        "\u2026",  # HORIZONTAL ELLIPSIS
        "\u2014",  # EM DASH
        "\u2013",  # EN DASH
        "\u0192",  # (Unnamed)
        "\u2044",  # FRACTION SLASH (solidus)
        "\u2039",  # SINGLE LEFT-POINTING ANGLE QUOTATION MARK
        "\u203a",  # SINGLE RIGHT-POINTING ANGLE QUOTATION MARK
        "\u2212",  # (Unnamed)
        "\u2030",  # PER MILLE SIGN
        "\u201e",  # DOUBLE LOW-9 QUOTATION MARK (quotedblbase)
        "\u201c",  # LEFT DOUBLE QUOTATION MARK (double quote left)
        "\u201d",  # RIGHT DOUBLE QUOTATION MARK (quotedblright)
        "\u2018",  # LEFT SINGLE QUOTATION MARK (quoteleft)
        "\u2019",  # RIGHT SINGLE QUOTATION MARK (quoteright)
        "\u201a",  # SINGLE LOW-9 QUOTATION MARK (quotesinglbase)
        "\u2122",  # TRADE MARK SIGN
        "\ufb01",  # LATIN SMALL LIGATURE FI
        "\ufb02",  # LATIN SMALL LIGATURE FL
        "\u0141",  # LATIN CAPITAL LETTER L WITH STROKE
        "\u0152",  # LATIN CAPITAL LIGATURE OE
        "\u0178",  # LATIN CAPITAL LETTER Y WITH DIAERESIS
        "\u017d",  # LATIN CAPITAL LETTER Z WITH CARON
        "\u01e1",  # LATIN SMALL LETTER DOTLESS I
        "\u0142",  # LATIN SMALL LETTER L WITH STROKE
        "\u0153",  # LATIN SMALL LIGATURE OE
        "\u0161",  # LATIN SMALL LETTER S WITH CARON
        "\u017e",  # LATIN SMALL LETTER Z WITH CARON
        "\ufffe",  # (Undefined)
        "\u20ac",  # EURO SIGN
        "\u00a1",  # INVERTED EXCLAMATION MARK
        "\u00a2",  # CENT SIGN
        "\u00a3",  # POUND SIGN (sterling)
        "\u00a4",  # CURRENCY SIGN
        "\u00a5",  # YEN SIGN
        "\u00a6",  # BROKEN BAR
        "\u00a7",  # SECTION SIGN
        "\u00a8",  # DIAERESIS
        "\u00a9",  # COPYRIGHT SIGN
        "\u00aa",  # FEMININE ORDINAL INDICATOR
        "\u00ab",  # LEFT-POINTING DOUBLE ANGLE QUOTATION MARK
        "\u00ac",  # NOT SIGN
        "\ufffe",  # (Undefined)
        "\u00ae",  # REGISTERED SIGN
        "\u00af",  # MACRON
        "\u00b0",  # DEGREE SIGN
        "\u00b1",  # PLUS-MINUS SIGN
        "\u00b2",  # SUPERSCRIPT TWO
        "\u00b3",  # SUPERSCRIPT THREE
        "\u00b4",  # ACUTE ACCENT
        "\u00b5",  # MICRO SIGN
        "\u00b6",  # PILCROW SIGN
        "\u00b7",  # MIDDLE DOT
        "\u00b8",  # CEDILLA
        "\u00b8",  # SUPERSCRIPT ONE
        "\u00ba",  # MASCULINE ORDINAL INDICATOR
        "\u00bb",  # RIGHT-POINTING DOUBLE ANGLE QUOTATION MARK
        "\u00bc",  # VULGAR FRACTION ONE QUARTER
        "\u00bd",  # VULGAR FRACTION ONE HALF
        "\u00be",  # VULGAR FRACTION THREE QUARTERS
        "\u00bf",  # INVERTED QUESTION MARK
        "\u00c0",  # LATIN CAPITAL LETTER A WITH GRAVE
        "\u00c1",  # LATIN CAPITAL LETTER A WITH ACUTE
        "\u00c2",  # LATIN CAPITAL LETTER A WITH CIRCUMFLEX
        "\u00c3",  # LATIN CAPITAL LETTER A WITH TILDE
        "\u00c4",  # LATIN CAPITAL LETTER A WITH DIAERESIS
        "\u00c5",  # LATIN CAPITAL LETTER A WITH RING ABOVE
        "\u00c6",  # LATIN CAPITAL LETTER AE
        "\u00c7",  # LATIN CAPITAL LETTER C WITH CEDILLA
        "\u00c8",  # LATIN CAPITAL LETTER E WITH GRAVE
        "\u00c9",  # LATIN CAPITAL LETTER E WITH ACUTE
        "\u00ca",  # LATIN CAPITAL LETTER E WITH CIRCUMFLEX
        "\u00cb",  # LATIN CAPITAL LETTER E WITH DIAERESIS
        "\u00cc",  # LATIN CAPITAL LETTER I WITH GRAVE
        "\u00cd",  # LATIN CAPITAL LETTER I WITH ACUTE
        "\u00ce",  # LATIN CAPITAL LETTER I WITH CIRCUMFLEX
        "\u00cf",  # LATIN CAPITAL LETTER I WITH DIAERESIS
        "\u00d0",  # LATIN CAPITAL LETTER ETH
        "\u00d1",  # LATIN CAPITAL LETTER N WITH TILDE
        "\u00d2",  # LATIN CAPITAL LETTER O WITH GRAVE
        "\u00d3",  # LATIN CAPITAL LETTER O WITH ACUTE
        "\u00d4",  # LATIN CAPITAL LETTER O WITH CIRCUMFLEX
        "\u00d5",  # LATIN CAPITAL LETTER O WITH TILDE
        "\u00d6",  # LATIN CAPITAL LETTER O WITH DIAERESIS
        "\u00d7",  # MULTIPLICATION SIGN
        "\u00d8",  # LATIN CAPITAL LETTER O WITH STROKE
        "\u00d9",  # LATIN CAPITAL LETTER U WITH GRAVE
        "\u00da",  # LATIN CAPITAL LETTER U WITH ACUTE
        "\u00db",  # LATIN CAPITAL LETTER U WITH CIRCUMFLEX
        "\u00dc",  # LATIN CAPITAL LETTER U WITH DIAERESIS
        "\u00dd",  # LATIN CAPITAL LETTER Y WITH ACUTE
        "\u00de",  # LATIN CAPITAL LETTER THORN
        "\u00df",  # LATIN SMALL LETTER SHARP S
        "\u00e0",  # LATIN SMALL LETTER A WITH GRAVE
        "\u00e1",  # LATIN SMALL LETTER A WITH ACUTE
        "\u00e2",  # LATIN SMALL LETTER A WITH CIRCUMFLEX
        "\u00e3",  # LATIN SMALL LETTER A WITH TILDE
        "\u00e4",  # LATIN SMALL LETTER A WITH DIAERESIS
        "\u00e5",  # LATIN SMALL LETTER A WITH RING ABOVE
        "\u00e6",  # LATIN SMALL LETTER AE
        "\u00e7",  # LATIN SMALL LETTER C WITH CEDILLA
        "\u00e8",  # LATIN SMALL LETTER E WITH GRAVE
        "\u00e9",  # LATIN SMALL LETTER E WITH ACUTE
        "\u00ea",  # LATIN SMALL LETTER E WITH CIRCUMFLEX
        "\u00eb",  # LATIN SMALL LETTER E WITH DIAERESIS
        "\u00ec",  # LATIN SMALL LETTER I WITH GRAVE
        "\u00ed",  # LATIN SMALL LETTER I WITH ACUTE
        "\u00ee",  # LATIN SMALL LETTER I WITH CIRCUMFLEX
        "\u00ef",  # LATIN SMALL LETTER I WITH DIAERESIS
        "\u00f0",  # LATIN SMALL LETTER ETH
        "\u00f1",  # LATIN SMALL LETTER N WITH TILDE
        "\u00f2",  # LATIN SMALL LETTER O WITH GRAVE
        "\u00f3",  # LATIN SMALL LETTER O WITH ACUTE
        "\u00f4",  # LATIN SMALL LETTER O WITH CIRCUMFLEX
        "\u00f5",  # LATIN SMALL LETTER O WITH TILDE
        "\u00f6",  # LATIN SMALL LETTER O WITH DIAERESIS
        "\u00f7",  # DIVISION SIGN
        "\u00f8",  # LATIN SMALL LETTER O WITH STROKE
        "\u00f9",  # LATIN SMALL LETTER U WITH GRAVE
        "\u00fa",  # LATIN SMALL LETTER U WITH ACUTE
        "\u00fb",  # LATIN SMALL LETTER U WITH CIRCUMFLEX
        "\u00fc",  # LATIN SMALL LETTER U WITH DIAERESIS
        "\u00fd",  # LATIN SMALL LETTER Y WITH ACUTE
        "\u00fe",  # LATIN SMALL LETTER THORN
        "\u00ff",  # LATIN SMALL LETTER Y WITH DIAERESIS
    )
)

encoding_table = codecs.charmap_build(decoding_table)


class PdfDocCodec(codecs.Codec):
    def encode(self, input: str, errors: str = "strict") -> tuple[bytes, int]:
        return codecs.charmap_encode(input, errors, encoding_table)

    def decode(self, input: bytes, errors: str = "strict") -> tuple[str, int]:
        return codecs.charmap_decode(input, errors, decoding_table)


class IncrementalEncoder(codecs.IncrementalEncoder):
    def encode(self, input: str, final: bool = False) -> bytes:
        return codecs.charmap_encode(input, self.errors, encoding_table)[0]


class IncrementalDecoder(codecs.IncrementalDecoder):
    def decode(self, input: Buffer, final: bool = False) -> str:
        return codecs.charmap_decode(input, self.errors, decoding_table)[0]


class StreamWriter(PdfDocCodec, codecs.StreamWriter):
    pass


class StreamReader(PdfDocCodec, codecs.StreamReader):
    pass


def find_pdfdoc(encoding: str) -> codecs.CodecInfo | None:
    if encoding.lower() not in ("pdfdoc", "pdfdoc_naut"):
        return

    return codecs.CodecInfo(
        name=encoding.lower(),
        encode=PdfDocCodec().encode,
        decode=PdfDocCodec().decode,
        incrementalencoder=IncrementalEncoder,
        incrementaldecoder=IncrementalDecoder,
        streamreader=StreamReader,
        streamwriter=StreamWriter,
    )


codecs.register(find_pdfdoc)
