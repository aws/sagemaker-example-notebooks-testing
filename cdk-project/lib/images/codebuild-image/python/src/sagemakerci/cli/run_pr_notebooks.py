#!/usr/bin/env python3
import argparse
import os
import sys
import time

from github import Github
from sagemakerci import kernels, parse_notebook
from sagemakerci.git import Git
from sagemakerci.run_notebook import (
    ensure_session,
    execute_notebook,
    get_output_prefix,
    is_running,
    upload_notebook,
    wait_for_complete,
)


def parse_args(args):
    parser = argparse.ArgumentParser(os.path.basename(__file__))
    parser.set_defaults(func=lambda x: parser.print_usage())
    parser.add_argument("--pr", help="Pull request number", type=int, required=True)
    parser.add_argument("--instance", help="Instance type", type=str, required=False)
    parser.add_argument(
        "--skip-docker",
        default=True,
        help="Skip notebooks that use Docker",
        type=bool,
        required=False,
    )

    parsed = parser.parse_args(args)
    if not parsed.pr:
        parser.error("--pr required")

    return parsed


def notebook_filenames(pr_num):
    g = Github(Git().oauth_token)
    repo = g.get_repo("aws/amazon-sagemaker-examples")
    pr = repo.get_pull(pr_num)
    return filter(parse_notebook.is_notebook, [file.filename for file in pr.get_files()])


def main():
    args = parse_args(sys.argv[1:])

    jobs = {}

    session = ensure_session()
    instance_type = args.instance or "ml.m5.xlarge"
    for notebook in notebook_filenames(args.pr):
        if args.skip_docker and parse_notebook.contains_code(
            notebook, ["docker ", 'instance_type = "local"']
        ):
            job_name = None
        else:
            image = kernels.kernel_image_for(notebook)
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
                print(f"* {'kernel':>11}: {kernels.kernel_type_for(notebook):<11}")
                print("*")
                print(f"* {'status':>11}: {status:<11}")
                print("*")
                if status != "Completed":
                    print(failure_reason)
                    if status != "Skipped":
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
