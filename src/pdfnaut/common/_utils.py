from __future__ import annotations

from collections.abc import Generator, Iterable
from itertools import islice
from typing import TypeVar

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
