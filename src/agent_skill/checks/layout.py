"""The physical shape of the markdown.

Exists because a 135-column line shipped and every check passed —
nothing measured width. This is the sole owner of the physical checks;
when a second check repeated them at a different severity, one defect
produced two findings.

A file is in shape when it is canonical: the text `fmt` prints from the
tree the file parses to. That one comparison owns everything the
printer decides — paragraph width, trailing whitespace, blank lines,
list numbering, the final newline — so none of it is scanned for here
a second way. A branch of its own is kept only for what the printer
leaves as written: an example's body (its tabs, CRs and width), a line
no fill can shorten, a table row's cells, and a fence the file never
closes, which is a file that does not parse as written.
"""

import re
from functools import partial
lazy from collections.abc import Callable, Iterator

from agent_skill.checks import check, per_skill
from agent_skill.doc import (
    WIDTH,
    Block,
    Doc,
    Fence,
    ListBlock,
    Quote,
    Table,
    canonical,
    words,
)
from agent_skill.report import Finding, Level, declare, fail, note
lazy from agent_skill.ids import Location
lazy from agent_skill.model import Skill

#: A line of the file a finding is about, as its location.
type At = Callable[[int], Location]

#: A rule heading and its contents entry are one line by construction:
#: the ID, the tier, the title. Over-length there is a title-length
#: problem, reported separately.
HEADING = re.compile(r"^#{1,6} [A-Z]{2}-[A-Z]+-\d+[a-z]? \[")
TOC = re.compile(r"^\s*- [A-Z]{2}-[A-Z]+-\d+[a-z]? \[")

#: What a line may open with before its text: a quote's `>`, an item's
#: marker.
_MARKS = re.compile(r">|-|\d{1,9}\.")

# The branches a finding of this check comes from.
UNCLOSED = declare("layout", "unclosed", Level.FAIL)
CANONICAL = declare("layout", "canonical", Level.FAIL)
TAB = declare("layout", "tab", Level.FAIL)
CR = declare("layout", "cr", Level.FAIL)
CODE_WIDTH = declare("layout", "code_width", Level.FAIL)
TITLE_WIDTH = declare("layout", "title_width", Level.NOTE)
SPAN_WIDTH = declare("layout", "span_width", Level.NOTE)
PROSE_WIDTH = declare("layout", "prose_width", Level.FAIL)
INLINE_FENCE = declare("layout", "inline_fence", Level.FAIL)
TABLE_CELLS = declare("layout", "table_cells", Level.FAIL)


@check("layout", "canonical form, examples' tabs and width, table cells")
@per_skill
def layout(skill: Skill) -> Iterator[Finding]:
    """The physical shape of every markdown file in the skill.

    The file is read as it is on disk, newlines untranslated: read the
    usual way, every CR became a line break before anything could see
    it. Everything after the canonical comparison is measured on the
    canonical text, so a defect the printer removes is reported once,
    by that comparison, and a line number is the one the file has once
    `fmt` has run.
    """
    for path in skill.markdown:
        text = path.read_text(newline="")
        at = partial(skill.at, path)
        opened = next((b for b in _walk(Doc.parse(text).blocks) if _open(b)), None)
        if opened is not None:
            yield fail("an example's fence is never closed", at(opened.line), UNCLOSED)
            continue
        want = canonical(text)
        tree = Doc.parse(want)
        yield from _canonical(text, want, at)
        yield from _kept(want, at)
        yield from _widths(want, tree, at)
        yield from _inline_fences(want, tree, at)
        yield from _table_cells(tree, at)


def _walk(blocks: tuple[Block, ...]) -> Iterator[Block]:
    """Every block in `blocks`, nested ones included, in order."""
    for block in blocks:
        yield block
        match block:
            case ListBlock(items):
                for item in items:
                    yield from _walk(item.blocks)
            case Quote(inner):
                yield from _walk(inner)
            case _:
                pass


def _open(block: Block) -> bool:
    """Is `block` a fence its file or list item ends inside?"""
    return isinstance(block, Fence) and not block.closed


def _code(tree: Doc) -> set[int]:
    """Every line a fence of `tree` is printed on, its own included."""
    return {
        i
        for b in _walk(tree.blocks)
        if isinstance(b, Fence)
        for i in range(b.line, b.line + b.body.count("\n") + 2)
    }


def _canonical(text: str, want: str, at: At) -> Iterator[Finding]:
    """The first line where the file is not what `fmt` would print."""
    if text == want:
        return
    have, wanted = text.split("\n"), want.split("\n")
    i = next(
        (k for k, (a, b) in enumerate(zip(have, wanted, strict=False)) if a != b),
        min(len(have), len(wanted)),
    )
    if f"{text}\n" == want:
        differs = "the file does not end in a newline"
    else:
        differs = f"the line is {_shown(have, i)}, canonical is {_shown(wanted, i)}"
    yield fail(
        f"not in canonical form: {differs} — `agent-skill fmt` re-prints it",
        at(i + 1),
        CANONICAL,
    )


def _shown(lines: list[str], i: int) -> str:
    """Line `i` of `lines` quoted, its tabs and CRs made visible."""
    if i >= len(lines):
        return "the end of the file"
    line = lines[i][:60].replace("\t", "\\t").replace("\r", "\\r")
    return f"`{line}`"


def _kept(want: str, at: At) -> Iterator[Finding]:
    """A tab or a CR the printer keeps: in an example, a span, a cell.

    One in running text is whitespace the printer removes, which
    `_canonical` reports.
    """
    for char, name, branch in (("\t", "hard tab", TAB), ("\r", "CR present", CR)):
        if (found := want.find(char)) >= 0:
            yield fail(name, at(want.count("\n", 0, found) + 1), branch)


def _lone(line: str) -> bool:
    """Is `line`, past its markers, one word filling cannot split?"""
    found = list(words(line))
    while found and _MARKS.fullmatch(found[0]):
        found.pop(0)
    return len(found) == 1


def _widths(want: str, tree: Doc, at: At) -> Iterator[Finding]:
    """Lines past `WIDTH` that no fill could bring under it.

    An example's line is the example's to shorten, and fails. A rule
    title is one line by construction, and a code span or link is never
    split, so either may pass the limit alone; each is a note. The
    frontmatter and a table row, an example's included, are not
    measured: neither can wrap.
    """
    head = 0 if tree.frontmatter is None else tree.frontmatter.count("\n") + 3
    code = _code(tree)
    for i, line in enumerate(want.split("\n"), 1):
        if len(line) <= WIDTH or i <= head or line.lstrip(" >").startswith("|"):
            continue
        where = at(i)
        if i in code:
            yield fail(
                f"code line is {len(line)} columns (limit {WIDTH})", where, CODE_WIDTH
            )
        elif HEADING.match(line) or TOC.match(line):
            yield note(
                f"rule title makes the line {len(line)} columns", where, TITLE_WIDTH
            )
        elif _lone(line):
            yield note(
                f"a code span or link no line can hold makes the line {len(line)} "
                "columns",
                where,
                SPAN_WIDTH,
            )
        else:
            yield fail(
                f"prose line is {len(line)} columns (limit {WIDTH})", where, PROSE_WIDTH
            )


def _inline_fences(want: str, tree: Doc, at: At) -> Iterator[Finding]:
    """Three backticks inside running text, read differently by each."""
    code = _code(tree)
    for i, line in enumerate(want.split("\n"), 1):
        if i not in code and re.search(r"\S```", line):
            yield fail("inline triple backtick", at(i), INLINE_FENCE)


def _table_cells(tree: Doc, at: At) -> Iterator[Finding]:
    r"""Every row of a table has as many cells as its header.

    A `|` inside a code span in a cell, `X | None`, splits that cell on
    GitHub, and nothing else measured it. The printer keeps the cells it
    read, so a row split that way is canonical and only this sees it.
    """
    for table in (b for b in _walk(tree.blocks) if isinstance(b, Table)):
        for k, row in enumerate(table.rows):
            if len(row) != len(table.header):
                yield fail(
                    f"a table row has {len(row)} cells where its header has "
                    f"{len(table.header)}; write a `|` inside a cell as `\\|`",
                    at(table.line + 2 + k),
                    TABLE_CELLS,
                )
