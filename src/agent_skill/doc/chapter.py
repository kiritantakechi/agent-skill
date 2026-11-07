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
from enum import Enum
from typing import Self
lazy from collections.abc import Iterator

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
    entry,
    words,
)
from agent_skill.ids import RuleId, Tier, Version, ranges

#: The section a chapter lists its tool-decided claims under.
DECIDED = "Decided by tools"

#: The H2 a contents list sits under.
CONTENTS = "Contents"

#: The H2 a renumbering's rename table sits under, after the revision
#: it names.
RENAMED = re.compile(r"Rule IDs before the .+ revision")

#: The labels a rule's parts open with, and the shape any label has.
WHY, CHECK, RELAXED = "**Why:**", "**Check:**", "*Relaxed form:*"
LABEL = re.compile(r"\*\*[^*]+:\*\*|\*Relaxed form:\*")

#: The cells of a `Decided by tools` row: tool, lint, level, forbids.
_LINT_CELLS = 4

#: The cells of a rename row: before, now.
_RENAME_CELLS = 2

#: The cells an override row opens with: the other's rule, then ours.
_OVERRIDE_CELLS = 2


def _code_id(text: str) -> RuleId | None:
    """The rule ID a code span spells, as `` `RS-ERR-03` `` does."""
    inner = text.removeprefix("`").removesuffix("`")
    return RuleId.try_parse(inner) if f"`{inner}`" == text else None


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

    @property
    def parts(self) -> tuple[Part, ...]:
        """The rule's body as the elements it states, in its order.

        A label opens its element and a fence is an example; a block
        with neither carries the element before it on, as `_part` reads
        a second paragraph of a Why, except after an example, where
        nothing is carried. A block no element holds is `STRAY`, and so
        is what follows it until the next label or example.
        """
        out: list[Part] = []
        for block in self.body:
            opened = _opens(block)
            if opened is None and out and out[-1].element is not Element.EXAMPLE:
                out[-1] = Part(out[-1].element, (*out[-1].blocks, block))
                continue
            if opened is None:
                opened = Element.STRAY if out else Element.STATEMENT
            out.append(Part(opened, (block,)))
        return tuple(out)

    def heading(self) -> Heading:
        """The `###` heading this rule is read from."""
        return Heading(3, f"{self.id} {self.tier} {self.title}", self.line)


def _ends_part(block: Block) -> bool:
    """Does `block` end the labelled part before it?"""
    if isinstance(block, Paragraph):
        return bool(LABEL.match(block.text))
    return isinstance(block, (Fence, Heading))


class Element(Enum):
    """What a block of a rule states, in the order a rule states them.

    A statement, the relaxed form an `[M!]` rule gives, a Why, a Check,
    then examples. `STRAY` is a block none of them holds: prose after an
    example, a heading inside the rule, a label the shape has no place
    for. Each element can be put in its place by moving it whole; a
    stray block can only be placed by someone reading it.
    """

    STATEMENT = "statement"
    RELAXED = "relaxed form"
    WHY = "Why"
    CHECK = "Check"
    EXAMPLE = "example"
    STRAY = "stray"


#: The order a rule states its elements in. A stray block has no place.
ORDER = (
    Element.STATEMENT,
    Element.RELAXED,
    Element.WHY,
    Element.CHECK,
    Element.EXAMPLE,
)

#: The element each label of the shape opens.
_LABELLED = {RELAXED: Element.RELAXED, WHY: Element.WHY, CHECK: Element.CHECK}


@dataclass(frozen=True, slots=True)
class Part:
    """One element of a rule, and the blocks that state it."""

    element: Element
    blocks: tuple[Block, ...]


def _opens(block: Block) -> Element | None:
    """The element `block` opens, or None when it carries one on.

    A fence is an example and a label opens its element; a heading, or
    a label the shape does not have, opens a stray run.
    """
    match block:
        case Fence():
            return Element.EXAMPLE
        case Heading():
            return Element.STRAY
        case Paragraph() if m := LABEL.match(block.text):
            return _LABELLED.get(m.group(0), Element.STRAY)
        case _:
            return None


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
    found = entry(words(block.text))
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
        case (Paragraph() as p,) if (found := entry(p.words)) is not None:
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
    line: int = field(default=0, compare=False)


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


def parse_becomes(cell: str) -> Becomes | None:
    """What a rename row's `Now` cell says the old ID became.

    None when it says none of the three, which a table can be written
    to say and a check has to be able to report.
    """
    if (rid := _code_id(cell)) is not None:
        return rid
    if m := _DEMOTED.fullmatch(cell):
        return Demoted(m["tool"], m["lint"])
    if m := _REMOVED.fullmatch(cell):
        return Removed(m["reason"].strip())
    return None


def print_becomes(becomes: Becomes) -> str:
    """The `Now` cell saying `becomes`, which `parse_becomes` reads."""
    match becomes:
        case RuleId():
            return f"`{becomes}`"
        case Demoted(tool, lint):
            return f"lint `{tool}:{lint}`"
        case Removed(reason):
            return f"removed — {reason}"


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
    #: The rows that name no old ID, or say nothing a rename can say,
    #: as their two cells are written.
    unread: tuple[tuple[str, str], ...] = ()

    @property
    def originals(self) -> tuple[RuleId, ...]:
        """Every ID the families ran before the revision, in order."""
        return tuple(
            RuleId(first.standard, first.family, n)
            for first, last in self.ranges
            for n in range(first.number, last.number + 1)
        )

    @property
    def unchanged(self) -> tuple[RuleId, ...]:
        """The original IDs no row names: each still names its rule.

        A row read or not names its old ID, since the table lists it.
        """
        unread = (RuleId.try_parse(before.strip("`")) for before, _ in self.unread)
        listed = {r.before for r in self.rows} | set(unread)
        return tuple(rid for rid in self.originals if rid not in listed)

    @classmethod
    def read(cls, section: Section) -> Self:
        """The rename table a section holds, and the ranges above it."""
        tables = [i for i, b in enumerate(section.lead) if isinstance(b, Table)]
        lead = section.lead[: tables[0]] if tables else section.lead
        text = " ".join(b.text for b in lead if isinstance(b, Paragraph))
        stated = tuple(ranges(text))
        rows: list[Rename] = []
        unread: list[tuple[str, str]] = []
        cells = (row for i in tables[:1] for _, row in _rows(section.lead[i]))
        for before, now in (row for row in cells if len(row) == _RENAME_CELLS):
            old, becomes = RuleId.try_parse(before.strip("`")), parse_becomes(now)
            if old is None or becomes is None:
                unread.append((before, now))
            else:
                rows.append(Rename(old, becomes))
        return cls(section.title, stated, tuple(rows), tuple(unread))


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
        """The chapter `doc` is.

        A rule heading before the first section is refused rather than
        read as scope, where every reader of rules would miss it.
        """
        blocks = doc.blocks
        title = ""
        if blocks and isinstance(blocks[0], Heading) and blocks[0].level == 1:
            title, blocks = blocks[0].text, blocks[1:]
        first = next((i for i, b in enumerate(blocks) if _is_h2(b)), len(blocks))
        scope, rest = blocks[:first], blocks[first:]
        if stray := next((b for b in scope if _rule_heading(b)), None):
            msg = f"line {stray.line}: a rule before the first `##` section"
            raise ValueError(msg)
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
        """The rows of the `Decided by tools` table, each on its line.

        Its columns are `| Tool | Lint | Level | Forbids |`.
        """
        return tuple(
            LintRow(row[0], row[1].strip("`"), row[2], row[3], line)
            for s in self.sections
            if s.title == DECIDED
            for block in s.lead
            for line, row in _rows(block)
            if len(row) == _LINT_CELLS
        )

    @property
    def renames(self) -> tuple[RenameTable, ...]:
        """Every rename table the chapter carries."""
        return tuple(
            RenameTable.read(s) for s in self.sections if RENAMED.fullmatch(s.title)
        )


def _is_h2(block: Block) -> bool:
    """Is `block` a section heading?"""
    return isinstance(block, Heading) and block.level == _SECTION


def _rows(block: Block) -> tuple[tuple[int, tuple[str, ...]], ...]:
    """The body rows of a table, each on its line.

    Each escaped pipe is read as a pipe. A table's header and delimiter
    take its first two lines, and each row one line after them.
    """
    if not isinstance(block, Table):
        return ()
    return tuple(
        (block.line + 2 + k, tuple(c.replace("\\|", "|") for c in row))
        for k, row in enumerate(block.rows)
    )


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
            if (rule := core_rule(item)) is not None
        )

    @property
    def overrides(self) -> tuple[Override, ...]:
        """Every row of a table that says where this standard departs.

        Such a row opens its first cell with the other standard's rule
        and its second with the rule here that applies instead.
        """
        return tuple(
            row
            for block in self.doc().blocks
            for line, cells in _rows(block)
            if (row := _override(cells, line)) is not None
        )


#: A core rule's tier as its bold label spells it, the label's end
#: included: `` `[M]`** ``.
_CORE_TIERS = {f"`{t}`**": t for t in Tier}


def core_rule(item: Item) -> Rule | None:
    """The core rule a list item states, if it states one.

    Its paragraph opens with the two words `**ZS-CORE-01 `[M]`**`.
    """
    if not item.blocks or not isinstance(first := item.blocks[0], Paragraph):
        return None
    match first.words:
        case (bold, spelled, *statement) if (
            bold.startswith("**")
            and (rid := RuleId.try_parse(bold.removeprefix("**"))) is not None
            and (tier := _CORE_TIERS.get(spelled)) is not None
        ):
            head = (Paragraph(tuple(statement), first.line),) if statement else ()
            return Rule(rid, tier, "", (*head, *item.blocks[1:]), item.line)
        case _:
            return None


@dataclass(frozen=True, slots=True)
class Override:
    """One row of a delta's table of where it departs from another.

    The other standard's rule, as much of its title as the row quotes,
    and the rule here that applies instead.
    """

    theirs: RuleId
    quoted: str
    ours: RuleId
    line: int = field(default=0, compare=False)


def _override(cells: tuple[str, ...], line: int) -> Override | None:
    """The override a table row states, if it states one.

    Each of its first two cells opens with an ID in a code span.
    """
    if len(cells) < _OVERRIDE_CELLS:
        return None
    theirs, quoted = _opening_id(cells[0])
    ours, _ = _opening_id(cells[1])
    if theirs is None or ours is None:
        return None
    return Override(theirs, quoted, ours, line)


def _opening_id(cell: str) -> tuple[RuleId | None, str]:
    """The ID `cell` opens with, and what follows it.

    In a code span of its own, `` `RS-API-15` Title ``, or bare, as
    `fmt` sets a citation: `RS-API-15 Title`.
    """
    if not cell.startswith("`"):
        first, _, rest = cell.partition(" ")
        return RuleId.try_parse(first), rest.strip()
    span, tick, rest = cell.removeprefix("`").partition("`")
    if not tick:
        return None, cell
    return RuleId.try_parse(span), rest.strip()


#: The statuses a migration row may give an old spelling: removed, kept
#: as an alias of the new one, kept and behaving otherwise, kept and
#: scheduled for removal (normalize-the-standards, decision 9).
STATUSES = ("gone", "alias", "changed", "deprecated")

#: The statuses whose old spelling the reader's command finds: those
#: whose spelling is to be rewritten wherever it stands.
SOUGHT = ("gone", "alias")

#: What stands for code a spelling leaves out: `extern "C" { … }`. A
#: spelling holding one is a shape, which no fixed string finds.
ELIDED = "\u2026"


def migration_header(target: str) -> tuple[str, str, str, str, str]:
    """A migration table's columns: old, target, status, since, rule.

    `target` is what the standard is for, as section 2 names it:
    `Python 3.15`. Since is the release — or, for a language with
    editions, the edition — from which the row's status holds.
    """
    return ("Old", target, "Status", "Since", "Rule")


def reality_header(target: str) -> tuple[str, str, str]:
    """Section 2.2's columns: the migration table's, less two.

    Section 2.2 is the migration table restricted to the rows whose
    Since is the target, rendered from it: Since is the target in every
    row, and Status is the chapter's to read.
    """
    old, new, _, _, rule = migration_header(target)
    return (old, new, rule)


@dataclass(frozen=True, slots=True)
class Migration:
    """One row of a migration table, its cells as written."""

    old: str
    new: str
    status: str
    since: str
    rule: str
    line: int = field(default=0, compare=False)

    @property
    def spelling(self) -> str | None:
        """The old spelling: the code span the cell is, else None."""
        inner = self.old.removeprefix("`").removesuffix("`")
        return inner if self.old == f"`{inner}`" and "`" not in inner else None

    @property
    def owner(self) -> RuleId | None:
        """The rule the row names as its owner, bare, else None."""
        return RuleId.try_parse(self.rule)

    @property
    def landed(self) -> Version | None:
        """The release or edition the Since cell names, else None."""
        return Version.try_parse(self.since)


def migrations(table: Table) -> tuple[Migration, ...]:
    """The rows of `table`, read as a migration table's."""
    return tuple(
        Migration(*cells, line=line)
        for line, cells in _rows(table)
        if len(cells) == len(migration_header(""))
    )


#: How a delta rule relates to the anchor rule it departs from: it says
#: the opposite, it binds harder, or it says more (decision 10).
RELATIONS = ("overrides", "tightens", "extends")

#: What separates the tier before from the tier after in a departure.
ARROW = "\u2192"


def departures_header(anchor: str, delta: str) -> tuple[str, ...]:
    """A delta's departures: anchor rule, relation, rule here, why."""
    return (f"{anchor} rule", "Relation", f"{delta} rule", "Tier", "Reason")


@dataclass(frozen=True, slots=True)
class Departure:
    """One row of a delta's departures table, its cells as written."""

    theirs: str
    relation: str
    ours: str
    tier: str
    reason: str
    line: int = field(default=0, compare=False)

    @property
    def tiers(self) -> tuple[Tier, Tier] | None:
        """The tier before and after, as `[M!] → [M]` states them."""
        before, arrow, after = self.tier.partition(f" {ARROW} ")
        try:
            return (Tier.parse(before), Tier.parse(after)) if arrow else None
        except ValueError:
            return None


def departures(table: Table) -> tuple[Departure, ...]:
    """The rows of `table`, read as a departures table's."""
    width = len(departures_header("", ""))
    return tuple(
        Departure(*cells, line=line)
        for line, cells in _rows(table)
        if len(cells) == width
    )


def history(doc: Doc) -> Iterator[tuple[Block, bool]]:
    """Each top-level block of `doc`, and whether it is history.

    History is what a rename table's section holds: IDs that no longer
    exist, listed on purpose, for a reader holding an old citation to
    look up. Its IDs are neither citations to check nor to rewrite.
    """
    renamed = False
    for block in doc.blocks:
        if isinstance(block, Heading) and block.level <= _SECTION:
            renamed = block.level == _SECTION and bool(RENAMED.fullmatch(block.text))
        yield block, renamed


def owned(doc: Doc) -> Iterator[tuple[Block, RuleId | None]]:
    """Each top-level block of `doc`, and the rule it sits under.

    A rule runs from its `###` heading, which is its own, to the next
    heading of a rule, a section or the title. A block outside every
    rule — the scope, the contents, a section's lead — sits under none.
    The examples and the prose a check holds to a rule are found here,
    so each knows which rule's own text it is reading.
    """
    rule: RuleId | None = None
    for block in doc.blocks:
        if isinstance(block, Heading):
            if (found := _rule_heading(block)) is not None:
                rule = found[0]
            elif block.level <= _SECTION:
                rule = None
        yield block, rule


def citing(doc: Doc) -> Iterator[Block]:
    """Every top-level block of `doc` whose rule IDs are citations.

    That is every block but the history a rename table's section holds.
    """
    return (block for block, held in history(doc) if not held)
