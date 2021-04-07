#!/usr/bin/env python3
import argparse
import os
import sys
import time

from pathlib import Path

import pandas as pd

from sagemakerci.run_notebook import (
    ensure_session,
    get_output_prefix,
    upload_notebook,
    execute_notebook,
)
from sagemakerci.cli.run_pr_notebooks import is_notebook, kernel_image_for, kernel_type_for
from sagemakerci.utils import default_bucket


def parse_args(args):
    parser = argparse.ArgumentParser(os.path.basename(__file__))
    parser.set_defaults(func=lambda x: parser.print_usage())
    parser.add_argument("--instance", help="Instance type", type=str, required=False)

    parsed = parser.parse_args(args)

    return parsed


def notebook_filenames():
    return [str(filename) for filename in Path(".").rglob("*.ipynb")]


def save_csv_to_s3(notebooks, job_names, kernels):
    session = ensure_session()

    df = pd.DataFrame({"filename": notebooks, "processing-job-name": job_names, "kernel": kernels})

    csv_name = f"{time.strftime('%Y-%m-%d-%H-%M-%S', time.gmtime())}.csv"
    df.to_csv(csv_name)

    s3 = session.client("s3")
    bucket = default_bucket(session)
    prefix = "full_repo_scan"

    s3_path = os.path.join(prefix, csv_name)
    try:
        s3.head_object(Bucket=bucket, Key=s3_path)
    except:
        s3.upload_file(csv_name, bucket, s3_path)

    return f"s3://{bucket}/{prefix}/{csv_name}"


def main():
    args = parse_args(sys.argv[1:])

    notebooks = notebook_filenames()
    job_names = []
    kernels = []

    session = ensure_session()
    instance_type = args.instance or "ml.m5.xlarge"
    for notebook in notebooks:
        image = kernel_image_for(notebook)
        s3path = upload_notebook(notebook, session)
        job_name = execute_notebook(
            image=image,
            input_path=s3path,
            notebook=notebook,
            instance_type=instance_type,
            session=session,
            output_prefix=get_output_prefix(),
            parameters={},
        )

        print(job_name)
        job_names.append(job_name)
        kernels.append(kernel_type_for(notebook))

    print("\n" * 2)
    print("-" * 100)
    print("\n" * 2)
    print(save_csv_to_s3(notebooks, job_names, kernels))


if __name__ == "__main__":
    main()
