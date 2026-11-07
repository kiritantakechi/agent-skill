"""A GitHub Actions workflow, read as far as the checks read one.

The harness depends on no YAML parser, and what the checks ask of a
workflow is written in a small part of YAML: each `uses:`, its value
and the comment after it. That part is read here, once, for `pins`.
"""

import re
from dataclasses import dataclass
lazy from collections.abc import Iterator
lazy from pathlib import Path

from agent_skill.layout import WORKFLOWS
from agent_skill.text import group, strip_comment

#: What a workflow file is called.
SUFFIXES = (".yml", ".yaml")

#: A `uses:` key and its value, alone on its line or opening a step,
#: commented out or not, and the comment after it. A line of prose that
#: mentions `uses:` is not one: the key opens the line, and nothing but
#: a comment follows the value.
_USES = re.compile(
    r"^ *(?:# *)*(?:- +)?uses: *"
    r"(?P<value>\"[^\"]*\"|'[^']*'|[^\s#]+)"
    r" *(?:# *(?P<comment>.*?))? *$"
)

#: A commit, as `git` names one in full.
_COMMIT = re.compile(r"[0-9a-f]{40}")

#: How a workflow names an action that is no third party's: a path in
#: the repository it runs in, or a container image.
_NOT_THIRD_PARTY = ("./", "docker://")


@dataclass(frozen=True, slots=True)
class Uses:
    """One `uses:`: what it names, at which ref, and its comment."""

    #: the line it is on, counted from 1
    line: int
    #: `actions/checkout`, `./tools/lint`, `docker://alpine:3`
    action: str
    #: what follows the `@`; "" when nothing does
    ref: str
    #: the comment after the value, its `#` taken off; "" for none
    comment: str

    @property
    def third_party(self) -> bool:
        """Is this an action named by its repository?

        Not a local action, which is the repository's own code at the
        commit being run, nor a container image.
        """
        return not self.action.startswith(_NOT_THIRD_PARTY)

    @property
    def commit(self) -> bool:
        """Does the ref name a commit, all 40 hexadecimal digits?"""
        return _COMMIT.fullmatch(self.ref) is not None

    @property
    def named(self) -> str:
        """The value as written: `actions/checkout@v7`."""
        return f"{self.action}@{self.ref}" if self.ref else self.action


def shipped(assets: list[Path]) -> list[Path]:
    """The workflows among a skill's assets."""
    return [p for p in assets if p.suffix in SUFFIXES]


def run_by(root: Path) -> list[Path]:
    """The workflows the repository at `root` runs, in sorted order."""
    directory = root / WORKFLOWS
    if not directory.is_dir():
        return []
    return sorted(p for p in directory.iterdir() if p.suffix in SUFFIXES)


def uses(text: str) -> Iterator[Uses]:
    """Every `uses:` in a workflow, a commented-out one included.

    A step kept as a comment, such as a job to enable later, is copied
    back in by whoever enables it, at whatever its ref names by then.
    """
    for number, line in enumerate(text.split("\n"), 1):
        if (found := _uses_on(line, number)) is not None:
            yield found


def _uses_on(line: str, number: int) -> Uses | None:
    """The `uses:` `line` holds, or None when it holds none."""
    m = _USES.match(line)
    if m is None:
        return None
    action, _, ref = _scalar(m["value"]).partition("@")
    return Uses(number, action, ref, group(m, "comment"))


def _uncommented(line: str) -> str:
    """`line` without a comment after its content."""
    return strip_comment(line, " #", "\"'").rstrip()


def _scalar(text: str) -> str:
    """A scalar's text: unquoted, and without a comment after it."""
    text = _uncommented(f" {text}").strip()
    if len(text) > 1 and text[0] == text[-1] and text[0] in "\"'":
        return text[1:-1]
    return text
