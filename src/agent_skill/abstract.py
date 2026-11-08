"""The abstract standard: each concept the standards share, stated once.

`abstract/` holds one file per abstract chapter, named from the
vocabulary, and `principles.md`, the questions section 3 of every base
standard opens with (one-abstract-standard, decisions 1 and 7). A
chapter is in the chapter template every standard's chapter is in, and
an entry is rule-shaped: `### AS-ERR-03 [M] Title`, a statement that
names no construct of any one language, then one table giving, for each
base standard, the rule that realises it, how, at what tier and why.

It is read by the parser and the chapter layer that read the standards,
so an entry is a `Rule` whose body is its statement and its table, and
`print ∘ parse` is the identity on it as on every file they read. What a
check needs to know about it beyond its files is a record in the shape
of a profile (`profiles.abstract`), as a standard's is.
"""

import re
from dataclasses import dataclass, field
from functools import cached_property
lazy from collections.abc import Iterable, Iterator, Mapping
lazy from pathlib import Path

from agent_skill.doc import Doc, ListBlock, Paragraph, Table
from agent_skill.doc.chapter import LABEL, Rule
from agent_skill.ids import Location, Relation, RuleId, Tier
from agent_skill.layout import ABSTRACT, in_repository, root_of
from agent_skill.model import Chapter
from agent_skill.profiles.abstract import PROFILE
lazy from agent_skill.doc import Block
lazy from agent_skill.model import Tree
lazy from agent_skill.profiles import Profile

#: The file the design questions are in.
PRINCIPLES = "principles.md"

#: An entry's realisation table: a row per base standard.
HEADER = ("Standard", "Rule", "Relation", "Tier", "Reason")


@dataclass(frozen=True, slots=True)
class Realisation:
    """One row of an entry's realisation table, its cells as written."""

    standard: str
    rule: str
    relation: str
    tier: str
    reason: str
    line: int = field(default=0, compare=False)

    @property
    def related(self) -> Relation | None:
        """The relation the row states, or None when it states none."""
        return Relation.try_parse(self.relation)

    @property
    def rid(self) -> RuleId | None:
        """The rule the row names, bare, or None when it names none."""
        return RuleId.try_parse(self.rule)

    @property
    def lint(self) -> str:
        """What a `decided` row names: its lint, as its row spells it.

        The cell is the lint in a code span, `` `F403` ``, as the Lint
        column of a `Decided by tools` table writes it; "" when it is
        not one code span.
        """
        inner = self.rule.removeprefix("`").removesuffix("`")
        return inner if self.rule == f"`{inner}`" and inner else ""

    @property
    def named(self) -> str:
        """What the row names, as a finding prints it: rule or lint."""
        return self.lint or self.rule


def tier_cell(row: Realisation, tiers: Mapping[RuleId, Tier]) -> str | None:
    """The Tier cell `row` holds, rendered from what it names.

    A row naming a rule shows that rule's tier, so the cell cannot
    drift from the rule; a `decided` or `absent` row names none and
    shows none. None when it cannot be rendered: no relation, or a rule
    that is not there, which is another finding.
    """
    relation = row.related
    if relation is None:
        return None
    if not relation.ruled:
        return ""
    tier = tiers.get(row.rid) if row.rid is not None else None
    return None if tier is None else str(tier)


def with_tiers(doc: Doc, tiers: Mapping[RuleId, Tier]) -> Doc:
    """`doc` with each realisation row's Tier cell rendered.

    A cell that cannot be rendered is left as written.
    """
    column = HEADER.index("Tier")

    def rendered(table: Table) -> Table:
        rows = []
        for row, read in zip(table.rows, _read(table), strict=True):
            cell = tier_cell(read, tiers) if read is not None else None
            if cell is None or len(row) != len(HEADER):
                rows.append(row)
            else:
                rows.append((*row[:column], cell, *row[column + 1 :]))
        return Table(table.header, table.align, tuple(rows), table.line)

    blocks = tuple(
        rendered(b) if isinstance(b, Table) and b.header == HEADER else b
        for b in doc.blocks
    )
    return Doc(doc.frontmatter, blocks)


def _read(table: Table) -> Iterator[Realisation | None]:
    """Each row of `table` as a realisation; None where it is not."""
    for k, row in enumerate(table.rows):
        cells = tuple(c.replace("\\|", "|") for c in row)
        if len(cells) == len(HEADER):
            yield Realisation(*cells, line=table.line + 2 + k)
        else:
            yield None


def realisations(table: Table) -> tuple[Realisation, ...]:
    """The rows of `table`, read as a realisation table's."""
    return tuple(r for r in _read(table) if r is not None)


@dataclass(frozen=True, slots=True)
class Concept:
    """One entry of the abstract standard, read from its rule shape."""

    rule: Rule

    @property
    def id(self) -> RuleId:
        """The entry's ID: `AS-ERR-03`."""
        return self.rule.id

    @property
    def tier(self) -> Tier:
        """The tier the concept deserves."""
        return self.rule.tier

    @property
    def title(self) -> str:
        """The entry's title, as its heading states it."""
        return self.rule.title

    @property
    def statement(self) -> tuple[Paragraph, ...]:
        """The paragraphs before the realisation table.

        A paragraph a label opens, a Why or a Check, is none of them:
        those are each realisation's, in its own language.
        """
        out: list[Paragraph] = []
        for block in self.rule.body:
            if not isinstance(block, Paragraph) or LABEL.match(block.text):
                break
            out.append(block)
        return tuple(out)

    @property
    def tables(self) -> tuple[Table, ...]:
        """Every table under the entry headed as a realisation table."""
        return tuple(
            b for b in self.rule.body if isinstance(b, Table) and b.header == HEADER
        )

    @property
    def rows(self) -> tuple[Realisation, ...]:
        """Each row of the entry's realisation tables, in order."""
        return tuple(r for t in self.tables for r in realisations(t))

    @property
    def shaped(self) -> bool:
        """Is the entry a statement and then one realisation table?

        Nothing else: no Why, Check or example, which are each
        realisation's in its own language, and no second table.
        """
        body = self.rule.body
        said = len(self.statement)
        return (
            said > 0
            and len(body) == said + 1
            and isinstance(body[-1], Table)
            and body[-1].header == HEADER
        )


@dataclass(frozen=True, slots=True)
class Question:
    """One design question: its bold wording, and its one sentence."""

    question: str
    sentence: str
    line: int = field(default=0, compare=False)


#: An item's opening bold words, and what follows them.
_BOLD = re.compile(r"\*\*(?P<question>.+?)\*\*\s*(?P<rest>.*)", re.DOTALL)


def questions(blocks: Iterable[Block]) -> tuple[Question, ...]:
    """The questions the first numbered list among `blocks` asks.

    Each item opens with its question in bold; what follows is its
    sentence. Read the same way from `principles.md` and from a
    standard's section 3, so the two are compared as one shape.
    """
    listed = next(
        (b for b in blocks if isinstance(b, ListBlock) and b.start is not None), None
    )
    if listed is None:
        return ()
    out: list[Question] = []
    for item in listed.items:
        first = item.blocks[0] if item.blocks else None
        m = _BOLD.fullmatch(first.text) if isinstance(first, Paragraph) else None
        if m is not None:
            out.append(Question(m["question"], m["rest"], item.line))
    return tuple(out)


class Abstract:
    """The abstract standard at `root`, each file parsed once.

    `root` is None for a tree outside a repository's layout, which has
    nowhere to keep one: read as a standard with no files, so whatever
    it would have held is reported missing rather than passed over.
    """

    def __init__(self, root: Path | None, profile: Profile = PROFILE) -> None:
        """Read the abstract standard at `root` with its record."""
        self.root = root
        self.profile = profile

    @property
    def prefix(self) -> str:
        """The prefix every entry's ID carries: `AS`."""
        return self.profile.prefix

    @cached_property
    def chapters(self) -> list[Chapter]:
        """Every abstract chapter, in file-name order."""
        if self.root is None:
            return []
        return [
            Chapter(p, self.profile.name)
            for p in sorted(self.root.glob("*.md"))
            if p.name != PRINCIPLES
        ]

    @cached_property
    def principles(self) -> Chapter | None:
        """`principles.md`, or None when there is none."""
        if self.root is None or not (path := self.root / PRINCIPLES).is_file():
            return None
        return Chapter(path, self.profile.name)

    @property
    def markdown(self) -> list[Path]:
        """Every file: the chapters, then `principles.md` if there."""
        held = [] if self.principles is None else [self.principles.path]
        return [c.path for c in self.chapters] + held

    @cached_property
    def concepts(self) -> tuple[tuple[Chapter, Concept], ...]:
        """Each entry, with the chapter that holds it, in file order."""
        return tuple(
            (c, Concept(rule)) for c in self.chapters for rule in c.typed.rules
        )

    @property
    def words(self) -> frozenset[str]:
        """The vocabulary word of each abstract chapter: its stem."""
        return frozenset(c.path.stem for c in self.chapters)

    @cached_property
    def questions(self) -> tuple[Question, ...]:
        """The design questions, in order; none with no file."""
        if self.principles is None:
            return ()
        return questions(self.principles.doc.blocks)

    def at(
        self, file: str | Path = "", line: int | None = None, rule: RuleId | None = None
    ) -> Location:
        """A location in the abstract standard, named from the root.

        It lies in no skill, so no choice of skills hides a finding in
        it.
        """
        name = file.name if isinstance(file, Path) else file
        where = f"{ABSTRACT}/{name}" if name else str(ABSTRACT)
        return Location(file=where, line=line, rule=rule)

    def doc(self, path: Path) -> Doc:
        """The tree of one of its files, as read once."""
        return next(c.doc for c in self._files if c.path == path)

    @property
    def _files(self) -> Iterator[Chapter]:
        """Every file as a chapter, `principles.md` last."""
        yield from self.chapters
        if self.principles is not None:
            yield self.principles


def abstract_of(tree: Tree) -> Abstract:
    """The abstract standard beside the skills of `tree`.

    It sits at the root of the repository the skills sit in, as the
    README does, so a control's copy reads its own. A tree outside a
    repository's layout has no root to keep one at, and reads as one
    with no files.
    """
    skills = tree.skills[0].root.parent if tree.skills else None
    if skills is None or not in_repository(skills):
        return Abstract(None)
    return Abstract(root_of(skills) / ABSTRACT)
