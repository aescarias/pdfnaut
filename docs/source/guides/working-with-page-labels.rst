Working with Page Labels
========================

Page labels provide a mechanism for uniquely numbering or identifying a consecutive range of pages. Page labels support multiple numbering styles and can help with page navigation.

The :attr:`.PdfDocument.page_labels` property allows accessing the page label tree. The page label tree stores the page labelling ranges used for page numbering.

.. code-block:: python

    from pdfnaut import PdfDocument

    pdf = PdfDocument.from_filename(r"ISO_32000-2_sponsored-ec2.pdf")
    print(pdf.page_labels) # <PageLabelTree [0, 2, 15, 1003]>

The page label tree is provided as a mapping-like structure. This means that you can perform actions such as adding, setting, or removing page labels from the document.

The keys of the page label tree identify the logical page index (starting from zero) where the labelling range starts. The labelling ranges are consecutive and non-overlapping. If a label tree has the keys ``0`` and ``15``, the first labelling range ``0`` starts at page 1 up to page 15 and the next range ``15`` spans from page 16 up to the last page of the document.

The values of the page label tree are the page labelling ranges themselves, represented via the :class:`.PageLabelRange` class.

Page Labelling Ranges
---------------------

Page labelling ranges have 3 elements:

1. Numbering style
2. Prefix
3. Start page number

The numbering style is set using :attr:`.PageLabelRange.style`. The PDF specification allows the following numbering styles:

- :attr:`.PageNumberingStyle.DECIMAL_ARABIC` for decimal Arabic numerals (1, 2, 3, 4, 5, ...)
- :attr:`.PageNumberingStyle.UPPERCASE_ROMAN` for uppercase Roman numerals (I, II, III, IV, V, ...)
- :attr:`.PageNumberingStyle.LOWERCASE_ROMAN` for lowercase Roman numerals (i, ii, iii, iv, v, ...)
- :attr:`.PageNumberingStyle.UPPERCASE_LETTER` for uppercase bijective base-26 (A, B, C, ..., Z, AA, AB, ...)
- :attr:`.PageNumberingStyle.LOWERCASE_LETTER` for lowercase bijective base-26 (a, b, c, ..., z, aa, ab, ...)
- ``None`` for no numeric portion (default).

You can specify a prefix using :attr:`.PageLabelRange.prefix`. This prefix will appear before the numeric portion of the label. For example, with ``Errata-`` set as the prefix, the labels may appear as ``Errata-1``, ``Errata-2``, and so on.

Using :attr:`.PageLabelRange.start`, you may also offset where the numeric portion starts. By default, this is 1, meaning numbering starts at 1, then continues with 2, 3, 4, and so on. 

Adding and Removing Page Labels
-------------------------------

To add a page labelling range to a document, you can do:

.. code-block:: python

    pdf.page_labels[index] = PageLabelRange(...)

where ``index`` is the logical page index where you want the labelling range to start. 

When page labels are used in a PDF document, the page labelling ranges must cover all pages in the document. This means that, even if you only want custom page numbering for a certain range of pages, you must also specify ranges that cover the pages before and after the target page range.

If the document has no page labels specified, the page label tree will be automatically created when you add a page label range.

To delete a page labelling range, you can do:

.. code-block:: python

    del pdf.page_labels[index]

Since the ranges are consecutive, removing a page labelling range means that the pages that were previously covered by the range will now be covered by the previous range.

To delete the page label tree entirely, you can do:

.. code-block:: python

    del pdf.page_labels


Getting Page Labels
-------------------

As seen earlier, the page labelling ranges can be accessed by indexing :attr:`.PdfDocument.page_labels`. You can get a list of all page labelling ranges by using the :meth:`.PageLabelTree.get_ranges` method.

Getting the page labels themselves is done via the :meth:`.PageLabelTree.get_all` and :meth:`.PageLabelTree.get_label_for` methods.

- :meth:`.PageLabelTree.get_all` returns a generator yielding the labels for each page of the document.
- :meth:`.PageLabelTree.get_label_for` returns the page label corresponding to the provided page index.

If the document does not define any page labels, these methods will return page labels in decimal Arabic numbering (1, 2, 3, 4, 5, ...).

.. code-block:: python

    from pdfnaut import PdfDocument

    pdf = PdfDocument.from_filename(r"ISO_32000-2_sponsored-ec2.pdf")
    print(pdf.page_labels) # <PageLabelTree [0, 2, 15, 1003]>

    print(list(pdf.page_labels.get_all())) # ['Cover-A', 'Cover-B', 'i', 'ii', 'iii', ...]
    print(pdf.page_labels.get_label_for(25)) # 11

Aside from indexing :attr:`.PdfDocument.page_labels` to access the page labelling ranges, two convenience methods are provided to get the labels within a labelling range and get a list of all labelling ranges. These methods are :meth:`.PageLabelTree.get_labels_in_range` and :meth:`.PageLabelTree.get_ranges`, respectively.

.. code-block:: python

    # ['i', 'ii', 'iii', ..., 'xii', 'xiii']
    print(list(pdf.page_labels.get_labels_in_range(2))) 

    # [(PageLabelRange(...), 0, 2), (PageLabelRange(...), 2, 15), ...]
    print(list(pdf.page_labels.get_ranges()))
