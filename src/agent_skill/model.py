"""What a skill is made of.

One parse, shared by every check. The recurring defect this replaces was
a predicate implemented twice and fixed once: `#[repr(C)]` per-line in
one tool and block-wide in another, a marker contract relaxed in three
tools and not the fourth, which silently dropped two blocks from a
corpus of 215.
"""

import re
from dataclasses import dataclass
from functools import cached_property
from typing import override
lazy from pathlib import Path

from agent_skill.text import code_only, group, strip_comment, syntax_for
lazy from agent_skill.profiles import Profile, profile_for

#: Every fenced example declares what it is, and the marker leads the
#: block. A `//!` container-doc run may precede it, because that is
#: where a real Zig or Rust file puts its module documentation; nothing
#: else may.
#:
#: `rejected` names the tool that does the rejecting —
#: `// rejected — clippy: …` — because a language has several ways to be
#: wrong and one word for all of them names none of them: Python has the
#: interpreter, the type checker and the linter, and Rust has `rustc`
#: and `clippy`. Every standard uses these three words.
MARKERS = ("verified", "fragment", "rejected")

#: `// verified — GOOD: the qualifier`. The comment syntax varies by
#: language and so does the vocabulary; the shape does not. `kind` is
#: matched loosely here and judged against the owning profile in
#: `checks/markers.py`, because a grammar that hardcodes the words
#: cannot be extended without being rewritten.
_MARKER = re.compile(
    r"^(?://|#) (?P<kind>[a-z][a-z-]*)"
    r"(?: — (?P<verdict>GOOD|BAD))?"
    r"(?:[ :—] ?(?P<qualifier>.*))?$"
)


@dataclass(frozen=True, slots=True)
class Marker:
    """A fenced example's marker line, and what it declares."""

    raw: str

    @property
    def _m(self) -> re.Match[str] | None:
        return _MARKER.match(self.raw)

    @property
    def valid(self) -> bool:
        """Does the line have the shape of a marker at all?"""
        return self._m is not None

    @property
    def kind(self) -> str:
        """The marker word, such as `verified`; "" for no marker."""
        return group(self._m, "kind")

    @property
    def verdict(self) -> str:
        """`GOOD` or `BAD`, or "" when the marker gives no verdict."""
        return group(self._m, "verdict")

    @property
    def qualifier(self) -> str:
        """What follows the kind and verdict; "" when nothing does."""
        return group(self._m, "qualifier")

    @property
    def verified(self) -> bool:
        """Is the block marked `verified`?"""
        return self.kind == "verified"

    @property
    def tool(self) -> str:
        """The tool a `rejected` block names.

        "" when it names none.
        """
        return group(re.match(r"^(?:— )?([a-z][a-z-]*):", self.qualifier))

    @property
    def bad(self) -> bool:
        """The block that shows the wrong form.

        The marker classifies the block; the word appearing inside a
        prose qualifier does not. `// verified — BAD` yes,
        `… a BAD frame` no.
        """
        return self.verdict == "BAD"

    @property
    def quotation(self) -> bool:
        """Reproduced from someone else's source.

        The rules do not govern a quotation.
        """
        return "quoted from" in self.raw

    @property
    def evidence(self) -> bool:
        """Shown as evidence rather than offered as advice."""
        return self.bad or self.quotation


@dataclass(frozen=True, slots=True)
class Block:
    """One fenced example."""

    file: str
    rule: str
    line: int  #: 1-based line of the block's first body line
    body: str
    lang: str
    marker: Marker

    @property
    def where(self) -> str:
        """`file:line [rule]`, for a finding about this block."""
        return f"{self.file}:{self.line} [{self.rule}]"

    @property
    def lines(self) -> list[str]:
        """The body, one string per line."""
        return self.body.split("\n")

    @property
    def code(self) -> str:
        """The body with every comment removed.

        Comments are found the way the block's own language spells them,
        and the line count is kept.
        """
        return code_only(self.body, *syntax_for(self.lang))

    def at(self, index: int) -> int:
        """The file line number of body line `index`."""
        return self.line + index


@dataclass(frozen=True, slots=True)
class Rule:
    """One chapter rule: its heading, and the body under it."""

    id: str
    tier: str  #: M, M! or S
    title: str
    body: str
    file: str
    line: int

    @property
    def where(self) -> str:
        """`file:line`, for a finding about this rule."""
        return f"{self.file}:{self.line}"

    @property
    def statement(self) -> str:
        """The rule's text before its Why."""
        return self.body.split("**Why")[0]

    @property
    def why(self) -> str:
        """The rule's Why section."""
        return _section(self.body, "Why")

    @property
    def check(self) -> str:
        """The rule's Check section."""
        return _section(self.body, "Check")

    @property
    def pointer(self) -> bool:
        """Does this rule point at the rule that owns the topic?

        A pointer states no Why and no Check: the owner has them. Half
        of one and half of the other is a rule that duplicated its owner
        and drifted.
        """
        return self.statement.lstrip().startswith("Owned by")

    @property
    def owner(self) -> str:
        """The rule a pointer points at, or "".

        It is the first rule ID in the opening 200 characters of the
        statement.
        """
        m = re.search(r"[A-Z]{2}-[A-Z]+-\d+[a-z]?", self.statement.lstrip()[:200])
        return m.group(0) if m else ""

    @property
    def owner_chapter(self) -> str:
        """The chapter an `Owned by` pointer names, or ""."""
        m = re.match(r"Owned by `references/([a-z0-9-]+\.md)`", self.statement.lstrip())
        return group(m)


@dataclass(frozen=True, slots=True)
class LintRow:
    """One row of a chapter's `Decided by tools` table.

    A claim a tool settles alone.
    """

    tool: str
    lint: str
    level: str
    forbids: str
    file: str
    line: int

    @property
    def where(self) -> str:
        """`file:line`, for a finding about this row."""
        return f"{self.file}:{self.line}"


@dataclass(frozen=True, slots=True)
class Rename:
    """One row of a rename table: an old ID and what it became.

    `now` is a rule ID, `lint <tool>:<name>` for a rule demoted to a
    lint-table row, or `removed — <reason>`.
    """

    before: str
    now: str
    line: int

    @property
    def lint(self) -> tuple[str, str] | None:
        """The tool and lint, for a rule demoted to a lint-table row.

        None for anything else.
        """
        m = re.fullmatch(r"lint `([a-z]+):([^`]+)`", self.now)
        return (group(m), group(m, 2)) if m else None

    @property
    def removed(self) -> str | None:
        """The reason, for a rule removed outright.

        None for anything else.
        """
        m = re.fullmatch(r"removed —\s*(.*)", self.now)
        return group(m).strip() if m else None

    @property
    def target(self) -> str:
        """The new ID, for a rule that was renumbered or merged.

        "" for anything else.
        """
        return group(re.fullmatch(r"`([A-Z]{2}-[A-Z]+-\d+)`", self.now))


#: The section a chapter lists its tool-decided claims under.
DECIDED = "Decided by tools"

#: The section a migration chapter keeps a renumbering's rename table
#: under.
RENAMED = re.compile(r"^## Rule IDs before the .+ revision$", re.MULTILINE)

#: The en dash a range is written with, as prose writes a range of
#: numbers.
DASH = "\u2013"

#: A family's range as a rename table states it: first and last ID
#: joined by the dash, or one ID.
_RANGE = re.compile(rf"`([A-Z]{{2}}-[A-Z]+)-(\d+)`(?:{DASH}`\1-(\d+)`)?")

#: The cells of a rename-table row: `| Before | Now |`.
_RENAME_CELLS = 2

#: The cells of a lint-table row: `| Tool | Lint | Level | Forbids |`.
_LINT_CELLS = 4


@dataclass(frozen=True, slots=True)
class RenameTable:
    """One revision's rename table.

    The range each family ran before the revision, and a row for each
    old ID that changed. An ID in range with no row still names the
    rule it named.

    `span` is where the section sits in its file, for the renumbering
    that rewrites it.
    """

    heading: str
    ranges: tuple[tuple[str, int, int], ...]
    rows: tuple[Rename, ...]
    span: tuple[int, int]

    @property
    def originals(self) -> list[str]:
        """Every ID the families ran before the revision.

        In the order the ranges give.
        """
        return [
            f"{family}-{n:02d}"
            for family, lo, hi in self.ranges
            for n in range(lo, hi + 1)
        ]

    @property
    def unchanged(self) -> list[str]:
        """The original IDs no row lists.

        Each still names the rule it named.
        """
        listed = {r.before for r in self.rows}
        return [rid for rid in self.originals if rid not in listed]


def rename_tables(text: str) -> list[RenameTable]:
    """Every rename table in `text`.

    The ranges are read from the prose above the table.
    """
    out: list[RenameTable] = []
    for m in RENAMED.finditer(text):
        nxt = re.compile(r"^## ", re.MULTILINE).search(text, m.end())
        end = nxt.start() if nxt else len(text)
        lead = re.split(r"^\|", text[m.end() : end], maxsplit=1, flags=re.MULTILINE)[0]
        ranges = tuple(
            (r.group(1), int(r.group(2)), int(r.group(3) or r.group(2)))
            for r in _RANGE.finditer(lead)
        )
        rows = tuple(
            Rename(cells[0].strip("`"), cells[1], line)
            for line, cells in _rows(text, m.start())
            if len(cells) == _RENAME_CELLS
        )
        out.append(RenameTable(m.group(0), ranges, rows, (m.start(), end)))
    return out


def without_renames(text: str) -> str:
    """`text` with every rename table blanked, line count kept.

    A rename table lists IDs that no longer exist, on purpose: they are
    what a reader holding an old citation looks up. Read as citations
    they are dangling.
    """

    def blank(m: re.Match[str]) -> str:
        return "\n" * m.group(0).count("\n")

    table = r"^## Rule IDs before the .+ revision$.*?(?=^## |\Z)"
    return re.sub(table, blank, text, flags=re.MULTILINE | re.DOTALL)


def _rows(text: str, start: int) -> list[tuple[int, list[str]]]:
    """The body rows of the first table after `start`.

    Each as (line number, cells).
    """
    out: list[tuple[int, list[str]]] = []
    lines = text.split("\n")
    first = text[:start].count("\n")
    seen_header = False
    for i in range(first, len(lines)):
        line = lines[i]
        if line.startswith("## ") and i > first:
            break
        if not line.startswith("|"):
            if seen_header and out:
                break
            continue
        # A pipe inside a cell is written `\|`, as markdown requires
        # even inside a code span; only an unescaped pipe divides cells.
        inner = line.strip().removeprefix("|").removesuffix("|")
        cells = [c.strip().replace("\\|", "|") for c in re.split(r"(?<!\\)\|", inner)]
        if not seen_header:
            seen_header = True
            continue
        if set("".join(cells)) <= set("-: "):
            continue
        out.append((i + 1, cells))
    return out


def _section(body: str, name: str) -> str:
    """The text of a labelled section.

    It runs up to the next label, heading or example. The next *label*
    — `**Check:**` — not the next line that opens with `**`. A Why
    holding a bolded phrase at the start of a line was read as ending
    there, so a long Why measured short.
    """
    m = re.search(
        rf"\*\*{name}:?\*\*(.*?)(?=\n\*\*[^*\n]+:\*\*|\n### |\n## |\n```|\Z)",
        body,
        re.DOTALL,
    )
    return group(m)


@dataclass(eq=False)
class Chapter:
    """One reference chapter, parsed once.

    `cached_property` needs a `__dict__`, so this is deliberately
    neither frozen nor slotted.
    """

    path: Path
    prefix: str

    @property
    def name(self) -> str:
        """The chapter's file name, as findings cite it."""
        return self.path.name

    @cached_property
    def text(self) -> str:
        """The chapter's markdown, read once."""
        return self.path.read_text()

    @cached_property
    def rules(self) -> list[Rule]:
        """Every rule the chapter states, in order."""
        out: list[Rule] = []
        heads = list(
            re.finditer(
                rf"^### ({self.prefix}-[A-Z]+-\d+[a-z]?) \[(M!|M|S)\] (.+)$",
                self.text,
                re.MULTILINE,
            )
        )
        for i, m in enumerate(heads):
            end = heads[i + 1].start() if i + 1 < len(heads) else len(self.text)
            body = self.text[m.end() : end]
            nxt = re.search(r"^## ", body, re.MULTILINE)
            out.append(
                Rule(
                    id=m.group(1),
                    tier=m.group(2),
                    title=m.group(3).strip(),
                    body=body[: nxt.start()] if nxt else body,
                    file=self.name,
                    line=self.text[: m.start()].count("\n") + 1,
                )
            )
        return out

    @cached_property
    def toc(self) -> dict[str, tuple[str, str]]:
        """Id -> (tier, title), from the chapter's own contents list."""
        head = self.text.split("\n---\n")[0]
        return {
            m.group(1): (m.group(2), m.group(3).strip())
            for m in re.finditer(
                rf"^\s*- ({self.prefix}-[A-Z]+-\d+[a-z]?) \[(M!|M|S)\] (.+)$",
                head,
                re.MULTILINE,
            )
        }

    @cached_property
    def lint_rows(self) -> list[LintRow]:
        """The rows of the `Decided by tools` table.

        Its columns are `| Tool | Lint | Level | Forbids |`.
        """
        m = re.search(rf"^## {DECIDED}$", self.text, re.MULTILINE)
        if not m:
            return []
        return [
            LintRow(cells[0], cells[1].strip("`"), cells[2], cells[3], self.name, line)
            for line, cells in _rows(self.text, m.start())
            if len(cells) == _LINT_CELLS
        ]

    @cached_property
    def rename_tables(self) -> list[RenameTable]:
        """Every rename table the chapter carries."""
        return rename_tables(self.text)

    @cached_property
    def renames(self) -> list[Rename]:
        """Every row of every rename table this chapter carries.

        Each table's columns are `| Before | Now |`.
        """
        return [row for table in self.rename_tables for row in table.rows]

    def blocks(self, lang: str) -> list[Block]:
        """Every fenced `lang` example, with the rule it sits under."""
        out: list[Block] = []
        heads = list(
            re.finditer(
                rf"^### ({self.prefix}-[A-Z]+-\d+[a-z]?) \[", self.text, re.MULTILINE
            )
        )
        for m in re.finditer(
            rf"^```{lang}\n(.*?)^```", self.text, re.MULTILINE | re.DOTALL
        ):
            body = m.group(1)
            prev = [h for h in heads if h.start() < m.start()]
            out.append(
                Block(
                    file=self.name,
                    rule=prev[-1].group(1) if prev else "?",
                    line=self.text[: m.start()].count("\n") + 2,
                    body=body,
                    lang=lang,
                    marker=Marker(marker_line(body)),
                )
            )
        return out


def marker_line(body: str) -> str:
    """The block's marker line, or "" when it has none."""
    for line in body.split("\n"):
        if line.startswith("//!"):
            continue
        return line
    return ""


class Skill:
    """A skill directory, parsed once."""

    def __init__(self, root: Path, profile: Profile | None = None) -> None:
        """Read the skill at `root`.

        `profile` defaults to the one `profile_for` finds for the
        directory's name.
        """
        self.root = root
        self.name = root.name

        self.profile = profile or profile_for(self.name)

    @override
    def __repr__(self) -> str:
        """The skill's name, as `Skill(<name>)`."""
        return f"Skill({self.name})"

    @property
    def prefix(self) -> str:
        """The rule-ID prefix the profile declares, such as `RS`."""
        return self.profile.prefix

    @property
    def skill_md(self) -> Path:
        """The skill's `SKILL.md`."""
        return self.root / "SKILL.md"

    @cached_property
    def text(self) -> str:
        """`SKILL.md`, read once."""
        return self.skill_md.read_text()

    @cached_property
    def chapters(self) -> list[Chapter]:
        """Every chapter under `references/`, in file-name order."""
        return [
            Chapter(p, self.prefix)
            for p in sorted((self.root / "references").glob("*.md"))
        ]

    @cached_property
    def documents(self) -> list[Chapter]:
        """`SKILL.md` and every chapter: everywhere an example can sit.

        Read as a chapter, `SKILL.md` has no `###` rules, so this serves
        the examples only; `chapters` stays the rule source.
        """
        return [Chapter(self.skill_md, self.prefix), *self.chapters]

    def path_of(self, document: str) -> Path:
        """The file a block's `file` names: `SKILL.md`, or a chapter."""
        if document == self.skill_md.name:
            return self.skill_md
        return self.root / "references" / document

    @cached_property
    def rules(self) -> list[Rule]:
        """Every chapter rule, chapter by chapter."""
        return [r for c in self.chapters for r in c.rules]

    @cached_property
    def lint_rows(self) -> list[LintRow]:
        """Every lint-table row of every chapter."""
        return [row for c in self.chapters for row in c.lint_rows]

    @cached_property
    def rename_tables(self) -> list[RenameTable]:
        """Every rename table of every chapter."""
        return [table for c in self.chapters for table in c.rename_tables]

    @cached_property
    def renames(self) -> list[Rename]:
        """Every row of every rename table."""
        return [r for c in self.chapters for r in c.renames]

    @cached_property
    def by_id(self) -> dict[str, Rule]:
        """Each chapter rule, by its ID."""
        return {r.id: r for r in self.rules}

    @cached_property
    def core_rules(self) -> list[tuple[str, str, str]]:
        """(id, tier, body) for every rule stated in SKILL.md itself."""
        return [
            (m.group(1), m.group(2), m.group(0))
            for m in re.finditer(
                rf"^- \*\*({self.prefix}-CORE-\d+[a-z]?) `(\[M!?\]|\[S\])`\*\*"
                rf".*?(?=^- \*\*{self.prefix}-CORE|\n## |\Z)",
                self.text,
                re.MULTILINE | re.DOTALL,
            )
        ]

    @property
    def markdown(self) -> list[Path]:
        """Every markdown file: the chapters, then `SKILL.md`."""
        return [c.path for c in self.chapters] + [self.skill_md]

    @property
    def assets(self) -> list[Path]:
        """Every file directly in `assets/`, in sorted order.

        Empty when the skill has no `assets/`.
        """
        d = self.root / "assets"
        return sorted(p for p in d.glob("*") if p.is_file()) if d.is_dir() else []

    def blocks(self, lang: str = "", *, verified: bool = False) -> list[Block]:
        """Every fenced example, or only the `verified` ones.

        `lang` limits them to one language; without it they are drawn
        from each language the profile names.
        """
        langs = [lang] if lang else self.profile.languages
        out = [b for lg in langs for c in self.documents for b in c.blocks(lg)]
        return [b for b in out if b.marker.verified] if verified else out

    def advice(self, lang: str = "", *, verified: bool = False) -> list[Block]:
        """The blocks this standard offers as advice, not as evidence.

        `// verified — BAD` compiles, which is what the marker claims,
        and exists to contain the shape a rule forbids — which is what
        those patterns hunt. Ten of them sat in the self-application
        corpus, so a rule whose pattern matched its own illustration
        would have failed for demonstrating itself correctly.

        One definition, because there were five: this predicate was
        spelled inline in `checks/selfapply.py` and again in each of the
        three profiles, while the shared name sat here uncalled — in the
        module whose own docstring names "a predicate implemented twice
        and fixed once" as the defect it exists to prevent.
        """
        return [
            b for b in self.blocks(lang, verified=verified) if not b.marker.evidence
        ]


def load(root: Path) -> Skill:
    """The skill at `root`, read with its registered profile."""
    return Skill(root)


def discover(skills_dir: Path) -> list[Skill]:
    """Every skill in `skills_dir`, in name order.

    A skill is a directory there that holds a `SKILL.md`.
    """
    return [
        Skill(p) for p in sorted(skills_dir.iterdir()) if (p / "SKILL.md").is_file()
    ]


# ------------------------------------------------------------------
# predicates


def repr_c_above(lines: list[str], j: int) -> bool:
    """Is the item containing line `j` declared `#[repr(C)]`?

    Per line, not per block: a block that mixes a layout-sensitive type
    with an ordinary one must still report the ordinary one.
    """
    for k in range(j - 1, max(-1, j - 14), -1):
        s = lines[k].strip()
        if s.startswith("}"):
            return False
        if "repr(C)" in s:
            return True
    return False


def inside_tests(body: str) -> set[int]:
    """Indices of the lines inside a zig `test` block, by brace depth.

    Several rules are scoped to test bodies ("no `std.debug.print` in a
    test"), and a `const log = std.log.scoped(...)` at container scope
    is not what they hunt. Container scope is order-independent, so a
    `test` may sit anywhere.
    """
    inside: set[int] = set()
    depth, active = 0, False
    for i, line in enumerate(body.split("\n")):
        code = strip_comment(line)
        if not active and re.match(r"^\s*test\b", code):
            active, depth = True, 0
        if active:
            depth += code.count("{") - code.count("}")
            inside.add(i)
            if depth <= 0 and "}" in code:
                active = False
    return inside


_EXTERN_FN = re.compile(r'\bextern\s+(?:"[^"]*"\s+)?fn\b')


def needs_c_object(source: str) -> bool:
    """Does this block declare a symbol only a C object can supply?

    `extern struct` and `extern union` are layout qualifiers and link
    fine. Testing for the substring `extern ` excluded two blocks whose
    four tests pass.
    """
    return bool(_EXTERN_FN.search(code_only(source)))
