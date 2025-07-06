from __future__ import annotations

from collections import UserDict, UserList
from typing import SupportsIndex, cast, overload

from typing_extensions import TypeVar

from ...exceptions import PdfResolutionError
from .base import PdfObject, PdfReference

DictKey = TypeVar("DictKey", default=str, infer_variance=True)
DictVal = TypeVar("DictVal", default=PdfObject, infer_variance=True)


class PdfDictionary(UserDict[DictKey, DictVal]):
    """An associative table containing pairs of objects or entries where each entry is
    composed of a key which is a name object and a value which is any PDF object
    (see § 7.3.7, "Dictionary objects").

    :class:`PdfDictionary` is effectively a Python dictionary. Its keys are strings and
    its values are any PDF object. The main difference from a typical dictionary is that
    PdfDictionary automatically resolves references on key access.

    The underlying data in unresolved form is stored in :attr:`.PdfDictionary.data`.
    """

    def __getitem__(self, key: DictKey) -> DictVal:
        item = self.data[key]
        if isinstance(item, PdfReference):
            try:
                return cast(DictVal, item.get())
            except PdfResolutionError:
                pass

        return cast(DictVal, item)

    def __setitem__(self, key: DictKey, value: DictVal | PdfReference[DictVal]) -> None:
        self.data[key] = cast(DictVal, value)

    def __hash__(self) -> int:
        return hash((self.__class__, tuple(hash(v) for v in self.data.items())))


ArrVal = TypeVar("ArrVal", default=PdfObject)


class PdfArray(UserList[ArrVal]):
    """A heterogeneous collection of sequentially arranged items (see § 7.3.6, "Array objects").

    :class:`PdfArray` is effectively a Python list. The main difference from a typical list
    is that PdfArray automatically resolves references when indexing.

    The underlying data in unresolved form is stored in :attr:`.PdfArray.data`.
    """

    @overload
    def __getitem__(self, i: SupportsIndex) -> ArrVal: ...

    @overload
    def __getitem__(self, i: slice) -> PdfArray[ArrVal]: ...

    def __getitem__(self, i: SupportsIndex | slice) -> ArrVal | PdfArray[ArrVal]:
        item = self.data[i]
        if isinstance(i, slice):
            return PdfArray(cast(list[ArrVal], item))

        if isinstance(item, PdfReference):
            try:
                return cast(ArrVal, item.get())
            except PdfResolutionError:
                pass

        return cast(ArrVal, item)

    def __hash__(self) -> int:  # type: ignore -- our arrays are hashable!
        return hash((self.__class__, tuple(hash(v) for v in self.data)))
