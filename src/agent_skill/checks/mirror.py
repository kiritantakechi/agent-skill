"""Rules that say the same thing in two skills must agree on tier.

The table is anchored on rule **titles**, which survive renumbering — a
renumbering pass twice pointed it at unrelated rules. Titles only anchor
if they are unique, which the anatomy check enforces; ambiguity here is
a failure rather than a silent pick.
"""

import re

from agent_skill.checks import check
from agent_skill.checks.anatomy import overlap
from agent_skill.report import fail, note

#: (rule id in another skill, title of its counterpart in the anchor).
#: The id's prefix names which skill it belongs to, so a fourth standard
#: joins the table without restructuring it — and gets the unheld-pair
#: note for free.
MIRROR: list[tuple[str, str]] = [
    ("ZS-TYPE-39", "Give every operation its inverse, or document why there is none"),
    ("ZS-TYPE-40", "Keep argument order identical across sibling functions"),
    ("ZS-TYPE-41", "Split a function rather than adding a mode parameter"),
    ("ZS-ERR-37", "Give sibling error variants a uniform shape"),
    (
        "ZS-ERR-38",
        "Absorb a special case into the general path, or give it its own type",
    ),
    ("ZS-NAME-35", "Name the two halves of a pair symmetrically"),
    ("ZS-NAME-36", "One concept, one mechanism"),
    ("ZS-NAME-37", "Keep sibling modules structurally parallel"),
    (
        "ZS-CT-01",
        "Name the capability as a trait before writing the type that provides it",
    ),
    ("ZS-BUILD-24", "Count the encapsulation a split costs, not only what it buys"),
    ("ZS-BUILD-26", "Give the directory and the crate the same name"),
    ("ZS-NAME-02", "Capitalize acronyms as ordinary English words"),
]

ANCHOR = "rust-style"


def _shingles(s: str, n: int = 3) -> set[tuple[str, ...]]:
    words = " ".join(re.findall(r"[a-z]+", s.lower())).split()
    return {tuple(words[i : i + n]) for i in range(max(0, len(words) - n + 1))}


@check("mirror", "mirrored rules agree on tier", scope="all")
def mirror(skills):
    by_name = {s.name: s for s in skills}
    anchor = by_name.get(ANCHOR)
    if anchor is None:
        return
    by_prefix = {s.prefix: s for s in skills if s.name != ANCHOR}

    titles: dict[str, list] = {}
    for rule in anchor.rules:
        titles.setdefault(rule.title, []).append(rule)

    held = {rid for rid, _ in MIRROR}
    for rid, title in MIRROR:
        matches = titles.get(title, [])
        mirrored = by_prefix.get(rid.split("-")[0])
        if mirrored is None:
            continue  # that skill is not in this run; nothing to compare against
        other = mirrored.by_id.get(rid)
        if not matches:
            yield fail(f"no {ANCHOR} rule titled {title!r}", "mirror")
        elif len(matches) > 1:
            yield fail(
                f"{title!r} is ambiguous ({', '.join(r.id for r in matches)}); the anchor "
                f"cannot say which rule {rid} mirrors",
                "mirror",
            )
        elif other is None:
            yield fail(f"{rid} is not a rule in {mirrored.name}", "mirror")
        elif matches[0].tier != other.tier:
            yield fail(
                f"tier mismatch: {matches[0].id}[{matches[0].tier}] vs {rid}[{other.tier}]",
                "mirror",
            )

    # The table is hand-maintained, so it needs something that notices a
    # pair it does not yet hold: three mirrored rules were guarded by
    # nothing at all. Every non-anchor skill is searched, not just the
    # one the table was written for — a pair the table misses is the
    # same defect whichever standard it is in.
    anchor_shingles = [(r, _shingles(r.title)) for r in anchor.rules]
    for mirrored in by_prefix.values():
        for rule in mirrored.rules:
            if rule.id in held:
                continue
            a = _shingles(rule.title)
            if not a:
                continue
            for other, b in anchor_shingles:
                if b and overlap(a, b) > 0.5:
                    yield note(
                        f"{rule.id} and {other.id} look like a pair MIRROR does not hold "
                        f"({rule.title!r})",
                        "mirror",
                    )
