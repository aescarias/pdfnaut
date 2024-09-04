Filters
=======

Filters allow PDF authors to encode or compress the contents of streams into more compact formats.

pdfnaut can encode and/or decode the following formats:

- The ASCII family: ASCII85Decode (Adobe's implementation) and ASCIIHexDecode
- The Crypt filter (decode only, requires dependency, untested)
- FlateDecode (aka zlib/deflate)
- RunLengthDecode (decode only)

.. automodule:: pdfnaut.filters
    :undoc-members:
    :members:
