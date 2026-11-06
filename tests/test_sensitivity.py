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
from agent_skill.ids import Location
lazy from agent_skill.model import Skill

#: Two patterns over disjoint constructs, the shape that made `any`
#: unsafe.
TWO_PATTERNS = "**Check:** `rg -n 'alpha_call' src/` and `rg -n 'beta_call' src/`"


def fake(
    fires: dict[str, tuple[str, ...]],
    check: str = TWO_PATTERNS,
    unproven: frozenset[str] = frozenset(),
) -> SimpleNamespace:
    """A stand-in skill with one rule, its Check, and its fixtures."""
    rule = SimpleNamespace(id="XX-Y-01", check=check, title="a rule with two patterns")
    return SimpleNamespace(
        name="fake-style",
        rules=[rule],
        profile=SimpleNamespace(fires=fires, languages=("rust",), unproven=unproven),
        at=lambda: Location("fake-style"),
    )


def messages(skill: SimpleNamespace) -> list[str]:
    return [f.message for f in sensitivity.each(skill)]  # ty: ignore[invalid-argument-type] — a stand-in with only what the check reads


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


def test_a_rule_listed_with_no_fixture_proves_none_of_its_patterns() -> None:
    """A shipped profile may not list one; the cover still says so."""
    found = messages(fake({"XX-Y-01": ()}))
    assert len(found) == 2, found
    assert all("matches none of this rule's fixtures" in m for m in found)


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
    skill = fake({"XX-Y-99": ("anything",)}, unproven=frozenset({"XX-Y-01"}))
    found = messages(skill)
    assert found
    assert "a fixture names a rule this skill does not define" in found[0]


def test_a_pattern_neither_proven_nor_listed_fails() -> None:
    """The gap that used to be skipped without a word."""
    [found] = messages(fake({}))
    assert found.startswith("XX-Y-01: ships an `rg` pattern that no fixture proves")


def test_a_pattern_listed_as_unproven_is_accounted_for() -> None:
    assert messages(fake({}, unproven=frozenset({"XX-Y-01"}))) == []


@pytest.mark.parametrize(
    ("fires", "check", "listed", "stale"),
    [
        ({}, TWO_PATTERNS, "XX-Y-99", "names a rule this skill does not define"),
        (
            {"XX-Y-01": ("x = alpha_call()", "y = beta_call()")},
            TWO_PATTERNS,
            "XX-Y-01",
            "has a fixture in `fires` now",
        ),
        ({}, "**Check:** read it and judge.", "XX-Y-01", "ships no `rg` pattern"),
    ],
)
def test_an_entry_that_stopped_being_true_fails(
    fires: dict[str, tuple[str, ...]], check: str, listed: str, stale: str
) -> None:
    """An entry outliving its reason fails, so the list only shrinks."""
    found = messages(fake(fires, check, frozenset({listed}) | {"XX-Y-01"}))
    assert any(
        m.startswith(f"{listed}: listed as unproven") and stale in m for m in found
    ), found


def test_the_shipped_standards_are_covered(skills: list[Skill]) -> None:
    """The rule this change enforces, asserted on the real profiles."""
    for skill in skills:
        assert list(sensitivity.each(skill)) == [], (
            f"{skill.name} has an unproven pattern"
        )
