"""The examples, compiled.

`// verified` is a claim about a compiler, so a compiler is what settles it.
Extraction is also the only place that can tell "no defects" from "no input": an
empty crate builds, lints, tests and mutates clean.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from ..lang import toolchain_for
from ..proc import have
from ..report import fail, note
from . import check


@check("toolchain", "every // verified block compiles, and its tests run", slow=True)
def toolchain(skill):
    tc = toolchain_for(skill.profile.toolchain)
    if tc is None:
        return
    if not have(tc.tool):
        yield fail(f"`{tc.tool}` is not on PATH, so nothing verified these examples", skill.name)
        return
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as work:
        extraction = tc.extract(skill, Path(work) / "out")
        if not extraction:
            yield fail(
                "no `// verified` block was extracted — is the skill still there?", skill.name
            )
            return
        yield from tc.verify(extraction)


@check("mutation", "a shipped test must be able to fail", slow=True)
def mutation(skill):
    tc = toolchain_for(skill.profile.toolchain)
    if tc is None:
        return
    if not have(tc.tool):
        yield note(f"`{tc.tool}` is not on PATH; the toolchain check says so", skill.name)
        return
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as work:
        extraction = tc.extract(skill, Path(work) / "out")
        if extraction:
            yield from tc.mutate(extraction)
