from abc import ABC, abstractmethod
from collections.abc import Generator, Iterator, MutableMapping, MutableSequence
from typing import Any, Generic, Iterable, SupportsIndex, TypeGuard, cast, overload

from typing_extensions import Self, TypeVar

from ...common._utils import batched
from .base import PdfHexString, PdfObject, into_bytes, is_null_like
from .containers import PdfArray, PdfDictionary

_K = TypeVar("_K", bound=PdfObject, default=PdfObject)
_V = TypeVar("_V", bound=PdfObject, default=PdfObject)


class _FlatMapping(Generic[_K, _V], MutableMapping[_K, _V]):
    def __init__(self, tree: "_NNTree[_K, _V]") -> None:
        self._tree = tree

    def __getitem__(self, key: _K) -> _V:
        source = self._tree._get_source_items()
        if source is not None:
            return self._tree._into_output_value(source[key])

        items = self._tree._get_items() or PdfArray()
        for current_key, value in batched(items, 2, strict=True):
            if self._tree._into_output_key(current_key) == key:
                return self._tree._into_output_value(value)

        raise KeyError(key)

    def __setitem__(self, key: _K, value: _V) -> None:
        source = self._tree._get_source_items()
        if source is not None:
            source[key] = value
            self._tree._sync_items_from_source()
            return

        items = self._tree._get_items()
        if items is None:
            self._tree._set_items(items := PdfArray())

        # set key if present
        for index, current_key in enumerate(items[::2]):
            if self._tree._into_output_key(current_key) == key:
                items[2 * index + 1] = self._tree._into_input_value(value)
                return

        # add key otherwise
        for index in range(0, len(items), 2):
            current_key = items[index]
            if self._tree._into_output_key(current_key) > key:
                items[index:index] = [
                    self._tree._into_input_key(key),
                    self._tree._into_input_value(value),
                ]
                break
        else:
            items.extend([self._tree._into_input_key(key), self._tree._into_input_value(value)])

        self._tree._compute_and_set_limits()

    def __delitem__(self, key: _K) -> None:
        source = self._tree._get_source_items()
        if source is not None:
            del source[key]
            self._tree._sync_items_from_source()
            return

        items = self._tree._get_items() or PdfArray()
        for index, current_key in enumerate(items[::2]):
            if self._tree._into_output_key(current_key) == key:
                del items[2 * index : 2 * index + 2]
                return

        raise KeyError(key)

    def __iter__(self) -> Iterator[_K]:
        source = self._tree._get_source_items()
        if source is not None:
            yield from source
            return

        items = self._tree._get_items() or PdfArray()
        for key, _ in batched(items, 2, strict=True):
            yield self._tree._into_output_key(key)

    def __len__(self) -> int:
        source = self._tree._get_source_items()
        if source is not None:
            return len(source)

        items = self._tree._get_items() or PdfArray()
        return len(items) // 2

    def __repr__(self) -> str:
        return repr(self._tree._get_items_map())


_NT = TypeVar("_NT", bound="_NNTree")


class _NNTreeKidList(MutableSequence[_NT], Generic[_NT]):
    def __init__(self, arr: PdfArray, tree_type: type[_NT], *, parent: _NT | None = None) -> None:
        self._arr = arr
        self._parent = parent
        self._tree_type = tree_type

    def _get_source_kids(self) -> MutableSequence[_NT] | None:
        if self._parent is not None:
            return self._parent._get_source_kids()

    def _sync_from_source(self) -> None:
        source = self._get_source_kids()
        if source is None:
            return

        assert self._parent is not None
        self._parent._sync_kids_from_source()
        self._arr = cast(PdfArray[PdfObject], self._parent._raw["Kids"])

    def _decode_type(self, obj: PdfObject) -> _NT:
        assert isinstance(obj, PdfDictionary)
        return self._tree_type.from_dict(obj, parent=self._parent)

    def _encode_type(self, obj: _NT) -> PdfObject:
        return obj._raw

    @overload
    def __getitem__(self, index: SupportsIndex) -> _NT: ...

    @overload
    def __getitem__(self, index: slice) -> MutableSequence[_NT]: ...

    def __getitem__(self, index: SupportsIndex | slice) -> _NT | MutableSequence[_NT]:
        self._sync_from_source()

        if isinstance(index, slice):
            return [self._decode_type(it) for it in self._arr[index]]

        return self._decode_type(self._arr[index])

    def __len__(self) -> int:
        self._sync_from_source()
        return len(self._arr)

    def insert(self, index: int, value: _NT) -> None:
        self._sync_from_source()
        source = self._get_source_kids()

        if source is not None:
            source.insert(index, value)
            self._sync_from_source()
            return

        self._arr.insert(index, self._encode_type(value))

    @overload
    def __setitem__(self, index: SupportsIndex, value: _NT) -> None: ...

    @overload
    def __setitem__(self, index: slice, value: Iterable[_NT]) -> None: ...

    def __setitem__(self, index: SupportsIndex | slice, value: _NT | Iterable[_NT]) -> None:
        self._sync_from_source()

        source = self._get_source_kids()
        if source is not None:
            source[index] = value
            self._sync_from_source()
            return

        if isinstance(index, slice):
            assert isinstance(value, Iterable)
            self._arr[index] = [self._encode_type(it) for it in value]
        else:
            value = cast(_NT, value)
            self._arr[index] = self._encode_type(value)

    def __delitem__(self, index: SupportsIndex | slice) -> None:
        self._sync_from_source()

        source = self._get_source_kids()
        if source is not None:
            del source[index]
            self._sync_from_source()
            return

        del self._arr[index]


class _NNTree(ABC, Generic[_K, _V], MutableMapping[_K, _V]):
    @classmethod
    def from_dict(cls, data: PdfDictionary, *, parent: "_NNTree[_K, _V] | None" = None) -> Self:
        tree = cls(parent=parent)
        tree._raw = data
        return tree

    def __init__(
        self,
        items: dict[_K, _V] | None = None,
        kids: MutableSequence[Self] | None = None,
        limits: tuple[_K, _V] | None = None,
        *,
        parent: "_NNTree[_K, _V] | None" = None,
    ) -> None:
        """
        Initializes a tree object.

        All arguments are optional. ``items`` and ``kids`` are mutually exclusive
        and shall not be specified both at once. If ``limits`` is not provided,
        it is computed based on the provided items or children, where applicable.

        Arguments:
            items: The mapping of items contained in this node.
            kids: The immediate children nodes of this node.
            limits: The least and greatest keys of this node.
        """
        self.parent = parent

        self._raw = PdfDictionary()
        self._source_items: MutableMapping[_K, _V] | None = None
        self._source_kids: MutableSequence[Self] | None = None

        if items is not None:
            self._set_items_map(items)

        self.kids = kids

        if limits is not None:
            self._raw["Limits"] = PdfArray([self._into_output_key(lim) for lim in limits])
        else:
            self._compute_and_set_limits()

    def _get_source_items(self) -> MutableMapping[_K, _V] | None:
        return self._source_items

    def _get_source_kids(self) -> MutableSequence[Self] | None:
        return self._source_kids

    def _sync_items_from_source(self) -> None:
        source = self._source_items
        if source is None:
            return

        items = PdfArray()
        for key, value in sorted(source.items(), key=lambda item: item[0]):
            items.extend([self._into_input_key(key), self._into_input_value(value)])

        self._set_items(items)

    def _sync_kids_from_source(self) -> None:
        source = self._source_kids
        if source is None:
            return

        kids = PdfArray([kid._raw for kid in sorted(source, key=lambda k: k.limits or ())])
        for kid in source:
            kid.parent = self

        self._raw["Kids"] = kids

    @abstractmethod
    def _get_items(self) -> PdfArray[PdfObject] | None:
        raise NotImplementedError

    @abstractmethod
    def _set_items(self, items: PdfArray[PdfObject] | None) -> None:
        raise NotImplementedError

    @abstractmethod
    def _into_output_key(self, key: PdfObject) -> _K:
        return cast(_K, key)

    @abstractmethod
    def _into_output_value(self, value: PdfObject) -> _V:
        return cast(_V, value)

    @abstractmethod
    def _into_input_value(self, value: _V) -> PdfObject:
        return cast(PdfObject, value)

    @abstractmethod
    def _into_input_key(self, key: _K) -> PdfObject:
        return cast(PdfObject, key)

    @abstractmethod
    def _is_valid_key(self, key: object) -> bool:
        raise NotImplementedError

    @property
    def kids(self) -> "_NNTreeKidList[Self] | None":
        """The immediate children of this node."""
        if self._get_source_kids() is not None:
            self._sync_kids_from_source()

        kids = self._raw.get("Kids")
        if is_null_like(kids):
            return

        kids = cast(PdfArray, kids)
        return _NNTreeKidList[Self](kids, type(self), parent=self)

    @kids.setter
    def kids(self, value: MutableSequence[Self] | None) -> None:
        if value is None:
            self._source_kids = None
            self._raw.pop("Kids", None)
            return

        if self._get_items() is not None:
            raise ValueError("cannot set kids because items are already present")

        self._source_kids = value
        self._sync_kids_from_source()

    @property
    def limits(self) -> tuple[_K, _K] | None:
        """Two items representing the least and greatest keys included in the
        key-value pairs of the tree and any of its descendants."""

        limits = self._raw.get("Limits")
        if is_null_like(limits):
            return

        limits = cast(PdfArray, limits)
        return self._into_output_key(limits[0]), self._into_output_key(limits[1])

    def walk(self, compare_key: _K | None = None) -> Generator[tuple[_K, _V]]:
        """Walks the tree and yields the key-value pairs as found.

        When ``compare_key`` is specified, trees will be skipped if the comparison
        key does not fall within the range of the tree's :attr:`.limits` value.

        Raises :exc:`ValueError` if the tree contains both nodes and key-value pairs.
        """

        if self._source_items is not None:
            for key, value in self._source_items.items():
                yield (self._into_output_key(key), self._into_output_value(value))
            return

        if self.kids is not None and self._get_items() is not None:
            raise ValueError("nodes and items in tree are mutually exclusive")

        items = iter(self._get_items() or [])
        while not is_null_like(key := next(items, None)):
            assert key is not None

            value = next(items, None)
            if value is None:
                break

            yield (self._into_output_key(key), self._into_output_value(value))

        for tree in self.kids or []:
            if compare_key is not None and tree.limits is not None:
                first, last = tree.limits

                compare_key = cast(Any, compare_key)
                first = cast(Any, first)
                last = cast(Any, last)

                if compare_key < first or last < compare_key:
                    continue

            yield from tree.walk(compare_key)

    def find_leaf(self, target_key: _K) -> Self:
        """Finds the leaf node that contains ``target_key`` or otherwise the
        closest leaf node that can contain ``target_key``."""
        if not self.kids:
            return self

        closest = None
        for tree in self.kids:
            if tree.limits is None and (limits := tree._compute_limits()):
                tree._raw["Limits"] = limits

            assert tree.limits is not None
            first, last = tree.limits

            first = cast(Any, first)
            last = cast(Any, last)

            if first <= target_key <= last or target_key < first:
                return tree.find_leaf(target_key)

            closest = tree

        assert closest is not None
        return closest.find_leaf(target_key)

    def _get_items_map(self) -> dict[_K, _V] | None:
        if self._source_items is not None:
            self._sync_items_from_source()
            return dict(self._source_items)

        items = self._get_items()
        if items is None:
            return

        items_map: dict[_K, _V] = {}
        for key, value in batched(items, 2, strict=True):
            key = self._into_output_key(key)
            items_map[key] = self._into_output_value(value)

        return items_map

    def _set_items_map(self, mapping: dict[_K, _V] | None) -> None:
        self._source_items = mapping
        if mapping is None:
            self._set_items(None)
            return

        self._sync_items_from_source()

    def _compute_limits(self) -> PdfArray[PdfObject] | None:
        if self.parent is None:
            return

        first_item = next(self.walk(), None)
        if first_item is None:
            return

        lower_limit = upper_limit = first_item[0]

        for key, _ in self.walk():
            key = cast(Any, key)
            if key < lower_limit:
                lower_limit = key

            if key > upper_limit:
                upper_limit = key

        return PdfArray([self._into_input_key(lower_limit), self._into_input_key(upper_limit)])

    def _compute_and_set_limits(self) -> None:
        limits = self._compute_limits()

        if not limits:
            self._raw.pop("Limits", None)
        else:
            self._raw["Limits"] = limits

    def _update_node_limits(self, node: "_NNTree[_K, _V]") -> None:
        while node.parent is not None:
            node._compute_and_set_limits()
            node = node.parent

    def __iter__(self) -> Iterator[_K]:
        for key, _ in self.walk():
            yield key

    def __len__(self) -> int:
        return sum(1 for _ in self)

    def __getitem__(self, key: _K) -> _V:
        for ret_key, value in self.walk(key):
            if ret_key == key:
                return value

        raise KeyError(key) from None

    def __setitem__(self, key: _K, value: _V) -> None:
        leaf = self.find_leaf(key)

        items = _FlatMapping(leaf)
        items[key] = value

        self._update_node_limits(leaf)

    def __delitem__(self, key: _K) -> None:
        leaf = self.find_leaf(key)

        items = _FlatMapping(leaf)
        del items[key]

        self._update_node_limits(leaf)

    def __contains__(self, key: object) -> bool:
        if not self._is_valid_key(key):
            return False

        if not isinstance(key, PdfObject):
            return False

        key = self._into_output_key(key)
        for ret_key, _ in self.walk(key):
            if ret_key == key:
                return True

        return False


class NameTree(Generic[_V], _NNTree[bytes, _V]):
    """A tree object associating string keys with values. See ISO 32000-2:2020 §
    7.9.6 "Name trees"."""

    def _get_items(self) -> PdfArray[PdfObject] | None:
        self._sync_items_from_source()

        names = self._raw.get("Names")
        if is_null_like(names):
            return

        return cast(PdfArray, names)

    def _set_items(self, items: PdfArray[PdfObject] | None) -> None:
        if items is None:
            self._raw.pop("Names", None)
            return

        if not is_null_like(self._raw.get("Kids")):
            raise ValueError("cannot set names because kids is already present")

        self._raw["Names"] = items
        self._compute_and_set_limits()

    def _into_input_key(self, key: bytes) -> PdfObject:
        return cast(PdfObject, key)

    def _into_input_value(self, value: _V) -> PdfObject:
        return cast(PdfObject, value)

    def _into_output_key(self, key: PdfObject) -> bytes:
        assert self._is_valid_key(key)
        return into_bytes(key)

    def _into_output_value(self, value: PdfObject) -> _V:
        return cast(_V, value)

    def _is_valid_key(self, key: object) -> TypeGuard[PdfHexString | bytes]:
        return isinstance(key, PdfHexString | bytes)

    @property
    def names(self) -> MutableMapping[bytes, _V] | None:
        """The key-value pairs of this tree node."""
        if self._get_items() is not None:
            return _FlatMapping(self)

    @names.setter
    def names(self, value: dict[bytes, _V] | None) -> None:
        self._set_items_map(value)


class NumberTree(Generic[_V], _NNTree[int, _V]):
    """A tree object associating integer keys with values. See ISO 32000-2:2020 §
    7.9.7 "Number trees"."""

    def _get_items(self) -> PdfArray[PdfObject] | None:
        self._sync_items_from_source()

        nums = self._raw.get("Nums")
        if is_null_like(nums):
            return

        return cast(PdfArray, nums)

    def _set_items(self, items: PdfArray[PdfObject] | None) -> None:
        if items is None:
            self._raw.pop("Nums", None)
            return

        if not is_null_like(self._raw.get("Kids")):
            raise ValueError("cannot set nums because kids is already present")

        self._raw["Nums"] = items
        self._compute_and_set_limits()

    def _into_input_key(self, key: int) -> PdfObject:
        return cast(PdfObject, key)

    def _into_input_value(self, value: _V) -> PdfObject:
        return cast(PdfObject, value)

    def _into_output_key(self, key: PdfObject) -> int:
        assert self._is_valid_key(key)
        return key

    def _into_output_value(self, value: PdfObject) -> _V:
        return cast(_V, value)

    def _is_valid_key(self, key: object) -> TypeGuard[int]:
        return isinstance(key, int)

    @property
    def nums(self) -> MutableMapping[int, _V] | None:
        """The key-value pairs of this tree node."""
        if self._get_items() is not None:
            return _FlatMapping(self)

    @nums.setter
    def nums(self, value: dict[int, _V] | None) -> None:
        self._set_items_map(value)
