from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from ..common._utils import ensure
from ..cos.objects.base import PdfHexString, PdfName, PdfNull, PdfObject, PdfReference
from ..cos.objects.containers import PdfArray, PdfDictionary
from ..cos.objects.stream import PdfStream
from ..cos.parser import FreeObject

if TYPE_CHECKING:
    from ..cos.parser import PdfParser


class _PlaceholderType:
    def __repr__(self) -> str:
        return "PLACEHOLDER"


LOGGER = logging.getLogger(__name__)
PLACEHOLDER = _PlaceholderType()


def _is_page_or_page_tree(obj: PdfObject) -> bool:
    """Reports whether an object ``obj`` is a page object or a page tree node."""

    if not isinstance(obj, PdfDictionary) or "Type" not in obj:
        return False

    if not isinstance(tp := obj["Type"], PdfName) or tp.value not in [b"Page", b"Pages"]:
        return False

    return True


def copy_object(obj: PdfObject) -> PdfObject:
    """Performs a deep copy of a PDF object ``obj``. Returns the copied object.

    Deep copying works by creating a new object for the container then adding a copy
    of each element it contains into the new object.

    Numbers, literal strings, booleans, and the null object are not copied and are
    returned as is. Unlike :meth:`.clone_in_document`, when a reference is found,
    it is simply copied into the object without modifying the referred object.

    """

    if isinstance(obj, PdfDictionary):
        kv = PdfDictionary()
        for key, value in obj.data.items():
            kv.data[key] = copy_object(value)
        return kv
    elif isinstance(obj, PdfStream):
        return PdfStream(
            ensure(copy_object(obj.details), PdfDictionary),
            obj.raw,
            ensure(copy_object(obj._crypt_params), PdfDictionary),
        )
    elif isinstance(obj, PdfArray):
        arr = PdfArray()
        for value in obj.data:
            arr.data.append(copy_object(value))
        return arr
    elif isinstance(obj, PdfName):
        return PdfName(obj.value)
    elif isinstance(obj, PdfHexString):
        return PdfHexString(obj.raw)
    elif isinstance(obj, PdfReference):
        return PdfReference(obj.object_number, obj.generation)

    return obj


def clone_into_document(
    dest: PdfParser, root: PdfObject, *, ignore_keys: list[str] | None = None
) -> PdfObject:
    """Clones an object ``root`` and its contents into document ``dest``. Returns
    the cloned object.

    If the root object is a dictionary and the ``ignore_keys`` argument is provided,
    those keys will be ignored when cloning the root object.

    Cloning of an object is performed by deep-copying each element contained in it.
    When a reference is found, it is determined whether it is suitable for cloning
    into the document.

    A reference is determined suitable for cloning if it does not refer back to the
    ``root`` object. If it is unsuitable, a placeholder is added if the reference is
    ``root`` itself. If the reference may point back to the object (such as the
    reference being for a page tree), it is nulled.

    If the reference is suitable, its contents are added into the document and the new
    reference replaces the old reference in the object.
    """

    if ignore_keys is None:
        ignore_keys = []

    cloned_map = {}
    references = set()

    def inner(obj: PdfObject) -> PdfObject | _PlaceholderType:
        if obj in cloned_map:
            # object is already cloned
            return cloned_map[obj]

        if isinstance(obj, PdfReference):
            referred = obj.get()

            if referred is root:
                # object refers to our origin object. in which case, simply set
                # a placeholder for later processing
                return PLACEHOLDER

            if _is_page_or_page_tree(referred):
                # avoid going to pages or anything that might lead us back to the page tree
                LOGGER.warning("object %s cannot be reliably copied and has been set to null.", obj)
                return PdfNull()

            cloned_direct = inner(referred)
            assert not isinstance(cloned_direct, _PlaceholderType)

            cloned_map[obj] = dest.objects.add(cloned_direct)
            references.add(cloned_map[obj])
            return cloned_map[obj]
        elif isinstance(obj, PdfDictionary):
            kv = PdfDictionary()
            cloned_map[obj] = kv
            for key, value in obj.data.items():
                if obj is root and key in ignore_keys:
                    continue

                cloned_direct = inner(value)
                assert not isinstance(cloned_direct, _PlaceholderType)

                kv.data[key] = cloned_direct

            return kv
        elif isinstance(obj, PdfStream):
            stm = PdfStream(
                ensure(inner(obj.details), PdfDictionary),
                obj.raw,
                ensure(inner(obj._crypt_params), PdfDictionary),
            )
            cloned_map[obj] = stm
            return stm
        elif isinstance(obj, PdfArray):
            arr = PdfArray()
            cloned_map[obj] = arr

            for value in obj.data:
                cloned_direct = inner(value)
                assert not isinstance(cloned_direct, _PlaceholderType)

                arr.data.append(cloned_direct)

            return arr
        elif isinstance(obj, PdfName):
            return PdfName(obj.value)
        elif isinstance(obj, PdfHexString):
            return PdfHexString(obj.raw)

        return obj

    cloned = inner(root)
    assert not isinstance(cloned, _PlaceholderType)

    def replace_placeholders(obj: PdfObject | _PlaceholderType) -> PdfObject:
        if isinstance(obj, _PlaceholderType):
            return dest.objects.add(cloned)
        elif isinstance(obj, PdfArray):
            return PdfArray(replace_placeholders(it) for it in obj.data)
        elif isinstance(obj, PdfDictionary):
            return PdfDictionary({key: replace_placeholders(val) for key, val in obj.data.items()})
        elif isinstance(obj, PdfStream):
            obj.details = ensure(replace_placeholders(obj.details), PdfDictionary)
            obj._crypt_params = ensure(replace_placeholders(obj._crypt_params), PdfDictionary)
            return obj

        return obj

    final = replace_placeholders(cloned)
    for ref in references:
        direct = dest.objects[ref.object_number]
        assert not isinstance(direct, FreeObject)
        dest.objects[ref.object_number] = replace_placeholders(direct)

    return final
