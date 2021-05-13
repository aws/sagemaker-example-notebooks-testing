import collections
import datetime
import logging
import os
import re

logger = logging.getLogger(__name__)


class Changelog:
    _CHANGE_TYPE_TITLE_MAP = collections.OrderedDict(
        [
            ("breaking", "Breaking Changes"),
            ("deprecation", "Deprecations and Removals"),
            ("feature", "Features"),
            ("fix", "Bug Fixes and Other Changes"),
            ("documentation", "Documentation Changes"),
            ("infrastructure", "Testing and Release Infrastructure"),
        ]
    )

    def __init__(self, path):
        self.path = path

    def _read_previous_changes(self):
        if os.path.exists(self.path):
            with open(self.path, "r") as f:
                text = f.read().strip()
                index = text.find("# Changelog")
                index = text.find("##", index)
                return text[index:]

        return None

    def update(self, changes, tag):
        today = datetime.datetime.today().strftime("%Y-%m-%d")

        header = "# Changelog\n\n"
        existing_changelog = self._read_previous_changes()

        with open(self.path, mode="w", encoding="utf-8") as f:
            f.write(header)
            f.write(f"## {tag} ({today})\n\n")
            for change_type, title in Changelog._CHANGE_TYPE_TITLE_MAP.items():
                if change_type in changes:
                    f.write(f"### {title}\n\n")
                    for change in changes[change_type]:
                        f.write(f" * {change}\n")
                    f.write("\n")

            if existing_changelog:
                f.write(existing_changelog)
                f.write("\n")

    def extract_release_notes(self, tag):
        lines = []

        found = False
        with open(self.path, mode="r", encoding="utf-8") as f:
            for line in f:
                if found:
                    if line.startswith("## v"):
                        break
                    lines.append(line.rstrip())
                else:
                    found = line.startswith(f"## {tag}")
        return "\n".join(lines).strip()


class CommitParser:
    # order must be aligned with associated increment_type (major...post)
    _CHANGE_TYPES = ["breaking", "deprecation", "feature", "fix", "documentation", "infrastructure"]

    _EXCLUDE_PATTERNS = [
        re.compile(r"^[0-9a-f]+\s+prepare release v.*$", re.IGNORECASE),
        re.compile(r"^[0-9a-f]+\s+update development version to v.*$", re.IGNORECASE),
    ]

    # pylint: disable=line-too-long
    _PARSE_COMMIT_REGEX = re.compile(
        r"""
        ^(?P<sha>[0-9a-f]+)
        \s+
        (?:(?P<label>break(?:ing)?|feat(?:ure)?|depr(?:ecation)?|change|fix|doc(?:umentation)?|infra(?:structure)?)\s*:)?
        \s*
        (?P<message>.*?)
        \s*
        (?:(?P<pr>\(\#\d+\)))?
        \s*$
        """,
        re.VERBOSE | re.IGNORECASE,
    )

    _CANONICAL_LABELS = {
        "break": "breaking",
        "feat": "feature",
        "depr": "deprecation",
        "change": "fix",
        "doc": "documentation",
        "infra": "infrastructure",
    }

    _CHANGE_TO_INCREMENT_TYPE_MAP = {
        "breaking": "major",
        "feature": "minor",
        "deprecation": "minor",
        "fix": "patch",
        "documentation": "post",
        "infrastructure": "post",
    }

    def __init__(self, commits):
        self._skipped = []
        self._groups = {}

        self._add_commits(commits)

    def _add_commits(self, commits):
        for c in commits:
            self._add_commit(c)

        if self._skipped:
            logger.info("skipped commits: \n  %s", "\n  ".join(self._skipped))

    def _add_commit(self, commit):
        if self._exclude_commit(commit):
            self._skipped.append(commit)
            return

        sha, label, message = self._parse_commit(commit)

        if not sha:
            return

        if label in self._groups:
            self._groups[label].append(message)
        else:
            self._groups[label] = [message]

    def _parse_commit(self, commit):
        sha = label = message = None
        match = CommitParser._PARSE_COMMIT_REGEX.search(commit)
        if match:
            sha = match.group("sha")
            label = match.group("label") or "fix"
            label = CommitParser._CANONICAL_LABELS.get(label, label)
            message = match.group("message")

        else:
            self._skipped.append(commit)

        return sha, label, message

    def _exclude_commit(self, commit):
        return any((r.match(commit) for r in CommitParser._EXCLUDE_PATTERNS))

    def changes(self):
        return self._groups

    def increment_type(self):
        for change_type in CommitParser._CHANGE_TYPES:
            if change_type in self._groups:
                return CommitParser._CHANGE_TO_INCREMENT_TYPE_MAP[change_type]

        return "patch"
