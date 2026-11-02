"""Every passage the standards share is the template, filled in.

The passages were copied from one `SKILL.md` to the next and then edited
in place, so they agreed only nearly, and nothing noticed. The template
is kept once in the package (`agent_skill/shared/`); each skill carries
the filled-in copy, because a skill is installed alone and must read
without its siblings. `agent-skill fmt` rewrites a drifted copy.
"""

lazy from collections.abc import Iterator

from agent_skill import shared
from agent_skill.checks import check, per_skill
lazy from agent_skill.model import Skill
lazy from agent_skill.report import Finding


@check("shared-text", "every shared passage is the template, filled in")
@per_skill
def shared_text(skill: Skill) -> Iterator[Finding]:
    """Every shared passage that is not its template, filled in."""
    yield from shared.compare(skill)
