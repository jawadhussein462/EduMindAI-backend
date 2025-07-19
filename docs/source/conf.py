import os
import sys

sys.path.insert(
    0, os.path.abspath("../..")
)  # Adjust depending on your folder structure


# -- Project information -----------------------------------------------------
project = "EduMindAI"
copyright = "2025, Ali Rida Sahili, Hussein Jawad"
author = "Ali Rida Sahili, Hussein Jawad"

# -- General configuration ---------------------------------------------------

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
]


templates_path = ["_templates"]
exclude_patterns = []


# -- Options for HTML output -------------------------------------------------
html_theme = "sphinx_rtd_theme"  # 'alabaster'
html_static_path = ["_static"]
