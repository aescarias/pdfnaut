Working with Outlines
=====================

Document outlines, also known as bookmarks, provide a way of navigating through a document. In a PDF, outlines are a hierarchy of outline items that may themselves contain other items. 

pdfnaut allows accessing outlines via the :attr:`.PdfDocument.outline` property.

.. code-block:: python
    
    from pdfnaut import PdfDocument

    pdf = PdfDocument.from_filename("sample.pdf")
    print(pdf.outline)

:attr:`.PdfDocument.outline` contains the outline tree with pointers to the first and last element. To get the sequence of outline items included in the document, use ``pdf.outline.children``.

Each child is an :class:`.OutlineItem` which includes the outline's text, styling, the action it performs, or the immediate children of the item.

The text of an outline item can be obtained by accessing using :attr:`.OutlineItem.text`.

.. code-block:: python

    print(pdf.outline.children[0].text) # Introduction

The :attr:`.OutlineItem.color` and :attr:`.OutlineItem.flags` attributes may be used to obtain the color and flags (such as bold or italic) that are applied to the outline text.

An outline usually has an *action* that it performs which in the PDF may either be a destination within a page or an action such as opening a destination in another document. The destination an outline points to can be accessed using :attr:`.OutlineItem.destination`. The destination is either a PDF name or byte string indicating a *named destination* or an array containing an explicit destination (such as display page N and fit the page into view). 

The action may be accessed using :attr:`.OutlineItem.action`. This is an :class:`.Action` object describing the action to perform. ``destination`` and ``action`` are mutually exclusive meaning that both of them shall not be set in a standard-conforming document.
