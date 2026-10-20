"""The standard's own rules, applied to its own examples.

Review rounds each found an example edited to satisfy one rule while
breaking a rule in another chapter. Nothing checked across chapters, so
nothing objected.

Tier governs adoption by a reader, not the library's own evidence, so an
`[S]` rule the library declines to follow in its own examples fails here
too.
"""

from agent_skill.checks import check


@check("conventions", "the standard's own rules over its own examples")
def conventions(skill):
    yield from skill.profile.conventions(skill)
