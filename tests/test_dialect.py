"""Whether a `\\|` is an operator or a literal.

`outside_brackets` decides whether the `dialect` check reports a pattern. Wrong
in the permissive direction, the check stops reporting the defect it exists for
— and a `\\|` left in an `rg` pattern matches a literal pipe, finds nothing, and
reads as clean.

Written from scratch in `migrate-checks-to-ripgrep` and touched by exactly one
negative control until now.
"""

from __future__ import annotations

import pytest

from agent_skill.checks.dialect import outside_brackets


@pytest.mark.parametrize(
    ("pattern", "found"),
    [
        (r"Io.Threaded\|Io.Uring", True),  # the defect: BRE alternation left in place
        (r"a\|b\|c", True),
        (r"alpha|beta", False),  # already ERE, nothing to report
        (r"[a\|b]", False),  # inside a bracket expression nothing is an operator
        (r"[^\|]", False),
        (r"x[\|]y", False),
        (r"[[:space:]]*\|", True),  # a POSIX class closes on its outer `]`
        (r"_(max|min)[[:space:]]*(:[^=]*)?=[^=]", False),
        (r"[]]\|", True),  # a `]` in first position is literal, so the class ends later
        (r"[^]]\|", True),
        (r"[]|]", False),  # …and the `|` inside that class is still a literal
    ],
)
def test_an_operator_is_told_from_a_literal(pattern, found):
    assert outside_brackets(pattern, "\\|") is found


def test_a_posix_class_does_not_swallow_the_rest_of_the_pattern():
    """Stopping at the first `]` reads `]*\\|` as pattern text and accuses it."""
    assert outside_brackets(r"[[:alpha:]]x", "\\|") is False
    assert outside_brackets(r"[[:alpha:]]\|x", "\\|") is True


def test_an_unterminated_bracket_does_not_run_off_the_end():
    assert outside_brackets(r"[abc", "\\|") is False
    assert outside_brackets(r"[[:space:", "\\|") is False


def test_an_escaped_backslash_is_not_an_escape_of_what_follows():
    r"""`\\` is a literal backslash, so the `|` after it is bare, not escaped."""
    assert outside_brackets(r"a\\|b", "\\|") is False
