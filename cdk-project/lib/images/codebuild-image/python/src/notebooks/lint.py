import re

import black
import language_tool_python
from black_nb.cli import TARGET_VERSIONS, SubReport, format_file_in_place
from notebooks import dictionary, parse


def check_grammar(notebook):
    """Run LanguageTool against the given notebook.

    Args:
        notebook (Path): The notebook filename to run the formatting check against.

    Returns:
        [language_tool_python.Match]: A list of spelling and grammar rule violations found in the notebook.

    """
    tool = language_tool_python.LanguageTool("en-US")

    report = []

    cells = parse.markdown_cells(notebook)
    for cell in cells:
        code_block = False
        for line in cell:
            stripped_line = line.rstrip().strip(" #*")
            if stripped_line in ("```python", "```bash", "```"):
                code_block = not code_block
            if code_block:
                continue
            code_substituted_line = re.sub(
                "(`)\1{2,}[^`]*(`)\1{2,}|`[^`]*`", "[code]", stripped_line
            )
            matches = tool.check(code_substituted_line)
            report.extend(matches)

    is_correctly_spelled = lambda rule: rule.ruleIssueType == "misspelling" and (
        rule.matchedText in dictionary.allow_list
        or "-" in rule.matchedText
        or "_" in rule.matchedText
        or "$" in rule.matchedText
    )
    report = [rule for rule in report if not is_correctly_spelled(rule)]

    is_ignored_rule = lambda rule: rule.ruleId in dictionary.rules_to_ignore
    report = [rule for rule in report if not is_ignored_rule(rule)]

    return report


def check_code_format(notebook):
    """Run black-nb against the given notebook.

    Args:
        notebook (Path): The notebook filename to run the formatting check against.

    Returns:
        (bool, black_nb.SubReport): A boolean indicating whether the code would be reformatted
            and the corresponding report.

    """
    write_back = black.WriteBack.CHECK
    mode = black.Mode(
        target_versions=TARGET_VERSIONS,
        line_length=100,
        is_pyi=False,
        string_normalization=True,
    )
    report = format_file_in_place(
        src=notebook,
        write_back=write_back,
        mode=mode,
        clear_output=False,
        sub_report=SubReport(write_back=write_back),
    )
    print(str(report))
    if (report.change_count > 0) or (report.failure_count > 0):
        return True, report
    return False, report
