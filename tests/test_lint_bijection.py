"""Every lint the configuration sets one by one has exactly one row.

normalize-the-standards, decision 8: the rows are how a reader learns
what the build forbids, so a configured lint with no row is a rule
nobody can read, and one with two is a concept with two homes. A row
for a lint the configuration does not set one by one says why it is
listed, and a rule whose Check is only a lint is that lint's row.
"""

import pytest

from agent_skill.checks.citations import _reasoned, configured, only_lint, owed
from agent_skill.doc import Doc
from agent_skill.doc.chapter import LintRow, Rule
from agent_skill.ids import RuleId, Tier
lazy from agent_skill.model import Skill


def by_name(skills: list[Skill], name: str) -> Skill:
    return next(s for s in skills if s.name == name)


def test_a_delta_owes_rows_only_where_it_departs(skills: list[Skill]) -> None:
    """bevy-style repeats rust-style's lint table but for two entries.

    What it sets as its anchor does is the anchor's to row, and the two
    entries it relaxes to `allow` forbid nothing, so it owes no row.
    """
    bevy, rust = by_name(skills, "bevy-style"), by_name(skills, "rust-style")
    due, anchors = owed(bevy)
    assert due == {}
    assert ("clippy", "unwrap_used") in anchors
    assert ("rustc", "elided_lifetimes_in_paths") not in configured(bevy)
    assert configured(rust)["rustc", "elided_lifetimes_in_paths"] == "warn"
    assert set(owed(rust)[0]) == set(configured(rust))


@pytest.mark.parametrize(
    ("forbids", "reasoned"),
    [
        ("a trailing `return` — listed because a rule became it", True),
        ("a trailing `return`; Listed because the review asks for it", True),
        ("a trailing `return`", False),
        ("a trailing `return` — listed because", False),
        ("listed because it is", False),
    ],
)
def test_a_row_says_why_it_is_listed_after_what_it_forbids(
    forbids: str,
    reasoned: bool,  # noqa: FBT001 — a parametrised expectation
) -> None:
    assert _reasoned(LintRow("clippy", "needless_return", "warn", forbids)) is reasoned


@pytest.mark.parametrize(
    ("check", "only"),
    [
        ("**Check:** ruff `UP040`.", True),
        ("**Check:** clippy `unwrap_used` and `expect_used`.", True),
        ("**Check:** ruff `UP040`, and read each alias it leaves.", False),
        ("**Check:** `rg -n 'TypeAlias' src/` — every hit is the finding.", False),
        ("**Check:** read each alias.", False),
    ],
)
def test_a_check_that_is_only_a_lint_is_that_lints_row(
    check: str,
    only: bool,  # noqa: FBT001 — a parametrised expectation
) -> None:
    body = Doc.parse(f"Says it.\n\n**Why:** w.\n\n{check}").blocks
    assert only_lint(Rule(RuleId("PS", "TYPE", 1), Tier.M, "Use it", body)) is only
