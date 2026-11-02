"""A markdown file as a tree, and the one way it is written back.

`Doc.parse` reads a file into blocks and `str(doc)` prints them. The
printed form is the canonical one: blocks separated by one blank line,
no trailing whitespace, paragraphs filled greedily to `WIDTH`, list
items and table rows spelled one way. Printing inverts parsing on every
tree the parser can produce, so `str(Doc.parse(·))` is a projection
onto that form, and formatting a file is applying it.

Fences are recognised before anything else, at every level, so no line
inside an example is ever read as a heading, a table row or a list item.

The subset is the one the standards use: ATX headings, paragraphs,
backtick fences, pipe tables, `-` and `1.` lists, block quotes and
GitHub's alerts, `---` rules and YAML frontmatter. Inline markup is not
parsed beyond what filling needs: a code span or a link is one word,
never split. A hard line break is outside the subset: the standards
have none, and filling would move it.

Each block records the line it starts on, for findings to cite. The
line takes no part in equality, so a tree compares equal to itself
re-printed.
"""

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Self, override
lazy from collections.abc import Iterator, Sequence

from agent_skill.ids import Tier, rule_id

#: The column limit: every paragraph is filled to it, and the `layout`
#: check reports any other line that passes it.
WIDTH = 100


@dataclass(frozen=True, slots=True)
class Heading:
    """`## text`, at `level` 1 to 6."""

    level: int
    text: str
    line: int = field(default=0, compare=False)


@dataclass(frozen=True, slots=True)
class Paragraph:
    """Running text, as the words it is filled from.

    A word is what filling never splits: a code span or a link with the
    spaces inside it is one word.
    """

    words: tuple[str, ...]
    line: int = field(default=0, compare=False)

    @property
    def text(self) -> str:
        """The words, joined by single spaces."""
        return " ".join(self.words)


@dataclass(frozen=True, slots=True)
class Fence:
    """A fenced example: its info string and its body.

    The body keeps each line's newline, as a file's text does, so an
    empty body and a body of one empty line differ.
    """

    info: str
    body: str
    line: int = field(default=0, compare=False)


class Align(Enum):
    """A table column's alignment, as its delimiter cell spells it."""

    NONE = "---"
    LEFT = ":---"
    RIGHT = "---:"
    CENTER = ":---:"


@dataclass(frozen=True, slots=True)
class Table:
    r"""A pipe table: header cells, alignments, body rows.

    A cell is kept as written, escapes included, so a `\|` inside a
    code span is still a `\|` when the table is printed.
    """

    header: tuple[str, ...]
    align: tuple[Align, ...]
    rows: tuple[tuple[str, ...], ...]
    line: int = field(default=0, compare=False)


@dataclass(frozen=True, slots=True)
class Item:
    """One list item: the blocks it holds."""

    blocks: tuple[Block, ...]
    line: int = field(default=0, compare=False)


@dataclass(frozen=True, slots=True)
class ListBlock:
    """A list: its items, where its numbering starts, and its spacing.

    `start` is None for a `-` list. A loose list has a blank line
    between items; a tight one has none.
    """

    items: tuple[Item, ...]
    start: int | None = None
    loose: bool = False
    line: int = field(default=0, compare=False)


class Alert(Enum):
    """The kind a GitHub alert names on its quote's first line."""

    NOTE = "NOTE"
    TIP = "TIP"
    IMPORTANT = "IMPORTANT"
    WARNING = "WARNING"
    CAUTION = "CAUTION"


@dataclass(frozen=True, slots=True)
class Quote:
    """A block quote: the blocks it holds, and the alert it is, if any.

    `> [!NOTE]` makes a quote an alert only on a line of its own; joined
    to the text after it, it is that text's first word. The alert is
    kept apart from the blocks so filling cannot join the two.
    """

    blocks: tuple[Block, ...]
    alert: Alert | None = None
    line: int = field(default=0, compare=False)


@dataclass(frozen=True, slots=True)
class Divider:
    """A `---` rule between blocks."""

    line: int = field(default=0, compare=False)


type Block = Heading | Paragraph | Fence | Table | ListBlock | Quote | Divider


@dataclass(frozen=True, slots=True)
class Doc:
    """A file: its frontmatter, if it has any, and its blocks."""

    frontmatter: str | None
    blocks: tuple[Block, ...]

    @classmethod
    def parse(cls, text: str) -> Self:
        """The tree `text` is read as. Every text is read as some tree.

        A file whose first line of text is `---` opens with
        frontmatter, which runs to the next `---` line, or to the end.
        Read otherwise, a leading rule would print as frontmatter.
        """
        lines = [line.rstrip() for line in text.split("\n")]
        top = next((i for i, line in enumerate(lines) if line), len(lines))
        if top == len(lines) or lines[top].strip() != "---":
            return cls(None, _blocks(lines, 1))
        close = next(
            (i for i in range(top + 1, len(lines)) if lines[i].strip() == "---"),
            len(lines),
        )
        body = _blocks(lines[close + 1 :], close + 2)
        return cls("\n".join(lines[top + 1 : close]), body)

    @override
    def __str__(self) -> str:
        """The canonical text of this tree."""
        parts = [] if self.frontmatter is None else [f"---\n{self.frontmatter}\n---"]
        parts.extend("\n".join(printed(block)) for block in self.blocks)
        return "\n\n".join(parts) + "\n" if parts else ""


# ------------------------------------------------------------------
# words and filling

#: A word that would begin a block if it began a line: a list marker,
#: a heading's hashes, a rule or a setext underline, a quote, a pipe,
#: an HTML tag, a fence, an alert. Filling never starts a line with one
#: or leaves one alone on its first line, so a filled paragraph reads
#: back as the paragraph it was, here and in any CommonMark renderer.
_LEADS = re.compile(
    r"[-+*=]+|_{3,}|\d{1,9}[.)]|#{1,6}|[>|<].*|(?:```|~~~).*|\[![A-Z]+\]"
)


def words(text: str) -> tuple[str, ...]:
    """The words of running text, split at whitespace.

    A code span and a link are each one word with the spaces inside
    them kept, and a line break inside one becomes a space.
    """
    out: list[str] = []
    word: list[str] = []
    i = 0
    while i < len(text):
        end = _inline_end(text, i)
        if end > i:
            word.append(re.sub(r"[ \t]*\n[ \t]*", " ", text[i:end]))
            i = end
        elif text[i].isspace():
            if word:
                out.append("".join(word))
                word = []
            i += 1
        else:
            word.append(text[i])
            i += 1
    if word:
        out.append("".join(word))
    return tuple(out)


def _inline_end(text: str, i: int) -> int:
    """Where the code span, link or escape starting at `i` ends.

    `i` itself when none starts there.
    """
    if text[i] == "\\" and i + 1 < len(text) and not text[i + 1].isspace():
        return i + 2
    if text[i] == "`":
        run = _run(text, i)
        close = _closing(text, i + run, run)
        return close + run if close >= 0 else i + run
    if text.startswith(("[", "!["), i):
        return _link_end(text, i)
    return i


def _run(text: str, i: int) -> int:
    """The length of the run of backticks starting at `i`."""
    j = i
    while j < len(text) and text[j] == "`":
        j += 1
    return j - i


def _closing(text: str, i: int, run: int) -> int:
    """Where the next run of exactly `run` backticks starts, or -1."""
    while (i := text.find("`", i)) >= 0:
        found = _run(text, i)
        if found == run:
            return i
        i += found
    return -1


def _link_end(text: str, i: int) -> int:
    """Where `[text](target)` or `![text](target)` at `i` ends.

    `i` when no link starts there.
    """
    close = _matching(text, i + text.startswith("!", i), "[", "]")
    if close < 0 or not text.startswith("(", close + 1):
        return i
    end = _matching(text, close + 1, "(", ")")
    return end + 1 if end >= 0 else i


def _matching(text: str, i: int, opener: str, closer: str) -> int:
    """The `closer` that balances the `opener` at `i`, or -1.

    Code spans and escapes inside are stepped over, and a blank line
    ends the search, as it ends a paragraph.
    """
    depth, j = 0, i
    while j < len(text):
        c = text[j]
        if c in "`\\":
            j = max(_inline_end(text, j), j + 1)
            continue
        if text.startswith("\n\n", j):
            return -1
        depth += (c == opener) - (c == closer)
        if depth == 0:
            return j
        j += 1
    return -1


def wrap(words: Sequence[str], width: int = WIDTH) -> list[str]:
    """`words` filled greedily into lines of at most `width` columns.

    A word that would begin a block if it began a line is kept with the
    word before it, or, first in the paragraph, with the word after it.
    A word wider than `width` gets a line of its own, and passes it.
    """
    units: list[str] = []
    for word in words:
        lone_lead = len(units) == 1 and _LEADS.fullmatch(units[0]) is not None
        if units and (_LEADS.fullmatch(word) is not None or lone_lead):
            units[-1] = f"{units[-1]} {word}"
        else:
            units.append(word)
    out: list[str] = []
    for unit in units:
        if out and len(out[-1]) + 1 + len(unit) <= width:
            out[-1] = f"{out[-1]} {unit}"
        else:
            out.append(unit)
    return out


# ------------------------------------------------------------------
# reading

_FENCE = re.compile(r"(?P<ticks>`{3,})(?P<info>[^`]*)")
_HEADING = re.compile(r"(?P<marks>#{1,6})(?:[ \t]+(?P<text>.*))?")
_DIVIDER = re.compile(r"-{3,}")
_ITEM = re.compile(r"(?P<marker>-|(?P<number>\d{1,9})\.)(?: (?P<rest>.*))?")
_DELIMITER = re.compile(r"\|(?:[ \t]*:?-+:?[ \t]*\|)+")
_ALERT = re.compile(rf"\[!(?P<kind>{'|'.join(a.value for a in Alert)})\]")


def _indent(line: str) -> int:
    """How many spaces `line` starts with."""
    return len(line) - len(line.lstrip(" "))


def _interrupts(line: str) -> bool:
    """Does `line` end the paragraph above it and begin a block?"""
    s = line.lstrip(" ")
    return bool(
        _FENCE.fullmatch(s)
        or _HEADING.fullmatch(s)
        or _DIVIDER.fullmatch(s)
        or _ITEM.fullmatch(s)
        or s.startswith(">")
    )


def _blocks(lines: list[str], first: int) -> tuple[Block, ...]:
    """The blocks of `lines`, whose first is line `first` of its file.

    Each reader takes the lines from `i` and says where it stopped. Two
    lists of one kind with nothing between them are one list: no way of
    printing them could keep them apart.
    """
    out: list[Block] = []
    i = 0
    while i < len(lines):
        s = lines[i].lstrip(" ")
        if not s:
            i += 1
            continue
        at = first + i
        block: Block
        if _FENCE.fullmatch(s):
            block, i = _fence(lines, i, at)
        elif m := _HEADING.fullmatch(s):
            block, i = Heading(len(m["marks"]), (m["text"] or "").strip(), at), i + 1
        elif _DIVIDER.fullmatch(s):
            block, i = Divider(at), i + 1
        elif s.startswith("|") and _is_delimiter(lines, i + 1):
            block, i = _table(lines, i, at)
        elif s.startswith(">"):
            block, i = _quote(lines, i, at)
        elif _ITEM.fullmatch(s):
            block, i = _list(lines, i, first)
        else:
            block, i = _paragraph(lines, i, at)
        last = out[-1] if out else None
        if (
            isinstance(block, ListBlock)
            and isinstance(last, ListBlock)
            and (block.start is None) == (last.start is None)
        ):
            loose = last.loose or block.loose
            block = ListBlock(last.items + block.items, last.start, loose, last.line)
            out.pop()
        out.append(block)
    return tuple(out)


def _fence(lines: list[str], i: int, at: int) -> tuple[Fence, int]:
    """The fence opening at `i`, up to its closing line or the end.

    A body line loses as much indentation as the opening line had.
    """
    s = lines[i].lstrip(" ")
    m = _FENCE.fullmatch(s)
    ticks = len(m["ticks"]) if m else 3
    info = m["info"].strip() if m else ""
    indent = _indent(lines[i])
    body: list[str] = []
    j = i + 1
    while j < len(lines):
        inner = lines[j].lstrip(" ")
        if inner and set(inner) == {"`"} and len(inner) >= ticks:
            j += 1
            break
        body.append(lines[j][min(indent, _indent(lines[j])) :])
        j += 1
    return Fence(info, "".join(f"{b}\n" for b in body), at), j


def _is_delimiter(lines: list[str], i: int) -> bool:
    """Is line `i` a table's delimiter row?"""
    return i < len(lines) and bool(_DELIMITER.fullmatch(lines[i].strip()))


def _cells(row: str) -> tuple[str, ...]:
    r"""The cells of a table row, split at each unescaped pipe.

    A pipe inside a cell is written `\|`, as markdown requires even
    inside a code span.
    """
    inner = row.strip().removeprefix("|")
    if inner.endswith("|") and not inner.endswith("\\|"):
        inner = inner[:-1]
    first, *rest = inner.split("|")
    cells = [first]
    for part in rest:
        if cells[-1].endswith("\\"):
            cells[-1] += f"|{part}"
        else:
            cells.append(part)
    return tuple(cell.strip() for cell in cells)


def _table(lines: list[str], i: int, at: int) -> tuple[Table, int]:
    """The table whose header is line `i`."""
    header = _cells(lines[i])
    align = tuple(
        Align(f"{':' if c.startswith(':') else ''}---{':' if c.endswith(':') else ''}")
        for c in _cells(lines[i + 1])
    )
    j = i + 2
    rows: list[tuple[str, ...]] = []
    while j < len(lines) and lines[j].lstrip(" ").startswith("|"):
        rows.append(_cells(lines[j]))
        j += 1
    return Table(header, align, tuple(rows), at), j


def _quote(lines: list[str], i: int, at: int) -> tuple[Quote, int]:
    """The block quote at `i`: its `>` lines, read as blocks."""
    inner: list[str] = []
    j = i
    while j < len(lines) and lines[j].lstrip(" ").startswith(">"):
        s = lines[j].lstrip(" ")[1:]
        inner.append(s.removeprefix(" "))
        j += 1
    if m := _ALERT.fullmatch(inner[0].strip()):
        return Quote(_blocks(inner[1:], at + 1), Alert(m["kind"]), at), j
    return Quote(_blocks(inner, at), None, at), j


def _paragraph(lines: list[str], i: int, at: int) -> tuple[Paragraph, int]:
    """The paragraph starting at `i`, up to a blank line or a block."""
    j = i + 1
    while j < len(lines) and lines[j].strip() and not _interrupts(lines[j]):
        j += 1
    text = "\n".join(line.strip() for line in lines[i:j])
    return Paragraph(words(text), at), j


def _list(lines: list[str], i: int, first: int) -> tuple[ListBlock, int]:
    """The list whose first item is line `i`.

    It runs while items of the same kind follow at the same indent. An
    item holds every line indented to its content, and blank lines
    between such lines; blank lines between items make the list loose.
    """
    at, indent = first + i, _indent(lines[i])
    head = _ITEM.fullmatch(lines[i].lstrip(" "))
    ordered = head is not None and head["number"] is not None
    start = int(head["number"]) if head and head["number"] else None
    items: list[Item] = []
    loose = False
    while (m := _item_at(lines, i, indent, ordered=ordered)) is not None:
        content_indent = indent + len(m["marker"]) + 1
        content = [m["rest"] or ""]
        j = i + 1
        while (k := _next_content(lines, j, content_indent)) is not None:
            content.extend("" for _ in range(j, k))
            content.append(lines[k][content_indent:])
            j = k + 1
        items.append(Item(_blocks(content, first + i), first + i))
        k = j
        while k < len(lines) and not lines[k].strip():
            k += 1
        if _item_at(lines, k, indent, ordered=ordered) is None:
            i = j
            break
        loose |= k > j
        i = k
    return ListBlock(tuple(items), start, loose, at), i


def _item_at(
    lines: list[str], i: int, indent: int, *, ordered: bool
) -> re.Match[str] | None:
    """The item of this list on line `i`, if one is there."""
    if i >= len(lines) or _indent(lines[i]) != indent:
        return None
    m = _ITEM.fullmatch(lines[i].lstrip(" "))
    if m is None or (m["number"] is not None) != ordered:
        return None
    return m


def _next_content(lines: list[str], j: int, content_indent: int) -> int | None:
    """The next line of an item's content at or after `j`, if any.

    Blank lines are passed over only when a line indented to the
    content follows them.
    """
    k = j
    while k < len(lines) and not lines[k].strip():
        k += 1
    if k < len(lines) and _indent(lines[k]) >= content_indent:
        return k
    return None


# ------------------------------------------------------------------
# printing


def printed(block: Block, width: int = WIDTH) -> list[str]:
    """The canonical lines of `block`, filled to `width`."""
    out: list[str]
    match block:
        case Heading(level, text):
            out = ["#" * level + (f" {text}" if text else "")]
        case Paragraph(words):
            out = [" ".join(words)] if _is_entry(words) else wrap(words, width)
        case Fence(info, body):
            out = _fence_lines(info, body)
        case Table(header, align, rows):
            delimiter = "|" + "|".join(a.value for a in align) + "|"
            out = [_row(header), delimiter, *(_row(row) for row in rows)]
        case ListBlock():
            out = _list_lines(block, width)
        case Quote(blocks, alert):
            inner = list(_joined(blocks, width - 2, in_item=False))
            if alert is not None:
                inner.insert(0, f"[!{alert.value}]")
            out = [f"> {ln}" if ln else ">" for ln in inner] or [">"]
        case Divider():
            out = ["---"]
    return out


#: The tiers as a contents entry spells them.
_TIERS = frozenset(str(t) for t in Tier)


def _is_entry(words: tuple[str, ...]) -> bool:
    """Do `words` open with an ID and a tier, as a contents entry does?

    An entry names its rule as the rule's heading does, so like a
    heading it is one line, however long: an entry split across lines
    is read back truncated by anything that reads it line by line.
    """
    return (
        len(words) > 1
        and words[1] in _TIERS
        and bool(re.fullmatch(rule_id(), words[0]))
    )


def _fence_lines(info: str, body: str) -> list[str]:
    """A fence long enough that no line of its body closes it."""
    body_lines = body.split("\n")[:-1] if body else []
    closers = [len(s) for b in body_lines if (s := b.lstrip(" ")) and set(s) == {"`"}]
    ticks = "`" * max([3, *(n + 1 for n in closers)])
    return [f"{ticks}{info}", *body_lines, ticks]


def _row(cells: tuple[str, ...]) -> str:
    """`| a | b |`, and `| |` for an empty cell."""
    return "|" + "|".join(f" {cell} " if cell else " " for cell in cells) + "|"


def _list_lines(block: ListBlock, width: int) -> list[str]:
    """Each item under its marker, its content indented to match."""
    out: list[str] = []
    for k, item in enumerate(block.items):
        if k and block.loose:
            out.append("")
        marker = "-" if block.start is None else f"{block.start + k}."
        pad = " " * (len(marker) + 1)
        inner = list(_joined(item.blocks, width - len(pad), in_item=True))
        out.append(f"{marker} {inner[0]}" if inner else marker)
        out.extend(f"{pad}{ln}" if ln else "" for ln in inner[1:])
    return out


def _joined(blocks: tuple[Block, ...], width: int, *, in_item: bool) -> Iterator[str]:
    """The lines of `blocks`, with a blank line between each two.

    In a list item a list follows its paragraph directly, as a nested
    list does in every standard's contents.
    """
    for k, block in enumerate(blocks):
        nested = isinstance(block, ListBlock) and isinstance(blocks[k - 1], Paragraph)
        if k and not (in_item and nested):
            yield ""
        yield from printed(block, width)
