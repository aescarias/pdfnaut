from __future__ import annotations

import hashlib
from collections.abc import Iterable
from datetime import time
from typing import TypeVar

from ..cos.objects.base import PdfHexString, PdfReference


def get_value_from_bytes(contents: PdfHexString | bytes) -> bytes:
    """Returns the inner value of ``contents`` if it is an instance of
    :class:`.PdfHexString`, otherwise returns ``contents``"""
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
    """Generates a file identifier as described in ``§ 14.4 File identifiers``.
    File identifiers are values that uniquely separate a revision from another.

    The file identifier is generated using the same information specified in the standard.
    That is, the current time (formatted as ISO), the file path, and the file size in bytes.
    """

    id_digest = hashlib.md5(time().isoformat("auto").encode())
    id_digest.update(filename.encode())
    id_digest.update(str(content_size).encode())

    return PdfHexString(id_digest.hexdigest().encode())
