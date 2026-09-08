from ._ascii import ASCII85Filter, ASCIIHexFilter
from ._base import PdfFilter
from ._crypt import CryptFetchFilter
from ._flate import FlateFilter
from ._image import CCITTFaxFilter, DCTFilter, JBIG2Filter, JPXFilter
from ._rle import RunLengthFilter

SUPPORTED_FILTERS: dict[bytes, type[PdfFilter]] = {
    b"FlateDecode": FlateFilter,
    b"ASCII85Decode": ASCII85Filter,
    b"ASCIIHexDecode": ASCIIHexFilter,
    b"RunLengthDecode": RunLengthFilter,
    b"Crypt": CryptFetchFilter,
    b"CCITTFaxDecode": CCITTFaxFilter,
    b"DCTDecode": DCTFilter,
    b"JBIG2Decode": JBIG2Filter,
    b"JPXDecode": JPXFilter,
}
