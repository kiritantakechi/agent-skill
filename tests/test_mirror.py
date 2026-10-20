"""Mirrored rules agree on tier, in every standard rather than in one pair.

The check was written for `rust-style` against `zig-style` and named both
skills as module constants, so a third standard could disagree with the anchor
about a tier and nothing would look. These cases pin the routing: the skill a
table entry refers to comes from the rule id's prefix.
"""

from __future__ import annotations

from dataclasses import dataclass

from agent_skill.checks import mirror as m


@dataclass(frozen=True)
class Rule:
    id: str
    tier: str
    title: str


class Skill:
    def __init__(self, name, prefix, rules):
        self.name, self.prefix, self.rules = name, prefix, rules
        self.by_id = {r.id: r for r in rules}


TITLE = "One concept, one mechanism"


def run(table, skills):
    original, m.MIRROR = m.MIRROR, table
    try:
        return list(m.mirror(skills))
    finally:
        m.MIRROR = original


def anchor(tier="[M]"):
    return Skill("rust-style", "RS", [Rule("RS-NAME-01", tier, TITLE)])


def test_a_third_skill_is_routed_by_its_prefix():
    third = Skill("third-style", "XX", [Rule("XX-NAME-09", "[S]", TITLE)])
    findings = run([("XX-NAME-09", TITLE)], [anchor(), third])
    assert [f.message for f in findings] == ["tier mismatch: RS-NAME-01[[M]] vs XX-NAME-09[[S]]"]


def test_a_third_skill_that_agrees_is_silent():
    third = Skill("third-style", "XX", [Rule("XX-NAME-09", "[M]", TITLE)])
    assert run([("XX-NAME-09", TITLE)], [anchor(), third]) == []


def test_an_entry_for_a_skill_not_in_this_run_is_skipped():
    """A partial run must not report every absent skill as a missing rule."""
    assert run([("ZS-NAME-36", TITLE)], [anchor()]) == []


def test_an_unheld_pair_is_noticed_in_any_skill_not_only_the_first():
    third = Skill("third-style", "XX", [Rule("XX-NAME-09", "[M]", TITLE)])
    [found] = run([], [anchor(), third])
    assert found.level.value == "note"
    assert "XX-NAME-09 and RS-NAME-01" in found.message
