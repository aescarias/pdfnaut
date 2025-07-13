Dictionary Models and Accessors
===============================

.. note::
    This is a technical document referring to internal functionality in pdfnaut. It is mostly relevant to users wishing to contribute to or extend pdfnaut's functionality.

Most structures in PDFs are dictionary objects that may be accessed and modified. These structures can usually be easily represented as Python classes.

Because the information in these dictionaries is low level, pdfnaut strives to map this information into more idiomatic forms. To do this, *descriptors* are employed which allow us to implement custom behaviors on attribute access and modification. This is mostly useful when transforming values from one type to another.

pdfnaut 0.9 introduced the concept of **dictionary models** (or dictmodels, for short) which aims to abstract the underlying dictionary into a dataclass-like structure. Dictmodels are constructed using the :func:`~pdfnaut.common.dictmodels.dictmodel` decorator. An example of a dictmodel is shown below:

.. code-block:: python

    @dictmodel()
    class MyModel(PdfDictionary):
        number: int
        text: str
        date: datetime.datetime
        name: Literal[...]
        optional: Union[..., None]


Understanding Accessors
-----------------------

Each key in a dictionary is represented in a dictmodel by an **accessor**. An accessor is responsible for handling type conversions between the object type stored in PDF and the idiomatically equivalent type in Python. These are implemented using the descriptor protocol.

4 accessors are currently defined:

- :class:`.StandardAccessor` is the base accessor which handles types that do not need a complex mapping such as numbers and booleans.
- :class:`.NameAccessor` maps name objects to Python strings.
- :class:`.DateAccessor` maps date values stored in text strings to Python :class:`datetime.datetime` objects.
- :class:`.TextStringAccessor` maps PDF text strings to Python strings.

The accessor used for each member of the dictmodel will depend on the type specified:

- The types :class:`int`, :class:`float`, and :class:`bool` use the standard accessor. :class:`.PdfDictionary` and :class:`.PdfArray` also currently use this accessor although they will receive their own special accessors in the future.
- The :class:`str` type is automatically mapped to a text string accessor. However, it is also possible to map it to a name accessor by specifying the :class:`Annotated[str, "name"]` form.
- Literal types defined using :class:`typing.Literal` are mapped to name accessors.
- :class:`datetime.datetime` objects are mapped to date accessors.

Using Dictmodels
----------------

Each member name in a dictmodel is automatically mapped to a corresponding title-cased key in the underlying dictionary. This means that a dictmodel member named ``base_version`` would access the underlying contents using the key ``BaseVersion``. 

This behavior may be modified by specifying the ``key`` argument in the :func:`.~pdfnaut.common.dictmodels.field` function.

Creating a standard accessor can be done by simply defining the name of the field and its type:

.. code-block:: python

    @dictmodel()
    class MyModel(PdfDictionary):
        number: int

A name accessor using a literal type can be defined as follows:

.. code-block:: python

    Value = Literal["X", "Y", "Z"]

    @dictmodel()
    class MyModel(PdfDictionary):
        value: Value


A generic name accessor is defined using the Annotated form:

.. code-block:: python

    @dictmodel()
    class MyModel(PdfDictionary):
        value: Annotated[str, "name"]

A date accessor is simply defined using the :class:`datetime.datetime` type:

.. code-block:: python

    @dictmodel()
    class MyModel(PdfDictionary):
        value: datetime.datetime

