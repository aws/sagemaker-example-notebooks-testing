#!/usr/bin/env python3
import argparse
import os
import sys

from notebooks import lint, parse


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

    failures = {}

    for notebook in parse.pr_notebook_filenames(args.pr):
        failed, report = lint.check_code_format(notebook)
        if failed:
            failures[notebook] = report
            basename = os.path.basename(notebook)
            print("\n" * 2)
            print(f"* {basename} " + "*" * (97 - len(basename)))
            print("*")
            print(f"* {'report':>11}: {str(report):<11}")
            print("*")

    print("\n" * 2)
    print("-" * 100)
    if len(failures) > 0:
        raise Exception(
            "One or more notebooks did not pass the code formatting check. Please see above for error messages. "
            "To reformat the code in your notebook, use black-nb: https://pypi.org/project/black-nb/ "
            "Run the command `black-nb -l 100 your_notebook_file.ipynb`"
        )


if __name__ == "__main__":
    main()
