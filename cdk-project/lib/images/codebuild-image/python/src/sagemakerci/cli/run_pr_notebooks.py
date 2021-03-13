#!/usr/bin/env python3
import argparse
import json
import os
import sys

from sagemakerci.run_notebook import run_notebook

from github import Github

BASE_PYTHON_IMAGE = "521695447989.dkr.ecr.us-west-2.amazonaws.com/papermill-processing:latest"
DATA_SCIENCE_IMAGE = "521695447989.dkr.ecr.us-west-2.amazonaws.com/papermill-processing:latest"
MXNET_IMAGE = "521695447989.dkr.ecr.us-west-2.amazonaws.com/mxnet:241305b59a3dde0ad9b85e645a2adb216ffc022ddfd60541969b5f522eadbe4a"
PYTORCH_IMAGE = "521695447989.dkr.ecr.us-west-2.amazonaws.com/pytorch:cc677286ac46d07e4f8ba9b888f8c102ae03eb8ae889206d93c0a1b6d415a183"
TENSORFLOW_1_IMAGE = "521695447989.dkr.ecr.us-west-2.amazonaws.com/tensorflow-1:4526a3991b9b69ef572c0320471705e1a16ed3971a3be05fc2bfc3a46e830bef"
TENSORFLOW_2_IMAGE = "521695447989.dkr.ecr.us-west-2.amazonaws.com/tensorflow-2:11dd30e958a2278bedcbc12b80bb37ef4a2cb503b095f2428b090b5ab334a101"

NOTEBOOK_INSTANCE_KERNELS = {
    "conda_mxnet_latest_p37": MXNET_IMAGE,
    "conda_mxnet_p27": MXNET_IMAGE,
    "conda_mxnet_p36": MXNET_IMAGE,
    "conda_python2": BASE_PYTHON_IMAGE,
    "conda_python3": BASE_PYTHON_IMAGE,
    "conda_pytorch_latest_p36": PYTORCH_IMAGE,
    "conda_pytorch_p27": PYTORCH_IMAGE,
    "conda_pytorch_p36": PYTORCH_IMAGE,
    "conda_tensorflow_p27": TENSORFLOW_1_IMAGE,
    "conda_tensorflow_p36": TENSORFLOW_1_IMAGE,
    "conda_tensorflow2_p36": TENSORFLOW_2_IMAGE,
}


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
    # token = sagemakerci.git.Git().oauth_token
    g = Github()  # token)
    repo = g.get_repo("aws/amazon-sagemaker-examples")
    pr = repo.get_pull(pr_num)
    return filter(is_notebook, [file.filename for file in pr.get_files()])


def kernel_image_for(notebook):
    """Read the notebook and extract the kernel name, if any"""
    with open(notebook, "r") as f:
        nb = json.load(f)

        md = nb.get("metadata")
        if md:
            ks = md.get("kernelspec")
            if ks:
                kernel_name = ks["display_name"]

    if kernel_name:
        print(kernel_name)
        if kernel_name in NOTEBOOK_INSTANCE_KERNELS:
            return NOTEBOOK_INSTANCE_KERNELS[kernel_name]
        elif "Base Python" in kernel_name:
            return BASE_PYTHON_IMAGE
        elif "Data Science" in kernel_name:
            return DATA_SCIENCE_IMAGE
        elif "MXNet" in kernel_name:
            return MXNET_IMAGE
        elif "PyTorch" in kernel_name:
            return PYTORCH_IMAGE
        elif "TensorFlow 1" in kernel_name:
            return TENSORFLOW_1_IMAGE
        elif "TensorFlow 2" in kernel_name:
            return TENSORFLOW_2_IMAGE
    return DATA_SCIENCE_IMAGE


def main():
    args = parse_args(sys.argv[1:])

    results = {}

    instance_type = args.instance or "ml.m5.xlarge"
    for notebook in notebook_filenames(args.pr):
        image = kernel_image_for(notebook)
        print(image)
        results[notebook] = run_notebook(
            image=image,
            notebook=notebook,
            role="SageMakerRole",
            instance_type=instance_type,
        )

    failures = {}

    for notebook, result in results.items():
        job_name, status, local, failure_reason = result
        print("\n" * 2)
        basename = os.path.basename(notebook)
        print(f"* {basename} " + "*" * (77 - len(basename)))
        print("*")
        print(f"* {'job name':>11}: {job_name:<11}")
        print("*")
        print(f"* {'status':>11}: {status:<11}")
        print("*")
        if status != "Completed":
            print(failure_reason)
            failures[notebook] = failure_reason

    print("\n" * 2)
    print("-" * 70)
    if len(failures) > 0:
        raise Exception(
            "One or more notebooks failed to execute. Please see above for error messages. "
            "If you need more information, please see the CloudWatch logs for the corresponding Processing job."
        )


if __name__ == "__main__":
    main()
