"""Every authored pattern, shown to catch its target in both directions.

The module was titled "every" and its code asserted `any`: one pattern
matching stood as evidence for the rest of a rule's Check. Measured on
the shipped standard, `ZS-MIG-12` ships four patterns over four disjoint
families of dead API, its one fixture matched the first, and the other
three were counted as proven by a fixture none of them touched. Any of
the three could have been narrowed until it matched nothing at all
without this check noticing.

The second direction — every fixture matched by some pattern — is what
keeps the first honest. With only the first, an uncovered pattern is
"fixed" by adding a snippet nobody has related to the rule.
"""

from types import SimpleNamespace

import pytest

from agent_skill.checks.sensitivity import sensitivity
lazy from agent_skill.model import Skill

#: Two patterns over disjoint constructs, the shape that made `any`
#: unsafe.
TWO_PATTERNS = "**Check:** `rg -n 'alpha_call' src/` and `rg -n 'beta_call' src/`"


def fake(
    fires: dict[str, tuple[str, ...]], check: str = TWO_PATTERNS
) -> SimpleNamespace:
    """A stand-in skill with one rule, its Check, and its fixtures."""
    rule = SimpleNamespace(id="XX-Y-01", check=check, title="a rule with two patterns")
    return SimpleNamespace(
        name="fake-style",
        rules=[rule],
        profile=SimpleNamespace(fires=fires, languages=("rust",)),
    )


def messages(skill: SimpleNamespace) -> list[str]:
    return [f.message for f in sensitivity(skill)]  # ty: ignore[invalid-argument-type] — a stand-in with only what the check reads


def test_a_full_cover_passes() -> None:
    assert messages(fake({"XX-Y-01": ("x = alpha_call()", "y = beta_call()")})) == []


def test_one_fixture_no_longer_stands_for_every_pattern() -> None:
    """The regression, stated as the defect it was: this once passed."""
    found = messages(fake({"XX-Y-01": ("x = alpha_call()",)}))
    assert len(found) == 1, found
    assert "/beta_call/ matches none of this rule's fixtures" in found[0]


def test_a_fixture_no_pattern_matches_is_reported() -> None:
    found = messages(
        fake({"XX-Y-01": ("x = alpha_call()", "y = beta_call()", "z = gamma_call()")})
    )
    assert len(found) == 1, found
    assert "'z = gamma_call()' is matched by none" in found[0]


def test_both_directions_report_together() -> None:
    """A cover that fails each way names each failure.

    It reports them together rather than stopping at the first.
    """
    found = messages(fake({"XX-Y-01": ("x = alpha_call()", "z = gamma_call()")}))
    assert len(found) == 2, found
    assert any("/beta_call/ matches none" in m for m in found)
    assert any("'z = gamma_call()' is matched by none" in m for m in found)


def test_one_pattern_and_one_fixture_still_works() -> None:
    assert (
        messages(
            fake(
                {"XX-Y-01": ("x = alpha_call()",)},
                "**Check:** `rg -n 'alpha_call' src/`",
            )
        )
        == []
    )


def test_a_rule_listed_with_no_fixture_is_reported() -> None:
    found = messages(fake({"XX-Y-01": ()}))
    assert found
    assert "listed with no fixture" in found[0]


@pytest.mark.parametrize(
    ("check", "expected"),
    [
        ("**Check:** read it and judge.", "ships no command"),
        ("", "no **Check:** to run against it"),
    ],
)
def test_a_fixture_with_nothing_to_run_against_is_reported(
    check: str, expected: str
) -> None:
    found = messages(fake({"XX-Y-01": ("x = alpha_call()",)}, check))
    assert found
    assert expected in found[0]


def test_a_fixture_naming_an_unknown_rule_is_reported() -> None:
    skill = fake({"XX-Y-99": ("anything",)})
    found = messages(skill)
    assert found
    assert "a fixture names a rule this skill does not define" in found[0]


def test_the_shipped_standards_are_covered(skills: list[Skill]) -> None:
    """The rule this change enforces, asserted on the real profiles."""
    for skill in skills:
        if skill.profile.fires:
            assert list(sensitivity(skill)) == [], (
                f"{skill.name} has an unproven pattern"
            )
