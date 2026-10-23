"""The physical shape of the markdown: table cells."""

from agent_skill.checks.layout import _table_cells

TABLE = ["| Stale | Current |", "|---|---|"]


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
