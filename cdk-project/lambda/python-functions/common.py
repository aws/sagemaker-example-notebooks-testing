import logging
import os

import boto3

CHANGE_CONTROL_TABLE = "CHANGE_CONTROL_TABLE"


def get_logger():
    """Configure logging and return a logger object.
    Meant to be called once at module load time.
    """
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    logging.getLogger("boto3").setLevel(logging.ERROR)
    logging.getLogger("botocore").setLevel(logging.ERROR)

    return logger


def get_artifact_bucket():
    return os.environ["ARTIFACT_BUCKET"]


def get_github_oauth_token(secrets_client):
    secret_id = os.environ["OAUTH_SECRET_ID"]
    return secrets_client.get_secret_value(SecretId=secret_id)["SecretString"]
