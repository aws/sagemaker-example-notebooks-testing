#!/usr/bin/env python3
import argparse
import json
import os
import sys
import time

from sagemakerci.run_notebook import (
    ensure_session,
    get_output_prefix,
    upload_notebook,
    execute_notebook,
    wait_for_complete,
)
from sagemakerci.git import Git

import boto3
from github import Github


def get_latest_image_digest(registry, repository):
    client = boto3.client("ecr")
    response = client.describe_images(
        registryId=registry,
        repositoryName=repository,
        maxResults=1000,
    )
    images = response["imageDetails"]
    return sorted(images, key=lambda image: image["imagePushedAt"], reverse=True)[0]["imageDigest"]


CI_REGISTRY_ID = "521695447989"
LL_REGISTRY_ID = "236514542706"

BASE_PYTHON_IMAGE = f"{CI_REGISTRY_ID}.dkr.ecr.us-west-2.amazonaws.com/base-python@{get_latest_image_digest(CI_REGISTRY_ID, 'base-python')}"
DATA_SCIENCE_IMAGE = f"{CI_REGISTRY_ID}.dkr.ecr.us-west-2.amazonaws.com/data-science@{get_latest_image_digest(CI_REGISTRY_ID, 'data-science')}"
MXNET_IMAGE = f"{CI_REGISTRY_ID}.dkr.ecr.us-west-2.amazonaws.com/mxnet@{get_latest_image_digest(CI_REGISTRY_ID, 'mxnet')}"
PYTORCH_IMAGE = f"{CI_REGISTRY_ID}.dkr.ecr.us-west-2.amazonaws.com/pytorch@{get_latest_image_digest(CI_REGISTRY_ID, 'pytorch')}"
TENSORFLOW_1_IMAGE = f"{CI_REGISTRY_ID}.dkr.ecr.us-west-2.amazonaws.com/tensorflow-1@{get_latest_image_digest(CI_REGISTRY_ID, 'tensorflow-1')}"
TENSORFLOW_2_IMAGE = f"{CI_REGISTRY_ID}.dkr.ecr.us-west-2.amazonaws.com/tensorflow-2@{get_latest_image_digest(CI_REGISTRY_ID, 'tensorflow-2')}"
SPARK_IMAGE = f"{CI_REGISTRY_ID}.dkr.ecr.us-west-2.amazonaws.com/spark@{get_latest_image_digest(CI_REGISTRY_ID, 'spark')}"


def parse_args(args):
    parser = argparse.ArgumentParser(os.path.basename(__file__))
    parser.set_defaults(func=lambda x: parser.print_usage())
    parser.add_argument("--pr", help="Pull request number", type=int, required=True)
    parser.add_argument("--instance", help="Instance type", type=str, required=False)

    parsed = parser.parse_args(args)
    if not parsed.pr:
        parser.error("--pr required")

    return parsed


def is_notebook(filename):
    root, ext = os.path.splitext(filename)
    if ext == ".ipynb":
        return os.path.exists(filename)


def notebook_filenames(pr_num):
    g = Github(Git().oauth_token)
    repo = g.get_repo("aws/amazon-sagemaker-examples")
    pr = repo.get_pull(pr_num)
    return filter(is_notebook, [file.filename for file in pr.get_files()])


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


def kernel_type_for(notebook):
    kernel_name = kernel_for(notebook)

    if kernel_name:
        if any(
            name in kernel_name
            for name in ("MXNet", "conda_mxnet_latest_p37", "conda_mxnet_p27", "conda_mxnet_p36")
        ):
            return "MXNet"
        elif any(
            name in kernel_name
            for name in (
                "PyTorch",
                "conda_pytorch_latest_p36",
                "conda_pytorch_p27",
                "conda_pytorch_p36",
            )
        ):
            return "PyTorch"
        elif any(
            name in kernel_name
            for name in ("TensorFlow 1", "conda_tensorflow_p27", "conda_tensorflow_p36")
        ):
            return "TensorFlow 1"
        elif any(name in kernel_name for name in ("TensorFlow 2", "conda_tensorflow2_p36")):
            return "TensorFlow 2"
        elif any(name in kernel_name for name in ("SparkMagic", "PySpark", "pysparkkernel")):
            return "Spark"

    return "Data Science"


def kernel_image_for(notebook):
    kernel_type = kernel_type_for(notebook)

    if kernel_type == "MXNet":
        return MXNET_IMAGE
    elif kernel_type == "PyTorch":
        return PYTORCH_IMAGE
    elif kernel_type == "TensorFlow 1":
        return TENSORFLOW_1_IMAGE
    elif kernel_type == "TensorFlow 2":
        return TENSORFLOW_2_IMAGE
    elif kernel_type == "Spark":
        return SPARK_IMAGE

    return DATA_SCIENCE_IMAGE


def describe(job_name, session):
    session = ensure_session(session)
    client = session.client("sagemaker")
    response = client.describe_processing_job(ProcessingJobName=job_name)
    return response["ProcessingJobStatus"], response.get("ExitMessage")


def is_running(job_name, session):
    if not job_name:
        return False
    status, failure_reason = describe(job_name, session)
    if status in ("InProgress", "Stopping"):
        return True
    return False


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


def main():
    args = parse_args(sys.argv[1:])

    jobs = {}

    session = ensure_session()
    instance_type = args.instance or "ml.m5.xlarge"
    for notebook in notebook_filenames(args.pr):
        if contains_code(notebook, ["docker ", 'instance_type = "local"']):
            job_name = None
        else:
            image = kernel_image_for(notebook)
            s3path = upload_notebook(notebook, session)
            job_name = execute_notebook(
                image=image,
                input_path=s3path,
                notebook=notebook,
                role="SageMakerRole",
                instance_type=instance_type,
                session=session,
                output_prefix=get_output_prefix(),
                parameters={},
            )
            time.sleep(1)

        jobs[notebook] = job_name

    failures = {}

    while jobs:
        for notebook in list(jobs):
            job_name = jobs[notebook]
            if not is_running(job_name, session):
                if job_name:
                    status, failure_reason = wait_for_complete(
                        job_name, progress=False, session=session
                    )
                else:
                    status, failure_reason = (
                        "Skipped",
                        "This notebook was skipped because it either uses Docker or Local Mode.",
                    )

                basename = os.path.basename(notebook)
                print("\n" * 2)
                print(f"* {basename} " + "*" * (97 - len(basename)))
                print("*")
                print(f"* {'job name':>11}: {str(job_name):<11}")
                print("*")
                print(f"* {'kernel':>11}: {kernel_type_for(notebook):<11}")
                print("*")
                print(f"* {'status':>11}: {status:<11}")
                print("*")
                if status != "Completed":
                    print(failure_reason)
                    failures[notebook] = failure_reason
                jobs.pop(notebook)
            time.sleep(10)

    print("\n" * 2)
    print("-" * 100)
    if len(failures) > 0:
        raise Exception(
            "One or more notebooks failed to execute. Please see above for error messages. "
            "If you need more information, please see the CloudWatch logs for the corresponding Processing job."
        )


if __name__ == "__main__":
    main()
