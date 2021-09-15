#!/usr/bin/env python3
import argparse
import os
import sys
import time

import pandas as pd
from notebooks import kernels, parse
from notebooks.run import execute_notebook, get_output_prefix, upload_notebook
from notebooks.utils import default_bucket, ensure_session, kms_key


def parse_args(args):
    parser = argparse.ArgumentParser(os.path.basename(__file__))
    parser.set_defaults(func=lambda x: parser.print_usage())
    parser.add_argument("--instance", help="Instance type", type=str, required=False)

    parsed = parser.parse_args(args)

    return parsed


def save_csv_to_s3(notebooks, job_names, kernels):
    session = ensure_session()

    df = pd.DataFrame({"filename": notebooks, "processing-job-name": job_names, "kernel": kernels})

    csv_name = f"{time.strftime('%Y-%m-%d-%H-%M-%S', time.gmtime())}.csv"
    df.to_csv(csv_name, index=False)

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

    notebook_names = parse.all_notebook_filenames()
    job_names = []
    kernel_names = []

    session = ensure_session()
    instance_type = args.instance or "ml.m5.xlarge"
    for notebook in notebook_names:
        if parse.is_notebook_skipped(notebook):
            job_name = None
        else:
            image = kernels.kernel_image_for(notebook)
            s3path = upload_notebook(notebook, session)
            parameters = {"kms_key": kms_key()}
            job_name = execute_notebook(
                image=image,
                input_path=s3path,
                notebook=notebook,
                instance_type=instance_type,
                session=session,
                output_prefix=get_output_prefix(),
                parameters=parameters,
            )
            time.sleep(1)

        print(job_name)
        job_names.append(str(job_name))
        kernel_names.append(kernels.kernel_type_for(notebook))

    print("\n" * 2)
    print("-" * 100)
    print("\n" * 2)
    print(save_csv_to_s3(notebook_names, job_names, kernel_names))


if __name__ == "__main__":
    main()
