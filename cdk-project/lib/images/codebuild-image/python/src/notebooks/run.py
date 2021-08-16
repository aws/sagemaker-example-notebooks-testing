# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"). You
# may not use this file except in compliance with the License. A copy of
# the License is located at
#
#     http://aws.amazon.com/apache2.0/
#
# or in the "license" file accompanying this file. This file is
# distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF
# ANY KIND, either express or implied. See the License for the specific
# language governing permissions and limitations under the License.
"""Run a notebook on demand or on a schedule using Amazon SageMaker Processing Jobs"""

import asyncio
import errno
import io
import json
import logging
import os
import re
import time
from shlex import split
from subprocess import Popen

import boto3
import botocore
from notebooks.utils import default_bucket, ensure_session, get_execution_role

abbrev_image_pat = re.compile(
    r"(?P<account>\d+).dkr.ecr.(?P<region>[^.]+).amazonaws.com/(?P<image>[^:/]+)(?P<tag>:[^:]+)?"
)


def describe(job_name, session):
    """Get the status and exit message for a Processing job.

    Args:
        job_name (str):
        session:

    Returns:
        (str, str): A tuple with the status and the exit message.

    """
    session = ensure_session(session)
    client = session.client("sagemaker")
    response = client.describe_processing_job(ProcessingJobName=job_name)
    return response["ProcessingJobStatus"], response.get("ExitMessage")


def is_running(job_name, session):
    """Check whether a Processing job is still running.

    Args:
        job_name (str):
        session:

    Returns:
        bool: Whether the Processing job is running.

    """
    if not job_name:
        return False
    status, failure_reason = describe(job_name, session)
    if status in ("InProgress", "Stopping"):
        return True
    return False


def abbreviate_image(image):
    """If the image belongs to this account, just return the base name"""
    m = abbrev_image_pat.fullmatch(image)
    if m:
        tag = m.group("tag")
        if tag == None or tag == ":latest":
            tag = ""
        return m.group("image") + tag
    else:
        return image


abbrev_role_pat = re.compile(r"arn:aws:iam::(?P<account>\d+):role/(?P<name>[^/]+)")


def abbreviate_role(role):
    """If the role belongs to this account, just return the base name"""
    m = abbrev_role_pat.fullmatch(role)
    if m:
        return m.group("name")
    else:
        return role


def upload_notebook(notebook, session=None):
    """Uploads a notebook to S3 in the default SageMaker Python SDK bucket for
    this user. The resulting S3 object will be named "s3://<bucket>/papermill-input/notebook-YYYY-MM-DD-hh-mm-ss.ipynb".

    Args:
      notebook (str):
        The filename of the notebook you want to upload. (Required)
      session (boto3.Session):
        A boto3 session to use. Will create a default session if not supplied. (Default: None)

    Returns:
      The resulting object name in S3 in URI format.
    """
    session = ensure_session(session)
    s3 = session.client("s3")
    bucket = default_bucket(session)
    prefix = f"papermill_input/{time.strftime('%Y-%m-%d-%H-%M-%S', time.gmtime())}"

    directory, nb_filename = os.path.split(notebook)
    for root, dirs, files in os.walk(directory, followlinks=True):
        for filename in files:
            local_path = os.path.join(root, filename)
            relative_path = os.path.relpath(local_path, directory)
            s3_path = os.path.join(prefix, relative_path)
            try:
                s3.head_object(Bucket=bucket, Key=s3_path)
            except:
                s3.upload_file(local_path, bucket, s3_path)

    return f"s3://{bucket}/{prefix}/"


def upload_fileobj(notebook_fileobj, session=None):
    """Uploads a file object to S3 in the default SageMaker Python SDK bucket for
    this user. The resulting S3 object will be named "s3://<bucket>/papermill-input/notebook-YYYY-MM-DD-hh-mm-ss.ipynb".

    Args:
      notebook_fileobj (fileobj):
        A file object (as returned from open) that is reading from the notebook you want to upload. (Required)
      session (boto3.Session):
        A boto3 session to use. Will create a default session if not supplied. (Default: None)

    Returns:
      The resulting object name in S3 in URI format.
    """

    session = ensure_session(session)
    snotebook = f"notebook-{time.strftime('%Y-%m-%d-%H-%M-%S', time.gmtime())}.ipynb"

    s3 = session.client("s3")
    key = "papermill_input/" + snotebook
    bucket = default_bucket(session)
    s3path = f"s3://{bucket}/{key}"
    s3.upload_fileobj(notebook_fileobj, bucket, key)

    return s3path


def get_output_prefix():
    """Returns an S3 prefix in the Python SDK default bucket."""
    return f"s3://{default_bucket()}/papermill_output"


def execute_notebook(
    *,
    image,
    input_path,
    output_prefix,
    notebook,
    parameters,
    role=None,
    instance_type,
    session,
):
    session = ensure_session(session)

    if not role:
        role = get_execution_role(session)
    elif "/" not in role:
        account = session.client("sts").get_caller_identity()["Account"]
        role = f"arn:aws:iam::{account}:role/{role}"

    if "/" not in image:
        account = session.client("sts").get_caller_identity()["Account"]
        region = session.region_name
        image = f"{account}.dkr.ecr.{region}.amazonaws.com/{image}:latest"

    if notebook is None:
        notebook = input_path

    base = os.path.basename(notebook)
    nb_name, nb_ext = os.path.splitext(base)
    timestamp = time.strftime("%Y-%m-%d-%H-%M-%S", time.gmtime())

    job_name = (
        ("papermill-" + re.sub(r"[^-a-zA-Z0-9]", "-", nb_name))[: 62 - len(timestamp)]
        + "-"
        + timestamp
    )
    input_directory = "/opt/ml/processing/input/"
    local_input = os.path.join(input_directory, os.path.basename(notebook))
    result = f"{nb_name}-{timestamp}{nb_ext}"
    local_output = "/opt/ml/processing/output/"

    api_args = {
        "ProcessingInputs": [
            {
                "InputName": "notebook",
                "S3Input": {
                    "S3Uri": input_path,
                    "LocalPath": input_directory,
                    "S3DataType": "S3Prefix",
                    "S3InputMode": "File",
                    "S3DataDistributionType": "FullyReplicated",
                },
            },
        ],
        "ProcessingOutputConfig": {
            "Outputs": [
                {
                    "OutputName": "result",
                    "S3Output": {
                        "S3Uri": output_prefix,
                        "LocalPath": local_output,
                        "S3UploadMode": "EndOfJob",
                    },
                },
            ],
        },
        "ProcessingJobName": job_name,
        "ProcessingResources": {
            "ClusterConfig": {
                "InstanceCount": 1,
                "InstanceType": instance_type,
                "VolumeSizeInGB": 40,
            }
        },
        "StoppingCondition": {"MaxRuntimeInSeconds": 7200},
        "AppSpecification": {
            "ImageUri": image,
            "ContainerArguments": [
                "run_notebook",
            ],
        },
        "RoleArn": role,
        "Environment": {},
    }

    api_args["Environment"]["PAPERMILL_INPUT"] = local_input
    api_args["Environment"]["PAPERMILL_OUTPUT"] = local_output + result
    api_args["Environment"]["PAPERMILL_kernel"] = local_output + result
    if os.environ.get("AWS_DEFAULT_REGION") != None:
        api_args["Environment"]["AWS_DEFAULT_REGION"] = os.environ["AWS_DEFAULT_REGION"]
    api_args["Environment"]["PAPERMILL_PARAMS"] = json.dumps(parameters)
    api_args["Environment"]["PAPERMILL_NOTEBOOK_NAME"] = notebook

    client = boto3.client("sagemaker")
    result = client.create_processing_job(**api_args)
    job_arn = result["ProcessingJobArn"]
    job = re.sub("^.*/", "", job_arn)
    return job


def wait_for_complete(job_name, progress=True, sleep_time=10, session=None):
    """Wait for a notebook execution job to complete.

    Args:
      job_name (str):
        The name of the SageMaker Processing Job executing the notebook. (Required)
      progress (boolean):
        If True, print a period after every poll attempt. (Default: True)
      sleep_time (int):
        The number of seconds between polls. (Default: 10)
      session (boto3.Session):
        A boto3 session to use. Will create a default session if not supplied. (Default: None)

    Returns:
      A tuple with the job status and the failure message if any.
    """

    session = ensure_session(session)
    client = session.client("sagemaker")
    done = False
    while not done:
        if progress:
            print(".", end="")
        desc = client.describe_processing_job(ProcessingJobName=job_name)
        status = desc["ProcessingJobStatus"]
        if status != "InProgress":
            done = True
        else:
            time.sleep(sleep_time)
    if progress:
        print()
    return status, desc.get("ExitMessage")


def get_output_notebook(job_name, session=None):
    """Get the name and S3 uri for an output notebook from a previously completed job.

    Args:
      job_name (str): The name of the SageMaker Processing Job that executed the notebook. (Required)
      session (boto3.Session):
        A boto3 session to use. Will create a default session if not supplied. (Default: None)

    Returns:
        (str, str): A tuple with the notebook name and S3 uri to the output notebook.
    """
    session = ensure_session(session)
    client = session.client("sagemaker")
    desc = client.describe_processing_job(ProcessingJobName=job_name)

    prefix = desc["ProcessingOutputConfig"]["Outputs"][0]["S3Output"]["S3Uri"]
    notebook = os.path.basename(desc["Environment"]["PAPERMILL_OUTPUT"])
    return notebook, f"{prefix}/{notebook}"


def download_notebook(job_name, output=".", session=None):
    """Download the output notebook from a previously completed job.

    Args:
      job_name (str): The name of the SageMaker Processing Job that executed the notebook. (Required)
      output (str): The directory to copy the output file to. (Default: the current working directory)
      session (boto3.Session):
        A boto3 session to use. Will create a default session if not supplied. (Default: None)

    Returns:
      The filename of the downloaded notebook.
    """
    notebook, s3path = get_output_notebook(job_name, session)

    if not os.path.exists(output):
        try:
            os.makedirs(output)
        except OSError as e:
            if e.errno != errno.EEXIST:
                raise

    p1 = Popen(split(f"aws s3 cp --no-progress {s3path} {output}/"))
    p1.wait()
    return f"{output.rstrip('/')}/{notebook}"


def run_notebook(
    image,
    notebook,
    parameters={},
    role=None,
    instance_type="ml.m5.large",
    output_prefix=None,
    output=".",
    session=None,
):
    """Run a notebook in SageMaker Processing producing a new output notebook.

    Args:
        image (str): The ECR image that defines the environment to run the job (required).
        notebook (str): The local notebook to upload and run (required).
        parameters (dict): The dictionary of parameters to pass to the notebook (default: {}).
        role (str): The name of a role to use to run the notebook (default: calls get_execution_role()).
        instance_type (str): The SageMaker instance to use for executing the job (default: ml.m5.large).
        output_prefix (str): The prefix path in S3 for where to store the output notebook
                             (default: determined based on SageMaker Python SDK)
        output (str): The directory to copy the output file to (default: the current working directory).
        session (boto3.Session): The boto3 session to use. Will create a default session if not supplied (default: None).

    Returns:
        A tuple with the processing job name, the job status, the failure reason (or None) and the the path to
        the result notebook. The output notebook name is formed by adding a timestamp to the original notebook name.
    """
    session = ensure_session(session)
    if output_prefix is None:
        output_prefix = get_output_prefix()
    s3path = upload_notebook(notebook, session)
    job_name = execute_notebook(
        image=image,
        input_path=s3path,
        output_prefix=output_prefix,
        notebook=notebook,
        parameters=parameters,
        role=role,
        instance_type=instance_type,
        session=session,
    )
    print(f"Job {job_name} started")
    status, failure_reason = wait_for_complete(job_name)
    if status == "Completed":
        local = download_notebook(job_name, output=output)
    else:
        local = None
    return (job_name, status, local, failure_reason)


def stop_run(job_name, session=None):
    """Stop the named processing job

    Args:
       job_name (string): The name of the job to stop
       session (boto3.Session): The boto3 session to use. Will create a default session if not supplied (default: None)."""
    session = ensure_session(session)
    client = session.client("sagemaker")
    client.stop_processing_job(ProcessingJobName=job_name)


def describe_runs(n=0, notebook=None, rule=None, session=None):
    """Returns a generator of descriptions for all the notebook runs. See :meth:`describe_run` for details of
    the description.

    Args:
       n (int): The number of runs to return or all runs if 0 (default: 0)
       notebook (str): If not None, return only runs of this notebook (default: None)
       rule (str): If not None, return only runs invoked by this rule (default: None)
       session (boto3.Session): The boto3 session to use. Will create a default session if not supplied (default: None).
    """
    session = ensure_session(session)
    client = session.client("sagemaker")
    paginator = client.get_paginator("list_processing_jobs")
    page_iterator = paginator.paginate(NameContains="papermill-")

    for page in page_iterator:
        for item in page["ProcessingJobSummaries"]:
            job_name = item["ProcessingJobName"]
            if not job_name.startswith("papermill-"):
                continue
            d = describe_run(job_name, session)

            if notebook != None and notebook != d["Notebook"]:
                continue
            if rule != None and rule != d["Rule"]:
                continue
            yield d

            if n > 0:
                n = n - 1
                if n == 0:
                    return


def describe_run(job_name, session=None):
    """Describe a particular notebook run.

    Args:
     job_name (str): The name of the processing job that ran the notebook.

    Returns:
      A dictionary with keys for each element of the job description. For example::

      {'Notebook': 'scala-spark-test.ipynb',
       'Rule': '',
       'Parameters': '{"input": "s3://notebook-testing/const.txt"}',
       'Job': 'papermill-scala-spark-test-2020-10-21-20-00-11',
       'Status': 'Completed',
       'Failure': None,
       'Created': datetime.datetime(2020, 10, 21, 13, 0, 12, 817000, tzinfo=tzlocal()),
       'Start': datetime.datetime(2020, 10, 21, 13, 4, 1, 58000, tzinfo=tzlocal()),
       'End': datetime.datetime(2020, 10, 21, 13, 4, 55, 710000, tzinfo=tzlocal()),
       'Elapsed': datetime.timedelta(seconds=54, microseconds=652000),
       'Result': 's3://sagemaker-us-west-2-1234567890/papermill_output/scala-spark-test-2020-10-21-20-00-11.ipynb',
       'Input': 's3://sagemaker-us-west-2-1234567890/papermill_input/notebook-2020-10-21-20-00-08.ipynb',
       'Image': 'spark-scala-notebook-runner',
       'Instance': 'ml.m5.large',
       'Role': 'BasicExecuteNotebookRole-us-west-2'}
    """
    session = ensure_session(session)
    client = session.client("sagemaker")

    while True:
        try:
            desc = client.describe_processing_job(ProcessingJobName=job_name)
            break
        except botocore.exceptions.ClientError as e:
            if e.response["Error"]["Code"] == "ThrottlingException":
                time.sleep(1)
            else:
                raise e

    status = desc["ProcessingJobStatus"]
    if status == "Completed":
        output_prefix = desc["ProcessingOutputConfig"]["Outputs"][0]["S3Output"]["S3Uri"]
        notebook_name = os.path.basename(desc["Environment"]["PAPERMILL_OUTPUT"])
        result = f"{output_prefix}/{notebook_name}"
    else:
        result = None

    if status == "Failed":
        failure = desc["ExitMessage"]
    else:
        failure = None

    d = {}
    d["Notebook"] = desc["Environment"].get("PAPERMILL_NOTEBOOK_NAME", "")
    d["Rule"] = desc["Environment"].get("AWS_EVENTBRIDGE_RULE", "")
    d["Parameters"] = desc["Environment"].get("PAPERMILL_PARAMS", "")
    d["Job"] = job_name
    d["Status"] = status
    d["Failure"] = failure
    d["Created"] = desc["CreationTime"]
    d["Start"] = desc.get("ProcessingStartTime")
    d["End"] = desc.get("ProcessingEndTime")
    elapsed = None
    if d.get("Start") is not None and d.get("End") is not None:
        elapsed = d["End"] - d["Start"]
    d["Elapsed"] = elapsed
    d["Result"] = result
    d["Input"] = desc["ProcessingInputs"][0]["S3Input"]["S3Uri"]
    d["Image"] = abbreviate_image(desc["AppSpecification"]["ImageUri"])
    d["Instance"] = desc["ProcessingResources"]["ClusterConfig"]["InstanceType"]
    d["Role"] = abbreviate_role(desc["RoleArn"])

    return d


def expand_params(params):
    try:
        param_map = json.loads(params)
        return ", ".join([f"{p}={v}" for p, v in param_map.items()])
    except Exception:
        return ""


class NewJobs:
    def __init__(self, client):
        self.client = client
        self.latest_seen_job = None
        self.next_latest_seen_job = None

    async def get_new(self):
        next_token = None
        if self.next_latest_seen_job != None:
            self.latest_seen_job = self.next_latest_seen_job
            self.next_latest_seen_job = None
        while True:
            args = {"NextToken": next_token} if next_token else {}
            while True:
                try:
                    await asyncio.sleep(0)
                    result = self.client.list_processing_jobs(MaxResults=30, **args)
                    break
                except botocore.exceptions.ClientError as e:
                    if e.response["Error"]["Code"] == "ThrottlingException":
                        time.sleep(1)
                    else:
                        raise e
            jobs = result["ProcessingJobSummaries"]
            for job in jobs:
                if not self.next_latest_seen_job:
                    self.next_latest_seen_job = job["ProcessingJobName"]
                if job["ProcessingJobName"] == self.latest_seen_job:
                    return
                yield job
            next_token = result.get("NextToken")
            if not next_token:
                break


class NotebookRunTracker:
    """
    NotebookRunTracker keeps track of many recent running jobs and optimizes the number of boto calls
    you're doing to get the status by remembering previous runs and knowing that only in progress jobs can
    change status (and therefore need to be polled).
    """

    # We store the list backwards from how it's viewed outside so that we can just append new jobs on
    # the end.
    def __init__(self, max_jobs=20, session=None, log=None):
        self.session = ensure_session(session)
        self.client = self.session.client("sagemaker")
        self.log = log or logging.getLogger(__name__)
        self.max_jobs = max_jobs

        self.new_jobs = NewJobs(self.client)
        self.run_list = []
        self.in_progress = {}

    def __getitem__(self, item):
        return self.run_list[::-1][item]

    def __len__(self):
        return len(self.run_list)

    async def update_list(self):
        list_count = 0
        new_runs = []
        async for job in self.new_jobs.get_new():
            job_name = job["ProcessingJobName"]
            if not job_name.startswith("papermill-"):
                continue
            await asyncio.sleep(0)
            self.log.debug(f"Describing new job: {job_name}")
            desc = describe_run(job_name, session=self.session)
            new_runs.append(desc)
            if desc["Status"] == "InProgress" or desc["Status"] == "Stopping":
                self.in_progress[job_name] = desc
            list_count += 1
            if list_count >= self.max_jobs:
                break
        self.run_list.extend(new_runs[::-1])
        if len(self.run_list) > self.max_jobs:
            trimlen = len(self.run_list) - self.max_jobs
            for r in self.run_list[:trimlen]:
                if r["Status"] == "InProgress" or r["Status"] == "Stopping":
                    if r["Job"] in self.in_progress:
                        del self.in_progress[r["Job"]]
            self.run_list = self.run_list[trimlen:]

    async def update_in_progress(self):
        for job, desc in list(self.in_progress.items()):
            await asyncio.sleep(0)
            self.log.debug(f"Describing in progress job: {job}")
            new_desc = describe_run(job, session=self.session)
            desc["Status"] = new_desc["Status"]
            desc["Failure"] = new_desc["Failure"]
            desc["Start"] = new_desc["Start"]
            desc["End"] = new_desc["End"]
            desc["Elapsed"] = new_desc["Elapsed"]
            desc["Result"] = new_desc["Result"]

            if not (new_desc["Status"] == "InProgress" or new_desc["Status"] == "Stopping"):
                if (
                    job in self.in_progress
                ):  # because of the asyncio it's posssible for us to race here
                    del self.in_progress[job]

    async def update(self):
        await self.update_list()
        await self.update_in_progress()


def list_runs(n=0, notebook=None, rule=None, session=None):
    """Returns a pandas data frame of the runs, with the most recent at the top.

    Args:
        n (int): The number of runs to return or all runs if 0 (default: 0)
        notebook (str): If not None, return only runs of this notebook (default: None)
        rule (str): If not None, return only runs invoked by this rule (default: None)
        session (boto3.Session): The boto3 session to use. Will create a default session if not supplied (default: None).
    """
    import pandas as pd  # pylint: disable=import-error

    df = pd.DataFrame(describe_runs(n=n, notebook=notebook, rule=rule, session=session))
    df["Parameters"] = df["Parameters"].map(expand_params)
    return df


def download_all(lis, output=".", session=None):
    """Download each of the output notebooks from a list previously completed jobs.

    Args:
      lis (list, pandas.Series, or pandas.DataFrame): A list of jobs or a pandas DataFrame with a "Job" column (as returned by :meth:`list_runs`). (Required)
      output (str): The directory to copy the output files to. (Default: the current working directory)
      session (boto3.Session):
        A boto3 session to use. Will create a default session if not supplied. (Default: None)

    Returns:
      The list of the filenames of the downloaded notebooks.
    """
    import pandas as pd  # pylint: disable=import-error

    if isinstance(lis, pd.DataFrame):
        lis = list(lis["Job"])
    elif isinstance(lis, pd.Series):
        lis = list(lis)

    session = ensure_session(session)
    return [download_notebook(job, output, session) for job in lis]
