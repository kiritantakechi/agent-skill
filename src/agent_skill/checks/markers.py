"""Every block declares what it is, exactly once, and the marker leads it.

Ran for one language only until a sweep found 56 blocks spelling the marker
across two lines (`// fragment` then `// BAD`), which left the tools unable to
recognise the illustration blocks they exist to exempt.
"""

from __future__ import annotations

import re

from ..report import fail
from . import check

#: A verdict on its own line used to open a section inside a fence: rust spelled
#: the two halves `// bad` / `// good` in one block, zig spelled them `// BAD` /
#: `// GOOD`. Both are one fence per half now, so a verdict line that is not the
#: marker is a leftover.
STRAY_VERDICT = re.compile(r"^(?://|#) (GOOD|BAD)( —|:|$)", re.I)


def _leads(words: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(f"// {m}" for m in words) + tuple(f"# {m}" for m in words)


@check("markers", "one block, one marker, and the marker leads it")
def markers(skill):
    words = skill.profile.markers
    leads = _leads(words)
    named = " / ".join(f"`{w}`" for w in words)
    for lang in skill.profile.all_marked:
        for b in skill.blocks(lang):
            where = f"{skill.name}/{b.where}"
            if not b.marker.raw.startswith(leads):
                yield fail(f"no leading {named} marker", where)
            elif not b.marker.valid:
                yield fail(f"marker off-grammar: `{b.marker.raw[:60]}`", where)
            elif b.marker.kind not in words:
                # The grammar is deliberately loose; this is where the word is judged.
                yield fail(f"marker `{b.marker.kind}` is not one of {named}", where)
            if b.marker.kind == "verified" and "fragment" in b.marker.raw:
                yield fail("marked both verified and fragment", where)
            for j, line in enumerate(b.lines):
                if line == b.marker.raw:
                    continue
                if line.startswith(leads) or STRAY_VERDICT.match(line):
                    yield fail(
                        f"a second marker line, `{line[:40]}` — one block, one marker",
                        f"{skill.name}/{b.file}:{b.at(j)} [{b.rule}]",
                    )
