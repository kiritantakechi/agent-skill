"""The examples, compiled.

`// verified` is a claim about a compiler, so a compiler is what settles it.
Extraction is also the only place that can tell "no defects" from "no input": an
empty crate builds, lints, tests and mutates clean.
"""

import tempfile
from pathlib import Path

from agent_skill.checks import check
from agent_skill.lang import toolchain_for
from agent_skill.report import fail, note, unrun


@check("toolchain", "every // verified block compiles, and its tests run", slow=True)
def toolchain(skill):
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


@check("mutation", "a shipped test must be able to fail", slow=True)
def mutation(skill):
    tc = toolchain_for(skill.profile.toolchain)
    if tc is None:
        return
    if tc.missing():
        yield note("the toolchain check already says what is absent", skill.name)
        return
    # `Toolchain` is a Protocol, so nothing enforces `mutate` at runtime and a
    # toolchain without it raised `AttributeError` inside a check with no `try` —
    # aborting the whole run rather than reporting one gap.
    mutate = getattr(tc, "mutate", None)
    if mutate is None:
        yield unrun(
            f"the {tc.name} toolchain cannot mutate, so no test was pinned", skill.name
        )
        return
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as work:
        extraction = tc.extract(skill, Path(work) / "out")
        if extraction:
            yield from mutate(extraction)
