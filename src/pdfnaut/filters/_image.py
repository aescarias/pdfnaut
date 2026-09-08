"""Implementation of the image filters CCITTFaxDecode, JBIG2Decode, DCTDecode,
and JPXDecode.

All the filters here are pass-through or identity filters, meaning that they
actually do not perform any processing on the encoded data. The outputs of these
filters shall be further processed by a third-party image library.
"""

from ..cos.objects import PdfDictionary
from ._base import PdfFilter


class CCITTFaxFilter(PdfFilter):
    """Filter for either Group 3 or Group 4 CCITT facsimile (fax) encoded image
    data (see ISO 32000-2:2020 § 7.4.6 "CCITTFaxDecode filter").

    This is a pass-through filter, meaning it does not perform any encoding or
    decoding of its own. Instead, data is provided as is and expected to be
    processed by a third-party library supporting CCITT fax encoding.

    One common decoding strategy is to prepend a TIFF image header to the encoded
    data and provide the resulting image to a TIFF decoder, as TIFF natively supports
    CCITT fax encoding of this kind. Care should be taken to ensure that the stream
    parameters used by this filter are considered during this process.
    """

    def decode(self, contents: bytes, *, params: PdfDictionary[str, int] | None = None) -> bytes:  # pyright: ignore[reportIncompatibleMethodOverride]
        return contents

    def encode(self, contents: bytes, *, params: PdfDictionary[str, int] | None = None) -> bytes:  # pyright: ignore[reportIncompatibleMethodOverride]
        return contents


class JBIG2Filter(PdfFilter):
    """Filter for JBIG2 encoded bitonal image data, as specified in ISO 14492:2019
    (see ISO 32000-2:2020 § 7.4.7 "JBIG2Decode filter").

    This is a pass-through filter, meaning it does not perform any encoding or
    decoding of its own. Instead, data is provided as is and expected to be
    processed by a third-party library supporting JBIG2.

    It shall be noted that JBIG2 data is encoded according to Annex D.3 of
    ISO/IEC 14492:2019, without the specified 2-byte combination marker,
    in sequential organization per Annex D.1, and excluding the JBIG2 file
    header, end-of-page segments, and the end-of-file segment.

    The JBIG2Globals decode parameter shall contain the global (page 0) segments
    used by the image.
    """

    def decode(self, contents: bytes, *, params: PdfDictionary[str, int] | None = None) -> bytes:  # pyright: ignore[reportIncompatibleMethodOverride]
        return contents

    def encode(self, contents: bytes, *, params: PdfDictionary[str, int] | None = None) -> bytes:  # pyright: ignore[reportIncompatibleMethodOverride]
        return contents


class DCTFilter(PdfFilter):
    """Filter for JPEG encoded image data, which uses DCT (discrete cosine transform) as
    its primary technique for encoding (see ISO 32000-2:2020 § 7.4.8 "DCTDecode filter").

    This is a pass-through filter, meaning it does not perform any encoding or
    decoding of its own. Instead, data is provided as is and expected to be
    processed by a third-party library supporting JPEG. Note should be taken
    of the ColorTransform decode parameter during this process.
    """

    def decode(self, contents: bytes, *, params: PdfDictionary[str, int] | None = None) -> bytes:  # pyright: ignore[reportIncompatibleMethodOverride]
        return contents

    def encode(self, contents: bytes, *, params: PdfDictionary[str, int] | None = None) -> bytes:  # pyright: ignore[reportIncompatibleMethodOverride]
        return contents


class JPXFilter(PdfFilter):
    """Filter for JPEG 2000 compressed image data (see ISO 32000-2:2020 §
    7.4.9 "JPXDecode filter").

    This is a pass-through filter, meaning it does not perform any encoding or
    decoding of its own. Instead, data is provided as is and expected to be
    processed by a third-party library supporting JPEG 2000.

    JPEG 2000 processors decoding or encoding this image data should support the
    JPX baseline set of features found in ISO/IEC 15444-2, plus enumerated
    color space 12 (CMYK).
    """

    def decode(self, contents: bytes, *, params: PdfDictionary[str, int] | None = None) -> bytes:  # pyright: ignore[reportIncompatibleMethodOverride]
        return contents

    def encode(self, contents: bytes, *, params: PdfDictionary[str, int] | None = None) -> bytes:  # pyright: ignore[reportIncompatibleMethodOverride]
        return contents
