from typing import Any, TypeGuard, TypeVar

from pdfnaut.cos.objects import PdfObject
from pdfnaut.cos.objects.base import PdfHexString, PdfNull, PdfReference

T = TypeVar("T", bound=PdfObject)
R = TypeVar("R")
BytesLike = PdfHexString | bytes


def ensure(obj: Any, is_type: type[T]) -> T:
    """Asserts that an object ``obj`` is of type ``is_type``. Returns the object
    as is if this is the case; raises :exc:`TypeError` if not."""
    if not isinstance(obj, is_type):
        raise TypeError(f"expected type {is_type.__name__}, got {type(obj).__name__}")

    return obj


def is_null_like(obj: PdfObject | None) -> TypeGuard[PdfNull | None]:
    """Reports whether an object ``obj`` is the PDF null type or the Python ``None`` type."""
    return isinstance(obj, PdfNull) or obj is None


def deref(obj: PdfReference[R] | R) -> R:
    """Resolves and returns an object ``obj`` if it is a reference, otherwise
    returns it directly."""
    if isinstance(obj, PdfReference):
        return obj.get()

    return obj


def into_bytes(obj: BytesLike) -> bytes:
    """Returns the decoded value of ``contents`` if it is an instance of
    :class:`.PdfHexString`, otherwise returns ``contents`` as is."""
    return obj.value if isinstance(obj, PdfHexString) else obj
