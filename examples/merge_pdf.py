"""Script for merging multiple PDFs together."""

from __future__ import annotations

import argparse
from collections.abc import Generator

from rich.progress import track
from rich.status import Status

from pdfnaut import PdfDocument
from pdfnaut.exceptions import PdfParseError


def get_range_from_string(value: str, page_count: int) -> Generator[int, None, None]:
    if "," in value:
        ranges = [val.strip() for val in value.split(",")]
    else:
        ranges = [value.strip()]

    for rg in ranges:
        # single page
        try:
            yield from range((n := int(rg)) - 1, n)
        except ValueError:
            pass

        # word forms
        if value.lower() == "all":
            yield from range(page_count)
        elif value.lower() == "odd":
            yield from range(0, page_count, 2)
        elif value.lower() == "even":
            yield from range(1, page_count, 2)

        # page range in form FIRST-LAST
        first, sep, last = rg.partition("-")
        if not sep:
            raise ValueError(f"invalid range provided: {value!r}")

        try:
            first, last = first.strip(), last.strip()
            first, last = int(first), int(last)
        except ValueError as exc:
            raise ValueError(f"invalid range provided: {value!r}") from exc

        yield from range(first - 1, last)


parser = argparse.ArgumentParser(
    prog="merge-pdf", description="merge multiple PDF documents together"
)
parser.add_argument("documents", nargs="+", type=str, help="the list of documents to merge.")
parser.add_argument(
    "-R", "--ranges", nargs="*", type=str, help="the page range to merge from each document."
)
parser.add_argument("-O", "--output", type=str, required=True, help="the final merged PDF")

args = parser.parse_args()

if not args.ranges:
    args.ranges = ["all" for _ in args.documents]

if len(args.documents) != len(args.ranges):
    raise SystemExit("error: amount of documents and page ranges must match.")

new_doc = PdfDocument.new()

for nth, (doc_path, page_range) in enumerate(zip(args.documents, args.ranges), start=1):
    try:
        pdf = PdfDocument.from_filename(doc_path)
    except FileNotFoundError:
        print(f"could not load PDF {doc_path!r} because it was not found. skipping.")
        continue
    except PdfParseError as exc:
        print(f"an error occurred while reading PDF {doc_path!r}: {exc}. skipping.")
        continue

    try:
        page_nums = get_range_from_string(page_range, len(pdf.pages))
    except ValueError as exc:
        print(f"{exc}. skipping.")
        continue

    for idx in track(page_nums, f"merging document {nth}/{len(args.documents)}"):
        new_doc.pages.append(pdf.pages[idx])

if not new_doc.pages:
    print("failed to merge documents.")
    raise SystemExit(1)

with Status(f"saving document to {args.output!r}", spinner="bouncingBar"):
    new_doc.save(args.output)

print(f"successfully merged {len(args.documents)} document(s) into {args.output!r}.")
