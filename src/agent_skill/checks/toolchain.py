"""The examples, compiled, run and mutated, by one driver.

`// verified` is a claim about a compiler, so a compiler is what settles
it. Extraction is also the only place that can tell "no defects" from
"no input": an empty crate builds, lints, tests and mutates clean.

A toolchain supplies data and the maps between markdown and files
(`lang.Toolchain`); this module is the only code that runs one. Each
toolchain used to loop over its own steps and mutants, and the loops
disagreed: a timeout was a failure in one and a pass in another, a
surviving mutant failed a Rust run and was a note in Python and Zig, a
Rust mutant was reported in the extracted file's lines, and each
language drew its mutants with a grammar of its own.
"""

import tempfile
from dataclasses import replace
from enum import Enum
from pathlib import Path
lazy from collections.abc import Iterator

from agent_skill.checks import check, per_skill
from agent_skill.checks.skeleton import gone_rows
from agent_skill.lang import (
    deletable,
    execute,
    first_error,
    judged,
    needs,
    toolchain_for,
)
from agent_skill.report import Finding, Level, declare, fail, note, unrun
lazy from agent_skill.lang import Extraction, Step, Toolchain, Unit
lazy from agent_skill.model import Skill

#: What every toolchain asks `have` for. Each declares it beside its
#: `missing`, because a toolchain's `tool` does not say it — Python's is
#: the interpreter, which is resolved through its venv rather than
#: `PATH`, and its `missing()` asks for `ty` and `ruff` as well.
TOOLCHAINS = needs(lambda tc: tc.needs)

# The branches of `toolchain`. One set for every toolchain, because one
# policy decides them.
MISSING = declare("toolchain", "missing", Level.UNRUN)
EMPTY = declare("toolchain", "empty", Level.FAIL)
OUTSIDE = declare("toolchain", "outside", Level.FAIL)
TIMEOUT = declare("toolchain", "timeout", Level.FAIL)
FAILED = declare("toolchain", "failed", Level.FAIL)
UNFORMATTED = declare("toolchain", "unformatted", Level.FAIL)

# The branches of a normalised standard's `gone` rows (decision 9).
GONE_LIVE = declare("toolchain", "gone_live", Level.FAIL)
GONE_UNPROBED = declare("toolchain", "gone_unprobed", Level.NOTE)

# The branches of `mutation`.
MUTATION_MISSING = declare("mutation", "missing", Level.UNRUN)
MUTATION_EMPTY = declare("mutation", "empty", Level.UNRUN)
UNMUTATED_TIMEOUT = declare("mutation", "unmutated_timeout", Level.FAIL)
UNMUTATED = declare("mutation", "unmutated", Level.FAIL)
INCONCLUSIVE = declare("mutation", "inconclusive", Level.NOTE)
SURVIVOR = declare("mutation", "survivor", Level.NOTE)


@check(
    "toolchain",
    "every // verified block compiles, and its tests run",
    slow=True,
    needs=TOOLCHAINS,
)
@per_skill
def toolchain(skill: Skill) -> Iterator[Finding]:
    """Compile every `// verified` block, and run the tests it ships."""
    tc = toolchain_for(skill.profile.toolchain)
    if tc is None:
        return
    absent = tc.missing()
    if absent:
        for what in absent:
            yield unrun(
                f"{what}, so nothing verified these examples", skill.at(), MISSING
            )
        return
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as work:
        if skill.profile.normalized:
            yield from gone(tc, skill, Path(work) / "gone")
        extraction = tc.extract(skill, Path(work) / "out")
        if not extraction:
            yield fail(
                "no `// verified` block was extracted — is the skill still there?",
                skill.at(),
                EMPTY,
            )
            return
        yield from verify(tc, extraction)


def gone(tc: Toolchain, skill: Skill, out: Path) -> Iterator[Finding]:
    """Each migration row marked `gone` the pinned release provides.

    A row says its old spelling no longer exists in the target; the
    toolchain looks it up there (`Toolchain.probe`), so a row naming a
    live API fails rather than sending a reader to rewrite working code.
    A spelling the toolchain cannot look up is noted, not passed: the
    row stands unverified, and the note says so.
    """
    out.mkdir(parents=True, exist_ok=True)
    for row, where in gone_rows(skill):
        spelling = row.spelling or ""
        step = tc.probe(skill, spelling, out)
        if step is None:
            yield note(
                f"`{spelling}` is marked gone, and {tc.name}'s probe cannot look it up "
                "in the pinned release, so nothing verified it",
                where,
                GONE_UNPROBED,
            )
            continue
        ran = execute(step)
        if ran.timed_out:
            yield fail(
                f"{step.name} did not finish in {step.timeout:g}s", where, TIMEOUT
            )
        elif ran.ok:
            found = ran.out.strip().split("\n")[0][:100]
            yield fail(
                f"`{spelling}` is marked gone, and the pinned release still provides it"
                + (f": {found}" if found else ""),
                where,
                GONE_LIVE,
            )
        elif ran.rc != 1:
            yield fail(
                f"{step.name} `{spelling}`: {first_error(ran)[:100]}", where, FAILED
            )


@check(
    "mutation",
    "a shipped test must be able to fail",
    slow=True,
    needs=TOOLCHAINS,
)
@per_skill
def mutation(skill: Skill) -> Iterator[Finding]:
    """Statements no shipped test notices being deleted."""
    tc = toolchain_for(skill.profile.toolchain)
    if tc is None:
        return
    # Its own finding, not a pointer at `toolchain`'s. A note here let
    # `--only mutation` report success having mutated nothing.
    absent = tc.missing()
    if absent:
        for what in absent:
            yield unrun(
                f"{what}, so no shipped test was mutated", skill.at(), MUTATION_MISSING
            )
        return
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as work:
        extraction = tc.extract(skill, Path(work) / "out")
        if not extraction:
            # `toolchain` fails the empty extraction; what this check
            # says is that it had nothing to mutate, which is not a
            # mutation run that found every test pinned.
            yield unrun(
                "no `// verified` block was extracted, so no shipped test was mutated",
                skill.at(),
                MUTATION_EMPTY,
            )
            return
        yield from mutate(tc, extraction)


def verify(tc: Toolchain, ex: Extraction) -> Iterator[Finding]:
    """Run each step of `tc` over `ex`, then its formatter.

    A unit's steps stop at its first failure, since a test of a block
    that does not build only reports that again; a step over the whole
    extraction always runs. A block that reaches outside the directory
    it runs in is refused before anything runs it.
    """
    stopped: set[Path] = set()
    for unit in ex.units:
        if tc.outside is not None and tc.outside.search(unit.block.body):
            stopped.add(unit.path)
            c = tc.language.comment
            yield fail(
                f"a `{c} verified` block may not need the network, the clock, "
                f"or stdin; mark it `{c} fragment`",
                unit.where,
                OUTSIDE,
            )
    for step in tc.steps(ex):
        if step.unit is not None and step.unit.path in stopped:
            continue
        found = judged(step, execute(step), ex, failed=FAILED, timeout=TIMEOUT)
        if found and step.unit is not None:
            stopped.add(step.unit.path)
        yield from found
    yield from _unformatted(tc, ex)


def _unformatted(tc: Toolchain, ex: Extraction) -> Iterator[Finding]:
    """Each block its formatter would rewrite.

    The formatter writes the extraction, and `restore` reads it back,
    so a block is judged exactly as `fmt` would rewrite it: at its own
    column, with nothing the extractor wrapped around it.
    """
    step = tc.formatter(ex)
    found = judged(step, execute(step), ex, failed=FAILED, timeout=TIMEOUT)
    if found:
        yield from found
        return
    restored = tc.restore(ex)
    for unit in ex.units:
        if restored[unit.block] != unit.block.body:
            yield fail(
                f"not `{step.name}` clean — `agent-skill fmt` rewrites it",
                unit.where,
                UNFORMATTED,
            )


class Verdict(Enum):
    """What the tests made of one mutant."""

    KILLED = "killed"
    SURVIVED = "survived"
    INCONCLUSIVE = "inconclusive"


def mutate(tc: Toolchain, ex: Extraction) -> Iterator[Finding]:
    """A shipped test must be able to fail.

    Every unit whose block ships a test has each line `deletable` picks
    deleted in turn, and its tests run. The unmutated tests run first,
    once for each command (a crate's tests are one run for all its
    units): a mutant of code whose tests already fail says nothing.

    A survivor is a note, in every language: an illustrative example's
    test pins the case its name describes, and a guard outside that
    case is expected to survive, so which survivor is a test that cannot
    fail is a reader's judgement (design.md, decision 6).
    """
    passed: dict[tuple[tuple[str, ...], Path], bool] = {}
    for unit in ex.units:
        if not tc.language.tests(unit.block.body):
            continue
        step = tc.tests(ex, unit)
        if step is None:
            continue
        key = (step.cmd, step.cwd)
        if key not in passed:
            unmutated = replace(step, name=f"the unmutated {step.name}")
            found = judged(
                unmutated,
                execute(unmutated),
                ex,
                failed=UNMUTATED,
                timeout=UNMUTATED_TIMEOUT,
            )
            passed[key] = not found
            yield from found
        if passed[key]:
            yield from _mutants(tc, unit, step)


def _mutants(tc: Toolchain, unit: Unit, step: Step) -> Iterator[Finding]:
    """Each line of `unit` whose deletion its tests do not notice."""
    original = unit.path.read_text()
    lines = original.split("\n")
    for i, statement in deletable(tc.language, unit.block.body):
        unit.path.write_text("\n".join(lines[:i] + lines[i + 1 :]))
        try:
            verdict = _verdict(step, tc.mutant_timeout)
        finally:
            unit.path.write_text(original)
        if verdict is Verdict.INCONCLUSIVE:
            yield note(
                f"`{statement[:44]}` timed out — inconclusive: hung, or slow",
                unit.where_at(i),
                INCONCLUSIVE,
            )
        elif verdict is Verdict.SURVIVED:
            yield note(
                f"`{statement[:52]}` can be deleted and every test still passes",
                unit.where_at(i),
                SURVIVOR,
            )


def _verdict(step: Step, timeout: float) -> Verdict:
    """Killed, survived, or neither: its tests did not finish.

    Deleting a loop increment turns a test into a hang, so a timeout is
    often the tests failing; but a busy machine times out too. Counted
    as killed, the run goes quiet under load and still reports clean.

    A survivor is run twice. Survivors are rare, so a second opinion is
    nearly free, and it is what stands between a transient — a build
    directory a killed run left half-written — and a reported survivor
    the example does not have.
    """
    for _ in range(2):
        ran = execute(step, timeout)
        if ran.timed_out:
            return Verdict.INCONCLUSIVE
        if not ran.ok:
            return Verdict.KILLED
    return Verdict.SURVIVED
