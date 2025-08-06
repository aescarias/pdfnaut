# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

from __future__ import annotations

from pdfnaut import __version__

project = "pdfnaut"
copyright = "2024, Angel Carias"
author = "Angel Carias"
release = __version__

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    "sphinx.ext.napoleon",
    "sphinx.ext.autodoc",
    "sphinx.ext.autosectionlabel",
    "sphinx.ext.intersphinx",
    "sphinx.ext.viewcode",
    "sphinx_design",
    "sphinx_copybutton",
]

templates_path = ["_templates"]
exclude_patterns = []


# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = "furo"
html_static_path = ["_static"]
html_logo = "_static/pdfnaut-logo.svg"
html_theme_options = {
    "sidebar_hide_name": True,
    "source_repository": "https://github.com/aescarias/pdfnaut/",
    "source_branch": "main",
    "source_directory": "docs/source/",
}

copybutton_prompt_text = r">>> |\.\.\. "
copybutton_prompt_is_regexp = True

autoclass_content = "both"
autodoc_class_signature = "separated"
autodoc_default_options = {"show-inheritance": True}
autodoc_preserve_defaults = True
autodoc_type_aliases = {
    "PdfObject": "~pdfnaut.cos.objects.base.PdfObject",
    "PdfXRefEntry": "~pdfnaut.cos.objects.xref.PdfXRefEntry",
    "MapObject": "~pdfnaut.cos.parser.MapObject",
}

intersphinx_mapping = {"python": ("https://docs.python.org/3", None)}
