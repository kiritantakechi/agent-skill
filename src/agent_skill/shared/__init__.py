"""The text every standard shares, kept once.

Four `SKILL.md` files carried the same reading procedure, tier table and
marker legend, and nothing kept them the same, so they were the same
only *nearly*: "several of its entries" in one and "most of its entries"
in the next, a closing line under the tier table in three of four, and
two orders for one table's columns. Each skill still carries its own
copy, because a skill is installed alone and must read completely
without its siblings. The copy is what the template says, filled in with
that skill's values, and `shared-text` fails when it is not.

A template is markdown. `{name}` is a short value the profile declares
or the skill's own parse supplies. A block that is only `…` is a free
region: the skill writes its own paragraphs there, and the comparison
skips them. Everything else must appear in order, and the template and
the copy are compared as the trees they parse to, so how a paragraph is
filled is never a finding but changing a word is.
"""

import difflib
import re
from dataclasses import dataclass
from pathlib import Path
lazy from collections.abc import Iterator

from agent_skill.doc import Block, Doc, Heading, Paragraph, printed
from agent_skill.report import Finding, Level, declare, fail, note
lazy from agent_skill.ids import Location
lazy from agent_skill.lang import language
lazy from agent_skill.model import Skill, located

HERE = Path(__file__).parent

#: A template block that is only `…`: a region the skill writes itself.
FREE = Paragraph(("…",))

#: The severity model every review protocol uses: label, then meaning.
#: The examples column is each standard's own.
SEVERITIES: tuple[tuple[str, str], ...] = (
    (
        "Unsound",
        "Corrupts memory or data, or crashes the runtime, from code that looks safe",
    ),
    (
        "Stale",
        (
            "A spelling the target superseded — fails to build, or worse, "
            "builds and means something else"
        ),
    ),
    ("Incorrect", "Produces wrong results or crashes on reachable input"),
    ("Contract", "Breaks or under-specifies the public surface"),
    ("Design", "Works, but the shape will cost later"),
    ("Performance", "Measurable, avoidable cost"),
    ("Style", "Idiom and readability"),
)

#: The H2s of a review protocol, in order.
REVIEW_SECTIONS: tuple[str, ...] = (
    "Severity model",
    "Review order",
    "Mechanical pass",
    "Output format",
    "Refactoring a codebase to this standard",
)

REVIEW = "references/review-checklist.md"

# The branches of `shared-text` that `compare` finds through, and of
# `fmt` that `rewrite` reports through.
MISSING = declare("shared-text", "missing", Level.FAIL)
DIFFERS = declare("shared-text", "differs", Level.FAIL)
STRAY = declare("shared-text", "stray", Level.FAIL)
FREE_REGION = declare("fmt", "free_region", Level.FAIL)
REWRITTEN = declare("fmt", "rewritten", Level.NOTE)

#: What every finding of `compare` ends with.
REWRITES = " — `agent-skill fmt` rewrites it"


@dataclass(frozen=True, slots=True)
class Passage:
    """One shared passage.

    Where it lives, and the template it is filled from.
    """

    document: str  #: path relative to the skill root
    section: str  #: the H2 it fills
    template: str  #: file under this package

    def text(self) -> str:
        """The template, read from this package."""
        return (HERE / self.template).read_text()


PASSAGES: tuple[Passage, ...] = (
    Passage("SKILL.md", "How to use this standard", "how-to-use.md"),
    Passage("SKILL.md", "1. Tiers", "tiers.md"),
    Passage("SKILL.md", "5. Review checklist", "review-checklist.md"),
    Passage("SKILL.md", "6. Reference map", "reference-map.md"),
    Passage("SKILL.md", "7. Bundled assets", "bundled-assets.md"),
    Passage(REVIEW, "Severity model", "severity.md"),
)


def major_minor(version: str) -> str:
    """The major.minor of `version`, or "" when it has none.

    `1.99` from `1.99`, `3.15` from `3.15.0rc1`, `0.20` from `0.20.0`.
    """
    m = re.match(r"\d+\.\d+", version)
    return m.group(0) if m else ""


def skill_sections(skill: Skill) -> tuple[str, ...]:
    """The H2s of a conforming `SKILL.md`, in order."""
    target = f"{skill.profile.language} {major_minor(skill.profile.release)}"
    return (
        "How to use this standard",
        "1. Tiers",
        f"2. {target} reality check",
        "3. Design principles",
        "4. Core rules",
        "5. Review checklist",
        "6. Reference map",
        "7. Bundled assets",
    )


def title(skill: Skill) -> str:
    """The H1 of a conforming `SKILL.md`."""
    return f"# {skill.profile.language} Style — {major_minor(skill.profile.release)}"


def slots(skill: Skill) -> dict[str, str]:
    """Every value a template may name, for one skill."""
    profile = skill.profile
    pin = profile.release
    toolchain = profile.toolchain
    comment = language(profile.languages[0] if profile.languages else "").comment
    return {
        "language": profile.language,
        "target": major_minor(pin),
        "prefix": profile.prefix,
        "comment": comment,
        "verified_as": profile.verified_as.format(
            pin=pin,
            toolchain=str(toolchain.pin.version.public) if toolchain else "",
        ),
        "tools": ", ".join(f"`{t}`" for t in profile.tools),
        "strict_scope": profile.strict_scope,
        "delta_step": f"9. {profile.delta_step}" if profile.delta_step else "",
        "core_count": str(len(skill.core_rules)),
        "chapter_count": str(len(skill.rules)),
    }


_SLOT = re.compile(r"\{([a-z_]+)\}")


def render(passage: Passage, values: dict[str, str]) -> tuple[Block, ...]:
    """The passage's blocks, filled in: fixed blocks, or `FREE`.

    A list an optional item was left out of has no gap to close: a
    list's numbers are printed from its start, not kept as written.
    """
    lines: list[str] = []
    for line in passage.text().split("\n"):
        # An empty slot on a line of its own leaves the line out.
        # Substituted first, it would leave a blank line, which ends the
        # list it was in.
        alone = re.fullmatch(r"\{([a-z_]+)\}", line.strip())
        if alone and not values.get(alone.group(1), ""):
            continue
        lines.append(_SLOT.sub(lambda m: values.get(m.group(1), m.group(0)), line))
    return Doc.parse("\n".join(lines)).blocks


def normal(block: str) -> str:
    """`block` with every run of whitespace collapsed to one space."""
    return " ".join(block.split())


def flat(block: Block) -> str:
    """`block` printed on one line, to quote it or measure a likeness.

    Never to compare: two blocks are the same when their trees are.
    """
    return normal("\n".join(printed(block)))


@dataclass(frozen=True, slots=True)
class Alignment:
    """Which actual block each fixed template block corresponds to."""

    template: tuple[Block, ...]
    actual: tuple[Block, ...]
    #: template index -> actual index, for fixed blocks that have a
    #: counterpart
    pairs: dict[int, int]

    def gaps(self) -> list[tuple[int, list[int]]]:
        """The unpaired actual blocks at each template position.

        A gap is keyed by the template index of the block that follows
        it, or by `len(template)` for the tail.
        """
        out: list[tuple[int, list[int]]] = []
        prev = -1
        anchors = sorted(self.pairs.items(), key=lambda kv: kv[1])
        for t, a in [*anchors, (len(self.template), len(self.actual))]:
            between = list(range(prev + 1, a))
            if between:
                out.append((t, between))
            prev = a
        return out

    def free_before(self, t: int) -> bool:
        """Is there a free region immediately before index `t`?

        In the template, with only unpaired blocks between the two.
        """
        k = t - 1
        while k >= 0 and k not in self.pairs and self.template[k] != FREE:
            k -= 1
        return k >= 0 and self.template[k] == FREE


#: The `difflib` ratio at or above which an edited block still counts as
#: the copy of a template block.
_ALIKE = 0.6


def align(template: tuple[Block, ...], actual: tuple[Block, ...]) -> Alignment:
    """Pair each fixed template block with its copy in `actual`.

    Equal trees first, in order. A block that was edited still has a
    counterpart — the closest unpaired block between its neighbours' —
    so a drifted sentence is reported as drifted rather than as missing
    beside some unexplained text, and `fmt` can put the template's
    version in its place.
    """
    pairs: dict[int, int] = {}
    cursor = 0
    for t, block in enumerate(template):
        if block == FREE:
            continue
        for a in range(cursor, len(actual)):
            if actual[a] == block:
                pairs[t] = a
                cursor = a + 1
                break
    for t, block in enumerate(template):
        if block == FREE or t in pairs:
            continue
        lo = max((a for k, a in pairs.items() if k < t), default=-1) + 1
        hi = min((a for k, a in pairs.items() if k > t), default=len(actual))
        scored = [
            (difflib.SequenceMatcher(None, flat(block), flat(actual[a])).ratio(), a)
            for a in range(lo, hi)
        ]
        best = max(scored, default=(0.0, -1))
        if best[0] >= _ALIKE:
            pairs[t] = best[1]
    return Alignment(template, actual, pairs)


def first_difference(want: Block, got: Block) -> str:
    """The first word where two blocks part, with a little context."""
    a, b = flat(want).split(), flat(got).split()
    i = next(
        (k for k, (x, y) in enumerate(zip(a, b, strict=False)) if x != y),
        min(len(a), len(b)),
    )
    return f"template has `{' '.join(a[i : i + 6])}`, found `{' '.join(b[i : i + 6])}`"


@dataclass(frozen=True, slots=True)
class Copy:
    """One passage as a skill carries it, aligned to its template."""

    skill: str
    passage: Passage
    path: Path
    doc: Doc
    #: the passage's blocks, as a range of `doc.blocks`
    span: tuple[int, int]
    alignment: Alignment

    def where(self, block: Block | None = None) -> Location:
        """The line `block` of the copy is on, or its heading's."""
        at = block or self.doc.blocks[self.span[0] - 1]
        return located(self.skill, self.passage.document, at.line or None)


def _span(doc: Doc, heading: str) -> tuple[int, int] | None:
    """The blocks under the H2 `heading`, up to the next H2 or H1.

    None when `doc` has no such heading.
    """
    blocks = doc.blocks
    title = Heading(2, heading)
    start = next((i + 1 for i, b in enumerate(blocks) if b == title), None)
    if start is None:
        return None
    end = next(
        (
            i
            for i in range(start, len(blocks))
            if isinstance(b := blocks[i], Heading) and b.level <= title.level
        ),
        len(blocks),
    )
    return start, end


def copies(skill: Skill) -> Iterator[Copy]:
    """Every shared passage the skill carries, aligned.

    A missing section is skipped: the skeleton check owns the shape, and
    reporting it twice is one defect as two. Each file is read when its
    passage is reached, so a passage rewritten before it is seen as
    written.
    """
    values = slots(skill)
    for passage in PASSAGES:
        path = skill.root / passage.document
        if not path.is_file():
            continue
        doc = Doc.parse(path.read_text())
        span = _span(doc, passage.section)
        if span is None:
            continue
        actual = doc.blocks[span[0] : span[1]]
        aligned = align(render(passage, values), actual)
        yield Copy(skill.name, passage, path, doc, span, aligned)


def compare(skill: Skill) -> Iterator[Finding]:
    """Every way a skill's copies differ from the template."""
    for copy in copies(skill):
        al = copy.alignment
        for t, block in enumerate(al.template):
            if block == FREE:
                continue
            a = al.pairs.get(t)
            if a is None:
                yield fail(
                    f"missing shared text: `{flat(block)[:70]}`{REWRITES}",
                    copy.where(),
                    MISSING,
                )
            elif al.actual[a] != block:
                differs = first_difference(block, al.actual[a])
                yield fail(
                    f"differs from the shared template — {differs}{REWRITES}",
                    copy.where(al.actual[a]),
                    DIFFERS,
                )
        for t, extra in al.gaps():
            if not al.free_before(t):
                stray = al.actual[extra[0]]
                yield fail(
                    f"text the template has no place for: `{flat(stray)[:70]}`"
                    f"{REWRITES}",
                    copy.where(stray),
                    STRAY,
                )


def rewrite(skill: Skill) -> list[Finding]:
    """Rewrite every copy from the template.

    What the skill wrote in the free regions is kept. A section with
    text outside any free region is left alone and reported as a
    failure: the rewrite would have to drop that text or guess where it
    goes, and neither is a formatter's decision. Each copy rewritten is
    a note, and the file it is in is printed in its canonical form.
    """
    changed: list[Finding] = []
    for copy in copies(skill):
        al = copy.alignment
        where = copy.where()
        if any(not al.free_before(t) for t, _ in al.gaps()):
            changed.append(
                fail("text outside a free region; not rewritten", where, FREE_REGION)
            )
            continue
        gaps = dict(al.gaps())
        out: list[Block] = []
        for t, block in enumerate(al.template):
            if block != FREE:
                out.append(block)
                continue
            owner = min((k for k in gaps if k > t), default=None)
            if owner is not None:
                out.extend(al.actual[a] for a in gaps.pop(owner))
        doc, (start, end) = copy.doc, copy.span
        new = Doc(doc.frontmatter, (*doc.blocks[:start], *out, *doc.blocks[end:]))
        if new != doc:
            copy.path.write_text(str(new))
            changed.append(note("rewritten from the template", where, REWRITTEN))
    return changed
