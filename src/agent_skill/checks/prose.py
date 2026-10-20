"""The text around the examples.

A standard states facts and cites sources. It does not narrate how it
was built: which machine ran a probe, on what date, how many times. A
reader cannot act on any of that, and the marker legend belongs in
`SKILL.md` once rather than restated in every chapter.
"""

import re
lazy from collections.abc import Iterator

from agent_skill.checks import check
from agent_skill.report import Finding, fail
lazy from agent_skill.model import Skill

PROVENANCE = [
    (
        r"on this (machine|install|toolchain)",
        "provenance about the machine it was written on",
    ),
    (
        r"[Vv]erified \d{4}-\d{2}-\d{2}",
        "dated as of a run; say which version it is about",
    ),
    (r"unverified on", "provenance about the machine it was written on"),
    (r"\btwice, two different ways\b", "how many times it was run"),
    (r"Blocks marked `// verified`", "the marker legend; SKILL.md states it once"),
    (
        r"marks a deliberately incomplete snippet",
        "the marker legend; SKILL.md states it once",
    ),
    (
        r"was (compiled and )?run against the local toolchain",
        "the marker legend; SKILL.md states it once",
    ),
    (
        r"were compiled against that toolchain",
        "the marker legend; SKILL.md states it once",
    ),
]

LEGEND = "carries a marker on its first line"

POSITIONAL = (
    r"({pre}-[A-Z]+-\d+[a-z]?,?\s+(below|above)\b"
    r"|\bthe rule (below|above)\b|\bsee (below|above)\b)"
)


@check("prose", "no build provenance, one legend, unbroken quotes")
def prose(skill: Skill) -> Iterator[Finding]:
    """Build provenance, broken quotes, and references by position."""
    for path in skill.markdown:
        text = path.read_text()
        tag = f"{skill.name}/{path.name}"
        yield from _provenance(text, tag)
        yield from _broken_quotes(text, tag)
        yield from _positional(text, tag, skill.prefix)

    seen = sum(path.read_text().count(LEGEND) for path in skill.markdown)
    if seen != 1:
        yield fail(
            f"the marker legend appears {seen} time(s); "
            "it belongs in SKILL.md exactly once",
            skill.name,
        )

    yield from skill.profile.prose(skill)


def _provenance(text: str, tag: str) -> Iterator[Finding]:
    """Each line that narrates how the standard was built."""
    for i, line in enumerate(text.split("\n"), 1):
        for pattern, why in PROVENANCE:
            if re.search(pattern, line):
                yield fail(why, f"{tag}:{i}")
                break  # one line, one finding


def _broken_quotes(text: str, tag: str) -> Iterator[Finding]:
    """Each blockquote continuation that lost its `>`.

    Such a line renders as a separate paragraph, and nothing else
    measures it.
    """
    quoted = False
    for i, line in enumerate(text.split("\n"), 1):
        if line.startswith(">"):
            quoted = True
        elif not line.strip():
            quoted = False
        elif quoted:
            yield fail("blockquote continuation lost its `>`", f"{tag}:{i}")
            quoted = False


def _positional(text: str, tag: str, prefix: str) -> Iterator[Finding]:
    """Each cross-reference by position rather than by ID.

    A cross-reference is an ID; `the rule below` breaks when a rule
    moves.
    """
    positional = re.compile(POSITIONAL.format(pre=prefix))
    for i, line in enumerate(text.split("\n"), 1):
        if positional.search(line):
            yield fail("positional cross-reference; cite the ID alone", f"{tag}:{i}")
