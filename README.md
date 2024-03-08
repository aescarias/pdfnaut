# PDFnaut

PDFnaut is a Python library for parsing PDF 1.7 files.

> This library is currently unstable and has been tested only with a small set of simple documents. If you face an issue using PDFnaut, see [Coverage](#coverage) below.

PDFnaut currently provides a barebones low-level interface for parsing PDF objects as defined in the [PDF 1.7 specification](https://opensource.adobe.com/dc-acrobat-sdk-docs/pdfstandards/PDF32000_2008.pdf). It currently attempts to be very strict in this respect, so PDFnaut may not be able to parse possibly valid documents that may not fully conform to the standard.

```py
from pdfnaut.parsers import PdfParser

with open("tests/docs/sample.pdf", "rb") as doc:
    pdf = PdfParser(doc.read())
    pdf.parse()

    # Get the pages object from the trailer
    root = pdf.resolve_reference(pdf.trailer["Root"])
    pages = pdf.resolve_reference(root["Pages"])
    
    # Get the first page contents
    first_page = pdf.resolve_reference(pages["Kids"][0])
    first_page_stream = pdf.resolve_reference(first_page["Contents"])
    print(first_page_stream.contents)
```

## Coverage

The following tracks coverage of certain portions of the PDF standard.

- Compression filters: **Supported** (only FlateDecode, ASCII85Decode, and ASCIIHexDecode for now)
- Reading from encrypted PDFs: **Supported** (ARC4 and AES; requires a user-supplied implementation or availability of a compatible module -- `pycryptodome` for now)
- XRef streams: **Supported**
- File specifications: **Not supported**
