"""`agent-skill renumber`, on a throwaway repository."""

from __future__ import annotations

import pytest
from structure_fixture import RULE, Demo

from agent_skill import renumber
from agent_skill.model import Skill


def chapter(title: str, rules: list[tuple[str, str]], extra: str = "") -> str:
    contents = "\n".join(f"- {rid} [M] {t}" for rid, t in rules)
    body = "\n".join(RULE.format(id=rid, title=t) for rid, t in rules)
    return f"# {title}\n\n{contents}\n\n---\n\n{body}{extra}"


@pytest.fixture
def repo(tmp_path):
    """A repository with one standard whose errors chapter has lost its first rule,
    and whose concurrency chapter is still called `free-threading.md`."""
    refs = tmp_path / "skills" / "demo-style" / "references"
    refs.mkdir(parents=True)
    (tmp_path / "skills" / "demo-style" / "SKILL.md").write_text(
        "---\nname: demo-style\n---\n\n# Demo\n\nSee `references/free-threading.md` DS-FT-01, "
        "and DS-ERR-02 then DS-ERR-03, and the `DS-FT` family.\n"
    )
    (refs / "errors.md").write_text(
        chapter("Errors", [("DS-ERR-02", "Name them"), ("DS-ERR-03", "Wrap them")])
    )
    (refs / "free-threading.md").write_text(chapter("Threads", [("DS-FT-01", "Lock it")]))
    (refs / "migration.md").write_text(chapter("Migration", [("DS-MIG-01", "Use the new name")]))
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


def run(repo, **chapters):
    plan = renumber.plan(repo, "demo-style", chapters, Demo())
    renumber.apply(repo, plan)
    return plan


def snapshot(root):
    return {p: p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


THREADS = {"free-threading": "concurrency"}


def test_overlapping_ids_are_rewritten_in_one_pass(repo):
    run(repo, **THREADS)
    skill_md = (repo / "skills/demo-style/SKILL.md").read_text()
    # A chain of replacements would turn both into -01.
    assert "DS-ERR-01 then DS-ERR-02" in skill_md
    skill = Skill(repo / "skills/demo-style", Demo())
    assert {r.id: r.title for r in skill.rules}["DS-ERR-01"] == "Name them"


def test_a_chapter_rename_moves_the_file_the_code_and_every_path(repo):
    run(repo, **THREADS)
    refs = repo / "skills/demo-style/references"
    assert not (refs / "free-threading.md").exists()
    assert "### DS-CONC-01 [M] Lock it" in (refs / "concurrency.md").read_text()
    skill_md = (repo / "skills/demo-style/SKILL.md").read_text()
    assert "`references/concurrency.md` DS-CONC-01" in skill_md
    assert "the `DS-CONC` family" in skill_md
    profile = (repo / "src/agent_skill/profiles/demo_style.py").read_text()
    assert '"DS-ERR-02"' in profile and "references/concurrency.md" in profile
    test = (repo / "tests/test_demo.py").read_text()
    assert "demo-style/references/concurrency.md" in test and "DS-CONC-01" in test


def test_the_rename_table_records_every_old_id(repo):
    run(repo, **THREADS)
    skill = Skill(repo / "skills/demo-style", Demo())
    table = {r.before: r.target for r in skill.renames}
    assert table == {
        "DS-ERR-02": "DS-ERR-01",
        "DS-ERR-03": "DS-ERR-02",
        "DS-FT-01": "DS-CONC-01",
        "DS-MIG-01": "DS-MIG-01",
    }


def test_a_second_run_composes_onto_the_first(repo):
    run(repo, **THREADS)
    errors = repo / "skills/demo-style/references/errors.md"
    # A content edit: the first errors rule goes, and its row records why.
    errors.write_text(chapter("Errors", [("DS-ERR-02", "Wrap them")]))
    migration = repo / "skills/demo-style/references/migration.md"
    row = "| `DS-ERR-02` | `DS-ERR-01` |"
    migration.write_text(migration.read_text().replace(row, "| `DS-ERR-02` | removed — x |"))
    run(repo)
    table = {r.before: r.now for r in Skill(repo / "skills/demo-style", Demo()).renames}
    assert table["DS-ERR-02"] == "removed — x"
    assert table["DS-ERR-03"] == "`DS-ERR-01`"
    assert "### DS-ERR-01 [M] Wrap them" in errors.read_text()


def test_a_deleted_rule_without_a_disposition_stops_the_run(repo):
    run(repo, **THREADS)
    (repo / "skills/demo-style/references/errors.md").write_text(
        chapter("Errors", [("DS-ERR-02", "Wrap them")])
    )
    before = snapshot(repo)
    with pytest.raises(renumber.RenumberError, match="no longer exists"):
        run(repo)
    assert snapshot(repo) == before


def test_a_name_outside_the_vocabulary_stops_the_run(repo):
    before = snapshot(repo)
    with pytest.raises(renumber.RenumberError, match="vocabulary"):
        run(repo, **{"free-threading": "free-threading-2"})
    assert snapshot(repo) == before


def test_an_unknown_id_is_reported_and_left_alone(repo):
    plan = run(repo, **THREADS)
    assert any("DS-ERR-99" in line for line in plan.leftovers)
    assert "DS-ERR-99" in (repo / "tests/test_demo.py").read_text()
