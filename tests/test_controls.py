"""Each control injects one defect and asserts the check owning it notices.

A check that cannot fail looks exactly like a check that passes, so the controls
are tests in their own right rather than a claim in a README.
"""

import importlib

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
        c.name
        for c in all_checks()
        if c.name not in owned and c.name not in WITHOUT_A_CONTROL
    ]
    assert not missing, f"no negative control for: {missing}"


def test_no_exemption_outlives_its_check():
    """An exemption standing over nothing is an exemption nobody re-examined."""
    known = {c.name for c in all_checks()}
    stale = sorted(set(WITHOUT_A_CONTROL) - known)
    assert not stale, f"exemption names a check that no longer exists: {stale}"


def test_every_exemption_gives_a_reason():
    for name, reason in WITHOUT_A_CONTROL.items():
        assert reason and len(reason) > 20, (
            f"{name} is exempt with no reason worth reading"
        )


#: Each structure control, and the branch it is named for. Stubbing the branch
#: out must make the control stop firing: a control that still fires has been
#: satisfied by some other branch, and proves nothing about its own.
BRANCHES = {
    "a section title with a subtitle the other standards do not have": (
        "agent_skill.checks.skeleton",
        "_skill_md",
    ),
    "a chapter named outside the shared vocabulary": (
        "agent_skill.checks.skeleton",
        "_chapters",
    ),
    "a rule filed in a chapter whose family is another": (
        "agent_skill.checks.skeleton",
        "_chapters",
    ),
    "a severity label the shared model does not have": (
        "agent_skill.checks.skeleton",
        "_review",
    ),
    "section 5 drifting from the protocol's review order": (
        "agent_skill.checks.skeleton",
        "_skill_md",
    ),
    "a rename row leading to a rule that does not exist": (
        "agent_skill.checks.skeleton",
        "_renames",
    ),
    "a rename row mapping an ID to itself": ("agent_skill.checks.skeleton", "_renames"),
    "an old ID dropped from the rename table while no rule carries it": (
        "agent_skill.checks.skeleton",
        "_unchanged",
    ),
    "a shared sentence edited in one standard's copy": (
        "agent_skill.shared",
        "compare",
    ),
    "a gap in a chapter's numbering": ("agent_skill.checks.anatomy", "structural"),
    "a Why that runs to a fourth line": ("agent_skill.checks.anatomy", "structural"),
    "a ty lint row at a level the shipped configuration does not set": (
        "agent_skill.checks.citations",
        "python_rows",
    ),
}


@pytest.mark.parametrize("name", sorted(BRANCHES))
def test_a_structure_control_needs_its_own_branch(name, scratch, monkeypatch):
    control = next(c for c in CONTROLS if c.name == name)
    module, attr = BRANCHES[name]
    monkeypatch.setattr(importlib.import_module(module), attr, lambda *a, **k: iter(()))
    control.break_it(scratch)
    result = by_name(control.check).run(discover(scratch))
    assert not any(f.level is Level.FAIL for f in result.findings), (
        f"`{name}` still fires with `{attr}` stubbed out — another branch is reporting it"
    )
