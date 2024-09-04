Building a PDF
==============

pdfnaut provides an interface for building new PDF documents called :class:`~pdfnaut.serializer.PdfSerializer`. The serializer provides all functions needed to write a new document.

Writing the PDF Header
----------------------

We first create an instance of the serializer and append the PDF header. All PDFs start with this header and this identifies the PDF version the document implements. A binary marker is also inserted afterwards by default.

.. code-block:: python

    builder = PDFSerializer()
    builder.write_header("1.7")

Defining our Objects
--------------------

Next, we define the objects in the PDF. The first object (1, 0) will include our document's catalog.

.. code-block:: python

    builder.objects[(1, 0)] = PdfDictionary({
        "Type": PdfName(b"Catalog"),
        "Pages": PdfReference(2, 0)
    })

Object (2, 0) will include our page tree. To keep things simple, our document will only have one page and will not use compression.

.. code-block:: python

    builder.objects[(2, 0)] = PdfDictionary({
        "Type": PdfName(b"Pages"),
        "Kids": PdfArray([PdfReference(3, 0)]),
        "Count": 1
    })

Object (3, 0) is the page itself. We specify its media box (practically its page size) to be 500 by 500 units (by default, each PDF unit in user space represents 1/72 of an inch, similar to a point in desktop publishing). We also specify where the Contents of this page are and the font used.

.. code-block:: python

    builder.objects[(3, 0)] = PdfDictionary({
        "Type": PdfName(b"Page"),
        "Parent": PdfReference(2, 0),
        "MediaBox": PdfArray([0, 0, 500, 500]),
        "Resources": PdfDictionary({ 
            "Font": PdfDictionary({ 
                "F13": PdfReference(4, 0) 
            })
        }),
        "Contents": PdfReference(5, 0)
    })

Object (4, 0) is the font specified in Resources. Again, for simplicity, we will specify Helvetica -- one of a few standard fonts that a PDF renderer should support by default.

.. code-block:: python

    builder.objects[(4, 0)] = PdfDictionary({
        "Type": PdfName(b"Font"),
        "Subtype": PdfName(b"Type1"), # Adobe Type 1 Font Format / PostScript
        "BaseFont": PdfName(b"Helvetica"),
        "Encoding": PdfName(b"WinAnsiEncoding")
    })

Object (5, 0) is the content stream defining the page itself. 

- The first line and last line delimit the text object.
- The second line specifies the font which shall be used to draw text (Tf). The first operand is ``/F13`` (Helvetica) and the second operand is 12 which is the unit (point) size of the glyph.
- The third line tells the renderer to position the text at x=100, y=400 (PDFs by default use a coordinate system with a bottom-left origin).
- The fourth line tells the renderer to draw the text "Hello".

.. code-block:: python

    page_contents = textwrap.dedent("""BT
        /F13 12 Tf
        100 400 Td
        (Hello) Tj
    ET""")

    builder.objects[(5, 0)] = PdfStream(
        PdfDictionary(
            { "Length": len(page_contents) }
        ), 
        page_contents.encode()
    )

Generating the XRef table
-------------------------

In the previous section, we defined the objects. This does not write them, though. Writing objects should preferably be coupled with the generation of the XRef table. To do this, we loop over the objects we defined earlier, write the object, and then add a new entry to the list that includes this offset. After the loop, we insert the recommended free entry at the start and generate the XRef table.

.. code-block:: python

    # f | n | c, object_number, next_free | offset | obj_stm, gen_if_used | generation | idx
    table: list[tuple[str, int, int, int]] = []

    for (obj_num, gen_num), item in builder.objects.items():
        offset = builder.write_object((obj_num, gen_num), item)
        table.append(("n", obj_num, gen_num, offset))

    table.insert(0, ("f", 0, 65535, 0))

    xref_table = builder.generate_xref_table(table)

.. seealso:: 
    :meth:`~pdfnaut.serializer.PdfSerializer.generate_xref_table`

Writing the XRef table and trailer
----------------------------------
After generating the table, we can proceed to write it. PDFs support two types of XRef tables: a traditional XRef table and an XRef stream. To keep things readable, we will use the traditional table. :meth:`~pdfnaut.serializer.PdfSerializer.write_standard_xref_table` produces such table and returns the startxref offset that we can use later. 

We then write the trailer and the startxref offset using :meth:`~pdfnaut.serializer.write_trailer`. To end the PDF, we add the ``%%EOF`` marker and write the new document as usual.

.. code-block:: python

    startxref = builder.write_standard_xref_table(xref_table)

    builder.write_trailer(PdfDictionary({ 
        "Size": xref_table.sections[0].count, 
        "Root": PdfReference(1, 0)
    }), startxref)

    builder.write_eof()

    with open("serialized.pdf", "wb") as fp:
        fp.write(builder.content)
