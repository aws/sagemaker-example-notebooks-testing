import re


# a subset of PEP 440
_VERSION_REGEX = re.compile(
    r"""
    ^\s*
    v?
    (?P<major>\d+)
    (?:\.(?P<minor>\d+))?
    (?:\.(?P<patch>\d+))?
    (?:\.(?P<pre>(?P<pre_label>a|b|rc)(?P<pre_n>\d+)))?
    (?:\.post(?P<post>\d+))?
    (?:\.dev(?P<dev>\d+))?
    \s*$
""",
    re.VERBOSE | re.IGNORECASE,
)


class Version:
    def __init__(
        self, major, minor=0, patch=0, pre=None, post=None, dev=None
    ):  # pylint: disable=too-many-arguments
        self.major = major
        self.minor = minor
        self.patch = patch
        self.pre = pre
        self.post = post
        self.dev = dev

        if len([x for x in [pre, post, dev] if x is not None]) > 1:
            raise ValueError(f"invalid version: {str(self)}")

        self.tag = f"v{str(self)}"

    def __str__(self):
        parts = [str(x) for x in [self.major, self.minor, self.patch]]

        if self.pre:
            parts.append(f"{self.pre[0]}{self.pre[1]}")

        if self.post is not None:
            parts.append(f"post{self.post}")

        if self.dev is not None:
            parts.append(f"dev{self.dev}")

        return ".".join(parts).lower()

    def increment(self, increment_type):  # pylint: disable=too-many-branches
        incr = None
        if increment_type == "major":
            incr = Version(self.major + 1)
        elif increment_type == "minor":
            incr = Version(self.major, self.minor + 1)
        elif increment_type == "patch":
            incr = Version(self.major, self.minor, self.patch + 1)
        elif increment_type == "pre":
            if self.pre:
                pre = (self.pre[0], self.pre[1] + 1)
                patch = self.patch
            elif self.dev is not None:
                pre = ("a", 0)
                patch = self.patch
            else:
                pre = ("a", 0)
                patch = self.patch + 1
            incr = Version(self.major, self.minor, patch, pre=pre)
        elif increment_type == "post":
            if self.pre or self.dev is not None:
                raise ValueError(f"can't increment post on a prerelease version: {str(self)}")
            post = self.post + 1 if self.post is not None else 0
            incr = Version(self.major, self.minor, self.patch, post=post)
        elif increment_type == "dev":
            if self.pre:
                raise ValueError(f"can't increment dev on a prerelease version: {str(self)}")
            if self.dev:
                dev = self.dev + 1
                patch = self.patch
            else:
                dev = 0
                patch = self.patch + 1
            incr = Version(self.major, self.minor, patch, dev=dev)

        return incr


def parse(version):
    match = _VERSION_REGEX.search(version)
    if not match:
        raise ValueError(f"invalid version: {version}")

    return Version(
        int(match.group("major") or 0),
        int(match.group("minor") or 0),
        int(match.group("patch") or 0),
        (match.group("pre_label"), int(match.group("pre_n"))) if match.group("pre") else None,
        int(match.group("post")) if match.group("post") else None,
        int(match.group("dev")) if match.group("dev") else None,
    )


def next_version(tag, min_version, increment_type):
    if not tag:
        return min_version

    return parse(tag).increment(increment_type)


def update_version_file(path, version):
    with open(path, "w") as f:
        f.write(str(version))
        f.write("\n")
