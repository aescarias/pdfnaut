# pdfnaut

[![Documentation Status](https://readthedocs.org/projects/pdfnaut/badge/?version=latest)](https://pdfnaut.readthedocs.io/en/latest/?badge=latest)
![PyPI - License](https://img.shields.io/pypi/l/pdfnaut)
![PyPI - Downloads](https://img.shields.io/pypi/dw/pdfnaut)
![PyPI - Version](https://img.shields.io/pypi/v/pdfnaut)

> [!Warning]
> pdfnaut is currently in an early stage of development and has only been tested with a small set of compliant documents. Some non-compliant documents may work under strict=False. Expect bugs or issues.

pdfnaut aims to become a PDF processor for parsing PDF 2.0 files.

pdfnaut provides both a low-level interface for reading and writing PDF objects as described in the [PDF 2.0 specification](https://developer.adobe.com/document-services/docs/assets/5b15559b96303194340b99820d3a70fa/PDF_ISO_32000-2.pdf) and a high-level document interface for actions like reading and writing metadata, accessing pages, creating objects, etc.

## Installation

pdfnaut requires at least Python 3.9 or later. To install via pip:

```plaintext
python -m pip install pdfnaut
```

If you plan to work with encrypted or protected PDF documents, you must install one of the supported crypt providers. See [this](https://pdfnaut.readthedocs.io/en/latest/reference/standard_handler.html#standard-security-handler) for details.

## Examples

Example 1: Accessing the content stream of a page

```py
from pdfnaut import PdfDocument

pdf = PdfDocument.from_filename("example.pdf")
first_page = next(pdf.flattened_pages)

if first_page.content_stream:
    print(first_page.content_stream.contents)
```

Example 2: Reading document information

```py
from pdfnaut import PdfDocument

pdf = PdfDocument.from_filename("example.pdf")

assert pdf.doc_info is not None, "No document information available."

print(pdf.doc_info.title)
print(pdf.doc_info.producer)
```

For more examples on what pdfnaut can do, see the guides in our [documentation](https://pdfnaut.readthedocs.io/en/latest).
