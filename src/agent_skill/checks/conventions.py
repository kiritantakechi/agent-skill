"""The standard's own rules, applied to its own examples.

Review rounds each found an example edited to satisfy one rule while
breaking a rule in another chapter. Nothing checked across chapters, so
nothing objected.

Tier governs adoption by a reader, not the library's own evidence, so an
`[S]` rule the library declines to follow in its own examples fails here
too.
"""

lazy from collections.abc import Iterator

from agent_skill.checks import check, per_skill
lazy from agent_skill.model import Skill
lazy from agent_skill.report import Finding


@check("conventions", "the standard's own rules over its own examples")
@per_skill
def conventions(skill: Skill) -> Iterator[Finding]:
    """The profile's own rules, applied to the skill's own examples.

    Each profile declares the branches its rules fire through.
    """
    if (rules := skill.profile.conventions) is not None:
        yield from rules(skill)
