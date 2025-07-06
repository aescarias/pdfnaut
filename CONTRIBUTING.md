# Contributing Guidelines

Thank you for considering a contribution to pdfnaut. Your efforts help keep this project alive.

## Reporting Issues

When reporting an issue, please provide a *Minimal Reproducible Example (MRE)*. This should include the simplest way to reproduce the issue (exact steps, ideally) alongside the PDF document being parsed.

Your issue report should include:

- A description of the issue (alongside the issue title).
- Steps for reproducing this issue.
- A **Minimal Reproducible Example (MRE)** as described above.
- What you expected to see when running the MRE.
- The actual behavior you see when running the MRE.
- The version of ``pdfnaut`` being used.

## Contributing to Source Code

### Style Guide

- pdfnaut implements the [PDF 2.0 specification](https://developer.adobe.com/document-services/docs/assets/5b15559b96303194340b99820d3a70fa/PDF_ISO_32000-2.pdf).
- We use [Ruff](https://docs.astral.sh/ruff/) for code formatting.
- Docstrings should be written according to the [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html#docstrings).
- Markdown documents are linted through [Markdownlint](https://github.com/DavidAnson/markdownlint).
- Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/). See [Commit Messages](#commit-messages).

### Versioning

pdfnaut follows [Semantic Versioning 2.0.0](https://semver.org/spec/v2.0.0.html). In short:

- Major versions are ground-breaking changes. These hold no guarantees.
- Minor versions include additions that guarantee an upgrade is possible but not a downgrade.
- Patch versions are small fixes or additions that guarantee both an upgrade and a downgrade is possible.

For example:

- Upgrading from `1.0.0` to `2.0.0` is incompatible. So is downgrading from `2.0.0` to `1.0.0`.
- Upgrading from `1.0.0` to `1.1.0` is compatible, but not downgrading from `1.1.0` to `1.0.0`.
- Upgrading from `1.0.0` to `1.0.1` is compatible. So is downgrading from `1.0.1` to `1.0.0`.

### Commit Messages

Commit messages should be descriptive and concise. Commit messages should also specify their scope. The scope should be the modules or areas affected by the commit. (for example, `fix(parser): ...`).

The scopes currently in use are:

- `docs` for docstrings, comments, guides, and related resources.
- `writer` for serialization and writing documents.
- `parser` for tokenizing, parsing and reading, and filters.
- `tests` for code coverage and unit testing.
- `security` for encryption and permission-related features.
- `objects` for basic objects, common data structures, and high-level objects.

The commit types currently in use are:

- `feat` for new features.
- `fix` For bug fixes (if applicable, reference the issue the commit resolves).
- `chore` for anything else not covered in the other types.
