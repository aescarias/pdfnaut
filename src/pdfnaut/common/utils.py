from __future__ import annotations

import hashlib
from collections.abc import Iterable
from datetime import time
from typing import TypeVar

from ..cos.objects.base import ObjectGetter, PdfHexString, PdfObject, PdfReference
from ..cos.objects.containers import PdfArray, PdfDictionary
from ..cos.objects.stream import PdfStream


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
    described in § 14.4 "File identifiers".

    File identifiers are values that uniquely separate a revision of a document
    from another. The file identifier is generated using the same information
    specified in the standard, that is, the current time, the file path and
    the file size in bytes.
    """

    id_digest = hashlib.md5(time().isoformat("auto").encode())
    id_digest.update(filename.encode())
    id_digest.update(str(content_size).encode())

    return PdfHexString(id_digest.hexdigest().encode())


def renumber_references(
    root: PdfObject, resolver: ObjectGetter, start: int = 1
) -> tuple[PdfObject, dict[int, PdfObject]]:
    """Renumbers all references in ``root`` (including its nested objects) based on ``start``.

    Arguments:
        root (PdfDictionary, PdfArray, or PdfStream):
            The root object to renumber references in.

        resolver (ObjectGetter):
            The resolver attached to each new reference.

        start (int, optional):
            An integer from which to start numbering new references (by default, 1).

    Returns:
        A tuple of two items including the root object with the renumbered references and a
        mapping of reference numbers to items that can be written to the object store.

    .. warning::
        Because this function works recursively, ``root`` should not contain cyclic
        references, that is, reference paths that may point back to ``root``.
    """
    references = {}

    def inner(obj: PdfObject) -> PdfObject:
        nonlocal start

        if isinstance(obj, PdfDictionary):
            for key, value in obj.data.items():
                obj.data[key] = inner(value)
        elif isinstance(obj, PdfStream):
            for key, value in obj.details.data.items():
                obj.details.data[key] = inner(value)
        elif isinstance(obj, PdfArray):
            for idx, value in enumerate(obj.data):
                obj.data[idx] = inner(value)
        elif isinstance(obj, PdfReference):
            referred = inner(obj.get())

            val = PdfReference(start, 0).with_resolver(resolver)
            start += 1

            references[val.object_number] = referred
            return val

        return obj

    return inner(root), references
