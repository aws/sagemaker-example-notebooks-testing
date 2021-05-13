import json
import os

from sagemakerci.run_notebook import ensure_session


def is_notebook(filename):
    root, ext = os.path.splitext(filename)
    if ext == ".ipynb":
        return os.path.exists(filename)


def kernel_for(notebook):
    """Read the notebook and extract the kernel name, if any"""
    with open(notebook, "r") as f:
        nb = json.load(f)

        md = nb.get("metadata")
        if md:
            ks = md.get("kernelspec")
            if ks:
                return ks["display_name"]
    return None


def code_cells(notebook):
    with open(notebook) as notebook_file:
        cells = json.load(notebook_file)["cells"]
    code_cells = []
    for cell in cells:
        if cell["cell_type"] == "code":
            code_cells.append(cell["source"])
    return code_cells


def contains_code(notebook, snippets):
    cells = code_cells(notebook)

    for cell in cells:
        for line in cell:
            if any(snippet in line for snippet in snippets):
                return True

    return False


def markdown_cells(notebook):
    with open(notebook) as notebook_file:
        cells = json.load(notebook_file)["cells"]
    md_cells = []
    for cell in cells:
        if cell["cell_type"] == "markdown":
            md_cells.append(cell["source"])
    return md_cells
