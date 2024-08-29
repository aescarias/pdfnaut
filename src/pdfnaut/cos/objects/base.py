from __future__ import annotations

from binascii import hexlify, unhexlify
from dataclasses import dataclass
from collections.abc import Callable
from typing import cast, Generic, TYPE_CHECKING, TypeVar, Union
from typing_extensions import Self

from ...exceptions import PdfResolutionError

if TYPE_CHECKING:
    from .containers import PdfArray, PdfDictionary


class PdfNull:
    """A PDF object representing nothing (``§ 7.3.9 Null Object``)."""
    def __repr__(self) -> str:
        return "null"


@dataclass
class PdfComment:
    """A comment introduced by the presence of the percent sign (``%``) outside a string or 
    inside a string. Comments have no syntactical meaning and shall be interpreted as 
    whitespace (``§ 7.2.4 Comments``)."""
    value: bytes


if TYPE_CHECKING:
    from typing_extensions import TypeVar

    T = TypeVar("T", default=bytes)
else:
    T = TypeVar("T") # pytest complains if this is not here


@dataclass
class PdfName(Generic[T]):
    """An atomic symbol uniquely defined by a sequence of 8-bit characters 
    (``§ 7.3.5 Name Objects``)."""
    value: T


@dataclass
class PdfHexString:
    """A PDF hexadecimal string which can be used to include arbitrary binary data in a PDF
    (``§ 7.3.4.3 Hexadecimal Strings``)."""
    
    raw: bytes
    """The hex value of the string"""
    
    def __post_init__(self) -> None:
        # If uneven, we append a zero. (it's hexadecimal -- 2 chars = byte)
        if len(self.raw) % 2 != 0:
            self.raw += b"0"

    @classmethod
    def from_raw(cls, data: bytes):
        """Creates a hexadecimal string from ``data``"""
        return cls(hexlify(data))

    @property
    def value(self) -> bytes:
        """The decoded value of the hex string"""
        return unhexlify(self.raw)


T = TypeVar("T")
@dataclass
class PdfReference(Generic[T]):
    """A reference to a PDF indirect object (``§ 7.3.10 Indirect objects``)."""
    object_number: int
    generation: int

    def __post_init__(self) -> None:
        self._resolver: ObjectGetter | None = None

    def with_resolver(self, resolver: ObjectGetter) -> Self:
        self._resolver = resolver
        return self

    def get(self) -> T:
        """Returns the object this reference points to. If unable to resolve, 
        returns :exc:`.PdfResolutionError`"""
        if self._resolver:
            return self._resolver(self)

        raise PdfResolutionError("Could not resolve")


@dataclass
class PdfOperator:
    """A PDF operator within a content stream (``§ 7.8.2 Content streams``)."""
    value: bytes


def parse_text_string(encoded: PdfHexString | bytes) -> str:
    """Parses a text string as defined in ``§ 7.9.2.2 Text string type``.

    Text strings may either be encoded in PDFDocEncoding, UTF-16BE, or (PDF 2.0) UTF-8.
    Each encoding is indicated by a byte-order mark at the beginning (``\xfe\xff`` 
    for UTF-16BE and ``\xef\xbb\xbf`` for UTF-8). PDFDocEncoded strings have no such
    mark.
    """
    value = cast(bytes, encoded.value if isinstance(encoded, PdfHexString) else encoded)

    if value.startswith(b"\xfe\xff"):
        return value.decode("utf-16be")
    elif value.startswith(b"\xef\xbb\xbf"):
        return value.decode("utf-8")

    # FIXME: Write an actual encoding for PDFDocEncoding. This ain't it.
    try:
        return value.decode("pdfdoc")
    except LookupError:
        return value.decode("latin-1")


PdfObject = Union[
    bool, int, float, bytes, "PdfArray", "PdfDictionary", 
    PdfHexString, PdfName, PdfReference, PdfNull
]
ObjectGetter = Callable[[PdfReference], T]
