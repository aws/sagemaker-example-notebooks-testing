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
    reference_details = {}

    for notebook in parse.get_deleted_files(args.pr):
        deleted_references = parse.check_file_references(notebook)
        if deleted_references:
            reference_details[notebook] = deleted_references
            basename = os.path.basename(notebook)
            print("\n" * 2)
            print(f"* {basename} " + "*" * (97 - len(basename)))
            print(f'The defaulting filenames are{" ".join(deleted_references)}')

    print("\n" * 2)
    print("-" * 100)
    if reference_details:
        raise Exception(
            "One or more notebooks did not pass the link check. Please see above for error messages."
        )


if __name__ == "__main__":
    main()

