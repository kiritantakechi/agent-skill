"""The chapter layer: lossless over the tree, complete on the corpus.

It is the one reader of a standard's rules, tables and rename history.
The line-wise readers it was first held to are gone, so it is held here
to the tree it reads: every heading that names a rule is a rule, every
row of a rename table is read, and every example is a fence of the tree.
"""

import pytest

from agent_skill.doc import (
    Doc,
    Fence,
    Heading,
    ListBlock,
    Quote,
    Table,
    entry,
    printed,
    words,
)
from agent_skill.doc.chapter import (
    Chapter,
    Demoted,
    Removed,
    Rule,
    SkillMd,
    citing,
    owned,
    parse_becomes,
    print_becomes,
)
from agent_skill.ids import RuleId, Tier
lazy from agent_skill.doc import Block
lazy from agent_skill.model import Skill


def _read(chapter_text: str) -> Chapter:
    return Chapter.read(Doc.parse(chapter_text))


def _prose(blocks: tuple[Block, ...]) -> list[str]:
    """The words of `blocks` as printed, with quote markers dropped."""
    return [w for b in blocks for line in printed(b) for w in line.split() if w != ">"]


def _fences(blocks: tuple[Block, ...]) -> list[Fence]:
    out: list[Fence] = []
    for b in blocks:
        if isinstance(b, Fence):
            out.append(b)
        elif isinstance(b, ListBlock):
            out.extend(f for item in b.items for f in _fences(item.blocks))
        elif isinstance(b, Quote):
            out.extend(_fences(b.blocks))
    return out


def test_every_shipped_chapter_reads_back_as_its_tree(skills: list[Skill]) -> None:
    for skill in skills:
        for chapter in skill.chapters:
            doc = Doc.parse(chapter.text)
            assert Chapter.read(doc).doc() == doc, f"{skill.name}/{chapter.name}"


def test_every_skill_md_reads_back_as_its_tree(skills: list[Skill]) -> None:
    for skill in skills:
        doc = Doc.parse(skill.text)
        assert SkillMd.read(doc).doc() == doc, skill.name


def _rule_headings(doc: Doc) -> list[tuple[RuleId, Tier, str, int]]:
    """Every `###` heading of `doc` that names a rule, with its line."""
    return [
        (*found, b.line)
        for b in doc.blocks
        if isinstance(b, Heading) and b.level == 3
        if (found := entry(words(b.text))) is not None
    ]


def test_every_heading_that_names_a_rule_is_a_rule(skills: list[Skill]) -> None:
    found = 0
    for skill in skills:
        for chapter in skill.chapters:
            rules = [(r.id, r.tier, r.title, r.line) for r in chapter.typed.rules]
            assert rules == _rule_headings(chapter.doc), chapter.name
            found += len(rules)
    assert found > 1000


def test_every_rename_row_and_range_is_read(skills: list[Skill]) -> None:
    rows = 0
    for skill in skills:
        for chapter in skill.chapters:
            for table in chapter.typed.renames:
                assert table.ranges, f"{skill.name}: {table.heading}"
                assert table.unread == (), f"{skill.name}: {table.heading}"
                listed = {r.before for r in table.rows}
                assert listed <= set(table.originals), table.heading
                rows += len(table.rows)
    assert rows > 1000


def test_every_core_rule_is_an_item_of_section_4(skills: list[Skill]) -> None:
    """Core rules until a standard is normalised, then none."""
    for skill in skills:
        core = skill.core
        assert bool(core) != skill.profile.normalized, skill.name
        assert all(r.id.family == "CORE" and not r.title for r in core), skill.name


def test_a_core_rule_and_a_chapter_rule_are_one_type(skills: list[Skill]) -> None:
    zig = next(s for s in skills if s.name == "zig-style")
    core = SkillMd.read(Doc.parse(zig.text)).core_rules
    chapter = _read(zig.chapters[0].text).rules
    assert {type(core[0]), type(chapter[0])} == {Rule}
    assert {type(core[0].tier), type(chapter[0].tier)} == {Tier}
    assert RuleId.parse("ZS-CORE-12a") in {r.id for r in core}


def test_every_example_is_a_fence_of_the_tree(skills: list[Skill]) -> None:
    for skill in skills:
        for document in skill.documents:
            blocks = sorted(
                (b.lang, b.body)
                for lang in skill.profile.languages
                for b in document.blocks(lang)
            )
            fences = _fences(Doc.parse(document.text).blocks)
            want = sorted(
                (f.info, f.body) for f in fences if f.info in skill.profile.languages
            )
            assert blocks == want, f"{skill.name}/{document.name}"


def test_an_example_is_under_the_rule_whose_heading_is_above_it() -> None:
    """And under none in a section's lead.

    The line-wise reader carried the rule above the section on into it.
    """
    text = CHAPTER + "\n## More\n\n```zig\n// fragment\n```\n"
    owners = [rule for b, rule in owned(Doc.parse(text)) if isinstance(b, Fence)]
    assert owners == [RuleId.parse("XS-OUT-01"), None]


CHAPTER = """# Output

Scope: what a review prints.

## Contents

- **Format**
  - XS-OUT-01 [M] Print the findings as a table
  - SMELL TEST
- Decided by tools

---

## Format

### XS-OUT-01 [M] Print the findings as a table

Say what was found.

*Relaxed form:* a list will do.

**Why:** a table sorts. It also aligns.

**Check:** read it.

```markdown
## Findings

### XS-OUT-02 [M] Not a rule, an example
```

The same, as a list:

### SMELL TEST

## Decided by tools

| Tool | Lint | Level | Forbids |
|---|---|---|---|
| `clippy` | `print_stdout` | deny | `println!` |
"""


def test_a_heading_inside_an_example_neither_ends_a_rule_nor_starts_one() -> None:
    chapter = _read(CHAPTER)
    (rule,) = chapter.rules
    assert rule.id == RuleId.parse("XS-OUT-01")
    assert rule.examples == (
        Fence("markdown", "## Findings\n\n### XS-OUT-02 [M] Not a rule, an example\n"),
    )
    assert [s.title for s in chapter.sections] == ["Format", "Decided by tools"]


def test_a_rule_reads_into_its_parts() -> None:
    (rule,) = _read(CHAPTER).rules
    assert _prose(rule.statement) == ["Say", "what", "was", "found."]
    assert _prose(rule.relaxed)[2:] == ["a", "list", "will", "do."]
    assert _prose(rule.why) == [
        "**Why:**",
        "a",
        "table",
        "sorts.",
        "It",
        "also",
        "aligns.",
    ]
    assert _prose(rule.check)[1:] == ["read", "it."]


def test_a_contents_label_may_name_a_part_that_is_not_a_rule() -> None:
    contents = _read(CHAPTER).contents
    assert contents is not None
    assert [str(e.id) for e in contents.entries] == ["XS-OUT-01"]
    assert str(Chapter.read(Doc.parse(CHAPTER)).doc()) == CHAPTER


def test_the_tool_table_is_read_from_its_section() -> None:
    (row,) = _read(CHAPTER).tools
    assert (row.tool, row.lint, row.level) == ("`clippy`", "print_stdout", "deny")


def test_a_block_outside_every_section_is_refused() -> None:
    text = CHAPTER.replace("---\n\n## Format", "---\n\nStray.\n\n## Format")
    with pytest.raises(ValueError, match="before the first `##` section"):
        _read(text)


def test_a_rule_before_every_section_is_refused() -> None:
    text = CHAPTER.replace("Scope: what", "### XS-OUT-09 [M] Early\n\nScope: what")
    with pytest.raises(ValueError, match="a rule before the first `##` section"):
        _read(text)


def test_a_contents_section_without_its_rule_is_refused() -> None:
    with pytest.raises(ValueError, match="one list, then a `---` rule"):
        _read(CHAPTER.replace("---\n\n## Format", "## Format", 1))


@pytest.mark.parametrize(
    ("cell", "becomes"),
    [
        ("`XS-ERR-02`", RuleId.parse("XS-ERR-02")),
        ("`XS-CORE-12a`", RuleId.parse("XS-CORE-12a")),
        ("lint `clippy:unwrap_used`", Demoted("clippy", "unwrap_used")),
        ("removed — XS-ERR-02 states it", Removed("XS-ERR-02 states it")),
    ],
)
def test_a_rename_row_says_what_the_old_id_became(
    cell: str, becomes: RuleId | Demoted | Removed
) -> None:
    assert parse_becomes(cell) == becomes
    assert print_becomes(becomes) == cell


def test_a_rename_row_that_says_nothing_known_reads_as_nothing() -> None:
    assert parse_becomes("see above") is None


RENAMED = """## Rule IDs before the Demo 1.2 revision

Before the revision the family ran `XS-OUT-01`\u2013`XS-OUT-04`.

| Before | Now |
|---|---|
| `XS-OUT-02` | `XS-OUT-01` |
| `XS-OUT-03` | see above |
| `XS-OUT` | removed — merged |
"""


def test_a_rename_row_it_cannot_read_is_kept_as_written() -> None:
    (table,) = _read(CHAPTER + "\n" + RENAMED).renames
    assert [(str(r.before), r.now) for r in table.rows] == [
        ("XS-OUT-02", RuleId.parse("XS-OUT-01"))
    ]
    assert table.unread == (
        ("`XS-OUT-03`", "see above"),
        ("`XS-OUT`", "removed — merged"),
    )
    # A row names its old ID, read or not: the rest are unchanged.
    assert [str(r) for r in table.unchanged] == ["XS-OUT-01", "XS-OUT-04"]


def test_a_tool_row_is_found_on_its_line() -> None:
    (row,) = _read(CHAPTER).tools
    assert CHAPTER.splitlines()[row.line - 1].startswith("| `clippy` |")


def test_only_the_rename_tables_section_cites_nothing() -> None:
    doc = Doc.parse(CHAPTER + "\n" + RENAMED + "\n## After\n\nXS-OUT-01 again.\n")
    kept = list(citing(doc))
    assert Heading(2, "Format") in kept
    assert Heading(2, "After") in kept
    assert Heading(2, "Rule IDs before the Demo 1.2 revision") not in kept
    assert not any(isinstance(b, Table) and b.header[0] == "Before" for b in kept)


SKILL_MD = """# Delta Style — 1.2

## 2. Delta 1.2 reality check

| Other rule | What applies instead | Why |
|---|---|---|
| `RS-API-15` Keep every struct field private | `XS-OUT-01` — public | Reasons. |
| Not an ID | `XS-OUT-01` | Skipped. |

## 4. Core rules

- **XS-CORE-01 `[M!]`** Say it. *Relaxed form:* less.
- **XS-CORE-02 `[X]`** Not a tier, so not a rule.
"""


def test_an_override_row_names_both_rules_and_quotes_a_title() -> None:
    (row,) = SkillMd.read(Doc.parse(SKILL_MD)).overrides
    assert row.theirs == RuleId.parse("RS-API-15")
    assert row.quoted == "Keep every struct field private"
    assert row.ours == RuleId.parse("XS-OUT-01")


def test_a_core_item_with_no_tier_is_no_rule() -> None:
    (core,) = SkillMd.read(Doc.parse(SKILL_MD)).core_rules
    assert (core.id, core.tier) == (RuleId.parse("XS-CORE-01"), Tier.M_BANG)
    assert _prose(core.body)[:2] == ["Say", "it."]
