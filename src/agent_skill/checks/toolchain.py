"""The examples, compiled.

`// verified` is a claim about a compiler, so a compiler is what settles
it. Extraction is also the only place that can tell "no defects" from
"no input": an empty crate builds, lints, tests and mutates clean.
"""

import tempfile
from pathlib import Path
lazy from collections.abc import Iterator

from agent_skill.checks import check
from agent_skill.lang import toolchain_for
from agent_skill.report import Finding, fail, unrun
lazy from agent_skill.model import Skill

#: What the three toolchains ask `have` for: `cargo`, `zig`, and the
#: two tools beside the pinned Python. Declared rather than derived,
#: because a toolchain's `tool` does not say it — Python's is the
#: interpreter, which is resolved through its venv rather than `PATH`,
#: and its `missing()` asks for `ty` and `ruff` as well.
TOOLCHAINS = ("cargo", "zig", "ty", "ruff")


@check(
    "toolchain",
    "every // verified block compiles, and its tests run",
    slow=True,
    needs=TOOLCHAINS,
)
def toolchain(skill: Skill) -> Iterator[Finding]:
    """Compile every `// verified` block, and run the tests it ships."""
    tc = toolchain_for(skill.profile.toolchain)
    if tc is None:
        return
    absent = tc.missing()
    if absent:
        for what in absent:
            yield unrun(f"{what}, so nothing verified these examples", skill.name)
        return
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as work:
        extraction = tc.extract(skill, Path(work) / "out")
        if not extraction:
            yield fail(
                "no `// verified` block was extracted — is the skill still there?",
                skill.name,
            )
            return
        yield from tc.verify(extraction)


@check(
    "mutation",
    "a shipped test must be able to fail",
    slow=True,
    needs=TOOLCHAINS,
)
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
            yield unrun(f"{what}, so no shipped test was mutated", skill.name)
        return
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as work:
        extraction = tc.extract(skill, Path(work) / "out")
        if not extraction:
            # `toolchain` fails the empty extraction; what this check
            # says is that it had nothing to mutate, which is not a
            # mutation run that found every test pinned.
            yield unrun(
                "no `// verified` block was extracted, so no shipped test was mutated",
                skill.name,
            )
            return
        yield from tc.mutate(extraction)
