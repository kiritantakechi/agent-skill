"""`agent-skill renumber`, on a throwaway repository."""

import re
lazy from pathlib import Path

import pytest

from agent_skill import renumber
from agent_skill.model import Skill
from agent_skill.text import reflow
from structure_fixture import RULE, Demo


def chapter(title: str, rules: list[tuple[str, str]], extra: str = "") -> str:
    contents = "\n".join(f"- {rid} [M] {t}" for rid, t in rules)
    body = "\n".join(RULE.format(id=rid, title=t) for rid, t in rules)
    return f"# {title}\n\n{contents}\n\n---\n\n{body}{extra}"


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A repository with one standard, part-way through a revision.

    Its errors chapter has lost its first rule, and its concurrency
    chapter is still called `free-threading.md`.
    """
    refs = tmp_path / "skills" / "demo-style" / "references"
    refs.mkdir(parents=True)
    (tmp_path / "skills" / "demo-style" / "SKILL.md").write_text(
        "---\nname: demo-style\n---\n\n# Demo\n\n"
        "See `references/free-threading.md` DS-FT-01, "
        "and DS-ERR-02 then DS-ERR-03, and the `DS-FT` family.\n"
    )
    (refs / "errors.md").write_text(
        chapter("Errors", [("DS-ERR-02", "Name them"), ("DS-ERR-03", "Wrap them")])
    )
    (refs / "free-threading.md").write_text(
        chapter("Threads", [("DS-FT-01", "Lock it")])
    )
    (refs / "migration.md").write_text(
        chapter("Migration", [("DS-MIG-01", "Use the new name")])
    )
    profiles = tmp_path / "src" / "agent_skill" / "profiles"
    profiles.mkdir(parents=True)
    (profiles / "demo_style.py").write_text(
        'FIRES = {"DS-ERR-03": "x"}  # references/free-threading.md\n'
    )
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_demo.py").write_text(
        'PATH = "demo-style/references/free-threading.md"  # DS-FT-01, DS-ERR-99\n'
    )
    (tmp_path / "README.md").write_text("Nothing about DS rules.\n")
    return tmp_path


def run(repo: Path, **chapters: str) -> renumber.Plan:
    plan = renumber.plan(repo, "demo-style", chapters, Demo())
    renumber.apply(repo, plan)
    return plan


def snapshot(root: Path) -> dict[Path, bytes]:
    return {p: p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


THREADS = {"free-threading": "concurrency"}


def test_overlapping_ids_are_rewritten_in_one_pass(repo: Path) -> None:
    run(repo, **THREADS)
    skill_md = (repo / "skills/demo-style/SKILL.md").read_text()
    # A chain of replacements would turn both into -01.
    assert "DS-ERR-01 then DS-ERR-02" in skill_md
    skill = Skill(repo / "skills/demo-style", Demo())
    assert {r.id: r.title for r in skill.rules}["DS-ERR-01"] == "Name them"


def test_a_chapter_rename_moves_the_file_the_code_and_every_path(repo: Path) -> None:
    run(repo, **THREADS)
    refs = repo / "skills/demo-style/references"
    assert not (refs / "free-threading.md").exists()
    assert "### DS-CONC-01 [M] Lock it" in (refs / "concurrency.md").read_text()
    skill_md = (repo / "skills/demo-style/SKILL.md").read_text()
    assert "`references/concurrency.md` DS-CONC-01" in skill_md
    assert "the `DS-CONC` family" in skill_md
    profile = (repo / "src/agent_skill/profiles/demo_style.py").read_text()
    assert '"DS-ERR-02"' in profile
    assert "references/concurrency.md" in profile
    test = (repo / "tests/test_demo.py").read_text()
    assert "demo-style/references/concurrency.md" in test
    assert "DS-CONC-01" in test


def test_another_skills_rename_table_follows_the_renumbering(repo: Path) -> None:
    """It cites this skill only to say what replaced its own rule."""
    other = repo / "skills" / "other-style" / "references" / "migration.md"
    other.parent.mkdir(parents=True)
    other.write_text(
        "# Migration\n\n## Rule IDs before the Other 1.0 revision\n\n"
        "Before the revision the families ran `OS-ERR-01`.\n\n"
        "| Before | Now |\n|---|---|\n"
        "| `OS-ERR-01` | removed — DS-ERR-02 states it |\n"
    )
    run(repo, **THREADS)
    assert "| `OS-ERR-01` | removed — DS-ERR-01 states it |" in other.read_text()


def test_the_rename_table_states_the_ranges_and_lists_what_changed(repo: Path) -> None:
    run(repo, **THREADS)
    (table,) = Skill(repo / "skills/demo-style", Demo()).rename_tables
    assert table.ranges == (("DS-ERR", 2, 3), ("DS-FT", 1, 1), ("DS-MIG", 1, 1))
    assert {r.before: r.target for r in table.rows} == {
        "DS-ERR-02": "DS-ERR-01",
        "DS-ERR-03": "DS-ERR-02",
        "DS-FT-01": "DS-CONC-01",
    }
    assert table.unchanged == ["DS-MIG-01"]


def test_the_table_is_named_by_the_target_not_the_patch(repo: Path) -> None:
    """A patch release moves the pin and is not a new revision."""
    skill = Skill(repo / "skills/demo-style", Demo())
    assert renumber.heading(skill) == "## Rule IDs before the Demo 1.2 revision"


def test_a_run_that_changes_nothing_starts_no_table(repo: Path) -> None:
    run(repo, **THREADS)
    migration = repo / "skills/demo-style/references/migration.md"
    migration.write_text(
        migration.read_text().replace("Demo 1.2 revision", "Demo 1.1 revision")
    )
    before = migration.read_text()
    run(repo)
    assert migration.read_text() == before


def test_an_unlisted_original_gains_a_row_when_it_moves(repo: Path) -> None:
    run(repo, **THREADS)
    migration = repo / "skills/demo-style/references/migration.md"
    # A rule added during the revision, ahead of the original DS-MIG-01
    # under a free ID.
    text = migration.read_text()
    first = RULE.format(id="DS-MIG-02", title="Read the table")
    text = text.replace("- DS-MIG-01", "- DS-MIG-02 [M] Read the table\n- DS-MIG-01", 1)
    migration.write_text(text.replace("### DS-MIG-01", first + "### DS-MIG-01", 1))
    run(repo)
    (table,) = Skill(repo / "skills/demo-style", Demo()).rename_tables
    rows = {r.before: r.now for r in table.rows}
    assert rows["DS-MIG-01"] == "`DS-MIG-02`"
    assert "DS-MIG-02" not in rows
    assert table.ranges[-1] == ("DS-MIG", 1, 1)


def test_an_unlisted_original_that_is_gone_stops_the_run(repo: Path) -> None:
    run(repo, **THREADS)
    migration = repo / "skills/demo-style/references/migration.md"
    text = migration.read_text()
    rule = re.search(r"^### DS-MIG-01 .*?(?=^## )", text, re.MULTILINE | re.DOTALL)
    assert rule is not None
    migration.write_text(
        text.replace("- DS-MIG-01 [M] Use the new name\n", "").replace(rule[0], "")
    )
    before = snapshot(repo)
    with pytest.raises(renumber.RenumberError, match="DS-MIG-01 has no row"):
        run(repo)
    assert snapshot(repo) == before


def test_a_second_run_composes_onto_the_first(repo: Path) -> None:
    run(repo, **THREADS)
    errors = repo / "skills/demo-style/references/errors.md"
    # A content edit: the first errors rule goes, and its row records
    # why.
    errors.write_text(chapter("Errors", [("DS-ERR-02", "Wrap them")]))
    migration = repo / "skills/demo-style/references/migration.md"
    row = "| `DS-ERR-02` | `DS-ERR-01` |"
    migration.write_text(
        migration.read_text().replace(row, "| `DS-ERR-02` | removed — x |")
    )
    run(repo)
    table = {r.before: r.now for r in Skill(repo / "skills/demo-style", Demo()).renames}
    assert table["DS-ERR-02"] == "removed — x"
    assert table["DS-ERR-03"] == "`DS-ERR-01`"
    assert "### DS-ERR-01 [M] Wrap them" in errors.read_text()


def test_a_deleted_rule_without_a_disposition_stops_the_run(repo: Path) -> None:
    run(repo, **THREADS)
    (repo / "skills/demo-style/references/errors.md").write_text(
        chapter("Errors", [("DS-ERR-02", "Wrap them")])
    )
    before = snapshot(repo)
    with pytest.raises(renumber.RenumberError, match="no longer exists"):
        run(repo)
    assert snapshot(repo) == before


def test_a_name_outside_the_vocabulary_stops_the_run(repo: Path) -> None:
    before = snapshot(repo)
    with pytest.raises(renumber.RenumberError, match="vocabulary"):
        run(repo, **{"free-threading": "free-threading-2"})
    assert snapshot(repo) == before


def test_an_unknown_id_is_reported_and_left_alone(repo: Path) -> None:
    plan = run(repo, **THREADS)
    assert any("DS-ERR-99" in line for line in plan.leftovers)
    assert "DS-ERR-99" in (repo / "tests/test_demo.py").read_text()


def test_reflow_pushes_overflow_into_the_next_line() -> None:
    text = (
        "word " * 19 + "end-of-the-line-word"
    ).rstrip() + "\nnext line of the same paragraph.\n"
    out = reflow(text, width=100)
    lines = out.split("\n")
    assert all(len(ln) <= 100 for ln in lines)
    assert lines[1].startswith("end-of-the-line-word next line")
    assert " ".join(out.split()) == " ".join(text.split())


def test_reflow_keeps_a_list_items_hanging_indent_and_leaves_code_alone() -> None:
    item = "1. **Read.** " + "word " * 19 + "tail"
    code = "```\n" + "x" * 120 + "\n```"
    out = reflow(f"{item}\n\n{code}\n", width=100)
    assert "\n   word word tail" in out
    assert "x" * 120 in out


def test_reflow_does_not_join_a_new_list_item_or_a_why() -> None:
    para = "word " * 20 + "tail"
    for nxt in ("- a list item", "2. next", "**Why:** because"):
        out = reflow(f"{para}\n{nxt}\n", width=100)
        assert f"\ntail\n{nxt}" in out


def test_the_counts_skill_md_states_follow_the_rules(repo: Path) -> None:
    skill_md = repo / "skills/demo-style/SKILL.md"
    skill_md.write_text(
        "---\nname: demo-style\ndescription: >-\n  A 9-rule library.\n---\n\n"
        "| `references/errors.md` | `DS-ERR` (7) | x |\n"
        "| `references/free-threading.md` | `DS-FT` (3) | x |\n"
    )
    run(repo, **THREADS)
    text = skill_md.read_text()
    assert "A 4-rule library." in text
    assert "`DS-ERR` (2)" in text
    assert "`DS-CONC` (1)" in text


def test_reflow_leaves_a_contents_line_whole() -> None:
    line = "  - RS-TRAIT-14 [S] " + "word " * 18 + "type"
    assert reflow(line + "\n", width=100) == line + "\n"


def test_reflow_never_breaks_inside_a_code_span() -> None:
    line = (
        "**Check:** "
        + "word " * 10
        + "`rg -n '^(alpha|beta|gamma|delta) *=' Cargo.toml` tail"
    )
    out = reflow(line + "\n", width=100)
    assert "`rg -n '^(alpha|beta|gamma|delta) *=' Cargo.toml`" in out


def test_the_run_that_renames_the_migration_chapter_writes_its_table(
    repo: Path,
) -> None:
    refs = repo / "skills/demo-style/references"
    (refs / "migration.md").rename(refs / "migration-and-dead-apis.md")

    run(repo, **THREADS, **{"migration-and-dead-apis": "migration"})

    assert not (refs / "migration-and-dead-apis.md").exists()
    (table,) = Skill(repo / "skills/demo-style", Demo()).rename_tables
    assert table.ranges[0] == ("DS-ERR", 2, 3)
