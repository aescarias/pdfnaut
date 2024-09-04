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
first_page = next(pdf.flattened_pages)

if first_page.content_stream:
    print(first_page.content_stream.contents)
```

The more mature low-level API

```py
from pdfnaut import PdfParser

with open("tests/docs/sample.pdf", "rb") as doc:
    pdf = PdfParser(doc.read())
    pdf.parse()

    pages = pdf.trailer["Root"]["Pages"]

    first_page_stream = pages["Kids"][0]["Contents"]
    print(first_page_stream.decode())
```
