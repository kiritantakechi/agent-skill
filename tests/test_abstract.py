"""The abstract standard, read by the parser that reads the standards.

`abstract/` is one file per abstract chapter in the chapter template,
and `principles.md`. The demo abstract standard (`checks.demo`) holds
every property, and is read here as the shipped one is.
"""

from pathlib import Path

import pytest

from agent_skill.abstract import (
    HEADER,
    PRINCIPLES,
    Abstract,
    Concept,
    abstract_of,
)
from agent_skill.checks import demo
from agent_skill.doc import Doc, canonical
from agent_skill.doc.chapter import Chapter
from agent_skill.fmt import format_abstract
from agent_skill.ids import Relation, RuleId, Tier
from agent_skill.layout import ABSTRACT
from agent_skill.model import Skill, Tree
from structure_fixture import repository

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def abstract(tmp_path: Path) -> Abstract:
    """The demo abstract standard, beside the demo and its delta."""
    return abstract_of(repository(tmp_path))


def test_the_abstract_standard_is_found_beside_the_skills(
    abstract: Abstract, tmp_path: Path
) -> None:
    assert abstract.root == tmp_path / ABSTRACT
    assert [c.path.name for c in abstract.chapters] == ["errors.md", "migration.md"]
    assert abstract.principles is not None
    assert abstract.words == {"errors", "migration"}


def test_a_tree_outside_a_repository_has_no_abstract_standard(tmp_path: Path) -> None:
    demo.build(tmp_path)
    found = abstract_of(Tree.of([Skill(tmp_path / demo.PROFILE.name, demo.PROFILE)]))
    assert found.root is None
    assert found.chapters == []
    assert found.questions == ()


def test_an_entry_is_a_rule_whose_body_is_a_statement_and_a_table(
    abstract: Abstract,
) -> None:
    concepts = [concept for _, concept in abstract.concepts]
    assert [str(c.id) for c in concepts] == ["AS-ERR-01", "AS-ERR-02", "AS-ERR-03"]
    first = concepts[0]
    assert first.tier is Tier.M_BANG
    assert first.shaped
    assert len(first.statement) == 1
    (row,) = first.rows
    assert (row.standard, row.rid, row.related, row.tier, row.reason) == (
        demo.PROFILE.name,
        RuleId.parse("DS-ERR-01"),
        Relation.REALISES,
        "[M!]",
        "",
    )


def test_a_decided_row_names_its_lint_and_no_rule(abstract: Abstract) -> None:
    (row,) = abstract.concepts[2][1].rows
    assert row.related is Relation.DECIDED
    assert row.rid is None
    assert row.lint == "division-by-zero"
    assert row.tier == ""


#: An empty realisation table, as an entry's body would hold it.
TABLE = f"| {' | '.join(HEADER)} |\n|---|---|---|---|---|\n"


@pytest.mark.parametrize(
    ("body", "shaped"),
    [
        (f"Said.\n\n{TABLE}", True),
        (TABLE, False),
        ("Said.\n", False),
        (f"Said.\n\n**Why:** w.\n\n{TABLE}", False),
        (f"Said.\n\n{TABLE}\n```text\nx\n```\n", False),
        (f"Said.\n\n{TABLE}\n{TABLE}", False),
    ],
)
def test_an_entry_is_a_statement_then_one_realisation_table(
    body: str,
    shaped: bool,  # noqa: FBT001 — a column of the table above
) -> None:
    text = f"# E\n\nScope: s.\n\n## S\n\n### AS-ERR-01 [M] Do it\n\n{body}"
    (rule,) = Chapter.read(Doc.parse(text)).rules
    assert Concept(rule).shaped is shaped


def test_the_questions_are_read_in_order(abstract: Abstract) -> None:
    (question,) = abstract.questions
    assert question.question == "What can be deleted?"
    assert question.sentence.startswith("Fewer parts")


@pytest.mark.parametrize("name", list(demo.ABSTRACT_FILES))
def test_print_after_parse_is_the_identity_on_the_demo_abstract_standard(
    abstract: Abstract, name: str
) -> None:
    assert abstract.root is not None
    text = (abstract.root / name).read_text()
    assert canonical(text) == text


def test_formatting_the_abstract_standard_is_idempotent(abstract: Abstract) -> None:
    assert abstract.root is not None
    before = {p: p.read_text() for p in abstract.markdown}
    assert format_abstract(Abstract(abstract.root)) == []
    assert format_abstract(Abstract(abstract.root)) == []
    assert {p: p.read_text() for p in abstract.markdown} == before


def test_formatting_prints_an_entry_canonically(abstract: Abstract) -> None:
    assert abstract.root is not None
    path = abstract.root / "errors.md"
    text = path.read_text()
    path.write_text(
        text.replace("so the unit that meets one", "so the unit\nthat meets one")
    )
    (note,) = format_abstract(Abstract(abstract.root))
    assert str(note.where) == f"./{ABSTRACT}/errors.md"
    assert path.read_text() == text


def test_the_shipped_abstract_standard_prints_as_it_is_read() -> None:
    shipped = Abstract(ROOT / ABSTRACT)
    for path in shipped.markdown:
        text = path.read_text()
        assert canonical(text) == text, path
    assert (ROOT / ABSTRACT / PRINCIPLES).exists() or shipped.principles is None
