"""Each control injects one defect and asserts the check owning it notices.

A check that cannot fail looks exactly like a check that passes, so the controls
are tests in their own right rather than a claim in a README.
"""

from __future__ import annotations

import pytest

from agent_skill.checks import all_checks, by_name
from agent_skill.checks.controls import CONTROLS, WITHOUT_A_CONTROL, FixtureGone
from agent_skill.model import discover
from agent_skill.report import Level


@pytest.mark.parametrize("control", CONTROLS, ids=lambda c: c.name)
def test_control_fires(control, scratch):
    all_checks()
    check = by_name(control.check)
    assert check is not None, f"no check named {control.check!r}"
    try:
        control.break_it(scratch)
    except FixtureGone as e:
        pytest.fail(f"the fixture has drifted out of the skill: {e}")
    result = check.run(discover(scratch))
    assert any(f.level is Level.FAIL for f in result.findings), (
        f"`{control.check}` still passes with `{control.name}` injected"
    )


def test_every_check_has_a_control():
    """A check nothing can break is a check nothing verifies."""
    owned = {c.check for c in CONTROLS}
    missing = [
        c.name for c in all_checks() if c.name not in owned and c.name not in WITHOUT_A_CONTROL
    ]
    assert not missing, f"no negative control for: {missing}"


def test_no_exemption_outlives_its_check():
    """An exemption standing over nothing is an exemption nobody re-examined."""
    known = {c.name for c in all_checks()}
    stale = sorted(set(WITHOUT_A_CONTROL) - known)
    assert not stale, f"exemption names a check that no longer exists: {stale}"


def test_every_exemption_gives_a_reason():
    for name, reason in WITHOUT_A_CONTROL.items():
        assert reason and len(reason) > 20, f"{name} is exempt with no reason worth reading"
