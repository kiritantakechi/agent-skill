r"""Reading the check table, including cells holding its own separator.

The reason column was scanned as `[^|]*`, which stops at the first `|` —
including the `\\|` a GFM table requires for a literal pipe. Measured on
the shipped README: the `dialect` row's reason, 159 characters
describing what `\\|` means in two grammars, read back as the two
characters `` ` \\ `` and satisfied "every row carries a reason" on
them.

A check that asks whether a field is present has to read the field.
"""

from pathlib import Path

import pytest

from agent_skill.checks import all_checks
from agent_skill.checks.documented import documented_rows

README = Path(__file__).resolve().parents[1] / "README.md"


#: The README table's header, which makes the lines under it a table.
HEADER = "| Check | Catches | Added because |\n|---|---|---|\n"


def row(name: str, catches: str, why: str) -> str:
    return f"{HEADER}| `{name}` | {catches} | {why} |\n"


def test_the_shipped_table_reads_in_full() -> None:
    """The regression, stated against the row that exhibited it."""
    rows = documented_rows(README.read_text())
    catches, why = rows["dialect"]
    assert why.startswith("`\\|` is alternation"), (
        "the reason was truncated at its escaped pipe"
    )
    assert len(why) > 100, f"read back only {len(why)} characters of the reason"
    assert "syntax from a grammar" in catches


def test_every_shipped_row_carries_a_reason() -> None:
    rows = documented_rows(README.read_text())
    assert rows, "no rows parsed at all"
    thin = {name: why for name, (_, why) in rows.items() if len(why) < 20}
    assert not thin, f"rows whose reason reads as a fragment: {thin}"


@pytest.mark.parametrize(
    "why",
    [
        # opens with the escape
        r"`\|` is alternation to `grep` and a literal pipe to `rg`.",
        # mid-cell
        r"the shape `a\|b` shipped in twenty patterns and matched nothing.",
        # twice
        r"both `\|` and `\(` were carried across, and neither fired.",
    ],
)
def test_an_escaped_pipe_does_not_end_the_cell(why: str) -> None:
    rows = documented_rows(row("dialect", "a pattern in the wrong grammar", why))
    assert rows["dialect"][1] == why


def test_an_unescaped_pipe_still_separates_cells() -> None:
    """The escape is what makes a pipe content.

    A bare one is still the table's own syntax.
    """
    rows = documented_rows(row("dialect", "catches", "first | second"))
    assert rows["dialect"] == ("catches", "second"), (
        "a bare pipe opened a fourth column, "
        "so the reason is the last cell, not the whole tail"
    )


def test_an_empty_reason_is_still_empty() -> None:
    """The fix reads more of the cell; it must not invent content."""
    assert documented_rows(row("dialect", "catches", ""))["dialect"][1] == ""
    assert documented_rows(row("dialect", "catches", "   "))["dialect"][1] == ""


def test_a_row_that_is_not_a_check_row_is_not_read_as_one() -> None:
    assert documented_rows(f"{HEADER}| `dialect` | only one cell |\n") == {}
    assert documented_rows(f"{HEADER}| `Dialect` | a | b |\n") == {}, (
        "the name column is lowercase"
    )


def test_a_row_inside_an_example_is_not_a_row() -> None:
    """The table is read from the tree, where a fence is code."""
    assert documented_rows(f"```markdown\n{row('dialect', 'a', 'b')}```\n") == {}


def test_a_stated_scope_is_read_from_the_first_cell() -> None:
    """A check's `covers` is matched against `catches`, the first cell.

    A shift in the cells would match it against the wrong text.
    """
    rows = documented_rows(README.read_text())
    stated = [c for c in all_checks() if c.covers]
    assert stated, "no check states its scope, so nothing is compared"
    for c in stated:
        assert c.covers in rows[c.name][0], c.name
