"""The shipped skills, parsed, and a throwaway copy to break."""

from pathlib import Path

import pytest

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
