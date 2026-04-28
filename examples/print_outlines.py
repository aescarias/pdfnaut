"""This script prints the outline tree of a PDF document."""

import sys
from getpass import getpass

from pdfnaut import PdfDocument
from pdfnaut.objects.outlines import OutlineItem, OutlineTree

if len(sys.argv) < 2:
    sys.exit(f"usage: {sys.argv[0]} [filename]")

filename = sys.argv[1]

pdf = PdfDocument.from_filename(filename)

if not pdf.access_level:
    password = getpass()
    if not pdf.decrypt(password):
        sys.exit("Authentication failed. Try again!")


def print_outline_tree(
    tree: OutlineItem | OutlineTree, *, level: int = 0, indent: str = "  ", indicator: str = ""
) -> None:
    outline = tree.first

    while outline is not None:
        title = outline.text
        print(f"{indent * level}{indicator}{title}")

        if outline.first is not None:
            print_outline_tree(outline, level=level + 1, indent=indent, indicator=indicator)

        outline = outline.next


if pdf.outline is not None and pdf.outline.first:
    print_outline_tree(pdf.outline, indicator="- ")
else:
    print("This document has no outlines.")
