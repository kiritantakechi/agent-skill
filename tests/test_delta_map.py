"""A delta's departures from its anchor are one typed map.

normalize-the-standards, decision 10: bevy-style related to rust-style
in five forms, and only its override table was structured. A normalised
delta states each departure as a row — anchor rule, relation, delta
rule, tier before and after, reason — and each departing rule says what
it departs from, so the table and the rules can be held to each other.
The demo's delta (`checks.demo.DELTA`) holds every property; the
controls break it one property at a time.
"""

lazy from pathlib import Path

import pytest

from agent_skill.checks import by_name, demo
from agent_skill.checks.crossref import departs_from
from agent_skill.doc import Doc
from agent_skill.doc.chapter import Departure, Rule, SkillMd
from agent_skill.ids import RuleId, Tier
from agent_skill.model import Skill, Tree

#: The checks a delta is read by, beside the ones the demo is held to.
HELD = (
    "anatomy",
    "skeleton",
    "layout",
    "shared-text",
    "citations",
    "crossref",
    "mirror",
)


@pytest.fixture
def tree(tmp_path: Path) -> Tree:
    """The demo and its delta, each read with its own profile."""
    demo.build(tmp_path)
    demo.build_delta(tmp_path)
    return Tree.of(Skill(tmp_path / name, p) for name, p in demo.PROFILES.items())


@pytest.mark.parametrize("name", HELD)
def test_the_delta_holds_every_property(tree: Tree, name: str) -> None:
    check = by_name(name)
    assert check is not None
    result = check.run(tree)
    assert [str(f) for f in (*result.fails, *result.unrun)] == []


@pytest.mark.parametrize(
    ("statement", "departs"),
    [
        ("Departs from DS-ERR-01. A caller decides.", RuleId("DS", "ERR", 1)),
        ("Departs from DS-ERR-01, and more.", None),
        ("A caller decides; it departs from DS-ERR-01.", None),
        ("Departs from nothing.", None),
    ],
)
def test_a_departing_rule_opens_by_naming_what_it_departs_from(
    statement: str, departs: RuleId | None
) -> None:
    body = Doc.parse(f"{statement}\n\n**Why:** w.\n\n**Check:** c.").blocks
    assert departs_from(Rule(RuleId("DL", "ERR", 1), Tier.M, "Do it", body)) == departs


@pytest.mark.parametrize(
    ("cell", "tiers"),
    [
        ("[M!] → [M]", (Tier.M_BANG, Tier.M)),
        ("[S] → [S]", (Tier.S, Tier.S)),
        ("[M] -> [S]", None),
        ("[M]", None),
        ("[X] → [M]", None),
    ],
)
def test_a_departure_states_the_tier_before_and_after(
    cell: str, tiers: tuple[Tier, Tier] | None
) -> None:
    assert Departure("DS-ERR-01", "tightens", "DL-ERR-01", cell, "why").tiers == tiers


def test_an_override_row_reads_its_ids_bare_or_quoted() -> None:
    """`fmt` sets a citation bare, in a cell too, and the row stays."""
    quoted = "| `RS-API-15` Keep fields private | `BV-ECS-01` — public | why |"
    bare = "| RS-API-15 Keep fields private | BV-ECS-01 — public | why |"
    head = "| rust-style rule | Instead | Why |\n|---|---|---|\n"

    def rows(row: str) -> tuple[tuple[RuleId, str, RuleId], ...]:
        md = SkillMd.read(Doc.parse(f"# T\n\n## 3. Design\n\n{head}{row}\n"))
        return tuple((o.theirs, o.quoted, o.ours) for o in md.overrides)

    assert (
        rows(bare)
        == rows(quoted)
        == ((RuleId("RS", "API", 15), "Keep fields private", RuleId("BV", "ECS", 1)),)
    )
