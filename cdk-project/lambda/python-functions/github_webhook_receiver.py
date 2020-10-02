import datetime
import collections
import json

import boto3

import common

GitHubUser = collections.namedtuple("GitHubUser", "id, login")
PullRequest = collections.namedtuple("PullRequest", "owner, repo, branch, commit, submitter")

logger = common.get_logger()
cb_client = boto3.client("codebuild")


def parse_event(body):
    # we only care about pull request events
    if "pull_request" in body:
        # we only care about these two actions
        if body["action"] in ("opened", "synchronize"):
            submitter_id = body["pull_request"]["user"]["id"]
            submitter_login = body["pull_request"]["user"]["login"]
            owner = body["pull_request"]["base"]["repo"]["owner"]["login"]
            repo = body["pull_request"]["base"]["repo"]["name"]
            branch = body["pull_request"]["base"]["ref"]
            commit = "pr/{0}".format(body["number"])  # pr/xxx

            submitter = GitHubUser(submitter_id, submitter_login)
            return PullRequest(owner, repo, branch, commit, submitter)

    return None


def build_project_name(pr):
    # codebuild project names need to match this pattern: <owner>-<repo>-<branch>-pr
    # but owner 'aws' and branch 'master' are omitted for brevity
    parts = []
    if pr.owner != "aws":
        parts.append(pr.owner)

    parts.append(pr.repo)

    if pr.branch != "master":
        parts.append(pr.branch)

    parts.append("pr")

    return "-".join(parts)


def list_builds(project_name, next_token):
    kwargs = {"projectName": project_name, "sortOrder": "DESCENDING"}

    if next_token:
        kwargs["nextToken"] = next_token

    return cb_client.list_builds_for_project(**kwargs)


def find_stale_builds(project_name, source_version):
    stale_builds = []

    # only consider builds <= 1 day old
    search_after = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=1)

    next_token = None
    while True:
        # get build ids, most recent first
        response = list_builds(project_name, next_token)
        build_ids = response["ids"]
        next_token = response.get("nextToken")

        # no builds? stop looking
        if not build_ids:
            break

        builds = cb_client.batch_get_builds(ids=build_ids)["builds"]

        for b in builds:
            # if it's running, and for the same pr, add it to stale list
            if b["buildStatus"] == "IN_PROGRESS" and b["sourceVersion"] == source_version:
                stale_builds.append(b["id"])

            # if startTime < cutoff, stop looking
            if b["startTime"] < search_after:
                next_token = None
                break

        if not next_token:
            break

    logger.info("found %d stale builds for %s:%s", len(stale_builds), project_name, source_version)
    return stale_builds


def cancel_stale_builds(project_name, source_version):
    stale_builds = find_stale_builds(project_name, source_version)

    for build_id in stale_builds:
        cb_client.stop_build(id=build_id)
        logger.info("stopped stale build %s for %s:%s", build_id, project_name, source_version)


def handler(event, context):  # pylint: disable=unused-argument
    try:
        pr = parse_event(json.loads(event["body"]))

        if pr:
            logger.info("received webhook: %s", pr)
            project_name = build_project_name(pr)

            cancel_stale_builds(project_name, pr.commit)

            response = cb_client.start_build(projectName=project_name, sourceVersion=pr.commit)
            build_id = response["build"]["id"]
            logger.info("started build %s for %s:%s", build_id, project_name, pr.commit)

        return {"statusCode": 200}

    except Exception as e:  # pylint: disable=broad-except
        logger.exception()
        return {"statusCode": 500, "body": str(e)}
