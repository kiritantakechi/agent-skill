"""Rule shape under standard-structure: numbering, Why length, lint rows, rename tables."""

from __future__ import annotations

import pytest
from structure_fixture import build, edit, reparse

from agent_skill.checks.anatomy import structural
from agent_skill.checks.citations import python_rows, row_shape
from agent_skill.checks.skeleton import shape
from agent_skill.model import DASH, Rename

ROWS = """

## Decided by tools

| Tool | Lint | Level | Forbids |
|---|---|---|---|
| ruff | `B006` | error | a mutable default argument |
| ty | `possibly-unresolved-reference` | warn | a name that may not be bound |
"""

RANGES = f"Before the revision the families ran `DS-ERR-01`{DASH}`DS-ERR-09`."

RENAMES = f"""

## Rule IDs before the Demo 1.2 revision

{RANGES}

| Before | Now |
|---|---|
| `DS-ERR-07` | `DS-ERR-02` |
| `DS-ERR-08` | lint `ruff:B006` |
| `DS-ERR-09` | removed — said nothing the compiler does not |
"""


@pytest.fixture
def demo(tmp_path):
    return build(tmp_path)


def structural_messages(skill) -> list[str]:
    return [m for m, _ in structural(skill)]


def test_a_gap_in_the_numbering(demo):
    broken = edit(demo, "references/errors.md", "DS-ERR-02", "DS-ERR-03")
    broken = edit(broken, "references/errors.md", "DS-ERR-02", "DS-ERR-03")
    assert any("should be DS-ERR-02" in m for m in structural_messages(broken))


def test_a_suffixed_number(demo):
    broken = edit(demo, "references/errors.md", "### DS-ERR-02", "### DS-ERR-01a")
    broken = edit(broken, "references/errors.md", "- DS-ERR-02", "- DS-ERR-01a")
    assert any("no suffix" in m for m in structural_messages(broken))


def test_a_four_line_why(demo):
    broken = edit(
        demo, "references/errors.md", "**Why:** one line of reason.", "**Why:** a\nb\nc\nd."
    )
    assert any("Why runs 4 lines" in m for m in structural_messages(broken))


def test_a_three_line_why_is_fine(demo):
    fine = edit(demo, "references/errors.md", "**Why:** one line of reason.", "**Why:** a\nb\nc.")
    assert structural_messages(fine) == []


def test_lint_rows_are_parsed_and_are_not_rules(demo):
    path = demo.root / "references" / "errors.md"
    path.write_text(path.read_text() + ROWS)
    skill = reparse(demo)
    rows = skill.lint_rows
    assert [(r.tool, r.lint, r.level) for r in rows] == [
        ("ruff", "B006", "error"),
        ("ty", "possibly-unresolved-reference", "warn"),
    ]
    assert [r.id for r in skill.rules] == ["DS-ERR-01", "DS-ERR-02", "DS-MIG-01"]
    assert "Decided by tools" not in skill.by_id["DS-ERR-02"].body


def test_a_row_for_a_tool_the_standard_does_not_require(demo):
    path = demo.root / "references" / "errors.md"
    path.write_text(path.read_text() + ROWS)
    skill = reparse(demo)
    found = [message for _, message in row_shape(skill.lint_rows, ("python", "ruff"))]
    assert found == ["`ty` is not a tool this standard requires"]


def test_a_row_at_a_level_that_fails_nothing(demo):
    path = demo.root / "references" / "errors.md"
    path.write_text(path.read_text() + ROWS.replace("| warn |", "| ignore |"))
    skill = reparse(demo)
    found = [message for _, message in row_shape(skill.lint_rows, ("ruff", "ty"))]
    assert any("fails no run" in m for m in found)


def test_python_rows_against_the_shipped_configuration(demo):
    path = demo.root / "references" / "errors.md"
    path.write_text(path.read_text() + ROWS)
    rows = reparse(demo).lint_rows
    assert list(python_rows(rows, {"B006"}, {"possibly-unresolved-reference": "warn"})) == []
    off = [m for _, m in python_rows(rows, set(), {"possibly-unresolved-reference": "warn"})]
    assert off == ["`B006` is a row, and `assets/ruff.toml` does not enable it"]
    level = [m for _, m in python_rows(rows, {"B006"}, {"possibly-unresolved-reference": "error"})]
    assert level == ["`possibly-unresolved-reference` is `warn` in the row and `error` as shipped"]
    unknown = [m for _, m in python_rows(rows, {"B006"}, {})]
    assert unknown == ["`possibly-unresolved-reference` is not a rule the pinned ty recognises"]


def test_rename_rows_parse_three_ways():
    assert Rename("A", "`DS-ERR-02`", 1).target == "DS-ERR-02"
    assert Rename("A", "lint `ruff:B006`", 1).lint == ("ruff", "B006")
    assert Rename("A", "removed — said nothing", 1).removed == "said nothing"


def test_a_rename_table_that_resolves(demo):
    rows = demo.root / "references" / "errors.md"
    rows.write_text(rows.read_text() + ROWS)
    path = demo.root / "references" / "migration.md"
    path.write_text(path.read_text() + RENAMES)
    skill = reparse(demo)
    assert len(skill.renames) == 3
    assert [m for m, _ in shape(skill) if "renamed" in m or "became" in m or "removed" in m] == []


def test_a_rename_table_states_its_ranges(demo):
    path = demo.root / "references" / "migration.md"
    path.write_text(
        path.read_text() + RENAMES.replace("`DS-ERR-09`.", "`DS-ERR-09` and `DS-MIG-01`.")
    )
    (table,) = reparse(demo).rename_tables
    assert table.ranges == (("DS-ERR", 1, 9), ("DS-MIG", 1, 1))
    assert table.unchanged[:2] == ["DS-ERR-01", "DS-ERR-02"]
    assert table.unchanged[-1] == "DS-MIG-01"


def test_an_unlisted_id_no_rule_carries(demo):
    path = demo.root / "references" / "migration.md"
    path.write_text(path.read_text() + RENAMES)
    found = [m for m, _ in shape(reparse(demo))]
    assert "DS-ERR-01 has no row" not in " ".join(found)
    assert any(m.startswith("DS-ERR-03 has no row") for m in found)


def test_a_table_that_states_no_ranges(demo):
    path = demo.root / "references" / "migration.md"
    path.write_text(path.read_text() + RENAMES.replace(f"{RANGES}\n\n", ""))
    assert any("states no ranges" in m for m, _ in shape(reparse(demo)))


def test_a_row_mapping_an_id_to_itself(demo):
    path = demo.root / "references" / "migration.md"
    path.write_text(path.read_text() + RENAMES + "| `DS-ERR-01` | `DS-ERR-01` |\n")
    assert any("becoming itself" in m for m, _ in shape(reparse(demo)))


def test_a_rename_into_a_rule_that_was_deleted(demo):
    path = demo.root / "references" / "migration.md"
    path.write_text(path.read_text() + RENAMES.replace("`DS-ERR-02` |", "`DS-ERR-05` |"))
    skill = reparse(demo)
    assert any("which no rule carries" in m for m, _ in shape(skill))


def test_a_demotion_into_a_row_no_chapter_lists(demo):
    path = demo.root / "references" / "migration.md"
    path.write_text(path.read_text() + RENAMES)
    skill = reparse(demo)
    assert any("which no chapter lists" in m for m, _ in shape(skill))


def test_a_removal_without_a_reason(demo):
    path = demo.root / "references" / "migration.md"
    text = RENAMES.replace("removed — said nothing the compiler does not", "removed — ")
    path.write_text(path.read_text() + text)
    skill = reparse(demo)
    assert any("gives no reason" in m for m, _ in shape(skill))


def test_rust_rows_against_the_shipped_lint_table(demo):
    from agent_skill.checks.citations import rust_rows
    from agent_skill.model import LintRow

    def row(tool, lint, level):
        return LintRow(tool, lint, level, "x", "errors.md", 1)

    catalogue = {
        "clippy.unwrap_used": ("allow", set()),
        "clippy.cast_lossless": ("allow", {"pedantic"}),
        "rust.unsafe_code": ("allow", set()),
    }
    shipped = {
        "clippy.unwrap_used": '"deny"',
        "clippy.pedantic": '{ level = "warn", priority = -1 }',
        "rust.unsafe_code": '"forbid"',
    }
    fine = [row("clippy", "unwrap_used", "deny"), row("clippy", "cast_lossless", "warn")]
    fine.append(row("rustc", "unsafe_code", "forbid"))
    assert list(rust_rows(fine, shipped, catalogue)) == []
    wrong = [m for _, m in rust_rows([row("clippy", "unwrap_used", "warn")], shipped, catalogue)]
    assert wrong == ["`unwrap_used` is `warn` in the row and `deny` as shipped"]
    unknown = [m for _, m in rust_rows([row("clippy", "unwarp_used", "deny")], shipped, catalogue)]
    assert unknown == ["`unwarp_used` is not a clippy lint the pinned toolchain knows"]


def test_the_rust_catalogue_reads_the_toolchain():
    import pytest

    from agent_skill.checks.citations import rust_catalogue

    catalogue = rust_catalogue()
    if catalogue is None:
        pytest.skip("clippy-driver or rustdoc is not installed")
    assert catalogue["clippy.unwrap_used"][0] == "allow"
    assert "pedantic" in catalogue["clippy.cast_lossless"][1]
    assert "rust.unsafe_code" in catalogue
    assert "rustdoc.broken_intra_doc_links" in catalogue


def test_a_bold_phrase_inside_a_why_does_not_end_it(demo):
    """A Why ends at the next label, not at the next line that opens with `**`."""
    long_why = "**Why:** one.\n**Two** is bold.\nthree.\nfour."
    broken = edit(demo, "references/errors.md", "**Why:** one line of reason.", long_why)
    assert any("Why runs 4 lines" in m for m in structural_messages(broken))


def test_an_escaped_pipe_stays_inside_its_cell(demo):
    rows = """

## Decided by tools

| Tool | Lint | Level | Forbids |
|---|---|---|---|
| clippy | `map_clone` | warn | `.map(\\|x\\| x.clone())` — `.cloned()` |
"""
    path = demo.root / "references" / "errors.md"
    path.write_text(path.read_text() + rows)
    (row,) = reparse(demo).lint_rows
    assert (row.lint, row.forbids) == ("map_clone", "`.map(|x| x.clone())` — `.cloned()`")
