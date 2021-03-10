#!/usr/bin/env python3
from __future__ import absolute_import

import argparse
import os
import logging

from fabric import Connection

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

KEY_FILE = os.path.expanduser("~/.key_id")
IP_FILE = os.path.expanduser("~/.ip_address")


def read_file(file_name):
    with open(file_name, "r") as file:
        content = file.read().replace("\n", "")
    return content


USER = "ubuntu"
HOST = read_file(IP_FILE)
PEM = "{}.pem".format(read_file(KEY_FILE))
CONDA_ENV = "test_env_py3"
BRANCH_NAME = "pull_request"
KEEP_ALIVE = 30


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--github-user", type=str, help="GitHub user of the framework image repo", default="aws"
    )
    parser.add_argument(
        "--github-repo", type=str, required=True, help="Github repo of the " "framework image"
    )
    parser.add_argument(
        "--branch",
        type=str,
        help="Branch to check out, defaults to pull_request",
        default=BRANCH_NAME,
    )
    parser.add_argument("--pr-number", type=str, help="Github pull request number")
    parser.add_argument("--test-cmd", type=str, required=True, help="Command of running tests")
    parser.add_argument(
        "--setup-file", type=str, help="File with setup commands to configure " "dependencies"
    )
    parser.add_argument("--skip-setup", action="store_true", help="Whether to skip test setup")
    args = parser.parse_args()

    # launch test on remote instance
    conn = RemoteConnection(
        USER,
        HOST,
        PEM,
        CONDA_ENV,
        args.github_user,
        args.github_repo,
        args.pr_number,
        args.branch,
        KEEP_ALIVE,
        args.setup_file,
        args.skip_setup,
    )
    conn.run(args.test_cmd)
    conn.close()


class RemoteConnection:
    def __init__(
        self,
        user,
        host,
        pem,
        conda_env,
        github_user,
        repo,
        pr_num,
        branch,
        keepalive,
        setup_file=None,
        skip_setup=False,
    ):
        kwargs = {"key_filename": pem}
        self.conn = Connection(user=user, host=host, connect_kwargs=kwargs)
        self.conda_env = conda_env
        self.conda_env_cmd = "source activate {}".format(self.conda_env)
        self.github_user = github_user
        self.repo = repo
        self.pr_num = pr_num
        self.branch = branch
        self.keepalive = keepalive
        self.setup_file = setup_file
        self.skip_setup = skip_setup

    def create_conda_env(self):
        logger.info("Creating conda env: %s", self.conda_env)
        create_env_cmd = "conda create -y -n {} python=3.6".format(self.conda_env)
        self.conn.run(create_env_cmd, hide="out")

    def close(self):
        self.conn.close()

    def clone(self):
        uri = "https://github.com/{}/{}.git".format(self.github_user, self.repo)
        cmd = "git clone {}".format(uri)
        logger.info("Cloning repo: %s", uri)
        with self.conn.prefix(self.conda_env_cmd):
            self.conn.run(cmd, hide="out")

    def checkout_branch(self):
        with self.conn.cd(self.repo), self.conn.prefix(self.conda_env_cmd):
            cmd = "git checkout {}".format(self.branch)
            if self.pr_num:
                cmd = "git fetch origin refs/pull/{}/head:{} && {}".format(
                    self.pr_num, self.branch, cmd
                )
            self.conn.run(cmd, hide="out")

    def install_dependencies(self):
        with self.conn.cd(self.repo), self.conn.prefix(self.conda_env_cmd):
            if self.setup_file and os.path.isfile(self.setup_file):
                with open(self.setup_file, "r") as f:
                    setup_cmds = f.read()
                    logger.info("Running setup command: %s", setup_cmds)
                self.conn.put(self.setup_file)
                cmd = "bash ../%s" % self.setup_file
                self.conn.run(cmd, hide="out")
            else:
                logger.info("No setup file found. Skip installing dependencies.")

    def run_tests(self, test_cmd):
        with self.conn.cd(self.repo), self.conn.prefix(self.conda_env_cmd):

            self.conn.transport = self.conn.client.get_transport()
            if self.conn.transport is None:
                # If a connection has not been established the low level transport
                # object doesn't exist.
                # Opening a connection here so we can configure keepalive time.
                # TODO: context management
                self.conn.open()
            self.conn.transport.set_keepalive(self.keepalive)

            logger.info("Running test command: %s", test_cmd)
            self.conn.run(test_cmd)

    def run(self, test_cmd):
        if not self.skip_setup:
            self.create_conda_env()
            self.clone()
            self.checkout_branch()
            self.install_dependencies()
        self.run_tests(test_cmd)


if __name__ == "__main__":
    main()
