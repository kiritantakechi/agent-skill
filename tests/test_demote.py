"""`agent-skill demote`, on a throwaway repository."""

from __future__ import annotations

import pytest
from structure_fixture import RULE, Demo, build

from agent_skill import demote, renumber, shared
from agent_skill.checks.anatomy import structural
from agent_skill.checks.skeleton import shape
from agent_skill.model import DASH, Skill

ERRORS = f"""# Errors

## Contents

- **Raising**
  - DS-ERR-01 [M] Name them
  - DS-ERR-02 [M] Wrap them
- **Catching**
  - DS-ERR-03 [M] Catch narrowly

---

## Raising

{RULE.format(id="DS-ERR-01", title="Name them")}
{RULE.format(id="DS-ERR-02", title="Wrap them")}
## Catching

{RULE.format(id="DS-ERR-03", title="Catch narrowly")}"""

MIGRATION = f"""# Migration

## Contents

- **Moving**
  - DS-MIG-01 [M] Use the new name

---

## Moving

{RULE.format(id="DS-MIG-01", title="Use the new name")}"""

#: The current revision's table, part-way through: the old -02 was removed, the old -03
#: is the new -02, and the -03 there is now is a rule the revision added.
TABLE = f"""
## Rule IDs before the Demo 1.2.3 revision

Before the revision the families ran `DS-ERR-01`{DASH}`DS-ERR-03` and `DS-MIG-01`.

| Before | Now |
|---|---|
| `DS-ERR-02` | removed — x |
| `DS-ERR-03` | `DS-ERR-02` |
"""

ROW = ["clippy", "unwrap_used", "deny", "an `unwrap` on a `Result` | `Option`"]


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "skills" / "demo-style"
    (root / "references").mkdir(parents=True)
    (root / "SKILL.md").write_text("---\nname: demo-style\n---\n\n# Demo\n\nDS-ERR-02 wraps.\n")
    (root / "references" / "errors.md").write_text(ERRORS)
    (root / "references" / "migration.md").write_text(MIGRATION)
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    return tmp_path


def run(repo, asked):
    demotion = demote.plan(repo, "demo-style", asked, Demo())
    demote.apply(demotion)
    return demotion


def skill(repo) -> Skill:
    return Skill(repo / "skills/demo-style", Demo())


def text(repo, name: str) -> str:
    return (repo / "skills/demo-style/references" / name).read_text()


def snapshot(root):
    return {p: p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


def test_rows_replace_the_rule_and_start_the_table(repo):
    run(repo, {"DS-ERR-02": {"rows": [ROW]}})
    errors = text(repo, "errors.md")
    assert "DS-ERR-02" not in errors
    assert errors.index("- Decided by tools\n") < errors.index("\n---\n")
    demo = skill(repo)
    (row,) = demo.lint_rows
    assert (row.tool, row.lint, row.level) == ("clippy", "unwrap_used", "deny")
    assert row.forbids == "an `unwrap` on a `Result` | `Option`"
    (table,) = demo.rename_tables
    assert table.ranges == (("DS-ERR", 1, 3), ("DS-MIG", 1, 1))
    assert {r.before: r.now for r in table.rows} == {"DS-ERR-02": "lint `clippy:unwrap_used`"}


def test_a_lint_row_already_listed_and_a_merge(repo):
    run(repo, {"DS-ERR-02": {"rows": [ROW]}, "DS-ERR-03": {"merge": "DS-ERR-01"}})
    run(repo, {"DS-ERR-01": {"lint": ["clippy", "unwrap_used"]}})
    errors = text(repo, "errors.md")
    # Both sections emptied, so both go, with their contents entries.
    assert "## Raising" not in errors and "**Catching**" not in errors
    assert errors.count("| clippy |") == 1
    (table,) = skill(repo).rename_tables
    assert {r.before: r.now for r in table.rows} == {
        "DS-ERR-01": "lint `clippy:unwrap_used`",
        "DS-ERR-02": "lint `clippy:unwrap_used`",
        "DS-ERR-03": "lint `clippy:unwrap_used`",
    }


def test_a_demotion_composes_with_the_table_it_finds(repo):
    migration = repo / "skills/demo-style/references/migration.md"
    migration.write_text(MIGRATION + TABLE)
    run(repo, {"DS-ERR-02": {"remove": "y"}, "DS-ERR-01": {"merge": "DS-ERR-03"}})
    (table,) = skill(repo).rename_tables
    assert {r.before: r.now for r in table.rows} == {
        "DS-ERR-01": "`DS-ERR-03`",
        "DS-ERR-02": "removed — x",
        "DS-ERR-03": "removed — y",
    }


def test_demote_then_renumber_closes_the_gap(repo):
    run(repo, {"DS-ERR-02": {"remove": "said nothing"}})
    renumber.apply(repo, renumber.plan(repo, "demo-style", {}, Demo()))
    demo = skill(repo)
    assert [r.id for r in demo.rules] == ["DS-ERR-01", "DS-ERR-02", "DS-MIG-01"]
    assert demo.by_id["DS-ERR-02"].title == "Catch narrowly"
    (table,) = demo.rename_tables
    assert {r.before: r.now for r in table.rows} == {
        "DS-ERR-02": "removed — said nothing",
        "DS-ERR-03": "`DS-ERR-02`",
    }


def test_a_citation_left_behind_is_reported(repo):
    demotion = run(repo, {"DS-ERR-02": {"remove": "said nothing"}})
    assert demotion.leftovers == [
        "skills/demo-style/SKILL.md:7 cites DS-ERR-02, which is now removed — said nothing"
    ]


@pytest.mark.parametrize(
    ("asked", "message"),
    [
        ({"DS-ERR-09": {"remove": "x"}}, "no chapter rule"),
        ({"DS-ERR-02": {"remove": "x", "merge": "DS-ERR-01"}}, "exactly one"),
        ({"DS-ERR-02": {"retire": "x"}}, "exactly one"),
        ({"DS-ERR-02": {"remove": " "}}, "needs its reason"),
        ({"DS-ERR-02": {"lint": ["clippy", "unwrap_used"]}}, "no chapter lists"),
        ({"DS-ERR-02": {"rows": [["clippy", "unwrap_used"]]}}, "rows are"),
        ({"DS-ERR-02": {"merge": "DS-ERR-02"}}, "keeps"),
        ({"DS-ERR-02": {"merge": "DS-ERR-03"}, "DS-ERR-03": {"remove": "x"}}, "keeps"),
    ],
)
def test_a_plan_that_cannot_be_done_writes_nothing(repo, asked, message):
    before = snapshot(repo)
    with pytest.raises(demote.DemoteError, match=message):
        run(repo, asked)
    assert snapshot(repo) == before


def test_demote_then_renumber_leaves_a_conforming_skill_conforming(tmp_path):
    demo = build(tmp_path / "skills")
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    run(tmp_path, {"DS-ERR-01": {"remove": "said nothing"}})
    renumber.apply(tmp_path, renumber.plan(tmp_path, "demo-style", {}, Demo()))
    after = Skill(demo.root, Demo())
    assert [r.id for r in after.rules] == ["DS-ERR-01", "DS-MIG-01"]
    assert list(shared.compare(after)) == []
    assert [m for m, _ in [*shape(after), *structural(after)]] == []
