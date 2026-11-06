"""What a skill is made of: its files, each parsed once.

One parse, shared by every check. The recurring defect this replaces was
a predicate implemented twice and fixed once: `#[repr(C)]` per-line in
one tool and block-wide in another, a marker contract relaxed in three
tools and not the fourth, which silently dropped two blocks from a
corpus of 215.

Nothing here reads markdown. A file is parsed by the document model and
read as a chapter by its chapter layer (`agent_skill.doc`); this module
holds the files, parses each once, and says where an example and a
finding are. It used to match rules, tables and fences in raw text
beside the tree, so every structure had two readers that agreed on the
shipped files and on nothing else.
"""

import re
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from typing import Self, override
lazy from collections.abc import Collection, Iterable, Iterator

from agent_skill.doc import Doc, Fence, walk
from agent_skill.doc import chapter as layer
from agent_skill.ids import Location, RuleId
from agent_skill.text import group
from agent_skill.vocabulary import RENAMES
lazy from agent_skill.lang import language
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


#: The file every skill is read from first.
SKILL_MD = "SKILL.md"

#: The directory a skill keeps its chapters in.
REFERENCES = "references"

#: The file under `references/` that every rename table lives in.
RENAMES_MD = f"{RENAMES}.md"


def located(
    skill: str | None,
    document: str = "",
    line: int | None = None,
    rule: RuleId | None = None,
) -> Location:
    """`line` of `document` in `skill`, under `rule`, as far as known.

    A block or a chapter names its document by file name alone —
    `SKILL.md`, or a chapter's `errors.md` — while a location names a
    file by its path in the skill, so a bare chapter name is put under
    `references/`; a name with a directory in it is already a path.
    """
    file = None
    if document:
        bare = document != SKILL_MD and "/" not in document
        file = f"{REFERENCES}/{document}" if bare else document
    return Location(skill, file, line, rule)


@dataclass(frozen=True, slots=True)
class Block:
    """One fenced example, and the rule it sits under.

    `rule` is None for an example outside every rule: in `SKILL.md`, a
    chapter's scope, or a section's lead.
    """

    file: str
    rule: RuleId | None
    line: int  #: 1-based line of the block's first body line
    body: str
    lang: str
    marker: Marker
    skill: str | None = None  #: the skill whose markdown holds it

    @property
    def where(self) -> Location:
        """The block's first body line, under its rule."""
        return self.where_at(0)

    def where_at(self, index: int) -> Location:
        """Body line `index` of the block, under its rule."""
        return located(self.skill, self.file, self.at(index), self.rule)

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
        return language(self.lang).code(self.body)

    def at(self, index: int) -> int:
        """The file line number of body line `index`."""
        return self.line + index


def marker_line(body: str) -> str:
    """The block's marker line, or "" when it has none.

    The first line of the body that is not `//!` container
    documentation.
    """
    for line in body.split("\n"):
        if line.startswith("//!"):
            continue
        return line
    return ""


@dataclass(eq=False)
class Chapter:
    """One markdown file of a skill, parsed once.

    A chapter under `references/`, or `SKILL.md` read for its examples.
    `cached_property` needs a `__dict__`, so this is deliberately
    neither frozen nor slotted.
    """

    path: Path
    skill: str  #: the name of the skill it belongs to

    @property
    def name(self) -> str:
        """The chapter's file name, as its blocks name it."""
        return self.path.name

    def where(self, line: int | None = None, rule: RuleId | None = None) -> Location:
        """`line` of this chapter under `rule`, or the chapter."""
        return located(self.skill, self.name, line, rule)

    @cached_property
    def text(self) -> str:
        """The chapter's markdown, read once."""
        return self.path.read_text()

    @cached_property
    def doc(self) -> Doc:
        """The chapter as the document model parses it, once."""
        return Doc.parse(self.text)

    @cached_property
    def _layer(self) -> tuple[layer.Chapter, str | None]:
        """The chapter as the chapter layer reads it, and why not."""
        try:
            return layer.Chapter.read(self.doc), None
        except ValueError as e:
            return layer.Chapter("", (), None, ()), str(e)

    @property
    def typed(self) -> layer.Chapter:
        """Its rules, contents, tool rows and rename tables, typed.

        Empty when the chapter does not read as one, so a check reading
        it finds nothing rather than stopping the run: `refused` says
        why, and `skeleton` reports it.
        """
        return self._layer[0]

    @property
    def refused(self) -> str | None:
        """Why the chapter layer refused this file, if it did."""
        return self._layer[1]

    def blocks(self, lang: str) -> list[Block]:
        """Every fenced `lang` example, with the rule it sits under.

        Found in the tree, where a fence is recognised before anything
        else, so a fence inside an example is part of it and an example
        in a list item is an example. Under a rule is under its `###`
        heading, as `layer.owned` reads the file; a file the chapter
        layer refuses still has its examples.
        """
        return [
            Block(
                self.name,
                rule,
                fence.line + 1,
                fence.body,
                lang,
                Marker(marker_line(fence.body)),
                self.skill,
            )
            for top, rule in layer.owned(self.doc)
            for fence in walk((top,))
            if isinstance(fence, Fence) and fence.info == lang
        ]


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
        return self.root / SKILL_MD

    @property
    def renames_md(self) -> Path:
        """`references/renames.md`, which holds every rename table."""
        return self.root / REFERENCES / RENAMES_MD

    def asset(self, rel: str) -> Path:
        """The file this skill applies under `rel`: `assets/ci.yml`.

        Its own; or, for a delta that does not ship one, its anchor's.
        A delta ships only the assets it departs in, so one it does not
        ship is its anchor's, and every reader asks this rather than
        joining the path itself.
        """
        own = self.root / rel
        anchor = self.profile.anchor
        if own.exists() or not anchor:
            return own
        return self.root.parent / anchor / rel

    @cached_property
    def text(self) -> str:
        """`SKILL.md`, read once."""
        return self.skill_md.read_text()

    @cached_property
    def doc(self) -> Doc:
        """`SKILL.md` as the document model parses it, once."""
        return Doc.parse(self.text)

    @cached_property
    def typed(self) -> layer.SkillMd:
        """`SKILL.md`'s title, sections, core rules and overrides."""
        return layer.SkillMd.read(self.doc)

    @cached_property
    def core(self) -> tuple[layer.Rule, ...]:
        """Every rule `SKILL.md` states, typed as a chapter's are."""
        return self.typed.core_rules

    @cached_property
    def chapter_rules(self) -> tuple[layer.Rule, ...]:
        """Every chapter rule, chapter by chapter, typed."""
        return tuple(r for c in self.chapters for r in c.typed.rules)

    @cached_property
    def ids(self) -> frozenset[RuleId]:
        """Every ID this skill gives a rule, in a chapter or `SKILL.md`.

        What a citation, a rename or an asset names to name a rule.
        """
        return frozenset(r.id for r in (*self.chapter_rules, *self.core))

    @cached_property
    def docs(self) -> dict[Path, Doc]:
        """Every markdown file parsed: the chapters, then `SKILL.md`."""
        return {c.path: c.doc for c in self.chapters} | {self.skill_md: self.doc}

    @cached_property
    def chapters(self) -> list[Chapter]:
        """Every chapter under `references/`, in file-name order."""
        return [
            Chapter(p, self.name) for p in sorted((self.root / REFERENCES).glob("*.md"))
        ]

    @cached_property
    def documents(self) -> list[Chapter]:
        """`SKILL.md` and every chapter: everywhere an example can sit.

        Read as a chapter, `SKILL.md` has no `###` rules, so this serves
        the examples only; `chapters` stays the rule source.
        """
        return [Chapter(self.skill_md, self.name), *self.chapters]

    def path_of(self, document: str) -> Path:
        """The file a block's `file` names: `SKILL.md`, or a chapter."""
        if document == self.skill_md.name:
            return self.skill_md
        return self.root / REFERENCES / document

    def at(
        self,
        file: str | Path = "",
        line: int | None = None,
        rule: RuleId | None = None,
    ) -> Location:
        """A location in this skill: `line` of `file`, under `rule`.

        `file` is a path in the skill, or a document as a block or a
        chapter names it; "" is the skill as a whole.
        """
        if isinstance(file, Path):
            file = file.relative_to(self.root).as_posix()
        return located(self.name, file, line, rule)

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
    return [Skill(p) for p in sorted(skills_dir.iterdir()) if (p / SKILL_MD).is_file()]


@dataclass(frozen=True, slots=True)
class Tree:
    """Every skill a run reads: what each check is a function of.

    A check that compares a skill with its siblings always has them:
    choosing skills on the command line chooses which findings are
    shown. Only a check of one skill at a time is spared the others,
    since nothing it finds in them would be.
    """

    skills: tuple[Skill, ...]

    @classmethod
    def of(cls, skills: Iterable[Skill]) -> Self:
        """The tree holding `skills`, in the order given."""
        return cls(tuple(skills))

    def __iter__(self) -> Iterator[Skill]:
        """Each skill, in order."""
        return iter(self.skills)

    def only(self, names: Collection[str]) -> Tree:
        """The skills called one of `names`, in order."""
        return Tree(tuple(s for s in self.skills if s.name in names))
