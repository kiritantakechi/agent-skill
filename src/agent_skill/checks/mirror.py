"""Rules that say the same thing in two skills must agree on tier.

Each profile names the standard its rules are compared with, and the
pairs it holds (`Profile.mirror`). A pair is anchored on the other
rule's **title**, which survives renumbering — a renumbering pass twice
pointed an ID-keyed table at unrelated rules. Titles only anchor if they
are unique, which the anatomy check enforces; ambiguity here is a
failure rather than a silent pick.
"""

import re
lazy from collections.abc import Iterator

from agent_skill.checks import check
from agent_skill.checks.anatomy import overlap
from agent_skill.ids import Location, RuleId
from agent_skill.report import Level, declare, fail, note
lazy from agent_skill.doc.chapter import Rule
lazy from agent_skill.model import Skill, Tree
lazy from agent_skill.report import Finding

#: Above this overlap between two titles, the rules look like a pair.
LOOKS_PAIRED = 0.5

# The branches a finding of this check comes from.
NO_ANCHOR_RULE = declare("mirror", "no_anchor_rule", Level.FAIL)
AMBIGUOUS = declare("mirror", "ambiguous", Level.FAIL)
NOT_A_RULE = declare("mirror", "not_a_rule", Level.FAIL)
TIER = declare("mirror", "tier", Level.FAIL)
UNHELD = declare("mirror", "unheld", Level.NOTE)


def _shingles(s: str, n: int = 3) -> set[tuple[str, ...]]:
    words = " ".join(re.findall(r"[a-z]+", s.lower())).split()
    return {tuple(words[i : i + n]) for i in range(max(0, len(words) - n + 1))}


@check("mirror", "mirrored rules agree on tier")
def mirror(tree: Tree) -> Iterator[Finding]:
    """Each profile's pairs agree on tier; a pair it misses is noted.

    A finding lies in the skill whose rule mirrors the anchor's, at
    that rule, or in the anchor when it is the anchor's title that
    does not resolve. A skill whose anchor is not in the tree is not
    compared: there is nothing to compare it with.
    """
    by_name = {s.name: s for s in tree}
    compared = [
        (skill, anchor)
        for skill in tree
        if skill.profile.mirror is not None
        and (anchor := by_name.get(skill.profile.mirror.anchor)) is not None
    ]
    for skill, anchor in compared:
        yield from _held(skill, anchor)
    for skill, anchor in compared:
        yield from _unheld(skill, anchor)


def _pairs(skill: Skill) -> tuple[tuple[RuleId, str], ...]:
    """The pairs `skill`'s profile holds: a rule here, a title there."""
    declared = skill.profile.mirror
    return declared.pairs if declared is not None else ()


def _held(mirrored: Skill, anchor: Skill) -> Iterator[Finding]:
    """Each held pair resolves to one rule a side, at one tier."""
    titles: dict[str, list[Rule]] = {}
    for rule in anchor.chapter_rules:
        titles.setdefault(rule.title, []).append(rule)
    by_id = {r.id: r for r in mirrored.chapter_rules}

    for rid, title in _pairs(mirrored):
        matches = titles.get(title, [])
        other = by_id.get(rid)
        if not matches:
            yield fail(
                f"no {anchor.name} rule titled {title!r}",
                Location(anchor.name),
                NO_ANCHOR_RULE,
            )
        elif len(matches) > 1:
            named = ", ".join(str(r.id) for r in matches)
            yield fail(
                f"{title!r} is ambiguous ({named}); "
                f"the anchor cannot say which rule {rid} mirrors",
                Location(anchor.name),
                AMBIGUOUS,
            )
        elif other is None:
            yield fail(
                f"{rid} is not a rule in {mirrored.name}",
                Location(mirrored.name),
                NOT_A_RULE,
            )
        elif matches[0].tier != other.tier:
            yield fail(
                f"tier mismatch: {matches[0].id} {matches[0].tier} "
                f"vs {rid} {other.tier}",
                Location(mirrored.name, rule=rid),
                TIER,
            )


def _unheld(mirrored: Skill, anchor: Skill) -> Iterator[Finding]:
    """A pair that looks mirrored and that the profile does not hold.

    The pairs are written by hand, so they need something that notices
    a pair they do not yet hold: three mirrored rules were guarded by
    nothing at all. Every skill compared with the anchor is searched,
    not just the one with pairs — a pair a profile misses is the same
    defect whichever standard it is in.
    """
    held = {rid for rid, _ in _pairs(mirrored)}
    anchor_shingles = [(r, _shingles(r.title)) for r in anchor.chapter_rules]
    for rule in mirrored.chapter_rules:
        if rule.id in held:
            continue
        a = _shingles(rule.title)
        if not a:
            continue
        for other, b in anchor_shingles:
            if b and overlap(a, b) > LOOKS_PAIRED:
                yield note(
                    f"{rule.id} and {other.id} look like a pair its profile does "
                    f"not mirror ({rule.title!r})",
                    Location(mirrored.name, rule=rule.id),
                    UNHELD,
                )
