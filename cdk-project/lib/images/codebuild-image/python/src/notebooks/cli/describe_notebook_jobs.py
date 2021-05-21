#!/usr/bin/env python3
import argparse
import os
import sys
import time
from datetime import datetime, timezone

import pandas as pd
from notebooks.run import execute_notebook, get_output_notebook, get_output_prefix, upload_notebook
from notebooks.utils import default_bucket, ensure_session


def parse_args(args):
    parser = argparse.ArgumentParser(os.path.basename(__file__))
    parser.set_defaults(func=lambda x: parser.print_usage())
    parser.add_argument("--csv", help="CSV file with Processing job names", type=str, required=True)

    parsed = parser.parse_args(args)

    return parsed


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
    dataframe = pd.read_csv(csv_filename, index_col=False)

    output_notebooks = []
    runtimes = []
    statuses = []
    errors = []
    dates = []

    sagemaker = session.client("sagemaker")
    for index, row in dataframe.iterrows():
        job_name = row["processing-job-name"]
        if job_name == "None":
            uri = "None"
            runtime = 0
            status = "Skipped"
            error = "UsesDocker"
            date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        else:
            response = sagemaker.describe_processing_job(ProcessingJobName=job_name)
            date = response.get("ProcessingEndTime", datetime.now(timezone.utc)).strftime(
                "%Y-%m-%d"
            )
            notebook, uri = get_output_notebook(job_name, session)
            status = response.get("ProcessingJobStatus")

            runtime = (
                response.get("ProcessingEndTime", datetime.now(timezone.utc))
                - response.get("ProcessingStartTime", datetime.now(timezone.utc))
            ).total_seconds()
            if runtime < 0:
                runtime = 0

            error = response.get("ExitMessage")
            if error == "Kernel died":
                error = "KernelDied"
            elif error:
                found_error_type = False
                valid_error_types = ("Exception:", "Error:", "InvalidArn:", "NotFound:", "InUse:")
                lines = error.splitlines()
                for line in reversed(lines):
                    if any(error_type in line for error_type in valid_error_types):
                        error = line.split(":", 1)[0]
                        found_error_type = True
                        break
                if not found_error_type:
                    error = "Uncategorized"

            if status == "Stopped":
                error = "TimedOut"

        output_notebooks.append(uri)
        runtimes.append(runtime)
        statuses.append(status)
        errors.append(error)
        dates.append(date)

        print(job_name)
        time.sleep(1)

    new_dataframe = pd.DataFrame(
        {
            "date": dates,
            "filename": dataframe["filename"],
            "processing-job-name": dataframe["processing-job-name"],
            "kernel": dataframe["kernel"],
            "output": output_notebooks,
            "runtime": runtimes,
            "status": statuses,
            "error": errors,
        }
    )

    print("\n" * 2)
    print("-" * 100)
    print("\n" * 2)
    print(save_csv_to_s3(new_dataframe, csv_filename))


if __name__ == "__main__":
    main()
