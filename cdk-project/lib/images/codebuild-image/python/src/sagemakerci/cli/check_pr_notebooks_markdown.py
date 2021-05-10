#!/usr/bin/env python3
import argparse
import json
import os
import sys

import language_tool_python

from sagemakerci.cli.run_pr_notebooks import notebook_filenames


def parse_args(args):
    parser = argparse.ArgumentParser(os.path.basename(__file__))
    parser.set_defaults(func=lambda x: parser.print_usage())
    parser.add_argument("--pr", help="Pull request number", type=int, required=True)

    parsed = parser.parse_args(args)
    if not parsed.pr:
        parser.error("--pr required")

    return parsed


def markdown_cells(notebook):
    with open(notebook) as notebook_file:
        cells = json.load(notebook_file)["cells"]
    md_cells = []
    for cell in cells:
        if cell["cell_type"] == "markdown":
            md_cells.append(cell["source"])
    return md_cells


def check_grammar(notebook):
    tool = language_tool_python.LanguageTool("en-US")

    report = []

    cells = markdown_cells(notebook)
    for cell in cells:
        for line in cell:
            stripped_line = line.rstrip().strip(" #*")
            matches = tool.check(stripped_line)
            report.extend(matches)
    return report


def main():
    args = parse_args(sys.argv[1:])

    failures = {}

    for notebook in notebook_filenames(args.pr):
        report = check_grammar(notebook)
        if report:
            failures[notebook] = report
            basename = os.path.basename(notebook)
            print("\n" * 2)
            print(f"* {basename} " + "*" * (97 - len(basename)))
            print()
            print("\n".join(report))

    print("\n" * 2)
    print("-" * 100)
    if len(failures) > 0:
        raise Exception(
            "One or more notebooks did not pass the spelling and grammar check. Please see above for error messages. "
            "To fix the text in your notebook, use language_tool_python.utils.correct: https://pypi.org/project/language-tool-python/"
        )


if __name__ == "__main__":
    main()
