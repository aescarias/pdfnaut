from abc import ABC, abstractmethod
from collections.abc import Generator, Iterator, Mapping
from typing import Any, Generic, TypeGuard, TypeVar, cast

from typing_extensions import Self

from ..helpers import into_bytes, is_null_like
from .base import PdfHexString, PdfObject
from .containers import PdfArray, PdfDictionary

_K = TypeVar("_K", bound=PdfObject)
_V = TypeVar("_V", bound=PdfObject)


class _NNTree(ABC, Generic[_K, _V], Mapping[_K, _V]):
    def __init__(self, data: PdfDictionary) -> None:
        self._raw = data

    @abstractmethod
    def _get_items(self) -> list[PdfObject] | None:
        raise NotImplementedError

    @abstractmethod
    def _into_output_key(self, key: PdfObject) -> _K:
        return cast(_K, key)

    @abstractmethod
    def _is_valid_key(self, key: object) -> bool:
        raise NotImplementedError

    @property
    def kids(self) -> list[Self] | None:
        """The immediate children of this node."""
        kids = self._raw.get("Kids")
        if is_null_like(kids):
            return

        return [type(self)(kid) for kid in cast(PdfArray[PdfDictionary], kids)]

    @property
    def limits(self) -> tuple[_K, _K] | None:
        """Two items representing the least and greatest keys included in the
        key-value pairs of the tree and any of its descendants."""

        limits = self._raw.get("Limits")
        if is_null_like(limits):
            return

        limits = cast(PdfArray, limits)
        return self._into_output_key(limits[0]), self._into_output_key(limits[1])

    def walk(self, compare_key: _K | None = None) -> Generator[tuple[_K, PdfObject]]:
        """Walks the tree and yields the key-value pairs as found.

        When ``compare_key`` is specified, trees will be skipped if the comparison
        key does not fall within the range of the tree's :attr:`.limits` value.

        Raises :exc:`ValueError` if the tree contains both nodes and key-value pairs.
        """

        if self.kids is not None and self._get_items() is not None:
            raise ValueError("nodes and items in tree are mutually exclusive")

        items = iter(self._get_items() or [])
        while not is_null_like(key := next(items, None)):
            assert key is not None

            value = next(items, None)
            if value is None:
                break

            yield (self._into_output_key(key), value)

        for tree in self.kids or []:
            if compare_key is not None and tree.limits is not None:
                first, last = tree.limits

                compare_key = cast(Any, compare_key)
                first = cast(Any, first)
                last = cast(Any, last)

                if compare_key < first or last < compare_key:
                    continue

            yield from tree.walk(compare_key)

    def __iter__(self) -> Iterator[_K]:
        for key, _ in self.walk():
            yield key

    def __len__(self) -> int:
        return sum(1 for _ in self)

    def __getitem__(self, key: _K) -> _V:
        for ret_key, value in self.walk(key):
            if ret_key == key:
                return cast(_V, value)

        raise KeyError(key) from None

    def __contains__(self, key: object) -> bool:
        if not self._is_valid_key(key):
            return False

        key = cast(_K, key)
        for ret_key, _ in self.walk(key):
            if ret_key == key:
                return True

        return False


class NameTree(Generic[_V], _NNTree[bytes, _V]):
    """A tree object associating string keys with values. See ISO 32000-2:2020 §
    7.9.6 "Name trees"."""

    def _get_items(self) -> list[PdfObject] | None:
        names = self._raw.get("Names")
        if is_null_like(names):
            return

        return list(cast(PdfArray, names))

    def _into_output_key(self, key: PdfObject) -> bytes:
        assert self._is_valid_key(key)
        return into_bytes(key)

    def _is_valid_key(self, key: object) -> TypeGuard[PdfHexString | bytes]:
        return isinstance(key, PdfHexString | bytes)

    @property
    def names(self) -> list[PdfObject] | None:
        """The key-value pairs of this node."""
        return self._get_items()


class NumberTree(Generic[_V], _NNTree[int, _V]):
    """A tree object associating integer keys with values. See ISO 32000-2:2020 §
    7.9.7 "Number trees"."""

    def _get_items(self) -> list[PdfObject] | None:
        nums = self._raw.get("Nums")
        if is_null_like(nums):
            return

        return list(cast(PdfArray, nums))

    def _into_output_key(self, key: PdfObject) -> int:
        assert self._is_valid_key(key)
        return key

    def _is_valid_key(self, key: object) -> TypeGuard[int]:
        return isinstance(key, int)

    @property
    def nums(self) -> list[PdfObject] | None:
        """The key-value pairs of this node."""
        return self._get_items()
