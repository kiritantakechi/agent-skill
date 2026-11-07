"""The normal form a normalised standard is held to, and printed in.

No shipped standard is normalised yet (normalize-the-standards, decision
14), so the properties are tried on the demo standard their controls
break (`checks.demo`), and the normaliser's laws on every shipped file,
in memory: when a standard is normalised, `fmt` must already be a map
that loses no example and that a second run leaves alone.
"""

from dataclasses import replace
lazy from pathlib import Path

import pytest

from agent_skill.checks import by_name, demo
from agent_skill.checks.anatomy import disorder, restates
from agent_skill.doc import Doc, Fence, text_of, walk, words
from agent_skill.doc.chapter import Element, Rule
from agent_skill.doc.normal import bare, in_order, normal
from agent_skill.fmt import format_skill
from agent_skill.ids import RuleId, Tier
from agent_skill.model import Skill, Tree

#: The checks the demo is held to whole, so that each control of the
#: normal form breaks it in one place: the two the controls target, its
#: canonical print, and its shared passages.
HELD = (
    "anatomy",
    "skeleton",
    "layout",
    "shared-text",
    "citations",
    "frontmatter",
    "prose",
)

#: The demo's chapter of rules.
ERRORS = "references/errors.md"


@pytest.fixture
def built(tmp_path: Path) -> Skill:
    """The demo standard, written and read with its own profile."""
    demo.build(tmp_path)
    return Skill(tmp_path / demo.PROFILE.name, demo.PROFILE)


def edit(skill: Skill, rel: str, old: str, new: str) -> Skill:
    """`skill` with one edit to `rel`, read again."""
    path = skill.root / rel
    text = path.read_text()
    assert old in text, f"{rel}: {old!r}"
    path.write_text(text.replace(old, new, 1))
    return Skill(skill.root, skill.profile)


def fired(skill: Skill, name: str) -> list[str]:
    """The branch of each failure `name` reports in `skill`."""
    check = by_name(name)
    assert check is not None, name
    return [str(f.branch) for f in check.run(Tree.of([skill])).fails]


def fails(skill: Skill, name: str) -> list[str]:
    """What `name` fails or could not look at in `skill`."""
    check = by_name(name)
    assert check is not None, name
    result = check.run(Tree.of([skill]))
    return [str(f) for f in (*result.fails, *result.unrun)]


@pytest.mark.parametrize("name", HELD)
def test_the_demo_holds_every_property(built: Skill, name: str) -> None:
    """Else a control on it could pass on a defect it did not inject."""
    assert fails(built, name) == []


def rule(markdown: str, title: str = "Return the error", tier: Tier = Tier.M) -> Rule:
    """A rule of the demo's family, its body read from `markdown`."""
    return Rule(RuleId("DS", "ERR", 1), tier, title, Doc.parse(markdown).blocks)


def said(r: Rule) -> list[str]:
    """Each block of the rule's body, as its first line prints."""
    return [text_of((b,)).split("\n")[0] for b in r.body]


GOOD = "```text\n// verified — GOOD\nok\n```"
FRAGMENT = "```text\n// fragment\npart\n```"
BAD = "```text\n// verified — BAD\nno\n```"


def test_a_rule_reads_as_the_elements_it_states() -> None:
    r = rule(
        f"Says it.\n\n*Relaxed form:* less.\n\n**Why:** w.\n\nMore of why.\n\n"
        f"**Check:** c.\n\n{GOOD}\n\nAfter it.\n\n**Note:** n."
    )
    assert [(p.element, len(p.blocks)) for p in r.parts] == [
        (Element.STATEMENT, 1),
        (Element.RELAXED, 1),
        (Element.WHY, 2),
        (Element.CHECK, 1),
        (Element.EXAMPLE, 1),
        (Element.STRAY, 1),
        (Element.STRAY, 1),
    ]


def test_fmt_puts_a_rules_elements_in_order() -> None:
    r = rule(f"Says it.\n\n{GOOD}\n\n**Check:** c.\n\n**Why:** w.\n\nMore of why.")
    assert disorder(r) == (Element.CHECK, Element.EXAMPLE)
    ordered = in_order(r)
    assert said(ordered) == [
        "Says it.",
        "**Why:** w.",
        "More of why.",
        "**Check:** c.",
        "```text",
    ]
    assert disorder(ordered) is None


def test_a_stray_block_moves_with_what_it_follows() -> None:
    """Prose after an example stays beside it, for a person to place."""
    r = rule(
        f"Says it.\n\n{GOOD}\n\nAfter it.\n\n{BAD}\n\n**Why:** w.\n\n**Check:** c."
    )
    ordered = in_order(r)
    assert said(ordered) == [
        "Says it.",
        "**Why:** w.",
        "**Check:** c.",
        "```text",
        "After it.",
        "```text",
    ]
    assert [f.body.split("\n")[0] for f in ordered.examples] == [
        "// verified — GOOD",
        "// verified — BAD",
    ]


@pytest.mark.parametrize(
    ("statement", "restated"),
    [
        ("Never use features for mutually exclusive choices.", True),
        (
            "Never use **features** for `mutually` exclusive choices: one per crate.",
            True,
        ),
        ("A feature is additive, so never use one for a choice.", False),
        ("Never use features.", False),
    ],
)
def test_a_statement_that_opens_with_its_title_restates_it(
    statement: str,
    restated: bool,  # noqa: FBT001 — a parametrised expectation
) -> None:
    title = "Never use features for mutually exclusive choices"
    assert restates(rule(f"{statement}\n\n**Why:** w.", title)) is restated


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("as `RS-ERR-03` says", "as RS-ERR-03 says"),
        ("(`references/errors.md` RS-ERR-03).", "(RS-ERR-03)."),
        ("see `references/api.md` RS-API-15, RS-API-16", "see RS-API-15, RS-API-16"),
        ("`references/errors.md` `RS-ERR-03`'s table", "RS-ERR-03's table"),
        # A family is not a rule, and a path alone names a chapter,
        # which a person rewrites.
        ("the `RS-ERR` family", "the `RS-ERR` family"),
        ("`references/errors.md` lists them", "`references/errors.md` lists them"),
        # Code that holds an ID is code.
        ('`reason = "RS-ERR-03"`', '`reason = "RS-ERR-03"`'),
    ],
)
def test_a_citation_is_set_bare(text: str, expected: str) -> None:
    assert " ".join(bare(words(text))) == expected


def test_fmt_prints_a_normalized_standard_in_normal_form(built: Skill) -> None:
    broken = edit(
        built, ERRORS, "as DS-ERR-01 says", "as `references/errors.md` `DS-ERR-01` says"
    )
    broken = edit(
        broken,
        ERRORS,
        "**Check:** read each function",
        f"{FRAGMENT}\n\n**Check:** read each function",
    )
    assert fails(broken, "anatomy")
    format_skill(broken)
    fixed = Skill(built.root, built.profile)
    assert fails(fixed, "anatomy") == []
    assert "as DS-ERR-01 says" in (fixed.root / ERRORS).read_text()


def test_fmt_leaves_a_standard_that_is_not_normalized_as_it_is(built: Skill) -> None:
    """While the gate stands, a standard's citations are its own."""
    plain = Skill(built.root, replace(demo.PROFILE, normalized=False))
    quoted = edit(plain, ERRORS, "as DS-ERR-01 says", "as `DS-ERR-01` says")
    before = (quoted.root / ERRORS).read_text()
    format_skill(quoted)
    assert (quoted.root / ERRORS).read_text() == before
    assert fails(quoted, "anatomy") == []


def test_the_normal_form_is_a_law_abiding_map_on_every_shipped_file(
    skills: list[Skill],
) -> None:
    """Idempotent, read back as printed, and no example touched.

    So normalising a standard is one run of `fmt` and a reading of what
    it could not place, never a repair of what it broke.
    """
    for skill in skills:
        chapters = {c.path for c in skill.chapters}
        for path, doc in skill.docs.items():
            once = normal(doc, chapter=path in chapters)
            assert Doc.parse(str(once)) == once, path
            assert normal(once, chapter=path in chapters) == once, path
            bodies = sorted(f.body for f in walk(doc.blocks) if isinstance(f, Fence))
            kept = sorted(f.body for f in walk(once.blocks) if isinstance(f, Fence))
            assert kept == bodies, path


#: The demo's section 4, as `fmt` renders it from the rules it lists.
CORE = (
    "## 4. Core rules\n\n"
    "- **Errors**\n"
    "  - DS-ERR-01 [M!] Return an error for a failure the caller can handle\n"
    "- **Migration**\n"
    "  - DS-MIG-01 [M] Write the new name of a renamed function\n"
)


def test_section_4_is_rendered_from_the_ids_it_lists(built: Skill) -> None:
    """Any list of the IDs, in any order or grouping, renders as one.

    So the IDs are the projection's source, and the rendering is its
    fixed point: a second `fmt` changes nothing.
    """
    assert CORE in built.text
    flat = edit(
        built,
        "SKILL.md",
        CORE,
        "## 4. Core rules\n\n- DS-MIG-01 [S] An old title\n- DS-ERR-01 [M] Another\n",
    )
    assert fired(flat, "skeleton") == ["skeleton.core_drift"]
    format_skill(flat)
    once = (built.root / "SKILL.md").read_text()
    assert CORE in once
    format_skill(Skill(built.root, built.profile))
    assert (built.root / "SKILL.md").read_text() == once
    assert fails(Skill(built.root, built.profile), "skeleton") == []


def test_fmt_leaves_a_section_4_it_cannot_project_as_it_is(built: Skill) -> None:
    """A core rule of its own is a person's to map, through `revise`."""
    own = edit(
        built,
        "SKILL.md",
        "- **Migration**",
        "- **DS-CORE-01 `[M]`** Return an error (DS-ERR-01).\n- **Migration**",
    )
    before = (own.root / "SKILL.md").read_text()
    found = format_skill(own)
    assert [str(f.branch) for f in found if f.level.name == "FAIL"] == [
        "fmt.core_unrendered"
    ]
    assert (own.root / "SKILL.md").read_text() == before
    assert fired(own, "skeleton") == ["skeleton.core_rule"]


#: The demo's migration chapter.
MIGRATION = "references/migration.md"


def test_fmt_writes_the_command_the_migration_table_generates(built: Skill) -> None:
    """A row added is a pattern added: the command is the table's."""
    added = edit(
        built,
        MIGRATION,
        "| `old_flag` | `new_flag` | alias | 1.1 | DS-MIG-01 |\n",
        "| `old_flag` | `new_flag` | alias | 1.1 | DS-MIG-01 |\n"
        "| `it's` | `its` | gone | 1.1 | DS-MIG-01 |\n"
        "| `old_mode` | `new_mode` | changed | 1.1 | DS-MIG-01 |\n",
    )
    assert fired(added, "skeleton") == ["skeleton.migration_command"]
    format_skill(added)
    fixed = Skill(built.root, built.profile)
    assert fired(fixed, "skeleton") == []
    text = (fixed.root / MIGRATION).read_text()
    assert "  -e 'old_flag' \\\n  -e 'it'\\''s' \\\n  .\n" in text
    assert "old_mode' \\" not in text


def _gone_section(skill: Skill) -> str:
    """Section 2.2 of `skill`'s `SKILL.md`, heading to next heading."""
    text = (skill.root / "SKILL.md").read_text()
    start = text.index("### 2.2 No longer compiles")
    return text[start : text.index("### 2.3", start)]


def test_fmt_renders_section_2_2_from_the_rows_the_target_made(built: Skill) -> None:
    """A row of 1.2 joins section 2.2; one moved to 1.1 leaves it."""
    edited = edit(
        built,
        MIGRATION,
        "| `old_name` | `new_name` | gone | 1.2 | DS-MIG-01 |\n",
        "| `old_name` | `new_name` | gone | 1.1 | DS-MIG-01 |\n"
        "| `old_mode` | `new_mode` | changed | 1.2 | DS-MIG-01 |\n",
    )
    assert fired(edited, "skeleton") == ["skeleton.reality_drift"]
    format_skill(edited)
    fixed = Skill(built.root, built.profile)
    assert fired(fixed, "skeleton") == []
    section = _gone_section(fixed)
    assert "| `old_mode` | `new_mode` | DS-MIG-01 |" in section
    assert "old_name" not in section
    assert " ".join(section.split()).endswith("whatever its release.")
    format_skill(fixed)
    assert _gone_section(Skill(built.root, built.profile)) == section


def test_section_2_2_with_no_row_of_the_target_is_its_closing_line(
    built: Skill,
) -> None:
    """No table over no row: the line saying where they are stays."""
    edited = edit(
        built,
        MIGRATION,
        "| `old_name` | `new_name` | gone | 1.2 | DS-MIG-01 |",
        "| `old_name` | `new_name` | gone | 1.1 | DS-MIG-01 |",
    )
    format_skill(edited)
    fixed = Skill(built.root, built.profile)
    assert fired(fixed, "skeleton") == []
    section = _gone_section(fixed)
    assert "|" not in section
    assert "`DS-MIG` in section 6" in section


@pytest.mark.parametrize(
    ("since", "said"),
    [
        ("1.3", "after the target's, `1.2`"),
        ("1.2.0", "not a release's series, `1.2`"),
        ("2024", "is no release"),
        ("soon", "is no release"),
    ],
)
def test_a_since_the_target_cannot_have_is_a_row_misread(
    built: Skill, since: str, said: str
) -> None:
    edited = edit(
        built,
        MIGRATION,
        "| `old_flag` | `new_flag` | alias | 1.1 | DS-MIG-01 |",
        f"| `old_flag` | `new_flag` | alias | {since} | DS-MIG-01 |",
    )
    assert fired(edited, "skeleton") == ["skeleton.migration_row"]
    assert said in fails(edited, "skeleton")[0]
