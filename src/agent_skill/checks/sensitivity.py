"""Each authored pattern, shown to catch its defect, or listed unproven.

`self-application` proves **specificity**: a deciding pattern must not
fire on the standard's own compliant examples, so tier 1 is required to
be empty. Nothing proved **sensitivity**. A pattern that matches nothing
anywhere passes that test perfectly, and in a report it is
indistinguishable from a pattern that ran and correctly found the code
clean.

So a rule may declare snippets containing its own defect, and its
patterns are asserted to hit them. Declared per rule rather than
derived, because what counts as the defect is the rule's claim and not
something the harness can infer.

**Every** pattern, which is what the title says and what the code did
not do. It asserted `any`, so one pattern matching stood as evidence for
the rest: measured, `ZS-MIG-12` ships four patterns over four disjoint
families of dead API and its one fixture matched the first, leaving
three counted as proven by a snippet none of them touched. Any of those
three could have been narrowed until it matched nothing at all and this
check would have kept reporting the rule covered.

The cover is asserted in both directions — every pattern hits some
fixture, and every fixture is hit by some pattern. The second is what
keeps the first honest: without it, an uncovered pattern is "fixed" by
adding a snippet nobody has related to the rule, which proves the
snippet.

A rule with no fixture was skipped, and said nothing — so the check
read as proving every shipped pattern while most of them had no fixture
at all. That gap is now stated per profile, in `unproven`, and held
both ways: a rule that ships a pattern is proven or listed, and an entry
that stopped being true fails.
"""

lazy from collections.abc import Iterator

from agent_skill.checks import check, per_skill
from agent_skill.checks.patterns import check_text, patterns_of
from agent_skill.checks.search import matches, searcher_problem
from agent_skill.report import Level, declare, fail, unrun
lazy from agent_skill.checks.patterns import Pattern
lazy from agent_skill.doc.chapter import Rule
lazy from agent_skill.model import Skill
lazy from agent_skill.report import Finding

# The branches a finding of this check comes from.
SEARCHER = declare("sensitivity", "searcher", Level.UNRUN)
ORPHAN_FIXTURE = declare("sensitivity", "orphan_fixture", Level.FAIL)
UNACCOUNTED = declare("sensitivity", "unaccounted", Level.FAIL)
STALE_UNPROVEN = declare("sensitivity", "stale_unproven", Level.FAIL)
NO_CHECK = declare("sensitivity", "no_check", Level.FAIL)
NO_COMMAND = declare("sensitivity", "no_command", Level.FAIL)
NO_ANSWER = declare("sensitivity", "no_answer", Level.FAIL)
PATTERN_UNCOVERED = declare("sensitivity", "pattern_uncovered", Level.FAIL)
FIXTURE_UNCOVERED = declare("sensitivity", "fixture_uncovered", Level.FAIL)


@check(
    "sensitivity",
    "an authored pattern is shown to catch what it was written for",
    needs=("rg",),
)
@per_skill
def sensitivity(skill: Skill) -> Iterator[Finding]:
    """Each rule's patterns against its fixtures, as a two-way cover.

    And every rule that ships a pattern either has fixtures or is
    listed as unproven: a rule with neither used to be skipped without
    a word, which is how most shipped patterns went unproven while this
    check read as covering all of them.
    """
    yield from _accounted(skill)
    declared = skill.profile.fires
    if not declared:
        return
    if problem := searcher_problem():
        yield unrun(problem, skill.at(), SEARCHER)
        return
    # `tests/test_profiles.py` holds a profile with fixtures to naming
    # the language they are prepared as, as the corpus they stand in for
    # is.
    lang = skill.profile.languages[0]

    by_id = {r.id: r for r in skill.chapter_rules}
    for rid in sorted(set(declared) - set(by_id)):
        yield fail(
            f"{rid}: a fixture names a rule this skill does not define",
            skill.at(),
            ORPHAN_FIXTURE,
        )

    for rid, fixtures in sorted(declared.items()):
        rule = by_id.get(rid)
        if rule is None:
            continue
        yield from _fixtures(skill, rule, fixtures, lang)


def _accounted(skill: Skill) -> Iterator[Finding]:
    """Each rule that ships a pattern is proven, or listed as not yet.

    Both directions, as the cover is: a rule neither proven nor listed
    fails, and so does an entry that has stopped being true — a rule
    gone, a rule that no longer ships a pattern, or one that has a
    fixture now. Without the second, the list would only ever grow.
    """
    profile = skill.profile
    by_id = {rule.id: rule for rule in skill.chapter_rules}
    shipping = {
        rid
        for rid, rule in by_id.items()
        if any(p.kind == "command" for p in patterns_of(check_text(rule)))
    }
    for rid in sorted(shipping - set(profile.fires) - profile.unproven):
        yield fail(
            f"{rid}: ships an `rg` pattern that no fixture proves and `unproven` "
            f"does not list — give it a fixture in `fires`, or say it is unproven "
            f"— {by_id[rid].title}",
            skill.at(),
            UNACCOUNTED,
        )
    for rid in sorted(profile.unproven):
        if rid not in by_id:
            stale = "names a rule this skill does not define"
        elif rid in profile.fires:
            stale = "has a fixture in `fires` now"
        elif rid not in shipping:
            stale = "ships no `rg` pattern, so nothing of it is left to prove"
        else:
            continue
        yield fail(
            f"{rid}: listed as unproven, and {stale}", skill.at(), STALE_UNPROVEN
        )


def _fixtures(
    skill: Skill, rule: Rule, fixtures: tuple[str, ...], lang: str
) -> Iterator[Finding]:
    """One rule's fixtures, against the commands its Check ships."""
    rid = rule.id
    check = check_text(rule)
    if not check:
        yield fail(
            f"{rid}: has a fixture but no **Check:** to run against it",
            skill.at(),
            NO_CHECK,
        )
        return
    runnable = [p for p in patterns_of(check) if p.kind == "command"]
    if not runnable:
        yield fail(
            f"{rid}: has a fixture but its **Check:** ships no command — a fixture "
            "with nothing to run against it proves nothing",
            skill.at(),
            NO_COMMAND,
        )
        return
    yield from _cover(skill, rule, runnable, fixtures, lang)


def _cover(
    skill: Skill,
    rule: Rule,
    runnable: list[Pattern],
    fixtures: tuple[str, ...],
    lang: str,
) -> Iterator[Finding]:
    """Every pattern hits a fixture, and every fixture a pattern."""
    rid = rule.id
    # A grid rather than a list: one row per pattern, one column per
    # fixture, so both directions of the cover are read off the same
    # answers.
    grid = [[matches(fixture, p, lang) for fixture in fixtures] for p in runnable]
    if any(a is None for row in grid for a in row):
        yield fail(
            f"{rid}: a pattern gave no answer against its own fixture — rejected, "
            "timed out, or the searcher is missing",
            skill.at(),
            NO_ANSWER,
        )
        return

    for pattern, row in zip(runnable, grid, strict=True):
        if not any(row):
            yield fail(
                f"{rid}: /{pattern.text}/ matches none of this rule's fixtures, so "
                f"nothing shows it can catch anything — {rule.title}",
                skill.at(),
                PATTERN_UNCOVERED,
            )
    for i, fixture in enumerate(fixtures):
        if not any(row[i] for row in grid):
            yield fail(
                f"{rid}: the fixture {fixture.strip()[:60]!r} is matched by none of "
                "this rule's patterns — a fixture nothing relates to the rule is how "
                "an uncovered pattern gets covered without being fixed",
                skill.at(),
                FIXTURE_UNCOVERED,
            )
