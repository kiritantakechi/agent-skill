"""Rule shape under standard-structure.

Numbering, Why length, lint rows, and rename tables.
"""

from dataclasses import dataclass
from typing import override
lazy from pathlib import Path

import pytest

from agent_skill.checks import by_name
from agent_skill.checks.anatomy import structural
from agent_skill.checks.citations import (
    python_rows,
    row_shape,
    rust_catalogue,
    rust_rows,
)
from agent_skill.checks.skeleton import shape
from agent_skill.model import DASH, LintRow, Rename
from structure_fixture import Demo, build, edit, reparse
lazy from agent_skill.model import Skill

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
def demo(tmp_path: Path) -> Skill:
    return build(tmp_path)


def structural_messages(skill: Skill) -> list[str]:
    return [m for m, _ in structural(skill)]


def test_a_gap_in_the_numbering(demo: Skill) -> None:
    broken = edit(demo, "references/errors.md", "DS-ERR-02", "DS-ERR-03")
    broken = edit(broken, "references/errors.md", "DS-ERR-02", "DS-ERR-03")
    assert any("should be DS-ERR-02" in m for m in structural_messages(broken))


def test_a_suffixed_number(demo: Skill) -> None:
    broken = edit(demo, "references/errors.md", "### DS-ERR-02", "### DS-ERR-01a")
    broken = edit(broken, "references/errors.md", "- DS-ERR-02", "- DS-ERR-01a")
    assert any("no suffix" in m for m in structural_messages(broken))


def test_a_four_line_why(demo: Skill) -> None:
    broken = edit(
        demo,
        "references/errors.md",
        "**Why:** one line of reason.",
        "**Why:** a\nb\nc\nd.",
    )
    assert any("Why runs 4 lines" in m for m in structural_messages(broken))


def anatomy_messages(skill: Skill) -> list[str]:
    check = by_name("anatomy")
    assert check is not None
    return [f.message for f in check.run([skill]).findings]


def test_a_relaxed_form_after_the_why_fails(demo: Skill) -> None:
    broken = edit(
        demo,
        "references/errors.md",
        "**Check:** read it.",
        "**Check:** read it.\n\n*Relaxed form:* skip it in tests.",
    )
    assert (
        "DS-ERR-01's relaxed form follows its Why; it is part of the statement, "
        "so it comes first" in anatomy_messages(broken)
    )


def test_a_relaxed_form_has_one_label(demo: Skill) -> None:
    broken = edit(
        demo,
        "references/errors.md",
        "Return errors.\n",
        "Return errors.\n\n**Relaxed form:** x.\n",
    )
    assert any(
        "labels its relaxed form `**Relaxed form:**`" in m
        for m in anatomy_messages(broken)
    )


def test_a_relaxed_label_filled_across_two_lines_is_still_its_label(
    demo: Skill,
) -> None:
    """Filling breaks a paragraph between any two words, these too."""
    marked = edit(demo, "references/errors.md", "- DS-ERR-01 [M]", "- DS-ERR-01 [M!]")
    marked = edit(
        marked, "references/errors.md", "### DS-ERR-01 [M]", "### DS-ERR-01 [M!]"
    )
    assert any("[M!] with no relaxed form" in m for m in anatomy_messages(marked))
    marked = edit(
        marked,
        "references/errors.md",
        "Return errors.\n",
        "Return errors. *Relaxed\nform:* x.\n",
    )
    assert not any("relaxed form" in m for m in anatomy_messages(marked))


def test_a_bold_citation_that_opens_a_line_defines_nothing(demo: Skill) -> None:
    cited = edit(
        demo,
        "references/errors.md",
        "Return errors.\n",
        "Return errors, as\n**DS-ERR-02** says.\n",
    )
    assert "bold-inline rule definitions" not in anatomy_messages(cited)
    defined = edit(
        cited, "references/errors.md", "Name them.\n", "**DS-ERR-02** Name them.\n"
    )
    assert "bold-inline rule definitions" in anatomy_messages(defined)


def test_a_citation_broken_across_lines_is_still_read(demo: Skill) -> None:
    broken = edit(
        demo,
        "references/errors.md",
        "read it.",
        "read `references/migration.md`\nDS-ERR-01.",
    )
    assert (
        "says migration.md for DS-ERR-01, which lives in errors.md"
        in anatomy_messages(broken)
    )


def test_an_abbreviated_id_list_fails(demo: Skill) -> None:
    broken = edit(demo, "references/errors.md", "read it.", "read DS-ERR-01, -02.")
    check = by_name("anatomy")
    assert check is not None
    messages = [f.message for f in check.run([broken]).findings]
    assert any("`DS-ERR-01, -02` abbreviates rule IDs" in m for m in messages)


def test_a_rule_that_only_points_at_its_owner_fails(demo: Skill) -> None:
    """No pointer form exists any more: a rule without a Why is one."""
    broken = edit(
        demo,
        "references/errors.md",
        "Name them.\n\n**Why:** one line of reason.\n\n**Check:** read it.",
        "Owned by DS-ERR-01.",
    )
    check = by_name("anatomy")
    assert check is not None
    messages = [f.message for f in check.run([broken]).findings]
    assert "DS-ERR-02 states no Why" in messages


def test_a_three_line_why_is_fine(demo: Skill) -> None:
    fine = edit(
        demo,
        "references/errors.md",
        "**Why:** one line of reason.",
        "**Why:** a\nb\nc.",
    )
    assert structural_messages(fine) == []


@dataclass
class Twenty(Demo):
    """The demo at 1.20, whose older releases have two-digit minors."""

    @override
    def pin(self) -> str:
        return "1.20.3"


@pytest.fixture
def twenty(tmp_path: Path) -> Skill:
    return build(tmp_path, Twenty())


def test_a_rule_naming_an_older_release(twenty: Skill) -> None:
    broken = edit(
        twenty, "references/errors.md", "one line of reason.", "stable since 1.13."
    )
    assert [m for m in structural_messages(broken) if " names " in m] == [
        (
            "DS-ERR-01 names 1.13, below its target 1.20: a rule speaks of its "
            "target, and the migration chapter keeps the history"
        )
    ]


@pytest.mark.parametrize("prose", ["stable since 1.9.", "1.9 and 1.13 added it."])
def test_a_one_digit_minor_is_an_older_release(twenty: Skill, prose: str) -> None:
    """Two digits were needed: `since 3.9` passed, `since 3.13` not."""
    broken = edit(twenty, "references/errors.md", "one line of reason.", prose)
    assert any("DS-ERR-01 names 1.9" in m for m in structural_messages(broken)), (
        structural_messages(broken)
    )


def test_a_title_naming_an_older_release(twenty: Skill) -> None:
    broken = edit(
        twenty,
        "references/errors.md",
        "### DS-ERR-02 [M] Name them",
        "### DS-ERR-02 [M] As 1.13",
    )
    assert any("DS-ERR-02 names 1.13" in m for m in structural_messages(broken))


def test_a_core_rule_naming_an_older_release(twenty: Skill) -> None:
    broken = edit(
        twenty,
        "SKILL.md",
        "## 4. Core rules\n\nNone.",
        "## 4. Core rules\n\n- **DS-CORE-01 `[M]`** Use the call 1.18 added.",
    )
    assert any("DS-CORE-01 names 1.18" in m for m in structural_messages(broken))


@pytest.mark.parametrize(
    ("rel", "old", "new"),
    [
        ("references/migration.md", "one line of reason.", "1.13 renamed it."),
        ("SKILL.md", "Nothing changed.", "1.13 renamed it."),
        ("references/review-checklist.md", "Run the tools.", "Grep for 1.13's name."),
        (
            "references/errors.md",
            "**Check:** read it.",
            '**Check:** read it.\n\n```rust\n// fragment\nlet v = "1.13";\n```',
        ),
        (
            "references/errors.md",
            "one line of reason.",
            "1.20 and 1.21 are fine, and so are 1.5x faster and 1.05 s.",
        ),
        (
            "references/errors.md",
            "one line of reason.",
            'a caret `"1.2"`, a literal `wait(\n1.5)` and ~1.3 ns.',
        ),
    ],
    ids=["migration", "reality check", "protocol", "fenced", "not older", "code"],
)
def test_a_version_that_is_history_or_no_release(
    twenty: Skill, rel: str, old: str, new: str
) -> None:
    fine = edit(twenty, rel, old, new)
    assert [m for m in structural_messages(fine) if " names " in m] == []


def test_lint_rows_are_parsed_and_are_not_rules(demo: Skill) -> None:
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


def test_a_row_for_a_tool_the_standard_does_not_require(demo: Skill) -> None:
    path = demo.root / "references" / "errors.md"
    path.write_text(path.read_text() + ROWS)
    skill = reparse(demo)
    found = [message for _, message in row_shape(skill.lint_rows, ("python", "ruff"))]
    assert found == ["`ty` is not a tool this standard requires"]


def test_a_row_at_a_level_that_fails_nothing(demo: Skill) -> None:
    path = demo.root / "references" / "errors.md"
    path.write_text(path.read_text() + ROWS.replace("| warn |", "| ignore |"))
    skill = reparse(demo)
    found = [message for _, message in row_shape(skill.lint_rows, ("ruff", "ty"))]
    assert any("fails no run" in m for m in found)


def test_python_rows_against_the_shipped_configuration(demo: Skill) -> None:
    path = demo.root / "references" / "errors.md"
    path.write_text(path.read_text() + ROWS)
    rows = reparse(demo).lint_rows
    assert (
        list(python_rows(rows, {"B006"}, {"possibly-unresolved-reference": "warn"}))
        == []
    )
    off = [
        m
        for _, m in python_rows(rows, set(), {"possibly-unresolved-reference": "warn"})
    ]
    assert off == ["`B006` is a row, and `assets/ruff.toml` does not enable it"]
    level = [
        m
        for _, m in python_rows(
            rows, {"B006"}, {"possibly-unresolved-reference": "error"}
        )
    ]
    assert level == [
        "`possibly-unresolved-reference` is `warn` in the row and `error` as shipped"
    ]
    unknown = [m for _, m in python_rows(rows, {"B006"}, {})]
    assert unknown == [
        "`possibly-unresolved-reference` is not a rule the pinned ty recognises"
    ]


def test_rename_rows_parse_three_ways() -> None:
    assert Rename("A", "`DS-ERR-02`", 1).target == "DS-ERR-02"
    assert Rename("A", "lint `ruff:B006`", 1).lint == ("ruff", "B006")
    assert Rename("A", "removed — said nothing", 1).removed == "said nothing"


def test_a_rename_table_that_resolves(demo: Skill) -> None:
    rows = demo.root / "references" / "errors.md"
    rows.write_text(rows.read_text() + ROWS)
    path = demo.root / "references" / "migration.md"
    path.write_text(path.read_text() + RENAMES)
    skill = reparse(demo)
    assert len(skill.renames) == 3
    assert [
        m for m, _ in shape(skill) if "renamed" in m or "became" in m or "removed" in m
    ] == []


def test_a_rename_table_states_its_ranges(demo: Skill) -> None:
    path = demo.root / "references" / "migration.md"
    path.write_text(
        path.read_text()
        + RENAMES.replace("`DS-ERR-09`.", "`DS-ERR-09` and `DS-MIG-01`.")
    )
    (table,) = reparse(demo).rename_tables
    assert table.ranges == (("DS-ERR", 1, 9), ("DS-MIG", 1, 1))
    assert table.unchanged[:2] == ["DS-ERR-01", "DS-ERR-02"]
    assert table.unchanged[-1] == "DS-MIG-01"


def test_an_unlisted_id_no_rule_carries(demo: Skill) -> None:
    path = demo.root / "references" / "migration.md"
    path.write_text(path.read_text() + RENAMES)
    found = [m for m, _ in shape(reparse(demo))]
    assert "DS-ERR-01 has no row" not in " ".join(found)
    assert any(m.startswith("DS-ERR-03 has no row") for m in found)


def test_a_table_that_states_no_ranges(demo: Skill) -> None:
    path = demo.root / "references" / "migration.md"
    path.write_text(path.read_text() + RENAMES.replace(f"{RANGES}\n\n", ""))
    assert any("states no ranges" in m for m, _ in shape(reparse(demo)))


def test_a_row_mapping_an_id_to_itself(demo: Skill) -> None:
    path = demo.root / "references" / "migration.md"
    path.write_text(path.read_text() + RENAMES + "| `DS-ERR-01` | `DS-ERR-01` |\n")
    assert any("becoming itself" in m for m, _ in shape(reparse(demo)))


def test_a_rename_into_a_rule_that_was_deleted(demo: Skill) -> None:
    path = demo.root / "references" / "migration.md"
    path.write_text(
        path.read_text() + RENAMES.replace("`DS-ERR-02` |", "`DS-ERR-05` |")
    )
    skill = reparse(demo)
    assert any("which no rule carries" in m for m, _ in shape(skill))


def test_a_demotion_into_a_row_no_chapter_lists(demo: Skill) -> None:
    path = demo.root / "references" / "migration.md"
    path.write_text(path.read_text() + RENAMES)
    skill = reparse(demo)
    assert any("which no chapter lists" in m for m, _ in shape(skill))


def test_a_removal_without_a_reason(demo: Skill) -> None:
    path = demo.root / "references" / "migration.md"
    text = RENAMES.replace("removed — said nothing the compiler does not", "removed — ")
    path.write_text(path.read_text() + text)
    skill = reparse(demo)
    assert any("gives no reason" in m for m, _ in shape(skill))


def test_rust_rows_against_the_shipped_lint_table() -> None:
    def row(tool: str, lint: str, level: str) -> LintRow:
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
    fine = [
        row("clippy", "unwrap_used", "deny"),
        row("clippy", "cast_lossless", "warn"),
    ]
    fine.append(row("rustc", "unsafe_code", "forbid"))
    assert list(rust_rows(fine, shipped, catalogue)) == []
    wrong = [
        m
        for _, m in rust_rows(
            [row("clippy", "unwrap_used", "warn")], shipped, catalogue
        )
    ]
    assert wrong == ["`unwrap_used` is `warn` in the row and `deny` as shipped"]
    unknown = [
        m
        for _, m in rust_rows(
            [row("clippy", "unwarp_used", "deny")], shipped, catalogue
        )
    ]
    assert unknown == ["`unwarp_used` is not a clippy lint the pinned toolchain knows"]


def test_the_rust_catalogue_reads_the_toolchain() -> None:

    catalogue = rust_catalogue()
    if catalogue is None:
        pytest.skip("clippy-driver or rustdoc is not installed")
    assert catalogue["clippy.unwrap_used"][0] == "allow"
    assert "pedantic" in catalogue["clippy.cast_lossless"][1]
    assert "rust.unsafe_code" in catalogue
    assert "rustdoc.broken_intra_doc_links" in catalogue


def test_a_bold_phrase_inside_a_why_does_not_end_it(demo: Skill) -> None:
    """A Why ends at the next label, not the next line opening `**`."""
    long_why = "**Why:** one.\n**Two** is bold.\nthree.\nfour."
    broken = edit(
        demo, "references/errors.md", "**Why:** one line of reason.", long_why
    )
    assert any("Why runs 4 lines" in m for m in structural_messages(broken))


def test_an_escaped_pipe_stays_inside_its_cell(demo: Skill) -> None:
    rows = """

## Decided by tools

| Tool | Lint | Level | Forbids |
|---|---|---|---|
| clippy | `map_clone` | warn | `.map(\\|x\\| x.clone())` — `.cloned()` |
"""
    path = demo.root / "references" / "errors.md"
    path.write_text(path.read_text() + rows)
    (row,) = reparse(demo).lint_rows
    assert (row.lint, row.forbids) == (
        "map_clone",
        "`.map(|x| x.clone())` — `.cloned()`",
    )
