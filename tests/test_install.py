"""Installing a skill into an agent that reads skills."""

from __future__ import annotations

from dataclasses import replace

import pytest

from agent_skill.build import TARGETS, install, package
from agent_skill.model import Skill


@pytest.fixture
def target(tmp_path):
    home = tmp_path / "agent"
    (home / "skills").mkdir(parents=True)
    return replace(TARGETS[0], name="fake", skills=home / "skills", marker=home)


@pytest.fixture
def skill(scratch):
    return Skill(scratch / "rust-style")


def test_links_rather_than_copies(target, skill):
    link, how = install(skill, target)
    assert how == "linked"
    assert link.is_symlink() and link.readlink() == skill.root


def test_relinking_is_a_no_op(target, skill):
    install(skill, target)
    _, how = install(skill, target)
    assert how == "already linked"


def test_a_stale_link_is_repointed(target, skill, tmp_path):
    (target.skills / skill.name).symlink_to(tmp_path / "somewhere-else")
    link, how = install(skill, target)
    assert how == "linked"
    assert link.readlink() == skill.root


def test_a_copy_in_the_way_leaves_the_discovery_path(target, skill):
    """`skills/<name>.replaced` beside `skills/<name>` is a second skill
    claiming the same name, because discovery reads the name from frontmatter."""
    stale = target.skills / skill.name
    stale.mkdir()
    (stale / "SKILL.md").write_text("---\nname: rust-style\n---\n")

    link, how = install(skill, target)
    assert link.is_symlink() and link.readlink() == skill.root
    assert "moved to" in how
    assert (target.displaced / skill.name / "SKILL.md").exists()
    assert not target.displaced.is_relative_to(target.skills)
    assert [p.name for p in target.skills.iterdir()] == [skill.name]


def test_a_second_displacement_refuses_rather_than_clobbering(target, skill):
    (target.displaced / skill.name).mkdir(parents=True)
    stale = target.skills / skill.name
    stale.mkdir()
    _, how = install(skill, target)
    assert "left alone" in how
    assert not (target.skills / skill.name).is_symlink()


def test_targets_are_distinct():
    assert len({t.name for t in TARGETS}) == len(TARGETS)
    assert len({t.skills for t in TARGETS}) == len(TARGETS)


def test_the_package_holds_only_the_skill(tmp_path, skill):
    import zipfile

    archive = package(skill, tmp_path)
    with zipfile.ZipFile(archive) as z:
        names = z.namelist()
    assert names
    assert all(n.startswith(f"{skill.name}/") for n in names)
    assert not any("__pycache__" in n or n.endswith(".DS_Store") for n in names)
