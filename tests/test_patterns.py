"""The pattern engine.

Every case here is a defect that shipped: a pattern that could not fire,
a pattern that was dropped, and a pattern read in the wrong dialect.
"""

import re

import pytest

from agent_skill.checks.patterns import (
    check_text,
    dialect_of,
    filtered_of,
    patterns_of,
)
from agent_skill.checks.selfapply import own_patterns
lazy from agent_skill.model import Skill


@pytest.mark.parametrize(
    ("command", "mode"),
    [
        ("rg -n 'std\\.io'", "-E"),
        ("rg -n 'pub fn main\\(\\)' src/", "-E"),
        ("rg -nF 'assert('", "-F"),
        ("rg --fixed-strings 'a|b'", "-F"),
    ],
)
def test_a_command_is_a_regex_unless_it_says_fixed(command: str, mode: str) -> None:
    """Two values, not three.

    The library used to hold basic and extended expressions at once,
    chosen by whether a command happened to carry `-E`, and a pattern
    read in the wrong one matches nothing while reporting clean. What is
    left is a real distinction: a regex, or literal text.
    """
    assert dialect_of(command) == mode


def test_a_shipped_command_is_taken_as_written() -> None:
    [p] = patterns_of("**Check:** `rg -n '_(max|min)[[:space:]]*=' src/`")
    assert p.text == "_(max|min)[[:space:]]*="
    assert p.mode == "-E"
    assert p.kind == "command"


def test_a_filename_argument_is_not_a_pattern() -> None:
    """A filename read as a pattern is a build break, not a missed hit.

    A command-kind hit is tier 1, so every example naming the file would
    fail the standard. `*.c` and `*.h` were missing from the list and
    did exactly that once the dialect stopped tolerating a leading `*`.
    """
    assert [p.text for p in patterns_of("`rg -n 'pub fn' src/ -g '*.zig'`")] == [
        "pub fn"
    ]
    assert [p.text for p in patterns_of("`rg -n 'PyUnicode' -g '*.c' -g '*.h'`")] == [
        "PyUnicode"
    ]


def test_a_prose_span_is_a_fixed_string() -> None:
    """Compiling `|x| f(x)` as a regex made it match every line.

    It became an alternation, which is how the first version produced
    five thousand hits.
    """
    patterns = patterns_of("**Check:** search for `|x| f(x)` at every call site.")
    assert [(p.text, p.mode, p.kind) for p in patterns] == [("|x| f(x)", "-F", "prose")]


def test_a_prose_check_still_phrased_as_grep_is_read() -> None:
    """Most Checks that name a search say it in prose, with no command.

    Rewriting those is not part of the migration to `rg`, so the trigger
    still recognises the word — a verb in prose is not a tool
    invocation.
    """
    [p] = patterns_of("**Check:** grep for `weak_handle!` in every plugin.")
    assert (p.text, p.kind) == ("weak_handle!", "prose")


def test_a_check_that_names_no_pattern_yields_none() -> None:
    assert patterns_of("**Check:** read the function and judge it.") == []


def test_the_prose_fallback_has_something_to_fall_back_on(
    skills: list[Skill],
) -> None:
    """The branch for a prose Check is dead code if nothing reaches it.

    `patterns_of` only looks for a backticked span when the Check names
    a search without shipping a command. That population shrinks every
    time a Check is promoted, and the day it reaches zero the branch
    stops being exercised while every test still passes. Asserted rather
    than counted in a comment: a number in a comment is a claim nothing
    checks, which is what put `247` there and left it there after the
    real figure was measured at 280.
    """
    trigger = re.compile(
        r"\bgrep\b|\brg\b|\bscan\b|\bsearch for\b|\blook for\b", re.IGNORECASE
    )
    reaching = [
        r.id
        for s in skills
        for r in s.chapter_rules
        if (check := " ".join(check_text(r).split()))
        and not re.search(r"`rg\s", check)
        and trigger.search(check)
    ]
    assert reaching, "no Check reaches the prose fallback — the branch is now dead code"


def test_a_filter_is_not_a_pattern_to_find() -> None:
    """`| rg -v` drops hits; read whole, it was one more to find."""
    found, filters = filtered_of(
        r"**Check:** `rg -n 'pub use' -g '*.rs' src/ | rg -v '^src/lib\.rs'`."
    )
    assert [p.text for p in found] == ["pub use"]
    assert [p.text for p in filters] == [r"^src/lib\.rs"]


def test_a_filtered_check_is_run_and_said(skills: list[Skill]) -> None:
    """RS-API-04 was skipped whole, with no finding of any kind."""
    rust = next(s for s in skills if s.name == "rust-style")
    said = [
        f.message for f in own_patterns.each(rust) if f.message.startswith("RS-API-04")
    ]
    assert said, "the only filtered Check in the standards is silent again"
    assert "/pub use/" in said[0]
