#!/usr/bin/env python3

import argparse
import logging
import os
import shutil
import sys

import sagemakerci.changelog
import sagemakerci.codestar as cs
import sagemakerci.common
import sagemakerci.git
import sagemakerci.version

logging.basicConfig(level=logging.INFO)
logging.getLogger("boto3").setLevel(logging.ERROR)
logging.getLogger("botocore").setLevel(logging.ERROR)
logger = logging.getLogger(__name__)


def check_relative(path):
    if path.startswith("/"):
        raise argparse.ArgumentTypeError(f"path must be relative: {path}")

    return path


def parse_args(args):
    parser = argparse.ArgumentParser(os.path.basename(__file__))
    parser.set_defaults(func=lambda x: parser.print_usage())
    parser.add_argument("--prepare", help="prepare a release", action="store_true")
    parser.add_argument("--publish", help="publish a release", action="store_true")
    parser.add_argument(
        "--min-version", help="version to use if no release tag is found", default="0.1.0", type=str
    )
    parser.add_argument(
        "--version-file", help="path to version output file", default="VERSION", type=check_relative
    )
    parser.add_argument(
        "--no-version-file", help="do not write a version file", action="store_true"
    )
    parser.add_argument(
        "--changelog-file",
        help="path to changelog file",
        default="CHANGELOG.md",
        type=check_relative,
    )
    parser.add_argument(
        "--no-changelog-file", help="do not write a changelog file", action="store_true"
    )

    parsed = parser.parse_args(args)
    if not (parsed.prepare or parsed.publish):
        parser.error("--prepare or --publish required")

    return parsed


def prepare_release(args):
    git = sagemakerci.git.Git()

    # codebuild doesn't receive a git clone when running in codepipeline,
    # so we need to clone one to prepare the release
    if cs.pipeline_build():
        (owner, repo, branch) = cs.repository_details()
        expected_rev = cs.resolved_source_version()
        shutil.rmtree(cs.temp_repo_path(), ignore_errors=True)
        os.makedirs(cs.temp_repo_path())
        os.chdir(cs.temp_repo_path())
        git.clone(owner, repo, branch, expected_rev)

    mv = sagemakerci.version.parse(args.min_version)
    tag = git.find_version_tag()

    commits = git.list_commits(tag)

    cp = sagemakerci.changelog.CommitParser(commits)
    changes = cp.changes()
    increment_type = cp.increment_type()

    if not changes:
        raise ValueError("no changes since last release")

    nv = sagemakerci.version.next_version(tag, mv, increment_type)

    if not args.no_version_file:
        sagemakerci.version.update_version_file(args.version_file, nv)
        git.add(args.version_file)

    if not args.no_changelog_file:
        changelog = sagemakerci.changelog.Changelog(args.changelog_file)
        changelog.update(changes, nv.tag)
        git.add(args.changelog_file)

    git.commit(f"prepare release {nv.tag}")
    git.tag(nv.tag)

    # copy changed files back to the build directory
    if cs.pipeline_build():
        source_dir = cs.codebuild_source_dir()
        if not args.no_version_file:
            shutil.copyfile(args.version_file, os.path.join(source_dir, args.version_file))

        if not args.no_changelog_file:
            shutil.copyfile(args.changelog_file, os.path.join(source_dir, args.changelog_file))
        os.chdir(source_dir)


def publish_release(args):
    # if codepipeline, switch to the repo cloned during the prepare step
    if cs.pipeline_build():
        os.chdir(cs.temp_repo_path())

    git = sagemakerci.git.Git()

    tag = git.find_version_tag()
    if not tag:
        raise ValueError("no release tag found")

    changelog = sagemakerci.changelog.Changelog(args.changelog_file)

    changes = changelog.extract_release_notes(tag)

    # update version file, if this project uses one
    if not args.no_version_file:
        nv = sagemakerci.version.parse(tag).increment("dev")
        sagemakerci.version.update_version_file(args.version_file, nv)
        git.add(args.version_file)
        git.commit(f"update development version to {nv.tag}")

    git.push_to_remote(tag)
    git.create_github_release(tag, changes)

    # if codepipeline, switch back to the build directory
    if cs.pipeline_build():
        os.chdir(cs.codebuild_source_dir())


def main():
    args = parse_args(sys.argv[1:])

    if args.prepare:
        prepare_release(args)

    if args.publish:
        publish_release(args)


if __name__ == "__main__":
    main()
