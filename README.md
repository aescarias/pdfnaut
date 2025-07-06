# pdfnaut

[![Documentation Status](https://readthedocs.org/projects/pdfnaut/badge/?version=latest)](https://pdfnaut.readthedocs.io/en/latest/?badge=latest)
![PyPI - License](https://img.shields.io/pypi/l/pdfnaut)
![PyPI - Downloads](https://img.shields.io/pypi/dw/pdfnaut)
![PyPI - Version](https://img.shields.io/pypi/v/pdfnaut)

> [!Warning]
> pdfnaut is currently in an early stage of development and has only been tested with a small set of compliant documents. Some non-compliant documents may work under strict=False. Expect bugs or issues.

pdfnaut aims to become a PDF processor for parsing PDF 2.0 files.

pdfnaut provides a high-level interface for reading and writing PDF documents as described in the [PDF 2.0 specification](https://developer.adobe.com/document-services/docs/assets/5b15559b96303194340b99820d3a70fa/PDF_ISO_32000-2.pdf) for actions such as reading and writing metadata, modifying and inserting pages, creating PDF objects, etc.

## Installation

pdfnaut requires at least Python 3.9 or later. To install pdfnaut via pip:

```plaintext
python -m pip install pdfnaut
```

If you plan to work with encrypted or protected PDF documents, you must install one of the supported crypt providers. See [Standard Security Handler](https://pdfnaut.readthedocs.io/en/latest/reference/standard_handler.html#standard-security-handler) in the documentation for details.

## Examples

Example 1: Accessing the content stream of a page

```py
from pdfnaut import PdfDocument

pdf = PdfDocument.from_filename("tests/docs/sample.pdf")
for operator in pdf.pages[0].content_stream:
    print(operator)
```

Example 2: Reading document information

```py
from pdfnaut import PdfDocument

pdf = PdfDocument.from_filename("tests/docs/sample.pdf")
print(pdf.doc_info.title)
print(pdf.doc_info.author)
```

For more examples on what pdfnaut can do, see the [`examples` directory](https://github.com/aescarias/pdfnaut/tree/main/examples) in the repository or see the guides in the [documentation](https://pdfnaut.readthedocs.io/en/latest).

## Contributing

Contributions to pdfnaut should be done according to the [Contributing Guidelines](https://github.com/aescarias/pdfnaut/blob/main/CONTRIBUTING.md). You can contribute in many ways including adding small features, resolving issues, writing documentation, and more.

## License

pdfnaut is provided under the terms of the [Apache License 2.0](https://github.com/aescarias/pdfnaut/blob/main/LICENSE)
