"""What a skill is made of.

One parse, shared by every check. The recurring defect this replaces was a
predicate implemented twice and fixed once: `#[repr(C)]` per-line in one tool and
block-wide in another, a marker contract relaxed in three tools and not the
fourth, which silently dropped two blocks from a corpus of 215.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path

from .text import code_only, strip_comment, syntax_for

#: Every fenced example declares what it is, and the marker leads the block.
#: A `//!` container-doc run may precede it, because that is where a real Zig or
#: Rust file puts its module documentation; nothing else may.
#:
#: This is the default vocabulary, not the only one: a language whose failures
#: do not divide the way `does-not-compile` divides them says so in its profile.
#: Python has three ways to be wrong — the interpreter, the type checker, the
#: linter — and one word for all of them names none of them.
MARKERS = ("verified", "fragment", "does-not-compile")

#: `// verified — GOOD: the qualifier`. The comment syntax varies by language and
#: so does the vocabulary; the shape does not. `kind` is matched loosely here and
#: judged against the owning profile in `checks/markers.py`, because a grammar
#: that hardcodes the words cannot be extended without being rewritten.
_MARKER = re.compile(
    r"^(?://|#) (?P<kind>[a-z][a-z-]*)"
    r"(?: — (?P<verdict>GOOD|BAD))?"
    r"(?:[ :—] ?(?P<qualifier>.*))?$"
)


@dataclass(frozen=True, slots=True)
class Marker:
    raw: str

    @property
    def _m(self) -> re.Match[str] | None:
        return _MARKER.match(self.raw)

    @property
    def valid(self) -> bool:
        return self._m is not None

    @property
    def kind(self) -> str:
        m = self._m
        return m["kind"] if m else ""

    @property
    def verdict(self) -> str:
        m = self._m
        return (m["verdict"] or "") if m else ""

    @property
    def qualifier(self) -> str:
        m = self._m
        return (m["qualifier"] or "") if m else ""

    @property
    def verified(self) -> bool:
        return self.kind == "verified"

    @property
    def bad(self) -> bool:
        """The block that shows the wrong form.

        The marker classifies the block; the word appearing inside a prose
        qualifier does not. `// verified — BAD` yes, `… a BAD frame` no.
        """
        return self.verdict == "BAD"

    @property
    def quotation(self) -> bool:
        """Reproduced from someone else's source, so the rules do not govern it."""
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
        return f"{self.file}:{self.line} [{self.rule}]"

    @property
    def lines(self) -> list[str]:
        return self.body.split("\n")

    @property
    def code(self) -> str:
        return code_only(self.body, *syntax_for(self.lang))

    def at(self, index: int) -> int:
        """The file line number of body line `index`."""
        return self.line + index


@dataclass(frozen=True, slots=True)
class Rule:
    id: str
    tier: str  #: M, M! or S
    title: str
    body: str
    file: str
    line: int

    @property
    def where(self) -> str:
        return f"{self.file}:{self.line}"

    @property
    def statement(self) -> str:
        return self.body.split("**Why")[0]

    @property
    def why(self) -> str:
        return _section(self.body, "Why")

    @property
    def check(self) -> str:
        return _section(self.body, "Check")

    @property
    def pointer(self) -> bool:
        """Does this rule point at the rule that owns the topic?

        A pointer states no Why and no Check: the owner has them. Half of one and
        half of the other is a rule that duplicated its owner and drifted.
        """
        return self.statement.lstrip().startswith("Owned by")

    @property
    def owner(self) -> str:
        m = re.search(r"[A-Z]{2}-[A-Z]+-\d+[a-z]?", self.statement.lstrip()[:200])
        return m.group(0) if m else ""

    @property
    def owner_chapter(self) -> str:
        m = re.match(r"Owned by `references/([a-z0-9-]+\.md)`", self.statement.lstrip())
        return m.group(1) if m else ""


def _section(body: str, name: str) -> str:
    m = re.search(rf"\*\*{name}:?\*\*(.*?)(?=\n\*\*|\n### |\n## |\n```|\Z)", body, re.S)
    return m.group(1) if m else ""


@dataclass(eq=False)
class Chapter:
    """One reference chapter. Parsed once — `cached_property` needs a `__dict__`,
    so this is deliberately neither frozen nor slotted."""

    path: Path
    prefix: str

    @property
    def name(self) -> str:
        return self.path.name

    @cached_property
    def text(self) -> str:
        return self.path.read_text()

    @cached_property
    def rules(self) -> list[Rule]:
        out: list[Rule] = []
        heads = list(
            re.finditer(
                rf"^### ({self.prefix}-[A-Z]+-\d+[a-z]?) \[(M!|M|S)\] (.+)$", self.text, re.M
            )
        )
        for i, m in enumerate(heads):
            end = heads[i + 1].start() if i + 1 < len(heads) else len(self.text)
            body = self.text[m.end() : end]
            nxt = re.search(r"^## ", body, re.M)
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
        """id -> (tier, title), from the chapter's own contents list."""
        head = self.text.split("\n---\n")[0]
        return {
            m.group(1): (m.group(2), m.group(3).strip())
            for m in re.finditer(
                rf"^\s*- ({self.prefix}-[A-Z]+-\d+[a-z]?) \[(M!|M|S)\] (.+)$", head, re.M
            )
        }

    def blocks(self, lang: str) -> list[Block]:
        out: list[Block] = []
        heads = list(re.finditer(rf"^### ({self.prefix}-[A-Z]+-\d+[a-z]?) \[", self.text, re.M))
        for m in re.finditer(rf"^```{lang}\n(.*?)^```", self.text, re.M | re.S):
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

    def __init__(self, root: Path, profile=None):
        self.root = root
        self.name = root.name
        from .profiles import profile_for

        self.profile = profile or profile_for(self.name)

    def __repr__(self) -> str:
        return f"Skill({self.name})"

    @property
    def prefix(self) -> str:
        return self.profile.prefix

    @property
    def skill_md(self) -> Path:
        return self.root / "SKILL.md"

    @cached_property
    def text(self) -> str:
        return self.skill_md.read_text()

    @cached_property
    def chapters(self) -> list[Chapter]:
        return [Chapter(p, self.prefix) for p in sorted((self.root / "references").glob("*.md"))]

    @cached_property
    def rules(self) -> list[Rule]:
        return [r for c in self.chapters for r in c.rules]

    @cached_property
    def by_id(self) -> dict[str, Rule]:
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
                re.M | re.S,
            )
        ]

    @property
    def markdown(self) -> list[Path]:
        return [c.path for c in self.chapters] + [self.skill_md]

    @property
    def assets(self) -> list[Path]:
        d = self.root / "assets"
        return sorted(p for p in d.glob("*") if p.is_file()) if d.is_dir() else []

    def blocks(self, lang: str | None = None, *, verified: bool = False) -> list[Block]:
        langs = [lang] if lang else self.profile.languages
        out = [b for lg in langs for c in self.chapters for b in c.blocks(lg)]
        return [b for b in out if b.marker.verified] if verified else out

    def advice(self, lang: str | None = None, *, verified: bool = False) -> list[Block]:
        """The blocks this standard offers as advice, not as evidence.

        `// verified — BAD` compiles, which is what the marker claims, and exists
        to contain the shape a rule forbids — which is what those greps hunt. Ten
        of them sat in the self-application corpus, so a rule whose grep matched
        its own illustration would have failed for demonstrating itself
        correctly.

        One definition, because there were five: this predicate was spelled
        inline in `checks/selfapply.py` and again in each of the three profiles,
        while the shared name sat here uncalled — in the module whose own
        docstring names "a predicate implemented twice and fixed once" as the
        defect it exists to prevent.
        """
        return [b for b in self.blocks(lang, verified=verified) if not b.marker.evidence]


def load(root: Path) -> Skill:
    return Skill(root)


def discover(skills_dir: Path) -> list[Skill]:
    return [Skill(p) for p in sorted(skills_dir.iterdir()) if (p / "SKILL.md").is_file()]


# ------------------------------------------------------------------ predicates


def repr_c_above(lines: list[str], j: int) -> bool:
    """Is the item containing line `j` declared `#[repr(C)]`?

    Per line, not per block: a block that mixes a layout-sensitive type with an
    ordinary one must still report the ordinary one.
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

    Several rules are scoped to test bodies ("no `std.debug.print` in a test"),
    and a `const log = std.log.scoped(...)` at container scope is not what they
    hunt. Container scope is order-independent, so a `test` may sit anywhere.
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

    `extern struct` and `extern union` are layout qualifiers and link fine.
    Testing for the substring `extern ` excluded two blocks whose four tests pass.
    """
    return bool(_EXTERN_FN.search(code_only(source)))
