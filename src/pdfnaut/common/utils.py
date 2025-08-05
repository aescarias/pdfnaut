from __future__ import annotations

import hashlib
import logging
from collections.abc import Iterable
from datetime import time
from typing import TYPE_CHECKING, TypeVar

from ..cos.objects.base import PdfHexString, PdfName, PdfNull, PdfObject, PdfReference
from ..cos.objects.containers import PdfArray, PdfDictionary
from ..cos.objects.stream import PdfStream

if TYPE_CHECKING:
    from pdfnaut.cos.parser import PdfParser


LOGGER = logging.getLogger(__name__)
Placeholder = type("Placeholder", (), {})


def get_value_from_bytes(contents: PdfHexString | bytes) -> bytes:
    """Returns the decoded value of ``contents`` if it is an instance of
    :class:`.PdfHexString`, otherwise returns ``contents``."""
    return contents.value if isinstance(contents, PdfHexString) else contents


R = TypeVar("R")


def ensure_object(obj: PdfReference[R] | R) -> R:
    """Resolves ``obj`` to a direct object if ``obj`` is an instance of
    :class:`.PdfReference`. Otherwise, returns ``obj`` as is."""
    if isinstance(obj, PdfReference):
        return obj.get()

    return obj


def get_closest(values: Iterable[int], target: int) -> int:
    """Returns the integer in ``values`` closest to ``target``."""
    return min(values, key=lambda offset: abs(offset - target))


def generate_file_id(filename: str, content_size: int) -> PdfHexString:
    """Generates a file identifier using ``filename`` and ``content_size`` as
    described in § 14.4, "File identifiers".

    File identifiers are values that uniquely separate a revision of a document
    from another. The file identifier is generated using the same information
    specified in the standard, that is, the current time, the file path and
    the file size in bytes.
    """

    id_digest = hashlib.md5(time().isoformat("auto").encode())
    id_digest.update(filename.encode())
    id_digest.update(str(content_size).encode())

    return PdfHexString(id_digest.hexdigest().encode())


def is_page_or_page_tree(obj: PdfObject | PdfStream) -> bool:
    """Reports whether an object ``obj`` is a page object or a page tree node."""

    if not isinstance(obj, PdfDictionary) or "Type" not in obj:
        return False

    if not isinstance(tp := obj["Type"], PdfName) or tp.value not in [b"Page", b"Pages"]:
        return False

    return True


def copy_object(obj: PdfObject | PdfStream) -> PdfObject | PdfStream:
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
        return PdfStream(copy_object(obj.details), obj.raw, copy_object(obj._crypt_params))
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
    dest: PdfParser, root: PdfObject | PdfStream, *, ignore_keys: list[str] | None = None
) -> PdfObject | PdfStream:
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
    references replaces the old reference in the object.
    """

    if ignore_keys is None:
        ignore_keys = []

    cloned_map = {}
    references = set()

    def inner(obj: PdfObject | PdfStream) -> type[Placeholder] | PdfObject | PdfStream:
        if obj in cloned_map:
            # object is already cloned
            return cloned_map[obj]

        if isinstance(obj, PdfReference):
            referred = obj.get()

            if referred is root:
                # object refers to our origin object. in which case, simply set
                # a placeholder for later processing
                return Placeholder

            if is_page_or_page_tree(referred):
                # avoid going to pages or anything that might lead us to the page tree
                LOGGER.warning("object %s cannot be reliably copied and has been set to null.", obj)
                return PdfNull()

            cloned_direct = inner(referred)
            cloned_map[obj] = dest.objects.add(cloned_direct)
            references.add(cloned_map[obj])
            return cloned_map[obj]
        elif isinstance(obj, PdfDictionary):
            kv = PdfDictionary()
            cloned_map[obj] = kv
            for key, value in obj.data.items():
                if obj is root and key in ignore_keys:
                    continue

                kv.data[key] = inner(value)
            return kv
        elif isinstance(obj, PdfStream):
            stm = PdfStream(inner(obj.details), obj.raw, inner(obj._crypt_params))
            cloned_map[obj] = stm
            return stm
        elif isinstance(obj, PdfArray):
            arr = PdfArray()
            cloned_map[obj] = arr
            for value in obj.data:
                arr.data.append(inner(value))
            return arr
        elif isinstance(obj, PdfName):
            return PdfName(obj.value)
        elif isinstance(obj, PdfHexString):
            return PdfHexString(obj.raw)

        return obj

    cloned = inner(root)

    def replace_placeholders(obj: PdfObject | type[Placeholder]) -> PdfObject:
        if obj is Placeholder:
            return dest.objects.add(cloned)
        elif isinstance(obj, PdfArray):
            return PdfArray(replace_placeholders(it) for it in obj.data)
        elif isinstance(obj, PdfDictionary):
            return PdfDictionary({key: replace_placeholders(val) for key, val in obj.data.items()})
        elif isinstance(obj, PdfStream):
            obj.details = replace_placeholders(obj.details)
            obj._crypt_params = replace_placeholders(obj._crypt_params)
            return obj

        return obj

    final = replace_placeholders(cloned)
    for ref in references:
        direct = dest.objects[ref.object_number]
        dest.objects[ref.object_number] = replace_placeholders(direct)

    return final
