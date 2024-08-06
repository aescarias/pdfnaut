from __future__ import annotations

import re
from enum import IntEnum
from io import BytesIO
from typing import Any, TypeVar, cast, overload

from ..exceptions import PdfParseError
from ..cos.objects.base import PdfHexString, PdfIndirectRef, PdfName, PdfNull, PdfObject
from ..cos.objects.stream import PdfStream
from ..cos.objects.xref import (CompressedXRefEntry, FreeXRefEntry, InUseXRefEntry,
                                PdfXRefEntry, PdfXRefSubsection, PdfXRefTable)
from ..security.standard_handler import StandardSecurityHandler
from .tokenizer import PdfTokenizer
from ..typings.document import Trailer, XRefStream
from ..typings.encryption import StandardEncrypt


PDF_HEADER_REGEX = re.compile(rb"PDF-(?P<major>\d+).(?P<minor>\d+)")
INDIRECT_OBJ_HEADER_REGEX = re.compile(rb"(?P<num>\d+)\s+(?P<gen>\d+)\s+obj")

 
class PermsAcquired(IntEnum):
    NONE = 0
    """No permissions acquired, document is still encrypted."""
    USER = 1
    """User permissions within the limits specified by the security handler"""
    OWNER = 2
    """Owner permissions (all permissions)"""


class PdfParser:
    """A parser that can completely parse a PDF document.
    
    It consumes the PDF's cross-reference tables and trailers. It merges the tables
    into a single one and provides an interface to individually parse each indirect 
    object using :class:`~pdfnaut.cos.tokenizer.PdfTokenizer`.
    
    Arguments:
        data (bytes):
            The document to be processed.

    Keyword Arguments:
        strict (bool, optional):
            Whether to warn or fail at issues caused by non-spec-compliance.
            Defaults to False.
    """

    def __init__(self, data: bytes, *, strict: bool = False) -> None:
        self.strict = strict
        self._tokenizer = PdfTokenizer(data)

        self.updates: list[tuple[PdfXRefTable, Trailer | XRefStream]] = []
        """A list of all incremental updates present in the document. The items are two-element 
        tuples: first, the XRef table; second, the trailer. (most recent/last update first)"""

        # placeholder to make the type checker happy
        self.trailer: Trailer | XRefStream = { "Size": 0, "Root": PdfIndirectRef(0, 0) }
        """The most recent trailer in the PDF document.
        
        For details on the contents of the trailer, see ``§ 7.5.5 File Trailer`` in the PDF spec.
        """

        self.xref: dict[tuple[int, int], PdfXRefEntry] = {}
        """A cross-reference mapping combining the entries of all XRef tables present 
        in the document.
        
        The key is a tuple of two integers: object number and generation number. 
        The value is any of the 3 types of XRef entries (free, in use, compressed)
        """

        self.version = ""
        """The document's PDF version as seen in the header.
        
        To retrieve the PDF's version properly, access the Version entry part of the 
        document catalog. If not present, you can reliably depend on the header.
        """

        self.security_handler = None
        """The document's standard security handler, if any, as specified in the Encrypt 
        dictionary of the PDF trailer.

        This field being set indicates that a supported security handler was used for
        encryption. If not set, the parser will not attempt to decrypt this document.
        """

        self._encryption_key = None

    T = TypeVar("T")
    def _ensure_object(self, obj: PdfIndirectRef[T] | T) -> T:
        return self.get_object(obj) if isinstance(obj, PdfIndirectRef) else obj

    def _get_closest(self, values: list[int], target: int) -> int:
        return min(values, key=lambda offset: abs(offset - target))

    def _match_object_header(self) -> re.Match[bytes] | None:
        if not self._tokenizer.peek().isdigit():
            return
        
        return re.match(INDIRECT_OBJ_HEADER_REGEX, self._tokenizer.peek_line())
    
    def parse(self, start_xref: int | None = None) -> None:
        """Parses the entire document.
        
        It begins by parsing the most recent XRef table and trailer. If this trailer 
        points to a previous XRef, this function is called again with a ``start_xref``
        offset until no more XRefs are found.

        Arguments:
            start_xref (int, optional):
                The offset where the most recent XRef can be found.
        """
        # Move back for the header
        self._tokenizer.position = 0
        self.version = self.parse_header()

        # Because the function may be called recursively, we check if this is the first call.
        if start_xref is None:
            start_xref = self.lookup_xref_start()

        # Move to the offset where the XRef and trailer are
        self._tokenizer.position = start_xref
        xref, trailer = self.parse_xref_and_trailer()

        self.updates.append((xref, trailer))

        if "Prev" in trailer:
            # More XRefs were found. Recurse!
            self._tokenizer.position = 0
            self.parse(trailer["Prev"])
        else:
            # That's it. Merge them together.
            self.xref = self.get_merged_xrefs()
            self.trailer = self.updates[0][1]

        # Is the document encrypted with a standard security handler?
        if "Encrypt" in self.trailer:
            assert "ID" in self.trailer
            encryption = self._ensure_object(self.trailer["Encrypt"])

            if encryption["Filter"].value == b"Standard":
                self.security_handler = StandardSecurityHandler(
                    cast(StandardEncrypt, encryption), self.trailer["ID"])

    def parse_header(self) -> str:
        """Parses the %PDF-n.m header that is expected to be at the start of a PDF file."""
        header = self._tokenizer.parse_comment()
        if (mat := re.match(PDF_HEADER_REGEX, header.value)):
            return f"{mat.group('major').decode()}.{mat.group('minor').decode()}"

        raise PdfParseError("Expected PDF header at start of file.")
    
    def build_xref_map(self, xref: PdfXRefTable) -> dict[tuple[int, int], PdfXRefEntry]:
        """Creates a dictionary mapping references to XRef entries in the document."""
        entry_map: dict[tuple[int, int], PdfXRefEntry] = {}

        for section in xref.sections:
            for idx, entry in enumerate(section.entries, section.first_obj_number):
                if isinstance(entry, FreeXRefEntry):
                    gen = entry.gen_if_used_again
                elif isinstance(entry, InUseXRefEntry):
                    gen = entry.generation
                else:
                    gen = 0 # compressed entries

                entry_map[(idx, gen)] = entry

        return entry_map

    def get_merged_xrefs(self) -> dict[tuple[int, int], PdfXRefEntry]:
        """Combines all update XRef tables in the document into a cross-reference mapping
        that includes all entries."""
        entry_map: dict[tuple[int, int], PdfXRefEntry] = {}

        # from least recent to most recent
        for xref, _ in self.updates[::-1]:    
            entry_map.update(self.build_xref_map(xref))        

        return entry_map

    def lookup_xref_start(self) -> int:
        """Scans through the PDF until it finds the XRef offset then returns it"""
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

        return int(self._tokenizer.parse_numeric()) # startxref

    def parse_xref_and_trailer(self) -> tuple[PdfXRefTable, Trailer | XRefStream]:
        """Parses both the cross-reference table and the PDF trailer.
        
        PDFs may include a typical uncompressed XRef table (and hence separate XRefs and
        trailers) or an XRef stream that combines both.
        """
        if self._tokenizer.matches(b"xref"):
            xref = self.parse_simple_xref()
            self._tokenizer.skip_whitespace()
            trailer = self.parse_simple_trailer()
            return xref, trailer
        elif self._match_object_header():
            return self.parse_compressed_xref()
        elif not self.strict:
            # let's attempt to locate a nearby xref table
            target = self._tokenizer.position
            table_offsets = self._find_xref_offsets()

            # get the xref table nearest to our offset
            self._tokenizer.position = self._get_closest(table_offsets, target)
            xref, trailer = self.parse_xref_and_trailer()
            # make sure the user can see our corrections
            if "Prev" in trailer:
                trailer["Prev"] = self._get_closest(table_offsets, trailer["Prev"])
            return xref, trailer
        else:
            raise PdfParseError("XRef offset does not point to XRef table.")

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
        
    def parse_simple_trailer(self) -> Trailer:
        """Parses the PDF's standard trailer which is used to quickly locate other 
        cross reference tables and special objects.
        
        The trailer is separate if the XRef table is standard (uncompressed).
        Otherwise it is part of the XRef object."""
        self._tokenizer.skip(7) # past the 'trailer' keyword
        self._tokenizer.skip_whitespace()
        
        # next token is a dictionary
        trailer = cast(Trailer, self._tokenizer.parse_dictionary()) 
        return trailer

    def parse_simple_xref(self) -> PdfXRefTable:
        """Parses a standard, uncompressed XRef table of the format described in 
        ``§ 7.5.4 Cross-Reference Table``.

        If ``startxref`` points to an XRef object, :meth:`.parse_compressed_xref`
        should be called instead.
        """
        self._tokenizer.skip(4)
        self._tokenizer.skip_whitespace()

        table = PdfXRefTable([])

        while not self._tokenizer.done:
            # subsection
            subsection = re.match(rb"(?P<first_obj>\d+)\s(?P<count>\d+)", 
                                  self._tokenizer.peek_line())
            if subsection is None:
                break
            self._tokenizer.skip(subsection.end())
            self._tokenizer.skip_whitespace()

            # xref entries
            entries: list[PdfXRefEntry] = []
            for i in range(int(subsection.group("count"))):
                entry = re.match(rb"(?P<offset>\d{10}) (?P<gen>\d{5}) (?P<status>f|n)", 
                                 self._tokenizer.peek(20))
                if entry is None:
                    raise PdfParseError(f"Expected valid XRef entry at row {i + 1}")
                
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
            
            table.sections.append(PdfXRefSubsection(
                int(subsection.group("first_obj")),
                int(subsection.group("count")),
                entries
            ))
            
        return table

    def parse_compressed_xref(self) -> tuple[PdfXRefTable, XRefStream]:
        """Parses a compressed cross-reference stream which includes both the XRef table 
        and information from the PDF trailer. 
        
        Described in ``§ 7.5.4 Cross-Reference Streams``."""
        xref_stream = self.parse_indirect_object(
            InUseXRefEntry(self._tokenizer.position, 0), None)
        assert isinstance(xref_stream, PdfStream)

        contents = BytesIO(xref_stream.decode())

        xref_widths = xref_stream.details["W"]
        xref_indices = xref_stream.details.get("Index", [0, xref_stream.details["Size"]])

        table = PdfXRefTable([])

        for i in range(0, len(xref_indices), 2):
            section = PdfXRefSubsection(first_obj_number=xref_indices[i], 
                                        count=xref_indices[i + 1], 
                                        entries=[])
            
            for _ in range(section.count):
                field_type = int.from_bytes(contents.read(xref_widths[0]) or b'\x01')
                second = int.from_bytes(contents.read(xref_widths[1]))
                third = int.from_bytes(contents.read(xref_widths[2]))
                
                if field_type == 0:
                    section.entries.append(FreeXRefEntry(next_free_object=second, 
                                                         gen_if_used_again=third))
                elif field_type == 1:
                    section.entries.append(InUseXRefEntry(offset=second, generation=third))
                elif field_type == 2:
                    section.entries.append(CompressedXRefEntry(objstm_number=second, 
                                                               index_within=third))

            table.sections.append(section)

        return table, cast(XRefStream, xref_stream.details)

    def parse_indirect_object(self, xref_entry: InUseXRefEntry, 
                              reference: PdfIndirectRef | None) -> PdfObject | PdfStream:
        """Parses an indirect object not within an object stream, or basically, an object 
        that is directly referred to by an ``xref_entry`` and ``ref``"""
        self._tokenizer.position = xref_entry.offset
        self._tokenizer.skip_whitespace()

        mat = self._match_object_header()
        if not mat:
            raise PdfParseError("XRef entry does not point to indirect object.")
        self._tokenizer.skip(mat.end())
        self._tokenizer.skip_whitespace()

        contents = self._tokenizer.get_next_token()
        self._tokenizer.skip_whitespace()

        # uh oh, a stream?
        if self._tokenizer.matches(b"stream"):   
            extent = cast(dict[str, Any], contents)
            length = extent["Length"]
            if isinstance(length, PdfIndirectRef):
                _current = self._tokenizer.position
                length = self.get_object(length)
                self._tokenizer.position = _current 
            
            if not isinstance(length, int):
                raise PdfParseError("\\Length entry of stream extent not an integer")

            item = PdfStream(extent, self.parse_stream(xref_entry, length))
        else:
            item = contents

        return self._get_decrypted(item, reference) # type: ignore

    _WrapsEncryptable = TypeVar("_WrapsEncryptable", PdfObject, PdfStream)
    def _get_decrypted(self, pdf_object: _WrapsEncryptable, reference: PdfIndirectRef | None) -> _WrapsEncryptable:        
        if self.security_handler is None or not self._encryption_key or reference is None:
            return pdf_object

        if isinstance(pdf_object, PdfStream):
            use_stmf = True
            # Don't use StmF if the stream handles its own encryption
            if (filter_ := pdf_object.details.get("Filter")):
                if isinstance(filter_, PdfName) and filter_.value == b"Crypt":
                    use_stmf = False
                elif isinstance(filter_, list):
                    use_stmf = not any(isinstance(filt, PdfName) and filt.value == b"Crypt" 
                                        for filt in filter_)
            
            # Give the stream an instance of the security handler
            pdf_object._sec_handler = {
                "_Handler": self.security_handler,
                "_EncryptionKey": self._encryption_key,
                "_IndirectRef": reference
            }

            if use_stmf:
                pdf_object.raw = self.security_handler.decrypt_object(
                    self._encryption_key, pdf_object, reference)

            return pdf_object
        elif isinstance(pdf_object, PdfHexString):
            return PdfHexString.from_raw(
                self.security_handler.decrypt_object(
                    self._encryption_key, pdf_object.value, reference
                )
            )
        elif isinstance(pdf_object, bytes):
            return self.security_handler.decrypt_object(
                self._encryption_key, pdf_object, reference
            )
        elif isinstance(pdf_object, list):
            return [self._get_decrypted(obj, reference) for obj in pdf_object]
        elif isinstance(pdf_object, dict):
            # make a special exception if the dictionary is the Encrypt key in the trailer
            # we do not need to decrypt them
            if reference == self.trailer.get("Encrypt", {}):
                return pdf_object
            return {name: self._get_decrypted(value, reference) 
                    for name, value in pdf_object.items()}         

        # Why would a number be encrypted?
        return pdf_object

    def parse_stream(self, xref_entry: InUseXRefEntry, extent: int) -> bytes:
        """Parses a PDF stream of length ``extent``"""
        self._tokenizer.skip(6) # past the 'stream' keyword
        self._tokenizer.skip_next_eol(no_cr=True)
        
        contents = self._tokenizer.consume(extent)
        self._tokenizer.skip_next_eol(no_cr=True)

        if self.xref:
            # We get the offset of the entry directly following this one as a bounds check
            next_entry_at = iter(
                val for idx, val in enumerate(self.xref.values()) if 
                isinstance(val, InUseXRefEntry) and val.offset > xref_entry.offset
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
    def get_object(self, reference: PdfIndirectRef[T]) -> T:
        ...
    
    @overload
    def get_object(self, reference: tuple[int, int]) -> PdfObject | PdfStream | PdfNull:
        ...
    
    def get_object(self, reference: PdfIndirectRef | tuple[int, int]) -> PdfObject | PdfStream | PdfNull | Any:
        """Resolves a reference into the indirect object it points to.
        
        Arguments:
            reference (:class:`.PdfIndirectRef` | :class:`tuple[int, int]`): 
                A :class:`.PdfIndirectRef` object or a tuple of two integers representing, 
                in order, the object number and the generation number.
  
        Returns:
            The object the reference resolves to if valid, otherwise :class:`.PdfNull`.
        """
        if isinstance(reference, tuple):
            reference = PdfIndirectRef(*reference)

        root_entry = self.xref.get((reference.object_number, reference.generation))        
        if root_entry is None:
            return PdfNull()
        
        if isinstance(root_entry, InUseXRefEntry):
            return self.parse_indirect_object(root_entry, reference)
        elif isinstance(root_entry, CompressedXRefEntry):
            # Get the object stream it's part of (gen always 0)
            objstm_ref = (root_entry.objstm_number, 0)
            objstm_entry = self.xref[objstm_ref]
            assert isinstance(objstm_entry, InUseXRefEntry)

            objstm = self.parse_indirect_object(objstm_entry, PdfIndirectRef(*objstm_ref))
            assert isinstance(objstm, PdfStream)

            seq = PdfTokenizer(objstm.decode()[objstm.details["First"]:] or b"")
            
            for idx, token in enumerate(seq):
                if idx == root_entry.index_within:
                    return token
        
        return PdfNull()

    def decrypt(self, password: str) -> PermsAcquired:
        """Decrypts this document using the provided ``password``.

        The standard security handler may specify 2 passwords: an owner password and a user 
        password. The owner password would allow full access to the PDF and the user password 
        should allow access according to the permissions specified in the document.

        Returns:
            A :class:`.PermsAcquired` specifying the permissions acquired by ``password``.
            
            - If the document is not encrypted, defaults to :attr:`.PermsAcquired.OWNER`
            - if the document was not decrypted, defaults to :attr:`.PermsAcquired.NONE`
        """
        if self.security_handler is None:
            return PermsAcquired.OWNER
        
        # Is this the owner password?
        encryption_key, is_owner_pass = self.security_handler.authenticate_owner_password(password.encode())
        if is_owner_pass:
            self._encryption_key = encryption_key
            return PermsAcquired.OWNER
        
        # Is this the user password
        encryption_key, is_user_pass = self.security_handler.authenticate_user_password(password.encode())
        if is_user_pass:
            self._encryption_key = encryption_key
            return PermsAcquired.USER
        
        return PermsAcquired.NONE
