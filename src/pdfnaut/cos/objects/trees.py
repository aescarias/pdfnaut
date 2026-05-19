from collections.abc import Generator, Iterator, Mapping
from typing import cast

from ..helpers import into_bytes, is_null_like
from .base import PdfHexString, PdfObject
from .containers import PdfArray, PdfDictionary


class NameTree(Mapping[bytes, PdfObject]):
    """A tree object associating string keys with values. See ISO 32000-2:2020 §
    7.9.6 "Name trees"."""

    def __init__(self, data: PdfDictionary) -> None:
        self._data = data

    @property
    def kids(self) -> list[PdfObject] | None:
        kids = self._data.get("Kids")
        if is_null_like(kids):
            return

        return list(cast(PdfArray, kids))

    @property
    def names(self) -> list[PdfObject] | None:
        names = self._data.get("Names")
        if is_null_like(names):
            return

        return list(cast(PdfArray, names))

    @property
    def limits(self) -> tuple[bytes, bytes] | None:
        limits = self._data.get("Limits")
        if is_null_like(limits):
            return

        limits = cast(PdfArray[PdfHexString | bytes], limits)
        return into_bytes(limits[0]), into_bytes(limits[1])

    def walk(self, compare_key: bytes | None = None) -> Generator[tuple[bytes, PdfObject]]:
        if self.kids is not None and self.names is not None:
            raise ValueError("kids and names in name tree are mutually exclusive")

        names = iter(self.names or [])
        while not is_null_like(key := next(names, None)):
            assert key is not None

            value = next(names, None)
            if value is None:
                break

            key = into_bytes(cast(PdfHexString | bytes, key))
            yield (key, value)

        for kid in self.kids or []:
            tree = NameTree(cast(PdfDictionary, kid))

            if compare_key is not None and tree.limits is not None:
                first, last = tree.limits
                if compare_key < first or last < compare_key:
                    continue

            yield from tree.walk()

    def __iter__(self) -> Iterator[bytes]:
        for key, _ in self.walk():
            yield key

    def __len__(self) -> int:
        return sum(1 for _ in self)

    def __getitem__(self, key: bytes) -> PdfObject:
        for ret_key, value in self.walk(key):
            if ret_key == key:
                return value

        raise KeyError(key) from None

    def __contains__(self, key: object) -> bool:
        if not isinstance(key, (PdfHexString, bytes)):
            return False

        key = into_bytes(key)
        for ret_key, _ in self.walk(key):
            if ret_key == key:
                return True

        return False


class NumberTree(Mapping[int, PdfObject]):
    """A tree object associating integer keys with values. See ISO 32000-2:2020 §
    7.9.7 "Number trees"."""

    def __init__(self, data: PdfDictionary) -> None:
        self._data = data

    @property
    def kids(self) -> list[PdfObject] | None:
        kids = self._data.get("Kids")
        if is_null_like(kids):
            return

        return list(cast(PdfArray, kids))

    @property
    def nums(self) -> list[PdfObject] | None:
        nums = self._data.get("Nums")
        if is_null_like(nums):
            return

        return list(cast(PdfArray, nums))

    @property
    def limits(self) -> tuple[int, int] | None:
        limits = self._data.get("Limits")
        if is_null_like(limits):
            return

        limits = cast(PdfArray[int], limits)
        return limits[0], limits[1]

    def walk(self, compare_key: int | None = None) -> Generator[tuple[int, PdfObject]]:
        if self.kids is not None and self.nums is not None:
            raise ValueError("kids and nums in number tree are mutually exclusive")

        nums = iter(self.nums or [])
        while not is_null_like(key := next(nums, None)):
            assert key is not None

            value = next(nums, None)
            if value is None:
                break

            key = cast(int, key)
            yield (key, value)

        for kid in self.kids or []:
            tree = NumberTree(cast(PdfDictionary, kid))

            if compare_key is not None and tree.limits is not None:
                first, last = tree.limits
                if compare_key < first or last < compare_key:
                    continue

            yield from tree.walk()

    def __iter__(self) -> Iterator[int]:
        for key, _ in self.walk():
            yield key

    def __len__(self) -> int:
        return sum(1 for _ in self)

    def __getitem__(self, key: int) -> PdfObject:
        for ret_key, value in self.walk(key):
            if ret_key == key:
                return value

        raise KeyError(key) from None

    def __contains__(self, key: object) -> bool:
        if not isinstance(key, int):
            return False

        for ret_key, _ in self.walk(key):
            if ret_key == key:
                return True

        return False
