"""The plugin's manifests, against the layout and the skills."""

import json
lazy from pathlib import Path

import pytest

from agent_skill.checks import plugin as mod
from agent_skill.layout import PLUGIN, SKILLS
from agent_skill.report import Level
from structure_fixture import build
lazy from agent_skill.model import Skill

MANIFEST = {"name": PLUGIN.name, "version": "1.0.0", "license": "MIT"}
ENTRY = {"name": PLUGIN.name, "source": f"./{PLUGIN.as_posix()}"}


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A repository laid out as this one is, holding the demo skill."""
    build(tmp_path / SKILLS)
    write(tmp_path / PLUGIN / mod.MANIFEST, MANIFEST)
    write(tmp_path / mod.MARKETPLACE, {"name": "m", "owner": {}, "plugins": [ENTRY]})
    (tmp_path / "LICENSE").write_text("MIT\n")
    monkeypatch.setattr(mod, "have", lambda _tool: False)
    return tmp_path


def write(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))


def failures(repo: Path) -> list[str]:
    skill = Skill(repo / SKILLS / "demo-style")
    return [f.message for f in mod.plugin([skill]) if f.level is Level.FAIL]


def test_a_conforming_plugin_only_waits_for_the_validator(repo: Path) -> None:
    skill = Skill(repo / SKILLS / "demo-style")
    assert [f.level for f in mod.plugin([skill])] == [Level.UNRUN]


def test_a_manifest_naming_another_plugin(repo: Path) -> None:
    write(repo / PLUGIN / mod.MANIFEST, MANIFEST | {"name": "other"})
    assert failures(repo) == [f"names the plugin 'other', not {PLUGIN.name!r}"]


def test_a_version_stated_twice(repo: Path) -> None:
    market = {"name": "m", "owner": {}, "plugins": [ENTRY | {"version": "1.0.0"}]}
    write(repo / mod.MARKETPLACE, market)
    assert any("states a `version` for the plugin" in m for m in failures(repo))


def test_no_license_file(repo: Path) -> None:
    (repo / "LICENSE").unlink()
    assert failures(repo) == ["needs both a `license` and a LICENSE file at the root"]


def test_a_skill_the_checks_do_not_read(repo: Path) -> None:
    stray = repo / SKILLS / "stray-style"
    stray.mkdir()
    (stray / "SKILL.md").write_text("---\nname: stray-style\n---\n")
    assert any(
        "the plugin ships ['demo-style', 'stray-style']" in m for m in failures(repo)
    )
