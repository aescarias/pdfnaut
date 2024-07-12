# Unit tests for PDF encryption routines and the Standard security handler

from __future__ import annotations
from typing import cast, Any

from pdfnaut import PdfParser
from pdfnaut.cos.parser import PermsAcquired


def test_std_security_handler():
    with open("tests/docs/sample.pdf", "rb") as fp:
        parser = PdfParser(fp.read())
        parser.parse()

        # This document is not encrypted
        assert parser.security_handler is None
        # Unencrypted documents should return OWNER
        assert parser.decrypt("beepboop") is PermsAcquired.OWNER
    
    with open("tests/docs/encrypted-arc4.pdf", "rb") as fp:
        parser = PdfParser(fp.read())
        parser.parse()

        # This document is encrypted
        assert parser.security_handler is not None
        # with the user password 'nil'
        assert parser.decrypt("nil") is PermsAcquired.USER
        # with the owner password 'null'
        assert parser.decrypt("null") is PermsAcquired.OWNER
        # but not 'some'
        assert parser.decrypt("some") is PermsAcquired.NONE


def test_rc4_aes_decryption():
    # TODO: A stream check wouldn't hurt?
    # TODO: Some files have different StmF and StrF filters
    with open("tests/docs/encrypted-arc4.pdf", "rb") as fp:
        parser = PdfParser(fp.read())
        parser.parse()

        parser.decrypt("null")
        assert "Info" in parser.trailer
        metadata = cast("dict[str, Any]", parser.resolve_reference(parser.trailer["Info"]))
        assert metadata["Producer"].value == b"pypdf"

    with open("tests/docs/encrypted-aes128.pdf", "rb") as fp:
        parser = PdfParser(fp.read())
        parser.parse()

        parser.decrypt("nil")
        metadata = cast("dict[str, Any]", parser.resolve_reference(parser.trailer["Info"]))
        assert metadata["Producer"].value == b"pypdf"

def test_rc4_aes_password_values():
    with open("tests/docs/encrypted-arc4.pdf", "rb") as fp:
        parser = PdfParser(fp.read())
        parser.parse()

        encr_metadata = cast("dict[str, Any]", parser.resolve_reference(parser.trailer["Info"]))
        
        encrypt_dict = parser.resolve_reference(parser.trailer["Encrypt"])
        assert parser.security_handler is not None

        # Passwords
        o_value = parser.security_handler.compute_owner_password(b"null", b"nil")
        assert o_value.hex().lower().encode() == encrypt_dict["O"].raw.lower()

        u_value = parser.security_handler.compute_user_password(b"nil")
        assert u_value.hex().lower().encode() == encrypt_dict["U"].raw.lower()

        # Encryption with passwords
        encr_key = parser.security_handler.compute_encryption_key(b"nil")

        assert encr_metadata["Producer"].value == parser.security_handler.encrypt_object(
            encr_key, b"pypdf", parser.trailer["Info"]) 
