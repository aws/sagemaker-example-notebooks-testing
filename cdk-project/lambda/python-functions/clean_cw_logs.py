import datetime
import os
import time

import boto3
import common

logger = common.get_logger()

# lambda sets these as environment variables
MAXIMUM_LOG_GROUP_AGE = int(os.environ["MAX_LOG_GROUP_AGE_IN_MINUTES"])
REGION = os.environ["AWS_REGION"]


def get_log_groups(client, next_token, max_age_millis):
    current_time = time.time() * 1000
    request = {"logGroupNamePrefix": "/aws/sagemaker/Endpoints", "limit": 50}

    if next_token:
        request["nextToken"] = next_token

    response = client.describe_log_groups(**request)
    group_names = [
        lg["logGroupName"]
        for lg in response["logGroups"]
        if current_time - lg["creationTime"] > max_age_millis
    ]

    next_token = response.get("nextToken", None)
    return group_names, next_token


def delete_log_groups(client, group_names):
    for group_name in group_names:
        logger.info("Deleting %s", group_name)
        client.delete_log_group(logGroupName=group_name)
        logger.info("Deleted")
        time.sleep(0.5)


def lambda_handler(event, context):  # pylint: disable=unused-argument
    logger.info("Invoking log groups cleanup at %s...", event["time"])
    logger.info("Searching for log groups older than %s minutes", MAXIMUM_LOG_GROUP_AGE)
    max_age_millis = MAXIMUM_LOG_GROUP_AGE * 60 * 1000

    try:
        client = boto3.client("logs", region_name=REGION)
        next_token = None
        more = True
        while more:
            group_names, next_token = get_log_groups(client, next_token, max_age_millis)
            logger.info("Found %s items, deleting now", len(group_names))
            delete_log_groups(client, group_names)
            more = next_token is not None
            time.sleep(1)
    finally:
        logger.info("Finished at %s", str(datetime.datetime.now()))
