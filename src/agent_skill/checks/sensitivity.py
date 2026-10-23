"""Every authored pattern, shown to catch the defect it was written for.

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
"""

lazy from collections.abc import Iterator

from agent_skill.checks import check
from agent_skill.checks.patterns import patterns_of
from agent_skill.checks.search import matches, searcher_problem
from agent_skill.report import fail, unrun
lazy from agent_skill.checks.patterns import Pattern
lazy from agent_skill.model import Rule, Skill
lazy from agent_skill.report import Finding


@check(
    "sensitivity",
    "an authored pattern is shown to catch what it was written for",
    needs=("rg",),
)
def sensitivity(skill: Skill) -> Iterator[Finding]:
    """Each rule's patterns against its fixtures, as a two-way cover."""
    declared = skill.profile.fires
    if not declared:
        return
    if problem := searcher_problem():
        yield unrun(problem, skill.name)
        return
    if not skill.profile.languages:
        yield fail(
            f"{skill.name} declares fixtures but no language, so a fixture cannot "
            "be prepared the way the corpus it stands in for is",
            skill.name,
        )
        return
    lang = skill.profile.languages[0]

    by_id = {r.id: r for r in skill.rules}
    for rid in sorted(set(declared) - set(by_id)):
        yield fail(
            f"{rid}: a fixture names a rule this skill does not define", skill.name
        )

    for rid, fixtures in sorted(declared.items()):
        rule = by_id.get(rid)
        if rule is None:
            continue
        yield from _fixtures(skill, rule, fixtures, lang)


def _fixtures(
    skill: Skill, rule: Rule, fixtures: tuple[str, ...], lang: str
) -> Iterator[Finding]:
    """One rule's fixtures, against the commands its Check ships."""
    rid = rule.id
    if not fixtures:
        yield fail(f"{rid}: is listed with no fixture at all", skill.name)
        return
    if not rule.check:
        yield fail(
            f"{rid}: has a fixture but no **Check:** to run against it", skill.name
        )
        return
    runnable = [p for p in patterns_of(rule.check) if p.kind == "command"]
    if not runnable:
        yield fail(
            f"{rid}: has a fixture but its **Check:** ships no command — a fixture "
            "with nothing to run against it proves nothing",
            skill.name,
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
            skill.name,
        )
        return

    for pattern, row in zip(runnable, grid, strict=True):
        if not any(row):
            yield fail(
                f"{rid}: /{pattern.text}/ matches none of this rule's fixtures, so "
                f"nothing shows it can catch anything — {rule.title}",
                skill.name,
            )
    for i, fixture in enumerate(fixtures):
        if not any(row[i] for row in grid):
            yield fail(
                f"{rid}: the fixture {fixture.strip()[:60]!r} is matched by none of "
                "this rule's patterns — a fixture nothing relates to the rule is how "
                "an uncovered pattern gets covered without being fixed",
                skill.name,
            )
