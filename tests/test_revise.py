"""`revise`, which `renumber` and `demote` alias, on throwaway repos."""

import re
lazy from pathlib import Path

import pytest

from agent_skill import revise, shared
from agent_skill.checks.anatomy import structural
from agent_skill.checks.skeleton import skeleton
from agent_skill.doc import WIDTH, Doc, canonical
from agent_skill.doc.chapter import Chapter, Demoted, LintRow, Removed
from agent_skill.fmt import format_skill
from agent_skill.ids import DASH, RuleId
from agent_skill.layout import SKILLS
from agent_skill.model import Skill, Tree
from structure_fixture import DEMO, build
lazy from agent_skill.doc.chapter import Becomes, RenameTable

#: A rule of the repositories built here, which no check reads whole.
RULE = """### {id} [M] {title}

{title}.

**Why:** one line of reason.

**Check:** read it.
"""


def chapter(title: str, rules: list[tuple[str, str]], extra: str = "") -> str:
    contents = "\n".join(f"- {rid} [M] {t}" for rid, t in rules)
    body = "\n".join(RULE.format(id=rid, title=t) for rid, t in rules)
    return (
        f"# {title}\n\n## Contents\n\n{contents}\n\n---\n\n## {title}\n\n{body}{extra}"
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A repository with one standard, part-way through a revision.

    Its errors chapter has lost its first rule, and its concurrency
    chapter is still called `free-threading.md`.
    """
    refs = tmp_path / SKILLS / "demo-style" / "references"
    refs.mkdir(parents=True)
    (tmp_path / SKILLS / "demo-style" / "SKILL.md").write_text(
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


def demo(repo: Path) -> Skill:
    return Skill(repo / SKILLS / "demo-style", DEMO)


def plan(
    repo: Path,
    asked: revise.Plan | None = None,
    chapters: dict[str, str] | None = None,
) -> revise.Revision:
    return revise.revise(Tree.of([demo(repo)]), asked, chapters)


def run(
    repo: Path,
    asked: revise.Plan | None = None,
    chapters: dict[str, str] | None = None,
) -> revise.Revision:
    revision = plan(repo, asked, chapters)
    revision.apply()
    return revision


def tables(repo: Path) -> tuple[RenameTable, ...]:
    """Every rename table, read where it lives."""
    renames = demo(repo).renames_md
    return Chapter.read(Doc.parse(renames.read_text())).renames


def rows(table: RenameTable) -> dict[str, Becomes]:
    return {str(r.before): r.now for r in table.rows}


def titles(skill: Skill) -> dict[str, str]:
    """Each chapter rule's title, by its ID, in order."""
    return {str(r.id): r.title for r in skill.chapter_rules}


def tools(skill: Skill) -> list[LintRow]:
    """Every row of every chapter's `Decided by tools`."""
    return [row for c in skill.chapters for row in c.typed.tools]


def text(repo: Path, name: str) -> str:
    return (repo / SKILLS / "demo-style/references" / name).read_text()


def snapshot(root: Path) -> dict[Path, bytes]:
    return {p: p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


def rid(text: str) -> RuleId:
    return RuleId.parse(text)


THREADS = {"free-threading": "concurrency"}


# ------------------------------------------------------------------
# renumbering and renaming


def test_overlapping_ids_are_rewritten_in_one_pass(repo: Path) -> None:
    run(repo, chapters=THREADS)
    skill_md = (repo / SKILLS / "demo-style/SKILL.md").read_text()
    # A chain of replacements would turn both into -01.
    assert "DS-ERR-01 then DS-ERR-02" in skill_md
    assert titles(demo(repo))["DS-ERR-01"] == "Name them"


def test_a_chapter_rename_moves_the_file_the_code_and_every_path(repo: Path) -> None:
    run(repo, chapters=THREADS)
    refs = repo / SKILLS / "demo-style/references"
    assert not (refs / "free-threading.md").exists()
    assert "### DS-CONC-01 [M] Lock it" in (refs / "concurrency.md").read_text()
    skill_md = (repo / SKILLS / "demo-style/SKILL.md").read_text()
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
    other = repo / SKILLS / "other-style" / "references" / "renames.md"
    other.parent.mkdir(parents=True)
    other.write_text(
        "# Renamed\n\n## Rule IDs before the Other 1.0 revision\n\n"
        "Before the revision the families ran `OS-ERR-01`.\n\n"
        "| Before | Now |\n|---|---|\n"
        "| `OS-ERR-01` | removed — DS-ERR-02 states it |\n"
    )
    run(repo, chapters=THREADS)
    assert "| `OS-ERR-01` | removed — DS-ERR-01 states it |" in other.read_text()


def test_the_rename_table_states_the_ranges_and_lists_what_changed(repo: Path) -> None:
    run(repo, chapters=THREADS)
    (table,) = tables(repo)
    assert table.ranges == (
        (rid("DS-ERR-02"), rid("DS-ERR-03")),
        (rid("DS-FT-01"), rid("DS-FT-01")),
        (rid("DS-MIG-01"), rid("DS-MIG-01")),
    )
    assert rows(table) == {
        "DS-ERR-02": rid("DS-ERR-01"),
        "DS-ERR-03": rid("DS-ERR-02"),
        "DS-FT-01": rid("DS-CONC-01"),
    }
    assert table.unchanged == (rid("DS-MIG-01"),)


def test_the_rename_table_starts_renames_md_and_migration_names_it_once(
    repo: Path,
) -> None:
    run(repo, chapters=THREADS)
    renames = text(repo, "renames.md")
    assert renames.startswith(f"# {revise.TITLE}\n")
    assert "## Rule IDs before" not in text(repo, "migration.md")
    assert text(repo, "migration.md").count("renames.md") == 1
    assert "renames.md" not in (repo / SKILLS / "demo-style/SKILL.md").read_text()
    # A second revision finds the file, and names it no second time.
    run(repo, chapters={"concurrency": "async"})
    assert text(repo, "migration.md").count("renames.md") == 1


def test_the_table_is_named_by_the_target_not_the_patch(repo: Path) -> None:
    """A patch release moves the pin and is not a new revision."""
    assert revise.heading(demo(repo)) == "Rule IDs before the Demo 1.2 revision"


def test_a_run_that_changes_nothing_starts_no_table(repo: Path) -> None:
    run(repo, chapters=THREADS)
    renames = demo(repo).renames_md
    renames.write_text(
        renames.read_text().replace("Demo 1.2 revision", "Demo 1.1 revision")
    )
    before = renames.read_text()
    run(repo)
    assert renames.read_text() == before


def test_a_run_that_changes_nothing_writes_nothing_and_reports_nothing(
    repo: Path,
) -> None:
    run(repo, chapters=THREADS)
    revision = plan(repo)
    assert revision.renamed == {}
    assert revision.empty


def test_an_unlisted_original_gains_a_row_when_it_moves(repo: Path) -> None:
    run(repo, chapters=THREADS)
    migration = repo / SKILLS / "demo-style/references/migration.md"
    # A rule added during the revision, ahead of the original DS-MIG-01
    # under a free ID.
    body = migration.read_text()
    first = RULE.format(id="DS-MIG-02", title="Read the table")
    body = body.replace("- DS-MIG-01", "- DS-MIG-02 [M] Read the table\n- DS-MIG-01", 1)
    migration.write_text(body.replace("### DS-MIG-01", first + "\n### DS-MIG-01", 1))
    run(repo)
    (table,) = tables(repo)
    assert rows(table)["DS-MIG-01"] == rid("DS-MIG-02")
    assert "DS-MIG-02" not in rows(table)
    assert table.ranges[-1] == (rid("DS-MIG-01"), rid("DS-MIG-01"))


def test_an_unlisted_original_that_is_gone_stops_the_run(repo: Path) -> None:
    run(repo, chapters=THREADS)
    migration = repo / SKILLS / "demo-style/references/migration.md"
    body = migration.read_text()
    rule = re.search(r"^### DS-MIG-01 .*", body, re.MULTILINE | re.DOTALL)
    assert rule is not None
    migration.write_text(
        body.replace("- DS-MIG-01 [M] Use the new name\n", "- Gone\n").replace(
            rule[0], ""
        )
    )
    before = snapshot(repo)
    with pytest.raises(revise.ReviseError, match="DS-MIG-01 has no row"):
        run(repo)
    assert snapshot(repo) == before


def test_a_second_run_composes_onto_the_first(repo: Path) -> None:
    run(repo, chapters=THREADS)
    errors = repo / SKILLS / "demo-style/references/errors.md"
    # A content edit: the first errors rule goes, its row records why,
    # and the citation of it goes with it.
    errors.write_text(chapter("Errors", [("DS-ERR-02", "Wrap them")]))
    skill_md = repo / SKILLS / "demo-style/SKILL.md"
    skill_md.write_text(skill_md.read_text().replace("DS-ERR-01 then ", ""))
    renames = demo(repo).renames_md
    renames.write_text(
        renames.read_text().replace(
            "| `DS-ERR-02` | `DS-ERR-01` |", "| `DS-ERR-02` | removed — x |"
        )
    )
    run(repo)
    (table,) = tables(repo)
    assert rows(table)["DS-ERR-02"] == Removed("x")
    assert rows(table)["DS-ERR-03"] == rid("DS-ERR-01")
    assert "### DS-ERR-01 [M] Wrap them" in errors.read_text()


def test_a_deleted_rule_without_a_disposition_stops_the_run(repo: Path) -> None:
    run(repo, chapters=THREADS)
    (repo / SKILLS / "demo-style/references/errors.md").write_text(
        chapter("Errors", [("DS-ERR-02", "Wrap them")])
    )
    skill_md = repo / SKILLS / "demo-style/SKILL.md"
    skill_md.write_text(skill_md.read_text().replace("DS-ERR-01 then ", ""))
    before = snapshot(repo)
    with pytest.raises(revise.ReviseError, match="no longer exists"):
        run(repo)
    assert snapshot(repo) == before


def test_a_name_outside_the_vocabulary_stops_the_run(repo: Path) -> None:
    before = snapshot(repo)
    with pytest.raises(revise.ReviseError, match="vocabulary"):
        run(repo, chapters={"free-threading": "free-threading-2"})
    assert snapshot(repo) == before


def test_a_chapter_no_standard_has_stops_the_run(repo: Path) -> None:
    with pytest.raises(revise.ReviseError, match=r"no-such\.md"):
        plan(repo, chapters=THREADS | {"no-such": "async"})


def test_an_unknown_id_is_reported_and_left_alone(repo: Path) -> None:
    revision = run(repo, chapters=THREADS)
    assert any("DS-ERR-99" in line for line in revision.leftovers)
    assert "DS-ERR-99" in (repo / "tests/test_demo.py").read_text()


def test_a_citation_the_renumbering_would_capture_stops_the_run(
    repo: Path,
) -> None:
    """`DS-CONC-01` names no rule, until the rename gives it one."""
    readme = repo / "README.md"
    readme.write_text("DS-CONC-01 was planned and never written.\n")
    before = snapshot(repo)
    with pytest.raises(
        revise.ReviseError,
        match=r"DS-CONC-01, cited in README\.md, names no rule, and would name "
        r"the rule that is DS-FT-01 now",
    ):
        run(repo, chapters=THREADS)
    assert snapshot(repo) == before


def test_a_paragraph_whose_ids_grew_is_filled_as_fmt_would_fill_it(
    repo: Path,
) -> None:
    """`DS-FT` becomes `DS-CONC`: two columns more at every citation."""
    skill_md = repo / SKILLS / "demo-style/SKILL.md"
    cites = " ".join(["DS-FT-01"] * 10)
    skill_md.write_text(
        "---\nname: demo-style\n---\n\n# Demo\n\n"
        f"See {cites}.\nThen `references/free-threading.md`.\n"
    )
    run(repo, chapters=THREADS)
    written = skill_md.read_text()
    assert written == canonical(written)
    assert all(len(line) <= WIDTH for line in written.split("\n"))
    assert written.count("DS-CONC-01") == 10


def test_every_file_a_revision_writes_in_a_standard_is_canonical(
    repo: Path,
) -> None:
    revision = run(repo, chapters=THREADS)
    standards = repo / SKILLS
    written = [p for p in revision.writes if standards in p.parents]
    assert written
    for path in written:
        assert path.read_text() == canonical(path.read_text()), path.name


def test_text_outside_the_standards_keeps_its_line_breaks(repo: Path) -> None:
    """Nothing holds the README to the canonical form."""
    readme = repo / "README.md"
    readme.write_text("A line  with two spaces,\nbroken early: DS-FT-01.\n")
    run(repo, chapters=THREADS)
    assert readme.read_text() == "A line  with two spaces,\nbroken early: DS-CONC-01.\n"


def test_the_counts_skill_md_states_follow_the_rules(repo: Path) -> None:
    skill_md = repo / SKILLS / "demo-style/SKILL.md"
    skill_md.write_text(
        "---\nname: demo-style\ndescription: >-\n  A 9-rule library.\n---\n\n"
        "| File | Rule IDs | Covers |\n|---|---|---|\n"
        "| `references/errors.md` | `DS-ERR` (7) | x |\n"
        "| `references/free-threading.md` | `DS-FT` (3) | x |\n"
    )
    run(repo, chapters=THREADS)
    written = skill_md.read_text()
    assert "A 4-rule library." in written
    assert "`DS-ERR` (2)" in written
    assert "`DS-CONC` (1)" in written


def test_the_run_that_renames_the_migration_chapter_names_renames_md_there(
    repo: Path,
) -> None:
    refs = repo / SKILLS / "demo-style/references"
    (refs / "migration.md").rename(refs / "migration-and-dead-apis.md")

    run(repo, chapters=THREADS | {"migration-and-dead-apis": "migration"})

    assert not (refs / "migration-and-dead-apis.md").exists()
    assert (refs / "migration.md").read_text().count("renames.md") == 1
    (table,) = tables(repo)
    assert table.ranges[0] == (rid("DS-ERR-02"), rid("DS-ERR-03"))


def test_a_rename_table_anywhere_but_renames_md_stops_the_run(repo: Path) -> None:
    migration = repo / SKILLS / "demo-style/references/migration.md"
    migration.write_text(
        migration.read_text() + "\n## Rule IDs before the Demo 1.1 revision\n\n"
        "Before the revision the families ran `DS-ERR-01`.\n"
    )
    with pytest.raises(revise.ReviseError, match=r"in migration\.md; every one"):
        plan(repo)


# ------------------------------------------------------------------
# a plan


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
TABLE = f"""# Renamed

## Rule IDs before the Demo 1.2 revision

Before the revision the families ran `DS-ERR-01`{DASH}`DS-ERR-03` and `DS-MIG-01`.

| Before | Now |
|---|---|
| `DS-ERR-02` | removed — x |
| `DS-ERR-03` | `DS-ERR-02` |
"""

ROW = LintRow("clippy", "unwrap_used", "deny", "an `unwrap` on a `Result` | `Option`")


@pytest.fixture
def planned(tmp_path: Path) -> Path:
    """A standard whose `SKILL.md` cites its last errors rule."""
    root = tmp_path / SKILLS / "demo-style"
    (root / "references").mkdir(parents=True)
    (root / "SKILL.md").write_text(
        "---\nname: demo-style\n---\n\n# Demo\n\nDS-ERR-03 catches.\n"
    )
    (root / "references" / "errors.md").write_text(ERRORS)
    (root / "references" / "migration.md").write_text(MIGRATION)
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    return tmp_path


def test_a_row_replaces_the_rule_and_the_gap_closes(planned: Path) -> None:
    run(planned, {rid("DS-ERR-02"): ROW})
    errors = text(planned, "errors.md")
    assert "Wrap them" not in errors
    assert errors.index("- Decided by tools\n") < errors.index("\n---\n")
    after = demo(planned)
    assert list(titles(after)) == ["DS-ERR-01", "DS-ERR-02", "DS-MIG-01"]
    (row,) = tools(after)
    assert (row.tool, row.lint, row.level) == ("clippy", "unwrap_used", "deny")
    assert row.forbids == "an `unwrap` on a `Result` | `Option`"
    assert (
        "DS-ERR-02 catches." in (planned / SKILLS / "demo-style/SKILL.md").read_text()
    )
    (table,) = tables(planned)
    assert table.ranges == (
        (rid("DS-ERR-01"), rid("DS-ERR-03")),
        (rid("DS-MIG-01"), rid("DS-MIG-01")),
    )
    assert rows(table) == {
        "DS-ERR-02": Demoted("clippy", "unwrap_used"),
        "DS-ERR-03": rid("DS-ERR-02"),
    }


def test_a_lint_row_already_listed_and_a_merge(planned: Path) -> None:
    run(planned, {rid("DS-ERR-02"): ROW, rid("DS-ERR-01"): rid("DS-ERR-03")})
    skill_md = planned / SKILLS / "demo-style/SKILL.md"
    skill_md.write_text(skill_md.read_text().replace("DS-ERR-01 catches.", "It does."))
    run(planned, {rid("DS-ERR-01"): ROW})
    errors = text(planned, "errors.md")
    # Both sections emptied, so both go, with their contents entries.
    assert "## Raising" not in errors
    assert "**Catching**" not in errors
    assert errors.count("| clippy |") == 1
    assert "DS-ERR" not in errors
    (table,) = tables(planned)
    assert rows(table) == {
        "DS-ERR-01": Demoted("clippy", "unwrap_used"),
        "DS-ERR-02": Demoted("clippy", "unwrap_used"),
        "DS-ERR-03": Demoted("clippy", "unwrap_used"),
    }


def test_a_merge_redirects_every_citation_to_the_rule_it_went_into(
    planned: Path,
) -> None:
    run(planned, {rid("DS-ERR-03"): rid("DS-ERR-01")})
    skill_md = (planned / SKILLS / "demo-style/SKILL.md").read_text()
    assert "DS-ERR-01 catches." in skill_md


def test_a_plan_composes_with_the_table_it_finds(planned: Path) -> None:
    """The old -01 merged into what is now -01, so it has no row."""
    (planned / SKILLS / "demo-style/references/renames.md").write_text(TABLE)
    run(
        planned,
        {rid("DS-ERR-02"): Removed("y"), rid("DS-ERR-01"): rid("DS-ERR-03")},
    )
    (table,) = tables(planned)
    assert rows(table) == {"DS-ERR-02": Removed("x"), "DS-ERR-03": Removed("y")}
    assert list(titles(demo(planned)).values()) == [
        "Catch narrowly",
        "Use the new name",
    ]


def test_a_citation_of_a_rule_the_plan_takes_away_stops_the_run(
    planned: Path,
) -> None:
    """`SKILL.md` cites DS-ERR-03: it would name nothing, or another."""
    before = snapshot(planned)
    with pytest.raises(
        revise.ReviseError,
        match=r"DS-ERR-03, cited in .*SKILL\.md, is removed — said nothing",
    ):
        run(planned, {rid("DS-ERR-03"): Removed("said nothing")})
    assert snapshot(planned) == before


def test_a_gap_left_by_hand_will_not_give_its_citation_to_another_rule(
    planned: Path,
) -> None:
    """DS-ERR-02 went without a plan, and SKILL.md still cites it."""
    errors = planned / SKILLS / "demo-style/references/errors.md"
    rule = RULE.format(id="DS-ERR-02", title="Wrap them")
    errors.write_text(
        errors.read_text()
        .replace(rule, "")
        .replace("  - DS-ERR-02 [M] Wrap them\n", "")
    )
    skill_md = planned / SKILLS / "demo-style/SKILL.md"
    skill_md.write_text(skill_md.read_text() + "\nDS-ERR-02 wraps.\n")
    before = snapshot(planned)
    with pytest.raises(revise.ReviseError, match=r"DS-ERR-02, cited in .*SKILL"):
        run(planned)
    assert snapshot(planned) == before


def test_a_merge_into_an_inserted_rule_follows_it_through_the_renumbering(
    planned: Path,
) -> None:
    """DS-ERR-02a is a rule added mid-revision, between -02 and -03."""
    errors = planned / SKILLS / "demo-style/references/errors.md"
    inserted = RULE.format(id="DS-ERR-02a", title="Chain them")
    errors.write_text(
        errors.read_text()
        .replace("  - DS-ERR-03", "  - DS-ERR-02a [M] Chain them\n  - DS-ERR-03")
        .replace("## Catching\n", f"{inserted}\n## Catching\n")
    )
    run(planned, {rid("DS-ERR-01"): rid("DS-ERR-02a")})
    after = demo(planned)
    assert titles(after)["DS-ERR-02"] == "Chain them"
    # A table started now maps every ID there is, the inserted one too:
    # a reader may hold a citation of it.
    (table,) = tables(planned)
    assert rows(table) == {
        "DS-ERR-01": rid("DS-ERR-02"),
        "DS-ERR-02": rid("DS-ERR-01"),
        "DS-ERR-02a": rid("DS-ERR-02"),
    }


#: A section 4 stating two core rules of its own.
CORE = """## 4. Core rules

- **DS-CORE-01 `[M]`** Catch narrowly, always (DS-ERR-03).
- **DS-CORE-02 `[M]`** Say it twice.
"""


@pytest.fixture
def cored(planned: Path) -> Path:
    """`planned`, its `SKILL.md` stating two core rules, one cited."""
    skill_md = planned / SKILLS / "demo-style/SKILL.md"
    skill_md.write_text(f"{skill_md.read_text()}\n{CORE}\nAs DS-CORE-01 says.\n")
    return planned


def test_a_core_rule_merges_into_the_chapter_rule_it_abbreviated(
    cored: Path,
) -> None:
    """Its item becomes that rule's line; its citations follow."""
    run(
        cored,
        {
            rid("DS-ERR-01"): Removed("x"),
            rid("DS-CORE-01"): rid("DS-ERR-03"),
            rid("DS-CORE-02"): Removed("said what DS-ERR-03 says"),
        },
    )
    after = demo(cored)
    assert after.core == ()
    skill_md = after.skill_md.read_text()
    assert "- DS-ERR-02 [M] Catch narrowly\n" in skill_md
    assert "As DS-ERR-02 says." in skill_md
    assert "DS-CORE" not in skill_md
    (table,) = tables(cored)
    assert rows(table) == {
        "DS-ERR-01": Removed("x"),
        "DS-ERR-02": rid("DS-ERR-01"),
        "DS-ERR-03": rid("DS-ERR-02"),
        "DS-CORE-01": rid("DS-ERR-02"),
        "DS-CORE-02": Removed("said what DS-ERR-03 says"),
    }
    assert table.ranges[-1] == (rid("DS-CORE-01"), rid("DS-CORE-02"))


def test_a_core_merge_joins_the_table_the_revision_started(cored: Path) -> None:
    """The core family's range joins the ranges the table states."""
    (cored / SKILLS / "demo-style/references/renames.md").write_text(TABLE)
    run(cored, {rid("DS-CORE-01"): rid("DS-ERR-03")})
    (table,) = tables(cored)
    assert table.originals == (
        *(rid(f"DS-ERR-0{n}") for n in (1, 2, 3)),
        rid("DS-MIG-01"),
        rid("DS-CORE-01"),
        rid("DS-CORE-02"),
    )
    assert rows(table) == {
        "DS-ERR-02": Removed("x"),
        "DS-ERR-03": rid("DS-ERR-02"),
        "DS-CORE-01": rid("DS-ERR-03"),
    }
    assert [r.id for r in demo(cored).core] == [rid("DS-CORE-02")]


@pytest.mark.parametrize(
    ("asked", "message"),
    [
        ({"DS-CORE-01": {"lint": ["clippy", "unwrap_used"]}}, "a lint row"),
        ({"DS-CORE-01": {"merge": "DS-CORE-02"}}, "chapter rule this standard keeps"),
    ],
)
def test_a_core_rule_only_merges_into_a_chapter_rule_or_goes(
    cored: Path, asked: object, message: str
) -> None:
    run(cored, {rid("DS-ERR-02"): ROW})
    before = snapshot(cored)
    with pytest.raises(revise.ReviseError, match=message):
        run(cored, revise.read_plan(asked, demo(cored)))
    assert snapshot(cored) == before


@pytest.mark.parametrize(
    ("asked", "message"),
    [
        ({"DS-ERR-09": {"remove": "x"}}, "no chapter rule"),
        ({"DS-ERR-02": {"remove": "x", "merge": "DS-ERR-01"}}, "exactly one"),
        # `retire` is not a kind a plan has: malformed on purpose.
        ({"DS-ERR-02": {"retire": "x"}}, "exactly one"),
        ({"DS-ERR-02": {"remove": " "}}, "needs its reason"),
        ({"DS-ERR-02": {"lint": ["clippy", "unwrap_used"]}}, "no chapter lists"),
        ({"DS-ERR-02": {"rows": [["clippy", "unwrap_used"]]}}, "rows are"),
        # A rule becomes one row; a second lint is a row added by hand.
        ({"DS-ERR-02": {"rows": [list("abcd"), list("efgh")]}}, "rows are"),
        ({"DS-ERR-02": {"merge": "DS-ERR-02"}}, "keeps"),
        ({"DS-ERR-02": {"merge": "DS-ERR-03"}, "DS-ERR-03": {"remove": "x"}}, "keeps"),
        ({"no-rule": {"remove": "x"}}, "not a rule ID"),
        ({"DS-ERR-02": {"move": "migration"}}, "a move names"),
        ({"DS-ERR-02": {"move": "migration", "after": "first"}}, "a move names"),
        ({"DS-ERR-02": {"move": "errors", "after": "DS-ERR-01"}}, "already"),
        ({"DS-ERR-02": {"move": "nowhere", "after": "## X"}}, "no chapter the voc"),
        ({"DS-ERR-02": {"move": "migration", "after": "DS-ERR-01"}}, "no other rule"),
        ({"DS-ERR-09": {"move": "migration", "after": "## X"}}, "no chapter rule"),
    ],
)
def test_a_plan_that_cannot_be_done_writes_nothing(
    planned: Path, asked: object, message: str
) -> None:
    before = snapshot(planned)
    with pytest.raises(revise.ReviseError, match=message):
        run(planned, revise.read_plan(asked, demo(planned)))
    assert snapshot(planned) == before


def test_a_plan_file_says_each_kind_as_the_plan_types_it(planned: Path) -> None:
    run(planned, {rid("DS-ERR-02"): ROW})
    read = revise.read_plan(
        {
            "DS-ERR-01": {"lint": ["clippy", "unwrap_used"]},
            "DS-ERR-02": {"merge": "DS-ERR-01"},
            "DS-MIG-01": {"remove": " gone "},
        },
        demo(planned),
    )
    assert read == {
        rid("DS-ERR-01"): ROW,
        rid("DS-ERR-02"): rid("DS-ERR-01"),
        rid("DS-MIG-01"): Removed("gone"),
    }


def test_a_move_names_the_rule_it_follows_or_the_section_it_opens(
    planned: Path,
) -> None:
    read = revise.read_plan(
        {
            "DS-ERR-02": {"move": "migration", "after": "DS-MIG-01"},
            "DS-ERR-03": {"move": "migration", "after": "## Moving"},
        },
        demo(planned),
    )
    assert read == {
        rid("DS-ERR-02"): revise.Moved("migration", rid("DS-MIG-01")),
        rid("DS-ERR-03"): revise.Moved("migration", "Moving"),
    }


def test_a_moved_rule_takes_its_new_family_and_its_citations_follow(
    planned: Path,
) -> None:
    """DS-ERR-03 opens the migration section; both families close up."""
    revision = run(planned, {rid("DS-ERR-03"): revise.Moved("migration", "Moving")})
    assert revision.renamed == {
        rid("DS-ERR-03"): rid("DS-MIG-01"),
        rid("DS-MIG-01"): rid("DS-MIG-02"),
    }
    root = planned / SKILLS / "demo-style"
    migration = Chapter.read(Doc.parse((root / "references/migration.md").read_text()))
    assert [(r.id, r.title) for r in migration.rules] == [
        (rid("DS-MIG-01"), "Catch narrowly"),
        (rid("DS-MIG-02"), "Use the new name"),
    ]
    assert migration.contents is not None
    assert [e.id for e in migration.contents.entries] == [r.id for r in migration.rules]
    errors = Chapter.read(Doc.parse((root / "references/errors.md").read_text()))
    assert [s.title for s in errors.sections] == ["Raising"]
    assert "DS-MIG-01 catches." in (root / "SKILL.md").read_text()


def test_a_revision_leaves_a_conforming_skill_conforming(tmp_path: Path) -> None:
    """Once `fmt` has rendered section 4 from the rules it lists.

    A merge respells section 4's line for the rule it removes, and the
    title and tier on it are the removed rule's until `fmt` renders it.
    """
    built = build(tmp_path / SKILLS)
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    run(tmp_path, {rid("DS-ERR-01"): rid("DS-ERR-02")})
    format_skill(Skill(built.root, DEMO))
    after = Skill(built.root, DEMO)
    assert list(titles(after)) == ["DS-ERR-01", "DS-MIG-01"]
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


def test_removing_a_rule_takes_its_whole_example_with_it(planned: Path) -> None:
    errors = planned / SKILLS / "demo-style/references/errors.md"
    errors.write_text(
        ERRORS.replace(RULE.format(id="DS-ERR-02", title="Wrap them"), FENCED)
    )
    run(planned, {rid("DS-ERR-02"): Removed("said nothing")})
    written = errors.read_text()
    assert "Not a section" not in written
    assert "```" not in written
    assert written.count("**Why:**") == 2


@pytest.mark.parametrize("lead", ["", f"\n{revise.LEAD}\n"])
def test_rows_go_under_a_decided_by_tools_heading_with_no_table(
    planned: Path, lead: str
) -> None:
    errors = planned / SKILLS / "demo-style/references/errors.md"
    errors.write_text(
        ERRORS.replace("## Catching", f"## Decided by tools\n{lead}\n## Catching")
    )
    run(planned, {rid("DS-ERR-02"): ROW})
    (row,) = tools(demo(planned))
    assert (row.tool, row.lint) == ("clippy", "unwrap_used")
    written = errors.read_text()
    assert written.count(revise.LEAD) == 1
    assert "\n\n\n" not in written


def test_a_compiler_row_opens_its_table_with_the_compiler_lead(planned: Path) -> None:
    row = LintRow("zig", "unused local constant", "error", "a constant nothing reads")

    run(planned, {rid("DS-ERR-02"): row})

    errors = text(planned, "errors.md")
    assert revise.COMPILER_LEAD in errors
    assert revise.LEAD not in errors


def test_a_row_listed_already_with_other_words_stops_the_run(planned: Path) -> None:
    run(planned, {rid("DS-ERR-02"): ROW})
    other = LintRow(ROW.tool, ROW.lint, "warn", ROW.forbids)
    with pytest.raises(revise.ReviseError, match="listed already, at deny"):
        plan(planned, {rid("DS-ERR-01"): other})
