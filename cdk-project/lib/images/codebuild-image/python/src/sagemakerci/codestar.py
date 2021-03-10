import os
import tempfile

import boto3


def temp_repo_path():
    return os.path.join(tempfile.gettempdir(), "gitrepo")


def pipeline_build():
    return "CODEBUILD_INITIATOR" in os.environ and os.environ["CODEBUILD_INITIATOR"].startswith(
        "codepipeline/"
    )


def pipeline_name():
    if not pipeline_build():
        raise ValueError("not a pipeline build!")

    return os.environ["CODEBUILD_INITIATOR"].replace("codepipeline/", "")


def repository_details():
    # find first github source in the pipeline...
    cp_client = boto3.client("codepipeline")
    pipeline = cp_client.get_pipeline(name=pipeline_name())
    source = [
        act
        for st in pipeline["pipeline"]["stages"]
        for act in st["actions"]
        if act["actionTypeId"]["provider"] == "GitHub"
    ][0]

    # extract repo details
    owner = source["configuration"]["Owner"]
    repo = source["configuration"]["Repo"]
    branch = source["configuration"]["Branch"]

    return (owner, repo, branch)


def codebuild_source_dir():
    return os.environ.get("CODEBUILD_SRC_DIR")


def resolved_source_version():
    return os.environ.get("CODEBUILD_RESOLVED_SOURCE_VERSION")
