#!/usr/bin/env python3
import argparse
import os
import sys

from black import WriteBack
from black_nb import format_file_in_place

from sagemakerci.cli.run_pr_notebooks import notebook_filenames


def parse_args(args):
    parser = argparse.ArgumentParser(os.path.basename(__file__))
    parser.set_defaults(func=lambda x: parser.print_usage())
    parser.add_argument("--pr", help="Pull request number", type=int, required=True)

    parsed = parser.parse_args(args)
    if not parsed.pr:
        parser.error("--pr required")

    return parsed


def check_code_format(notebook):
    report = format_file_in_place(src=notebook, write_back=WriteBack.CHECK)
    print(str(report))
    if (report.change_count > 0) or (report.failure_count > 0):
        return False, report
    return True, report


def main():
    args = parse_args(sys.argv[1:])

    failures = {}

    for notebook in notebook_filenames(args.pr):
        failed, report = check_code_format(notebook)
        if failed:
            failures[notebook] = report
            basename = os.path.basename(notebook)
            print("\n" * 2)
            print(f"* {basename} " + "*" * (97 - len(basename)))
            print("*")
            print(str(report))

    print("\n" * 2)
    print("-" * 100)
    if len(failures) > 0:
        raise Exception(
            "One or more notebooks did not pass the code formatting check. Please see above for error messages. "
            "To reformat the code in your notebook, use black-nb: https://pypi.org/project/black-nb/"
        )


if __name__ == "__main__":
    main()
