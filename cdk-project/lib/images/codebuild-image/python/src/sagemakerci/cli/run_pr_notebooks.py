#!/usr/bin/env python3
import argparse
import json
import os
import sys

from sagemakerci.run_notebook import run_notebook

from github import Github


def parse_args(args):
    parser = argparse.ArgumentParser(os.path.basename(__file__))
    parser.set_defaults(func=lambda x: parser.print_usage())
    parser.add_argument("--pr", help="Pull request number", type=int, required=True)
    parser.add_argument("--image", help="Pull request number", type=str, required=False)
    parser.add_argument("--instance", help="Pull request number", type=str, required=False)

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


def main():
    args = parse_args(sys.argv[1:])

    results = {}

    image = args.image or "521695447989.dkr.ecr.us-west-2.amazonaws.com/papermill-processing:latest"
    instance_type = args.instance or "ml.m5.xlarge"
    for notebook in notebook_filenames(args.pr):
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