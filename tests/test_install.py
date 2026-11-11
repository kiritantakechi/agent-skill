"""Installing a skill into an agent that reads skills."""

import shutil
import zipfile
from dataclasses import replace
from pathlib import Path

import pytest

from agent_skill import build, cli
from agent_skill.build import EXCLUDE, TARGETS, install, package
from agent_skill.layout import SKILLS
from agent_skill.model import Skill
lazy from agent_skill.build import Target

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture
def target(tmp_path: Path) -> Target:
    home = tmp_path / "agent"
    (home / "skills").mkdir(parents=True)
    return replace(TARGETS[0], name="fake", skills=home / "skills", marker=home)


@pytest.fixture
def skill(scratch: Path) -> Skill:
    return Skill(scratch / "rust-style")


def test_links_rather_than_copies(target: Target, skill: Skill) -> None:
    done = install(skill, target)
    assert done.how == "linked"
    assert done.ok
    assert done.link.is_symlink()
    assert done.link.readlink() == skill.root


def test_a_relative_skills_directory_still_links_to_the_skill(
    target: Target, skill: Skill, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(skill.root.parent)
    link = install(Skill(Path(skill.name)), target).link
    assert link.resolve() == skill.root.resolve()
    assert (link / "SKILL.md").is_file()


def test_relinking_is_a_no_op(target: Target, skill: Skill) -> None:
    install(skill, target)
    assert install(skill, target).how == "already linked"


def test_a_stale_link_is_repointed(
    target: Target, skill: Skill, tmp_path: Path
) -> None:
    (target.skills / skill.name).symlink_to(tmp_path / "somewhere-else")
    done = install(skill, target)
    assert done.how == "linked"
    assert done.link.readlink() == skill.root


def test_a_copy_in_the_way_leaves_the_discovery_path(
    target: Target, skill: Skill
) -> None:
    """A displaced copy must leave `skills/`, or it is a second skill.

    `skills/<name>.replaced` beside `skills/<name>` is a second skill
    claiming the same name, because discovery reads the name from
    frontmatter.
    """
    stale = target.skills / skill.name
    stale.mkdir()
    (stale / "SKILL.md").write_text("---\nname: rust-style\n---\n")

    done = install(skill, target)
    assert done.link.is_symlink()
    assert done.link.readlink() == skill.root
    assert "moved to" in done.how
    assert done.ok
    assert (target.displaced / skill.name / "SKILL.md").exists()
    assert not target.displaced.is_relative_to(target.skills)
    assert [p.name for p in target.skills.iterdir()] == [skill.name]


def test_a_second_displacement_refuses_rather_than_clobbering(
    target: Target, skill: Skill
) -> None:
    (target.displaced / skill.name).mkdir(parents=True)
    stale = target.skills / skill.name
    stale.mkdir()
    done = install(skill, target)
    assert "left alone" in done.how
    assert not done.ok
    assert not (target.skills / skill.name).is_symlink()


def installed(target: Target, skills: Path) -> int:
    """`agent-skill install`, with `target` the only agent there is."""
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(build, "TARGETS", (target,))
        return cli.main(["--skills", str(skills), "install"])


def test_install_fails_when_it_leaves_a_differing_copy_alone(
    target: Target, skill: Skill, capsys: pytest.CaptureFixture[str]
) -> None:
    """The agent still reads the copy, so nothing was installed."""
    (target.displaced / skill.name).mkdir(parents=True)
    shutil.copytree(skill.root, target.skills / skill.name)
    (target.skills / skill.name / "SKILL.md").write_text("an older copy\n")
    assert installed(target, skill.root.parent) == 1
    assert "FAIL" in capsys.readouterr().out
    assert not (target.skills / skill.name).is_symlink()


def test_install_passes_when_the_copy_it_leaves_is_the_skill(
    target: Target, skill: Skill
) -> None:
    """A copy a package of the skill would hold, byte for byte."""
    (target.displaced / skill.name).mkdir(parents=True)
    shutil.copytree(skill.root, target.skills / skill.name)
    assert installed(target, skill.root.parent) == 0
    assert not (target.skills / skill.name).is_symlink()
    others = [p for p in target.skills.iterdir() if p.name != skill.name]
    assert others
    assert all(p.is_symlink() for p in others)


def test_targets_are_distinct() -> None:
    assert len({t.name for t in TARGETS}) == len(TARGETS)
    assert len({t.skills for t in TARGETS}) == len(TARGETS)


def test_the_package_leaves_out_what_the_repository_ignores(tmp_path: Path) -> None:
    """The skill sits in a `dist`: an ignored name above it is not."""
    root = tmp_path / "dist" / "demo-style"
    for junk in (
        ".ruff_cache/0.17/x",
        ".pytest_cache/v/x",
        ".venv/bin/python",
        "__pycache__/a.cpython-315.pyc",
        "assets/b.pyc",
        ".zig-cache/h/x",
    ):
        (root / junk).parent.mkdir(parents=True, exist_ok=True)
        (root / junk).write_text("x")
    (root / "SKILL.md").write_text("---\nname: demo-style\n---\n")
    (root / "assets" / "ruff.toml").write_text("")
    with zipfile.ZipFile(package(Skill(root), tmp_path / "out")) as z:
        names = z.namelist()
    assert sorted(names) == ["demo-style/SKILL.md", "demo-style/assets/ruff.toml"]


def test_the_exclusions_cover_everything_the_repository_ignores() -> None:
    """A name ignored wherever it stands is one no package holds.

    A path ignored in one place, as the eval suite's results are, lies
    outside every skill, where no package reaches.
    """
    ignored = [line.rstrip("/") for line in (REPO / ".gitignore").read_text().split()]
    assert {line for line in ignored if "/" not in line} <= set(EXCLUDE)
    paths = [Path(line) for line in ignored if "/" in line]
    assert not [p for p in paths if p.is_relative_to(SKILLS)]


def test_the_package_holds_only_the_skill(tmp_path: Path, skill: Skill) -> None:
    archive = package(skill, tmp_path)
    with zipfile.ZipFile(archive) as z:
        names = z.namelist()
    assert names
    assert all(n.startswith(f"{skill.name}/") for n in names)
    assert not any("__pycache__" in n or n.endswith(".DS_Store") for n in names)


def test_the_package_is_what_a_skill_upload_takes(tmp_path: Path, skill: Skill) -> None:
    """A `.zip` of the folder named after the skill, `SKILL.md` in it.

    The shape Agensi's checklist asks of an upload: a `SKILL.md` at the
    archive's root, or two folders down, is refused, and so is a
    frontmatter `name` that is not the folder's.
    """
    archive = package(skill, tmp_path)
    assert archive.name == f"{skill.name}.zip"
    with zipfile.ZipFile(archive) as z:
        names = z.namelist()
        manifest = z.read(f"{skill.name}/SKILL.md").decode()
    assert {n.split("/", 1)[0] for n in names} == {skill.name}
    assert f"\nname: {skill.name}\n" in manifest
