"""The physical shape of markdown: its canonical form, and the rest."""

lazy from pathlib import Path

import pytest

from agent_skill.checks.layout import WIDTH, layout
from agent_skill.model import Skill
from agent_skill.report import Finding, Level
from structure_fixture import Demo

TABLE = "| Stale | Current |\n|---|---|\n"

#: A word one column wider than any line.
LONG = "x" * (WIDTH + 1)


def found(tmp_path: Path, text: str) -> list[Finding]:
    """What `layout` reports for a skill whose `SKILL.md` is `text`."""
    root = tmp_path / "demo-style"
    root.mkdir(parents=True)
    (root / "SKILL.md").write_text(text)
    return list(layout(Skill(root, Demo())))


def failures(tmp_path: Path, text: str) -> list[str]:
    return [
        f"{f.where}: {f.message}"
        for f in found(tmp_path, text)
        if f.level is Level.FAIL
    ]


def test_a_canonical_file_is_in_shape(tmp_path: Path) -> None:
    text = f"# Title\n\nA paragraph.\n\n{TABLE}| a | b |\n\n```zig\nconst x = 1;\n```\n"
    assert found(tmp_path, text) == []


@pytest.mark.parametrize(
    ("text", "line"),
    [
        ("# Title\n\nA line   \n", 3),
        ("# Title\n\n\n## Section\n", 3),
        ("# Title\n\nno trailing newline", 4),
        ("# Title\r\n\r\nA line.\r\n", 1),
        ("# Title\n\n1. one\n3. two\n", 4),
        (f"# Title\n\n{'word ' * 30}end\n", 3),
    ],
    ids=[
        "trailing whitespace",
        "a doubled blank",
        "no final newline",
        "CRLF line ends",
        "a list's numbers",
        "a long paragraph",
    ],
)
def test_what_the_printer_decides_is_one_finding_at_its_first_line(
    tmp_path: Path, text: str, line: int
) -> None:
    [one] = failures(tmp_path, text)
    assert one.startswith(f"demo-style/SKILL.md:{line}: not in canonical form")


def test_a_fence_left_open_does_not_parse_and_is_reported_alone(tmp_path: Path) -> None:
    assert failures(tmp_path, "# Title\n\n```zig\nconst x = 1;\n") == [
        "demo-style/SKILL.md:3: an example's fence is never closed"
    ]


def test_an_example_keeps_its_tabs_its_crs_and_its_width(tmp_path: Path) -> None:
    text = f"# Title\n\n```zig\n\tconst x = 1;\nconst y\r= 2;\n{LONG}\n```\n"
    assert failures(tmp_path, text) == [
        "demo-style/SKILL.md:4: hard tab",
        "demo-style/SKILL.md:5: CR present",
        f"demo-style/SKILL.md:6: code line is {WIDTH + 1} columns (limit {WIDTH})",
    ]


def test_a_tab_in_running_text_is_the_printers_to_remove(tmp_path: Path) -> None:
    [one] = failures(tmp_path, "# Title\n\nA\ttab.\n")
    assert "not in canonical form" in one


def test_a_code_span_no_line_can_hold_is_a_note(tmp_path: Path) -> None:
    span = f"`{LONG}`."
    [one] = found(tmp_path, f"# Title\n\nsee\n{span}\nafter\n")
    assert one.level is Level.NOTE
    assert one.where == "demo-style/SKILL.md:4"
    [item] = found(tmp_path / "item", f"# Title\n\n- {span}\n")
    assert item.level is Level.NOTE


def test_a_long_rule_title_is_a_note(tmp_path: Path) -> None:
    [one] = found(tmp_path, f"# Title\n\n### DS-ERR-01 [M] {'word ' * 20}end\n")
    assert one.level is Level.NOTE
    assert one.message.startswith("rule title makes the line")


def test_frontmatter_and_table_rows_go_unmeasured(tmp_path: Path) -> None:
    text = f"---\ndescription: {LONG}\n---\n\n{TABLE}| {LONG} | b |\n"
    assert found(tmp_path, text) == []


def test_a_pipe_inside_a_code_span_splits_the_cell(tmp_path: Path) -> None:
    text = f"# Title\n\n{TABLE}| `Optional[X]` | `X | None` |\n"
    [one] = failures(tmp_path, text)
    assert one.startswith(
        "demo-style/SKILL.md:5: a table row has 3 cells where its header has 2"
    )


def test_an_escaped_pipe_does_not(tmp_path: Path) -> None:
    text = f"# Title\n\n{TABLE}| `Optional[X]` | `X \\| None` |\n"
    assert failures(tmp_path, text) == []


def test_a_table_inside_an_example_is_not_read(tmp_path: Path) -> None:
    text = f"# Title\n\n```markdown\n{TABLE}| a | b | c |\n```\n"
    assert failures(tmp_path, text) == []


def test_three_backticks_inside_running_text(tmp_path: Path) -> None:
    [one] = failures(tmp_path, "# Title\n\nSee x```zig here.\n")
    assert one == "demo-style/SKILL.md:3: inline triple backtick"
