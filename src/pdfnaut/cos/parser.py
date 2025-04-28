from __future__ import annotations

import re
from collections import UserDict
from enum import IntEnum
from functools import partial
from io import BufferedIOBase, BytesIO
from pathlib import Path
from typing import Any, BinaryIO, TypeVar, cast, overload

from typing_extensions import TypeAlias

from ..common.utils import generate_file_id, get_closest
from ..cos.objects.base import PdfHexString, PdfName, PdfNull, PdfObject, PdfReference
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
from .serializer import PdfSerializer, serialize
from .tokenizer import PdfTokenizer

PDF_HEADER_REGEX = re.compile(rb"PDF-(?P<major>\d+).(?P<minor>\d+)")
INDIRECT_OBJ_HEADER_REGEX = re.compile(rb"(?P<num>\d+)\s+(?P<gen>\d+)\s+obj")


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


MapObject: TypeAlias = "PdfObject | PdfStream | FreeObject"


class ObjectStream:
    """A mapping of object numbers to PDF objects representing an object stream.

    See § 7.5.7 Object streams for details.
    """

    def __init__(self, pdf: PdfParser, stream: PdfStream, stream_objnum: int) -> None:
        """
        Arguments:
            pdf (PdfParser):
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
        index_tokenizer = PdfTokenizer(self._decoded[: self._first])
        index_pairs = []

        for _ in range(self._n_objects):
            obj_num = cast(int, next(index_tokenizer))
            relative_offset = cast(int, next(index_tokenizer))  # relative to /First
            index_pairs.append((obj_num, relative_offset))

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

        _, relative_offset = self.index_pairs[index]
        start_of_obj_tokenizer = PdfTokenizer(self._decoded[self._first + relative_offset :])
        start_of_obj_tokenizer.resolver = self.pdf.get_object

        resolved = cast(PdfObject, next(start_of_obj_tokenizer))

        if cache:
            self.resolved_objects[index] = resolved

        return resolved

    def to_stream(self) -> PdfStream:
        """Returns a :class:`.PdfStream` representing the contents of this object stream."""

        object_string = b""
        indices = []

        for idx in range(self._n_objects):
            if cached := self.resolved_objects.get(idx):
                writing_object = cached
            else:
                writing_object = self.get_object(idx, cache=False)

            obj_num, _ = self.index_pairs[idx]
            entry = self.pdf.xref.get((obj_num, 0))

            start_offset = len(object_string)

            if entry is None:
                new_obj_num = self.pdf.objects.add(writing_object).object_number

                # guarantee that the pdf processor doesn't write a new object
                # but rather uses the one from the object stream
                self.pdf.xref[(new_obj_num, 0)] = CompressedXRefEntry(
                    self.stream_objnum, start_offset
                )
            else:
                new_obj_num = obj_num

            object_string += serialize(writing_object) + b" "

            indices.append((new_obj_num, start_offset))

        index_string = b""
        for obj_num, rel_offset in indices:
            index_string += f"{obj_num} {rel_offset}".encode() + b" "

        objstm_data = self.stream.details | PdfDictionary(
            Type=PdfName(b"ObjStm"),
            N=len(indices),
            First=len(index_string),
            Length=0,  # to be filled in
        )

        return PdfStream.create(index_string + object_string, cast(PdfDictionary, objstm_data))


class ObjectMap(UserDict[int, MapObject]):
    """A mapping of object numbers to either object references, in-use objects or free objects.

    Object references included in :attr:`.ObjectMap.unresolved` are items that have not been
    requested yet. Once an object is requested, it is removed from the unresolved set and
    added to the map as is.

    Free objects are indicated with the :class:`.FreeObject` class.
    """

    def __init__(self, pdf: PdfParser) -> None:
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

    def add(self, pdf_object: PdfObject | PdfStream) -> PdfReference[PdfObject | PdfStream]:
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


class PdfParser:
    """A parser that can completely parse a PDF document.

    It consumes the PDF's cross-reference tables and trailers. It merges the tables
    into a single one and provides an interface to individually parse each indirect
    object using :class:`~pdfnaut.cos.tokenizer.PdfTokenizer`.

    Arguments:
        data (bytes):
            The document to be processed.

        strict (bool, optional, keyword only):
            Whether to warn or fail on issues caused by non-spec-compliance.
            Defaults to False.
    """

    def __init__(self, data: bytes, *, strict: bool = False) -> None:
        self.strict = strict
        self._tokenizer = PdfTokenizer(data)
        self._tokenizer.resolver = self.get_object

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
        
        For details on the contents of the trailer, see § 7.5.5 File Trailer.
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

    def _tok_matches_object_header(self) -> re.Match[bytes] | None:
        if not self._tokenizer.peek().isdigit():
            return

        return re.match(INDIRECT_OBJ_HEADER_REGEX, self._tokenizer.peek_line())

    def parse(self, start_xref: int | None = None) -> None:
        """Parses the entire document.

        It begins by parsing the most recent XRef table and trailer. If this trailer
        points to a previous XRef, this function is called again with a ``start_xref``
        offset until no more XRefs are found.

        It also sets up the Standard security handler for use in case the document
        is encrypted.

        Arguments:
            start_xref (int, optional):
                The offset where the most recent XRef can be found. If no offset is
                provided, this function will attempt to locate one.
        """
        # Move to the header
        self._tokenizer.position = 0
        self.header_version = self.parse_header()

        # Because the function may be called recursively, we check if this is the first call.
        if start_xref is None:
            start_xref = self.lookup_xref_start()

        # Move to the offset where the XRef and trailer are
        self._tokenizer.position = start_xref
        section = self.parse_xref_and_trailer()

        self.updates.append(section)

        if "Prev" in section.trailer:
            # More XRefs were found. Recurse!
            self._tokenizer.position = 0
            self.parse(cast(int, section.trailer["Prev"]))
        else:
            # That's it. Merge them together.
            self.xref = self.get_merged_xrefs()
            self.trailer = self.updates[0].trailer

        # Fills the object store so we can refer to objects now!
        self.objects.fill()

        # Is the document encrypted with a standard security handler?
        if "Encrypt" in self.trailer:
            assert "ID" in self.trailer
            encryption = cast(PdfDictionary, self.trailer["Encrypt"])

            if cast(PdfName, encryption["Filter"]).value == b"Standard":
                self.security_handler = StandardSecurityHandler(
                    encryption, cast("list[PdfHexString | bytes]", self.trailer["ID"])
                )

    def parse_header(self) -> str:
        """Parses the %PDF-n.m header that is expected to be at the start of a PDF file."""
        header = self._tokenizer.parse_comment()
        pattern = re.compile(PDF_HEADER_REGEX)
        if mat := pattern.match(header.value):
            return f"{mat.group('major').decode()}.{mat.group('minor').decode()}"

        # Although not recommended, it is possible that some documents may start with
        # characters different than those of %PDF-n.m. Offsets should be calculated
        # based on the start of this token rather than the start of the document.
        if not self.strict:
            if mat := pattern.search(self._tokenizer.data):
                if self._tokenizer.data[mat.start() - 1] == 37:  # %
                    self._tokenizer.data = self._tokenizer.data[mat.start() - 1 :]
                    return f"{mat.group('major').decode()}.{mat.group('minor').decode()}"

        raise PdfParseError("Expected PDF header at start of file.")

    def build_xref_map(
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
                    # compressed entries are assumed 0
                    gen = 0

                entry_map[(idx, gen)] = entry

        return entry_map

    def get_merged_xrefs(self) -> dict[tuple[int, int], PdfXRefEntry]:
        """Combines all XRef updates in the document into a cross-reference mapping
        that includes all entries."""
        entry_map: dict[tuple[int, int], PdfXRefEntry] = {}
        hybrid_objnums = []

        # from least recent to most recent
        for section in self.updates[::-1]:
            update_map = self.build_xref_map(section.subsections)

            # if the document is a hybrid-reference file, append any hidden objects.
            if "XRefStm" in section.trailer:
                self._tokenizer.position = cast(int, section.trailer["XRefStm"])

                xrefstm = self.parse_compressed_xref()
                hybrid_map = self.build_xref_map(xrefstm.subsections)

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

    def lookup_xref_start(self) -> int:
        """Scans through the PDF until it finds the XRef offset then returns it."""
        contents = bytearray()

        # The PDF spec tells us we need to parse from the end of the file
        # and the XRef comes first
        self._tokenizer.position = len(self._tokenizer.data) - 1

        while self._tokenizer.position > 0:
            contents.insert(0, ord(self._tokenizer.peek()))
            if contents.startswith(b"startxref"):
                break
            self._tokenizer.position -= 1

        if not contents.startswith(b"startxref"):
            raise PdfParseError("Cannot locate XRef table. 'startxref' offset missing.")

        # advance to the startxref offset, we know it's there.
        self._tokenizer.skip(9)
        self._tokenizer.skip_whitespace()

        return int(self._tokenizer.parse_numeric())  # startxref

    def parse_xref_and_trailer(self) -> PdfXRefSection:
        """Parses both the cross-reference table and the PDF trailer.

        PDFs may include a typical uncompressed XRef table (and hence separate XRefs and
        trailers) or an XRef stream that combines both.
        """
        if self._tokenizer.matches(b"xref"):
            xref = self.parse_simple_xref()
            self._tokenizer.skip_whitespace()
            trailer = self.parse_simple_trailer()

            return PdfXRefSection(xref, trailer)
        elif self._tok_matches_object_header():
            return self.parse_compressed_xref()
        elif not self.strict:
            # let's attempt to locate a nearby xref table
            target = self._tokenizer.position
            table_offsets = self._find_xref_offsets()

            # get the xref table nearest to our offset
            self._tokenizer.position = get_closest(table_offsets, target)
            section = self.parse_xref_and_trailer()

            # make sure the user can see our corrections
            if "Prev" in section.trailer:
                section.trailer["Prev"] = get_closest(
                    table_offsets, cast(int, section.trailer["Prev"])
                )

            return section
        else:
            raise PdfParseError("XRef offset does not point to XRef section.")

    def _find_xref_offsets(self) -> list[int]:
        table_offsets = []

        # looks for the start of a xref table
        for mat in re.finditer(rb"(?<!start)xref(\W*)(\d+) (\d+)", self._tokenizer.data):
            table_offsets.append(mat.start())

        # looks for indirect objects, then checks if they are xref streams
        for mat in re.finditer(INDIRECT_OBJ_HEADER_REGEX, self._tokenizer.data):
            self._tokenizer.position = mat.start()
            self._tokenizer.skip(mat.end() - mat.start())
            self._tokenizer.skip_whitespace()

            if self._tokenizer.matches(b"<<"):
                mapping = self._tokenizer.parse_dictionary()
                if isinstance(typ := mapping.get("Type"), PdfName) and typ.value == b"XRef":
                    table_offsets.append(mat.start())

        return sorted(table_offsets)

    def parse_simple_trailer(self) -> PdfDictionary:
        """Parses the PDF's standard trailer which is used to quickly locate other
        cross reference tables and special objects.

        The trailer is separate if the XRef table is standard (uncompressed).
        Otherwise it is part of the XRef object.
        """
        self._tokenizer.skip(7)  # past the 'trailer' keyword
        self._tokenizer.skip_whitespace()

        # next token is a dictionary
        return self._tokenizer.parse_dictionary()

    def parse_simple_xref(self) -> list[PdfXRefSubsection]:
        """Parses a standard, uncompressed XRef table of the format described in
        § 7.5.4 Cross-Reference Table.

        If ``startxref`` points to an XRef object, :meth:`.parse_compressed_xref`
        should be called instead.
        """
        self._tokenizer.skip(4)
        self._tokenizer.skip_whitespace()

        subsections = []

        while not self._tokenizer.done:
            # subsection
            subsection = re.match(
                rb"(?P<first_obj>\d+)\s(?P<count>\d+)", self._tokenizer.peek_line()
            )
            if subsection is None:
                break

            self._tokenizer.skip(subsection.end())
            self._tokenizer.skip_whitespace()

            # xref entries
            entries: list[PdfXRefEntry] = []
            for idx in range(int(subsection.group("count"))):
                entry = re.match(
                    rb"(?P<offset>\d{10}) (?P<gen>\d{5}) (?P<status>f|n)",
                    self._tokenizer.peek(20),
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
                self._tokenizer.skip(entry.end())
                self._tokenizer.skip_whitespace()

            subsections.append(
                PdfXRefSubsection(
                    int(subsection.group("first_obj")),
                    int(subsection.group("count")),
                    entries,
                )
            )

        return subsections

    def parse_compressed_xref(self) -> PdfXRefSection:
        """Parses a compressed cross-reference stream which includes both the XRef table
        and information from the PDF trailer.

        As described in § 7.5.8 Cross-Reference Streams.
        """
        xref_stream = self.parse_indirect_object(InUseXRefEntry(self._tokenizer.position, 0), None)
        assert isinstance(xref_stream, PdfStream)

        contents = BytesIO(xref_stream.decode())

        xref_widths = cast(PdfArray[int], xref_stream.details["W"])
        xref_indices = cast(
            PdfArray[int],
            xref_stream.details.get("Index", PdfArray([0, xref_stream.details["Size"]])),
        )

        subsections = []

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

                # TODO: Warn of unknown field types once we have a logging facility
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

            subsections.append(subsection)

        return PdfXRefSection(subsections, xref_stream.details)

    def parse_indirect_object(
        self, xref_entry: InUseXRefEntry, reference: PdfReference | None
    ) -> PdfObject | PdfStream:
        """Parses an indirect object not within an object stream, or basically, an object
        that is directly referred to by an ``xref_entry`` and a ``reference``"""
        self._tokenizer.position = xref_entry.offset
        self._tokenizer.skip_whitespace()

        mat = self._tok_matches_object_header()
        if not mat:
            raise PdfParseError("XRef entry does not point to indirect object.")

        self._tokenizer.skip(mat.end())
        self._tokenizer.skip_whitespace()

        contents = self._tokenizer.get_next_token()
        self._tokenizer.skip_whitespace()

        # uh oh, a stream?
        if self._tokenizer.matches(b"stream"):
            extent = cast(PdfDictionary, contents)

            # the implicit get_object call might move us around so we must save and then
            # restore the previous position
            _current = self._tokenizer.position
            length = extent["Length"]
            self._tokenizer.position = _current

            if not isinstance(length, int):
                raise PdfParseError("\\Length entry of stream extent not an integer")

            item = PdfStream(extent, self.parse_stream(xref_entry, length))
        else:
            item = cast(PdfObject, contents)

        return self._get_decrypted(item, reference)

    @overload
    def _get_decrypted(
        self, pdf_object: PdfObject, reference: PdfReference | None
    ) -> PdfObject: ...

    @overload
    def _get_decrypted(
        self, pdf_object: PdfStream, reference: PdfReference | None
    ) -> PdfStream: ...

    def _get_decrypted(
        self, pdf_object: PdfObject | PdfStream, reference: PdfReference | None
    ) -> PdfObject | PdfStream:
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
                        pdf_object._crypt_params = {
                            "Handler": self.security_handler,
                            "EncryptionKey": self._encryption_key,
                            "Reference": reference,
                        }
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
            return PdfArray((self._get_decrypted(obj, reference) for obj in pdf_object.data))
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

    def parse_stream(self, xref_entry: InUseXRefEntry, extent: int) -> bytes:
        """Parses the contents of a PDF stream at ``xref_entry``.

        ``extent`` specifies the amount of bytes the stream is expected to have.
        """

        self._tokenizer.skip(6)  # past the 'stream' keyword
        self._tokenizer.skip_next_eol(no_cr=True)

        contents = self._tokenizer.consume(extent)
        self._tokenizer.skip_next_eol(no_cr=True)

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
            if self._tokenizer.position >= next(next_entry_at).offset:
                raise PdfParseError("\\Length key in stream extent parses beyond object.")
        except StopIteration:
            pass

        self._tokenizer.skip_whitespace()
        # Are we done?
        if not self._tokenizer.skip_if_matches(b"endstream"):
            raise PdfParseError("\\Length key in stream extent does not match end of stream.")

        return contents

    T = TypeVar("T")

    @overload
    def get_object(self, reference: PdfReference[T], cache: bool = True) -> T: ...

    @overload
    def get_object(
        self, reference: tuple[int, int], cache: bool = True
    ) -> PdfObject | PdfStream | PdfNull | FreeObject: ...

    def get_object(
        self, reference: PdfReference | tuple[int, int], cache: bool = True
    ) -> PdfObject | PdfStream | PdfNull | FreeObject | Any:
        """Resolves a reference into the indirect object it points to.

        Arguments:
            reference (:class:`.PdfReference` | :class:`tuple[int, int]`):
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
            return self.objects.get(reference.object_number)

        root_entry = self.xref.get((reference.object_number, reference.generation))

        if root_entry is None:
            # the reference is referring to a new object not registered in the xref table
            if (obj_entry := self.objects.get(reference.object_number)) is not None:
                self._hot_references.remove(reference)
                return obj_entry

            return PdfNull()

        if isinstance(root_entry, InUseXRefEntry):
            obj = self.parse_indirect_object(root_entry, reference)

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
                objstm = self.parse_indirect_object(
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

        Returns:
            A :class:`.PermsAcquired` value specifying the permissions acquired by ``password``.

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
            return PermsAcquired.OWNER

        # Is this the user password?
        encryption_key, is_user_pass = self.security_handler.authenticate_user_password(
            password.encode()
        )
        if is_user_pass:
            self._encryption_key = encryption_key
            return PermsAcquired.USER

        return PermsAcquired.NONE

    def save(self, filepath: str | Path | BinaryIO | BufferedIOBase) -> None:
        """Saves the contents of this parser to ``filepath``.

        ``filepath`` may either be a string containing a path, a :class:`pathlib.Path`
        instance, a binary stream (i.e. :class:`io.BufferedIOBase`), or a file-like object
        (i.e. :class:`typing.BinaryIO`).
        """

        builder = PdfSerializer()
        builder.write_header("2.0")

        rows: list[tuple[int, PdfXRefEntry]] = []

        use_compressed = False
        update_freelist = False

        for obj_num in self.objects:
            ref_tup = self.objects.initial_reference_map.get(obj_num)
            # Object is new
            if ref_tup is None:
                resolved = self._objstm_cache.get(obj_num, self.objects[obj_num])
                if isinstance(resolved, ObjectStream):
                    resolved = resolved.to_stream()

                if isinstance(resolved, FreeObject):
                    rows.append((obj_num, FreeXRefEntry(-1, 0)))
                    update_freelist = True
                else:
                    offset = builder.write_object((obj_num, 0), resolved)
                    rows.append((obj_num, InUseXRefEntry(offset, 0)))

                continue

            # Object is modified or left intact
            entry = self.xref[ref_tup]
            if isinstance(entry, FreeXRefEntry):
                resolved = self._objstm_cache.get(obj_num, self.objects[obj_num])
                if isinstance(resolved, ObjectStream):
                    resolved = resolved.to_stream()

                # Free entry left unmodified or can no longer be used
                if isinstance(resolved, FreeObject) or entry.gen_if_used_again >= 65535:
                    rows.append(
                        (
                            obj_num,
                            FreeXRefEntry(entry.next_free_object, entry.gen_if_used_again),
                        )
                    )
                    continue

                # Free entry now in use
                offset = builder.write_object((obj_num, entry.gen_if_used_again), resolved)
                rows.append((obj_num, InUseXRefEntry(offset, entry.gen_if_used_again)))
                update_freelist = True
            elif isinstance(entry, InUseXRefEntry):
                resolved = self._objstm_cache.get(obj_num, self.objects[obj_num])
                if isinstance(resolved, ObjectStream):
                    resolved = resolved.to_stream()

                # In use object freed
                if isinstance(resolved, FreeObject):
                    rows.append((obj_num, FreeXRefEntry(-1, entry.generation + 1)))
                    update_freelist = True
                    continue

                # In use object either modified or left intact
                offset = builder.write_object(ref_tup, resolved)
                rows.append((obj_num, InUseXRefEntry(offset, entry.generation)))
            elif isinstance(entry, CompressedXRefEntry):
                use_compressed = True
                rows.append(
                    (
                        obj_num,
                        CompressedXRefEntry(entry.objstm_number, entry.index_within),
                    )
                )

        if update_freelist:
            # let's first get the members of the freelist
            freelist_members = [
                idx for idx, (_, entry) in enumerate(rows) if isinstance(entry, FreeXRefEntry)
            ]

            for freelist_idx, xref_idx in enumerate(freelist_members):
                obj_num, entry = rows[xref_idx]
                assert isinstance(entry, FreeXRefEntry)

                if freelist_idx + 1 < len(freelist_members):
                    entry.next_free_object = rows[freelist_members[freelist_idx + 1]][0]
                else:
                    entry.next_free_object = 0

                rows[xref_idx] = (obj_num, entry)

        xref_section = builder.generate_xref_section(rows)

        new_trailer = PdfDictionary(
            {
                "Size": len(self.build_xref_map(xref_section)),
                "Root": self.trailer.data["Root"],
            }
        )

        if "Info" in self.trailer.data:
            new_trailer.data["Info"] = self.trailer.data["Info"]

        if isinstance(filepath, BinaryIO):
            filename = filepath.name
        elif isinstance(filepath, BufferedIOBase):
            filename = ""  # no filename
        else:
            filename = str(filepath)

        if "ID" in self.trailer.data:
            ids = cast(PdfArray["PdfHexString | bytes"], self.trailer.data["ID"])

            new_trailer.data["ID"] = PdfArray(
                [ids[0], generate_file_id(filename, len(builder.content))]
            )
        else:
            new_id = generate_file_id(filename, len(builder.content))
            new_trailer.data["ID"] = PdfArray([new_id, new_id])

        if use_compressed:
            startxref = builder.write_compressed_xref_section(
                PdfXRefSection(xref_section, new_trailer)
            )
            builder.write_trailer(None, startxref)
        else:
            startxref = builder.write_standard_xref_section(xref_section)
            builder.write_trailer(new_trailer, startxref)

        builder.write_eof()

        if isinstance(filepath, (BufferedIOBase, BinaryIO)):
            filepath.write(builder.content)
        else:
            with open(filepath, "wb") as output_fp:
                output_fp.write(builder.content)
