"""The physical shape of the markdown: table cells and line width."""

import pytest

from agent_skill.checks.layout import WIDTH, _table_cells, _widths
from agent_skill.report import Level

TABLE = ["| Stale | Current |", "|---|---|"]

#: A prose line one column over the limit.
LONG = "x" * (WIDTH + 1)


def test_a_pipe_inside_a_code_span_splits_the_cell() -> None:
    [found] = _table_cells([*TABLE, "| `Optional[X]` | `X | None` |"], "t.md")
    assert found.message.startswith("a table row has 3 cells where its header has 2")
    assert found.where == "t.md:3"


def test_an_escaped_pipe_does_not() -> None:
    row = "| `Optional[X]` | `X \\| None` |"
    assert list(_table_cells([*TABLE, row], "t.md")) == []


def test_a_fenced_table_is_not_read() -> None:
    lines = ["```", *TABLE, "| a | b | c |", "```"]
    assert list(_table_cells(lines, "t.md")) == []


def test_the_first_line_of_a_chapter_is_measured() -> None:
    """With no frontmatter, line 1 was skipped as if it closed one."""
    [found] = _widths([LONG, "", "short"], "t.md")
    assert found.where == "t.md:1"


@pytest.mark.parametrize(
    ("lines", "measured"),
    [
        (["---", f"description: {LONG}", "---"], []),
        (["---", f"description: {LONG}"], ["t.md:2"]),
    ],
    ids=["frontmatter", "an opening fence that never closes"],
)
def test_only_frontmatter_goes_unmeasured(
    lines: list[str], measured: list[str]
) -> None:
    found = list(_widths([*lines, "short"], "t.md"))
    assert [f.where for f in found] == measured


def test_a_code_span_no_line_can_hold_is_a_note() -> None:
    span = "`" + "x" * WIDTH + "`."
    [found] = _widths(["see", span, "after"], "t.md")
    assert found.level is Level.NOTE
    assert found.where == "t.md:2"
