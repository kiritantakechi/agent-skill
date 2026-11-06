"""A standard's normal form, which `fmt` prints for a normalised one.

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
lazy from collections.abc import Iterator, Sequence

from agent_skill.doc import (
    Block,
    Doc,
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
    Chapter,
    Element,
    Part,
    Rule,
    Section,
    history,
)
from agent_skill.ids import RuleId, leading

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
