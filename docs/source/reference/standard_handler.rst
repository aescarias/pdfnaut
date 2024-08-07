Standard Security Handler
=========================

The Standard security handler is the password-based encryption method that PDFs use.

In pdfnaut, the Standard security handler depends on user-supplied providers known as **crypt providers.** The crypt providers available are AES (in CBC mode) and ARC4. A third provider, the Identity provider, is included by default and does nothing.

pdfnaut does not include these providers. You must provide them yourself or install the `pycryptodome <https://pycryptodome.readthedocs.io/en/stable/>`_ package which will supply them for you (recommended).

To add your own crypt providers, modify one of the values in the `CRYPT_PROVIDERS` dictionary of :mod:`pdfnaut.security.providers`. The keys available are `ARC4`, `AESV2`, and `Identity`. `Identity` is already implemented.


.. automodule:: pdfnaut.security.providers
    :undoc-members:
    :members:

.. automodule:: pdfnaut.security.standard_handler
    :undoc-members:
    :members:
