Standard Security Handler
=========================

The standard security handler is the password-based encryption method used by PDFs.

In pdfnaut, the standard security handler relies on user-supplied providers known as **crypt providers**. The crypt providers available are AES-128 (in CBC mode) and ARC4. A third provider, the Identity provider, is implemented by default and does nothing.

pdfnaut does not include implementations for these providers. You must provide them yourself either manually or by installing one of the following packages:

- `pyca/cryptography <https://cryptography.io/en/latest/>`_ 
- `PyCryptodome <https://pycryptodome.readthedocs.io/en/stable/>`_ 

When selecting a crypt provider, pdfnaut first checks for the presence of `cryptography` falling back to `PyCryptodome` if the former isn't available. If neither is available, no encryption functionalities will be provided.

To add your own crypt providers, modify one of the values in the `CRYPT_PROVIDERS` dictionary of :mod:`pdfnaut.security.providers`. The keys available are `ARC4`, `AESV2`, and `Identity`. `Identity` is already implemented.


.. automodule:: pdfnaut.security.providers
    :undoc-members:
    :members:

.. automodule:: pdfnaut.security.standard_handler
    :undoc-members:
    :members:
