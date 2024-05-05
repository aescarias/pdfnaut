from __future__ import annotations

import re
from typing import Any, cast, TypeVar, overload
from enum import IntEnum
from io import BytesIO

from ..objects.base import PdfNull, PdfIndirectRef, PdfObject, PdfName, PdfHexString
from ..objects.stream import PdfStream
from ..objects.xref import (
    PdfXRefEntry, PdfXRefSubsection, PdfXRefTable, 
    FreeXRefEntry, InUseXRefEntry, CompressedXRefEntry
)
from ..exceptions import PdfParseError
from ..security_handler import StandardSecurityHandler
from .simple import PdfTokenizer


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
    object using :class:`~pdfnaut.parsers.simple.PdfTokenizer`."""

    def __init__(self, data: bytes) -> None:
        self._tokenizer = PdfTokenizer(data)

        self.updates: list[tuple[PdfXRefTable, dict[str, Any]]] = []
        """A list of all incremental updates present in the document. The items are two-element 
        tuples: first, the XRef table; second, the trailer. (most recent/last update first)"""

        self.trailer: dict[str, Any] = {}
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
            encryption = cast("dict[str, Any]", 
                self.resolve_reference(_E) if isinstance((_E := self.trailer["Encrypt"]), PdfIndirectRef) else _E)
            
            if encryption["Filter"].value == b"Standard":
                self.security_handler = StandardSecurityHandler(encryption, self.trailer["ID"])

    def parse_header(self) -> str:
        """Parses the %PDF-n.m header that is expected to be at the start of a PDF file."""
        header = self._tokenizer.parse_comment()
        mat = re.match(rb"PDF-(?P<major>\d+).(?P<minor>\d+)", header.value)
        if mat:
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
            contents.insert(0, ord(self._tokenizer.current))
            if contents.startswith(b"startxref"):
                break
            self._tokenizer.position -= 1
        
        if not contents.startswith(b"startxref"):
            raise PdfParseError("Cannot locate XRef table. 'startxref' offset missing.")
        
        # advance to the startxref offset, we know it's there.
        self._tokenizer.advance(9)
        self._tokenizer.advance_whitespace()

        return int(self._tokenizer.parse_numeric()) # startxref

    def parse_xref_and_trailer(self) -> tuple[PdfXRefTable, dict[str, Any]]:
        """Parses both the cross-reference table and the PDF trailer.
        
        PDFs may include a typical uncompressed XRef table (and hence separate XRefs and
        trailers) or an XRef stream that combines both.
        """
        if self._tokenizer.current + self._tokenizer.peek(3) == b"xref":
            xref = self.parse_simple_xref()
            self._tokenizer.advance_whitespace()
            trailer = self.parse_simple_trailer()
            return xref, trailer
        elif re.match(rb"(?P<num>\d+)\s+(?P<gen>\d+)\s+obj", self._tokenizer.current_to_eol):
            return self.parse_compressed_xref()
        else:
            raise PdfParseError("XRef offset does not point to XRef table.")
        
    def parse_simple_trailer(self) -> dict[str, Any]:
        """Parses the PDF's standard trailer which is used to quickly locate other 
        cross reference tables and special objects.
        
        The trailer is separate if the XRef table is standard (uncompressed).
        Otherwise it is part of the XRef object."""
        self._tokenizer.advance(7) # past the 'trailer' keyword
        self._tokenizer.advance_whitespace()
        
        # next token is a dictionary
        trailer = self._tokenizer.parse_dictionary()
        return trailer

    def parse_simple_xref(self) -> PdfXRefTable:
        """Parses a standard, uncompressed XRef table of the format described in 
        ``§ 7.5.4 Cross-Reference Table`` in the PDF spec.

        If ``startxref`` points to an XRef object, :meth:`.parse_compressed_xref`
        should be called instead.
        """
        self._tokenizer.advance(4)
        self._tokenizer.advance_whitespace()

        table = PdfXRefTable([])

        while not self._tokenizer.at_end():
            # subsection
            subsection = re.match(rb"(?P<first_obj>\d+)\s(?P<count>\d+)", 
                                self._tokenizer.current_to_eol)
            if subsection is None:
                break
            self._tokenizer.advance(subsection.end())
            self._tokenizer.advance_whitespace()

            # xref entries
            entries: list[PdfXRefEntry] = []
            for i in range(int(subsection.group("count"))):
                entry = re.match(rb"(?P<offset>\d{10}) (?P<gen>\d{5}) (?P<status>f|n)", 
                    self._tokenizer.current + self._tokenizer.peek(19))
                if entry is None:
                    raise PdfParseError(f"Expected valid XRef entry at row {i + 1}")
                
                offset = int(entry.group("offset"))
                generation = int(entry.group("gen"))

                if entry.group("status") == b"n":
                    entries.append(InUseXRefEntry(offset, generation))
                else:
                    entries.append(FreeXRefEntry(offset, generation))

                self._tokenizer.advance(20)
            
            table.sections.append(PdfXRefSubsection(
                int(subsection.group("first_obj")),
                int(subsection.group("count")),
                entries
            ))
            
        return table

    def parse_compressed_xref(self) -> tuple[PdfXRefTable, dict[str, Any]]:
        """Parses a compressed cross-reference stream which includes both the XRef table 
        and information from the PDF trailer. 
        
        Described in ``§ 7.5.4 Cross-Reference Streams``."""
        xref_stream = self.parse_indirect_object(
            InUseXRefEntry(self._tokenizer.position, 0))
        assert isinstance(xref_stream, PdfStream)

        contents = BytesIO(xref_stream.decompress())

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

        return table, xref_stream.details

    def parse_indirect_object(self, xref_entry: InUseXRefEntry) -> PdfObject | PdfStream:
        """Parses an indirect object not within an object stream, or basically, an object 
        that is directly referred to by an ``xref_entry``"""
        self._tokenizer.position = xref_entry.offset
        self._tokenizer.advance_whitespace()
        mat = re.match(rb"(?P<num>\d+)\s+(?P<gen>\d+)\s+obj", 
                       self._tokenizer.current_to_eol)
        if not mat:
            raise PdfParseError("XRef entry does not point to indirect object.")
        
        self._tokenizer.advance(mat.end())
        self._tokenizer.advance_whitespace()

        tok = self._tokenizer.next_token()
        self._tokenizer.advance_whitespace()

        try:
            indirect_ref = PdfIndirectRef(
                *list(self.xref.keys())[list(self.xref.values()).index(xref_entry)]
            )
        except ValueError:
            # The only way I know indirect_ref can be None is if we are parsing a compressed
            # XRef stream. XRef streams do not appear in the XRef and XRef streams cannot be 
            # encrypted so we do not need an indirect ref.
            indirect_ref = None

        # uh oh, a stream?
        if self._tokenizer.current + self._tokenizer.peek(5) == b"stream":   
            tok = cast("dict[str, Any]", tok)
            length = tok["Length"]
            if isinstance(length, PdfIndirectRef):
                _current = self._tokenizer.position
                length = self.resolve_reference(length)
                self._tokenizer.position = _current 
            if not isinstance(length, int):
                raise PdfParseError("\\Length entry of stream extent not an integer")

            stream = PdfStream(tok, self.parse_stream(xref_entry, length))
            if indirect_ref is None:
                return stream
            return self._get_decrypted(stream, indirect_ref)

        return self._get_decrypted(tok, indirect_ref) # type: ignore

    _WrapsEncryptable = TypeVar("_WrapsEncryptable", PdfObject, PdfStream)
    def _get_decrypted(self, pdf_object: _WrapsEncryptable, reference: PdfIndirectRef) -> _WrapsEncryptable:        
        if self.security_handler is None or not self._encryption_key:
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
                "Handler": self.security_handler,
                "EncryptionKey": self._encryption_key,
                "IndirectRef": reference
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
            if reference == self.trailer["Encrypt"]:
                return pdf_object
            return {name: self._get_decrypted(value, reference) for name, value in pdf_object.items()}         

        # Why would a number be encrypted?
        return pdf_object

    def parse_stream(self, xref_entry: InUseXRefEntry, extent: int) -> bytes:
        """Parses a PDF stream of length ``extent``"""
        self._tokenizer.advance(6) # past the 'stream' keyword

        # If the current character is LF or CRLF (but not just CR), skip.
        pos, eol = self._tokenizer.next_eol()
        if pos == self._tokenizer.position and eol != "\r":
            self._tokenizer.advance(len(eol))

        contents = self._tokenizer.data[self._tokenizer.position:
                                            self._tokenizer.position + extent]
        self._tokenizer.advance(len(contents))

        # Same check as earlier
        pos, eol = self._tokenizer.next_eol()
        if pos == self._tokenizer.position and eol != "\r":
            self._tokenizer.advance(len(eol))

        if self.xref:
            # As a bounds check, we get the offset of the entry directly following the current one.
            index_after = list(self.xref.values()).index(xref_entry)
            next_entry_hold = filter(
                lambda e: isinstance(e, InUseXRefEntry) and e.offset > xref_entry.offset, 
                list(self.xref.values())[index_after + 1:]
            )
        else:
            # The stream being parsed is (most likely) part of an XRef object
            next_entry_hold = iter([])

        # Check if we have consumed the appropriate bytes
        # Have we gone way beyond?
        try:
            if self._tokenizer.position >= next(next_entry_hold).offset:
                raise PdfParseError("\\Length key in stream extent parses beyond object.")
        except StopIteration:
            pass

        self._tokenizer.advance_whitespace()
        # Have we not reached the end?
        if not self._tokenizer.advance_if_next(b"endstream"):
            raise PdfParseError("\\Length key in stream extent does not match end of stream.")
        
        return contents

    T = TypeVar("T", PdfObject, PdfStream)
    @overload
    def resolve_reference(self, reference: PdfIndirectRef[T]) -> T:
        ...
    
    @overload
    def resolve_reference(self, reference: tuple[int, int]) -> PdfObject | PdfStream:
        ...
    
    def resolve_reference(self, reference: PdfIndirectRef | tuple[int, int]) -> PdfObject | PdfStream | PdfNull:
        """Resolves a reference into the indirect object it points to.
        
        Arguments:
            reference (:class:`.PdfIndirectRef` | tuple[int, int]): 
                An indirect reference object or a tuple of two integers representing, 
                in order, the object number and the generation number.
  
        Returns:
            A PDF object if the reference was found, otherwise :class:`.PdfNull`.
        """
        if isinstance(reference, tuple):
            root_entry = self.xref.get(reference)
        else:
            root_entry = self.xref.get((reference.object_number, reference.generation))
        
        if root_entry is None:
            return PdfNull()
        
        if isinstance(root_entry, InUseXRefEntry):
            return self.parse_indirect_object(root_entry)
        elif isinstance(root_entry, CompressedXRefEntry):
            # Get the object stream it's part of (gen always 0)
            objstm_entry = self.xref[(root_entry.objstm_number, 0)]
            assert isinstance(objstm_entry, InUseXRefEntry)
            objstm = self.parse_indirect_object(objstm_entry)
            assert isinstance(objstm, PdfStream)

            seq = PdfTokenizer(objstm.decompress()[objstm.details["First"]:] or b"")
            
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
