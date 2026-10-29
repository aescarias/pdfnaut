from __future__ import annotations

import logging
import mmap
import re
from collections import UserDict
from enum import IntEnum
from functools import partial
from io import BytesIO
from pathlib import Path
from typing import BinaryIO, TypeVar, cast

from typing_extensions import Buffer, Self, TypeAlias

from ..common._utils import get_closest
from ..cos.objects.base import (
    BytesLike,
    PdfHexString,
    PdfName,
    PdfNull,
    PdfObject,
    PdfReference,
    is_null_like,
)
from ..cos.objects.containers import PdfArray, PdfDictionary
from ..cos.objects.stream import PdfStream
from ..cos.objects.xref import (
    CompressedXRefEntry,
    FreeXRefEntry,
    InUseXRefEntry,
    PdfXRefEntry,
    PdfXRefSection,
    PdfXRefSubsection,
)
from ..exceptions import PdfParseError
from ..security.standard_handler import StandardSecurityHandler
from .lexer import PdfLexer, TokenType
from .object_parser import PdfObjectParser

LOGGER = logging.getLogger(__name__)


class PermsAcquired(IntEnum):
    """Permissions acquired after opening or decrypting a document."""

    NONE = 0
    """No permissions acquired, document is still encrypted."""
    USER = 1
    """User permissions within the limits specified by the security handler."""
    OWNER = 2
    """Owner permissions (all permissions)."""


class FreeObject:
    def __repr__(self) -> str:
        return "free"


MapObject: TypeAlias = "PdfObject | FreeObject"


class ObjectStream:
    """A mapping of object numbers to PDF objects representing an object stream
    (see ISO 32000-2:2020 § 7.5.7 "Object Streams")."""

    def __init__(self, pdf: PdfReader, stream: PdfStream, stream_objnum: int) -> None:
        """
        Arguments:
            pdf (PdfReader):
                The PDF parser or document to which this object stream belongs.

            stream (PdfStream):
                The stream being represented by this object.

            stream_objnum (int):
                The object number of this stream within the PDF document.
        """

        self.pdf = pdf
        self.stream = stream
        self.stream_objnum = stream_objnum

        # object index: resolved object
        self.resolved_objects: dict[int, PdfObject] = {}

        self._decoded = self.stream.decode()
        self._first = cast(int, self.stream.details["First"])
        self._n_objects = cast(int, self.stream.details["N"])

        # list of tuples of (object number, relative offset within)
        self.index_pairs = self.parse_indices()

    def parse_indices(self) -> list[tuple[int, int]]:
        """Parses the object stream's indices.

        The indices are a list of 2-element pairs specifying, in order, the object
        number of an item within the stream and the object's location within the
        stream relative to the offset in the /First key.
        """

        lexer = PdfLexer(self._decoded[: self._first])
        index_pairs: list[tuple[int, int]] = []

        for _ in range(self._n_objects):
            obj_num = int(lexer.read_token(TokenType.INTEGER).value)
            rel_offset = int(lexer.read_token(TokenType.INTEGER).value)  # relative to /First
            index_pairs.append((obj_num, rel_offset))

        return index_pairs

    def get_object(self, index: int, *, cache: bool = True) -> PdfObject:
        """Gets an object at a specified ``index`` inside an object stream.

        Arguments:
            index (int):
                The index of an object within the stream.

            cache (bool, optional, keyword only):
                Whether to access or write to the object store (by default, True).

                If True, this method will always retrieve from and write objects
                to the object store if possible. If False, this method will always
                retrieve objects from the contents of the stream.
        """

        if cache and index in self.resolved_objects:
            return self.resolved_objects[index]

        _, rel_offset = self.index_pairs[index]

        lexer = PdfLexer(self._decoded[self._first + rel_offset :])
        reader = PdfObjectParser(lexer, resolver=self.pdf.get_object)

        resolved = next(reader)
        if cache:
            self.resolved_objects[index] = resolved

        return resolved


class ObjectMap(UserDict[int, MapObject]):
    """A mapping of object numbers to either object references, in-use objects or free objects.

    Object references included in :attr:`.ObjectMap.unresolved` are items that have not been
    requested yet. Once an object is requested, it is removed from the unresolved set and
    added to the map as is.

    Free objects are indicated with the :class:`.FreeObject` class.
    """

    def __init__(self, pdf: PdfReader) -> None:
        super().__init__()

        self._pdf = pdf
        self.initial_reference_map: dict[int, tuple[int, int]] = {}
        """A mapping of object numbers to reference tuples for the initial entries made
        when the object map is filled."""

        self.unresolved = set()
        """A set of unresolved object numbers (objects that have not been requested 
        or cached yet)."""

    def fill(self) -> None:
        """Fills the object map with the items available in the PDF's xref table."""
        self.initial_reference_map = {obj: (obj, gen) for (obj, gen) in self._pdf.xref.keys()}
        self.unresolved.clear()

        for obj, gen in self.initial_reference_map.values():
            entry = self._pdf.xref[(obj, gen)]
            if isinstance(entry, FreeXRefEntry):
                self[obj] = FreeObject()
            else:
                self[obj] = PdfReference(obj, gen).with_resolver(self._pdf.get_object)
                self.unresolved.add(obj)

    T = TypeVar("T")

    def get_next_ref(self) -> PdfReference:
        """Creates a new reference based on the current object number in the map."""
        if not self:
            return PdfReference(1, 0)

        highest_objnum = max(self.keys())
        return PdfReference(highest_objnum + 1, 0)

    def add(self, pdf_object: PdfObject) -> PdfReference[PdfObject]:
        """Adds a new ``pdf_object`` to the map. Returns its reference."""
        reference = self.get_next_ref()
        self[reference.object_number] = pdf_object

        return reference.with_resolver(self._pdf.get_object)

    def delete(self, obj_num: int) -> MapObject | None:
        """Deletes object with number ``obj_num``. Returns the object if it
        exists, otherwise returns None."""
        return self.pop(obj_num, None)

    def free(self, obj_num: int) -> None:
        """Marks object with number ``obj_num`` as a free object."""
        self[obj_num] = FreeObject()

    def __getitem__(self, obj_num: int) -> MapObject:
        value = super().__getitem__(obj_num)

        if isinstance(value, PdfReference) and obj_num in self.unresolved:
            resolved = self[obj_num] = value.get()
            self.unresolved.discard(obj_num)
            return resolved

        return value


class PdfReader:
    """The low-level PDF document reader."""

    def __init__(self, source: Buffer | BinaryIO | str | Path, *, strict: bool = False) -> None:
        """Initializes a PDF reader.

        Args:
            source:
                The document to read. May be either a bytes object, a seekable
                binary file-like object, a string (representing a path),
                or a :class:`pathlib.Path` object.

            strict:
                Whether to read the document without attempting to perform repairs
                or fix issues caused by spec deviations (default is False).
        """

        self.strict = strict

        self._source = source
        self._setup_reader()

        self._lexer = PdfLexer(self._view)
        self._object_reader = PdfObjectParser(self._lexer, resolver=self.get_object)

        #   object number: object stream
        self._objstm_cache: dict[int, ObjectStream] = {}

        #   object number:  direct object
        self.objects = ObjectMap(self)
        """A mapping of objects present in the document."""

        self.updates: list[PdfXRefSection] = []
        """A list of all incremental updates present in the document (most recent update first)."""

        # placeholder to make the type checker happy
        self.trailer = PdfDictionary[str, PdfObject]({"Size": 0, "Root": PdfReference(0, 0)})
        """The most recent trailer in the PDF document.
        
        For details on the contents of the trailer, see ISO 32000-2:2020 § 7.5.5 "File Trailer".
        """

        self.xref: dict[tuple[int, int], PdfXRefEntry] = {}
        """A cross-reference mapping combining the entries of all XRef tables present 
        in the document.
        
        The key is a tuple of two integers: object number and generation number. 
        The value is any of the 3 types of XRef entries (free, in use, compressed).

        This attribute reflects the state of the XRef table when the document was 
        first loaded. Assume read-only.
        """

        self.header_version = ""
        """The document's PDF version as seen in the header.

        This value should be used if no Version entry exists in the document catalog or 
        if the header's version is newer. Otherwise, use the Version entry.
        """

        self.security_handler = None
        """The document's standard security handler, if any, as specified in the Encrypt 
        dictionary of the PDF trailer.

        This field being set indicates that a supported security handler was used for
        encryption. If not set, the parser will not attempt to decrypt this document.
        """

        self._encryption_key = None
        self._hot_references: list[PdfReference] = []
        """A list of references being currently processed by :meth:`.get_object()`.
        
        This is here as a measure to prevent circular reference loops.
        """

        self._parse()

    def _setup_reader(self) -> None:
        self._file_obj: BinaryIO | None = None
        self._mmap: mmap.mmap | None = None
        self._view: memoryview
        self._owns_source: bool = False

        if isinstance(self._source, BytesIO):
            self._file_obj = self._source
            self._view = self._source.getbuffer()
            return

        if isinstance(self._source, Buffer):
            self._view = memoryview(self._source)
            return

        if isinstance(self._source, (str, Path)):
            self._file_obj = open(self._source, "rb")
            self._owns_source = True
        else:
            self._file_obj = self._source

        try:
            try:
                self._mmap = mmap.mmap(self._file_obj.fileno(), 0, access=mmap.ACCESS_READ)
                self._view = memoryview(self._mmap)
            except ValueError:
                LOGGER.warning(
                    "mmap not supported on %r, loading document into memory", self._source
                )

                pos = self._file_obj.tell()
                try:
                    self._file_obj.seek(0)
                    contents = self._file_obj.read()
                finally:
                    self._file_obj.seek(pos)

                self._view = memoryview(contents)
        except Exception as exc:
            self._cleanup_reader()
            raise exc

    def _cleanup_reader(self) -> None:
        self._view.release()

        if self._mmap is not None:
            self._mmap.close()

        if self._file_obj is not None and self._owns_source:
            self._file_obj.close()

    @property
    def closed(self) -> bool:
        try:
            _ = self._view[0]
            return False
        except ValueError:
            pass

        if self._mmap is not None and not self._mmap.closed:
            return False

        if self._file_obj is not None and self._owns_source:
            return self._file_obj.closed

        return True

    def close(self) -> None:
        self._cleanup_reader()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc_args) -> bool:
        self.close()
        return False

    def _parse(self) -> None:
        """Parses the entire document.

        The parser begins by locating the PDF header, then finding and combining
        the cross-reference sections in the document. It finally builds the object
        store and prepares the security handler for encrypted documents.
        """

        # step 1: read the header
        header, offset = self._locate_header()
        self.header_version = header.removeprefix(b"%PDF-").decode("ascii")
        if offset != 0:
            original_view = self._view
            self._view = original_view[offset:]
            self._lexer._view = self._view
            original_view.release()

        # step 2: get the most recent startxref
        startxrefs = list(re.finditer(b"startxref", self._view))
        if not startxrefs:
            # TODO: trigger xref rebuild when not in strict mode
            raise PdfParseError("could not locate xref table because startxref is missing")

        # step 3: read the xref table
        startxref = self._get_startxref(startxrefs[-1].start())
        self._build_xref_table(startxref)

        # step 4: fill the object store so we can refer to objects.
        self.objects.fill()

        # step 5: check if the document uses the standard security handler.
        encryption = self.trailer.get("Encrypt")
        if not is_null_like(encryption):
            ids = cast(PdfArray[BytesLike], self.trailer["ID"])

            encryption = cast(PdfDictionary, encryption)
            sec_filter = cast(PdfName, encryption["Filter"])
            if sec_filter.value == b"Standard":
                self.security_handler = StandardSecurityHandler(encryption, ids)
            else:
                LOGGER.warning("document uses unknown security handler %s", sec_filter)

    def _locate_header(self) -> tuple[bytes, int]:
        """Locates the PDF header in ``view`` returning the header value (%PDF-n.m)
        and its absolute byte offset, from which the rest of the byte offsets shall
        be calculated."""

        # The PDF header SHOULD be at position 0; however, arbitrary data may precede
        # the header in some cases. Previous specs did not allow this explicitly.
        # The PDF 2.0 specification does have this provision, but does not specify the
        # maximum length of the arbitrary data, so in theory, the whole document should
        # be scanned.

        # %PDF-n.m where n is major version and m is minor version
        header = re.search(rb"%PDF-\d+\.\d+", self._view)
        if header is None:
            raise PdfParseError("could not locate PDF header")

        header_text = header.group()
        header_offset = header.start()

        if header_offset != 0 and self.strict:
            raise PdfParseError("PDF header not at offset 0")

        return (header_text, header_offset)

    def _get_startxref(self, offset: int) -> int:
        """Gets the startxref offset, pointing to an xref section."""

        self._lexer.seek(offset)

        # § 7.5.5 - An incremental update (or document) ends with three lines:
        # "startxref", the offset to the xref table and trailer, and "%%EOF".
        keyword = self._lexer.consume(9)
        if keyword != b"startxref":
            raise ValueError("offset must point to startxref")

        self._lexer.skip_whitespace()

        # read the startxref integer
        xref_start = bytearray()
        while (ch := self._lexer.peek()) and ch in b"0123456789":
            xref_start += self._lexer.consume()

        xref_start = int(xref_start)
        self._lexer.skip_whitespace()

        # read the EOF
        eof = self._lexer.consume(5)
        if eof != b"%%EOF":
            if self.strict:
                raise PdfParseError("expected EOF marker")

            LOGGER.warning("expected EOF marker after startxref")

        return xref_start

    def _build_xref_table(self, offset: int) -> None:
        """Recursively builds the PDF cross-reference table, starting from ``offset``."""
        self._lexer.seek(offset)

        section = self._parse_xref_section()
        self.updates.append(section)

        prev = section.trailer.get("Prev")
        if not is_null_like(prev):
            self._build_xref_table(cast(int, prev))
        else:
            self.xref = self._get_merged_xrefs()
            self.trailer = self.updates[0].trailer

    def _build_xref_mapping(
        self, subsections: list[PdfXRefSubsection]
    ) -> dict[tuple[int, int], PdfXRefEntry]:
        """Creates a dictionary mapping references to XRef entries in the document."""
        entry_map: dict[tuple[int, int], PdfXRefEntry] = {}

        for subsection in subsections:
            for idx, entry in enumerate(subsection.entries, subsection.first_obj_number):
                if isinstance(entry, FreeXRefEntry):
                    gen = entry.gen_if_used_again
                elif isinstance(entry, InUseXRefEntry):
                    gen = entry.generation
                else:
                    # compressed entries assume a generation of 0.
                    gen = 0

                entry_map[(idx, gen)] = entry

        return entry_map

    def _get_merged_xrefs(self) -> dict[tuple[int, int], PdfXRefEntry]:
        """Combines all XRef updates in the document into a cross-reference mapping
        that includes all entries."""
        entry_map: dict[tuple[int, int], PdfXRefEntry] = {}
        hybrid_objnums: list[int] = []

        # from least recent to most recent
        for section in self.updates[::-1]:
            update_map = self._build_xref_mapping(section.subsections)

            # if the document is a hybrid-reference file, append any hidden objects.
            if "XRefStm" in section.trailer:
                self._lexer.seek(cast(int, section.trailer["XRefStm"]))

                xrefstm = self._parse_compressed_xref()
                hybrid_map = self._build_xref_mapping(xrefstm.subsections)

                for (obj, gen), hybrid_entry in hybrid_map.items():
                    update_entry = update_map.get((obj, gen))

                    # But only append if they aren't a thing or they are marked as "free"
                    if update_entry is None or (
                        isinstance(update_entry, FreeXRefEntry) and hybrid_entry is not None
                    ):
                        entry_map[(obj, gen)] = hybrid_entry
                        hybrid_objnums.append(obj)

            entry_map.update(update_map)

        # If entries from the "hybrid section" were added, we have to remove
        # the free entries they are meant to replace. Otherwise, the object store
        # might get a bit confused and panic.
        for objnum in hybrid_objnums:
            for (num, gen), entry in entry_map.items():
                if num == objnum and isinstance(entry, FreeXRefEntry):
                    del entry_map[(num, gen)]
                    break

        return entry_map

    def _parse_xref_section(self) -> PdfXRefSection:
        """Parses the cross-reference section and the PDF trailer included."""

        start_offset = self._lexer.tell()

        if self._lexer.matches(b"xref"):
            xref = self._parse_simple_xref()
            self._lexer.skip_whitespace()
            trailer = self._parse_simple_trailer()

            return PdfXRefSection(xref, trailer)
        elif self._try_parse_object_header() is not None:
            self._lexer.seek(start_offset)
            return self._parse_compressed_xref()
        elif not self.strict:
            LOGGER.warning("did not find xref table at offset %d", self._lexer.tell())

            # let's attempt to locate a nearby xref table
            target = self._lexer.tell()
            table_offsets = self._find_xref_offsets()

            # get the xref table nearest to our offset
            self._lexer.seek(get_closest(table_offsets, target))
            section = self._parse_xref_section()

            # make sure the user can see our corrections
            if "Prev" in section.trailer:
                section.trailer["Prev"] = get_closest(
                    table_offsets, cast(int, section.trailer["Prev"])
                )

            return section
        else:
            raise PdfParseError("XRef offset does not point to XRef section.")

    def _try_parse_object_header(self) -> tuple[int, int] | None:
        first_token = self._lexer.peek_token()
        if first_token.type is not TokenType.INTEGER:
            return

        second_token = self._lexer.peek_token(1)
        if second_token.type is not TokenType.INTEGER:
            return

        third_token = self._lexer.peek_token(2)
        if third_token.type is not TokenType.WORD or third_token.value != b"obj":
            return

        # At this point, we have determined that we have a reference candidate,
        # that is, INTEGER INTEGER WORD.
        #
        # For this candidate to be a valid reference (ISO 32000-2:2020 § 7.3.10):
        #  - The word must be the value "R".
        #  - The object number must be positive. It must not contain leading zeros
        #    and must not contain the + sign.
        #  - The generation number must be non-negative. Similar to object numbers,
        #    it shall not contain the + or - sign. Leading zeros are not allowed,
        #    though single digit zero is.

        self._lexer.next_token()  # consume first integer
        self._lexer.next_token()  # consume second integer
        self._lexer.next_token()  # consume obj

        if first_token.value.startswith((b"+", b"-", b"0")):
            raise PdfParseError(f"invalid object number {first_token.value!r}")

        if second_token.value != b"0" and second_token.value.startswith((b"+", b"-", b"0")):
            raise PdfParseError(f"invalid generation number {second_token.value!r}")

        return (int(first_token.value), int(second_token.value))

    def _find_xref_offsets(self) -> list[int]:
        table_offsets: list[int] = []

        # looks for the start of a xref table
        for mat in re.finditer(rb"(?<!start)xref(\W*)(\d+) (\d+)", self._lexer._view):
            table_offsets.append(mat.start())

        # looks for indirect objects, then checks if they are xref streams
        for mat in re.finditer(rb"(?P<num>\d+)\s+(?P<gen>\d+)\s+obj", self._lexer._view):
            self._lexer.seek(mat.start())
            self._lexer.skip(mat.end() - mat.start())
            self._lexer.skip_whitespace()

            if self._lexer.matches(b"<<"):
                mapping = self._object_reader.next_object()
                assert isinstance(mapping, PdfDictionary)

                if isinstance(typ := mapping.get("Type"), PdfName) and typ.value == b"XRef":
                    table_offsets.append(mat.start())

        return sorted(table_offsets)

    def _parse_simple_trailer(self) -> PdfDictionary:
        """Parses the PDF's standard trailer which is used to quickly locate other
        cross reference tables and special objects.

        The trailer is separate if the XRef table is standard (uncompressed).
        Otherwise it is part of the XRef object.
        """
        self._lexer.match(b"trailer", "expected trailer keyword")
        self._lexer.skip_whitespace()

        trailer = self._object_reader.next_object()
        if not isinstance(trailer, PdfDictionary):
            raise PdfParseError("expected trailer dictionary")

        return trailer

    def _parse_simple_xref(self) -> list[PdfXRefSubsection]:
        """Parses a standard, uncompressed XRef table of the format described in
        ISO 32000-2:2020 § 7.5.4 "Cross-Reference table".

        If ``startxref`` points to an XRef object, :meth:`.parse_compressed_xref`
        should be called instead.
        """
        self._lexer.match(b"xref", "expected xref keyword")
        self._lexer.skip_whitespace()

        subsections: list[PdfXRefSubsection] = []

        while True:
            # subsection
            subsection = re.match(rb"(?P<first_obj>\d+)\s(?P<count>\d+)", self._lexer.peek_line())
            if subsection is None:
                break

            self._lexer.skip(subsection.end())
            self._lexer.skip_whitespace()

            # xref entries
            entries: list[PdfXRefEntry] = []
            for idx in range(int(subsection.group("count"))):
                entry = re.match(
                    rb"(?P<offset>\d{10}) (?P<gen>\d{5}) (?P<status>[fn])",
                    self._lexer.peek(20),
                )
                if entry is None:
                    raise PdfParseError(f"Expected valid XRef entry at row {idx + 1}")

                offset = int(entry.group("offset"))
                generation = int(entry.group("gen"))

                if entry.group("status") == b"n":
                    entries.append(InUseXRefEntry(offset, generation))
                else:
                    entries.append(FreeXRefEntry(offset, generation))

                # some files do not respect the 20-byte length req. for entries
                # hence this is here for tolerance
                self._lexer.skip(entry.end())
                self._lexer.skip_whitespace()

            subsections.append(
                PdfXRefSubsection(
                    int(subsection.group("first_obj")),
                    int(subsection.group("count")),
                    entries,
                )
            )

        return subsections

    def _parse_compressed_xref(self) -> PdfXRefSection:
        """Parses a compressed cross-reference stream which includes both the XRef table
        and information from the PDF trailer as described in ISO 32000-2:2020 § 7.5.8
        "Cross-reference streams".
        """
        xref_stream = self._parse_indirect_object(InUseXRefEntry(self._lexer.tell(), 0), None)
        xref_stream = cast(PdfStream, xref_stream)

        contents = BytesIO(xref_stream.decode())

        xref_widths = cast(PdfArray[int], xref_stream.details["W"])
        xref_indices = cast(
            PdfArray[int],
            xref_stream.details.get("Index", PdfArray([0, xref_stream.details["Size"]])),
        )

        subsections: list[PdfXRefSubsection] = []

        for idx in range(0, len(xref_indices), 2):
            subsection = PdfXRefSubsection(
                first_obj_number=xref_indices[idx],
                count=xref_indices[idx + 1],
                entries=[],
            )

            for _ in range(subsection.count):
                field_type = int.from_bytes(contents.read(xref_widths[0]) or b"\x01", "big")
                second = int.from_bytes(contents.read(xref_widths[1]), "big")
                third = int.from_bytes(contents.read(xref_widths[2]), "big")

                if field_type == 0:
                    subsection.entries.append(
                        FreeXRefEntry(next_free_object=second, gen_if_used_again=third)
                    )
                elif field_type == 1:
                    subsection.entries.append(InUseXRefEntry(offset=second, generation=third))
                elif field_type == 2:
                    subsection.entries.append(
                        CompressedXRefEntry(objstm_number=second, index_within=third)
                    )
                else:
                    LOGGER.warning("ignoring unknown field type %s in xref table", field_type)

            subsections.append(subsection)

        return PdfXRefSection(subsections, xref_stream.details)

    def _parse_indirect_object(
        self, xref_entry: InUseXRefEntry, reference: PdfReference | None
    ) -> PdfObject:
        """Parses an indirect object not within an object stream, or basically, an object
        that is directly referred to by an ``xref_entry`` and a ``reference``."""
        self._lexer.seek(xref_entry.offset)
        self._lexer.skip_whitespace()

        obj_header = self._try_parse_object_header()
        if obj_header is None:
            raise PdfParseError("XRef entry does not point to a valid indirect object.")

        self._lexer.skip_whitespace()
        contents = self._object_reader.next_object()
        self._lexer.skip_whitespace()

        # uh oh, a stream?
        if self._lexer.matches(b"stream"):
            extent = cast(PdfDictionary, contents)

            # the implicit get_object call might move us around so we must save and then
            # restore the previous position
            _current = self._lexer.tell()
            length = extent["Length"]
            self._lexer.seek(_current)

            if not isinstance(length, int):
                raise PdfParseError("Length entry of stream extent not an integer")

            item = PdfStream(extent, self._parse_stream(xref_entry, length))
        else:
            item = cast(PdfObject, contents)

        return self._get_decrypted(item, reference)

    def _get_decrypted(self, pdf_object: PdfObject, reference: PdfReference | None) -> PdfObject:
        if self.security_handler is None or not self._encryption_key or reference is None:
            return pdf_object

        if isinstance(pdf_object, PdfStream):
            use_stmf = True

            # Don't use StmF if the stream handles its own encryption
            if filter_ := pdf_object.details.get("Filter"):
                if isinstance(filter_, PdfName):
                    filters = PdfArray[PdfName]([filter_])
                else:
                    filters = cast(PdfArray[PdfName], filter_)

                for name in filters:
                    if name.value == b"Crypt":
                        use_stmf = False
                        pdf_object._crypt_params = PdfDictionary(
                            Handler=self.security_handler,
                            EncryptionKey=self._encryption_key,
                            Reference=reference,
                        )
                        break

            if use_stmf:
                pdf_object.raw = self.security_handler.decrypt_object(
                    self._encryption_key, pdf_object, reference
                )

            return pdf_object
        elif isinstance(pdf_object, PdfHexString):
            return PdfHexString.from_raw(
                self.security_handler.decrypt_object(
                    self._encryption_key, pdf_object.value, reference
                )
            )
        elif isinstance(pdf_object, bytes):
            return self.security_handler.decrypt_object(self._encryption_key, pdf_object, reference)
        elif isinstance(pdf_object, PdfArray):
            return PdfArray(
                (self._get_decrypted(cast(PdfObject, obj), reference) for obj in pdf_object.data)
            )
        elif isinstance(pdf_object, PdfDictionary):
            # The Encrypt key does not need decrypting.
            if reference == self.trailer.data["Encrypt"]:
                return pdf_object

            return PdfDictionary(
                {
                    name: self._get_decrypted(cast(PdfObject, value), reference)
                    for name, value in pdf_object.data.items()
                }
            )

        # Why would a number be encrypted?
        return pdf_object

    def _parse_stream(self, xref_entry: InUseXRefEntry, extent: int) -> bytes:
        """Parses the contents of a PDF stream at ``xref_entry``.

        ``extent`` specifies the amount of bytes the stream is expected to have.
        """

        self._lexer.match(b"stream", "expected stream keyword")
        self._lexer.skip_next_eol(no_cr=True)

        contents = self._lexer.consume(extent)
        self._lexer.skip_next_eol(no_cr=True)

        if self.xref:
            # We get the offset of the entry directly following this one as a bounds check
            next_entry_at = iter(
                val
                for val in self.xref.values()
                if isinstance(val, InUseXRefEntry) and val.offset > xref_entry.offset
            )
        else:
            # The stream being parsed is (most likely) part of an XRef object
            next_entry_at = iter([])

        # Have we gone way beyond the stream?
        try:
            if self._lexer.tell() >= next(next_entry_at).offset:
                raise PdfParseError("\\Length key in stream extent parses beyond object.")
        except StopIteration:
            pass

        # Are we done?
        self._lexer.skip_whitespace()
        if not self._lexer.match_and_skip(b"endstream"):
            raise PdfParseError("\\Length key in stream extent does not match end of stream.")

        return contents

    def get_object(
        self, reference: PdfReference | tuple[int, int], cache: bool = True
    ) -> MapObject:
        """Resolves a reference into the indirect object it points to.

        Arguments:
            reference (PdfReference | tuple[int, int]):
                A :class:`.PdfReference` object or a tuple of two integers representing,
                in order, the object number and the generation number.

            cache (bool, optional):
                Whether to interact with the object store when resolving references.
                Defaults to True.

                When True, the parser will read entries from the object store and write new
                ones if they are not present. If False, the parser will always fetch new
                entries and will not write to the object store.

                Note that the object store will be accessed regardless of the value of
                ``cache`` if the object is new and is not included in the xref table.

        Returns:
            The object the reference resolves to.

            If the reference is invalid (i.e. does not exist), returns :class:`.PdfNull`.
            If the object referred to is a free object, returns :class:`.FreeObject`.
        """
        if isinstance(reference, tuple):
            reference = PdfReference(*reference).with_resolver(self.get_object)

        self._hot_references.append(reference)
        if self._hot_references.count(reference) > 1:
            loop = " -> ".join(
                f"{ref.object_number} {ref.generation} R" for ref in self._hot_references
            )
            self._hot_references.clear()

            raise PdfParseError(f"Possible circular reference loop hit: {loop}")

        # If cache requested and the object is cached.
        if cache and reference.object_number not in self.objects.unresolved:
            self._hot_references.remove(reference)
            return self.objects[reference.object_number]

        root_entry = self.xref.get((reference.object_number, reference.generation))

        if root_entry is None:
            # the reference is referring to a new object not registered in the xref table
            if (obj_entry := self.objects.get(reference.object_number)) is not None:
                self._hot_references.remove(reference)
                return obj_entry

            return PdfNull()

        if isinstance(root_entry, InUseXRefEntry):
            obj = self._parse_indirect_object(root_entry, reference)

            if not cache:
                self._hot_references.remove(reference)
                return obj

            # Add to cache then set the object as resolved.
            self.objects[reference.object_number] = obj
            self.objects.unresolved.discard(reference.object_number)

            self._hot_references.remove(reference)

            return self.objects[reference.object_number]
        elif isinstance(root_entry, CompressedXRefEntry):
            # Get the object stream it's part of (gen always 0)
            objstm_ref = (root_entry.objstm_number, 0)
            objstm_entry = self.xref[objstm_ref]
            assert isinstance(objstm_entry, InUseXRefEntry)

            if cache and root_entry.objstm_number not in self.objects.unresolved:
                objstm = self.objects[root_entry.objstm_number]
            else:
                objstm = self._parse_indirect_object(
                    objstm_entry,
                    PdfReference(*objstm_ref).with_resolver(partial(self.get_object, cache=False)),
                )

            assert isinstance(objstm, PdfStream)

            if cache:
                self.objects[root_entry.objstm_number] = objstm
                self.objects.unresolved.discard(root_entry.objstm_number)

            if cache and root_entry.objstm_number in self._objstm_cache:
                stm = self._objstm_cache[root_entry.objstm_number]
            else:
                stm = ObjectStream(self, objstm, root_entry.objstm_number)

            if cache:
                self._objstm_cache[root_entry.objstm_number] = stm

            self._hot_references.remove(reference)
            return stm.get_object(root_entry.index_within)

        self._hot_references.remove(reference)
        return PdfNull()

    def decrypt(self, password: str) -> PermsAcquired:
        """Decrypts this document through the Standard security handler using the
        provided ``password``.

        The standard security handler may specify 2 passwords: an owner password and a user
        password. The owner password would allow full access to the PDF and the user password
        should allow access according to the permissions specified in the document.

        When the document is decrypted successfully, the object cache is cleared to make way
        for the new objects in decrypted form.

        Returns:
            PermsAcquired: A value specifying the permissions acquired by ``password``.

            - If the document is not encrypted, defaults to :attr:`.PermsAcquired.OWNER`
            - if the document was not decrypted, defaults to :attr:`.PermsAcquired.NONE`
        """
        if self.security_handler is None:
            return PermsAcquired.OWNER

        # Is this the owner password?
        encryption_key, is_owner_pass = self.security_handler.authenticate_owner_password(
            password.encode()
        )
        if is_owner_pass:
            self._encryption_key = encryption_key
            self.objects.fill()
            return PermsAcquired.OWNER

        # Is this the user password?
        encryption_key, is_user_pass = self.security_handler.authenticate_user_password(
            password.encode()
        )
        if is_user_pass:
            self._encryption_key = encryption_key
            self.objects.fill()
            return PermsAcquired.USER

        return PermsAcquired.NONE
