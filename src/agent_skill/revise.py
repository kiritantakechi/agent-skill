"""Revise a standard's rules: one operation, with laws.

Removing, merging, demoting, moving and renumbering rules, and renaming
the chapters that hold them, were two commands run in order with a hand
edit between them. They are one map here. A plan says what some old IDs
become — the rule each merged into, the lint-table row that replaces
it, its removal and why, or the place in another chapter it moves to —
and dense renumbering closes it, mapping the rules each family keeps,
in order, onto 01, 02, …. A move is a permutation of places before the
renumbering, so it is closed by the same renumbering: the rule takes
its new chapter's code, and both families close up. A move into a
chapter the standard does not ship creates it, in the chapter template
with its scope left to write, and section 6 names it; a chapter a plan
leaves with nothing in it goes, with its row. One rewrite then
applies the renumbering and the plan's merges to every rule ID in the
repository at once, so an ID that dense numbering hands to another rule
is never rewritten twice, and `references/renames.md` records what
every old ID became. A core rule `SKILL.md` states of its own may be
merged into the chapter rule it abbreviated, or removed: its item in
section 4 becomes that rule's line, or goes.

Nothing is written unless the result means what the input meant. Every
rule keeps its title under its new ID; no citation names a rule the plan
takes away; and no citation of an ID that named no rule comes to name
one. The last is the capture a person cannot see afterwards, because a
captured citation reads exactly like a correct one.

The rewrite reaches the abstract standard, whose rows each name a rule.

The laws are tested on throwaway copies of the shipped standards
(`tests/test_revise_laws.py`): a pure renumbering or chapter rename,
followed by its inverse, restores every file byte for byte; so does a
move followed by the move back to the rule's old place; an empty plan
writes nothing and reports nothing; and every ID cited before a
revision names the same rule after it, or the rename table says what it
became.
"""

import re
import subprocess
from dataclasses import dataclass, field
lazy from collections.abc import Callable, Collection, Iterator, Mapping, Sequence
lazy from pathlib import Path

from agent_skill import shared, vocabulary
from agent_skill.doc import (
    Align,
    Doc,
    Fence,
    Heading,
    Item,
    ListBlock,
    Paragraph,
    Quote,
    Table,
    text_of,
    words,
)
from agent_skill.doc import chapter as layer
from agent_skill.doc.chapter import (
    DECIDED,
    RENAMED,
    Demoted,
    LintRow,
    Removed,
    RenameTable,
    history,
    parse_becomes,
    print_becomes,
)
from agent_skill.doc.normal import listed, projection
from agent_skill.ids import FAMILY, RuleId, cited, print_range, respell
from agent_skill.layout import ABSTRACT, SKILLS, root_of
from agent_skill.model import REFERENCES, SKILL_MD, Skill
lazy from agent_skill.doc import Block
lazy from agent_skill.doc.normal import Mapped
lazy from agent_skill.lang import toolchains
lazy from agent_skill.model import Chapter, Tree


@dataclass(frozen=True, slots=True)
class Moved:
    """A rule moved to another chapter of its standard, and where in it.

    `chapter` is the stem of the chapter it goes to, `references/x.md`
    as `x`. `after` is the rule it follows there, or the title of the
    section it opens, `## Streams` as `Streams`. A chapter the standard
    does not ship is created, in the chapter template, with its scope
    left for its author to write. The rule takes the target family's
    code, and dense renumbering closes both families.
    """

    chapter: str
    after: RuleId | str


#: What a plan says an old ID becomes: the rule it merges into, the
#: lint-table row that replaces it, its removal and why, or the place
#: it moves to. A row is whole, since a demotion may have to add it;
#: the rename table records its tool and lint, `Demoted`, which is all
#: a table cell says. A moved rule is renumbered, so its row is its new
#: ID.
type Becomes = RuleId | LintRow | Removed | Moved

#: Some chapter rules, each with what it becomes. Every other rule is
#: kept, and dense renumbering closes the plan.
type Plan = Mapping[RuleId, Becomes]


class ReviseError(Exception):
    """The revision cannot be done as asked; nothing was written."""


class PlanError(ReviseError):
    """What was given as a plan is not one."""


#: The title and scope a revision opens `renames.md` with, when it is
#: the first to need one.
TITLE = "Renamed Rule IDs"
SCOPE = (
    "Scope: every rule ID a revision of this standard changed, and what it is now: a "
    "rule ID, a row of a `Decided by tools` table, or a removal and its reason. It "
    "states no rules; it is for a reader holding a citation made before a revision."
)

#: The sentence that names `renames.md` in the migration chapter, the
#: one place a reader holding an old ID is pointed to it.
NAMED = (
    "Every rule ID a revision of this standard changed, and what it became, is in "
    "`references/renames.md`."
)

#: The sentence of a rename table's lead that states its ranges.
_RAN = "Before the revision the families ran {}."

#: How a rename table opens: the ranges the families ran before.
_RANGES = (
    f"{_RAN} The table lists every ID in those ranges that changed, and what it is "
    "now; an ID it does not list is unchanged."
)

#: A rename table's columns.
_RENAME_HEADER = ("Before", "Now")

#: The lead of a `Decided by tools` table a revision starts.
LEAD = (
    "A tool settles these on its own; the shipped configuration enables each "
    "at the level shown."
)

#: The lead of a table whose rows a compiler decides. A compiler ships
#: no configuration, so nothing about its rows is "enabled".
COMPILER_LEAD = (
    "The compiler rejects each of these on its own; no setting turns one off."
)

#: A `Decided by tools` table's columns.
_LINT_HEADER = ("Tool", "Lint", "Level", "Forbids")


def compilers() -> frozenset[str]:
    """Tools whose rows are errors the compiler always reports."""
    return frozenset(t for tc in toolchains() for t in tc.compilers)


def heading(skill: Skill) -> str:
    """The title of the rename table for the revision `skill` is at.

    Named by the target, the pin's major.minor: a patch release moves
    the pin and is not a new revision, so it starts no second table.
    """
    return (
        f"Rule IDs before the {skill.profile.language} {skill.profile.target} revision"
    )


@dataclass(frozen=True, slots=True)
class Revision:
    """What a revision moves and writes, checked, and nothing done yet.

    Its parts are what the command line shows before writing, so a dry
    run and the run that writes are one computation.
    """

    repo: Path
    skills: tuple[Skill, ...]
    #: every old ID the revision changes -> what it is after it
    renamed: Mapping[RuleId, layer.Becomes]
    #: how many chapter rules the revised standards held before
    rules: int
    #: chapter path -> its new path
    moves: Mapping[Path, Path]
    #: path, as it will be after the moves -> its new text
    writes: Mapping[Path, str]
    #: what a person should look at: citations left as they were
    leftovers: tuple[str, ...]
    #: each chapter the plan leaves with nothing in it, which goes
    deleted: tuple[Path, ...] = ()

    @property
    def empty(self) -> bool:
        """Does the revision change nothing and report nothing?"""
        return not (self.moves or self.writes or self.leftovers or self.deleted)

    def apply(self) -> None:
        """Move the chapters, write every file, restate shared passages.

        A move goes through a name of its own first, so chapters that
        swap names — a permutation, like any renumbering — do not land
        on each other. A shared passage carries a rule count of its own,
        which a removal changed.
        """
        aside = {old: old.with_name(f".{old.name}.revising") for old in self.moves}
        for old, new in (
            *aside.items(),
            *((aside[o], n) for o, n in self.moves.items()),
        ):
            _move(self.repo, old, new)
        for path, text in self.writes.items():
            path.write_text(text)
        for path in self.deleted:
            path.unlink()
        if self.moves or self.writes:
            for skill in self.skills:
                shared.rewrite(Skill(skill.root, skill.profile))


def _move(repo: Path, old: Path, new: Path) -> None:
    """Move `old` to `new`, through git when git tracks it."""
    tracked = subprocess.run(  # noqa: S603 — a fixed argv, no shell
        ["git", "ls-files", "--error-unmatch", str(old)],  # noqa: S607 — the git on PATH, as a person runs it
        cwd=repo,
        capture_output=True,
        check=False,
    )
    if tracked.returncode == 0:
        subprocess.run(  # noqa: S603 — a fixed argv, no shell
            ["git", "mv", str(old), str(new)],  # noqa: S607 — the git on PATH
            cwd=repo,
            check=True,
        )
    else:
        old.rename(new)


def revise(
    tree: Tree, plan: Plan | None = None, chapters: Mapping[str, str] | None = None
) -> Revision:
    """Everything revising `tree` by `plan` would do, checked.

    Every standard in `tree` is renumbered densely, family by family;
    `plan` names chapter rules of those standards and what each becomes;
    `chapters` renames a chapter, by stem, in every standard of `tree`
    that has it. The rewrite reaches every file a citation can live in:
    every skill in the repository the tree sits in, its `src/`, its
    `tests/` and its README.
    """
    asked: dict[RuleId, Becomes] = dict(plan) if plan is not None else {}
    stems: dict[str, str] = dict(chapters) if chapters is not None else {}
    repo = _repo(tree)
    # Every path is compared with the corpus's, which are resolved.
    skills = [Skill(s.root.resolve(), s.profile) for s in tree]
    _all_named(skills, asked, stems)
    standards = [_Standard.read(skill, asked, stems) for skill in skills]
    for std in standards:
        std.name_renames()
    rewrite = _Rewrite(standards)
    corpus = _Corpus(repo, standards, rewrite)
    _refuse(standards, corpus.cites)
    writes = dict(corpus.writes)
    for std in standards:
        if (
            renames := std.renames(corpus.renames.get(std.skill.renames_md))
        ) is not None:
            writes[std.skill.renames_md] = renames
    for std in standards:
        if std.relocated and (md := _reprojected(std, writes)) is not None:
            writes[std.skill.skill_md] = md
    for std in standards:
        std.verify(writes, rewrite.swap(std))
    leftovers = [
        line
        for path, lines in corpus.leftovers.items()
        if path in writes
        for line in lines
    ]
    return Revision(
        repo,
        tuple(s.skill for s in standards),
        {k: v for s in standards for k, v in s.renamed.items()},
        sum(len(s.skill.chapter_rules) for s in standards),
        {k: v for s in standards for k, v in s.moves.items()},
        writes,
        tuple(sorted(set(leftovers + corpus.unnamed))),
        tuple(sorted(p for s in standards for p in s.deleted)),
    )


def _repo(tree: Tree) -> Path:
    """The repository every skill in `tree` sits in.

    A rewrite reaches the repository's `src/`, `tests/` and README as
    well as its skills, so a tree outside one has nowhere to rewrite.
    """
    if not tree.skills:
        msg = "there is no standard to revise"
        raise ReviseError(msg)
    where = {s.root.parent.resolve() for s in tree}
    skills = where.pop()
    if (
        where
        or len(skills.parts) <= len(SKILLS.parts)
        or root_of(skills) / SKILLS != skills
    ):
        msg = f"the skills are not one repository's `{SKILLS}`"
        raise ReviseError(msg)
    return root_of(skills)


def _all_named(
    skills: Sequence[Skill], plan: Plan, chapters: Mapping[str, str]
) -> None:
    """Every standard the plan names, and chapter renamed, is there."""
    prefixes = {s.prefix for s in skills}
    for rid in plan:
        if rid.standard not in prefixes:
            msg = f"{rid}: no standard being revised has the prefix {rid.standard}"
            raise ReviseError(msg)
    stems = {c.path.stem for s in skills for c in s.chapters}
    for old in chapters:
        if old not in stems:
            msg = f"no standard being revised has a chapter `{old}.md`"
            raise ReviseError(msg)


# ------------------------------------------------------------------ one
# standard


@dataclass
class _Standard:
    """One standard as the revision leaves it, before any respelling."""

    skill: Skill
    #: each renamed chapter's path -> its new path
    moves: dict[Path, Path]
    #: each chapter the plan edits, as it reads after the edit
    edited: dict[Path, layer.Chapter]
    #: every chapter rule the revision keeps -> its ID after it
    sigma: dict[RuleId, RuleId]
    #: every rule the plan merges -> the merged-into rule's ID after it
    merged: dict[RuleId, RuleId]
    #: every rule the plan demotes or removes -> what its row will say
    gone: dict[RuleId, Demoted | Removed]
    #: each family, spelled with its prefix, that a rename moves
    families: dict[str, str]
    #: each renamed chapter's stem -> its new stem
    stems: dict[str, str]
    #: `SKILL.md` as the plan leaves it, when the plan names a core rule
    #: or creates or deletes a chapter
    skill_md: Doc | None = None
    #: each chapter a move creates, as it reads after the plan
    created: dict[Path, layer.Chapter] = field(default_factory=dict)
    #: each chapter the plan leaves with nothing in it, which goes
    deleted: frozenset[Path] = frozenset()
    #: every rule the plan moves to another chapter
    relocated: frozenset[RuleId] = frozenset()

    @classmethod
    def read(cls, skill: Skill, plan: Plan, chapters: Mapping[str, str]) -> _Standard:
        """The plan applied to `skill`, and the renumbering after it."""
        if not skill.skill_md.is_file():
            msg = f"there is no skill called {skill.name}"
            raise ReviseError(msg)
        _readable(skill)
        stems = _stems(skill, chapters)
        asked = {rid: b for rid, b in plan.items() if rid.standard == skill.prefix}
        home = {r.id: c for c in skill.chapters for r in c.typed.rules}
        moving = {rid: b for rid, b in asked.items() if isinstance(b, Moved)}
        rows = _rows(skill, {r: b for r, b in asked.items() if r not in moving}, home)
        edited = {
            c.path: _with_rows(
                _without(c.typed, [rid for rid in asked if home.get(rid) is c]),
                rows.get(c.path, ()),
                c.name,
            )
            for c in skill.chapters
            if any(home.get(rid) is c for rid in asked)
        }
        created = _placed(skill, moving, home, edited)
        deleted = frozenset(
            path for path, c in edited.items() if not c.rules and not c.sections
        )
        sigma: dict[RuleId, RuleId] = {}
        spelled: dict[str, set[str]] = {}
        held = [
            (c.path, stems.get(c.path.stem, c.path.stem), edited.get(c.path, c.typed))
            for c in skill.chapters
            if c.path not in deleted
        ]
        held += [(path, path.stem, c) for path, c in created.items()]
        for _, stem, typed in held:
            code = vocabulary.code_for(stem)
            kept = typed.rules
            if kept and not code:
                msg = f"`{stem}.md` has no family code, and it holds rules"
                raise ReviseError(msg)
            for i, rule in enumerate(kept, 1):
                sigma[rule.id] = RuleId(skill.prefix, code, i)
                if rule.id in moving:
                    continue  # a move renames no family, though it leaves one
                was = f"{rule.id.standard}-{rule.id.family}"
                spelled.setdefault(was, set()).add(f"{skill.prefix}-{code}")
        families = {
            old: new
            for old, (new, *more) in ((k, sorted(v)) for k, v in spelled.items())
            if not more and new != old
        }
        moves = {
            c.path: c.path.with_name(f"{stems[c.path.stem]}.md")
            for c in skill.chapters
            if c.path.stem in stems
        }
        merged = {
            rid: sigma.get(into, into)
            for rid, into in asked.items()
            if isinstance(into, RuleId)
        }
        gone: dict[RuleId, Demoted | Removed] = {
            rid: Demoted(b.tool, b.lint) if isinstance(b, LintRow) else b
            for rid, b in asked.items()
            if isinstance(b, (LintRow, Removed))
        }
        core = {rid: b for rid, b in asked.items() if rid not in home}
        skill_md = _core_edited(skill, core, home) if core else None
        if created or deleted:
            md = skill_md or skill.doc
            skill_md = _remapped(skill, md, created, deleted)
        return cls(
            skill,
            moves,
            edited,
            sigma,
            merged,
            gone,
            families,
            stems,
            skill_md,
            created,
            deleted,
            frozenset(moving),
        )

    @property
    def renamed(self) -> dict[RuleId, layer.Becomes]:
        """Every old ID the revision changes, and what it is now."""
        moved = {old: new for old, new in self.sigma.items() if old != new}
        return moved | self.merged | self.gone

    @property
    def ids(self) -> dict[RuleId, RuleId]:
        """What every rule ID a citation can keep is respelled as."""
        return {old: new for old, new in self.sigma.items() if old != new} | self.merged

    def now(self, rid: RuleId) -> layer.Becomes | None:
        """What `rid`, if it names a rule before the revision, is after.

        A core rule keeps its ID unless the plan names it: core rules
        are `SKILL.md`'s, not a family's, so no renumbering moves one,
        and one with an inserted letter keeps it. None for an ID that
        names no rule.
        """
        if rid in self.renamed:
            return self.renamed[rid]
        if rid in self.sigma or rid in self.skill.ids:
            return rid
        return None

    def name_renames(self) -> None:
        """Name `renames.md` in the migration chapter, if this opens it.

        The migration chapter is where a reader holding an old ID is
        sent, so the file the revision opens is named there, once.
        """
        if not self.renamed or self.skill.renames_md.is_file():
            return
        migration = next(
            (
                c
                for c in self.skill.chapters
                if self.stems.get(c.path.stem, c.path.stem) == "migration"
            ),
            None,
        )
        if migration is None:
            msg = (
                f"{self.skill.name} has no references/migration.md to name "
                "references/renames.md in"
            )
            raise ReviseError(msg)
        typed = self.edited.get(migration.path, migration.typed)
        if "renames.md" in str(typed.doc()):
            return
        scope = (*typed.scope, Paragraph(words(NAMED)))
        self.edited[migration.path] = layer.Chapter(
            typed.title, scope, typed.contents, typed.sections
        )

    def renames(self, doc: Doc | None) -> str | None:
        """`renames.md` carried through the revision; None if unchanged.

        `doc` is the file as it stands with its prose respelled, or None
        when there is no file yet. Each table maps the IDs from before
        one revision to the IDs now, so every change moves each of its
        originals forward; the table for this revision is started if
        an ID changed and it is missing.
        """
        title = heading(self.skill)
        if doc is None:
            if not self.renamed:
                return None
            doc = Doc(None, (Heading(1, TITLE), Paragraph(words(SCOPE))))
        read = layer.Chapter.read(doc)
        sections = [
            _carried(s, self.now) if RENAMED.fullmatch(s.title) else s
            for s in read.sections
        ]
        core = self._core_renamed()
        sections = [
            _extended(s, core, self.now) if s.title == title and core else s
            for s in sections
        ]
        if self.renamed and not any(s.title == title for s in sections):
            sections.append(self._started(title))
        new = layer.Chapter(read.title, read.scope, read.contents, tuple(sections))
        text = str(new.doc())
        on_disk = self.skill.renames_md
        return None if on_disk.is_file() and text == on_disk.read_text() else text

    def _core_renamed(self) -> tuple[RuleId, ...]:
        """Every core rule, when the plan names any of them; else none.

        A table that records one core rule states the core family's
        range, so its unlisted core IDs read as unchanged, which they
        are.
        """
        core = tuple(r.id for r in self.skill.core)
        return core if any(rid in self.renamed for rid in core) else ()

    def _started(self, title: str) -> layer.Section:
        """The table for this revision: the ranges, and what changed."""
        before = [*(r.id for r in self.skill.chapter_rules), *self._core_renamed()]
        rows = tuple(
            (f"`{rid}`", print_becomes(now))
            for rid in before
            if (now := self.now(rid)) is not None and now != rid
        )
        table = Table(_RENAME_HEADER, (Align.NONE, Align.NONE), rows)
        lead = Paragraph(words(_RANGES.format(_stated(before))))
        return layer.Section(title, (lead, table), ())

    def verify(self, writes: Mapping[Path, str], swap: Callable[[str], str]) -> None:
        """Each kept rule has its title under its new ID, and only they.

        Read from the text that would be written, so the whole rewrite
        is checked and not only the map it was built from. A title can
        itself cite a rule, so the title expected is the old one with
        the same rewrite applied.
        """
        after: dict[RuleId, str] = {}
        kept = [
            (c.name, c.typed, writes.get(self.moves.get(c.path, c.path)))
            for c in self.skill.chapters
            if c.path not in self.deleted
        ]
        kept += [
            (path.name, typed, writes[path]) for path, typed in self.created.items()
        ]
        for name, was, text in kept:
            try:
                typed = was if text is None else layer.Chapter.read(Doc.parse(text))
            except ValueError as e:
                msg = f"the revision would leave `{name}` unreadable: {e}"
                raise ReviseError(msg) from None
            after |= {r.id: r.title for r in typed.rules}
        titles = {r.id: r.title for r in self.skill.chapter_rules}
        wrong = [
            f"{old} → {new}: `{titles[old]}` became `{after.get(new, 'nothing')}`"
            for old, new in self.sigma.items()
            if after.get(new) != swap(titles[old])
        ]
        if wrong:
            raise ReviseError(
                "a citation would change meaning:\n  " + "\n  ".join(wrong[:10])
            )
        if len(after) != len(self.sigma):
            msg = f"{len(self.sigma)} rules kept and {len(after)} after the rewrite"
            raise ReviseError(msg)


def _reprojected(std: _Standard, writes: Mapping[Path, str]) -> str | None:
    """`SKILL.md` with section 4 rendered from the chapters as written.

    As `fmt` renders it (normalize-the-standards, decision 7): the rules
    section 4 lists, grouped by chapter in section 6's order, each line
    its rule's. None when section 4 is no list to render, which
    `skeleton` reports, or renders as it stands.
    """
    path = std.skill.skill_md
    md = layer.SkillMd.read(Doc.parse(writes.get(path) or path.read_text()))
    title = shared.skill_sections(std.skill)[4]
    at = next((i for i, s in enumerate(md.sections) if s.title == title), None)
    ids = listed(md.sections[at].blocks()[1:]) if at is not None else None
    if at is None or ids is None:
        return None
    was = {new: old for old, new in std.moves.items()}
    chapters: list[Mapped] = []
    for stem in _map_stems(md):
        chapter = std.skill.root / REFERENCES / f"{stem}.md"
        if not vocabulary.code_for(stem) or chapter in std.deleted:
            continue
        on_disk = was.get(chapter, chapter)
        text = writes.get(chapter) or (on_disk.read_text() if on_disk.is_file() else "")
        typed = layer.Chapter.read(Doc.parse(text))
        entries = tuple(layer.Entry(r.id, r.tier, r.title) for r in typed.rules)
        chapters.append((typed.title, entries))
    section = md.sections[at]
    rendered = layer.Section(title, projection(ids, chapters), (), section.line)
    sections = (*md.sections[:at], rendered, *md.sections[at + 1 :])
    text = str(layer.SkillMd(md.frontmatter, md.title, md.preamble, sections).doc())
    return text if text != (writes.get(path) or path.read_text()) else None


#: A row of section 6 names its chapter's file: `references/errors.md`.
_MAPPED = re.compile(rf"`{REFERENCES}/(?P<stem>[a-z0-9-]+)\.md`")


def _map_stems(md: layer.SkillMd) -> list[str]:
    """The chapter each row of section 6 names, in its order."""
    section = next((s for s in md.sections if s.title == shared.MAP), None)
    tables = [b for b in section.lead if isinstance(b, Table)] if section else []
    rows = tables[0].rows if tables else ()
    return [m["stem"] for row in rows if row and (m := _MAPPED.fullmatch(row[0]))]


def _readable(skill: Skill) -> None:
    """Every chapter reads as one, and only `renames.md` has a table.

    A chapter the layer refuses reads as one with no rules, which would
    renumber as if it had none. A rename table anywhere else would not
    be carried through the revision.
    """
    for c in skill.chapters:
        if c.refused is not None:
            msg = f"`{c.name}` does not read as a chapter: {c.refused}"
            raise ReviseError(msg)
    elsewhere = [
        c.name for c in skill.chapters if c.path != skill.renames_md and c.typed.renames
    ]
    if any(RENAMED.fullmatch(s.title) for s in skill.typed.sections):
        elsewhere.append(SKILL_MD)
    if elsewhere:
        msg = (
            f"{skill.name} keeps a rename table in {', '.join(elsewhere)}; "
            "every one belongs in references/renames.md"
        )
        raise ReviseError(msg)


def _stems(skill: Skill, chapters: Mapping[str, str]) -> dict[str, str]:
    """The chapters of `skill` that `chapters` renames, stem to stem."""
    have = {c.path.stem for c in skill.chapters}
    stems = {old: new for old, new in chapters.items() if old in have and old != new}
    for old, new in stems.items():
        if vocabulary.RENAMES in (old, new):
            msg = "`renames.md` is the rename history, not a chapter to rename"
            raise ReviseError(msg)
        if not vocabulary.allowed(new):
            msg = f"`{new}` is not a chapter name in the shared vocabulary"
            raise ReviseError(msg)
    targets = [stems.get(s, s) for s in have]
    if len(set(targets)) != len(targets):
        msg = f"two chapters of {skill.name} would share a name: {sorted(targets)}"
        raise ReviseError(msg)
    return stems


def _rows(
    skill: Skill, asked: Mapping[RuleId, Becomes], home: Mapping[RuleId, Chapter]
) -> dict[Path, list[LintRow]]:
    """Each chapter's new lint rows, every entry of `asked` checked.

    A rule merges into a chapter rule this standard keeps; a row it
    becomes is added to its chapter unless the standard lists that lint
    already, and then it has to be the row listed. A core rule merges
    or goes: it abbreviated a chapter rule, and a row is a chapter's.
    """
    kept = {r for r in home if r not in asked}
    core = {r.id for r in skill.core}
    listed = {(r.tool, r.lint): r for c in skill.chapters for r in c.typed.tools}
    out: dict[Path, list[LintRow]] = {}
    for rid, becomes in asked.items():
        if rid not in home and rid not in core:
            msg = f"{skill.name} has no chapter rule or core rule {rid}"
            raise ReviseError(msg)
        if rid in core and isinstance(becomes, LintRow):
            msg = (
                f"{rid} is a core rule: it merges into the chapter rule it "
                "abbreviated, or goes, and a lint row is a chapter's"
            )
            raise ReviseError(msg)
        match becomes:
            case RuleId() if becomes not in kept:
                msg = f"{rid}: {becomes} is not a chapter rule this standard keeps"
                raise ReviseError(msg)
            case Removed(reason) if not reason.strip():
                msg = f"{rid}: a removal needs its reason"
                raise ReviseError(msg)
            case LintRow():
                key = Demoted(becomes.tool, becomes.lint)
                if parse_becomes(print_becomes(key)) != key:
                    msg = f"{rid}: `{key.tool}:{key.lint}` is not a lint a row can name"
                    raise ReviseError(msg)
                have = listed.setdefault((key.tool, key.lint), becomes)
                if have is becomes:
                    out.setdefault(home[rid].path, []).append(becomes)
                elif (have.level, have.forbids) != (becomes.level, becomes.forbids):
                    msg = (
                        f"{rid}: `{key.tool}:{key.lint}` is listed already, at "
                        f"{have.level}, and the plan's row says otherwise"
                    )
                    raise ReviseError(msg)
            case _:
                pass
    return out


def _without(chapter: layer.Chapter, gone: Collection[RuleId]) -> layer.Chapter:
    """`chapter` without the rules in `gone` and their contents entries.

    A section left with nothing in it goes too, with its label in the
    contents. A section that says something besides its rules stays.
    """
    if not gone:
        return chapter
    sections: list[layer.Section] = []
    emptied: set[str] = set()
    for s in chapter.sections:
        rules = tuple(r for r in s.rules if r.id not in gone)
        if s.rules and not rules and not s.lead:
            emptied.add(s.title)
            continue
        sections.append(layer.Section(s.title, s.lead, rules, s.line))
    contents = chapter.contents
    if contents is not None:
        items = _pruned(contents.items, gone, emptied)
        contents = layer.Contents(items, contents.loose, contents.line)
    return layer.Chapter(chapter.title, chapter.scope, contents, tuple(sections))


def _core_edited(
    skill: Skill, core: Mapping[RuleId, Becomes], home: Mapping[RuleId, Chapter]
) -> Doc:
    """`SKILL.md` with each core rule `core` names turned into a line.

    A core rule merged into the chapter rule it abbreviated becomes that
    rule's line, `ID [T] title`, as section 4 lists a chapter rule once
    it states none of its own (normalize-the-standards, decision 7); a
    removed one goes. Written with the rule's ID before the revision,
    which the rewrite then respells with every other citation.
    """
    lines: dict[RuleId, Item | None] = {}
    for rid, becomes in core.items():
        if isinstance(becomes, RuleId):
            rule = next(r for r in home[becomes].typed.rules if r.id == becomes)
            lines[rid] = layer.Entry(rule.id, rule.tier, rule.title).item()
        else:
            lines[rid] = None
    md = skill.typed
    sections = tuple(
        layer.Section(
            s.title,
            tuple(b for b in (_core_lines(b, lines) for b in s.lead) if b is not None),
            s.rules,
            s.line,
        )
        if s.title.startswith("4. ")
        else s
        for s in md.sections
    )
    return layer.SkillMd(md.frontmatter, md.title, md.preamble, sections).doc()


def _core_lines(block: Block, lines: Mapping[RuleId, Item | None]) -> Block | None:
    """`block` with each core rule `lines` names as its line.

    None when that leaves a list with no item.
    """
    if not isinstance(block, ListBlock):
        return block
    items: list[Item] = []
    for item in block.items:
        rule = layer.core_rule(item)
        if rule is None or rule.id not in lines:
            items.append(item)
        elif (line := lines[rule.id]) is not None:
            items.append(line)
    if not items:
        return None
    return ListBlock(tuple(items), block.start, block.loose, block.line)


def _pruned(
    items: tuple[layer.Group | layer.Entry, ...],
    gone: Collection[RuleId],
    emptied: Collection[str],
) -> tuple[layer.Group | layer.Entry, ...]:
    """Contents `items` without `gone`'s entries and emptied labels."""
    out: list[layer.Group | layer.Entry] = []
    for item in items:
        if isinstance(item, layer.Entry):
            if item.id not in gone:
                out.append(item)
            continue
        children = _pruned(item.children, gone, emptied)
        if item.children and not children and item.label.strip("*") in emptied:
            continue
        out.append(layer.Group(item.label, children, item.line))
    return tuple(out)


def _with_rows(
    chapter: layer.Chapter, rows: Sequence[LintRow], name: str
) -> layer.Chapter:
    """`chapter` with `rows` in its `Decided by tools` table.

    The table is started if there is none — in a section of its own at
    the chapter's end, named last in its contents, or under a `Decided
    by tools` heading that has no table yet, after what it says or the
    lead when it says nothing.
    """
    if not rows:
        return chapter
    cells = tuple(
        tuple(
            c.replace("|", "\\|") for c in (r.tool, f"`{r.lint}`", r.level, r.forbids)
        )
        for r in rows
    )
    lead = Paragraph(words(COMPILER_LEAD if rows[0].tool in compilers() else LEAD))
    fresh = Table(_LINT_HEADER, (Align.NONE,) * len(_LINT_HEADER), cells)
    sections = list(chapter.sections)
    contents = chapter.contents
    at = next((i for i, s in enumerate(sections) if s.title == DECIDED), None)
    if at is None:
        if contents is None:
            msg = f"`{name}` has no contents list to name its new table in"
            raise ReviseError(msg)
        sections.append(layer.Section(DECIDED, (lead, fresh), ()))
        items = (*contents.items, layer.Group(DECIDED, ()))
        contents = layer.Contents(items, contents.loose, contents.line)
    else:
        s = sections[at]
        k = next((i for i, b in enumerate(s.lead) if isinstance(b, Table)), None)
        if k is None:
            said = any(isinstance(b, Paragraph) for b in s.lead)
            body = (*s.lead, *(() if said else (lead,)), fresh)
        else:
            old = s.lead[k]
            assert isinstance(old, Table)  # noqa: S101 — `k` found it as one
            grown = Table(old.header, old.align, (*old.rows, *cells), old.line)
            body = (*s.lead[:k], grown, *s.lead[k + 1 :])
        sections[at] = layer.Section(s.title, body, s.rules, s.line)
    return layer.Chapter(chapter.title, chapter.scope, contents, tuple(sections))


#: What a chapter a move creates opens with, where its scope belongs:
#: a paragraph that is no `Scope:`, so `skeleton` fails the chapter
#: until its author has written what it owns.
UNSCOPED = (
    "TODO: write this chapter's `Scope:` paragraph — what it owns, and which chapters "
    "neighbour it — in place of this one."
)

#: What a chapter a move creates says it covers in section 6, until its
#: author says otherwise.
UNCOVERED = "TODO"


def _placed(
    skill: Skill,
    moving: Mapping[RuleId, Moved],
    home: Mapping[RuleId, Chapter],
    edited: dict[Path, layer.Chapter],
) -> dict[Path, layer.Chapter]:
    """Put each moved rule in its place, in plan order: new chapters.

    `edited` already holds each source chapter without the rules that
    leave it, and gains each target chapter with them. A target the
    standard does not ship is created in the chapter template: its
    title the vocabulary word, its scope `UNSCOPED`. Returned are the
    chapters created, by the path each will have.
    """
    created: dict[Path, layer.Chapter] = {}
    shipped = {c.path.stem: c for c in skill.chapters}
    for rid, moved in moving.items():
        source = home.get(rid)
        if source is None:
            msg = f"{skill.name} has no chapter rule {rid}; only a chapter rule moves"
            raise ReviseError(msg)
        if not vocabulary.code_for(moved.chapter):
            msg = f"{rid}: `{moved.chapter}` is no chapter the vocabulary gives a code"
            raise ReviseError(msg)
        if moved.chapter == source.path.stem:
            msg = f"{rid} is in `{source.name}` already"
            raise ReviseError(msg)
        rule = next(r for r in source.typed.rules if r.id == rid)
        if (target := shipped.get(moved.chapter)) is not None:
            path = target.path
            into = edited.get(path, target.typed)
        else:
            path = skill.root / REFERENCES / f"{moved.chapter}.md"
            into = created.get(path) or layer.Chapter(
                moved.chapter.capitalize(),
                (Paragraph(words(UNSCOPED)),),
                layer.Contents(()),
                (),
            )
        placed = _inserted(into, rule, moved.after)
        (created if target is None else edited)[path] = placed
    return created


def _inserted(
    chapter: layer.Chapter, rule: layer.Rule, after: RuleId | str
) -> layer.Chapter:
    """`chapter` with `rule` after `after`, or opening a section.

    A section title the chapter has no section for opens a new one,
    before `Decided by tools`, which a chapter states last. The rule's
    contents line goes where the rule does: after the line of the rule
    it follows, or first under the section's label, or before the line
    of the section's first rule when the contents has no labels.
    """
    entry = layer.Entry(rule.id, rule.tier, rule.title)
    if chapter.contents is None:
        msg = f"{rule.id}: the target chapter has no contents to list it in"
        raise ReviseError(msg)
    sections = list(chapter.sections)
    items = chapter.contents.items
    if isinstance(after, RuleId):
        at = next(
            (i for i, s in enumerate(sections) if any(r.id == after for r in s.rules)),
            None,
        )
        if at is None or after == rule.id:
            msg = f"{rule.id}: {after} is no other rule of the chapter it moves to"
            raise ReviseError(msg)
        s = sections[at]
        k = next(i for i, r in enumerate(s.rules) if r.id == after) + 1
        sections[at] = layer.Section(
            s.title, s.lead, (*s.rules[:k], rule, *s.rules[k:]), s.line
        )
        items = _listed_after(items, after, entry)
    else:
        at = next((i for i, s in enumerate(sections) if s.title == after), None)
        if at is None:
            last = len(sections) - (bool(sections) and sections[-1].title == DECIDED)
            sections.insert(last, layer.Section(after, (), (rule,)))
            items = _labelled(items, layer.Group(f"**{after}**", (entry,)))
        else:
            s = sections[at]
            first = s.rules[0].id if s.rules else None
            sections[at] = layer.Section(s.title, s.lead, (rule, *s.rules), s.line)
            items = _opened(items, after, first, entry)
    contents = layer.Contents(items, chapter.contents.loose, chapter.contents.line)
    return layer.Chapter(chapter.title, chapter.scope, contents, tuple(sections))


def _listed_after(
    items: tuple[layer.Group | layer.Entry, ...], after: RuleId, entry: layer.Entry
) -> tuple[layer.Group | layer.Entry, ...]:
    """Contents `items`, `entry` after `after`'s line, where it is."""
    out, found = _after(items, after, entry)
    if not found:
        msg = f"{entry.id}: the contents list no line for {after} to follow"
        raise ReviseError(msg)
    return out


def _after(
    items: tuple[layer.Group | layer.Entry, ...], after: RuleId, entry: layer.Entry
) -> tuple[tuple[layer.Group | layer.Entry, ...], bool]:
    """Contents `items`, `entry` after `after`'s line; was it there?"""
    out: list[layer.Group | layer.Entry] = []
    found = False
    for item in items:
        if isinstance(item, layer.Entry):
            out.append(item)
            if item.id == after:
                out.append(entry)
                found = True
        else:
            children, inner = _after(item.children, after, entry)
            found |= inner
            out.append(layer.Group(item.label, children, item.line))
    return tuple(out), found


def _labelled(
    items: tuple[layer.Group | layer.Entry, ...], group: layer.Group
) -> tuple[layer.Group | layer.Entry, ...]:
    """Contents `items`, a new section's `group` before the tools'."""
    last = len(items) - (
        bool(items)
        and isinstance(items[-1], layer.Group)
        and items[-1].label == DECIDED
    )
    return (*items[:last], group, *items[last:])


def _opened(
    items: tuple[layer.Group | layer.Entry, ...],
    title: str,
    first: RuleId | None,
    entry: layer.Entry,
) -> tuple[layer.Group | layer.Entry, ...]:
    """Contents `items`, `entry` first among section `title`'s."""
    out: list[layer.Group | layer.Entry] = []
    placed = False
    for item in items:
        if isinstance(item, layer.Group) and item.label.strip("*") == title:
            out.append(layer.Group(item.label, (entry, *item.children), item.line))
            placed = True
        elif isinstance(item, layer.Entry) and item.id == first and not placed:
            out += [entry, item]
            placed = True
        else:
            out.append(item)
    if not placed:
        msg = f"{entry.id}: the contents list nothing for `## {title}` to open"
        raise ReviseError(msg)
    return tuple(out)


def _remapped(
    skill: Skill,
    md: Doc,
    created: Mapping[Path, layer.Chapter],
    deleted: Collection[Path],
) -> Doc:
    """`SKILL.md` with section 6 naming the chapters the plan leaves.

    A created chapter's row goes before the migration chapter's, which
    the reference map keeps last of the chapters of rules; a deleted
    chapter's row goes. Each row names its family and its count of
    rules, which the rewrite then restates with every other count.
    """
    typed = layer.SkillMd.read(md)
    gone = {f"`{REFERENCES}/{p.name}`" for p in deleted}
    rows_new = [
        (
            f"`{REFERENCES}/{p.name}`",
            f"`{skill.prefix}-{vocabulary.code_for(p.stem)}` ({len(c.rules)})",
            UNCOVERED,
        )
        for p, c in created.items()
    ]
    sections = []
    for s in typed.sections:
        if s.title != shared.MAP:
            sections.append(s)
            continue
        lead = []
        for block in s.lead:
            if not isinstance(block, Table):
                lead.append(block)
                continue
            rows = [r for r in block.rows if not r or r[0] not in gone]
            last = f"`{REFERENCES}/{_MIGRATION}`"
            at = next((i for i, r in enumerate(rows) if r and r[0] == last), len(rows))
            rows[at:at] = rows_new
            lead.append(Table(block.header, block.align, tuple(rows), block.line))
        sections.append(layer.Section(s.title, tuple(lead), s.rules, s.line))
    return layer.SkillMd(
        typed.frontmatter, typed.title, typed.preamble, tuple(sections)
    ).doc()


#: The migration chapter, which the reference map lists last of those
#: that hold rules.
_MIGRATION = "migration.md"


def _carried(
    section: layer.Section, now: Callable[[RuleId], layer.Becomes | None]
) -> layer.Section:
    """A rename table's section, carried through one revision.

    Each original the ranges state goes where its row leads, or stays
    itself without one, and then wherever the revision moves that; a
    row is kept only where the result differs from the original. An
    original that names no rule any more is a rule deleted without its
    disposition, and stops the run: nothing else knows what it became.
    A row the table cannot read is kept as written.
    """
    table = RenameTable.read(section)
    if not table.ranges:
        msg = f"`{table.heading}` states no ranges, so its unlisted IDs are lost"
        raise ReviseError(msg)
    listed = {r.before: r.now for r in table.rows}
    order = dict.fromkeys((*table.originals, *listed))
    rows: list[tuple[str, ...]] = []
    for rid in order:
        was = listed.get(rid, rid)
        if isinstance(was, RuleId):
            moved = now(was)
            if moved is None and rid not in listed:
                msg = (
                    f"{rid} has no row, so the table says it is unchanged, and no "
                    "rule carries it — record what it became first"
                )
                raise ReviseError(msg)
            if moved is None:
                msg = (
                    f"{rid} became {was}, which no longer exists — record what it "
                    "became (a rule ID, lint `tool:name`, or removed — reason) first"
                )
                raise ReviseError(msg)
            was = moved
        if was != rid:
            rows.append((f"`{rid}`", print_becomes(was)))
    unread = set(table.unread)
    lead = list(section.lead)
    k = next((i for i, b in enumerate(lead) if isinstance(b, Table)), len(lead))
    old = lead[k] if k < len(lead) else Table(_RENAME_HEADER, (Align.NONE,) * 2, ())
    assert isinstance(old, Table)  # noqa: S101 — `k` found it as one, or made it
    rows += [
        row
        for row in old.rows
        if len(row) != len(_RENAME_HEADER)
        or tuple(c.replace("\\|", "|") for c in row) in unread
    ]
    # A table with no rows keeps its header; none is started for none.
    if k < len(lead) or rows:
        lead[k : k + 1] = [Table(old.header, old.align, tuple(rows), old.line)]
    return layer.Section(section.title, tuple(lead), section.rules, section.line)


def _extended(
    section: layer.Section,
    core: Sequence[RuleId],
    now: Callable[[RuleId], layer.Becomes | None],
) -> layer.Section:
    """This revision's table, its ranges and rows grown by `core`.

    A core rule merged or removed after the table was started is an
    original the table did not state: its family's range joins the
    ranges, and a row says what each became. The sentence stating the
    ranges is the one a revision writes, and is restated; a lead that
    states them otherwise stops the run rather than being rewritten.
    """
    table = RenameTable.read(section)
    extra = [rid for rid in core if rid not in table.originals]
    if not extra:
        return section
    at = next(i for i, b in enumerate(section.lead) if isinstance(b, Table))
    said = [b for b in section.lead[:at] if isinstance(b, Paragraph)]
    stated = " ".join(words(_RAN.format(_stated(table.originals))))
    if len(said) != 1 or stated not in (text := " ".join(said[0].words)):
        msg = (
            f"`{table.heading}` states its ranges otherwise than a revision writes "
            "them, so the core family cannot join them"
        )
        raise ReviseError(msg)
    grown_ranges = _RAN.format(_stated([*table.originals, *extra]))
    ranges = Paragraph(words(text.replace(stated, grown_ranges, 1)))
    old = section.lead[at]
    assert isinstance(old, Table)  # noqa: S101 — `at` found it as one
    rows = tuple(
        (f"`{rid}`", print_becomes(becomes))
        for rid in extra
        if (becomes := now(rid)) is not None and becomes != rid
    )
    grown = Table(old.header, old.align, (*old.rows, *rows), old.line)
    lead = tuple(
        ranges if b is said[0] else grown if b is old else b for b in section.lead
    )
    return layer.Section(section.title, lead, section.rules, section.line)


def _stated(ids: Sequence[RuleId]) -> str:
    """The runs of consecutive numbers each family held, as prose.

    In the order the families appear. A suffixed ID such as `-03a` is a
    run of its own, between the numbers it sits between, so the ranges
    state every ID the rows list; dense numbering always gives it a row.
    """
    held: dict[tuple[str, str], list[RuleId]] = {}
    for rid in ids:
        held.setdefault((rid.standard, rid.family), []).append(rid)
    runs: list[tuple[RuleId, RuleId]] = []
    for family in held.values():
        for rid in sorted(family):
            last = runs[-1][1] if runs else None
            if (
                last is not None
                and (last.standard, last.family) == (rid.standard, rid.family)
                and not (last.suffix or rid.suffix)
                and last.number == rid.number - 1
            ):
                runs[-1] = (runs[-1][0], rid)
            else:
                runs.append((rid, rid))
    spans = [print_range(lo, hi) for lo, hi in runs]
    if len(spans) > 1:
        return ", ".join(spans[:-1]) + f" and {spans[-1]}"
    return "".join(spans)


# ------------------------------------------------------------------ the
# rewrite


class _Rewrite:
    """The one rewrite: renumbering, merges, families, chapter paths.

    Built once, from every standard being revised, and applied to every
    file, so each citation is rewritten exactly once.
    """

    def __init__(self, standards: Sequence[_Standard]) -> None:
        """The rewrite every standard in `standards` asks for."""
        self.standards = standards
        self.ids = {k: v for s in standards for k, v in s.ids.items()}
        self.families = {k: v for s in standards for k, v in s.families.items()}
        self._swaps: dict[int, Callable[[str], str]] = {}

    def swap(self, own: _Standard | None) -> Callable[[str], str]:
        """The rewrite of one text, in `own`'s files or another's.

        A bare `references/x.md` is rewritten only in a standard's own
        files, where it can mean nothing but that standard's chapter;
        elsewhere only a path that names the skill is.
        """
        key = id(own)
        if key not in self._swaps:
            paths = [
                (_paths(s, bare=s is own), s.stems) for s in self.standards if s.stems
            ]

            def swap(text: str) -> str:
                text = respell(text, self.ids, self.families)
                for pattern, stems in paths:
                    text = pattern.sub(lambda m, stems=stems: _moved(m, stems), text)
                return text

            self._swaps[key] = swap
        return self._swaps[key]


def _paths(std: _Standard, *, bare: bool) -> re.Pattern[str]:
    """A path to a chapter `std` renames: with its skill, or bare."""
    olds = "|".join(re.escape(old) for old in std.stems)
    skill = re.escape(std.skill.name)
    if bare:
        return re.compile(rf"(?:(?<={skill}/)|(?<![\w/-]))references/({olds})\.md")
    return re.compile(rf"(?<={skill}/)references/({olds})\.md")


def _moved(m: re.Match[str], stems: Mapping[str, str]) -> str:
    """The path `m` matched, to the chapter's new name."""
    return f"references/{stems[m.group(1)]}.md"


def _respelled(doc: Doc, swap: Callable[[str], str], *, keep: bool) -> Doc:
    """`doc` with every text in it rewritten, history kept if `keep`."""
    blocks = tuple(
        block if keep and held else _block(block, swap) for block, held in history(doc)
    )
    front = None if doc.frontmatter is None else swap(doc.frontmatter)
    return Doc(front, blocks)


def _block(block: Block, swap: Callable[[str], str]) -> Block:
    """`block` with every text it holds rewritten by `swap`."""
    out: Block = block
    match block:
        case Heading(level, text, line):
            out = Heading(level, swap(text), line)
        case Paragraph(said, line):
            out = Paragraph(tuple(swap(w) for w in said), line)
        case Fence(info, body, line, closed):
            out = Fence(info, swap(body), line, closed)
        case Table(header, align, rows, line):
            cells = tuple(tuple(swap(c) for c in row) for row in rows)
            out = Table(tuple(swap(c) for c in header), align, cells, line)
        case ListBlock(items, start, loose, line):
            inner = tuple(
                Item(tuple(_block(b, swap) for b in i.blocks), i.line) for i in items
            )
            out = ListBlock(inner, start, loose, line)
        case Quote(blocks, alert, line):
            out = Quote(tuple(_block(b, swap) for b in blocks), alert, line)
        case _:
            pass
    return out


# ------------------------------------------------------------------ the
# repository


#: The suffixes of the files a citation can live in; "" is a file with
#: none, such as a `LICENSE`.
_TEXT = {".md", ".toml", ".yml", ".yaml", ".zig", ".zon", ".py", ".rs", ""}


def corpus(repo: Path) -> list[Path]:
    """Every file a citation can live in.

    The abstract standard is one: each realisation row names a rule.
    The archived OpenSpec changes are history, and keep the IDs they
    were written with.
    """
    skills = repo / SKILLS
    out = [p for p in sorted(skills.rglob("*")) if p.is_file() and p.suffix in _TEXT]
    out += sorted((repo / ABSTRACT).glob("*.md"))
    out += sorted((repo / "src").rglob("*.py")) + sorted((repo / "tests").rglob("*.py"))
    readme = repo / "README.md"
    return out + ([readme] if readme.is_file() else [])


class _Corpus:
    """Every file of the repository, read once and rewritten once.

    What each cites is gathered from the text as the plan leaves it and
    before it is respelled: the plan has already taken a removed rule's
    heading and contents entry away, so what still cites it is a
    citation the plan would strand.
    """

    def __init__(
        self, repo: Path, standards: Sequence[_Standard], rewrite: _Rewrite
    ) -> None:
        """Read and rewrite every file of `repo`."""
        self.repo = repo
        self.standards = standards
        #: every ID cited under a revised standard's prefix -> where
        self.cites: dict[RuleId, list[Path]] = {}
        #: path after the moves -> its new text, for what changes
        self.writes: dict[Path, str] = {}
        #: each standard's `renames.md`, its prose respelled
        self.renames: dict[Path, Doc] = {}
        #: per path written, what a person should look at
        self.leftovers: dict[Path, list[str]] = {}
        #: files outside the skills that name a renamed chapter bare
        self.unnamed: list[str] = []
        self.prefixes = {s.skill.prefix for s in standards}
        skills = repo / SKILLS
        trees = (skills, repo / ABSTRACT)
        for path in corpus(repo):
            own = next((s for s in standards if _owns(repo, s, path)), None)
            target = own.moves.get(path, path) if own else path
            swap = rewrite.swap(own)
            text = path.read_text()
            new: str | None
            if path.suffix == ".md" and any(t in path.parents for t in trees):
                new, said = self._markdown(path, text, own, swap)
            else:
                new, said = swap(text), text
                if new == text and target == path:
                    new = None
            if own is not None and path in own.deleted:
                new = None
            self._cited(path, said)
            if new is not None:
                self.writes[target] = new
                self.leftovers[target] = self._unknown(path, self._found(said))
            if skills not in path.parents and own is None:
                self.unnamed += _bare(path.relative_to(repo), new or text, standards)
        for std in standards:
            for path, chapter in std.created.items():
                doc = chapter.doc()
                self._cited(path, "\n\n".join(text_of((b,)) for b in doc.blocks))
                self.writes[path] = str(_respelled(doc, rewrite.swap(std), keep=True))

    def _found(self, said: str) -> set[RuleId]:
        """Every ID `said` cites under a revised standard's prefix."""
        return {rid for p in self.prefixes for rid in cited(said, p)}

    def _cited(self, path: Path, said: str) -> None:
        """Record what `said`, the citing text of `path`, cites."""
        where = path.relative_to(self.repo)
        for rid in sorted(self._found(said)):
            self.cites.setdefault(rid, []).append(where)

    def _markdown(
        self, path: Path, text: str, own: _Standard | None, swap: Callable[[str], str]
    ) -> tuple[str | None, str]:
        """A standard's markdown, rewritten through its tree.

        Returns its new text, or None when nothing in it changes, and
        the text whose IDs are citations. A standard's own rename
        tables are history and are kept; another standard's cite this
        one's IDs to say what replaced a rule of its own, which is a
        live citation and follows the revision. Another standard's file
        whose text the rewrite leaves as it is is not read as a tree at
        all: nothing in it would change.
        """
        if own is None and swap(text) == text:
            return None, text
        original = _parsed(path, own) or Doc.parse(text)
        doc = own.edited[path].doc() if own and path in own.edited else original
        cored = own.skill_md if own and path == own.skill.skill_md else None
        if cored is not None:
            doc = cored
        keep = own is not None
        said = "\n\n".join(
            [doc.frontmatter or ""]
            + [text_of((b,)) for b, held in history(doc) if not (keep and held)]
        )
        new = _respelled(doc, swap, keep=keep)
        if own is not None and path == own.skill.skill_md:
            new = _counted(new, own)
        if own is not None and path == own.skill.renames_md:
            self.renames[path] = new
            return None, said
        moved = own is not None and path in own.moves
        edited = own is not None and (path in own.edited or cored is not None)
        if new == original and not (moved or edited):
            return None, said
        return str(new), said

    def _unknown(self, path: Path, found: Collection[RuleId]) -> list[str]:
        """Each citation in `path` of an ID that names no rule."""
        out = []
        for std in self.standards:
            for rid in sorted(found):
                if rid.standard == std.skill.prefix and std.now(rid) is None:
                    if rid.family == vocabulary.CORE:
                        continue
                    out.append(
                        f"{path.relative_to(self.repo)}: cites {rid}, which "
                        f"{std.skill.name} does not define; left as it was"
                    )
        return out


def _owns(repo: Path, std: _Standard, path: Path) -> bool:
    """Is `path` one of `std`'s own files: its skill, or its profile?"""
    module = f"{std.skill.name.replace('-', '_')}.py"
    profile = repo / "src" / "agent_skill" / "profiles" / module
    return std.skill.root in path.parents or path == profile


def _parsed(path: Path, own: _Standard | None) -> Doc | None:
    """`own`'s parse of `SKILL.md` or a chapter, read once already."""
    if own is None:
        return None
    if path == own.skill.skill_md:
        return own.skill.doc
    return next((c.doc for c in own.skill.chapters if c.path == path), None)


def _counted(doc: Doc, std: _Standard) -> Doc:
    """`SKILL.md` with its counts restated from the rules after.

    One count per family in the reference map, and the total in the
    description. A count is the one thing a revision always changes and
    a person always forgets.
    """
    counts: dict[str, int] = {}
    for c in std.skill.chapters:
        code = vocabulary.code_for(std.stems.get(c.path.stem, c.path.stem))
        if code:
            counts[code] = len(std.edited.get(c.path, c.typed).rules)
    total = len(std.sigma) + sum(r.id not in std.renamed for r in std.skill.core)
    prefix = re.escape(std.skill.prefix)
    family = re.compile(rf"`{prefix}-({FAMILY})` \(\d+\)")

    def count(text: str) -> str:
        return family.sub(
            lambda m: (
                f"`{std.skill.prefix}-{m[1]}` ({counts[m[1]]})"
                if m[1] in counts
                else m.group()
            ),
            text,
        )

    front = doc.frontmatter
    if front is not None:
        front = re.sub(r"\b\d+(-rule \w+)", rf"{total}\1", front, count=1)
    return Doc(front, tuple(_block(b, count) for b in doc.blocks))


def _bare(where: Path, text: str, standards: Sequence[_Standard]) -> list[str]:
    """Each renamed chapter `text` names without saying whose it is."""
    return [
        f"{where}: names `references/{old}.md` without its skill"
        for s in standards
        for old in s.stems
        if re.search(rf"(?<![\w/-])references/{re.escape(old)}\.md", text)
    ]


def _refuse(standards: Sequence[_Standard], cites: Mapping[RuleId, list[Path]]) -> None:
    """Stop when a citation would name a rule it did not name before.

    Two ways. A citation of a rule the plan demotes or removes would
    name nothing, or — once dense numbering hands its ID on — the next
    rule down; whether it should name the lint, another rule, or
    nothing is a reading decision. And a citation of an ID that names
    no rule would come to name one if the renumbering gives that ID to
    a rule: left as it was, it silently cites that rule, and nothing
    afterwards can tell it from a correct one.
    """
    stranded = [
        f"{rid}, cited in {', '.join(map(str, cites[rid]))}, is "
        f"{print_becomes(std.gone[rid])} in the plan"
        for std in standards
        for rid in sorted(std.gone.keys() & cites.keys())
    ]
    captured = [
        f"{rid}, cited in {', '.join(map(str, cites[rid]))}, names no rule, and "
        f"would name the rule that is {owner} now"
        for std in standards
        for rid, owner in _owners(std, cites)
    ]
    reasons = []
    if stranded:
        reasons.append(
            "resolve these citations first; the plan takes their rules away:\n  "
            + "\n  ".join(stranded)
        )
    if captured:
        reasons.append(
            "resolve these citations first; renumbering would give each ID to "
            "another rule:\n  " + "\n  ".join(captured)
        )
    if reasons:
        raise ReviseError("\n".join(reasons))


def _owners(
    std: _Standard, cites: Mapping[RuleId, list[Path]]
) -> Iterator[tuple[RuleId, RuleId]]:
    """Each cited ID naming no rule that would name one, and whose."""
    owner = {new: old for old, new in std.sigma.items()}
    for rid in sorted(cites):
        if rid in owner and rid.standard == std.skill.prefix and std.now(rid) is None:
            yield rid, owner[rid]


# ------------------------------------------------------------------ a
# plan, as a file states it


#: The five things a plan's entry can say, each the key of its object.
KINDS = ("rows", "lint", "merge", "remove", "move")

#: How a move's `after` names a section, rather than a rule.
_HEADING = "## "

#: What each kind of entry holds, said as the refusal of anything else.
_SHAPES = {
    "rows": "rows are [[tool, lint, level, forbids]]: the one row the rule becomes",
    "lint": "a lint is [tool, lint]",
    "merge": "a merge names the rule it went into",
    "remove": "a removal needs its reason",
    "move": (
        'a move names the chapter and what the rule follows there: {"move": '
        '"<chapter>", "after": "<rule ID>"}, or "after": "## <section>" to open it'
    ),
}


def read_plan(raw: object, skill: Skill) -> Plan:
    """`raw`, a plan as `json.loads` reads it, as the plan it states.

    It maps each rule ID to an object holding one of `KINDS`:
    `{"rows": [[tool, lint, level, forbids]]}`, the row the rule
    becomes; `{"lint": [tool, lint]}`, a row `skill` lists already;
    `{"merge": "ID"}`, the rule it was folded into; `{"remove":
    "reason"}`; or `{"move": "stem", "after": "ID"}`, the chapter it
    moves to and the rule it follows there, `"after": "## Title"` for
    the first rule of that section. Anything else stops here, before a
    rule is read.
    """
    if not isinstance(raw, dict) or not raw:
        msg = "a plan is a JSON object naming at least one rule"
        raise PlanError(msg)
    listed = {(r.tool, r.lint): r for c in skill.chapters for r in c.typed.tools}
    out: dict[RuleId, Becomes] = {}
    for key, what in raw.items():
        rid = RuleId.try_parse(str(key))
        one = isinstance(what, dict) and len(what) == 1
        kind, value = next(iter(what.items())) if one else ("", "")
        becomes = _entry(str(kind), value) if one else None
        if isinstance(what, dict) and "move" in what:
            kind, becomes = "move", _move_entry(what)
        if rid is None:
            msg = f"{key}: not a rule ID"
            raise PlanError(msg)
        if becomes is None:
            shape = _SHAPES.get(str(kind), f"say exactly one of {', '.join(KINDS)}")
            msg = f"{rid}: {shape}"
            raise PlanError(msg)
        if isinstance(becomes, Demoted):
            row = listed.get((becomes.tool, becomes.lint))
            if row is None:
                msg = (
                    f"{rid}: no chapter lists the lint `{becomes.tool}:{becomes.lint}`"
                )
                raise ReviseError(msg)
            becomes = row
        out[rid] = becomes
    return out


def _entry(kind: str, value: object) -> Becomes | Demoted | None:
    """`{kind: value}` as what it says, or None when it says nothing.

    A `lint` entry names a row by its key, which only the skill can
    complete.
    """
    if kind == "rows" and isinstance(value, list) and len(value) == 1:
        row = value[0]
        if isinstance(row, list) and (cells := _strings(row, 4)) is not None:
            return LintRow(cells[0], cells[1], cells[2], cells[3])
    elif kind == "lint" and isinstance(value, list):
        if (cells := _strings(value, 2)) is not None:
            return Demoted(cells[0], cells[1])
    elif kind == "merge" and isinstance(value, str):
        return RuleId.try_parse(value)
    elif kind == "remove" and isinstance(value, str) and value.strip():
        return Removed(value.strip())
    return None


def _move_entry(what: object) -> Moved | None:
    """`{"move": stem, "after": ID or "## Title"}` as its move."""
    if not isinstance(what, dict):
        return None
    fields: dict[object, object] = dict(what.items())
    if set(fields) != {"move", "after"}:
        return None
    chapter, after = fields["move"], fields["after"]
    if not isinstance(chapter, str):
        return None
    if not isinstance(after, str):
        return None
    if after.startswith(_HEADING) and (title := after.removeprefix(_HEADING).strip()):
        return Moved(chapter, title)
    rid = RuleId.try_parse(after)
    return Moved(chapter, rid) if rid is not None else None


def _strings(value: Sequence[object], n: int) -> list[str] | None:
    """`value` as a list of `n` strings, or None when it is not one."""
    cells: list[str] = [c for c in value if isinstance(c, str)]
    return cells if len(cells) == len(value) == n else None
