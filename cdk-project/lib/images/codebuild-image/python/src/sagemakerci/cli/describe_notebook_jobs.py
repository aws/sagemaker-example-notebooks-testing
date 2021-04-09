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
    df = pd.read_csv(csv_filename)

    statuses = []
    errors = []

    sagemaker = session.client("sagemaker")
    for index, row in df.iterrows():
        job_name = row["processing-job-name"]
        response = sagemaker.describe_processing_job(ProcessingJobName=job_name)
        statuses.append(response["ProcessingJobStatus"])
        errors.append(response.get("FailureReason"))
        time.sleep(1)

    df["status"] = statuses
    df["error"] = errors

    print("\n" * 2)
    print("-" * 100)
    print("\n" * 2)
    print(save_csv_to_s3(df, csv_filename))


if __name__ == "__main__":
    main()
