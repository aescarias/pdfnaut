import pytest

from pdfnaut.common._utils import decimal_to_letter, decimal_to_roman


@pytest.mark.parametrize(
    ("input", "expected"),
    [
        (1, "I"),
        (4, "IV"),
        (9, "IX"),
        (49, "XLIX"),
        (90, "XC"),
        (400, "CD"),
        (900, "CM"),
        (1066, "MLXVI"),
        (1954, "MCMLIV"),
        (3999, "MMMCMXCIX"),
    ],
)
def test_decimal_to_roman(input: int, expected: str) -> None:
    assert decimal_to_roman(input) == expected


@pytest.mark.parametrize(
    ("input", "expected"),
    [
        (1, "A"),
        (2, "B"),
        (25, "Y"),
        (26, "Z"),
        (27, "AA"),
        (28, "AB"),
        (52, "AZ"),
        (53, "BA"),
        (701, "ZY"),
        (702, "ZZ"),
        (703, "AAA"),
        (16_384, "XFD"),
        (475_254, "ZZZZ"),
        (1_000_000, "BDWGN"),
    ],
)
def test_decimal_to_letter(input: int, expected: str) -> None:
    assert decimal_to_letter(input) == expected
