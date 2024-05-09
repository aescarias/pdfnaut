# pdfnaut

[![Documentation Status](https://readthedocs.org/projects/pdfnaut/badge/?version=latest)](https://pdfnaut.readthedocs.io/en/latest/?badge=latest)
![PyPI - License](https://img.shields.io/pypi/l/pdfnaut)
![PyPI - Downloads](https://img.shields.io/pypi/dw/pdfnaut)
![PyPI - Version](https://img.shields.io/pypi/v/pdfnaut)

> [!Warning]
> pdfnaut is currently in an early stage of development and has only been tested with a small set of compliant documents. Expect bugs or issues.

pdfnaut is a Python library for parsing PDF 1.7 files.

pdfnaut provides a low-level interface for reading and writing PDF objects as defined in the [PDF 1.7 specification](https://opensource.adobe.com/dc-acrobat-sdk-docs/pdfstandards/PDF32000_2008.pdf). pdfnaut currently does not attempt to deviate from the specification. There's no guarantee that valid documents not fully conforming to the standard will be processed correctly.

## Examples

The newer high-level API

```py
from pdfnaut import PdfDocument

pdf = PdfDocument.from_filename("tests/docs/sample.pdf")
first_page = list(pdf.flattened_pages)[0]
if "Contents" in first_page:
    first_page_stream = pdf.resolve_reference(first_page["Contents"])
    print(first_page_stream.decompress())
```

The more mature low-level API

```py
from pdfnaut import PdfParser

with open("tests/docs/sample.pdf", "rb") as doc:
    pdf = PdfParser(doc.read())
    pdf.parse()

    # Get the pages object from the trailer
    root = pdf.resolve_reference(pdf.trailer["Root"])
    pages = pdf.resolve_reference(root["Pages"])
    
    # Get the first page contents
    first_page = pdf.resolve_reference(pages["Kids"][0])
    first_page_stream = pdf.resolve_reference(first_page["Contents"])
    print(first_page_stream.decompress())
```

## Coverage

The following tracks coverage of certain portions of the PDF standard.

- Compression filters: **Supported** -- FlateDecode, ASCII85, ASCIIHex, Crypt (decode only), and RunLength (decode only).
- Reading from encrypted PDFs: **Supported** (ARC4 and AES; requires a user-supplied implementation or availability of a compatible module -- `pycryptodome` for now)
- XRef streams: **Supported**
- File specifications: **Not supported**
