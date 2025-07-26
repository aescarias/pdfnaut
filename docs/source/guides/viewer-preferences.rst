Viewer Preferences
==================

A PDF document may include viewer preferences instructing a PDF reader on how it should display a document either on screen or in print.

Accessing the viewer preferences can be done by using the :attr:`.PdfDocument.viewer_preferences` attribute. Note that this field may be absent, in which case, the PDF reader decides how to display the document.

.. code-block:: python
    
    from pdfnaut import PdfDocument
    pdf = PdfDocument.from_filename("sample.pdf")
    print(pdf.viewer_preferences)  # ViewerPreferences(display_doc_title=True)

The :class:`.ViewerPreferences` class includes a list of all available viewer preferences. They can be grouped as follows:

- Viewer preferences targeting interactive PDF processors. Examples include ``hide_menubar``, ``display_doc_title``, and ``direction``.
- Pre-press viewer preferences such as ``view_area`` and ``print_area``. These are deprecated in PDF 2.0
- Viewer preferences when printing such as ``print_scaling`` or ``num_copies``.

PDF 2.0 conforming documents may also enforce viewer preferences by means of the :attr:`.ViewerPreferences.enforce` attribute. Currently, the only enforceable preference is :attr:`.ViewerPreferences.print_scaling`.

Preferences may be modified via their attribute. Setting them to ``None`` removes the viewer preference from the document. It is worth noting that all viewer preferences are optional.

.. code-block:: python

    from pdfnaut import PdfDocument
    pdf = PdfDocument.from_filename("sample.pdf")
    
    pdf.viewer_preferences.center_window = True

To remove the viewer preferences dictionary entirely, setting :attr:`.PdfDocument.viewer_preferences` to None is enough.

Adding viewer preferences to a document can be done by creating an instance of :class:`.ViewerPreferences`.


.. code-block:: python

    from pdfnaut import PdfDocument
    from pdfnaut.objects import ViewerPreferences

    pdf = PdfDocument.from_filename("sample.pdf")

    pdf.viewer_preferences = ViewerPreferences(display_doc_title=True)

    pdf.save("view-prefs-sample.pdf")


Page Mode and Page Layout
-------------------------

Though not directly part of the viewer preferences, :attr:`.PdfDocument.page_mode` and :attr:`.PdfDocument.page_layout` also influence how a document is shown.

If a document's page mode is set to "FullScreen", the :attr:`.ViewerPreferences.non_full_screen_page_mode` may be used to specify the page mode used when full screen mode is exited.

