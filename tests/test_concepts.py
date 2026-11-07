"""The standards held to the abstract standard, and to one another.

The demo abstract standard holds every property, so `concepts` finds
nothing in it; each branch's control breaks one (`checks.controls`).
These hold what the controls do not: the detector's reach, and what an
entry takes out of it.
"""

lazy from pathlib import Path

from agent_skill.abstract import abstract_of
from agent_skill.checks.concepts import (
    LOOK_ALIKE,
    QUESTIONS,
    compared,
    concepts,
    look_alikes,
)
from agent_skill.layout import ABSTRACT, root_of
from agent_skill.model import Tree, discover
from structure_fixture import repository
lazy from agent_skill.model import Skill


def test_the_demo_and_its_abstract_standard_find_nothing(tmp_path: Path) -> None:
    found = [f for f in concepts(repository(tmp_path)) if f.branch != LOOK_ALIKE]
    assert [str(f) for f in found] == []


def test_every_pair_of_base_standards_is_compared_and_a_delta_with_its_anchor(
    skills: list[Skill],
) -> None:
    pairs = {(a.name, b.name) for a, b in compared(Tree.of(skills))}
    assert pairs == {
        ("python-style", "rust-style"),
        ("python-style", "zig-style"),
        ("rust-style", "zig-style"),
        ("bevy-style", "rust-style"),
    }


EMPTY = "# {0}\n\nScope: s.\n\n## Contents\n\n- **Concepts**\n\n---\n\n## Concepts\n"


def _unheld(scratch: Path, chapter: str) -> Tree:
    """The copy with `chapter` emptied, so its pairs are noted again."""
    root = root_of(scratch)
    (root / ABSTRACT / f"{chapter}.md").write_text(EMPTY.format(chapter.title()))
    return Tree.of(discover(scratch))


def _noted(tree: Tree) -> set[frozenset[str]]:
    return {
        frozenset((str(rule.id), str(other.id)))
        for _, rule, _, other in look_alikes(abstract_of(tree), tree)
    }


def test_two_standards_neither_of_which_is_rust_style_are_compared(
    scratch: Path,
) -> None:
    """An unheld pair with no Rust rule in it, read from the tree."""
    noted = _noted(_unheld(scratch, "modules"))
    assert any(not any(i.startswith("RS-") for i in pair) for pair in noted)


def test_an_entry_holding_two_rules_takes_their_pair_out_of_the_notes(
    scratch: Path,
) -> None:
    """The spec's pair: two rules one entry names are one concept."""
    held = next(
        c
        for _, c in abstract_of(Tree.of(discover(scratch))).concepts
        if c.title == "Name the two halves of a pair symmetrically"
    )
    rows = "".join(
        f"| {r.standard} | {r.rule} | realises | [M] | |\n" for r in held.rows
    )
    root = root_of(scratch)
    (root / ABSTRACT / "naming.md").write_text(
        "# Naming\n\nScope: s.\n\n## Contents\n\n- AS-NAME-01 [M] Pair names\n\n---\n\n"
        "## Pairs\n\n### AS-NAME-01 [M] Pair names\n\nSaid.\n\n"
        "| Standard | Rule | Relation | Tier | Reason |\n|---|---|---|---|---|\n" + rows
    )
    tree = _unheld(scratch, "modules")
    noted = _noted(tree)
    ours = [r.rule for r in held.rows]
    assert not any(frozenset((a, b)) in noted for a in ours for b in ours)
    assert any(not any(i.startswith("RS-") for i in pair) for pair in noted)


def test_no_delta_rule_restates_its_anchors_and_none_is_left_noted(
    skills: list[Skill],
) -> None:
    """A delta rule departs from its anchor's, and never restates it."""
    tree = Tree.of(skills)
    noted = {
        (str(rule.id), str(other.id))
        for a, rule, _, other in look_alikes(abstract_of(tree), tree)
        if a.profile.anchor
    }
    assert noted == set()


def test_a_question_the_abstract_standard_asks_otherwise_fails(scratch: Path) -> None:
    """The spec's scenario: zig's assertion question, third again."""
    md = scratch / "zig-style" / "SKILL.md"
    text = md.read_text()
    third = "3. **What can be made a value instead of an effect?**"
    assert third in text
    md.write_text(
        text.replace(third, "3. **What can be asserted instead of assumed?**")
    )
    found = [f for f in concepts(Tree.of(discover(scratch))) if f.branch == QUESTIONS]
    assert [(f.where.skill, f.where.file) for f in found] == [("zig-style", "SKILL.md")]


def test_a_delta_does_not_restate_the_questions(skills: list[Skill]) -> None:
    """Its section 3 is its departures table; its anchor asks them."""
    tree = Tree.of(skills)
    asked = [f.where.skill for f in concepts(tree) if f.branch == QUESTIONS]
    assert asked == []
    bevy = next(s for s in skills if s.profile.anchor)
    assert "**What can be deleted?**" not in bevy.text
