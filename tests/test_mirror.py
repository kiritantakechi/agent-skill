"""Mirrored rules agree on tier in every standard, not in one pair.

The check was written for `rust-style` against `zig-style` and named
both skills as module constants, so a third standard could disagree with
the anchor about a tier and nothing would look. These cases pin the
routing: the skill a table entry refers to comes from the rule id's
prefix.
"""

from dataclasses import dataclass

from agent_skill.checks import mirror as m
lazy from agent_skill.report import Finding


@dataclass(frozen=True)
class Rule:
    """The three fields of a rule that `mirror` reads."""

    id: str
    tier: str
    title: str


class Skill:
    """A stand-in skill: a name, a prefix, and its rules by ID."""

    def __init__(self, name: str, prefix: str, rules: list[Rule]) -> None:
        """Hold the rules, indexed by ID as the real skill does."""
        self.name, self.prefix, self.rules = name, prefix, rules
        self.by_id = {r.id: r for r in rules}


TITLE = "One concept, one mechanism"


def run(table: list[tuple[str, str]], skills: list[Skill]) -> list[Finding]:
    original, m.MIRROR = m.MIRROR, table
    try:
        return list(m.mirror(skills))  # ty: ignore[invalid-argument-type] — a stand-in with only what the check reads
    finally:
        m.MIRROR = original


def anchor(tier: str = "[M]") -> Skill:
    return Skill("rust-style", "RS", [Rule("RS-NAME-01", tier, TITLE)])


def test_a_third_skill_is_routed_by_its_prefix() -> None:
    third = Skill("third-style", "XX", [Rule("XX-NAME-09", "[S]", TITLE)])
    findings = run([("XX-NAME-09", TITLE)], [anchor(), third])
    assert [f.message for f in findings] == [
        "tier mismatch: RS-NAME-01[[M]] vs XX-NAME-09[[S]]"
    ]


def test_a_third_skill_that_agrees_is_silent() -> None:
    third = Skill("third-style", "XX", [Rule("XX-NAME-09", "[M]", TITLE)])
    assert run([("XX-NAME-09", TITLE)], [anchor(), third]) == []


def test_an_entry_for_a_skill_not_in_this_run_is_skipped() -> None:
    """A partial run must not call every absent skill a missing rule."""
    assert run([("ZS-NAME-29", TITLE)], [anchor()]) == []


def test_an_unheld_pair_is_noticed_in_any_skill_not_only_the_first() -> None:
    third = Skill("third-style", "XX", [Rule("XX-NAME-09", "[M]", TITLE)])
    [found] = run([], [anchor(), third])
    assert found.level.value == "note"
    assert "XX-NAME-09 and RS-NAME-01" in found.message
