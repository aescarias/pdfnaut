# Unit tests for PDF encryption routines and the Standard security handler
from __future__ import annotations

from typing import cast

from pdfnaut.cos.objects.base import PdfHexString, PdfReference, into_bytes
from pdfnaut.cos.objects.containers import PdfDictionary
from pdfnaut.cos.reader import PdfReader, PermsAcquired


def test_std_security_handler():
    with PdfReader("tests/docs/sample.pdf") as reader:
        # This document is not encrypted
        assert reader.security_handler is None
        # Unencrypted documents should return OWNER
        assert reader.decrypt("beepboop") is PermsAcquired.OWNER

    with PdfReader("tests/docs/encrypted-arc4.pdf") as reader:
        # This document is encrypted
        assert reader.security_handler is not None
        # with the user password 'nil'
        assert reader.decrypt("nil") is PermsAcquired.USER
        # with the owner password 'null'
        assert reader.decrypt("null") is PermsAcquired.OWNER
        # but not 'some'
        assert reader.decrypt("some") is PermsAcquired.NONE


def test_rc4_aes_decryption():
    # TODO: A stream check wouldn't hurt?
    # TODO: Some files have different StmF and StrF filters
    with PdfReader("tests/docs/encrypted-arc4.pdf") as reader:
        assert reader.decrypt("null")

        info = cast(PdfDictionary, reader.trailer["Info"])
        producer = cast("PdfHexString | bytes", info["Producer"])

        assert into_bytes(producer) == b"pypdf"

    with PdfReader("tests/docs/encrypted-aes128.pdf") as reader:
        assert reader.decrypt("nil")

        info = cast(PdfDictionary, reader.trailer["Info"])
        producer = cast("PdfHexString | bytes", info["Producer"])

        assert into_bytes(producer) == b"pypdf"


def test_rc4_aes_password_values():
    with PdfReader("tests/docs/encrypted-arc4.pdf") as reader:
        encr_metadata = cast(PdfDictionary, reader.trailer["Info"])

        encrypt_dict = cast(PdfDictionary, reader.trailer["Encrypt"])
        assert reader.security_handler is not None

        # Passwords
        o_value = reader.security_handler.compute_owner_password(b"null", b"nil")
        assert o_value.hex().lower().encode() == cast(PdfHexString, encrypt_dict["O"]).raw.lower()

        u_value = reader.security_handler.compute_user_password(b"nil")
        assert u_value.hex().lower().encode() == cast(PdfHexString, encrypt_dict["U"]).raw.lower()

        # Encryption with passwords
        encr_key = reader.security_handler.compute_encryption_key(b"nil")

        assert cast(
            PdfHexString, encr_metadata["Producer"]
        ).value == reader.security_handler.encrypt_object(
            encr_key, b"pypdf", cast(PdfReference, reader.trailer.data["Info"])
        )
