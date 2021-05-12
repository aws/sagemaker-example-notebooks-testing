#!/usr/bin/env python3
import argparse
import os
import sys
import time

from datetime import datetime
from pathlib import Path

import pandas as pd

from sagemakerci.run_notebook import (
    ensure_session,
    get_output_prefix,
    upload_notebook,
    execute_notebook,
    get_output_notebook,
)
from sagemakerci.utils import default_bucket


def parse_args(args):
    parser = argparse.ArgumentParser(os.path.basename(__file__))
    parser.set_defaults(func=lambda x: parser.print_usage())
    parser.add_argument("--csv", help="CSV file with Processing job names", type=str, required=True)

    parsed = parser.parse_args(args)

    return parsed


def notebook_filenames():
    return list(Path(".").rglob("*.ipynb"))


def save_csv_to_s3(df, csv_name):
    session = ensure_session()

    df.to_csv(csv_name, index=False)

    s3 = session.client("s3")
    bucket = default_bucket(session)
    prefix = "full_repo_scan"

    s3_path = os.path.join(prefix, csv_name)
    s3.upload_file(csv_name, bucket, s3_path)

    return f"s3://{bucket}/{prefix}/{csv_name}"


def main():
    args = parse_args(sys.argv[1:])

    session = ensure_session()

    csv_filename = args.csv
    df = pd.read_csv(csv_filename, index_col=False)

    output_notebooks = []
    runtimes = []
    statuses = []
    errors = []

    sagemaker = session.client("sagemaker")
    for index, row in df.iterrows():
        job_name = row["processing-job-name"]
        if job_name == "None":
            uri = "None"
            runtime = 0
            status = "Skipped"
            error = "This notebook was skipped because it either uses Docker or Local Mode."
        else:
            response = sagemaker.describe_processing_job(ProcessingJobName=job_name)
            notebook, uri = get_output_notebook(job_name, session)
            runtime = (
                response.get("ProcessingEndTime", datetime.now())
                - response.get("ProcessingStartTime")
            ).total_seconds()
            status = response.get("ProcessingJobStatus")
            error = response.get("ExitMessage")

        output_notebooks.append(uri)
        runtimes.append(runtime)
        statuses.append(status)
        errors.append(error)

        print(job_name)
        time.sleep(1)

    df["output notebook"] = output_notebooks
    df["runtime"] = runtimes
    df["status"] = statuses
    df["error"] = errors

    print("\n" * 2)
    print("-" * 100)
    print("\n" * 2)
    print(save_csv_to_s3(df, csv_filename))


if __name__ == "__main__":
    main()
