# Contributing Guidelines

Thank you for considering a contribution to PDFnaut. Your efforts keep this project alive.

## Reporting Issues

When reporting an issue, please provide a *Minimal Reproducible Example (MRE)*. This should include the simplest way to reproduce the issue and the PDF document being parsed.

## Contributing to Source Code

### Guidelines

- Docstrings should be written according to the [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html#docstrings).
- Code should mostly adhere to the [PEP8](https://www.python.org/dev/peps/pep-0008/) style guide.
- Markdown documents are linted through [Markdownlint](https://github.com/DavidAnson/markdownlint).
- Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/). See below.

#### Guidelines — Commit Messages

Commit messages should be descriptive and concise. They may include emojis in exceptional cases. (:tada:)

Commit messages should also specify their scope. The scope should be the modules or areas affected by the commit. (for example, `fix(parsers): ...`).

The commit types currently in use are:

- `feat` for new features.
- `fix` For bug fixes. (if applicable, they should reference the issue this commit resolves)
- `chore` for anything else not covered in the other types.
