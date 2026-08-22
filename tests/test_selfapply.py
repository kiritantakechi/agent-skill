"""The grep engine.

Every case here is a defect that shipped: a pattern that could not fire, a
pattern that was dropped, and a pattern read in the wrong dialect.
"""

from __future__ import annotations

import pytest

from agent_skill.checks.selfapply import grep_mode, patterns_of


@pytest.mark.parametrize(
    ("command", "mode"),
    [
        ("grep -rn 'pub fn main()' src/", "-G"),  # BRE: `(` and `)` are literal
        ("grep -rEn '_(max|min)' src/", "-E"),
        ("grep -rnF 'assert(' src/", "-F"),
        ("rg -n 'std\\.io'", "-E"),
    ],
)
def test_dialect_comes_from_the_command(command, mode):
    assert grep_mode(command) == mode


def test_a_shipped_grep_is_taken_as_written():
    [p] = patterns_of("**Check:** `grep -rEn '_(max|min)[[:space:]]*=' src/`")
    assert p.text == "_(max|min)[[:space:]]*="
    assert p.mode == "-E"
    assert p.kind == "command"


def test_a_filename_argument_is_not_a_pattern():
    patterns = patterns_of("`grep -rEn 'pub fn' src/ --include='*.zig'`")
    assert [p.text for p in patterns] == ["pub fn"]


def test_a_prose_span_is_a_fixed_string():
    """Compiling `|x| f(x)` as a regex turned it into an alternation matching
    every line, which is how the first version produced five thousand hits."""
    patterns = patterns_of("**Check:** grep for `|x| f(x)` at every call site.")
    assert [(p.text, p.mode, p.kind) for p in patterns] == [("|x| f(x)", "-F", "prose")]


def test_a_check_that_names_no_pattern_yields_none():
    assert patterns_of("**Check:** read the function and judge it.") == []
