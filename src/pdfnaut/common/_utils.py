from __future__ import annotations

from collections.abc import Generator, Iterable
from itertools import islice
from typing import TypeVar

LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
ROMAN_NUMERAL_PLACES = {
    1000: "M",
    900: "CM",
    500: "D",
    400: "CD",
    100: "C",
    90: "XC",
    50: "L",
    40: "XL",
    10: "X",
    9: "IX",
    5: "V",
    4: "IV",
    1: "I",
}

T = TypeVar("T")


# itertools recipe
def batched(iterable: Iterable[T], n: int, *, strict=False) -> Generator[tuple[T, ...]]:
    """Consumes ``iterable`` and yields batches of `n` elements (where `n` is an
    integer greater than 1) until the iterator is fully consumed.

    If ``strict`` is True, each batch must include exactly `n` elements, raising a
    :class:`ValueError` otherwise.

    This function is practically equivalent to :meth:`itertools.batched`.

    Example:
        batched('ABCDEFG', 3) -> ABC DEF G
    """
    if n < 1:
        raise ValueError("n must be at least one.")

    iterator = iter(iterable)
    while batch := tuple(islice(iterator, n)):
        if strict and len(batch) != n:
            raise ValueError("batched(): incomplete batch.")

        yield batch


def get_closest(values: Iterable[int], target: int) -> int:
    """Returns the integer in ``values`` closest to ``target``."""
    return min(values, key=lambda offset: abs(offset - target))


def decimal_to_roman(number: int) -> str:
    """Converts ``number`` to its representation in roman numerals, where ``number``
    is an integer greater than zero and lower than 4000."""

    if number <= 0 or number > 3_999:
        raise ValueError("number must be in range [1, 3999]")

    result: list[str] = []

    for place in ROMAN_NUMERAL_PLACES:
        n_places, _ = divmod(number, place)
        result.append(ROMAN_NUMERAL_PLACES[place] * n_places)

        number -= place * n_places
        if number <= 0:
            break

    return "".join(result)


def decimal_to_letter(number: int) -> str:
    """Converts ``number`` to bijective base-26, where ``number`` is an integer
    greater than zero."""

    if number <= 0:
        raise ValueError("number must be greater than zero")

    result: list[str] = []
    while number > 0:
        number, index = divmod(number - 1, len(LETTERS))
        result.insert(0, LETTERS[index])

    return "".join(result)
