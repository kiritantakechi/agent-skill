"""Per-skill knowledge, kept out of the skill directory.

The generic checks know what a skill *is*: a `SKILL.md` with frontmatter, a
`references/` of chapters, an `assets/`, and fenced examples that carry a marker.
Everything a check needs to know about *this particular* standard — its rule
prefix, its languages, the exemptions its own rules state, the predicates that
turn its `[M]` rules into patterns — lives in a profile here.

A skill with no profile still gets every generic check. It needs a profile only
to have its own rules applied to its own examples.

Profiles live in the package rather than in `skills/<name>/` because that
directory is symlinked into `~/.claude/skills/` and packaged into the shipped
`.skill`: tooling configuration inside it would be shipped to the reader.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from ..lang.rust import Crate
from ..model import MARKERS
from ..report import Finding

if TYPE_CHECKING:
    from ..checks.search import Span


@dataclass(frozen=True, slots=True)
class NotDecisive:
    """A pattern whose hits are candidates rather than defects.

    `anchor` is a literal substring of that rule's own `**Check:**` — the words
    `reason` is drawn from — and is verified to still be there, so rewriting a
    rule cannot leave a stale entry quietly suppressing its pattern.
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
    #: the tools a `rejected` block may name as the one that rejects it
    tools: tuple[str, ...] = ()
    #: Why this standard does not yet follow `standard-structure`, or None when
    #: it does. A reason, not a flag: an exemption that says nothing about why
    #: it exists cannot be told apart from one whose reason has lapsed.
    exempt_from_structure: str | None = None
    #: The language in the H1 and the shared text: "Rust", "Python", "Bevy".
    language: str = ""
    #: What `verified` means here, finishing "the block …". `{pin}` is filled
    #: with `pin()` and `{rust}` with the verified crate's `rust-version`, so the
    #: sentence cannot name a version the harness does not verify against.
    verified_as: str = ""
    #: The code in which `[M!]` binds as `[M]`: "library and high-reliability".
    strict_scope: str = ""
    #: A delta standard's extra reading step, or "" for a standard that stands alone.
    delta_step: str = ""
    toolchain: str | None = None
    #: how this skill's rust blocks are compiled; required when `toolchain == "rust"`,
    #: because the dependency line and the lint table differ per skill
    crate: Crate | None = None
    #: above this many hits a pattern enumerates rather than accuses
    judgement: int = 15
    #: rule id -> (corpus lines, the hit's span, in_test) -> "is this hit the case
    #: the rule permits?"
    #:
    #: A `Span`, not an index. It became one when a hit stopped being a line, and
    #: this said `int` for as long afterwards as nobody wrote a new exemption —
    #: the lambdas are untyped, so `ty` could not see the disagreement, and the
    #: next one written against the documented signature would have indexed
    #: `lines[at]` with a dataclass. That raises only when a rule actually fires.
    exempt: dict[str, Callable[[list[str], Span, set[int]], bool]] = field(default_factory=dict)
    not_decisive: dict[str, NotDecisive] = field(default_factory=dict)
    #: Rule id -> snippets containing the defects that rule exists to catch.
    #:
    #: `selfapply` proves a pattern does not fire on compliant code. Nothing
    #: proved it fires on anything at all, and a pattern that cannot match looks
    #: exactly like a pattern that correctly found nothing. An entry here is the
    #: other half: the pattern must hit this.
    #:
    #: Several snippets, not one, because a rule's Check may ship several
    #: patterns and one snippet cannot exhibit them all — `ZS-MIG-13` covers four
    #: disjoint families of dead API. While this was one snippet the assertion
    #: could only be `any`, so three of that rule's four patterns were counted as
    #: proven by a fixture none of them matched.
    #:
    #: Matched as a cover in both directions: every command pattern hits some
    #: snippet, and every snippet is hit by some pattern. The second direction is
    #: what keeps the first honest — without it, a pattern narrowed until it
    #: stops matching can be "fixed" by adding a snippet nothing relates to the
    #: rule.
    fires: dict[str, tuple[str, ...]] = field(default_factory=dict)

    @property
    def all_marked(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(self.languages + self.marked_languages))

    def pin(self) -> str | None:
        """The exact version this standard is verified against.

        The language toolchain for a language standard, the engine for a delta
        standard. The H1 names its major.minor, so the title and the harness
        cannot disagree about what the standard is for.
        """
        return None

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


def exemption_problem(profile: Profile) -> str | None:
    """What is wrong with a profile's structure exemption, if anything."""
    reason = profile.exempt_from_structure
    if reason is not None and not reason.strip():
        return f"{profile.name} is exempt from standard-structure and gives no reason"
    return None


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
