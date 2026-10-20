"""The shared templates render for every standard."""

import re

import pytest

from agent_skill import shared
lazy from agent_skill.model import Skill


@pytest.mark.parametrize("passage", shared.PASSAGES, ids=lambda p: p.template)
def test_every_template_fills_every_slot_for_every_standard(
    passage: shared.Passage, skills: list[Skill]
) -> None:
    for skill in skills:
        rendered = "\n\n".join(shared.render(passage, shared.slots(skill)))
        assert not re.search(r"\{[a-z_]+\}", rendered), (skill.name, passage.template)


def test_an_optional_list_item_leaves_no_gap(skills: list[Skill]) -> None:
    how_to = next(p for p in shared.PASSAGES if p.template == "how-to-use.md")
    for skill in skills:
        steps = shared.render(how_to, shared.slots(skill))[0]
        numbers = [int(n) for n in re.findall(r"^(\d+)\. ", steps, re.MULTILINE)]
        assert numbers == list(range(1, len(numbers) + 1)), skill.name
        assert len(numbers) == (5 if skill.profile.delta_step else 4), skill.name


def test_major_minor() -> None:
    assert shared.major_minor("1.99") == "1.99"
    assert shared.major_minor("3.15.0rc1") == "3.15"
    assert shared.major_minor("0.20.0") == "0.20"
    assert shared.major_minor(None) == ""
