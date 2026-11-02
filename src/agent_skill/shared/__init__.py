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
skips them. Everything else must appear verbatim and in order, compared
with whitespace collapsed, so re-wrapping a paragraph is never a finding
but changing a word is.
"""

import difflib
import re
import textwrap
from dataclasses import dataclass
from pathlib import Path
lazy from collections.abc import Iterator

from agent_skill.doc import WIDTH
from agent_skill.report import Finding, fail, note
from agent_skill.text import syntax_for
lazy from agent_skill.model import Skill

HERE = Path(__file__).parent

FREE = "…"

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
    target = f"{skill.profile.language} {major_minor(skill.profile.pin())}"
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
    return f"# {skill.profile.language} Style — {major_minor(skill.profile.pin())}"


def slots(skill: Skill) -> dict[str, str]:
    """Every value a template may name, for one skill."""
    profile = skill.profile
    crate = profile.crate
    pin = profile.pin()
    comment = syntax_for(profile.languages[0] if profile.languages else "")[0]
    return {
        "language": profile.language,
        "target": major_minor(pin),
        "prefix": profile.prefix,
        "comment": comment,
        "verified_as": profile.verified_as.format(
            pin=pin, rust=crate.rust_version if crate else ""
        ),
        "tools": ", ".join(f"`{t}`" for t in profile.tools),
        "strict_scope": profile.strict_scope,
        "delta_step": f"9. {profile.delta_step}" if profile.delta_step else "",
        "core_count": str(len(skill.core_rules)),
        "chapter_count": str(len(skill.rules)),
    }


_SLOT = re.compile(r"\{([a-z_]+)\}")
_ITEM = re.compile(r"^(\d+)\. ", re.MULTILINE)


def render(passage: Passage, values: dict[str, str]) -> list[str]:
    """The passage's blocks, filled in: fixed text, or `FREE`."""
    lines: list[str] = []
    for line in passage.text().split("\n"):
        # An empty slot on a line of its own leaves the line out.
        # Substituted first, it would leave a blank line, which ends the
        # list it was in.
        alone = re.fullmatch(r"\{([a-z_]+)\}", line.strip())
        if alone and not values.get(alone.group(1), ""):
            continue
        lines.append(_SLOT.sub(lambda m: values.get(m.group(1), m.group(0)), line))
    return [_renumber(b) for b in blocks("\n".join(lines))]


def _renumber(block: str) -> str:
    """Number a list's items consecutively from 1.

    1, 2, 3 …, so an optional item that was left out leaves no gap.
    """
    if not _ITEM.match(block):
        return block
    count = iter(range(1, 1000))
    return _ITEM.sub(lambda _: f"{next(count)}. ", block)


def blocks(text: str) -> list[str]:
    """Blank-line-separated blocks, never splitting a fenced example."""
    out: list[str] = []
    current: list[str] = []
    fenced = False
    for line in text.split("\n"):
        if line.startswith("```"):
            fenced = not fenced
        if not fenced and not line.strip():
            if current:
                out.append("\n".join(current))
                current = []
            continue
        current.append(line)
    if current:
        out.append("\n".join(current))
    return out


def normal(block: str) -> str:
    """`block` with every run of whitespace collapsed to one space."""
    return " ".join(block.split())


def section(text: str, heading: str) -> tuple[int, int] | None:
    """The line span of an H2's body.

    It runs from after its heading up to the next H2. None when `text`
    has no such heading.
    """
    lines = text.split("\n")
    fenced = False
    start: int | None = None
    for i, line in enumerate(lines):
        if line.startswith("```"):
            fenced = not fenced
        if fenced or not line.startswith("## "):
            continue
        if start is not None:
            return start, i
        if line == f"## {heading}":
            start = i + 1
    return (start, len(lines)) if start is not None else None


def h2s(text: str) -> list[str]:
    """Every H2 title outside a fenced block, in order."""
    fenced = False
    out: list[str] = []
    for line in text.split("\n"):
        if line.startswith("```"):
            fenced = not fenced
        elif not fenced and line.startswith("## "):
            out.append(line[3:])
    return out


@dataclass(frozen=True, slots=True)
class Alignment:
    """Which actual block each fixed template block corresponds to."""

    template: list[str]
    actual: list[str]
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


def align(template: list[str], actual: list[str]) -> Alignment:
    """Pair each fixed template block with its copy in `actual`.

    Exact matches first, in order. A block that was edited still has a
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
        want = normal(block)
        for a in range(cursor, len(actual)):
            if normal(actual[a]) == want:
                pairs[t] = a
                cursor = a + 1
                break
    for t, block in enumerate(template):
        if block == FREE or t in pairs:
            continue
        lo = max((a for k, a in pairs.items() if k < t), default=-1) + 1
        hi = min((a for k, a in pairs.items() if k > t), default=len(actual))
        scored = [
            (difflib.SequenceMatcher(None, normal(block), normal(actual[a])).ratio(), a)
            for a in range(lo, hi)
        ]
        best = max(scored, default=(0.0, -1))
        if best[0] >= _ALIKE:
            pairs[t] = best[1]
    return Alignment(template, actual, pairs)


def first_difference(want: str, got: str) -> str:
    """The first word where two blocks part, with a little context."""
    a, b = normal(want).split(), normal(got).split()
    i = next(
        (k for k, (x, y) in enumerate(zip(a, b, strict=False)) if x != y),
        min(len(a), len(b)),
    )
    return f"template has `{' '.join(a[i : i + 6])}`, found `{' '.join(b[i : i + 6])}`"


def wrap(block: str) -> str:
    """A block rewrapped to `WIDTH`.

    A table is kept as it is, and a list item gets a hanging indent.
    """
    if block.startswith("|"):
        return block
    if _ITEM.match(block):
        items = re.split(r"\n(?=\d+\. )", block)
        out = []
        for item in items:
            number, _, text = item.partition(" ")
            out.append(
                textwrap.fill(
                    normal(text),
                    WIDTH,
                    initial_indent=f"{number} ",
                    subsequent_indent=" " * (len(number) + 1),
                    break_long_words=False,
                    break_on_hyphens=False,
                )
            )
        return "\n".join(out)
    return textwrap.fill(
        normal(block), WIDTH, break_long_words=False, break_on_hyphens=False
    )


@dataclass(frozen=True, slots=True)
class Copy:
    """One passage as a skill carries it, aligned to its template."""

    passage: Passage
    path: Path
    span: tuple[int, int]
    alignment: Alignment


def copies(skill: Skill) -> Iterator[Copy]:
    """Every shared passage the skill carries, aligned.

    A missing section is skipped: the skeleton check owns the shape, and
    reporting it twice is one defect as two.
    """
    values = slots(skill)
    for passage in PASSAGES:
        path = skill.root / passage.document
        if not path.is_file():
            continue
        text = path.read_text()
        span = section(text, passage.section)
        if span is None:
            continue
        body = "\n".join(text.split("\n")[span[0] : span[1]])
        yield Copy(passage, path, span, align(render(passage, values), blocks(body)))


def compare(skill: Skill) -> Iterator[tuple[str, str]]:
    """Every way a skill's copies differ from the template.

    Each as (message, where).
    """
    for copy in copies(skill):
        al = copy.alignment
        where = f"{skill.name}/{copy.passage.document} § {copy.passage.section}"
        for t, block in enumerate(al.template):
            if block == FREE:
                continue
            a = al.pairs.get(t)
            if a is None:
                yield f"missing shared text: `{normal(block)[:70]}`", where
            elif normal(al.actual[a]) != normal(block):
                differs = first_difference(block, al.actual[a])
                yield f"differs from the shared template — {differs}", where
        for t, extra in al.gaps():
            if not al.free_before(t):
                stray = normal(al.actual[extra[0]])[:70]
                yield f"text the template has no place for: `{stray}`", where


def rewrite(skill: Skill) -> list[Finding]:
    """Rewrite every copy from the template.

    What the skill wrote in the free regions is kept. A section with
    text outside any free region is left alone and reported as a
    failure: the rewrite would have to drop that text or guess where it
    goes, and neither is a formatter's decision. Each copy rewritten is
    a note.
    """
    changed: list[Finding] = []
    for copy in copies(skill):
        al = copy.alignment
        where = f"{copy.passage.document} § {copy.passage.section}"
        if any(not al.free_before(t) for t, _ in al.gaps()):
            changed.append(fail("text outside a free region; not rewritten", where))
            continue
        gaps = dict(al.gaps())
        out: list[str] = []
        for t, block in enumerate(al.template):
            if block != FREE:
                out.append(wrap(block))
                continue
            owner = min((k for k in gaps if k > t), default=None)
            if owner is not None:
                out.extend(al.actual[a] for a in gaps.pop(owner))
        text = copy.path.read_text()
        lines = text.split("\n")
        start, end = copy.span
        rendered = "\n".join(
            [*lines[:start], "", *"\n\n".join(out).split("\n"), "", *lines[end:]]
        )
        if rendered != text:
            copy.path.write_text(rendered)
            changed.append(note("rewritten from the template", where))
    return changed
