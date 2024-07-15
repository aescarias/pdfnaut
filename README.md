# pdfnaut

[![Documentation Status](https://readthedocs.org/projects/pdfnaut/badge/?version=latest)](https://pdfnaut.readthedocs.io/en/latest/?badge=latest)
![PyPI - License](https://img.shields.io/pypi/l/pdfnaut)
![PyPI - Downloads](https://img.shields.io/pypi/dw/pdfnaut)
![PyPI - Version](https://img.shields.io/pypi/v/pdfnaut)

> [!Warning]
> pdfnaut is currently in an early stage of development and has only been tested with a small set of compliant documents. Some non-compliant documents may work under strict=False. Expect bugs or issues.

pdfnaut aims to become a PDF processor for parsing PDF 2.0 files.

Currently, pdfnaut provides a low-level interface for reading and writing PDF objects as defined in the [PDF 2.0 specification](https://developer.adobe.com/document-services/docs/assets/5b15559b96303194340b99820d3a70fa/PDF_ISO_32000-2.pdf).

## Examples

The newer high-level API

```py
from pdfnaut import PdfDocument

pdf = PdfDocument.from_filename("tests/docs/sample.pdf")
first_page = list(pdf.flattened_pages)[0]
if "Contents" in first_page:
    first_page_stream = pdf.get_object(first_page["Contents"])
    print(first_page_stream.decode())
```

The more mature low-level API

```py
from pdfnaut import PdfParser

with open("tests/docs/sample.pdf", "rb") as doc:
    pdf = PdfParser(doc.read())
    pdf.parse()

    # Get the pages object from the trailer
    root = pdf.get_object(pdf.trailer["Root"])
    pages = pdf.get_object(root["Pages"])
    
    # Get the first page contents
    first_page = pdf.get_object(pages["Kids"][0])
    first_page_stream = pdf.get_object(first_page["Contents"])
    print(first_page_stream.get_object())
```

## Coverage

The following tracks coverage of certain portions of the PDF standard.

- Compression filters: **Supported** -- FlateDecode, ASCII85, ASCIIHex, Crypt (decode only), and RunLength (decode only).
- Reading from encrypted PDFs: **Supported** (ARC4 and AES; requires a user-supplied implementation or availability of a compatible module -- `pycryptodome` for now)
- XRef streams: **Supported**
- File specifications, dates & other common data structures: **Not supported**
