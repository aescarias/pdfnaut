Dictionary Models and Accessors
===============================

.. note::
    This is a technical document regarding internal functionality in pdfnaut. It is mostly relevant to users wanting to contribute to or extend pdfnaut's functionality.

A PDF document is essentially a collection of dictionary objects. These objects range from pages to annotations and outline items. One of the goals of pdfnaut is provide idiomatic data models for each dictionary object, which avoids unnecessarily exposing PDF object internals to users.

Dictionary models (or dictmodels) are the backing mechanism behind many of these data models. A dictmodel provides a dataclass-like interface for mapping PDF objects to Python objects, which reduces the boilerplate required to do so. An example of a dictmodel is shown below:

.. code-block:: python

    @dictmodel
    class MyModel(PdfDictionary):
        number: int
        text: str
        date: datetime.datetime
        name: Literal[...]
        optional: ... | None = None


Understanding Dictmodels
------------------------

Dictionary models work by mapping field values to their corresponding PDF object types. This is achieved by using descriptors to control attribute access. These descriptors are referred to internally as **accessors**, because they are responsible for handling access and type conversions between the PDF object type and the Python object type.

pdfnaut defines the following accessors:

- :class:`.StandardAccessor` is the base accessor. The accessor handles types with transparent mapping between PDF and Python, such as numbers, booleans, and other PDF objects without conversion to their Python counterparts.
- :class:`.NameAccessor` maps PDF name objects to Python strings.
- :class:`.DateAccessor` maps PDF dates (stored as strings) to Python :class:`datetime.datetime` objects.
- :class:`.TextStringAccessor` maps PDF text strings to Python strings.
- :class:`.ModelAccessor` maps PDF dictionaries to other dictmodels.
- :class:`.TransformAccessor` is an special kind of accessor allowing user-defined mapping functions: the encoder, which handles Python to PDF mapping; and the decoder, which handles PDF to Python mapping.

The accessor used for each member of the dictmodel will depend on the type specified in the field:

- Fields storing integers, floats, and booleans use the standard accessor. If the field type is a PDF object type, it will also use the standard accessor.
- Fields with a :class:`typing.Literal` type use the name accessor. PDF names may also be mapped to Python strings by using `Annotated[str, "name"]` as the field type.
- Fields with the :class:`datetime.datetime` type are mapped to date accessors.
- Fields with the string type (:class:`str`) use the text string accessor.
- Fields where the type is another dictmodel use the model accessor.
- Fields specifying an encoder and decoder use the transform accessor.

It shall be noted that :class:`StandardAccessor` is the default accessor used if none of the types above are satisfied. ``T | None`` unions (for optional fields) will use the accessor according to the type ``T``. 

Each field name in a dictmodel is automatically mapped to a corresponding title-cased key in the underlying dictionary. This means that a dictmodel field named ``base_version`` will access the underlying PDF dictionary using the key ``BaseVersion``. This behavior may be modified by passing a ``key`` argument to the :func:`~pdfnaut.common.dictmodels.field` function.

Using Dictmodels
----------------

Dictionary models can be created using the :func:`~pdfnaut.common.dictmodels.dictmodel` decorator. Dictmodels must operate on subclasses of :class:`.PdfDictionary`.

Similar to Python data classes, the ``@dictmodel`` decorator takes three arguments:

- ``init`` which controls whether to build an initializer.
- ``repr`` which controls whether to build a user-friendly string representation.
- ``kw_only`` which controls whether fields in the dictmodel are keyword-only.

The following shows an example of a dictmodel ``Point`` with three fields ``x``, ``y``, and ``z``:

.. code-block:: python

    @dictmodel
    class Point(PdfDictionary):
        x: float
        y: float
        z: float | None = None


An instance of a dictmodel can be built as usually done with other classes. When printed, it should provide a developer-friendly representation of the object.

.. code-block:: python

    >>> point = Point(1, 2)
    >>> point
    Point(x=1, y=2)    


.. note::

    You may notice that, unlike dataclasses, the repr output by the ``Point`` dictmodel does not include the ``z`` field. This is because dictmodels intentionally exclude fields with default values from the ``__repr__`` output.


The underlying dictionary can be read using the ``data`` attribute:

.. code-block:: python

    >>> point = Point(1, 2)
    >>> point.data
    {"X": 1, "Y": 2}    


Notice not only the title-case names applied by the dictmodel, but also the lack of the ``Z`` field, since fields with default values are not written to the underlying dictionary to save space.

Because dictmodels inherit from :class:`PdfDictionary`, common dictionary operations should also work on dictmodels. Changes to the underlying dictionary are reflected by the dictmodel. Note however that these assume raw PDF objects and so do not perform any form of transformation as done with fields.

.. code-block:: python

    >>> point = Point(1, 2)
    >>> point["Z"] = 3
    >>> point.data
    {"X": 1, "Y": 2, "Z": 3}
    >>> point
    Point(x=1, y=2, z=3)   
