# Contributing Guidelines

Thank you for considering a contribution to pdfnaut. Your efforts help keep this project alive.

## Reporting Issues

When reporting an issue, please provide a *Minimal Reproducible Example (MRE)*. This should include the simplest way to reproduce the issue and the PDF document being parsed.

## Contributing to Source Code

### Style Guide

- Docstrings should be written according to the [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html#docstrings).
- Code should mostly adhere to the [PEP8](https://www.python.org/dev/peps/pep-0008/) style guide.
- Markdown documents are linted through [Markdownlint](https://github.com/DavidAnson/markdownlint).
- Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/). See below.

### Versioning

Our project follows [Semantic Versioning 2.0.0](https://semver.org/spec/v2.0.0.html). In short:

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

- `docs`: Docstrings; comments; guides and related resources¿
- `writer`: Serialization
- `parser`: Tokenizing; parsing and reading; filters
- `tests`: Code coverage; unit testing
- `security`: Encryption; permissions
- `objects`: Primitive objects; common data structures

The commit types currently in use are:

- `feat` for new features.
- `fix` For bug fixes (if applicable, they should reference the issue this commit resolves)
- `chore` for anything else not covered in the other types.
