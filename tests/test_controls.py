"""Each control injects one defect and asserts its branch reports it.

A check that cannot fail looks exactly like a check that passes, so the
controls are tests in their own right rather than a claim in a README.
They run through the runner the `controls` check uses, so a control
cannot fire in one and not the other.

The controls are a bijection onto the branches that can fail a run:
each such branch has one control or one exemption with its reason. The
branches are read off their declarations, so a branch added to a check
is uncovered until someone decides which it gets.
"""

import importlib
import pkgutil
from pathlib import Path

import pytest

import agent_skill
from agent_skill.checks import all_checks
from agent_skill.checks.controls import CONTROLS, EXEMPT, exercise
from agent_skill.layout import SKILLS
from agent_skill.report import DECLARED, Level
lazy from agent_skill.checks.controls import Control
lazy from agent_skill.ids import Branch

SKILLS_DIR = Path(__file__).resolve().parents[1] / SKILLS

#: `fmt` reports through branches of its own: a command, not a check, so
#: no run it is part of can fail.
COMMANDS = {"fmt"}


@pytest.mark.parametrize("control", CONTROLS, ids=lambda c: str(c.branch))
def test_control_fires(control: Control) -> None:
    found = exercise(control, SKILLS_DIR)
    if any(f.level is Level.UNRUN for f in found):
        pytest.skip(found[0].message)
    assert not found, "\n".join(str(f) for f in found)


def declared() -> dict[Branch, Level]:
    """Every branch any module declares, every module imported first.

    A branch is declared where it is reported, in a check, a profile or
    a toolchain; importing them all is what makes the set whole.
    """
    for info in pkgutil.walk_packages(agent_skill.__path__, "agent_skill."):
        if info.name != "agent_skill.__main__":
            importlib.import_module(info.name)
    return DECLARED


def failing() -> set[Branch]:
    """Every branch a registered check declares at `FAIL`."""
    checks = {c.name for c in all_checks()}
    return {
        b
        for b, level in declared().items()
        if level is Level.FAIL and b.check in checks
    }


def test_every_branch_belongs_to_a_check() -> None:
    names = {c.name for c in all_checks()} | COMMANDS
    strays = sorted(str(b) for b in declared() if b.check not in names)
    assert not strays, f"branches of no registered check: {strays}"


def test_controls_and_exemptions_are_a_bijection_onto_failing_branches() -> None:
    """Each branch that can fail a run: one control or one exemption."""
    controlled = [c.branch for c in CONTROLS]
    doubled = sorted({str(b) for b in controlled if controlled.count(b) > 1})
    assert not doubled, f"more than one control for: {doubled}"
    both = sorted(str(b) for b in set(controlled) & set(EXEMPT))
    assert not both, f"controlled and exempt at once: {both}"
    missing = sorted(str(b) for b in failing() - set(controlled) - set(EXEMPT))
    assert not missing, f"no control and no exemption for: {missing}"


def test_no_control_or_exemption_outlives_its_branch() -> None:
    """One standing over nothing is one nobody re-examined."""
    stale = sorted(
        str(b) for b in {c.branch for c in CONTROLS} | set(EXEMPT) if b not in failing()
    )
    assert not stale, f"names no branch that can fail a run: {stale}"


def test_every_exemption_gives_a_reason() -> None:
    for branch, reason in EXEMPT.items():
        assert len(reason) > 20, f"{branch} is exempt with no reason worth reading"


def test_every_other_branch_a_control_allows_is_its_checks_with_a_reason() -> None:
    for control in CONTROLS:
        for branch, reason in control.also.items():
            assert branch in failing(), (
                f"{control.branch} allows {branch}, which cannot fail"
            )
            assert branch.check == control.branch.check, (
                f"{control.branch} allows {branch}"
            )
            assert len(reason) > 20, f"{control.branch} allows {branch} with no reason"
