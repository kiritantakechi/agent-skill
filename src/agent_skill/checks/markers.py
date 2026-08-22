"""Every block declares what it is, exactly once, and the marker leads it.

Ran for one language only until a sweep found 56 blocks spelling the marker
across two lines (`// fragment` then `// BAD`), which left the tools unable to
recognise the illustration blocks they exist to exempt.
"""

from __future__ import annotations

import re

from ..model import MARKERS
from ..report import fail
from . import check

#: A verdict on its own line used to open a section inside a fence: rust spelled
#: the two halves `// bad` / `// good` in one block, zig spelled them `// BAD` /
#: `// GOOD`. Both are one fence per half now, so a verdict line that is not the
#: marker is a leftover.
STRAY_VERDICT = re.compile(r"^(?://|#) (GOOD|BAD)( —|:|$)", re.I)
LEADS = tuple(f"// {m}" for m in MARKERS) + tuple(f"# {m}" for m in MARKERS)


@check("markers", "one block, one marker, and the marker leads it")
def markers(skill):
    for lang in skill.profile.all_marked:
        for b in skill.blocks(lang):
            where = f"{skill.name}/{b.where}"
            if not b.marker.raw.startswith(LEADS):
                yield fail("no leading `verified` / `fragment` / `does-not-compile` marker", where)
            elif not b.marker.valid:
                yield fail(f"marker off-grammar: `{b.marker.raw[:60]}`", where)
            if b.marker.kind == "verified" and "fragment" in b.marker.raw:
                yield fail("marked both verified and fragment", where)
            for j, line in enumerate(b.lines):
                if line == b.marker.raw:
                    continue
                if line.startswith(LEADS) or STRAY_VERDICT.match(line):
                    yield fail(
                        f"a second marker line, `{line[:40]}` — one block, one marker",
                        f"{skill.name}/{b.file}:{b.at(j)} [{b.rule}]",
                    )
