# pdfnaut Examples

Showcased here are a collection of examples demonstrating the functionality of pdfnaut.

## `print_outlines`

The `print_outlines.py` script takes in a filename as an argument and prints out the document outline or bookmarks.

## `pdf_info`

The `pdf_info.py` script takes in a filename as an argument and outputs metadata from the document information dictionary alongside other details of the PDF

## `merge_pdf`

The `merge_pdf.py` script takes in any amount of files and outputs the merged contents from each according to the provided page ranges.

Please note that you must install the `rich` library to be able to run this script.

### Arguments

- `documents`: The PDF documents to merge.
- `ranges`: A page range for each document identifying the amount of pages to extract from each. Valid formats are:
  - Single page, for example, `10` would extract the 10th page.
  - `all` pages or an `even` or `odd` amount of pages.
  - Page range in form `[first]-[last]` (both inclusive).
  - Multiple ranges for the same document may be provided by separating them with commas.
- `output`: The filepath where the merged result will be output.
