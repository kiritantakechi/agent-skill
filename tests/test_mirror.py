"""Mirrored rules agree on tier in every standard, not in one pair.

The check was written for `rust-style` against `zig-style` and named
both skills as module constants, so a third standard could disagree with
the anchor about a tier and nothing would look. Each profile now names
the standard it is compared with and the pairs it holds, so these cases
pin the routing: a pair is read from the profile of the skill whose rule
it names.
"""

from agent_skill.checks import mirror as m
from agent_skill.doc.chapter import Rule
from agent_skill.ids import RuleId, Tier
from agent_skill.model import Tree
from agent_skill.profiles import Mirror, Profile
lazy from agent_skill.report import Finding


def rule(rid: str, tier: Tier, title: str) -> Rule:
    """A chapter rule with only what `mirror` reads: ID, tier, title."""
    return Rule(RuleId.parse(rid), tier, title, ())


class Skill:
    """A stand-in skill: a name, a profile, and its chapter rules."""

    def __init__(
        self, name: str, prefix: str, rules: list[Rule], mirror: Mirror | None = None
    ) -> None:
        """Hold the rules as the real skill's chapters give them."""
        self.name, self.prefix, self.chapter_rules = name, prefix, tuple(rules)
        self.profile = Profile(name, prefix, mirror=mirror)


TITLE = "One concept, one mechanism"


def run(skills: list[Skill]) -> list[Finding]:
    return list(m.mirror(Tree.of(skills)))  # ty: ignore[invalid-argument-type] — a stand-in with only what the check reads


def anchor(tier: Tier = Tier.M) -> Skill:
    return Skill("rust-style", "RS", [rule("RS-NAME-01", tier, TITLE)])


def third(tier: Tier, pairs: tuple[tuple[str, str], ...] = ()) -> Skill:
    rules = [rule("XX-NAME-09", tier, TITLE)]
    held = tuple((RuleId.parse(rid), title) for rid, title in pairs)
    return Skill("third-style", "XX", rules, Mirror("rust-style", held))


def test_a_third_skill_is_held_by_its_own_profile() -> None:
    findings = run([anchor(), third(Tier.S, (("XX-NAME-09", TITLE),))])
    assert [f.message for f in findings] == [
        "tier mismatch: RS-NAME-01 [M] vs XX-NAME-09 [S]"
    ]


def test_a_third_skill_that_agrees_is_silent() -> None:
    assert run([anchor(), third(Tier.M, (("XX-NAME-09", TITLE),))]) == []


def test_a_skill_whose_anchor_is_not_in_this_run_is_skipped() -> None:
    """A partial run must not call every absent rule a missing one."""
    assert run([third(Tier.S, (("XX-NAME-09", TITLE),))]) == []


def test_an_unheld_pair_is_noticed_in_any_skill_not_only_the_first() -> None:
    [found] = run([anchor(), third(Tier.M)])
    assert found.level.value == "note"
    assert "XX-NAME-09 and RS-NAME-01" in found.message


def test_a_skill_that_names_no_anchor_is_not_compared() -> None:
    alone = Skill("third-style", "XX", [rule("XX-NAME-09", Tier.S, TITLE)])
    assert run([anchor(), alone]) == []
