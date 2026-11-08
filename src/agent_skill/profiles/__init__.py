"""Per-skill knowledge, kept out of the skill directory.

The generic checks know what a skill *is*: a `SKILL.md` with
frontmatter, a `references/` of chapters, an `assets/`, and fenced
examples that carry a marker. Everything a check needs to know about
*this particular* standard — its rule prefix, its languages, the
exemptions its own rules state, the predicates that turn its `[M]` rules
into patterns — lives in a profile here.

A profile is a record: a frozen literal in its standard's module, with
no behaviour a check does not interpret. `PROFILES` names every one;
importing a profile's module registers nothing.

A skill with no profile still gets every generic check. It needs a
profile only to have its own rules applied to its own examples.

Profiles live in the package rather than beside a skill because a
skill's directory is what ships: it is copied with the plugin, linked
into `~/.claude/skills/` and packaged into its `.skill`, so tooling
configuration inside it would reach the reader.
"""

lazy from collections.abc import Mapping

from agent_skill.profiles import bevy_style, python_style, rust_style, zig_style
from agent_skill.profiles.record import (
    Delta,
    Evals,
    LineRule,
    Near,
    NotDecisive,
    Profile,
    Structural,
    Unless,
)

__all__ = [
    "PROFILES",
    "Delta",
    "Evals",
    "LineRule",
    "Near",
    "NotDecisive",
    "Profile",
    "Structural",
    "Unless",
    "profile_for",
]

#: Every profile this build knows, by its skill's name.
#:
#: A check that needs the roster asks for it rather than restating it:
#: the empty-corpus guard named two toolchains literally, so a third
#: that silently extracted nothing would have reported clean.
PROFILES: Mapping[str, Profile] = {
    p.name: p
    for p in (
        bevy_style.PROFILE,
        python_style.PROFILE,
        rust_style.PROFILE,
        zig_style.PROFILE,
    )
}


def profile_for(name: str) -> Profile:
    """`name`'s profile, or a bare one if it has none."""
    if name in PROFILES:
        return PROFILES[name]
    return Profile(name=name, prefix=_guess_prefix(name))


def _guess_prefix(name: str) -> str:
    """`rust-style` -> `RS`.

    Only used for a skill that ships no profile.
    """
    parts = [p for p in name.replace("_", "-").split("-") if p]
    return "".join(p[0] for p in parts[:2]).upper() or "XX"
