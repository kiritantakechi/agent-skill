"""The shipped skills, parsed, and a throwaway copy to break."""

from pathlib import Path
lazy from collections.abc import Iterator

import pytest

from agent_skill.build import TARGETS
from agent_skill.checks.controls import throwaway_tree
from agent_skill.layout import SKILLS
from agent_skill.model import discover
lazy from agent_skill.model import Skill

REPO = Path(__file__).resolve().parents[1]
SKILLS_DIR = REPO / SKILLS


@pytest.fixture(scope="session")
def skills() -> list[Skill]:
    """Every shipped skill, parsed once for the whole session."""
    return discover(SKILLS_DIR)


@pytest.fixture
def scratch(tmp_path: Path) -> Path:
    """A throwaway copy of the skills tree, for injecting a defect into.

    Built by the same function `controls` uses, so a control cannot fire
    in one runner and not the other.
    """
    return throwaway_tree(SKILLS_DIR, tmp_path)


def _agents() -> dict[Path, dict[str, str] | None]:
    """Each agent's skills directory here, and what each entry is."""
    return {
        t.skills: {
            p.name: str(p.readlink()) if p.is_symlink() else "a directory"
            for p in t.skills.iterdir()
        }
        if t.skills.is_dir()
        else None
        for t in TARGETS
    }


@pytest.fixture(autouse=True)
def _no_install_into_this_machine() -> Iterator[None]:
    """No test installs into an agent on this machine.

    `install` links into the user's own skills directories; a test
    gives it a target under its temporary directory, and fails here if
    one of the real ones changed while it ran.
    """
    before = _agents()
    yield
    assert _agents() == before, "a test changed an agent's skills directory"
