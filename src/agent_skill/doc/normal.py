"""A standard's normal form, which `fmt` prints.

Two rewrites a person need not judge: a rule is cited by its bare ID,
never quoted and never behind its chapter's path, and a rule states its
elements in one order — statement, relaxed form, Why, Check, examples.
Each is a map from tree to tree, applied before printing, so the
printer's laws hold unchanged: `print ∘ parse` is still the identity on
canonical text, and `normal` is idempotent on every tree. A citation
inside an example, or in a rename table's history, is left as written:
the first is code, the second names IDs that no longer exist.

A block the rule shape has no place for (`Element.STRAY`) moves with
the element before it, because only someone reading it can say where it
belongs; `anatomy` reports it until they have.
"""

import itertools
import re
lazy from collections.abc import Collection, Iterable, Iterator, Sequence

from agent_skill.doc import (
    Align,
    Block,
    Doc,
    Fence,
    Heading,
    Item,
    ListBlock,
    Paragraph,
    Quote,
    Table,
    walk,
    words,
)
from agent_skill.doc.chapter import (
    ORDER,
    SOUGHT,
    Chapter,
    Contents,
    Element,
    Entry,
    Group,
    Migration,
    Part,
    Rule,
    Section,
    history,
    migrations,
)
from agent_skill.ids import RuleId, Version, leading

#: A code span of one backtick on each side, and what it holds.
_SPAN = re.compile(r"(?<!`)`([^`]+)`(?!`)")

#: A word that is a path under `references/`, after any punctuation
#: that opens it: `` (`references/errors.md` ``.
_PATH = re.compile(r"(?P<lead>[^`]*)`(?P<path>references/[^`\s]+\.md)`")


def quoted(word: str) -> Iterator[RuleId]:
    """Each rule ID `word` sets in a code span of its own."""
    for m in _SPAN.finditer(word):
        if (rid := RuleId.try_parse(m[1])) is not None:
            yield rid


def _unquoted(word: str) -> str:
    """`word` with each rule ID in a code span of its own set bare."""
    return _SPAN.sub(lambda m: m[1] if RuleId.try_parse(m[1]) else m[0], word)


def qualified(run: Sequence[str]) -> Iterator[tuple[int, str, RuleId]]:
    """Each chapter path `run` puts before a rule ID, as cited.

    The index of the path's word, the path, and the ID the next word
    opens with, quoted or not: `` `references/errors.md` RS-ERR-03 ``.
    """
    for i, (word, after) in enumerate(itertools.pairwise(run)):
        m = _PATH.fullmatch(word)
        rid = leading(after.removeprefix("`"))
        if m is not None and rid is not None:
            yield i, word[m.start("path") : m.end("path")], rid


def bare(run: Sequence[str]) -> tuple[str, ...]:
    """`run` with every rule ID cited bare.

    Unquoted first, so a quoted ID after a path is an ID after a path;
    then each path before an ID is dropped, any punctuation opening its
    word kept on the ID's word. Section 6 maps every family to its file,
    which is where a reader needs the path.
    """
    out = [_unquoted(word) for word in run]
    for i, _, _ in reversed(list(qualified(out))):
        lead = _PATH.fullmatch(out[i])
        out[i : i + 2] = [f"{lead['lead'] if lead else ''}{out[i + 1]}"]
    return tuple(out)


def runs(block: Block) -> Iterator[tuple[int, tuple[str, ...]]]:
    """Each run of words `block` cites in, nested ones too, by line.

    A paragraph's words, a heading's, and a table cell's each; an
    example's are code, and none of them.
    """
    for inner in walk((block,)):
        match inner:
            case Paragraph(words=said, line=line):
                yield line, said
            case Heading(text=text, line=line):
                yield line, words(text)
            case Table(rows=rows, line=line):
                for k, row in enumerate(rows):
                    for cell in row:
                        yield line + 2 + k, words(cell)
            case _:
                pass


def _cited_bare(block: Block) -> Block:
    """`block`, every run of words in it with its citations bare.

    A heading or a cell already bare keeps its spelling, so only a
    citation moves anything.
    """

    def said(text: str) -> str:
        run = words(text)
        return text if (now := bare(run)) == run else " ".join(now)

    match block:
        case Paragraph(words=run, line=line):
            return Paragraph(bare(run), line)
        case Heading(level=level, text=text, line=line):
            return Heading(level, said(text), line)
        case Table(header=header, align=align, rows=rows, line=line):
            cited = tuple(tuple(said(cell) for cell in row) for row in rows)
            return Table(header, align, cited, line)
        case ListBlock(items=items, start=start, loose=loose, line=line):
            held = tuple(
                Item(tuple(_cited_bare(b) for b in item.blocks), item.line)
                for item in items
            )
            return ListBlock(held, start, loose, line)
        case Quote(blocks=inner, alert=alert, line=line, lazy=lazy):
            return Quote(tuple(_cited_bare(b) for b in inner), alert, line, lazy)
        case _:
            return block


def in_order(rule: Rule) -> Rule:
    """`rule` with its elements in the order a rule states them.

    A stray part moves with the element before it, so prose after an
    example stays beside that example; the sort is stable, so two
    examples keep their order.
    """
    held: list[Part] = []
    for part in rule.parts:
        if part.element is Element.STRAY and held:
            held[-1] = Part(held[-1].element, (*held[-1].blocks, *part.blocks))
        else:
            held.append(part)
    ranked = sorted(
        held, key=lambda p: ORDER.index(p.element) if p.element in ORDER else 0
    )
    body = tuple(block for part in ranked for block in part.blocks)
    return Rule(rule.id, rule.tier, rule.title, body, rule.line)


def normal(doc: Doc, *, chapter: bool) -> Doc:
    """`doc` with its citations bare, and a chapter's rules in order.

    A chapter the chapter layer refuses keeps its rules as they are;
    `skeleton` reports why it does not read.
    """
    cited = Doc(
        doc.frontmatter,
        tuple(b if held else _cited_bare(b) for b, held in history(doc)),
    )
    if not chapter:
        return cited
    try:
        read = Chapter.read(cited)
    except ValueError:
        return cited
    sections = tuple(
        Section(s.title, s.lead, tuple(in_order(r) for r in s.rules), s.line)
        for s in read.sections
    )
    ordered = Chapter(read.title, read.scope, read.contents, sections).doc()
    return Doc(cited.frontmatter, ordered.blocks)


# ------------------------------------------------------------------
# section 4, a projection of the chapters (decision 7)

#: A chapter as section 4 groups its rules: its title, and each rule's
#: ID, tier and title as its contents line states them.
type Mapped = tuple[str, tuple[Entry, ...]]


def listed(blocks: Sequence[Block]) -> tuple[RuleId, ...] | None:
    """The rules section 4 lists, read from the blocks under its title.

    Section 4 is one list of chapter titles over contents lines, or
    nothing at all; the IDs the lines name are what it lists, and what
    it is rendered from again. A flat list of lines is read too, as is
    any grouping of them. None when it holds anything else — a core
    rule of its own, a label over no line, a paragraph, a heading —
    which rendering would drop.
    """
    match tuple(blocks):
        case ():
            return ()
        case (ListBlock() as block,):
            try:
                items = Contents.read(block).items
            except ValueError:
                return None
            lines = [i for i in items if isinstance(i, Entry)]
            for group in (i for i in items if isinstance(i, Group)):
                if not group.children or not all(
                    isinstance(c, Entry) for c in group.children
                ):
                    return None  # a label over nothing, or over labels
                lines.extend(c for c in group.children if isinstance(c, Entry))
            return tuple(e.id for e in lines)
        case _:
            return None


def projection(ids: Iterable[RuleId], chapters: Sequence[Mapped]) -> tuple[Block, ...]:
    """Section 4: `ids` grouped by chapter, in `chapters`' order.

    `chapters` is section 6's order, each with its rules in its own
    order, so the result is a function of the set of IDs alone: every
    line's tier and title is its chapter's, and an ID no chapter holds
    has no line. A chapter none of whose rules is listed has no label.
    """
    wanted = set(ids)
    groups = (
        Group(f"**{title}**", tuple(e for e in entries if e.id in wanted))
        for title, entries in chapters
    )
    kept = tuple(g for g in groups if g.children)
    return (Contents(kept).block(),) if kept else ()


# ------------------------------------------------------------------
# the migration table's command (decision 9)

#: The info string of the fence holding the reader's command.
SHELL = "sh"


def sought(rows: Sequence[Migration]) -> tuple[str, ...]:
    """The old spellings a reader searches a codebase for, in row order.

    Each `gone` or `alias` row's: a spelling to rewrite wherever it
    stands. One that changed behaviour, or is deprecated and still
    works, is a rule's to judge, not a hit; so is a shape, which no
    fixed string finds (`Migration.shape`).

    A spelling is found where the code writes it out. A member keyed by
    its type, `Timer::finished`, is not there when the code calls it on
    a value, `timer.finished()`, which names no type a fixed string can
    see; and a bare `.finished(` cannot fail a build, since a live
    member may share the name (`EntityCommands::observe`). The type
    checker finds that call: `ty` as `unresolved-attribute`, `rustc`
    and `zig` as an error, on code they analyse.
    """
    found = (r.spelling for r in rows if r.status in SOUGHT and not r.shape)
    return tuple(dict.fromkeys(s for s in found if s is not None))


def command(spellings: Sequence[str]) -> Fence | None:
    """The reader's command: every spelling, as a whole word; or None.

    One pattern a line, so a row added is a line added. Generated from
    the table rather than kept beside it, so the two cannot disagree.
    A fixed string, matched where no word character runs on either
    side of it (`-w`): `Style` is not `TextStyle`, and `gen`, the name
    edition 2024 reserved, is not `generic`.
    """
    if not spellings:
        return None
    patterns = (f"  -e {_shell(s)} \\" for s in spellings)
    return Fence(SHELL, "\n".join(["rg -n -F -w \\", *patterns, "  ."]) + "\n")


def _shell(word: str) -> str:
    """`word` as one single-quoted shell word."""
    return "'" + word.replace("'", "'\\''") + "'"


def generated(doc: Doc, header: Sequence[str]) -> tuple[int, Fence | None] | None:
    """Where the migration table stands in `doc`, and what follows it.

    The index of the one top-level table headed `header`, and the
    command its rows generate; None when there is not exactly one.
    """
    at = [
        i
        for i, b in enumerate(doc.blocks)
        if isinstance(b, Table) and b.header == tuple(header)
    ]
    if len(at) != 1 or not isinstance(table := doc.blocks[at[0]], Table):
        return None
    return at[0], command(sought(migrations(table)))


def stated(doc: Doc, after: int) -> Fence | None:
    """The command `doc` states after block `after`, if any."""
    held = doc.blocks[after + 1] if after + 1 < len(doc.blocks) else None
    return held if isinstance(held, Fence) and held.info == SHELL else None


def with_command(doc: Doc, header: Sequence[str]) -> Doc:
    """`doc` with its migration table's command right after the table.

    The fence there is the command's place: one standing there is
    replaced, and none is written for a table with nothing to seek.
    """
    found = generated(doc, header)
    if found is None:
        return doc
    at, want = found
    rest = doc.blocks[at + 1 + (stated(doc, at) is not None) :]
    blocks = (*doc.blocks[: at + 1], *((want,) if want else ()), *rest)
    return Doc(doc.frontmatter, blocks)


# ------------------------------------------------------------------
# sections 2.1 and 2.2, projections of the migration table (decision 9)


def landed(
    rows: Iterable[Migration], since: Collection[Version], status: str
) -> tuple[Migration, ...]:
    """The rows of `status` whose Since is one of `since`, in order."""
    return tuple(r for r in rows if r.status == status and r.landed in since)


#: What the line after each subsection's table says of the rows of
#: an earlier release, by the status the subsection projects: how a
#: reader finds a spelling of it in their code. A `gone` member the
#: code reaches through a value is no fixed string's (`sought`).
_FOUND = {
    "changed": "its owning rule's Check finds it",
    "gone": (
        "the `rg` command after that table finds every `gone` and `alias` "
        "spelling the code writes out but a shape, whatever its release, and "
        "the type checker every `gone` member the code reaches through a value"
    ),
}


def older(family: str, status: str) -> Paragraph:
    """The line after a subsection's table: where an older change is.

    `family` is the migration chapter's, `PS-MIG`: section 6 maps it to
    its file, so the line names no path. A `changed` row is found by
    its rule; a `gone` one by the command the migration table
    generates where the code writes its spelling out, unless it is a
    shape, and by the type checker where the code reaches a member
    through a value.
    """
    said = (
        f"A `{status}` row of an earlier release is in the migration table, "
        f"`{family}` in section 6, with its Since; {_FOUND[status]}."
    )
    return Paragraph(words(said))


def reality(
    rows: Sequence[Migration],
    since: Collection[Version],
    header: Sequence[str],
    family: str,
    status: str,
) -> tuple[Block, ...]:
    """Section 2.1 or 2.2: the migration table restricted to the target.

    Each row of `status` whose Since is the target's, its Old, target
    spelling and rule, in the table's order, so the subsection is a
    function of the table alone; then the line saying where the other
    rows are. No table when no row landed in the target: a header over
    no row says nothing. A row's cells are read with each escaped pipe
    a pipe (`errdefer |err|`), so each is escaped again to be a cell.
    """
    kept = landed(rows, since, status)
    cells = tuple(
        tuple(c.replace("|", "\\|") for c in (r.old, r.new, r.rule)) for r in kept
    )
    table = Table(tuple(header), (Align.NONE,) * len(header), cells)
    return (*((table,) if kept else ()), older(family, status))
