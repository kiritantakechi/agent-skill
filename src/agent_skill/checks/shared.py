"""Every passage the standards share is the template, filled in.

The passages were copied from one `SKILL.md` to the next and then edited in
place, so they agreed only nearly, and nothing noticed. The template is kept once
in the package (`agent_skill/shared/`); each skill carries the filled-in copy,
because a skill is installed alone and must read without its siblings.
`agent-skill fmt` rewrites a drifted copy.
"""

from __future__ import annotations

from .. import shared
from ..report import fail
from . import check


@check("shared-text", "every shared passage is the template, filled in")
def shared_text(skill):
    if skill.profile.exempt_from_structure is not None:
        return
    for message, where in shared.compare(skill):
        yield fail(f"{message} — `agent-skill fmt` rewrites it", where)
