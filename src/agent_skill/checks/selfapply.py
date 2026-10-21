"""The standard's own Checks, run against its own examples.

Many rules end in a Check that is a literal `rg`. A standard whose
examples fail its own patterns is not a standard, and nothing was
running them.

What is left here is the judgement: which tier a hit belongs to, and how
it reads. Turning a Check into patterns is `patterns`, what they run
over is `corpus`, and running them is `search` — three concerns that
were in this file and that `crossref` was importing from a module named
after a different check.
"""

import re
lazy from collections.abc import Iterator

from agent_skill.checks import check
from agent_skill.checks.corpus import corpus_for
from agent_skill.checks.patterns import patterns_of
from agent_skill.checks.search import find, searcher_problem
from agent_skill.report import fail, note, unrun
lazy from agent_skill.checks.corpus import Corpus
lazy from agent_skill.checks.patterns import Pattern
lazy from agent_skill.checks.search import Span
lazy from agent_skill.model import Rule, Skill
lazy from agent_skill.report import Finding

#: One pattern's surviving hits: the rule whose Check it is, the
#: pattern, how it was searched, and the spans it matched.
type Row = tuple[Rule, Pattern, str, list[Span]]

#: Tier 1 decides, tier 2 narrows for a person, tier 3 enumerates.
type Tiers = tuple[list[Row], list[Row], list[Row]]


@check(
    "self-application",
    "the standard's own patterns over its own examples",
    needs=("rg",),
)
def selfapply(skill: Skill) -> Iterator[Finding]:
    """The skill's own Check patterns, over the skill's own examples."""
    lang = skill.profile.languages[0] if skill.profile.languages else ""
    if not lang:
        return
    if problem := searcher_problem():
        yield unrun(problem, skill.name)
        return
    yield from _run(skill, lang)


def _run(skill: Skill, lang: str) -> Iterator[Finding]:
    profile = skill.profile
    corpus = corpus_for(skill, lang)
    if not corpus.blocks or not skill.rules:
        yield fail(
            f"nothing to check: {corpus.blocks} blocks, {len(skill.rules)} rules — "
            f"an empty corpus passes every pattern in the library",
            skill.name,
        )
        return

    claimed: set[str] = set()
    tiers: Tiers = ([], [], [])

    for rule in skill.rules:
        if not rule.check:
            continue
        # An entry suppresses this rule's pattern, so it has to keep
        # quoting words the rule still says. Claimed before the
        # path-scoped skip below, or a `rg -v` rule with an entry would
        # look like a rule that vanished.
        if entry := profile.not_decisive.get(rule.id):
            claimed.add(rule.id)
            if entry.anchor not in " ".join(rule.check.split()):
                yield fail(
                    f"{rule.id}: the exemption quotes {entry.anchor!r}, which its "
                    f"**Check:** no longer says",
                    skill.name,
                )
        # `rg … | rg -v '^src/lib.rs'` asks *which file* the hit is in.
        # An example block is a single crate root, so it cannot be
        # evaluated here.
        if re.search(r"\brg -v\b", rule.check):
            continue
        yield from _search(skill, corpus, rule, tiers)

    # Only this skill's own entries: an entry naming a rule the skill no
    # longer defines is a suppression standing over nothing.
    for rid in sorted(set(profile.not_decisive) - claimed):
        yield fail(
            f"{rid}: the exemption names a rule this skill does not define", skill.name
        )

    yield from _report(skill, corpus, tiers)


def _search(
    skill: Skill, corpus: Corpus, rule: Rule, tiers: Tiers
) -> Iterator[Finding]:
    """Run one rule's patterns, filing what survives into its tier."""
    profile = skill.profile
    for pattern in patterns_of(rule.check):
        lines, used = find(corpus, pattern)
        if lines is None:
            yield fail(
                f"{rule.id}: the search gave no answer for its own Check pattern "
                f"/{pattern.text}/ — rejected, timed out, or not installed",
                skill.name,
            )
            continue
        exempt = profile.exempt.get(rule.id)
        source = corpus.lines_for(pattern)
        kept = [s for s in lines if not (exempt and exempt(source, s, corpus.in_test))]
        if not kept:
            continue
        row = (rule, pattern, used, kept)
        if len(kept) > profile.judgement:
            tiers[2].append(row)
        elif pattern.kind == "command" and rule.id not in profile.not_decisive:
            tiers[0].append(row)
        else:
            tiers[1].append(row)


def _report(skill: Skill, corpus: Corpus, tiers: Tiers) -> Iterator[Finding]:
    """Each tier as findings, the rows with the most hits first."""
    tier1, tier2, tier3 = tiers
    for row in sorted(tier1, key=lambda r: -len(r[3])):
        yield fail(_render(corpus, row), skill.name)
    for row in sorted(tier2, key=lambda r: -len(r[3])):
        entry = skill.profile.not_decisive.get(row[0].id)
        why = (
            entry.reason
            if entry
            else "prose span: the pattern narrows, a person decides"
        )
        yield note(
            _render(corpus, row, limit=3) + f"  ({why})",
            skill.name,
        )
    for row in sorted(tier3, key=lambda r: -len(r[3])):
        yield note(
            _render(corpus, row, limit=0) + "  (enumerates rather than accuses)",
            skill.name,
        )


def _render(corpus: Corpus, row: Row, *, limit: int = 8) -> str:
    rule, pattern, used, hits = row
    head = f"{rule.id} {used} /{pattern.text}/ — {len(hits)} hit(s) — {rule.title}"
    for h in hits[:limit]:
        chapter, owner, line, snippet = corpus.origin(h.start)
        across = f"+{len(h) - 1}" if len(h) > 1 else ""
        head += f"\n      {chapter}:{line}{across} [{owner}] {snippet}"
    if len(hits) > limit:
        head += f"\n      … {len(hits) - limit} more"
    return head
