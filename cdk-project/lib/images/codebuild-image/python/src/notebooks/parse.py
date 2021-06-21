import json
import os
from pathlib import Path

from github import Github
from notebooks.git import Git

SKIP_LIST = {
    "ground_truth_labeling_jobs",
    "aws_marketplace",
    "label_data",
    "contrib",
    "sagemaker-fundamentals",
    "end_to_end",
    "use-cases",
    "step-functions-data-science-sdk",
    "prep_data",
    "ingest_data",
    "advanced_functionality/distributed_tensorflow_mask_rcnn", 
    "sagemaker_edge_manager"
    
}


def all_notebook_filenames():
    """Return all the notebook filenames in the current directory.

    Returns:
        [str]: A list of strings containing paths to notebooks in the current directory.

    """
    return [str(filename) for filename in Path(".").rglob("*.ipynb")]


def pr_notebook_filenames(pr_num):
    """Return all the notebook filenames in a given GitHub pull request.

    Args:
        pr_num: The pull request number.

    Returns:
        [str]: A list of strings containing paths to notebooks in the PR.

    """
    g = Github(Git().oauth_token)
    repo = g.get_repo("aws/amazon-sagemaker-examples")
    pr = repo.get_pull(pr_num)
    return filter(is_notebook, [file.filename for file in pr.get_files()])


def is_notebook(filename):
    """Check whether a given file is a Jupyter notebook.

    Args:
        filename: The file to check.

    Returns:
        bool: Whether the given file is a Jupyter notebook.

    """
    root, ext = os.path.splitext(filename)
    if ext == ".ipynb":
        return os.path.exists(filename)


def kernel_for(notebook):
    """Parses the kernel metadata and returns the kernel display name.

    Args:
        notebook (Path): The path to the notebook for which to get the kernel.

    Returns:
        str: The kernel display name, if it exists.

    """
    with open(notebook, "r") as f:
        nb = json.load(f)

        md = nb.get("metadata")
        if md:
            ks = md.get("kernelspec")
            if ks:
                return ks["display_name"]
    return None


def code_cells(notebook):
    """Get a list of all the code cells in a given notebook.

    Args:
        notebook (Path): The notebook to get the code cells from.

    Returns:
        [[str]]: A list of code cells. Each code cell is a list of lines of code.

    """
    with open(notebook) as notebook_file:
        cells = json.load(notebook_file)["cells"]
    return [cell["source"] for cell in cells if cell["cell_type"] == "code"]


def contains_code(notebook, snippets):
    """Check whether a notebook contains any of a list of code snippets in any of its code cells.

    Args:
        notebook (Path): The notebook to check for code snippets.
        snippets ([str]): The list of code snippet strings to check for.

    Returns:
        bool: Whether any of the code snippets exist in the notebook's code cells.

    """
    cells = code_cells(notebook)

    for cell in cells:
        for line in cell:
            if any(snippet in line for snippet in snippets):
                return True

    return False


def markdown_cells(notebook):
    """Get a list of all the Markdown cells in a given notebook.

    Args:
        notebook (Path): The notebook to get the Markdown cells from.

    Returns:
        [[str]]: A list of Markdown cells. Each code cell is a list of lines of text.

    """
    with open(notebook) as notebook_file:
        cells = json.load(notebook_file)["cells"]
    return [cell["source"] for cell in cells if cell["cell_type"] == "markdown"]


def skip(notebook):
    """Check whether the notebook should be skipped.

    Args:
        notebook (Path): The notebook to check whether to skip.

    Returns:
        bool: True if the notebook should be skipped.

    """
    directories = Path(notebook).parents

    if notebook in SKIP_LIST:
        return True
    elif any([str(directory) in SKIP_LIST for directory in directories]):
        return True
    return False
