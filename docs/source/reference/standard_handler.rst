Standard Security Handler
=========================

The Standard security handler is the password-based encryption method that PDFs use.

In pdfnaut, the Standard security handler depends on user-supplied providers known as **crypt providers.** The crypt providers available are AES-128 (in CBC mode) and ARC4. A third provider, the Identity provider, is included by default and does nothing.

pdfnaut does not include these providers. You must provide them yourself or install one of the following packages:

- `pyca/cryptography <https://cryptography.io/en/latest/>`_ 
- `PyCryptodome <https://pycryptodome.readthedocs.io/en/stable/>`_ 

pdfnaut first checks for the presence of `cryptography` falling back on `PyCryptodome` if the former isn't available. If neither is available, no encryption functionalities will be available.

To add your own crypt providers, modify one of the values in the `CRYPT_PROVIDERS` dictionary of :mod:`pdfnaut.security.providers`. The keys available are `ARC4`, `AESV2`, and `Identity`. `Identity` is already implemented.


.. automodule:: pdfnaut.security.providers
    :undoc-members:
    :members:

.. automodule:: pdfnaut.security.standard_handler
    :undoc-members:
    :members:
