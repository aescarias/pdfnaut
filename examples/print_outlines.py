"""This script prints the outline tree of a PDF document."""

from __future__ import annotations

import sys
from getpass import getpass
from typing import cast

from pdfnaut import PdfDocument
from pdfnaut.cos.objects.base import PdfHexString, parse_text_string
from pdfnaut.cos.objects.containers import PdfDictionary

if len(sys.argv) < 2:
    sys.exit(f"usage: {sys.argv[0]} [filename]")

filename = sys.argv[1]

pdf = PdfDocument.from_filename(filename)

if not pdf.access_level:
    password = getpass()
    if not pdf.decrypt(password):
        sys.exit("Authentication failed. Try again!")


def print_outline_tree(
    tree: PdfDictionary, *, level: int = 0, indent: str = "  ", indicator: str = ""
) -> None:
    outline = cast(PdfDictionary, tree["First"])

    while True:
        title = parse_text_string(cast("bytes | PdfHexString", outline["Title"]))

        print(f"{indent * level}{indicator}{title}")

        if "First" in outline:
            print_outline_tree(outline, level=level + 1, indent=indent, indicator=indicator)

        if "Next" not in outline:
            break

        outline = cast(PdfDictionary, outline["Next"])


if pdf.outline_tree is not None:
    print_outline_tree(cast(PdfDictionary, pdf.outline_tree), indicator="- ")
else:
    print("This document includes no outlines.")
