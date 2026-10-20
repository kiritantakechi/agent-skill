"""Every check, over the skills this repository ships."""

import pytest

from agent_skill.checks import all_checks
lazy from agent_skill.checks import Check
lazy from agent_skill.model import Skill


def checks(*, slow: bool) -> list[Check]:
    return [c for c in all_checks() if c.slow is slow]


@pytest.mark.parametrize("check", checks(slow=False), ids=lambda c: c.name)
def test_check_is_clean(check: Check, skills: list[Skill]) -> None:
    result = check.run(skills)
    assert result.ok, "\n".join(f"  {f}" for f in result.fails)


@pytest.mark.toolchain
@pytest.mark.parametrize("check", checks(slow=True), ids=lambda c: c.name)
def test_toolchain_check_is_clean(check: Check, skills: list[Skill]) -> None:
    result = check.run(skills)
    assert result.ok, "\n".join(f"  {f}" for f in result.fails)


def test_every_check_has_a_label() -> None:
    for check in all_checks():
        assert check.label
        assert check.name
        assert check.scope in {"skill", "all"}


def test_names_are_unique() -> None:
    names = [c.name for c in all_checks()]
    assert len(names) == len(set(names))
