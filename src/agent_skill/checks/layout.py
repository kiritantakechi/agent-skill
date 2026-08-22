"""The physical shape of the markdown.

Exists because a 135-column line shipped and every check passed — nothing
measured width. This is the sole owner of the physical checks; when a second
check repeated them at a different severity, one defect produced two findings.
"""

from __future__ import annotations

import re

from ..report import fail, note
from . import check

WIDTH = 100

#: A rule heading and its contents entry are one line by construction: the ID,
#: the tier, the title. Rewrapping either corrupts it — that is how nineteen zig
#: contents entries were once truncated. Over-length there is a title-length
#: problem, reported separately.
HEADING = re.compile(r"^#{1,6} [A-Z]{2}-[A-Z]+-\d+[a-z]? \[")
TOC = re.compile(r"^\s*- [A-Z]{2}-[A-Z]+-\d+[a-z]? \[")


@check("layout", "line width, whitespace, fences")
def layout(skill):
    for path in skill.markdown:
        text = path.read_text()
        tag = f"{skill.name}/{path.name}"
        lines = text.split("\n")

        end_fm = 0
        if lines and lines[0] == "---":
            end_fm = next((i for i, ln in enumerate(lines[1:], 1) if ln == "---"), 0)

        fenced = False
        for i, line in enumerate(lines, 1):
            if line.startswith("```"):
                fenced = not fenced
                continue
            if line != line.rstrip():
                yield fail("trailing whitespace", f"{tag}:{i}")
            if i <= end_fm + 1 or len(line) <= WIDTH:
                continue
            if line.lstrip().startswith("|"):
                continue  # a table row cannot be wrapped
            if HEADING.match(line) or TOC.match(line):
                yield note(f"rule title makes the line {len(line)} columns", f"{tag}:{i}")
                continue
            kind = "code" if fenced else "prose"
            yield fail(f"{kind} line is {len(line)} columns (limit {WIDTH})", f"{tag}:{i}")

        if text.count("```") % 2:
            yield fail("unbalanced code fences", tag)
        if re.search(r"\S```", text):
            yield fail("inline triple backtick", tag)
        if "\r" in text:
            yield fail("CR present", tag)
        if "\t" in text:
            yield fail("hard tab", tag)
        if not text.endswith("\n"):
            yield fail("no trailing newline", tag)
        for i in range(2, len(lines)):
            if lines[i].startswith("#") and lines[i - 1] == "" and lines[i - 2] == "":
                yield fail("blank line doubled before a heading", f"{tag}:{i + 1}")

        yield from _ordered_lists(text, tag)


def _ordered_lists(text: str, tag: str):
    """A numbered list that skips or restarts reads as two lists."""
    run: list[int] = []
    fenced = False
    for line in text.split("\n"):
        if line.startswith("```"):
            fenced = not fenced
            continue
        m = None if fenced else re.match(r"^(\d+)\. ", line)
        if m:
            run.append(int(m.group(1)))
        elif line.strip() and not line.startswith("   "):
            if len(run) > 2 and run != list(range(run[0], run[0] + len(run))):
                yield fail(f"ordered list {run} not contiguous", tag)
            run = []
    if len(run) > 2 and run != list(range(run[0], run[0] + len(run))):
        yield fail(f"ordered list {run} not contiguous", tag)
