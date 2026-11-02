"""The physical shape of the markdown.

Exists because a 135-column line shipped and every check passed —
nothing measured width. This is the sole owner of the physical checks;
when a second check repeated them at a different severity, one defect
produced two findings.
"""

import re
lazy from collections.abc import Iterator

from agent_skill.checks import check
from agent_skill.doc import WIDTH, words
from agent_skill.report import Finding, fail, note
lazy from agent_skill.model import Skill

#: A rule heading and its contents entry are one line by construction:
#: the ID, the tier, the title. Rewrapping either corrupts it — that is
#: how nineteen zig contents entries were once truncated. Over-length
#: there is a title-length problem, reported separately.
HEADING = re.compile(r"^#{1,6} [A-Z]{2}-[A-Z]+-\d+[a-z]? \[")
TOC = re.compile(r"^\s*- [A-Z]{2}-[A-Z]+-\d+[a-z]? \[")


#: The fewest numbered lines judged as one list.
_JUDGED = 3


#: A table's separator row: `|---|:--:|` and the like.
_SEPARATOR = re.compile(r"^\|(?:\s*:?-+:?\s*\|)+\s*$")


@check("layout", "line width, whitespace, fences, table cells")
def layout(skill: Skill) -> Iterator[Finding]:
    """The physical shape of every markdown file in the skill."""
    for path in skill.markdown:
        text = path.read_text()
        tag = f"{skill.name}/{path.name}"
        lines = text.split("\n")
        yield from _trailing(lines, tag)
        yield from _widths(lines, tag)
        yield from _whole_file(text, tag)
        yield from _doubled_blanks(lines, tag)
        yield from _ordered_lists(text, tag)
        yield from _table_cells(lines, tag)


def _trailing(lines: list[str], tag: str) -> Iterator[Finding]:
    """Trailing whitespace on any line, fenced or not."""
    for i, line in enumerate(lines, 1):
        if line != line.rstrip():
            yield fail("trailing whitespace", f"{tag}:{i}")


def _widths(lines: list[str], tag: str) -> Iterator[Finding]:
    """Lines past `WIDTH`, outside the frontmatter.

    Its own branch, apart from trailing whitespace: the control for this
    one ended its line in a space, so it fired through the other branch
    and would have kept firing with this one gone.
    """
    # How many lines the frontmatter runs to, both fences included; none
    # when there is no frontmatter. This was the closing fence's index,
    # 0 without one, and lines up to it plus one were skipped — so line
    # 1 of every chapter was never measured.
    frontmatter = 0
    if lines and lines[0] == "---":
        frontmatter = next(
            (i + 1 for i, ln in enumerate(lines[1:], 1) if ln == "---"), 1
        )

    fenced = False
    for i, line in enumerate(lines, 1):
        if line.startswith("```"):
            fenced = not fenced
            continue
        if i <= frontmatter or len(line) <= WIDTH:
            continue
        if line.lstrip().startswith("|"):
            continue  # a table row cannot be wrapped
        if HEADING.match(line) or TOC.match(line):
            yield note(f"rule title makes the line {len(line)} columns", f"{tag}:{i}")
            continue
        if not fenced and len(words(line.strip())) == 1:
            # A code span or a link is never split, so one wider than
            # the limit has a line of its own and passes it.
            yield note(
                f"a code span or link no line can hold makes the line {len(line)} "
                "columns",
                f"{tag}:{i}",
            )
            continue
        kind = "code" if fenced else "prose"
        yield fail(f"{kind} line is {len(line)} columns (limit {WIDTH})", f"{tag}:{i}")


def _whole_file(text: str, tag: str) -> Iterator[Finding]:
    """Fence balance and the characters a file must not contain."""
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


def _doubled_blanks(lines: list[str], tag: str) -> Iterator[Finding]:
    """A heading with two blank lines above it.

    Fence-aware: `#` opens a heading in markdown and a comment in
    Python, and `ruff format` puts two blank lines before a top-level
    statement — so an unfenced test reads correct formatting as a
    doubled blank.
    """
    in_fence = False
    for i in range(2, len(lines)):
        if lines[i].startswith("```"):
            in_fence = not in_fence
        elif (
            not in_fence
            and lines[i].startswith("#")
            and lines[i - 1] == ""
            and lines[i - 2] == ""
        ):
            yield fail("blank line doubled before a heading", f"{tag}:{i + 1}")


def _ordered_lists(text: str, tag: str) -> Iterator[Finding]:
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
            if len(run) >= _JUDGED and run != list(range(run[0], run[0] + len(run))):
                yield fail(f"ordered list {run} not contiguous", tag)
            run = []
    if len(run) >= _JUDGED and run != list(range(run[0], run[0] + len(run))):
        yield fail(f"ordered list {run} not contiguous", tag)


def _cells(row: str) -> int:
    r"""How many cells a table row holds, split on each unescaped `|`.

    A code span does not protect a pipe: GitHub-flavoured Markdown
    splits the cell there unless it is written `\|`.
    """
    inner = row.strip().removeprefix("|").removesuffix("|")
    return len(re.split(r"(?<!\\)\|", inner))


def _table_cells(lines: list[str], tag: str) -> Iterator[Finding]:
    """Every row of a table has as many cells as its header.

    A `|` inside a code span in a cell, `X | None`, splits that cell on
    GitHub, and nothing else measured it.
    """
    fenced, header = False, 0
    for i, line in enumerate(lines):
        if line.lstrip().startswith("```"):
            fenced = not fenced
            continue
        if fenced:
            continue
        if not line.startswith("|"):
            header = 0
        elif _SEPARATOR.match(line) and i > 0:
            header = _cells(lines[i - 1])
        elif header and (n := _cells(line)) != header:
            yield fail(
                f"a table row has {n} cells where its header has {header}; "
                "write a `|` inside a cell as `\\|`",
                f"{tag}:{i + 1}",
            )
