"""`agent-skill demote`, on a throwaway repository."""

lazy from pathlib import Path

import pytest

from agent_skill import demote, renumber, shared
from agent_skill.checks.anatomy import structural
from agent_skill.checks.skeleton import skeleton
from agent_skill.doc import canonical
from agent_skill.layout import SKILLS
from agent_skill.model import DASH, Skill
from structure_fixture import RULE, Demo, build
lazy from agent_skill.demote import Entry

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

#: The current revision's table, part-way through: the old -02 was
#: removed, the old -03 is the new -02, and the -03 there is now is a
#: rule the revision added.
TABLE = f"""
## Rule IDs before the Demo 1.2 revision

Before the revision the families ran `DS-ERR-01`{DASH}`DS-ERR-03` and `DS-MIG-01`.

| Before | Now |
|---|---|
| `DS-ERR-02` | removed — x |
| `DS-ERR-03` | `DS-ERR-02` |
"""

ROW = ["clippy", "unwrap_used", "deny", "an `unwrap` on a `Result` | `Option`"]


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / SKILLS / "demo-style"
    (root / "references").mkdir(parents=True)
    (root / "SKILL.md").write_text(
        "---\nname: demo-style\n---\n\n# Demo\n\nDS-ERR-02 wraps.\n"
    )
    (root / "references" / "errors.md").write_text(ERRORS)
    (root / "references" / "migration.md").write_text(MIGRATION)
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    return tmp_path


def run(repo: Path, asked: dict[str, Entry]) -> demote.Demotion:
    demotion = demote.plan(repo, "demo-style", asked, Demo())
    demote.apply(demotion)
    return demotion


def skill(repo: Path) -> Skill:
    return Skill(repo / SKILLS / "demo-style", Demo())


def text(repo: Path, name: str) -> str:
    return (repo / SKILLS / "demo-style/references" / name).read_text()


def snapshot(root: Path) -> dict[Path, bytes]:
    return {p: p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


def test_rows_replace_the_rule_and_start_the_table(repo: Path) -> None:
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
    assert {r.before: r.now for r in table.rows} == {
        "DS-ERR-02": "lint `clippy:unwrap_used`"
    }


def test_a_lint_row_already_listed_and_a_merge(repo: Path) -> None:
    run(repo, {"DS-ERR-02": {"rows": [ROW]}, "DS-ERR-03": {"merge": "DS-ERR-01"}})
    run(repo, {"DS-ERR-01": {"lint": ["clippy", "unwrap_used"]}})
    errors = text(repo, "errors.md")
    # Both sections emptied, so both go, with their contents entries.
    assert "## Raising" not in errors
    assert "**Catching**" not in errors
    assert errors.count("| clippy |") == 1
    (table,) = skill(repo).rename_tables
    assert {r.before: r.now for r in table.rows} == {
        "DS-ERR-01": "lint `clippy:unwrap_used`",
        "DS-ERR-02": "lint `clippy:unwrap_used`",
        "DS-ERR-03": "lint `clippy:unwrap_used`",
    }


def test_a_demotion_composes_with_the_table_it_finds(repo: Path) -> None:
    migration = repo / SKILLS / "demo-style/references/migration.md"
    migration.write_text(MIGRATION + TABLE)
    run(repo, {"DS-ERR-02": {"remove": "y"}, "DS-ERR-01": {"merge": "DS-ERR-03"}})
    (table,) = skill(repo).rename_tables
    assert {r.before: r.now for r in table.rows} == {
        "DS-ERR-01": "`DS-ERR-03`",
        "DS-ERR-02": "removed — x",
        "DS-ERR-03": "removed — y",
    }


def resolve(repo: Path, rid: str) -> None:
    """Do what a person does with a citation a demotion left behind."""
    skill_md = repo / SKILLS / "demo-style/SKILL.md"
    skill_md.write_text(skill_md.read_text().replace(f"{rid} wraps.", "It wraps."))


def test_demote_then_renumber_closes_the_gap(repo: Path) -> None:
    run(repo, {"DS-ERR-02": {"remove": "said nothing"}})
    resolve(repo, "DS-ERR-02")
    renumber.apply(repo, renumber.plan(repo, "demo-style", {}, Demo()))
    demo = skill(repo)
    assert [r.id for r in demo.rules] == ["DS-ERR-01", "DS-ERR-02", "DS-MIG-01"]
    assert demo.by_id["DS-ERR-02"].title == "Catch narrowly"
    (table,) = demo.rename_tables
    assert {r.before: r.now for r in table.rows} == {
        "DS-ERR-02": "removed — said nothing",
        "DS-ERR-03": "`DS-ERR-02`",
    }


def test_renumber_will_not_give_a_citation_left_behind_to_another_rule(
    repo: Path,
) -> None:
    """SKILL.md still cites DS-ERR-02, which DS-ERR-03 would become."""
    run(repo, {"DS-ERR-02": {"remove": "said nothing"}})
    before = snapshot(repo)
    with pytest.raises(renumber.RenumberError, match=r"DS-ERR-02, cited in .*SKILL"):
        renumber.apply(repo, renumber.plan(repo, "demo-style", {}, Demo()))
    assert snapshot(repo) == before


def test_a_merge_into_an_inserted_rule_follows_it_through_the_renumbering(
    repo: Path,
) -> None:
    """DS-ERR-02a is a rule added mid-revision, between -02 and -03."""
    errors = repo / SKILLS / "demo-style/references/errors.md"
    inserted = RULE.format(id="DS-ERR-02a", title="Chain them")
    errors.write_text(
        errors.read_text()
        .replace("  - DS-ERR-03", "  - DS-ERR-02a [M] Chain them\n  - DS-ERR-03")
        .replace("## Catching\n", f"{inserted}\n## Catching\n")
    )
    run(repo, {"DS-ERR-01": {"merge": "DS-ERR-02a"}})
    renumber.apply(repo, renumber.plan(repo, "demo-style", {}, Demo()))
    demo = skill(repo)
    assert demo.by_id["DS-ERR-02"].title == "Chain them"
    (table,) = demo.rename_tables
    assert {r.before: r.now for r in table.rows} == {
        "DS-ERR-01": "`DS-ERR-02`",
        "DS-ERR-02": "`DS-ERR-01`",
    }


def test_a_citation_left_behind_is_reported(repo: Path) -> None:
    demotion = run(repo, {"DS-ERR-02": {"remove": "said nothing"}})
    assert demotion.leftovers == [
        (
            f"{SKILLS}/demo-style/SKILL.md:7 cites DS-ERR-02, "
            "which is now removed — said nothing"
        )
    ]


@pytest.mark.parametrize(
    ("asked", "message"),
    [
        ({"DS-ERR-09": {"remove": "x"}}, "no chapter rule"),
        ({"DS-ERR-02": {"remove": "x", "merge": "DS-ERR-01"}}, "exactly one"),
        # `retire` is not a key an `Entry` has: malformed on purpose.
        ({"DS-ERR-02": {"retire": "x"}}, "exactly one"),
        ({"DS-ERR-02": {"remove": " "}}, "needs its reason"),
        ({"DS-ERR-02": {"lint": ["clippy", "unwrap_used"]}}, "no chapter lists"),
        ({"DS-ERR-02": {"rows": [["clippy", "unwrap_used"]]}}, "rows are"),
        ({"DS-ERR-02": {"merge": "DS-ERR-02"}}, "keeps"),
        ({"DS-ERR-02": {"merge": "DS-ERR-03"}, "DS-ERR-03": {"remove": "x"}}, "keeps"),
    ],
)
def test_a_plan_that_cannot_be_done_writes_nothing(
    repo: Path, asked: dict[str, Entry], message: str
) -> None:
    before = snapshot(repo)
    with pytest.raises(demote.DemoteError, match=message):
        run(repo, asked)
    assert snapshot(repo) == before


def test_demote_then_renumber_leaves_a_conforming_skill_conforming(
    tmp_path: Path,
) -> None:
    demo = build(tmp_path / SKILLS)
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    run(tmp_path, {"DS-ERR-01": {"remove": "said nothing"}})
    renumber.apply(tmp_path, renumber.plan(tmp_path, "demo-style", {}, Demo()))
    after = Skill(demo.root, Demo())
    assert [r.id for r in after.rules] == ["DS-ERR-01", "DS-MIG-01"]
    assert list(shared.compare(after)) == []
    assert [f.message for f in [*skeleton.each(after), *structural(after)]] == []


#: DS-ERR-02, with an example holding a line that reads like a section.
FENCED = """### DS-ERR-02 [M] Wrap them

Wrap them.

```markdown
## Not a section
```

**Why:** one line of reason.

**Check:** read it.
"""


@pytest.fixture
def fenced(repo: Path) -> Path:
    errors = repo / SKILLS / "demo-style/references/errors.md"
    errors.write_text(
        ERRORS.replace(RULE.format(id="DS-ERR-02", title="Wrap them"), FENCED)
    )
    return errors


def test_a_heading_inside_an_example_does_not_end_the_rule(fenced: Path) -> None:
    rule = Skill(fenced.parents[1], Demo()).by_id["DS-ERR-02"]
    assert rule.body.rstrip("\n").endswith("**Check:** read it.")


def test_demoting_a_rule_takes_its_whole_example_with_it(
    repo: Path, fenced: Path
) -> None:
    before = skill(repo).by_id["DS-ERR-01"].body
    run(repo, {"DS-ERR-02": {"remove": "said nothing"}})
    errors = fenced.read_text()
    assert "Not a section" not in errors
    assert "```" not in errors
    assert errors.count("**Why:**") == 2
    assert skill(repo).by_id["DS-ERR-01"].body == before


@pytest.mark.parametrize("lead", ["", f"\n{demote.LEAD}\n"])
def test_rows_go_under_a_decided_by_tools_heading_with_no_table(
    repo: Path, lead: str
) -> None:
    errors = repo / SKILLS / "demo-style/references/errors.md"
    errors.write_text(
        ERRORS.replace("## Catching", f"## Decided by tools\n{lead}\n## Catching")
    )
    run(repo, {"DS-ERR-02": {"rows": [ROW]}})
    (row,) = skill(repo).lint_rows
    assert (row.tool, row.lint) == ("clippy", "unwrap_used")
    text = errors.read_text()
    assert text.count(demote.LEAD) == 1
    assert "\n\n\n" not in text


def test_a_compiler_row_opens_its_table_with_the_compiler_lead(repo: Path) -> None:
    row = ["zig", "unused local constant", "error", "a constant nothing reads"]

    run(repo, {"DS-ERR-02": {"rows": [row]}})

    errors = text(repo, "errors.md")
    assert demote.COMPILER_LEAD in errors
    assert demote.LEAD not in errors


def test_every_file_a_demotion_writes_is_in_its_canonical_form(repo: Path) -> None:
    """What `demote` writes, `fmt` would leave as it is."""
    demotion = run(repo, {"DS-ERR-02": {"rows": [ROW]}, "DS-ERR-03": {"remove": "y"}})
    assert demotion.writes
    for path, written in demotion.writes.items():
        assert written == canonical(written), path.name
