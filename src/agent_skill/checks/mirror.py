"""Rules that say the same thing in two skills must agree on tier.

The table is anchored on rule **titles**, which survive renumbering — a
renumbering pass twice pointed it at unrelated rules. Titles only anchor
if they are unique, which the anatomy check enforces; ambiguity here is
a failure rather than a silent pick.
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

#: (rule id in another skill, title of its counterpart in the anchor).
#: The id's prefix names which skill it belongs to, so a fourth standard
#: joins the table without restructuring it — and gets the unheld-pair
#: note for free.
MIRROR: list[tuple[str, str]] = [
    ("ZS-DATA-36", "Give every operation its inverse, or document why there is none"),
    ("ZS-DATA-37", "Keep argument order identical across sibling functions"),
    ("ZS-DATA-38", "Replace a `bool` parameter: split the function, or name the flag"),
    ("ZS-ERR-33", "Give sibling error variants a uniform shape"),
    (
        "ZS-ERR-34",
        "Absorb a special case into the general path, or give it its own type",
    ),
    ("ZS-NAME-28", "Name the two halves of a pair symmetrically"),
    ("ZS-NAME-29", "One concept, one mechanism"),
    ("ZS-NAME-30", "Keep sibling modules structurally parallel"),
    (
        "ZS-COMPTIME-16",
        "Name the capability as a trait before writing the type that provides it",
    ),
    ("ZS-BUILD-22", "Count the encapsulation a split costs, not only what it buys"),
    ("ZS-BUILD-24", "Give the directory and the crate the same name"),
    ("ZS-NAME-02", "Capitalize acronyms as ordinary English words"),
]

ANCHOR = "rust-style"

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
    """Pairs in `MIRROR` agree on tier; a pair it misses is noted.

    A finding lies in the skill whose rule mirrors the anchor's, at
    that rule, or in the anchor when it is the anchor's title that
    does not resolve.
    """
    by_name = {s.name: s for s in tree}
    anchor = by_name.get(ANCHOR)
    if anchor is None:
        return
    by_prefix = {s.prefix: s for s in tree if s.name != ANCHOR}
    yield from _held(anchor, by_prefix)
    yield from _unheld(anchor, by_prefix)


def _held(anchor: Skill, by_prefix: dict[str, Skill]) -> Iterator[Finding]:
    """Each `MIRROR` pair resolves to one rule a side, at one tier."""
    titles: dict[str, list[Rule]] = {}
    for rule in anchor.chapter_rules:
        titles.setdefault(rule.title, []).append(rule)
    by_id = {p: {r.id: r for r in s.chapter_rules} for p, s in by_prefix.items()}

    for spelled, title in MIRROR:
        rid = RuleId.parse(spelled)
        matches = titles.get(title, [])
        mirrored = by_prefix.get(rid.standard)
        if mirrored is None:
            continue  # that skill is not in this run; nothing to compare against
        other = by_id[rid.standard].get(rid)
        if not matches:
            yield fail(
                f"no {ANCHOR} rule titled {title!r}", Location(ANCHOR), NO_ANCHOR_RULE
            )
        elif len(matches) > 1:
            named = ", ".join(str(r.id) for r in matches)
            yield fail(
                f"{title!r} is ambiguous ({named}); "
                f"the anchor cannot say which rule {rid} mirrors",
                Location(ANCHOR),
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


def _unheld(anchor: Skill, by_prefix: dict[str, Skill]) -> Iterator[Finding]:
    """A pair that looks mirrored and that `MIRROR` does not yet hold.

    The table is hand-maintained, so it needs something that notices a
    pair it does not yet hold: three mirrored rules were guarded by
    nothing at all. Every non-anchor skill is searched, not just the one
    the table was written for — a pair the table misses is the same
    defect whichever standard it is in.
    """
    held = {RuleId.parse(spelled) for spelled, _ in MIRROR}
    anchor_shingles = [(r, _shingles(r.title)) for r in anchor.chapter_rules]
    for mirrored in by_prefix.values():
        for rule in mirrored.chapter_rules:
            if rule.id in held:
                continue
            a = _shingles(rule.title)
            if not a:
                continue
            for other, b in anchor_shingles:
                if b and overlap(a, b) > LOOKS_PAIRED:
                    yield note(
                        f"{rule.id} and {other.id} look like a pair MIRROR does "
                        f"not hold ({rule.title!r})",
                        Location(mirrored.name, rule=rule.id),
                        UNHELD,
                    )
