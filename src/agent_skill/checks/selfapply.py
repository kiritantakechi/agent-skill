"""The standard's own Checks, run against its own examples.

Many rules end in a Check that is a literal `rg`. A standard whose
examples fail its own patterns is not a standard, and nothing was
running them.

What is left here is the judgement: which tier a hit belongs to, and how
it reads. Turning a Check into patterns is `patterns`, what they run
over is `corpus`, and running them is `search` — three concerns that
were in this file and that `crossref` was importing from a module named
after a different check.

The repository applies a standard to itself too: the one the harness is
written to. Its workflow is that standard's shipped workflow plus what
the harness runs, so every step the two share is held to the asset's.
"""

lazy from collections.abc import Iterator

from agent_skill import workflow
from agent_skill.checks import check, per_skill
from agent_skill.checks.corpus import corpus_for
from agent_skill.checks.lines import excused
from agent_skill.checks.patterns import NEGATED, check_text, filtered_of, patterns_of
from agent_skill.checks.search import find, searcher_problem
from agent_skill.ids import Location
from agent_skill.layout import in_repository, root_of
from agent_skill.report import Level, declare, fail, note, unrun
lazy from agent_skill.checks.corpus import Corpus
lazy from agent_skill.checks.patterns import Pattern
lazy from agent_skill.checks.search import Span
lazy from agent_skill.doc.chapter import Rule
lazy from agent_skill.ids import RuleId
lazy from agent_skill.model import Skill, Tree
lazy from agent_skill.report import Finding
lazy from agent_skill.workflow import Step

#: One pattern's surviving hits: the rule whose Check it is, the
#: pattern, how it was searched, and the spans it matched.
type Row = tuple[Rule, Pattern, str, list[Span]]

#: Tier 1 decides, tier 2 narrows for a person, tier 3 enumerates.
type Tiers = tuple[list[Row], list[Row], list[Row]]

# The branches a finding of this check comes from.
SEARCHER = declare("self-application", "searcher", Level.UNRUN)
EMPTY = declare("self-application", "empty", Level.FAIL)
STALE_EXEMPTION = declare("self-application", "stale_exemption", Level.FAIL)
ORPHAN_EXEMPTION = declare("self-application", "orphan_exemption", Level.FAIL)
FILTERED_NO_ANSWER = declare("self-application", "filtered_no_answer", Level.FAIL)
FILTERED = declare("self-application", "filtered", Level.NOTE)
NO_ANSWER = declare("self-application", "no_answer", Level.FAIL)
DECIDES = declare("self-application", "decides", Level.FAIL)
NARROWS = declare("self-application", "narrows", Level.NOTE)
ENUMERATES = declare("self-application", "enumerates", Level.NOTE)
DRIFTED_STEP = declare("self-application", "drifted_step", Level.FAIL)


@check(
    "self-application",
    "the standard's own patterns over its own examples, and the repository's "
    "workflow over its standard's",
    needs=("rg",),
)
def selfapply(tree: Tree) -> Iterator[Finding]:
    """Each skill's own patterns, then the repository's workflows."""
    yield from own_patterns(tree)
    yield from _workflows(tree)


@per_skill
def own_patterns(skill: Skill) -> Iterator[Finding]:
    """The skill's own Check patterns, over the skill's own examples."""
    lang = skill.profile.languages[0] if skill.profile.languages else ""
    if not lang:
        return
    if problem := searcher_problem():
        yield unrun(problem, skill.at(), SEARCHER)
        return
    yield from _run(skill, lang)


def _run(skill: Skill, lang: str) -> Iterator[Finding]:
    profile = skill.profile
    corpus = corpus_for(skill, lang)
    rules = skill.chapter_rules
    if not corpus.blocks or not rules:
        yield fail(
            f"nothing to check: {corpus.blocks} blocks, {len(rules)} rules — "
            f"an empty corpus passes every pattern in the library",
            skill.at(),
            EMPTY,
        )
        return

    claimed: set[RuleId] = set()
    tiers: Tiers = ([], [], [])

    for rule in rules:
        check = check_text(rule)
        if not check:
            continue
        # An entry suppresses this rule's pattern, so it has to keep
        # quoting words the rule still says. Claimed before the
        # path-scoped branch below, or a `rg -v` rule with an entry
        # would look like a rule that vanished.
        if entry := profile.not_decisive.get(rule.id):
            claimed.add(rule.id)
            if entry.anchor not in " ".join(check.split()):
                yield fail(
                    f"{rule.id}: the exemption quotes {entry.anchor!r}, which its "
                    f"**Check:** no longer says",
                    skill.at(),
                    STALE_EXEMPTION,
                )
        if NEGATED.search(check):
            yield from _filtered(skill, corpus, rule, check)
            continue
        yield from _search(skill, corpus, rule, check, tiers)

    # Only this skill's own entries: an entry naming a rule the skill no
    # longer defines is a suppression standing over nothing.
    for rid in sorted(set(profile.not_decisive) - claimed):
        yield fail(
            f"{rid}: the exemption names a rule this skill does not define",
            skill.at(),
            ORPHAN_EXEMPTION,
        )

    yield from _report(skill, corpus, tiers)


def _filtered(
    skill: Skill, corpus: Corpus, rule: Rule, check: str
) -> Iterator[Finding]:
    """A Check that drops hits with `rg -v`, run as far as it can be.

    `rg … | rg -v '^src/lib.rs'` asks *which file* a hit is in, and an
    example block is a single crate root, so whether a hit survives is
    not decidable here. The rule used to be skipped whole and silently,
    patterns and all. What it searches for still runs, so a pattern
    `rg` rejects fails as any other does; what is left is said.
    """
    found, filters = filtered_of(check)
    hits: list[str] = []
    for pattern in found:
        lines, _ = find(corpus, pattern)
        if lines is None:
            yield fail(
                f"{rule.id}: the search gave no answer for its own Check pattern "
                f"/{pattern.text}/ — rejected, timed out, or not installed",
                skill.at(),
                FILTERED_NO_ANSWER,
            )
            continue
        hits.append(f"/{pattern.text}/ ({len(lines)} hit(s))")
    if hits:
        dropped = ", ".join(f"/{p.text}/" for p in filters) or "a second search"
        yield note(
            f"{rule.id}: ran {', '.join(hits)}, and its Check then drops hits with "
            f"`rg -v` {dropped}, which an example — one crate root — cannot "
            "answer; nothing here decides it",
            skill.at(),
            FILTERED,
        )


def _search(
    skill: Skill, corpus: Corpus, rule: Rule, check: str, tiers: Tiers
) -> Iterator[Finding]:
    """Run one rule's patterns, filing what survives into its tier."""
    profile = skill.profile
    for pattern in patterns_of(check):
        lines, used = find(corpus, pattern)
        if lines is None:
            yield fail(
                f"{rule.id}: the search gave no answer for its own Check pattern "
                f"/{pattern.text}/ — rejected, timed out, or not installed",
                skill.at(),
                NO_ANSWER,
            )
            continue
        exempt = profile.exempt.get(rule.id)
        source = corpus.lines_for(pattern)
        kept = [
            s
            for s in lines
            if not (exempt and excused(exempt, source, s.start - 1, corpus.in_test))
        ]
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
        yield fail(_render(corpus, row), skill.at(), DECIDES)
    for row in sorted(tier2, key=lambda r: -len(r[3])):
        entry = skill.profile.not_decisive.get(row[0].id)
        why = (
            entry.reason
            if entry
            else "prose span: the pattern narrows, a person decides"
        )
        yield note(_render(corpus, row, limit=3) + f"  ({why})", skill.at(), NARROWS)
    for row in sorted(tier3, key=lambda r: -len(r[3])):
        yield note(
            _render(corpus, row, limit=0) + "  (enumerates rather than accuses)",
            skill.at(),
            ENUMERATES,
        )


def _render(corpus: Corpus, row: Row, *, limit: int = 8) -> str:
    rule, pattern, used, hits = row
    head = f"{rule.id} {used} /{pattern.text}/ — {len(hits)} hit(s) — {rule.title}"
    for h in hits[:limit]:
        where, snippet = corpus.origin(h.start)
        across = f" (+{len(h) - 1} lines)" if len(h) > 1 else ""
        head += f"\n      {where}{across} {snippet}"
    if len(hits) > limit:
        head += f"\n      … {len(hits) - limit} more"
    return head


def _workflows(tree: Tree) -> Iterator[Finding]:
    """Each step a repository workflow shares with its standard's.

    The standard is the one the harness is written to, as its profile
    says, and its workflows are those it ships in `assets/`. Two steps
    are shared when `Step.identity` says they are one step; a shared
    step must use the same action at the same commit with the same
    `with:`, or run the same command, as one of the asset's does. So uv
    set up at another version, the interpreter installed at another
    release, or an action named at another commit, fails on the step
    that moved. A step the asset does not take is the repository's own
    and is not compared.
    """
    if not tree.skills or not in_repository(skills := tree.skills[0].root.parent):
        return
    standard = next((s for s in tree if s.profile.harness), None)
    if standard is None:
        return
    # Each step of the asset's, once for each way the asset takes it.
    asset: dict[str, list[Step]] = {}
    for path in workflow.shipped(standard.assets):
        for step in workflow.steps(path.read_text()):
            taken = asset.setdefault(step.identity, [])
            if all(step.held != other.held for other in taken):
                taken.append(step)
    root = root_of(skills)
    for path in workflow.run_by(root):
        rel = path.relative_to(root).as_posix()
        for step in workflow.steps(path.read_text()):
            taken = asset.get(step.identity, [])
            if taken and all(step.held != other.held for other in taken):
                theirs = " or ".join(other.stated for other in taken)
                yield fail(
                    f"{step.stated}, where {standard.name}'s workflow has {theirs}: "
                    "a step the two share is taken as the standard takes it",
                    Location(file=rel, line=step.line),
                    DRIFTED_STEP,
                )
