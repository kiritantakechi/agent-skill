from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from agent_skill.model import discover

REPO = Path(__file__).resolve().parents[1]
SKILLS_DIR = REPO / "skills"


@pytest.fixture(scope="session")
def skills():
    return discover(SKILLS_DIR)


@pytest.fixture
def scratch(tmp_path) -> Path:
    """A throwaway copy of the skills tree, for injecting a defect into."""
    target = tmp_path / "skills"
    shutil.copytree(SKILLS_DIR, target, symlinks=True)
    return target
