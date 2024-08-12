from typing import cast, overload, SupportsIndex
from typing_extensions import TypeVar

from .base import PdfReference, PdfObject
from ...exceptions import PdfResolutionError

DictKey = TypeVar("DictKey", default=str)
DictVal = TypeVar("DictVal", default=PdfObject)
DictDef = TypeVar("DictDef", default=None)


class PdfDictionary(dict[DictKey, DictVal]):
    """An associative table containing pairs of objects (entries) where each entry is
    composed of a key (a name object) and a value (any PDF object)
    (``§ 7.3.7 Dictionary objects``).

    :class:`PdfDictionary` is effectively a Python dictionary. Its keys are strings and
    its values are any PDF object. The main difference from a typical dictionary is that
    PdfDictionary automatically resolves references when indexing.

    To get the raw value actually stored in the dictionary for a key, use
    :meth:`.PdfDictionary.get_raw` or :meth:`.PdfDictionary.raw_at`.
    """

    def __getitem__(self, key: DictKey) -> DictVal:
        item = super().__getitem__(key)
        if isinstance(item, PdfReference):
            try:
                return cast(DictVal, item.get())
            except PdfResolutionError:
                pass
            
        return cast(DictVal, item)

    def __setitem__(self, key: DictKey, value: DictVal | PdfReference[DictVal]) -> None:
        return super().__setitem__(key, cast(DictVal, value))
    
    def get(self, key: DictKey, default: DictDef = None) -> DictVal | DictDef:  # pyright: ignore[reportIncompatibleMethodOverride]
        try:
            return self[key]
        except KeyError:
            return default

    def get_raw(
        self, key: DictKey, default: DictDef = None
    ) -> PdfReference[DictVal] | DictVal | DictDef:
        """Gets the raw unresolved value for ``key`` returning ``default`` if such key is not
        present.
        
        For most use cases, the subscript syntax (``dictionary[key]``) should be preferred 
        instead. This method is provided for completeness."""
        return super().get(key, default)
    
    def raw_at(self, key: DictKey) -> PdfReference[DictVal] | DictVal:
        """Gets the value for ``key`` raising a KeyError if such key is not found."""
        return super().__getitem__(key)


ArrVal = TypeVar("ArrVal", default=PdfObject)


class PdfArray(list[ArrVal]):
    """A heterogeneous collection of sequentially arranged items (``§ 7.3.6 Array objects``).

    :class:`PdfArray` is effectively a Python list. The main difference from a typical list
    is that PdfArray automatically resolves references when indexing.

    To get the raw object actually stored in the array for any index, use 
    :meth:`.PdfArray.raw_at`
    """

    @overload
    def __getitem__(self, index: SupportsIndex) -> ArrVal: ...

    @overload
    def __getitem__(self, index: slice) -> list[ArrVal]: ...

    def __getitem__(self, index: SupportsIndex | slice) -> ArrVal | list[ArrVal]:
        item = super().__getitem__(index)
        if isinstance(index, slice):
            return PdfArray(cast(list[ArrVal], item))  

        if isinstance(item, PdfReference):
            try:
                return cast(ArrVal, item.get())
            except PdfResolutionError:
                pass

        return cast(ArrVal, item)

    def raw_at(self, index: int) -> PdfReference[ArrVal] | ArrVal:
        """Gets the raw unresolved item at ``index`` raising an IndexError if such index
        is not present.
        
        For most use cases, the subscript syntax (``array[idx]``) should be preferred instead. 
        This method is provided for completeness."""
        return super().__getitem__(index)
