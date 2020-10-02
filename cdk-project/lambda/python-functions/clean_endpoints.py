import datetime
import os
import subprocess
import sys
import time

subprocess.check_call(["pip", "install", "--upgrade", "botocore", "--target", "/tmp/"])
subprocess.check_call(["pip", "install", "--upgrade", "boto3", "--target", "/tmp/"])
sys.path.insert(0, "/tmp/")
# pylint: disable=wrong-import-position
import botocore
import boto3
from botocore.exceptions import ClientError

import common

logger = common.get_logger()

DEFAULT_SLEEP_TIME_SECONDS = 10
LIST_MAX_RESULT_COUNT = 100
# lambda sets these as environment variables
MAXIMUM_ENDPOINT_AGE = os.environ["MAX_ENDPOINT_AGE_IN_MINUTES"]
REGION = os.environ["AWS_REGION"]


def retries(max_retry_count, exception_message_prefix, seconds_to_sleep=DEFAULT_SLEEP_TIME_SECONDS):
    """Retries until max retry count is reached.

    Args:
        max_retry_count (int): The retry count.
        exception_message_prefix (str): The message to include in the exception on failure.
        seconds_to_sleep (int): The number of seconds to sleep between executions.

    """
    for i in range(max_retry_count):
        yield i
        time.sleep(seconds_to_sleep)

    raise Exception(
        "'{}' has reached the maximum retry count of {}".format(
            exception_message_prefix, max_retry_count
        )
    )


def get_resources(client, next_token, before_timestamp, resource_type):
    list_req = {"MaxResults": LIST_MAX_RESULT_COUNT, "CreationTimeBefore": before_timestamp}

    if next_token:
        list_req.update({"NextToken": next_token})
    if resource_type == "MonitoringSchedules":
        response = client.list_monitoring_schedules(**list_req)
        resource_type = "MonitoringScheduleSummaries"
    elif resource_type == "ProcessingJobs":
        response = client.list_processing_jobs(**list_req)
        resource_type = "ProcessingJobSummaries"
    elif resource_type == "Endpoints":
        list_req.update({"StatusEquals": "InService"})
        response = client.list_endpoints(**list_req)
    elif resource_type == "EndpointConfigs":
        response = client.list_endpoint_configs(**list_req)
    elif resource_type == "Experiments":
        response = client.list_experiments(
            MaxResults=LIST_MAX_RESULT_COUNT, CreatedBefore=before_timestamp
        )
        resource_type = "ExperimentSummaries"
    resources = response[resource_type]
    new_next = response.get("NextToken", None)
    return resources, new_next


def stop_resources(client, resource_names, resource_type):
    stopped_all_resources = True
    for resource_name in resource_names:
        logger.info("Stopping %s", resource_name)
        if resource_type == "MonitoringSchedules":
            try:
                client.stop_monitoring_schedule(MonitoringScheduleName=resource_name)
            except Exception:  # pylint: disable=broad-except
                logger.exception("Unable to stop monitoring schedule")
                stopped_all_resources = False
            for _ in retries(60, "Waiting for Monitoring Schedules to stop", seconds_to_sleep=5):
                status = client.describe_monitoring_schedule(MonitoringScheduleName=resource_name)[
                    "MonitoringScheduleStatus"
                ]
                if status in {"Stopped", "Failed", "Completed"}:
                    break
        if resource_type == "ProcessingJobs":
            try:
                client.stop_processing_job(ProcessingJobName=resource_name)
            except Exception:  # pylint: disable=broad-except
                logger.exception("Unable to stop processing job")
                stopped_all_resources = False
            for _ in retries(60, "Waiting for Processing Jobs to stop", seconds_to_sleep=5):
                status = client.describe_processing_job(ProcessingJobName=resource_name)[
                    "ProcessingJobStatus"
                ]
                if status in {"Stopped", "Failed", "Completed"}:
                    break
        logger.info("Stopped %s", resource_name)
        time.sleep(0.5)
    return stopped_all_resources


def batch_stop_resources(client, before_timestamp, resource_type):
    try:
        next_token = None
        more = True
        while more:
            logger.info("Searching for %s from before: %s", resource_type.lower(), before_timestamp)
            resources, next_token = get_resources(
                client, next_token, before_timestamp, resource_type
            )
            logger.info("Found %s items, stopping now", len(resources))
            if resource_type == "MonitoringSchedules":
                resource_names = [resource["MonitoringScheduleName"] for resource in resources]
            elif resource_type == "ProcessingJobs":
                resource_names = [resource["ProcessingJobName"] for resource in resources]
            stopped = stop_resources(client, resource_names, resource_type)
            more = stopped and (next_token is not None)
            time.sleep(1)
    finally:
        logger.info(
            "Finished cleaning %s at %s", resource_type.lower(), str(datetime.datetime.now())
        )


def delete_experiment(client, experiment_name):
    trials = client.list_trials(ExperimentName=experiment_name)
    for trial in trials["TrialSummaries"]:
        trial_name = trial["TrialName"]
        trial_components = client.list_trial_components(TrialName=trial_name)
        for tc in trial_components["TrialComponentSummaries"]:
            tc_name = tc["TrialComponentName"]
            client.disassociate_trial_component(
                TrialName=trial_name,
                TrialComponentName=tc_name,
            )

            try:
                client.delete_trial_component(TrialComponentName=tc_name)
            except botocore.exceptions.ClientError as e:
                # If the trial component is still linked to another trial,
                # ignore it for now. (It will get deleted once completely unlinked.)
                linked_tc_msg = (
                    "An error occurred (ValidationException) when calling the "
                    "DeleteTrialComponent operation: TrialComponent %s is linked "
                    "to 1 or more trials and cannot be deleted."
                ) % tc_name
                if linked_tc_msg in str(e):
                    pass
                else:
                    raise

        client.delete_trial(TrialName=trial_name)
    client.delete_experiment(ExperimentName=experiment_name)


def delete_resources(client, resource_names, resource_type):
    for resource_name in resource_names:
        logger.info("Deleting %s", resource_name)
        if resource_type == "MonitoringSchedules":
            client.delete_monitoring_schedule(MonitoringScheduleName=resource_name)
        elif resource_type == "Endpoints":
            client.delete_endpoint(EndpointName=resource_name)
        elif resource_type == "EndpointConfigs":
            client.delete_endpoint_config(EndpointConfigName=resource_name)
        elif resource_type == "Experiments":
            delete_experiment(client, resource_name)
        logger.info("Deleted %s", resource_name)
        time.sleep(0.5)


def batch_delete_resources(client, before_timestamp, resource_type):
    try:
        next_token = None
        more = True
        while more:
            logger.info("Searching for %s from before: %s", resource_type.lower(), before_timestamp)
            resources, next_token = get_resources(
                client, next_token, before_timestamp, resource_type
            )
            logger.info("Found %s items, deleting now", len(resources))
            if resource_type == "MonitoringSchedules":
                resource_names = [resource["MonitoringScheduleName"] for resource in resources]
            elif resource_type == "Endpoints":
                resource_names = [resource["EndpointName"] for resource in resources]
            elif resource_type == "EndpointConfigs":
                resource_names = [resource["EndpointConfigName"] for resource in resources]
            elif resource_type == "Experiments":
                resource_names = [resource["ExperimentName"] for resource in resources]
            delete_resources(client, resource_names, resource_type)
            more = next_token is not None
            time.sleep(1)
    finally:
        logger.info(
            "Finished cleaning %s at %s", resource_type.lower(), str(datetime.datetime.now())
        )


def lambda_handler(event, context):  # pylint: disable=unused-argument
    logger.info("Invoking endpoint cleanup at %s...", event["time"])
    before_timestamp = datetime.datetime.now() - datetime.timedelta(
        minutes=int(MAXIMUM_ENDPOINT_AGE)
    )
    # Get all regions available for SageMaker.
    sagemaker_regions = boto3.Session().get_available_regions("sagemaker")
    # Clean up resources in each region.
    for region in sagemaker_regions:
        try:
            sm_client = boto3.Session(region_name=region).client("sagemaker")
            # cleaning schedules
            batch_stop_resources(sm_client, before_timestamp, "MonitoringSchedules")
            batch_stop_resources(sm_client, before_timestamp, "ProcessingJobs")
            batch_delete_resources(sm_client, before_timestamp, "MonitoringSchedules")
            # cleaning endpoints
            batch_delete_resources(sm_client, before_timestamp, "Endpoints")
            # cleaning endpoint_configs
            batch_delete_resources(sm_client, before_timestamp, "EndpointConfigs")
            # cleaning trials and trial components
            batch_delete_resources(sm_client, before_timestamp, "Experiments")
        except ClientError as e:
            logger.debug("ERROR in region %s: %s", region, str(e))
