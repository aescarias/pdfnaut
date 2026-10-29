from __future__ import annotations

import hashlib
from datetime import time
from pathlib import Path
from typing import IO, cast

from ..cos.objects.base import PdfHexString, PdfName, PdfObject
from ..cos.objects.containers import PdfArray, PdfDictionary
from ..cos.objects.stream import PdfStream
from ..cos.objects.xref import (
    CompressedXRefEntry,
    FreeXRefEntry,
    InUseXRefEntry,
    PdfXRefEntry,
    PdfXRefSection,
)
from .reader import FreeObject, ObjectStream, PdfReader
from .serializer import PdfSerializer, serialize


def generate_file_id(filename: str, content_size: int) -> PdfHexString:
    """Generates a file identifier using the filename and content size,
    as discussed in ISO 32000-2:2020 § 14.4 "File identifiers"."""

    id_digest = hashlib.md5(time().isoformat("auto").encode())
    id_digest.update(filename.encode())
    id_digest.update(str(content_size).encode())
    return PdfHexString(id_digest.hexdigest().encode())


class PdfWriter:
    """The low-level PDF document writer, operating on the object store of a
    :class:`PdfReader` instance."""

    def __init__(self, pdf: PdfReader) -> None:
        """Initializes the PDF writer.

        Args:
            pdf: The PDF reader instance to write a document from.
        """
        self._pdf: PdfReader = pdf

    def _object_stream_to_stream(self, objstm: ObjectStream) -> PdfStream:
        """Serializes an object stream instance to a PDF stream."""

        object_string = bytearray()
        indices: list[tuple[int, int]] = []

        for idx in range(objstm._n_objects):
            cached = objstm.resolved_objects.get(idx)
            writing_object = cached if cached is not None else objstm.get_object(idx, cache=False)

            obj_num, _ = objstm.index_pairs[idx]
            entry = self._pdf.xref.get((obj_num, 0))
            start_offset = len(object_string)

            if entry is None:
                new_obj_num = self._pdf.objects.add(writing_object).object_number
                self._pdf.xref[(new_obj_num, 0)] = CompressedXRefEntry(
                    objstm.stream_objnum, start_offset
                )
            else:
                new_obj_num = obj_num

            object_string.extend(serialize(writing_object) + b" ")
            indices.append((new_obj_num, start_offset))

        index_string = bytearray()
        for obj_num, rel_offset in indices:
            index_string.extend(f"{obj_num} {rel_offset}".encode() + b" ")

        objstm_data = objstm.stream.details | PdfDictionary(
            Type=PdfName(b"ObjStm"),
            N=len(indices),
            First=len(index_string),
            Length=0,
        )

        return PdfStream.create(
            bytes(index_string + object_string), cast(PdfDictionary, objstm_data)
        )

    def _get_object_to_write(self, obj_num: int) -> PdfObject | FreeObject:
        resolved_from_map = self._pdf.objects[obj_num]
        if objstm := self._pdf._objstm_cache.get(obj_num):
            return self._object_stream_to_stream(objstm)

        return resolved_from_map

    def save(self, filepath: str | Path | IO[bytes]) -> None:
        """Saves the document to a path or binary stream."""
        builder = PdfSerializer()
        builder.write_header("2.0")

        rows: list[tuple[int, PdfXRefEntry]] = []
        use_compressed = False
        update_freelist = False

        for obj_num in self._pdf.objects:
            ref_tup = self._pdf.objects.initial_reference_map.get(obj_num)

            if ref_tup is None:
                resolved = self._get_object_to_write(obj_num)
                if isinstance(resolved, FreeObject):
                    rows.append((obj_num, FreeXRefEntry(-1, 0)))
                    update_freelist = True
                else:
                    offset = builder.write_object((obj_num, 0), resolved)
                    rows.append((obj_num, InUseXRefEntry(offset, 0)))
                continue

            entry = self._pdf.xref[ref_tup]
            if isinstance(entry, FreeXRefEntry):
                resolved = self._get_object_to_write(obj_num)

                if isinstance(resolved, FreeObject) or entry.gen_if_used_again >= 65535:
                    rows.append(
                        (
                            obj_num,
                            FreeXRefEntry(entry.next_free_object, entry.gen_if_used_again),
                        )
                    )
                    continue

                offset = builder.write_object((obj_num, entry.gen_if_used_again), resolved)
                rows.append((obj_num, InUseXRefEntry(offset, entry.gen_if_used_again)))
                update_freelist = True
            elif isinstance(entry, InUseXRefEntry):
                resolved = self._get_object_to_write(obj_num)

                if isinstance(resolved, FreeObject):
                    rows.append((obj_num, FreeXRefEntry(-1, entry.generation + 1)))
                    update_freelist = True
                    continue

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
                "Size": sum(subsection.count for subsection in xref_section),
                "Root": self._pdf.trailer.data["Root"],
            }
        )

        if "Info" in self._pdf.trailer.data:
            new_trailer.data["Info"] = self._pdf.trailer.data["Info"]

        if isinstance(filepath, Path):
            filename = str(filepath)
        elif isinstance(filepath, str):
            filename = filepath
        else:
            filename = getattr(filepath, "name", "")

        if "ID" in self._pdf.trailer.data:
            ids = cast(PdfArray[PdfHexString | bytes], self._pdf.trailer.data["ID"])
            new_trailer.data["ID"] = PdfArray(
                [ids[0], generate_file_id(filename, builder.content.tell())]
            )
        else:
            new_id = generate_file_id(filename, builder.content.tell())
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

        if isinstance(filepath, (str, Path)):
            with open(filepath, "wb") as output_fp:
                output_fp.write(builder.content.getbuffer())
        else:
            filepath.write(builder.content.getbuffer())
