"""The document model: printing inverts parsing; formatting projects.

Trees and texts are drawn from seeded generators, so a failure names a
case that reproduces.
"""

import random
from itertools import pairwise
from pathlib import Path
lazy from collections.abc import Callable

import pytest

from agent_skill.doc import (
    WIDTH,
    Alert,
    Align,
    Block,
    Divider,
    Doc,
    Fence,
    Heading,
    Item,
    ListBlock,
    Paragraph,
    Quote,
    Table,
    words,
    wrap,
)
from agent_skill.layout import SKILLS

ROOT = Path(__file__).resolve().parents[1]
SHIPPED = sorted((ROOT / SKILLS).rglob("*.md"))

#: Words a paragraph may open with.
PLAIN = (
    "the",
    "rule",
    "**Why:**",
    "*Relaxed",
    "form:*",
    "`code`",
    "`a  b`",
    "`x | y`",
    "``a ` b``",
    "[a link](https://example.com/a)",
    "![an image](i.png)",
    "RS-ERR-03,",
    "(`references/errors.md`",
    "0.17.3.",
    "x" * 30,
    "é—ü",
)

#: Words that would open a block at the start of a line.
LEADS = (
    "-",
    "+",
    "*",
    "1.",
    "12)",
    "#",
    "###",
    ">",
    ">x",
    "|",
    "|a|",
    "```",
    "---",
    "=",
)

#: The ones a paragraph may hold more than once: two lone runs of
#: backticks would read back as one code span.
REPEATABLE = tuple(lead for lead in LEADS if not lead.startswith("`"))

#: A word no line can hold.
LONG = "`rg -n '" + "x" * 120 + "'`"


def seeded(seed: int) -> random.Random:
    """A generator that draws the same cases on every run."""
    return random.Random(seed)  # noqa: S311 — reproducible test cases, not secrets


def _paragraph(rng: random.Random) -> Paragraph:
    first = rng.choice([*((w,) for w in PLAIN), ("BV-ECS-12", "[M!]")])
    rest = [
        rng.choice((*PLAIN, *PLAIN, *REPEATABLE, LONG))
        for _ in range(rng.randint(0, 40))
    ]
    return Paragraph((*first, *rest))


def _fence(rng: random.Random) -> Fence:
    pool = ("fn main() {}", "## not a heading", "- not an item", "| not | a row |")
    pool += ("> not a quote", "---", "", "    indented", "```", "````", "```rust")
    body = "".join(f"{rng.choice(pool)}\n" for _ in range(rng.randint(0, 5)))
    return Fence(rng.choice(("", "rust", "zig", "python", "sh")), body)


def _cell(rng: random.Random) -> str:
    return rng.choice(("", "a", "`X \\| None`", "**Mandatory** in all code", "`[M]`"))


def _table(rng: random.Random) -> Table:
    columns = rng.randint(1, 4)
    return Table(
        tuple(_cell(rng) for _ in range(columns)),
        tuple(rng.choice(list(Align)) for _ in range(columns)),
        tuple(
            tuple(_cell(rng) for _ in range(rng.randint(1, 5)))
            for _ in range(rng.randint(0, 3))
        ),
    )


def _blocks(rng: random.Random, depth: int, *, top: bool = False) -> tuple[Block, ...]:
    """Blocks as a container holds them.

    Two lists of one kind side by side read back as one list, and a
    file whose text opens with a rule opens with frontmatter, so
    neither is drawn.
    """
    out: list[Block] = []
    for _ in range(rng.randint(0, 4) if depth else rng.randint(1, 8)):
        block = _block(rng, depth)
        same_kind = (
            out
            and isinstance(block, ListBlock)
            and isinstance(out[-1], ListBlock)
            and (block.start is None) == (out[-1].start is None)
        )
        if same_kind or (top and not out and isinstance(block, Divider)):
            continue
        out.append(block)
    return tuple(out)


#: Deep enough to nest a list in a quote in a list.
DEPTH = 3


def _heading(rng: random.Random) -> Heading:
    text = " ".join(rng.choice(PLAIN) for _ in range(rng.randint(0, 4)))
    return Heading(rng.randint(1, 6), text)


def _list(rng: random.Random, depth: int) -> ListBlock:
    items = tuple(Item(_blocks(rng, depth + 1)) for _ in range(rng.randint(1, 4)))
    start = rng.choice((None, None, 1, 9, 10))
    # One item has no gap to be loose in.
    return ListBlock(items, start, loose=len(items) > 1 and rng.random() < 0.5)


def _quote(rng: random.Random, depth: int) -> Quote:
    return Quote(_blocks(rng, depth + 1), rng.choice((None, None, *Alert)))


def _block(rng: random.Random, depth: int) -> Block:
    kinds: list[Callable[[random.Random], Block]] = [
        _heading,
        _paragraph,
        _paragraph,
        _fence,
        _table,
        lambda _: Divider(),
    ]
    if depth < DEPTH:
        kinds += [lambda r: _list(r, depth)] * 2 + [lambda r: _quote(r, depth)]
    return rng.choice(kinds)(rng)


def _doc(rng: random.Random) -> Doc:
    frontmatter = rng.choice(
        (None, None, "name: x", "", "name: x\ndescription: >-\n  a b")
    )
    return Doc(frontmatter, _blocks(rng, 0, top=frontmatter is None))


def test_parsing_a_printed_tree_gives_the_tree_back() -> None:
    rng = seeded(20)
    for _ in range(600):
        doc = _doc(rng)
        text = str(doc)
        assert Doc.parse(text) == doc, text


def _noise(rng: random.Random) -> str:
    """Text no printer wrote: each construct, misspelt and misplaced."""
    pool = (
        "",
        "",
        "text and `code`",
        "a `span that",
        "runs on` here",
        "#",
        "## Title ##",
        "####### seven",
        "-",
        "- item",
        "  - nested",
        "    - deeper",
        "1. one",
        "10. ten",
        "   continued",
        "+ plus",
        "* star",
        ">",
        "> quoted",
        "> [!NOTE]",
        ">> twice",
        "|a|b|",
        "|---|:-:|",
        "| c |",
        "```",
        "```rust",
        "  ```",
        "---",
        "  ---",
        "***",
        "===",
        "[!WARNING]",
        "RS-ERR-01 [M] An entry",
        "\tTab",
        "word " * 30,
        LONG,
    )
    return "\n".join(rng.choice(pool) for _ in range(rng.randint(0, 30)))


def test_formatting_any_text_twice_changes_nothing_the_first_did_not() -> None:
    rng = seeded(21)
    for _ in range(1500):
        once = str(Doc.parse(_noise(rng)))
        assert str(Doc.parse(once)) == once, once


@pytest.mark.parametrize(
    "path", SHIPPED, ids=lambda p: str(p.relative_to(ROOT / SKILLS))
)
def test_every_shipped_file_survives_its_canonical_form(path: Path) -> None:
    doc = Doc.parse(path.read_text())
    canonical = str(doc)
    assert Doc.parse(canonical) == doc
    assert str(Doc.parse(canonical)) == canonical


def test_a_heading_inside_an_example_is_part_of_the_example() -> None:
    text = "### RS-ERR-01 [M] Rule\n\n```markdown\n## Findings\n- not an item\n```\n"
    doc = Doc.parse(text)
    assert [type(b) for b in doc.blocks] == [Heading, Fence]
    assert doc.blocks[1] == Fence("markdown", "## Findings\n- not an item\n")


def test_an_example_left_open_runs_to_the_end_and_is_closed() -> None:
    doc = Doc.parse("```zig\nconst x = 1;\n## still code\n")
    assert doc.blocks == (Fence("zig", "const x = 1;\n## still code\n\n"),)
    assert str(doc).endswith("```\n")
    (fence,) = doc.blocks
    assert isinstance(fence, Fence)
    assert not fence.closed
    (printed,) = Doc.parse(str(doc)).blocks
    assert isinstance(printed, Fence)
    assert printed.closed


def test_a_fence_is_long_enough_for_what_it_holds() -> None:
    fence = Fence("markdown", "```rust\nfn f() {}\n```\n")
    assert str(Doc(None, (fence,))).startswith("````markdown\n")
    assert Doc.parse(str(Doc(None, (fence,)))).blocks == (fence,)


def test_a_paragraph_is_filled_to_the_width() -> None:
    text = " ".join(["word"] * 60)
    lines = str(Doc.parse(text)).splitlines()
    assert all(len(line) <= WIDTH for line in lines)
    assert all(len(a) + 1 + len(b.split()[0]) > WIDTH for a, b in pairwise(lines))


def test_a_code_span_or_a_link_is_never_split() -> None:
    span = "`rg -n 'a b c' references/`"
    link = "[the build chapter](build.md#a-b)"
    assert words(f"see {span}, then\n{link}.") == (
        "see",
        f"{span},",
        "then",
        f"{link}.",
    )


def test_a_code_span_broken_across_lines_is_one_word() -> None:
    assert words("`// rejected —\n<tool>: …` — the") == (
        "`// rejected — <tool>: …`",
        "—",
        "the",
    )


def test_a_word_wider_than_the_line_has_a_line_of_its_own() -> None:
    assert wrap(["see", LONG, "and", "more"], 40) == ["see", LONG, "and more"]


@pytest.mark.parametrize("lead", LEADS)
def test_filling_never_starts_a_line_with_what_would_open_a_block(lead: str) -> None:
    for width in range(8, 30):
        lines = wrap(["aaaa", "bb", lead, "cccccc", "d"], width)
        assert not any(line.split()[0] == lead for line in lines[1:]), lines
        assert Doc.parse("\n".join(lines)).blocks == (
            Paragraph(("aaaa", "bb", lead, "cccccc", "d")),
        )


def test_a_contents_entry_stays_on_one_line_however_long() -> None:
    entry = (
        "ZS-MEM-06 [M] Name the allocator for its role — `gpa`, `arena`, "
        "`scratch` — and place it after the receiver"
    )
    assert len(entry) > WIDTH
    text = f"- **Part 1**\n  - {entry}\n"
    assert str(Doc.parse(text)) == text


def test_a_loose_list_is_spaced_between_every_item() -> None:
    text = "- **A**\n  - XS-A-01 [M] One\n\n- **B**\n  - XS-A-02 [S] Two\n- Decided\n"
    doc = Doc.parse(text)
    (contents,) = doc.blocks
    assert isinstance(contents, ListBlock)
    assert contents.loose
    assert str(doc) == text.replace("\n- Decided", "\n\n- Decided")


def test_an_ordered_list_is_numbered_from_its_start() -> None:
    doc = Doc.parse("9. nine\n9. ten\n   more of ten\n")
    assert str(doc) == "9. nine\n10. ten more of ten\n"


def test_a_table_keeps_its_escaped_pipes_and_empty_cells() -> None:
    text = "| Before | Now |\n|---|---|\n| `X \\| None` | |\n"
    (table,) = Doc.parse(text).blocks
    assert table == Table(
        ("Before", "Now"), (Align.NONE, Align.NONE), (("`X \\| None`", ""),)
    )
    assert str(Doc.parse(text)) == text


def test_an_alert_keeps_its_marker_on_a_line_of_its_own() -> None:
    text = "> [!NOTE]\n> The **non-array** hash maps did not follow.\n"
    (quote,) = Doc.parse(text).blocks
    assert isinstance(quote, Quote)
    assert quote.alert is Alert.NOTE
    assert str(Doc.parse(text)) == text


def test_a_marker_joined_to_its_text_is_not_an_alert() -> None:
    (quote,) = Doc.parse("> [!NOTE] At 0.17.0 each backend compiled.\n").blocks
    assert isinstance(quote, Quote)
    assert quote.alert is None


def test_frontmatter_is_kept_as_written() -> None:
    text = "---\nname: x\ndescription: >-\n  a b\n---\n\n# Title\n"
    doc = Doc.parse(text)
    assert doc.frontmatter == "name: x\ndescription: >-\n  a b"
    assert str(doc) == text


def test_a_block_knows_the_line_it_starts_on() -> None:
    doc = Doc.parse("---\nname: x\n---\n\n# Title\n\nText\nmore.\n\n- a\n- b\n")
    assert [b.line for b in doc.blocks] == [5, 7, 10]
    lst = doc.blocks[2]
    assert isinstance(lst, ListBlock)
    assert [item.line for item in lst.items] == [10, 11]
