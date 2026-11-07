"""The anchor sweep: that it runs, and what it does with no answer.

Both cases here shipped. The sweep was unreachable — a `return` above it
and the loop indented into its branch — for as long as its negative
control passed through a different branch of the same check. And the
surviving call site read `find`'s `None` as an empty hit set, which is
the failure the `UNRUN` level exists to make impossible everywhere else.
"""

import ast
from pathlib import Path

import pytest

from agent_skill.checks import crossref
from agent_skill.checks.patterns import patterns_of
from agent_skill.doc import Table, text_of, walk
from agent_skill.doc.chapter import departures, departures_header
from agent_skill.report import Level
lazy from agent_skill.model import Skill

SOURCE = Path(crossref.__file__)

#: The bevy delta, and every skill by name.
type Bevy = tuple[Skill, dict[str, Skill]]


@pytest.fixture
def bevy(skills: list[Skill]) -> Bevy:
    """`bevy-style`, and every skill by name."""
    by_name = {s.name: s for s in skills}
    return by_name["bevy-style"], by_name


def test_the_sweep_is_reachable() -> None:
    """Asserted on the syntax tree; it reads correct everywhere else.

    The loop is indented, spelled and typed exactly as it would be if it
    ran. Nothing short of asking where it sits relative to the `return`
    above it can tell the difference, which is why reading the function
    did not.
    """
    tree = ast.parse(SOURCE.read_text())
    fn = next(
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.FunctionDef) and n.name == "_anchor_patterns"
    )
    assert isinstance(fn.body[-1], ast.For), (
        "the anchor loop is not the last statement of the function, "
        "which is what it looks like when an early return above it "
        "has swallowed it into a branch"
    )
    swallowed = [
        node
        for node in ast.walk(fn)
        if isinstance(node, ast.If)
        and any(isinstance(s, ast.Return) for s in node.body)
        and any(isinstance(s, (ast.For, ast.While)) for s in node.body)
    ]
    assert not swallowed, (
        "a loop sits after a `return` in the same block, so it cannot execute"
    )


def test_a_search_that_cannot_answer_is_not_an_accounted_for_delta(
    bevy: Bevy, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`None` and `[]` are both falsy; this caller collapsed the two."""
    delta, by_name = bevy
    monkeypatch.setattr(crossref, "find", lambda _corpus, pattern: (None, pattern.mode))

    findings = list(crossref._anchor_patterns(delta, by_name))

    assert findings, "every pattern gave no answer and the sweep reported nothing"
    assert all(f.level is Level.FAIL for f in findings)
    assert all("gave no answer" in f.message for f in findings)


def test_a_search_that_answers_nothing_is_a_clean_result(
    bevy: Bevy, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The other half: an empty answer is an answer and stays silent."""
    delta, by_name = bevy
    monkeypatch.setattr(crossref, "find", lambda _corpus, pattern: ([], pattern.mode))

    assert list(crossref._anchor_patterns(delta, by_name)) == []


def test_the_sweep_has_something_to_sweep(bevy: Bevy) -> None:
    """A guard over an empty subject set passes for the wrong reason.

    The sweep only runs the anchor's patterns for a rule the delta's
    `SKILL.md` does not name. If that population ever reached zero,
    every assertion above would still pass over nothing at all.
    """
    delta, by_name = bevy

    named = set(crossref._named(delta.doc))
    anchor = by_name.get(delta.profile.anchor)
    assert anchor is not None, "the delta declares no anchor the tree holds"

    runnable = [
        rule.id
        for rule in anchor.chapter_rules
        if rule.check
        and rule.id not in named
        and any(p.kind == "command" for p in patterns_of(text_of(rule.check)))
    ]
    assert runnable, (
        "no anchor rule reaches the sweep — it would pass over an empty set"
    )


def test_the_shipped_delta_states_its_table(bevy: Bevy) -> None:
    """Normalised, it states its departures as one typed table."""
    delta, by_name = bevy
    anchor = delta.profile.anchor
    header = departures_header(anchor, delta.name)
    rows = [
        row
        for block in walk(delta.doc.blocks)
        if isinstance(block, Table) and block.header == header
        for row in departures(block)
    ]
    assert rows, "bevy-style has no departure row to read"
    assert list(crossref._departures(delta, by_name[anchor])) == []


def test_an_anchor_missing_from_the_tree_is_unrun(bevy: Bevy) -> None:
    """A sweep that could not look is not one that found nothing."""
    delta, by_name = bevy
    alone = {delta.name: delta}
    assert by_name[delta.profile.anchor] is not None
    found = list(crossref._anchor_patterns(delta, alone))
    assert [f.level for f in found] == [Level.UNRUN]
