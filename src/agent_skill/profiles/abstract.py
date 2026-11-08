"""The abstract standard's record: what a check reads about it.

It is a profile in shape, so the readers that take one read the
abstract standard as they read a standard: its prefix is the one every
entry's ID carries, and no skill may cite. It ships nothing, so it has
no toolchain, no languages and no `SKILL.md` to hold a frontmatter.
"""

from agent_skill.profiles.record import Profile

PROFILE = Profile(name="abstract", prefix="AS", language="Abstract")
