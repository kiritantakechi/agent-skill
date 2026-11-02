"""Each control injects one defect and asserts its branch reports it.

A check that cannot fail looks exactly like a check that passes, so the
controls are tests in their own right rather than a claim in a README.
They run through the runner the `controls` check uses, so a control
cannot fire in one and not the other.
"""

from pathlib import Path

import pytest

from agent_skill.checks import all_checks
from agent_skill.checks.controls import CONTROLS, WITHOUT_A_CONTROL, exercise
from agent_skill.layout import SKILLS
from agent_skill.report import Level
lazy from agent_skill.checks.controls import Control

SKILLS_DIR = Path(__file__).resolve().parents[1] / SKILLS


@pytest.mark.parametrize("control", CONTROLS, ids=lambda c: str(c.branch))
def test_control_fires(control: Control) -> None:
    found = exercise(control, SKILLS_DIR)
    if any(f.level is Level.UNRUN for f in found):
        pytest.skip(found[0].message)
    assert not found, "\n".join(str(f) for f in found)


def test_every_check_has_a_control() -> None:
    """A check nothing can break is a check nothing verifies."""
    owned = {c.branch.check for c in CONTROLS}
    missing = [
        c.name
        for c in all_checks()
        if c.name not in owned and c.name not in WITHOUT_A_CONTROL
    ]
    assert not missing, f"no negative control for: {missing}"


def test_no_exemption_outlives_its_check() -> None:
    """An exemption standing over nothing is one nobody re-examined."""
    known = {c.name for c in all_checks()}
    stale = sorted(set(WITHOUT_A_CONTROL) - known)
    assert not stale, f"exemption names a check that no longer exists: {stale}"


def test_every_exemption_gives_a_reason() -> None:
    for name, reason in WITHOUT_A_CONTROL.items():
        assert reason, f"{name} is exempt with no reason worth reading"
        assert len(reason) > 20, f"{name} is exempt with no reason worth reading"


def test_one_control_per_branch() -> None:
    """Two controls on one branch prove the same thing twice."""
    seen = [c.branch for c in CONTROLS]
    doubled = sorted({str(b) for b in seen if seen.count(b) > 1})
    assert not doubled, f"more than one control for: {doubled}"
