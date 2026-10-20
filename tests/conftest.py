from pathlib import Path

import pytest

from agent_skill.checks.controls import throwaway_tree
from agent_skill.model import discover

REPO = Path(__file__).resolve().parents[1]
SKILLS_DIR = REPO / "skills"


@pytest.fixture(scope="session")
def skills():
    return discover(SKILLS_DIR)


@pytest.fixture
def scratch(tmp_path) -> Path:
    """A throwaway copy of the skills tree, for injecting a defect into.

    Built by the same function `controls` uses, so a control cannot fire in one
    runner and not the other.
    """
    return throwaway_tree(SKILLS_DIR, tmp_path)
