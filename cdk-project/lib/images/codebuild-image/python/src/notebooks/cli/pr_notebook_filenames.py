#!/usr/bin/env python3
import argparse
import os
import sys

from notebooks import parse


def parse_args(args):
    parser = argparse.ArgumentParser(os.path.basename(__file__))
    parser.set_defaults(func=lambda x: parser.print_usage())
    parser.add_argument("--pr", help="Pull request number", type=int, required=True)

    parsed = parser.parse_args(args)
    if not parsed.pr:
        parser.error("--pr required")

    return parsed


def main():
    args = parse_args(sys.argv[1:])

    filenames = parse.pr_notebook_filenames(args.pr)
    filenames_string = " ".join(filenames)
    print(filenames_string)  # This returns the string to bash scripts calling this python script


if __name__ == "__main__":
    main()
