"""The anchor sweep: that it runs at all, and what it does with a search that could not answer.

Both cases here shipped. The sweep was unreachable — a `return` above it and the loop indented into
its branch — for as long as its negative control passed through a different branch of the same
check.
And the surviving call site read `find`'s `None` as an empty hit set, which is the failure the
`UNRUN` level exists to make impossible everywhere else.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from agent_skill.checks import crossref
from agent_skill.report import Level

SOURCE = Path(crossref.__file__)


@pytest.fixture
def bevy(skills):
    by_prefix = {s.prefix: s for s in skills}
    delta = by_prefix["BV"]
    return delta, by_prefix, list(crossref.OVERRIDE_ROW.finditer(delta.text))


def test_the_sweep_is_reachable():
    """Asserted on the syntax tree, because it reads correct at every other level.

    The loop is indented, spelled and typed exactly as it would be if it ran. Nothing short of
    asking where it sits relative to the `return` above it can tell the difference, which is why
    reading the function did not.
    """
    tree = ast.parse(SOURCE.read_text())
    fn = next(
        n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "_anchor_patterns"
    )
    assert isinstance(fn.body[-1], ast.For), (
        "the anchor loop is not the last statement of the function, which is what it looks like "
        "when an early return above it has swallowed it into a branch"
    )
    swallowed = [
        node
        for node in ast.walk(fn)
        if isinstance(node, ast.If)
        and any(isinstance(s, ast.Return) for s in node.body)
        and any(isinstance(s, (ast.For, ast.While)) for s in node.body)
    ]
    assert not swallowed, "a loop sits after a `return` in the same block, so it cannot execute"


def test_a_search_that_cannot_answer_is_not_an_accounted_for_delta(bevy, monkeypatch):
    """`None` and `[]` are both falsy; this caller used to collapse them."""
    delta, by_prefix, rows = bevy
    monkeypatch.setattr(
        "agent_skill.checks.search.find", lambda corpus, pattern: (None, pattern.mode)
    )

    findings = list(crossref._anchor_patterns(delta, by_prefix, rows))

    assert findings, "every pattern gave no answer and the sweep reported nothing"
    assert all(f.level is Level.FAIL for f in findings)
    assert all("gave no answer" in f.message for f in findings)


def test_a_search_that_answers_nothing_is_a_clean_result(bevy, monkeypatch):
    """The other half: an empty answer is an answer, and must stay silent."""
    delta, by_prefix, rows = bevy
    monkeypatch.setattr(
        "agent_skill.checks.search.find", lambda corpus, pattern: ([], pattern.mode)
    )

    assert list(crossref._anchor_patterns(delta, by_prefix, rows)) == []


def test_the_sweep_has_something_to_sweep(bevy):
    """A guard over an empty subject set passes for the wrong reason.

    The sweep only runs an anchor's patterns when the delta cites that anchor and the rule is not
    named in the delta's `SKILL.md`. If that population ever reached zero, every assertion above
    would still pass over nothing at all.
    """
    delta, by_prefix, rows = bevy
    from agent_skill.checks.patterns import patterns_of

    named = set(re.findall(r"\b[A-Z]{2}-[A-Z]+-\d+[a-z]?\b", delta.text))
    anchors = {p for p in by_prefix if p != delta.prefix and any(m.group(1)[:2] == p for m in rows)}
    assert anchors, "the delta cites no anchor, so the sweep has no standard to run"

    runnable = [
        rule.id
        for prefix in anchors
        for rule in by_prefix[prefix].rules
        if rule.check
        and rule.id not in named
        and any(p.kind == "command" for p in patterns_of(rule.check))
    ]
    assert runnable, "no anchor rule reaches the sweep — it would pass over an empty set"
