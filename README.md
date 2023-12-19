# PDFnaut

PDFnaut is a Python library for parsing PDF 1.7 files.

> This library is currently unstable and has been tested only with a small set of simple documents. If you face an issue using PDFnaut, see [Coverage](#coverage) below.

PDFnaut currently provides a barebones low-level interface for parsing PDF objects as defined in the [PDF 1.7 specification](https://opensource.adobe.com/dc-acrobat-sdk-docs/pdfstandards/PDF32000_2008.pdf).

```py
from pdfnaut.parse import PdfParser

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

- Compression filters (FlateDecode, ASCII85Decode, etc): **Not supported**
- Reading from encrypted PDFs: **Not supported**
- Linearized PDFs: **Almost**. They will parse but require testing.
- Compressed XRef objects: **Not supported**
