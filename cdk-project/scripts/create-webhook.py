#!/usr/bin/env python3

import argparse
import json
import logging
import os
import sys
import urllib

import boto3

DEFAULT_REPO_OWNER = "aws"
OAUTH_SECRET_ID = "/codebuild/github/oauth"

logging.basicConfig(level=logging.INFO)
logging.getLogger("boto3").setLevel(logging.ERROR)
logging.getLogger("botocore").setLevel(logging.ERROR)
logger = logging.getLogger()


def parse_args(args):
    parser = argparse.ArgumentParser(os.path.basename(__file__))
    parser.set_defaults(func=lambda x: parser.print_usage())
    parser.add_argument("--owner", help="repository owner", default=DEFAULT_REPO_OWNER, type=str)
    parser.add_argument("--repo", help="repository name", type=str, required=True)
    return parser.parse_args(args)


def get_request_headers(oauth_token):
    return {"Authorization": f"token {oauth_token}", "Content-Type": "application/json"}


def get_request_payload(webhook_uri):
    return {
        "name": "web",
        "config": {"url": webhook_uri, "content_type": "json"},
        "events": ["push", "pull_request"],
    }


def get_webhook_uri(region):
    apig_client = boto3.client("apigateway")

    response = apig_client.get_rest_apis()
    apis = response["items"]

    webhook_api_id = [item for item in apis if item["name"] == "GitHubWebhookApi"][0]["id"]
    webhook_uri = f"https://{webhook_api_id}.execute-api.{region}.amazonaws.com/prod/"
    logger.info("webhook uri: %s", webhook_uri)
    return webhook_uri


def get_oauth_token():
    secrets_client = boto3.client("secretsmanager")
    return secrets_client.get_secret_value(SecretId=OAUTH_SECRET_ID)["SecretString"]


def create_webhook(owner, repo, webhook_uri, oauth_token):
    github_uri = f"https://api.github.com/repos/{owner}/{repo}/hooks"
    headers = get_request_headers(oauth_token)
    payload = get_request_payload(webhook_uri)
    request = urllib.request.Request(
        github_uri, data=bytes(json.dumps(payload), encoding="utf-8"), headers=headers
    )
    urllib.request.urlopen(request)


def main(args):
    args = parse_args(args)

    region = boto3.session.Session().region_name
    if not region:
        raise ValueError("aws region not set - run aws configure")

    webhook_uri = get_webhook_uri(region)
    oauth_token = get_oauth_token()

    # create the webhook
    create_webhook(args.owner, args.repo, webhook_uri, oauth_token)
    logger.info("created webhook - repo: %s/%s target: %s", args.owner, args.repo, webhook_uri)


if __name__ == "__main__":
    main(sys.argv[1:])
