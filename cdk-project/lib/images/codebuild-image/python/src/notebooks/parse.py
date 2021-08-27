import json
import os
from pathlib import Path
from os import walk
from github import Github
from notebooks.git import Git

SKIP_LIST = {
    "advanced_functionality/distributed_tensorflow_mask_rcnn", 
    "advanced_functionality/multi_model_linear_learner_home_value/linear_learner_multi_model_endpoint_inf_pipeline.ipynb",
    "aws_marketplace",
    "contrib",
    "end_to_end",
    "ground_truth_labeling_jobs",
    "ingest_data",
    "label_data",
    "prep_data",
    "reinforcement_learning/bandits_statlog_vw_customEnv/bandits_statlog_vw_customEnv.ipynb",
    "async-inference/Async-Inference-Walkthrough.ipynb"
    "sagemaker-fundamentals",
    "sagemaker-pipelines/tabular/lambda-step/sagemaker-pipelines-lambda-step.ipynb",
    "sagemaker-pipelines/tabular/tensorflow2-california-housing-sagemaker-pipelines-deploy-endpoint/tensorflow2-california-housing-sagemaker-pipelines-deploy-endpoint.ipynb",
    "sagemaker_edge_manager",
    "sagemaker_neo_compilation_jobs/gluoncv_yolo/gluoncv_yolo_neo.ipynb",
    "step-functions-data-science-sdk",
    "training/distributed_training/pytorch/data_parallel/rnnt/RNNT_notebook.ipynb",
    "use-cases",
}

def all_notebook_filenames():
    """Return all the notebook filenames in the current directory.

    Returns:
        [str]: A list of strings containing paths to notebooks in the current directory.

    """
    return [str(filename) for filename in Path(".").rglob("*.ipynb")]


def get_pr_files(pr_num):
    """Return all the files in a given GitHub pull request.

    Args:
        pr_num: The pull request number.

    Returns:
        [File]: A list of File objects for all the files in the PR.

    """
    g = Github(Git().oauth_token)
    repo = g.get_repo("aws/amazon-sagemaker-examples")
    pr = repo.get_pull(pr_num)
    return pr.get_files()


def pr_notebook_filenames(pr_num):
    """Return all the notebook filenames in a given GitHub pull request.

    Args:
        pr_num: The pull request number.

    Returns:
        [str]: A list of strings containing paths to notebooks in the PR.

    """
    return filter(is_notebook, [file.filename for file in get_pr_files(pr_num)])


def get_deleted_files(pr_num):
    """Return all the deleted files in a given GitHub pull request.

    Args:
        pr_num: The pull request number.

    Returns:
        [str]: A list of strings containing names of the deleted notebooks in the PR.

    """

    return filter(is_deleted, [file for file in get_pr_files(pr_num)])

def is_deleted(file):
    """Check whether a given file is in a removed or deleted state.

    Args:
        filename: The filename to check.

    Returns:
        bool: Whether the given file has been removed or not.

    """
    return file.status == 'removed'

def check_file_references(name):
    """Check whether a given file is referenced in the repo

    Args:
        filename: The filename to check.

    Returns:
        bool: Whether the given file has been refereenced in the repo or not.

    """
    references = []
    for root, dirs, files in walk(Path(".")):
        for file_name in files:
            if is_notebook(file_name):
                nb_markdown_cells = markdown_cells(os.path.join(root, file_name))
                for cell in nb_markdown_cells:
                    for line in cell:
                        if name in line:
                            references.append(file_name)
            else:
                with open(os.path.join(root, file_name), encoding="utf8", errors='ignore') as non_nb_file:
                    if name in non_nb_file.read():
                        references.append(file_name)
    return references

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


def all_cells(notebook):
    with open(notebook) as notebook_file:
        cells = json.load(notebook_file)["cells"]
    return cells

def code_cells(notebook):
    """Get a list of all the code cells in a given notebook.

    Args:
        notebook (Path): The notebook to get the code cells from.

    Returns:
        [[str]]: A list of code cells. Each code cell is a list of lines of code.

    """

    cells = all_cells(notebook)
    return [cell["source"] for cell in cells if cell["cell_type"] == "code"]


def contains_code(notebook, snippets):
    """Check whether a notebook contains any of a list of code snippets in any of its code cells.

    Args:
        notebook (Path): The notebook to check for code snippets.
        snippets ([str]): The list of code snippet strings to check for.

    Returns:
        bool: Whether any of the code snippets exist in the notebook's code cells.

    """
    cells = all_cells(notebook)
    source = [cell["source"] for cell in cells]

    for cell_source in source:
        for line in cell_source:
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
    cells = all_cells(notebook)
    return [cell["source"] for cell in cells if cell["cell_type"] == "markdown"]


def skip(notebook):
    """Check whether the notebook should be skipped.

    Args:
        notebook (Path): The notebook to check whether to skip.

    Returns:
        bool: True if the notebook should be skipped.

    """
    directories = Path(notebook).parents

    if str(notebook) in SKIP_LIST:
        return True
    elif any([str(directory) in SKIP_LIST for directory in directories]):
        return True
    return False
