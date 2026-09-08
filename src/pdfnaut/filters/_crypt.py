"""Implementation of the Crypt filter."""

from typing import TYPE_CHECKING, cast

from ..cos.objects import PdfDictionary, PdfName, PdfReference
from ._base import PdfFilter

if TYPE_CHECKING:
    from ..security.standard_handler import StandardSecurityHandler


# TODO: Please test
class CryptFetchFilter(PdfFilter):
    """Filter for encrypted streams (see ISO 32000-2:2020 § 7.4.10 "Crypt Filter").

    This filter takes two optional parameters: ``Type``, which defines the decode parameters
    as being for this filter; and ``Name``, which defines what filter should be used to
    decrypt the stream.

    This filter requires 3 additional parameters. These parameters are for use exclusively
    within the PDF processor and shall not be written to the document.

    - **Handler**: An instance of the security handler.
    - **EncryptionKey**: The encryption key generated from the security handler.
    - **Reference**: The indirect reference of the object to decrypt.
    """

    def encode(self, contents: bytes, *, params: PdfDictionary | None = None) -> bytes:  # pyright: ignore[reportIncompatibleMethodOverride]
        raise NotImplementedError("Crypt: Encrypting streams not implemented.")

    def decode(self, contents: bytes, *, params: PdfDictionary | None = None) -> bytes:  # pyright: ignore[reportIncompatibleMethodOverride]
        if params is None:
            raise ValueError("Crypt: This filter requires parameters.")

        cf_name = cast(PdfName, params.get("Name", PdfName(b"Identity")))
        if cf_name.value == b"Identity":
            return contents

        handler = cast("StandardSecurityHandler", params["Handler"])
        crypt_filter = cast(PdfDictionary, handler.encryption.get("CF", PdfDictionary())).get(
            cf_name.value.decode()
        )

        return handler.decrypt_object(
            cast(bytes, params["EncryptionKey"]),
            contents,
            cast(PdfReference, params.data["Reference"]),
            crypt_filter=cast("PdfDictionary | None", crypt_filter),
        )
