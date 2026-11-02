"""Every block declares what it is exactly once, led by its marker.

Ran for one language only until a sweep found 56 blocks spelling the
marker across two lines (`// fragment` then `// BAD`), which left the
tools unable to recognise the illustration blocks they exist to exempt.
"""

import re
lazy from collections.abc import Iterator

from agent_skill.checks import check, per_skill
from agent_skill.model import MARKERS
from agent_skill.report import Finding, Level, declare, fail
lazy from agent_skill.model import Block, Skill

#: A verdict on its own line used to open a section inside a fence: rust
#: spelled the two halves `// bad` / `// good` in one block, zig spelled
#: them `// BAD` / `// GOOD`. Both are one fence per half now, so a
#: verdict line that is not the marker is a leftover.
STRAY_VERDICT = re.compile(r"^(?://|#) (GOOD|BAD)( —|:|$)", re.IGNORECASE)

# The branches a finding of this check comes from.
NO_MARKER = declare("markers", "no_marker", Level.FAIL)
OFF_GRAMMAR = declare("markers", "off_grammar", Level.FAIL)
UNKNOWN_KIND = declare("markers", "unknown_kind", Level.FAIL)
VERIFIED_FRAGMENT = declare("markers", "verified_fragment", Level.FAIL)
REJECTED_TOOL = declare("markers", "rejected_tool", Level.FAIL)
SECOND_MARKER = declare("markers", "second_marker", Level.FAIL)


def _leads(words: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(f"// {m}" for m in words) + tuple(f"# {m}" for m in words)


@check("markers", "one block, one marker, and the marker leads it")
@per_skill
def markers(skill: Skill) -> Iterator[Finding]:
    """Every block's marker, held to its profile's marker grammar."""
    leads = _leads(MARKERS)
    named = " / ".join(f"`{w}`" for w in MARKERS)
    for lang in skill.profile.all_marked:
        for b in skill.blocks(lang):
            yield from _leading(b, skill, leads, named)
            yield from _second(b, leads)


def _leading(
    b: Block, skill: Skill, leads: tuple[str, ...], named: str
) -> Iterator[Finding]:
    """What is wrong with the marker that opens `b`."""
    where = b.where
    if not b.marker.raw.startswith(leads):
        yield fail(f"no leading {named} marker", where, NO_MARKER)
    elif not b.marker.valid:
        yield fail(f"marker off-grammar: `{b.marker.raw[:60]}`", where, OFF_GRAMMAR)
    elif b.marker.kind not in MARKERS:
        # The grammar is deliberately loose; this is where the
        # word is judged.
        yield fail(
            f"marker `{b.marker.kind}` is not one of {named}", where, UNKNOWN_KIND
        )
    if b.marker.kind == "verified" and "fragment" in b.marker.raw:
        yield fail("marked both verified and fragment", where, VERIFIED_FRAGMENT)
    if b.marker.kind == "rejected" and b.marker.tool not in skill.profile.tools:
        tools = " / ".join(f"`{t}`" for t in skill.profile.tools) or "no tool"
        yield fail(
            f"`rejected` must name the tool that rejects it — "
            f"`rejected — <tool>: …`, one of {tools}",
            where,
            REJECTED_TOOL,
        )


def _second(b: Block, leads: tuple[str, ...]) -> Iterator[Finding]:
    """Every line in `b`, besides its marker, that reads as one."""
    for j, line in enumerate(b.lines):
        if line == b.marker.raw:
            continue
        if line.startswith(leads) or STRAY_VERDICT.match(line):
            yield fail(
                f"a second marker line, `{line[:40]}` — one block, one marker",
                b.where_at(j),
                SECOND_MARKER,
            )
