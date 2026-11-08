"""The text around the examples.

A standard states facts and cites sources. It does not narrate how it
was built: which machine ran a probe, on what date, how many times. A
reader cannot act on any of that, and the marker legend belongs in
`SKILL.md` once rather than restated in every chapter.
"""

import re
from functools import partial
lazy from collections.abc import Callable, Iterator

from agent_skill.checks import check, per_skill
from agent_skill.checks.lines import prose as own_rules
from agent_skill.doc import Fence, ListBlock, Quote, Table, text_of, walk
from agent_skill.doc.chapter import citing, migration_header
from agent_skill.ids import cited_at
from agent_skill.report import Finding, Level, declare, fail
lazy from agent_skill.checks.skeleton import target
lazy from agent_skill.doc import Doc
lazy from agent_skill.ids import Location
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

#: What follows a rule ID that points by position: `RS-ERR-03 below`.
AFTER_ID = re.compile(r",?\s+(below|above)\b")

#: A reference by position that names no ID at all.
POSITIONAL = re.compile(r"\bthe rule (below|above)\b|\bsee (below|above)\b")

#: A line of the file a finding is about, as its location.
type At = Callable[[int], Location]

# The branches a finding of this check comes from. Each profile declares
# those of its own prose rules.
PROVENANCE_LINE = declare("prose", "provenance", Level.FAIL)
BROKEN_QUOTE = declare("prose", "broken_quote", Level.FAIL)
POSITIONAL_REFERENCE = declare("prose", "positional", Level.FAIL)
LEGEND_COUNT = declare("prose", "legend", Level.FAIL)

# The branch of dated statements (normalize-the-standards, decision 13).
DATED = declare("prose", "dated", Level.FAIL)

#: Words that date a statement by its writing, or say how it was made:
#: true when written, and silently false a release later.
DATING = re.compile(
    r"\b(?:currently|not yet|as of|compiled against|measured)\b", re.IGNORECASE
)

#: A date, as prose writes one: `2026-09-01`, `September 2026`.
DATE = re.compile(
    r"\b\d{4}-\d{2}(?:-\d{2})?\b|\b(?:January|February|March|April|May|June|July|"
    r"August|September|October|November|December)\s+\d{4}\b"
)

#: An inline code span, which is content rather than prose.
_SPAN = re.compile(r"(`+)[^`\n]*?\1")


@check("prose", "no build provenance, one legend, unbroken quotes")
@per_skill
def prose(skill: Skill) -> Iterator[Finding]:
    """Build provenance, broken quotes, and references by position."""
    for path, doc in skill.docs.items():
        text = path.read_text()
        at = partial(skill.at, path)
        yield from _provenance(text, at)
        yield from _broken_quotes(doc, at)
        yield from _positional(text, at, skill.prefix)

    seen = sum(path.read_text().count(LEGEND) for path in skill.markdown)
    if seen != 1:
        yield fail(
            f"the marker legend appears {seen} time(s); "
            "it belongs in SKILL.md exactly once",
            skill.at(),
            LEGEND_COUNT,
        )

    yield from own_rules(skill)
    yield from dated(skill)


def dated(skill: Skill) -> Iterator[Finding]:
    """Each statement dated by its writing (decision 13).

    "currently", "not yet", "as of", "compiled against", "measured", or
    a date: what was true when the line was written and is false a
    release later, with nothing to say so. A date belongs to the
    migration table, which keys what changed by release; an example is
    code, and a rename table history.
    """
    migration = migration_header(target(skill))
    for path, doc in skill.docs.items():
        for top in citing(doc):
            for block in walk((top,)):
                if isinstance(block, (Fence, ListBlock, Quote)):
                    continue  # code; or blocks walked on their own
                text = _SPAN.sub(" ", text_of((block,)))
                found = DATING.search(text)
                keyed = isinstance(block, Table) and block.header == migration
                if found is None and not keyed:
                    found = DATE.search(text)
                if found is not None:
                    line = block.line + text.count("\n", 0, found.start())
                    yield fail(
                        f"`{found.group(0)}` dates the statement by its writing; say "
                        "what holds of the target, or put the date in the migration "
                        "table",
                        skill.at(path, line),
                        DATED,
                    )


def _provenance(text: str, at: At) -> Iterator[Finding]:
    """Each line that narrates how the standard was built."""
    for i, line in enumerate(text.split("\n"), 1):
        for pattern, why in PROVENANCE:
            if re.search(pattern, line):
                yield fail(why, at(i), PROVENANCE_LINE)
                break  # one line, one finding


def _broken_quotes(doc: Doc, at: At) -> Iterator[Finding]:
    """Each blockquote continuation that lost its `>`.

    Whether a renderer reads such a line into the quote or out of it
    differs between renderers, and the parser records it on the quote
    it follows (`Quote.lazy`). Read from the tree, a `>` line inside an
    example is code, not a quote.
    """
    for quote in walk(doc.blocks):
        if isinstance(quote, Quote) and quote.lazy is not None:
            yield fail(
                "blockquote continuation lost its `>`", at(quote.lazy), BROKEN_QUOTE
            )


def _positional(text: str, at: At, prefix: str) -> Iterator[Finding]:
    """Each cross-reference by position rather than by ID.

    A cross-reference is an ID; `the rule below` breaks when a rule
    moves.
    """
    for i, line in enumerate(text.split("\n"), 1):
        if POSITIONAL.search(line) or any(
            AFTER_ID.match(line, end) for _, end in cited_at(line, prefix)
        ):
            yield fail(
                "positional cross-reference; cite the ID alone",
                at(i),
                POSITIONAL_REFERENCE,
            )
