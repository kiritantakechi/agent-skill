"""The counts `normalize-the-standards` moved, and what they read.

The baseline in its tasks is this table, printed by `agent-skill
measure`, and so is 7.2's after. A count a check of the normal form
decides is that check's, so a check and its count cannot disagree.
"""

lazy from pathlib import Path

import pytest

from agent_skill.checks import demo
from agent_skill.ids import Relation
from agent_skill.lang import toolchain_for
from agent_skill.measure import concepts_measured, entries, found, measured, table
from agent_skill.model import Skill
from structure_fixture import repository


def test_every_standard_is_measured_on_every_row(skills: list[Skill]) -> None:
    printed = table(skills).split("\n")
    head, rule, *rows = printed
    assert head == "| Measure | " + " | ".join(s.name for s in skills) + " |"
    assert rule.count("---") == len(skills) + 1
    assert rows
    for row in rows:
        cells = [c.strip() for c in row.strip("|").split("|")]
        assert len(cells) == len(skills) + 1, row
        assert all(cells), row


def test_a_standard_in_normal_form_measures_nothing_left_to_do(tmp_path: Path) -> None:
    """The demo holds the normal form, so each of its counts is zero."""
    demo.build(tmp_path)
    skill = Skill(tmp_path / demo.PROFILE.name, demo.PROFILE)
    assert sum(found(skill).values()) == 0
    counts = measured(skill)
    assert counts["restated titles"] == "0"
    assert counts["section 2 subsections, lines"].startswith("3, ")


@pytest.mark.parametrize(
    ("name", "lint", "group"),
    [
        ("rust-style", ("clippy", "unwrap_used"), ("clippy", "pedantic")),
        ("bevy-style", ("clippy", "unwrap_used"), ("clippy", "pedantic")),
        ("python-style", ("ty", "unsound-yield"), ("ruff", "ALL")),
    ],
)
def test_a_configuration_sets_lints_one_by_one_and_groups_not(
    skills: list[Skill], name: str, lint: tuple[str, str], group: tuple[str, str]
) -> None:
    skill = next(s for s in skills if s.name == name)
    toolchain = toolchain_for(skill.profile.toolchain)
    assert toolchain is not None
    configured = toolchain.configured(skill)
    assert lint in configured
    assert group not in configured


def test_a_compiler_ships_no_configuration(skills: list[Skill]) -> None:
    for skill in skills:
        toolchain = toolchain_for(skill.profile.toolchain)
        if toolchain is not None and toolchain.compilers >= set(toolchain.rows):
            assert not toolchain.configured(skill), skill.name


#: The rows the abstract standard adds, as `measure` labels them.
ABSTRACT_ROWS = (
    *(f"realisations `{r}`" for r in Relation),
    "look-alike pairs no entry holds",
    "domain chapters",
    "rules in abstract chapters realising nothing",
)


def test_the_abstract_rows_are_measured_for_every_standard(skills: list[Skill]) -> None:
    labels = [
        row.split(" | ")[0].removeprefix("| ") for row in table(skills).split("\n")
    ]
    assert set(ABSTRACT_ROWS) <= set(labels)
    counts = concepts_measured(skills)
    assert set(counts) == {s.name for s in skills}
    for skill in skills:
        assert counts[skill.name]["domain chapters"] == str(len(skill.profile.domain))


def test_a_delta_realises_through_its_anchor_and_departs_by_its_table(
    tmp_path: Path,
) -> None:
    """The demo realises its three entries; its delta tightens one."""
    skills = list(repository(tmp_path))
    counts = concepts_measured(skills)
    demo_counts, delta = counts[demo.PROFILE.name], counts[demo.DELTA.name]
    assert (
        demo_counts["realisations `realises`"],
        demo_counts["realisations `decided`"],
    ) == ("2", "1")
    assert delta["realisations `tightens`"] == "1"
    assert delta["realisations `realises`"] == "1"
    assert delta["realisations `decided`"] == "1"
    assert demo_counts["rules in abstract chapters realising nothing"] == "1"
    printed = entries(skills).split("\n")
    assert printed[2:] == ["| errors | 3 |", "| migration | 0 |", "| all | 3 |"]
