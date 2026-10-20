"""The skeleton check, on a conforming standard.

The standard is built to conform and then broken one way at a time.
"""

import dataclasses
lazy from pathlib import Path

import pytest

from agent_skill.checks.anatomy import structural
from agent_skill.checks.skeleton import shape, skeleton
from structure_fixture import Demo, build, edit, reparse
lazy from agent_skill.model import Skill


@pytest.fixture
def demo(tmp_path: Path) -> Skill:
    return build(tmp_path)


def messages(skill: Skill) -> list[str]:
    return [message for message, _ in shape(skill)]


def test_the_demo_conforms(demo: Skill) -> None:
    assert messages(demo) == []
    assert list(structural(demo)) == []
    assert list(skeleton(demo)) == []


def test_a_title_naming_another_version(demo: Skill) -> None:
    broken = edit(demo, "SKILL.md", "# Demo Style — 1.2", "# Demo Style — 1.1")
    assert any("the title is" in m for m in messages(broken))


def test_a_renamed_section(demo: Skill) -> None:
    broken = edit(
        demo, "SKILL.md", "## 3. Design principles", "## 3. Design principles — less"
    )
    assert any("section 4 of 8" in m for m in messages(broken))


def test_a_section_out_of_order(demo: Skill) -> None:
    broken = edit(demo, "SKILL.md", "## 4. Core rules", "## 4. Rules")
    assert any("`## 4. Core rules`" in m for m in messages(broken))


def test_a_chapter_named_outside_the_vocabulary(demo: Skill) -> None:
    path = demo.root / "references" / "errors.md"
    path.rename(path.with_name("errors-and-control-flow.md"))
    assert any("not a chapter name" in m for m in messages(reparse(demo)))


def test_a_rule_carrying_another_chapters_code(demo: Skill) -> None:
    broken = edit(demo, "references/errors.md", "### DS-ERR-02", "### DS-TEST-02")
    assert any("whose family is `ERR`" in m for m in messages(broken))


def test_a_missing_migration_chapter(demo: Skill) -> None:
    (demo.root / "references" / "migration.md").unlink()
    assert any("references/migration.md" in m for m in messages(reparse(demo)))


def test_an_invented_severity(demo: Skill) -> None:
    broken = edit(
        demo, "references/review-checklist.md", "| **Style** |", "| **Nit** |"
    )
    assert any("severity model" in m for m in messages(broken))


def test_a_review_protocol_missing_a_section(demo: Skill) -> None:
    broken = edit(
        demo,
        "references/review-checklist.md",
        "## Refactoring a codebase to this standard",
        "## Refactoring",
    )
    assert any("protocol's sections" in m for m in messages(broken))


def test_section_five_drifting_from_the_review_order(demo: Skill) -> None:
    broken = edit(demo, "SKILL.md", "2. **Errors.** Look.", "2. **Panics.** Look.")
    assert any("section 5 lists" in m for m in messages(broken))


def test_reference_map_columns_out_of_order(demo: Skill) -> None:
    broken = edit(
        demo, "SKILL.md", "| File | Rule IDs | Covers |", "| File | Covers | Rule IDs |"
    )
    assert any("reference map's columns" in m for m in messages(broken))


def test_an_exemption_over_a_conforming_standard_is_reported(tmp_path: Path) -> None:
    exempt = build(tmp_path, dataclasses.replace(Demo(), exempt_from_structure="later"))
    assert any("already conforms" in f.message for f in skeleton(exempt))


def test_an_exemption_over_a_nonconforming_standard_is_quiet(tmp_path: Path) -> None:
    exempt = build(tmp_path, dataclasses.replace(Demo(), exempt_from_structure="later"))
    broken = edit(exempt, "SKILL.md", "## 4. Core rules", "## 4. Rules")
    assert list(skeleton(broken)) == []


def test_an_exemption_without_a_reason_fails(tmp_path: Path) -> None:
    blank = build(tmp_path, dataclasses.replace(Demo(), exempt_from_structure=" "))
    assert any("gives no reason" in f.message for f in skeleton(blank))
