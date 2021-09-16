import json
import os
from pathlib import Path
from os import walk
from github import Github
from notebooks.git import Git
import re

# List of notebooks and directories skipped by the CI currently
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
    "async-inference",
    "patterns/ml_gateway/ml-gateway.ipynb",
    "reinforcement_learning/bandits_statlog_vw_customEnv/bandits_statlog_vw_customEnv.ipynb",
    "sagemaker-fundamentals",
    "sagemaker-pipelines/tabular/lambda-step/sagemaker-pipelines-lambda-step.ipynb",
    "sagemaker-pipelines/tabular/tensorflow2-california-housing-sagemaker-pipelines-deploy-endpoint/tensorflow2-california-housing-sagemaker-pipelines-deploy-endpoint.ipynb",
    "sagemaker_edge_manager",
    "sagemaker_neo_compilation_jobs/gluoncv_yolo/gluoncv_yolo_neo.ipynb",
    "step-functions-data-science-sdk",
    "training/distributed_training/pytorch/data_parallel/rnnt/RNNT_notebook.ipynb",
    "use-cases",
}

# Not all notebooks can run on local_mode as well as SageMaker mode.
# This is a list of some notebooks that use Local Mode, but optionally, and can be run on the CI in "SageMaker Mode"
# Such notebooks have local_mode usage set to False by default.
LOCAL_MODE_OPTIONAL_LIST = [
    "reinforcement_learning/rl_mountain_car_coach_gymEnv/rl_mountain_car_coach_gymEnv.ipynb",
    "reinforcement_learning/rl_resource_allocation_ray_customEnv/rl_news_vendor_ray_custom.ipynb",
    "reinforcement_learning/rl_resource_allocation_ray_customEnv/rl_bin_packing_ray_custom.ipynb",
    "reinforcement_learning/rl_resource_allocation_ray_customEnv/rl_vehicle_routing_problem_ray_custom.ipynb",
    "reinforcement_learning/rl_managed_spot_cartpole_coach/rl_managed_spot_cartpole_coach_gymEnv.ipynb",
    "reinforcement_learning/rl_portfolio_management_coach_customEnv/rl_portfolio_management_coach_customEnv.ipynb",
    "reinforcement_learning/rl_predictive_autoscaling_coach_customEnv/rl_predictive_autoscaling_coach_customEnv.ipynb",
    "reinforcement_learning/rl_stock_trading_coach_customEnv/rl_stock_trading_coach_customEnv.ipynb",
    "reinforcement_learning/rl_cartpole_coach/rl_cartpole_coach_gymEnv.ipynb",
    "frameworks/pytorch/get_started_mnist_train.ipynb",
    "frameworks/mxnet/get_started_mnist_train.ipynb",
    "frameworks/tensorflow/get_started_mnist_train.ipynb"
]


def get_lm_optional_nb_names():
    return LOCAL_MODE_OPTIONAL_LIST


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
        name: The filename to check.

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


def contains_code(notebook, regex_list):
    """Check whether a notebook contains any of a list of code snippets in any of its code cells.

    Args:
        notebook (Path): The notebook to check for code snippets.
        regex_list ([str]): The list of regexes to check for

    Returns:
        bool: Whether any of the code snippets exist in the notebook's code cells.

    """
    source = code_cells(notebook)
    for cell_source in source:
        for line in cell_source:
            # Ignore comments
            if line.startswith('#'):
                continue
            # if the line contains any of the regexes, return True
            for regex in regex_list:
                if re.search(regex, line, re.IGNORECASE):
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


def is_skip_reason_other(notebook):
    """Check whether the notebook should be skipped, because it uses features like AWS Marketplace
    crowd sourcing or others

    Args:
        notebook (Path): The notebook to check whether to skip.

    Returns:
        bool: True if the notebook should be skipped because of above mentioned reasons

    """
    directories = Path(notebook).parents

    if str(notebook) in SKIP_LIST:
        return True
    elif any([str(directory) in SKIP_LIST for directory in directories]):
        return True
    return False


def local_mode_mandatory(notebook):
    """Check whether the notebook should be skipped because runs only in Local Mode

    Args:
        notebook (Path): The notebook to check.

    Returns:
        bool: True if local mode is mandatory.

    """
    directories = Path(notebook).parents
    return "reinforcement_learning" in directories and str(notebook) not in get_lm_optional_nb_names()


def uses_unsupported_feature_or_framework(notebook,skip_args):
    """Check whether the notebook should be skipped because it uses FXS, Docker or Local Mode.

    Args:
        notebook (Path): The notebook to check.
        skip_args (dict): A dictionary containing feature flag for each kind of skip, user-driven with sensible defaults
    Returns:
        bool: True if the notebook uses FXS, Docker or Local Mode.

    """
    functionalities_to_check = {
        "docker": ["docker\s+", "docker-compose\s+"],
        "local_mode": ['instance_type\s?=\s?"local"'],
        "fsx_efs": ['\s?FSxLustre\s?', '\s?EFS\s?']
    }

    for identifier in functionalities_to_check:
        if skip_args.get(identifier, True) and contains_code(notebook, functionalities_to_check[identifier]):
            return True

    return False


def is_notebook_skipped(notebook, skip_args):
    """Top level method to whether the notebook should be skipped based on certain conditions, as described by the methods above

    Args:
        notebook (Path): The notebook to check.
        skip_args (dict): A dictionary containing feature flag for enabling each kind of skip, user-driven with sensible defaults
    Returns:
        bool: True if the notebook skip conditions are met, False otherwise

    """
    # These notebooks run end-to-end, even though they use docker so we will explicitly not skip them
    if str(notebook) in get_lm_optional_nb_names():
        return False

    # Otherwise, check for presence of docker, local mode, efs, fsx or other reasons to skip
    return is_skip_reason_other(notebook) or uses_unsupported_feature_or_framework(notebook, skip_args)

