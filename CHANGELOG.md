<!-- markdownlint-configure-file { "MD024": { "siblings_only": true } } -->
# Changelog

This is the changelog for pdfnaut. Versions follow the scheme specified in the [Contributing Guide](./CONTRIBUTING.md#versioning). Dates are specified in YYYY-MM-DD format.

## [unreleased]

### Additions

- Allow modifying annotations in pages by adding `AnnotationList` for `Page.annotations`.
- Read support for document outlines via `PdfDocument.outline`.

### Changes

- Move annotations to separate `pdfnaut.objects.annotations` module.
- Rewrite `PdfSerializer` to use BytesIO object rather than a list of bytes. This should considerably decrease the time taken to save a document.
- The `PdfSerializer.content` attribute now contains a BytesIO object of the content to be written.
- Move to 3.10 union syntax in dictmodels (`T | None`).
- Allow the `@dictmodel` decorator to be used without parentheses.

### Removals

- Drop support for Python 3.9.
- `BitFlagAccessor` removed as it was causing type errors in Python 3.13 and later and was also unused.
- `PdfSerializer.objects` attribute removed as it was not directly used by the class. Users are now expected to create the mapping of objects themselves.

### Fixes

- Set proper `stop` default to `PageList.index` method.

## [0.10.0] (2025-08-05)

### Additions

- Mark information dictionary via `MarkInfo` and `PdfDocument.mark_info`
- Developer extensions dictionary via `ExtensionMap` and `PdfDocument.extensions`.
- Viewer preferences via `ViewerPreferences` and `PdfDocument.viewer_preferences`.
- Write support for the `PdfDocument` properties `language`, `page_mode`, and `page_layout`.

### Changes

- Rename enum members from `TitleCase` to `UPPER_SNAKE_CASE` to conform with Python naming conventions for constants.
- Warn for issues in non-conforming documents.
- Improve performance when parsing indirect references by no longer using regex.
- Replace field-accessor system with dictmodels. See the dev guide for details.
- `PdfDocument.from_filename` now accepts `pathlib.Path` objects.
- Improve page cloning mechanism so more complex pages can be copied without causing recursion errors.

### Fixes

- Parentheses in literal strings are now always escaped. The balancing behavior implemented previously was incorrect.
- Address float imprecision in `parse_iso8601` date utility.

## [0.9.0] (2025-07-06)

### Additions

- `PdfDocument.pages` for inserting, removing, and replacing pages.
- Support writing to objects inside object streams.
- Inline image parsing for content streams via `PdfInlineImage`.
- `flatten_pages` is now part of the public API.
- Add `skip_if_comment` and `parse_kv_map_until` to tokenizer.

### Changes

- Hashing and comparison support for PDF objects.
- Rename `ContentStreamIterator` to `ContentStreamTokenizer`.

### Fixes

- No longer parse indirect references in content streams as they are not allowed in this context and they cause problems with expression such as `1 0 0 RG`.
- Tolerate real numbers that start and end with a trailing or leading period (`.25`, `10.`).
- Skip comments when parsing container types such as arrays.
- No longer skip character after parsing tokens in content streams. This caused problems with expression such as `[1 0 0]TJ`

## [0.8.0] (2025-03-08)

### Additions

- Read/write support for document permissions via `UserAccessPermissions` and `PdfDocument.access_permissions`.
- Read/write support for XMP metadata.
- Support for saving documents to in-memory byte objects.
- Create PDF documents using `PdfDocument.new`.
- Modify streams in-place using `PdfStream.modify`.
- Support for Python 3.13.
- Add remaining page boundaries to `Page`: BleedBox, TrimBox, and ArtBox.
- Add `Annotation.color` field.

### Changes

- Cache objects within object streams.
- Allow date utilities to encode date strings in partial form.
- Gracefully handle circular references.
- Write file identifier entry in trailer when saving documents.
- Move utilities to `pdfnaut.common` package.
- Rename `PdfDocument.info` to `PdfDocument.doc_info`.
- Rename `PdfDocument.metadata` to `PdfDocument.xmp_info`.
- Raise `CryptProviderMissingError` rather than `NotImplementedError` when attempting to decrypt documents without a crypt provider.

### Removals

- `PdfDate` in favor of separate date utility functions.

### Fixes

- Acknowledge Crypt filter params in `PdfStream.create`.
- Process contiguous octal escape sequences properly. Also guarantee that octal escape codes are always encoded as a single byte.
- Populate free list with correct values when writing a document.
- Use correct bit positions in `AnnotationFlags`.

## [0.7.0] (2024-11-30)

### Additions

- Support for writing PDF documents.
- Support for adding, freeing, and removing PDF objects via `PdfParser.objects`.
- Support for reading hybrid-reference files.
- Support for `pyca/cryptography` alongside `pycryptodome`.
- Encoding support for PDF streams via `PdfStream.create`.
- Encoding support for RunLengthEncode filter.

### Changes

- Tolerate documents that do not immediately start with the PDF header.
- Set `PdfDocument` to inherit from `PdfParser`.
- Rewrite PDF classes to use descriptor-based field system.
- Replace `PdfParser.updates` items with `PdfXRefSection` instances.

### Removals

- `PdfXRefTable` removed in favor of `PDFXRefSection` class.

### Fixes

- Add values for `length` and `byteorder` arguments for an `int.to_bytes` call occurring in the FlateDecode filter.

## [0.6.0] (2024-09-21)

### Additions

- Automatic indirect reference resolution with `PdfDictionary` and `PdfArray` replacing the built-in `list` and `dict` types.
- Partial implementation of the `Page`, `Info`, and `Annotation` classes.
- Read/write support for PDF dates and text strings.
- Read/write support for PDFDocEncoded strings.
- Caching for PDF indirect objects.

### Removals

- Drop support for Python 3.8.
- `typings` package removed in favor of more flexible class-based implementations.

### Fixes

- Do not skip character when processing literal strings with octal escape sequences (`\ddd`).
- Add default `byteorder` value to instances of `int.from_bytes` and `int.to_bytes` in code. This argument was not specified by default in Python 3.10 and earlier.
- Move `TypeAlias` import to type checking clause. `TypeAlias` was added in 3.10 and hence importing modules that depend on it would cause problems on 3.9.
- Replace typing's `Protocol` with the typing-extensions version. In some 3.9 releases, inheriting from Protocol subclasses can cause problems.

## [0.5.0] (2024-08-08)

### Additions

- `ContentStreamIterator` for iterating over PDF content streams.
- Add convenience functions to tokenizer such as `peek()`, `skip()`, `consume()`, `matches()`, `skip_while()` and `consume_while()`.
- Replace `current_to_eol()` and `next_eol()` in tokenizer with `peek_line()` and `skip_next_eol`.

### Changes

- Rename `PdfIndirectRef` to `PdfReference`.
- Rename `PdfParser.version` to `PdfParser.header_version` to reflect the version source.
- Move `pdfnaut.objects` package to `pdfnaut.cos.objects`.

## [0.4.0] (2024-07-15)

### Additions

- `PdfDocument.access_level` for retrieving document permission/encryption status.
- Read and write support for PDF 1.5 cross-reference streams.

### Changes

- Depend on `typing-extensions` for all supported Python versions.
- Rename `PdfParser.resolve_reference` to `PdfParser.get_object` for parity with other PDF libraries.
- Rename `PdfTokenizer.is_content_stream` to `PdfTokenizer.parse_operators`.
- Rename `PdfSerializer.generate_standard_xref_table` to `PdfSerializer.generate_xref_table`.
- Rename `PdfStream.decompress` to `PdfStream.decode`.
- Move `PdfTokenizer`, `PdfParser`, and `PdfSerializer` to `pdfnaut.cos` package.
- Move Standard security handler to `pdfnaut.security` module.

## [0.3.1] (2024-06-08)

### Fixes

- Allow writing XRef tables with multiple subsections.

## [0.3.0] (2024-05-26)

### Additions

- `TypedDicts` for representing PDF dictionaries including the trailer, catlaog, outlines, and others. This introduces the `typing-extensions` dependency for users running Python 3.11 or earlier.
- The `PdfDocument` class as a foundation for the high-level document API.
- Allow specifying `strict` mode when processing non-spec-compliant PDF documents.

### Changes

- Improve performance when tokenizing indirect references by first checking for a digit before invoking regex.
- Tolerate standard XRef entry lines that are not 20 bytes long.
- Tolerate incorrect `startxref` offsets when reading documents.

## [0.2.0] (2024-05-05)

### Additions

- Encoding support for ASCIIHexDecode, ASCII85Decode, and FlateDecode filters.
- Decoding support for RunLengthDecode filter.
- Framework for encrypting objects via the Standard security handler.

### Fixes

- Do not attempt to decrypt `Encrypt` trailer in dictionary.
- Apply PNG prediction functions at byte level rather than sample level in FlateDecode, meaning that all color components of a sample are processed.
- Remove broken TIFF predictor.

## [0.1.1] (2024-04-14)

### Additions

- Publish documentation to Read the Docs
- Rename `PdfParser.update_xrefs` to `PdfParser.updates`.

### Fixes

- Properly handle whitespace characters occurring at the end of data when processing tokens that may contain them such as indirect references.

## [0.1.0] (2024-03-30)

The first release of pdfnaut. :tada:

[unreleased]: https://github.com/aescarias/pdfnaut/compare/v0.10...HEAD
[0.10.0]: https://github.com/aescarias/pdfnaut/compare/v0.9...v0.10
[0.9.0]: https://github.com/aescarias/pdfnaut/compare/v0.8...v0.9
[0.8.0]: https://github.com/aescarias/pdfnaut/compare/v0.7...v0.8
[0.7.0]: https://github.com/aescarias/pdfnaut/compare/v0.6...v0.7
[0.6.0]: https://github.com/aescarias/pdfnaut/compare/v0.5...v0.6
[0.5.0]: https://github.com/aescarias/pdfnaut/compare/v0.4...v0.5
[0.4.0]: https://github.com/aescarias/pdfnaut/compare/v0.3.1...v0.4
[0.3.1]: https://github.com/aescarias/pdfnaut/compare/v0.3...v0.3.1
[0.3.0]: https://github.com/aescarias/pdfnaut/compare/v0.2...v0.3
[0.2.0]: https://github.com/aescarias/pdfnaut/compare/v0.1.1...v0.2
[0.1.1]: https://github.com/aescarias/pdfnaut/compare/v0.1...v0.1.1
[0.1.0]: https://github.com/aescarias/pdfnaut/releases/tag/v0.1
