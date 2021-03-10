import json
import re
import subprocess
import urllib

import boto3

import sagemakerci.common


class Git:
    _OAUTH_SECRET_ID = "/codebuild/github/oauth"
    _REMOTE_PARSE_REGEX = re.compile(
        r"^.*[:/](?P<owner>[\w\-]+)/(?P<repo>[\w\-]+)\.git$", re.IGNORECASE
    )

    def __init__(self):
        self._oauth_token = None
        self._branch_protection_uri = None
        self._release_uri = None

    @property
    def oauth_token(self):
        if self._oauth_token is None:
            secrets_client = boto3.client("secretsmanager")
            self._oauth_token = secrets_client.get_secret_value(SecretId=Git._OAUTH_SECRET_ID)[
                "SecretString"
            ]

        return self._oauth_token

    @property
    def branch_protection_uri(self):
        if self._branch_protection_uri is None:
            owner, repo = self._origin_details()
            branch = self._current_branch()
            self._branch_protection_uri = (
                f"https://api.github.com/repos/{owner}/{repo}/branches/{branch}/protection"
            )

        return self._branch_protection_uri

    @property
    def release_uri(self):
        if self._release_uri is None:
            owner, repo = self._origin_details()
            self._release_uri = f"https://api.github.com/repos/{owner}/{repo}/releases"

        return self._release_uri

    def add(self, path):
        cmd = f"git add {path}".split()
        sagemakerci.common.check_call_quiet(cmd)

    def commit(self, message):
        sagemakerci.common.check_call_quiet(
            ["git", "-c", "user.name=ci", "-c", "user.email=ci", "commit", "-m", message]
        )

    def tag(self, tag):
        sagemakerci.common.check_call_quiet(f"git tag {tag}".split())

    def _revcount(self, ref="HEAD"):
        return int(sagemakerci.common.check_output_noerr(f"git rev-list {ref} --count".split()))

    def find_version_tag(self):
        depth = 1
        cmd = "git describe --tags --abbrev=0 --match v[0-9][0-9.]*".split()

        # try up to 1024 commits
        for _ in range(0, 10):
            try:
                return sagemakerci.common.check_output_capture_error(cmd)
            except subprocess.CalledProcessError as e:
                if self._revcount() < depth:
                    # no more commits
                    return None

                if "No tags" in e.stdout or "No names found" in e.stdout:
                    depth = depth * 2
                    sagemakerci.common.check_call_quiet(f"git fetch --depth {depth}".split())
                else:
                    raise

        return None

    def list_commits(self, since_tag):
        cmd = ["git", "log", "--pretty=%h %s"]
        if since_tag:
            cmd.append(f"{since_tag}..HEAD")

        commits = sagemakerci.common.check_output_noerr(cmd)
        return commits.split("\n") if commits else []

    def _current_branch(self):
        cmd = "git branch --format %(refname:short)".split()
        return sagemakerci.common.check_output_noerr(cmd)

    def _origin_details(self):
        cmd = "git remote get-url --all origin".split()
        remote = sagemakerci.common.check_output_noerr(cmd)

        match = Git._REMOTE_PARSE_REGEX.search(remote)
        owner = match.group("owner")
        repo = match.group("repo")

        return (owner, repo)

    def _github_headers(self):
        return {"Authorization": f"token {self.oauth_token}", "Content-Type": "application/json"}

    def _check_branch_protection(self):
        # note: branch protection is only available for public repos or
        # private repos in a github pro org. the functions here related to
        # branch projection will all fail in free/private repos

        # https://developer.github.com/v3/repos/branches/#get-branch-protection
        try:
            request = urllib.request.Request(
                self.branch_protection_uri, headers=self._github_headers()
            )

            with urllib.request.urlopen(request) as resp:
                payload = json.loads(resp.read(), encoding="utf-8")
                return payload["enforce_admins"]["enabled"]
        except urllib.error.HTTPError as e:
            body = e.fp.read().decode("utf-8")
            if "Branch not protected" in body:
                return False
            raise

        return False

    def _enable_branch_protection(self):
        # https://developer.github.com/v3/repos/branches/#add-admin-enforcement-of-protected-branch
        request = urllib.request.Request(
            self.branch_protection_uri + "/enforce_admins",
            headers=self._github_headers(),
            method="POST",
        )

        # blind post - any failure will raise HTTPError
        urllib.request.urlopen(request)

    def _remove_branch_protection(self):
        # https://developer.github.com/v3/repos/branches/#remove-admin-enforcement-of-protected-branch
        request = urllib.request.Request(
            self.branch_protection_uri + "/enforce_admins",
            headers=self._github_headers(),
            method="DELETE",
        )

        # blind post - any failure will raise HTTPError
        urllib.request.urlopen(request)

    def push_to_remote(self, tag):
        protected = self._check_branch_protection()
        if protected:
            self._remove_branch_protection()

        sagemakerci.common.check_call_quiet("git push".split())
        sagemakerci.common.check_call_quiet(f"git push origin {tag}".split())

        if protected:
            self._enable_branch_protection()

    def create_github_release(self, tag, body):
        payload = {"tag_name": tag, "name": tag, "draft": False}

        if body:
            payload["body"] = body

        request = urllib.request.Request(
            self.release_uri,
            data=bytes(json.dumps(payload), encoding="utf-8"),
            headers=self._github_headers(),
        )

        urllib.request.urlopen(request)

    def clone(
        self, owner, repo, branch, expected_rev, depth=1
    ):  # pylint: disable=too-many-arguments
        uri = f"https://{self.oauth_token}@github.com/{owner}/{repo}.git"
        sagemakerci.common.check_call_quiet(
            f"git clone --depth {depth} --single-branch --branch {branch} {uri} .".split()
        )

        rev = sagemakerci.common.check_output_noerr("git rev-parse --verify HEAD".split())

        # make sure we fetched the version we expected
        if rev != expected_rev:
            raise ValueError(f"unexpected revision - got {rev}, expected {expected_rev}")
