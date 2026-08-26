"""Per-skill knowledge, kept out of the skill directory.

The generic checks know what a skill *is*: a `SKILL.md` with frontmatter, a
`references/` of chapters, an `assets/`, and fenced examples that carry a marker.
Everything a check needs to know about *this particular* standard — its rule
prefix, its languages, the exemptions its own rules state, the predicates that
turn its `[M]` rules into greps — lives in a profile here.

A skill with no profile still gets every generic check. It needs a profile only
to have its own rules applied to its own examples.

Profiles live in the package rather than in `skills/<name>/` because that
directory is symlinked into `~/.claude/skills/` and packaged into the shipped
`.skill`: tooling configuration inside it would be shipped to the reader.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field

from ..lang.rust import Crate
from ..model import MARKERS
from ..report import Finding


@dataclass(frozen=True, slots=True)
class NotDecisive:
    """A grep whose hits are candidates rather than defects.

    `anchor` is a literal substring of that rule's own `**Check:**` — the words
    `reason` is drawn from — and is verified to still be there, so rewriting a
    rule cannot leave a stale entry quietly suppressing its grep.
    """

    anchor: str
    reason: str


@dataclass
class Profile:
    """What one skill's checks need to know about it."""

    name: str
    prefix: str
    languages: tuple[str, ...] = ()
    #: fence tags that carry markers but are not compiled
    marked_languages: tuple[str, ...] = ()
    #: the marker words this skill's blocks may use, in its own comment syntax
    markers: tuple[str, ...] = MARKERS
    toolchain: str | None = None
    #: how this skill's rust blocks are compiled; required when `toolchain == "rust"`,
    #: because the dependency line and the lint table differ per skill
    crate: Crate | None = None
    #: above this many hits a grep enumerates rather than accuses
    judgement: int = 15
    #: rule id -> (corpus lines, index, in_test) -> "is this hit the case the rule permits?"
    exempt: dict[str, Callable[[list[str], int, set[int]], bool]] = field(default_factory=dict)
    not_decisive: dict[str, NotDecisive] = field(default_factory=dict)

    @property
    def all_marked(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(self.languages + self.marked_languages))

    def conventions(self, skill) -> Iterable[Finding]:
        """This standard's own rules, applied to its own examples."""
        return ()

    def prose(self, skill) -> Iterable[Finding]:
        """This standard's own rules, applied to the text around its examples."""
        return ()

    def inside_tests(self, body: str) -> set[int]:
        """Body-line indices a rule scoped to test code should look at.

        Which lines those are is a fact about the language, so the generic
        corpus builder asks rather than assumes.
        """
        return set()


_REGISTRY: dict[str, Profile] = {}


def register(profile: Profile) -> Profile:
    _REGISTRY[profile.name] = profile
    return profile


def _load() -> dict[str, Profile]:
    if not _REGISTRY:
        from . import bevy_style, python_style, rust_style, zig_style  # noqa: F401
    return _REGISTRY


def registered() -> tuple[Profile, ...]:
    """Every profile this build knows about.

    A check that needs the roster asks for it rather than restating it: the
    empty-corpus guard named rust and zig literally, so a third toolchain that
    silently extracted nothing would have reported clean.
    """
    return tuple(_load().values())


def profile_for(name: str) -> Profile:
    registry = _load()
    if name in registry:
        return registry[name]
    return Profile(name=name, prefix=_guess_prefix(name))


def _guess_prefix(name: str) -> str:
    """`rust-style` -> `RS`. Only used for a skill that ships no profile."""
    parts = [p for p in name.replace("_", "-").split("-") if p]
    return "".join(p[0] for p in parts[:2]).upper() or "XX"
