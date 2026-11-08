"""The shared templates render for every standard."""

import re

import pytest

from agent_skill import shared
from agent_skill.doc import Doc, ListBlock
from agent_skill.ids import cited
lazy from agent_skill.model import Skill


@pytest.mark.parametrize("passage", shared.PASSAGES, ids=lambda p: p.template)
def test_every_template_fills_every_slot_for_every_standard(
    passage: shared.Passage, skills: list[Skill]
) -> None:
    for skill in skills:
        rendered = str(Doc(None, shared.render(passage, shared.slots(skill))))
        assert not re.search(r"\{[a-z_]+\}", rendered), (skill.name, passage.template)


def test_an_optional_list_item_leaves_no_gap(skills: list[Skill]) -> None:
    how_to = next(p for p in shared.PASSAGES if p.template == "how-to-use.md")
    for skill in skills:
        steps = shared.render(how_to, shared.slots(skill))[0]
        assert isinstance(steps, ListBlock), skill.name
        printed = str(Doc(None, (steps,)))
        numbers = [int(n) for n in re.findall(r"^(\d+)\. ", printed, re.MULTILINE)]
        assert numbers == list(range(1, len(numbers) + 1)), skill.name
        assert len(numbers) == (5 if skill.profile.delta_step else 4), skill.name


def test_the_title_rendered_is_the_one_each_standard_ships(
    skills: list[Skill],
) -> None:
    """Named by its pin's series: a patch release moves the pin only."""
    for skill in skills:
        assert shared.title(skill).text == skill.typed.title, skill.name


def test_no_template_cites_a_rule() -> None:
    """A rule a shared passage cites is cited in every standard.

    `revise` refuses to remove or demote a cited rule, and `fmt` puts
    the passage back, so the citation could never be resolved; and a
    renaming of the chapter it names left it citing no rule. The
    templates said `-ERR-03` and `-TEST-05` until a renaming of
    `errors` failed `revise`'s inverse law on them.
    """
    for passage in shared.PASSAGES:
        rendered = passage.text().replace("{prefix}", "XS")
        assert list(cited(rendered)) == [], passage.template
