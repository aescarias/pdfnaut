from __future__ import annotations

from typing import TypedDict, TYPE_CHECKING

from pdfnaut.objects import PdfName, PdfHexString

if TYPE_CHECKING:
    from typing_extensions import Required


class Encrypt(TypedDict, total=False):
    Filter: Required[PdfName]
    """The name of the preferred security handler for this document, which shall be 
    used to encrypt the document. If SubFilter is absent, this shall be the only handler
    used when opening the document."""
    SubFilter: PdfName
    """A name completely specifying the format and interpretation of the contents of 
    this dictionary. It allows security handlers other than the one set in Filter to 
    decrypt the document."""
    V: int
    """The algorithm to use when encrypting/decrypting the document.
    
    0 - An undocumented algorithm (default; shall never occur).
    1 - Encryption of data using AES or RC4 with a key length of 40 bits.
    2 - Encryption of data using AES or RC4 with a key length greater than 40 bits.
    3 - An unpublished algorithm allowing key lengths between 40 and 128 bits. Shall never occur.
    4 - The security handler defines what algorithms it uses.
    """
    Length: int
    """The length of the encryption key in bits. It shall be a multiple of 8."""
    CF: dict[str, EncrCryptFilter]
    """(if V=4) A mapping of crypt filter names to dictionaries."""
    StmF: PdfName
    """(if V=4) The crypt filter to use when decrypting streams."""
    StrF: PdfName
    """(If V=4) The crypt filter to use when decrypting strings."""
    EFF: PdfName
    """(If V=4) The crypt filter to use when decrypting embedded file streams."""


class EncrCryptFilter(TypedDict, total=False):
    Type: PdfName
    """Shall be 'CryptFilter'."""
    CFM: PdfName
    """The method used, if any, to decrypt data.
    
    - None: The application shall not decrypt data.
    - V2: The application shall ask for an encryption key then decrypt the data using ARC4.
    - AESV2: The application shall ask for an encryption key then decrypt the data using 
    AES128 in CBC mode. """
    AuthEvent: PdfName
    """The event that triggers a request for authentication."""
    Length: int
    """The bit length of the encryption key. It shall be a multiple of 8."""


class StandardEncrypt(Encrypt, total=False):
    R: Required[int]
    """The Revision of the Standard security handler that shall be used (2, 3, or 4)."""
    O: Required[bytes | PdfHexString]
    """A 32-byte string, based on both the owner and user passwords, that shall be used in 
    computing the encryption key and in determining whether a valid Owner password was entered."""
    U: Required[bytes | PdfHexString]
    """A 32-byte string, based on the User password, that shall be used in determining whether 
    to prompt the user for a password and, if so, whether a valid user or owner password was 
    entered."""
    P: Required[int]
    """A set of flags indicating which operations are permitted on the document. """
    EncryptMetadata: bool    
    """Indicates whether the document-level metadata stream shall be encrypted."""
