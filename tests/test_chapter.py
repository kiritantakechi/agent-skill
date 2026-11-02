"""The chapter layer: lossless over the tree, and in step with `model`.

`model` is the reader every check uses today. Each test here holds the
new layer to what the old one finds in the shipped skills, so the new
one is shown right on the corpus before any check moves onto it.
"""

import pytest

from agent_skill.doc import Doc, Fence, ListBlock, Quote, printed
from agent_skill.doc.chapter import (
    Chapter,
    Demoted,
    Removed,
    Rule,
    SkillMd,
    _becomes,
)
from agent_skill.ids import RuleId, Tier
lazy from agent_skill.doc import Block
lazy from agent_skill.model import Skill


def _read(chapter_text: str) -> Chapter:
    return Chapter.read(Doc.parse(chapter_text))


def _prose(blocks: tuple[Block, ...]) -> list[str]:
    """The words of `blocks` as printed, with quote markers dropped."""
    return [w for b in blocks for line in printed(b) for w in line.split() if w != ">"]


def _unquoted(text: str) -> list[str]:
    """The words of raw text, with quote markers dropped."""
    return [w for w in text.split() if w != ">"]


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


def test_the_new_layer_finds_every_rule_the_old_one_does(skills: list[Skill]) -> None:
    found = 0
    for skill in skills:
        for chapter in skill.chapters:
            old = [(r.id, r.tier, r.title) for r in chapter.rules]
            new = [
                (str(r.id), r.tier.value, r.title) for r in _read(chapter.text).rules
            ]
            assert new == old, f"{skill.name}/{chapter.name}"
            found += len(new)
    assert found > 1000


def test_each_rule_is_found_on_the_line_the_old_layer_gives(
    skills: list[Skill],
) -> None:
    for skill in skills:
        for chapter in skill.chapters:
            old = [r.line for r in chapter.rules]
            assert [r.line for r in _read(chapter.text).rules] == old, chapter.name


def test_the_contents_lists_the_entries_the_old_layer_reads(
    skills: list[Skill],
) -> None:
    for skill in skills:
        for chapter in skill.chapters:
            contents = _read(chapter.text).contents
            entries = contents.entries if contents else ()
            new = {str(e.id): (e.tier.value, e.title) for e in entries}
            assert new == chapter.toc, f"{skill.name}/{chapter.name}"
            assert len(entries) == len(new)


def test_the_tool_table_has_the_rows_the_old_layer_reads(
    skills: list[Skill],
) -> None:
    for skill in skills:
        for chapter in skill.chapters:
            old = [(r.tool, r.lint, r.level, r.forbids) for r in chapter.lint_rows]
            new = [
                (r.tool, r.lint, r.level, r.forbids) for r in _read(chapter.text).tools
            ]
            assert new == old, f"{skill.name}/{chapter.name}"


def test_each_rename_table_states_what_the_old_layer_reads(
    skills: list[Skill],
) -> None:
    rows = 0
    for skill in skills:
        for chapter in skill.chapters:
            tables = _read(chapter.text).renames
            assert len(tables) == len(chapter.rename_tables)
            for old, new in zip(chapter.rename_tables, tables, strict=True):
                assert [
                    (f"{a.standard}-{a.family}", a.number, b.number)
                    for a, b in new.ranges
                ] == list(old.ranges)
                assert [str(r) for r in new.originals] == old.originals
                for was, now in zip(old.rows, new.rows, strict=True):
                    assert str(now.before) == was.before
                    match now.now:
                        case RuleId():
                            assert str(now.now) == was.target
                        case Demoted(tool, lint):
                            assert (tool, lint) == was.lint
                        case Removed(reason):
                            assert reason == was.removed
                    rows += 1
    assert rows > 1000


def test_the_core_rules_are_the_ones_the_old_layer_reads(
    skills: list[Skill],
) -> None:
    for skill in skills:
        core = SkillMd.read(Doc.parse(skill.text)).core_rules
        old = [(rid, tier) for rid, tier, _ in skill.core_rules]
        assert [(str(r.id), str(r.tier)) for r in core] == old, skill.name


def test_a_core_rule_and_a_chapter_rule_are_one_type(skills: list[Skill]) -> None:
    zig = next(s for s in skills if s.name == "zig-style")
    core = SkillMd.read(Doc.parse(zig.text)).core_rules
    chapter = _read(zig.chapters[0].text).rules
    assert {type(core[0]), type(chapter[0])} == {Rule}
    assert {type(core[0].tier), type(chapter[0].tier)} == {Tier}
    assert RuleId.parse("ZS-CORE-12a") in {r.id for r in core}


def test_why_and_check_say_what_the_old_layer_reads(skills: list[Skill]) -> None:
    for skill in skills:
        for chapter in skill.chapters:
            new = _read(chapter.text).rules
            for old, rule in zip(chapter.rules, new, strict=True):
                assert _prose(rule.why)[1:] == _unquoted(old.why), old.id
                assert _prose(rule.check)[1:] == _unquoted(old.check), old.id


def test_every_example_the_old_layer_finds_is_a_fence_of_the_tree(
    skills: list[Skill],
) -> None:
    for skill in skills:
        for document in skill.documents:
            old = sorted(
                (b.lang, b.body)
                for lang in skill.profile.languages
                for b in document.blocks(lang)
            )
            fences = _fences(Doc.parse(document.text).blocks)
            new = sorted(
                (f.info, f.body) for f in fences if f.info in skill.profile.languages
            )
            assert new == old, f"{skill.name}/{document.name}"


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
    assert _becomes(cell) == becomes


def test_a_rename_row_that_says_nothing_known_is_refused() -> None:
    with pytest.raises(ValueError, match="not an ID, a lint row or a removal"):
        _becomes("see above")
