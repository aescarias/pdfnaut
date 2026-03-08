Working with Outlines
=====================

Document outlines, also known as bookmarks, allow a user to navigate through the contents of a document. PDF outlines are represented as a hierarchy of outline items which include attributes such as text, color, and destination.

To access the document outline, you can use the :attr:`.PdfDocument.outline` property:

.. code-block:: python
    
    from pdfnaut import PdfDocument

    pdf = PdfDocument.from_filename("sample.pdf")
    print(pdf.outline)

:attr:`.PdfDocument.outline` contains the document outline tree which has pointers to the first and last outline item. To get the sequence of outline items included in the document, use ``pdf.outline.children``.

Each child is an :class:`.OutlineItem` which includes the outline's text and style flags (bold and italic), the action it performs, as well as the immediate children of the item.

To get the outline's text, you can use :attr:`.OutlineItem.text`:

.. code-block:: python

    print(pdf.outline.children[0].text)  # Introduction

Similarly, the :attr:`.OutlineItem.color` and :attr:`.OutlineItem.flags` attributes can be used to retrieve the color of the outline text and the style flags applied to the outline text, respectively. 

When triggered, an outline item will usually jump to a part of the current document, of an external document, or to a completely different resource, such as multimedia or URIs. This can be achieved using two methods:

- specifying the :attr:`.OutlineItem.destination` property which takes a :class:`.Destination` object or a string pointing to a named destination.
- specifying the :attr:`.OutlineItem.action` property which takes an :class:`.Action` object.

An outline item may have a destination or an action, but not both.

Adding outlines
---------------

.. note::
    
    If a document does not already have an outline, you will need to call the :meth:`.PdfDocument.new_outline` method to initialize the outline tree before inserting items to it.

To append or insert outlines to an outline tree or item, you can use the :meth:`.OutlineList.append` and :meth:`.OutlineList.insert` methods in the ``children`` property of the :class:`.OutlineTree` and :class:`.OutlineItem` classes.

.. code-block:: python

    item = OutlineItem(
        text="Hello, world!", 
        destination=Destination.fit(pdf.pages[0])
    )

    pdf.outline.children[0].append(item)

Outline items are represented using the :class:`.OutlineItem` class which takes multiple arguments, including the outline text and the destination. The destination is specified here as a :class:`.Destination` object. Destinations have 3 properties: the page to display, the location to jump to, and a zoom factor. These properties can be modified using the constructors provided in the :class:`.Destination` object (such as :meth:`.Destination.fit`).

.. important::
    Because each outline item tracks the document it is part of, to add an outline item as a child of another, the parent outline item must already be part of the outline tree. You may also explicitly set the PDF an outline item belongs to by providing the ``pdf`` parameter.

Once the outline item has a PDF attached to it, you can add outline items to it.

.. code-block:: python

    item = OutlineItem(
        text="Hello, world!", 
        destination=Destination.fit(pdf.pages[0])
    )
    pdf.outline.children[0].append(item)

    item.children.append(
        OutlineItem("Foo", destination=Destination.fit(pdf.pages[1]))
    )
    item.children.append(
        OutlineItem("Bar", destination=Destination.fit(pdf.pages[2]))
    )


Removing outlines
-----------------

To remove an outline item, you can use the :meth:`.OutlineList.pop` method. To remove all the children within an outline item, you can use the :meth:`.OutlineList.clear` method.

To remove the outline tree from the document, you can use the `del` operator on :attr:`.PdfDocument.outline`.
