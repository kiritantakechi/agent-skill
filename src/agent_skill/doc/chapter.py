"""A standard's files read as what they are: chapters, sections, rules.

A layer over `Doc`, never beside it: every node is built from blocks
the document model parsed, and `doc()` gives those blocks back, so a
chapter read and written again is the file it was. What a rule, a
contents entry or a rename row says is typed here once, from the tree,
rather than matched in raw text by each check that wants it.

A chapter opens with its title, the prose that scopes it, a contents
list and a `---` rule, then its `##` sections; a rule is a `###`
heading naming its ID, tier and title, and runs to the next one or to
the section's end. `SKILL.md` has frontmatter, a title, a preamble and
its numbered sections, and states its core rules as list items in
section 4.
"""

import re
from dataclasses import dataclass, field
from typing import Self

from agent_skill.doc import (
    Block,
    Divider,
    Doc,
    Fence,
    Heading,
    Item,
    ListBlock,
    Paragraph,
    Table,
    words,
)
from agent_skill.ids import RuleId, Tier, rule_id

#: The section a chapter lists its tool-decided claims under.
DECIDED = "Decided by tools"

#: The H2 a contents list sits under.
CONTENTS = "Contents"

#: The H2 a renumbering's rename table sits under, after the revision
#: it names.
RENAMED = re.compile(r"Rule IDs before the .+ revision")

#: The en dash a range of IDs is written with.
DASH = "\u2013"

#: Two IDs joined by the dash, or one ID alone.
_RANGE = re.compile(rf"`({rule_id()})`(?:{DASH}`({rule_id()})`)?")

#: The labels a rule's parts open with, and the shape any label has.
WHY, CHECK, RELAXED = "**Why:**", "**Check:**", "*Relaxed form:*"
_LABEL = re.compile(r"\*\*[^*]+:\*\*|\*Relaxed form:\*")

#: The cells of a `Decided by tools` row: tool, lint, level, forbids.
_LINT_CELLS = 4

#: The cells of a rename row: before, now.
_RENAME_CELLS = 2

#: The tiers' spellings, for telling an entry from a label.
_TIERS = frozenset(str(t) for t in Tier)


def _entry(found: tuple[str, ...]) -> tuple[RuleId, Tier, str] | None:
    """The ID, tier and title `found` opens with, if it opens so."""
    match found:
        case (rid, tier, *title) if re.fullmatch(rule_id(), rid) and tier in _TIERS:
            return RuleId.parse(rid), Tier.parse(tier), " ".join(title)
        case _:
            return None


@dataclass(frozen=True, slots=True)
class Rule:
    """One rule: its ID, tier and title, and the blocks under it.

    A core rule has no title: it is a list item in `SKILL.md` that opens
    with its ID and tier and goes straight to its statement.
    """

    id: RuleId
    tier: Tier
    title: str
    body: tuple[Block, ...]
    line: int = field(default=0, compare=False)

    def _part(self, label: str) -> tuple[Block, ...]:
        """The blocks a label opens, up to the next label or example.

        A heading ends it too. A paragraph without a label carries the
        part on, as a second paragraph of a Why does.
        """
        start = next(
            (
                i
                for i, b in enumerate(self.body)
                if isinstance(b, Paragraph) and b.text.startswith(label)
            ),
            None,
        )
        if start is None:
            return ()
        end = start + 1
        while end < len(self.body) and not _ends_part(self.body[end]):
            end += 1
        return self.body[start:end]

    @property
    def statement(self) -> tuple[Block, ...]:
        """What the rule says: its prose before the first label."""
        out: list[Block] = []
        for block in self.body:
            if _ends_part(block) and not isinstance(block, Fence):
                break
            if not isinstance(block, Fence):
                out.append(block)
        return tuple(out)

    @property
    def relaxed(self) -> tuple[Block, ...]:
        """The relaxed form an `[M!]` rule states, if it states one."""
        return self._part(RELAXED)

    @property
    def why(self) -> tuple[Block, ...]:
        """The rule's Why."""
        return self._part(WHY)

    @property
    def check(self) -> tuple[Block, ...]:
        """The rule's Check."""
        return self._part(CHECK)

    @property
    def examples(self) -> tuple[Fence, ...]:
        """Every fenced example under the rule, in order."""
        return tuple(b for b in self.body if isinstance(b, Fence))

    def heading(self) -> Heading:
        """The `###` heading this rule is read from."""
        return Heading(3, f"{self.id} {self.tier} {self.title}", self.line)


def _ends_part(block: Block) -> bool:
    """Does `block` end the labelled part before it?"""
    if isinstance(block, Paragraph):
        return bool(_LABEL.match(block.text))
    return isinstance(block, (Fence, Heading))


@dataclass(frozen=True, slots=True)
class Section:
    """One `##` section: what precedes its first rule, and its rules."""

    title: str
    lead: tuple[Block, ...]
    rules: tuple[Rule, ...]
    line: int = field(default=0, compare=False)

    def blocks(self) -> tuple[Block, ...]:
        """The section as blocks, its heading first."""
        rules = (b for r in self.rules for b in (r.heading(), *r.body))
        return (Heading(2, self.title, self.line), *self.lead, *rules)


def _sections(blocks: tuple[Block, ...]) -> tuple[Section, ...]:
    """`blocks` read as sections, each opening with its `##` heading.

    A block before the first heading belongs to no section, and is
    refused rather than dropped.
    """
    out: list[Section] = []
    for block in blocks:
        if isinstance(block, Heading) and block.level == _SECTION:
            out.append(Section(block.text, (), (), block.line))
        elif not out:
            msg = f"line {block.line}: a block before the first `##` section"
            raise ValueError(msg)
        else:
            out[-1] = _grow(out[-1], block)
    return tuple(out)


def _grow(section: Section, block: Block) -> Section:
    """`section` with `block` added to its lead or to its last rule."""
    if (found := _rule_heading(block)) is not None:
        rule = Rule(*found, (), block.line)
        return Section(
            section.title, section.lead, (*section.rules, rule), section.line
        )
    if not section.rules:
        return Section(section.title, (*section.lead, block), (), section.line)
    *done, last = section.rules
    grown = Rule(last.id, last.tier, last.title, (*last.body, block), last.line)
    return Section(section.title, section.lead, (*done, grown), section.line)


#: The heading levels of a section and of a rule.
_SECTION, _RULE = 2, 3


def _rule_heading(block: Block) -> tuple[RuleId, Tier, str] | None:
    """The ID, tier and title a `###` heading names, if any."""
    if not isinstance(block, Heading) or block.level != _RULE:
        return None
    found = _entry(words(block.text))
    return found if found and found[2] else None


@dataclass(frozen=True, slots=True)
class Entry:
    """One contents line: the ID, tier and title of a rule."""

    id: RuleId
    tier: Tier
    title: str
    line: int = field(default=0, compare=False)

    def item(self) -> Item:
        """The list item this entry is read from."""
        text = f"{self.id} {self.tier} {self.title}"
        return Item((Paragraph(words(text), self.line),), self.line)


@dataclass(frozen=True, slots=True)
class Group:
    """A label, and the entries and labels listed under it.

    A label names a part of the chapter that is not a rule: a group of
    rules, `Decided by tools`, or a `###` such as zig's `SMELL TEST`.
    """

    label: str
    children: tuple[Group | Entry, ...]
    line: int = field(default=0, compare=False)

    @property
    def entries(self) -> tuple[Entry, ...]:
        """Every entry under this label, at any depth, in order."""
        return _entries(self.children)

    def item(self) -> Item:
        """The list item this group is read from."""
        label = Paragraph(words(self.label), self.line)
        if not self.children:
            return Item((label,), self.line)
        nested = ListBlock(tuple(c.item() for c in self.children), line=self.line)
        return Item((label, nested), self.line)


def _entries(items: tuple[Group | Entry, ...]) -> tuple[Entry, ...]:
    """The entries among `items` and under their labels, in order."""
    return tuple(
        e for i in items for e in (i.entries if isinstance(i, Group) else (i,))
    )


@dataclass(frozen=True, slots=True)
class Contents:
    """A chapter's contents list: groups and entries, in order."""

    items: tuple[Group | Entry, ...]
    loose: bool = False
    line: int = field(default=0, compare=False)

    @property
    def entries(self) -> tuple[Entry, ...]:
        """Every entry, grouped or not, in order."""
        return _entries(self.items)

    def block(self) -> ListBlock:
        """The list this contents is read from."""
        return ListBlock(
            tuple(i.item() for i in self.items), None, self.loose, self.line
        )

    @classmethod
    def read(cls, block: ListBlock) -> Self:
        """The contents a list states.

        Each item is an entry, or a label with entries nested under it.
        """
        return cls(
            tuple(_contents_item(i) for i in block.items), block.loose, block.line
        )


def _contents_item(item: Item) -> Group | Entry:
    """A contents item: an entry, or a label over a tight list."""
    match item.blocks:
        case (Paragraph() as p,) if (found := _entry(p.words)) is not None:
            return Entry(*found, item.line)
        case (Paragraph() as label,):
            return Group(label.text, (), item.line)
        case (Paragraph() as label, ListBlock(start=None, loose=False) as nested):
            children = tuple(_contents_item(i) for i in nested.items)
            return Group(label.text, children, item.line)
        case _:
            msg = f"line {item.line}: a contents item is an entry or a labelled list"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class LintRow:
    """One row of `Decided by tools`: a claim a tool settles alone."""

    tool: str
    lint: str
    level: str
    forbids: str


@dataclass(frozen=True, slots=True)
class Demoted:
    """A rule that became a lint-table row: the tool and its lint."""

    tool: str
    lint: str


@dataclass(frozen=True, slots=True)
class Removed:
    """A rule removed outright, and why."""

    reason: str


#: What an old ID became: another ID, a lint row, or nothing.
type Becomes = RuleId | Demoted | Removed

_DEMOTED = re.compile(r"lint `(?P<tool>[a-z]+):(?P<lint>[^`]+)`")
_REMOVED = re.compile(r"removed —\s*(?P<reason>.*)")


def _becomes(cell: str) -> Becomes:
    """What a rename row's `Now` cell says the old ID became."""
    if m := re.fullmatch(rf"`({rule_id()})`", cell):
        return RuleId.parse(m[1])
    if m := _DEMOTED.fullmatch(cell):
        return Demoted(m["tool"], m["lint"])
    if m := _REMOVED.fullmatch(cell):
        return Removed(m["reason"].strip())
    msg = f"not an ID, a lint row or a removal: {cell!r}"
    raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class Rename:
    """One row of a rename table: an old ID and what it became."""

    before: RuleId
    now: Becomes


@dataclass(frozen=True, slots=True)
class RenameTable:
    """One revision's rename table.

    The ranges the families ran before the revision, and a row for each
    old ID that changed. An ID in range with no row still names the rule
    it named.
    """

    heading: str
    ranges: tuple[tuple[RuleId, RuleId], ...]
    rows: tuple[Rename, ...]

    @property
    def originals(self) -> tuple[RuleId, ...]:
        """Every ID the families ran before the revision, in order."""
        return tuple(
            RuleId(first.standard, first.family, n)
            for first, last in self.ranges
            for n in range(first.number, last.number + 1)
        )


@dataclass(frozen=True, slots=True)
class Chapter:
    """A reference chapter.

    `contents` is None for a chapter that lists no rules, as the review
    protocol does; such a chapter has no `---` after its scope either.
    """

    title: str
    scope: tuple[Block, ...]
    contents: Contents | None
    sections: tuple[Section, ...]

    @classmethod
    def read(cls, doc: Doc) -> Self:
        """The chapter `doc` is."""
        blocks = doc.blocks
        title = ""
        if blocks and isinstance(blocks[0], Heading) and blocks[0].level == 1:
            title, blocks = blocks[0].text, blocks[1:]
        first = next((i for i, b in enumerate(blocks) if _is_h2(b)), len(blocks))
        scope, rest = blocks[:first], blocks[first:]
        match rest:
            case (Heading(text=text), ListBlock() as listed, Divider(), *after) if (
                text == CONTENTS
            ):
                return cls(title, scope, Contents.read(listed), _sections(tuple(after)))
            case (Heading(text=text), *_) if text == CONTENTS:
                msg = "a contents section holds one list, then a `---` rule"
                raise ValueError(msg)
            case _:
                return cls(title, scope, None, _sections(rest))

    def doc(self) -> Doc:
        """The blocks this chapter is read from."""
        head: list[Block] = [Heading(1, self.title)] if self.title else []
        head.extend(self.scope)
        if self.contents is not None:
            head += [Heading(2, CONTENTS), self.contents.block(), Divider()]
        return Doc(None, (*head, *(b for s in self.sections for b in s.blocks())))

    @property
    def rules(self) -> tuple[Rule, ...]:
        """Every rule the chapter states, in order."""
        return tuple(r for s in self.sections for r in s.rules)

    @property
    def tools(self) -> tuple[LintRow, ...]:
        """The rows of the `Decided by tools` table.

        Its columns are `| Tool | Lint | Level | Forbids |`.
        """
        return tuple(
            LintRow(row[0], row[1].strip("`"), row[2], row[3])
            for s in self.sections
            if s.title == DECIDED
            for block in s.lead
            for row in _rows(block)
            if len(row) == _LINT_CELLS
        )

    @property
    def renames(self) -> tuple[RenameTable, ...]:
        """Every rename table the chapter carries."""
        return tuple(
            _rename_table(s) for s in self.sections if RENAMED.fullmatch(s.title)
        )


def _is_h2(block: Block) -> bool:
    """Is `block` a section heading?"""
    return isinstance(block, Heading) and block.level == _SECTION


def _rename_table(section: Section) -> RenameTable:
    """The rename table a section holds, and the ranges above it."""
    tables = [i for i, b in enumerate(section.lead) if isinstance(b, Table)]
    lead = section.lead[: tables[0]] if tables else section.lead
    text = " ".join(b.text for b in lead if isinstance(b, Paragraph))
    ranges = tuple(
        (RuleId.parse(m[1]), RuleId.parse(m[2] or m[1])) for m in _RANGE.finditer(text)
    )
    rows = tuple(
        Rename(RuleId.parse(row[0].strip("`")), _becomes(row[1]))
        for i in tables[:1]
        for row in _rows(section.lead[i])
        if len(row) == _RENAME_CELLS
    )
    return RenameTable(section.title, ranges, rows)


def _rows(block: Block) -> tuple[tuple[str, ...], ...]:
    """The body rows of a table, each escaped pipe read as a pipe."""
    if not isinstance(block, Table):
        return ()
    return tuple(tuple(c.replace("\\|", "|") for c in row) for row in block.rows)


@dataclass(frozen=True, slots=True)
class SkillMd:
    """A standard's `SKILL.md`.

    Its frontmatter, title, preamble, and numbered sections.
    """

    frontmatter: str | None
    title: str
    preamble: tuple[Block, ...]
    sections: tuple[Section, ...]

    @classmethod
    def read(cls, doc: Doc) -> Self:
        """The `SKILL.md` `doc` is."""
        blocks = doc.blocks
        title = ""
        if blocks and isinstance(blocks[0], Heading) and blocks[0].level == 1:
            title, blocks = blocks[0].text, blocks[1:]
        first = next((i for i, b in enumerate(blocks) if _is_h2(b)), len(blocks))
        return cls(doc.frontmatter, title, blocks[:first], _sections(blocks[first:]))

    def doc(self) -> Doc:
        """The blocks this file is read from."""
        head: list[Block] = [Heading(1, self.title)] if self.title else []
        head.extend(self.preamble)
        body = (b for s in self.sections for b in s.blocks())
        return Doc(self.frontmatter, (*head, *body))

    @property
    def core_rules(self) -> tuple[Rule, ...]:
        """Every rule section 4 states, in order.

        Each is a list item that opens `**ID `[T]`**`.
        """
        return tuple(
            rule
            for s in self.sections
            if s.title.startswith("4. ")
            for block in s.lead
            if isinstance(block, ListBlock)
            for item in block.items
            if (rule := _core_rule(item)) is not None
        )


#: The bold label a core rule opens with: `**ZS-CORE-01 `[M]`**`.
_CORE = re.compile(rf"\*\*({rule_id()}) `(\[[^\]]*\])`\*\*")


def _core_rule(item: Item) -> Rule | None:
    """The core rule a list item states, if it states one."""
    if not item.blocks or not isinstance(first := item.blocks[0], Paragraph):
        return None
    m = _CORE.fullmatch(" ".join(first.words[:2]))
    if m is None:
        return None
    statement = first.words[2:]
    head = (Paragraph(statement, first.line),) if statement else ()
    return Rule(
        RuleId.parse(m[1]), Tier.parse(m[2]), "", (*head, *item.blocks[1:]), item.line
    )
