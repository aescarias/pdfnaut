# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = 'pdfnaut'
copyright = '2024, Angel Carias'
author = 'Angel Carias'
release = '0.1.1'

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    "sphinx.ext.napoleon",
    "sphinx.ext.autodoc",
    "sphinx.ext.autosectionlabel",
    "sphinx_design",
    "sphinx_copybutton"
]

templates_path = ['_templates']
exclude_patterns = []


# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = 'furo'
html_static_path = ['_static']
html_logo = "_static/pdfnaut-logo.svg"

copybutton_prompt_text = r'>>> |\.\.\. '
copybutton_prompt_is_regexp = True

autoclass_content = "both"
autodoc_class_signature = "separated"
autodoc_default_options = {
    "show-inheritance": True
}
