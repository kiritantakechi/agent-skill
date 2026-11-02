"""Per-skill knowledge, kept out of the skill directory.

The generic checks know what a skill *is*: a `SKILL.md` with
frontmatter, a `references/` of chapters, an `assets/`, and fenced
examples that carry a marker. Everything a check needs to know about
*this particular* standard — its rule prefix, its languages, the
exemptions its own rules state, the predicates that turn its `[M]` rules
into patterns — lives in a profile here.

A skill with no profile still gets every generic check. It needs a
profile only to have its own rules applied to its own examples.

Profiles live in the package rather than beside a skill because a
skill's directory is what ships: it is copied with the plugin, linked
into `~/.claude/skills/` and packaged into its `.skill`, so tooling
configuration inside it would reach the reader.
"""

import importlib
from dataclasses import dataclass, field
lazy from collections.abc import Callable, Iterable

lazy from agent_skill.checks.search import Span
lazy from agent_skill.lang.rust import Crate
lazy from agent_skill.model import Skill
lazy from agent_skill.report import Finding

#: Whether a hit is the case its rule permits, given the corpus lines,
#: the hit's span, and the lines that sit inside tests.
type Exemption = Callable[[list[str], Span, set[int]], bool]


@dataclass(frozen=True, slots=True)
class NotDecisive:
    """A pattern whose hits are candidates rather than defects.

    `anchor` is a literal substring of that rule's own `**Check:**` —
    the words `reason` is drawn from — and is verified to still be
    there, so rewriting a rule cannot leave a stale entry quietly
    suppressing its pattern.
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
    #: the tools a `rejected` block may name as the one that rejects it
    tools: tuple[str, ...] = ()
    #: The language in the H1 and the shared text: "Rust", "Python",
    #: "Bevy".
    language: str = ""
    #: What `verified` means here, finishing "the block …". `{pin}` is
    #: filled with `pin()` and `{rust}` with the verified crate's
    #: `rust-version`, so the sentence cannot name a version the harness
    #: does not verify against.
    verified_as: str = ""
    #: The code in which `[M!]` binds as `[M]`: "library and
    #: high-reliability".
    strict_scope: str = ""
    #: A delta standard's extra reading step, or "" for a standard that
    #: stands alone.
    delta_step: str = ""
    #: The standard a delta is a delta on, by name; "" for one that
    #: stands alone, and required exactly when `delta_step` is set.
    #:
    #: Declared rather than read from the override table, because the
    #: table is what `crossref` checks: deriving the anchor from its
    #: rows meant deleting the table deleted the anchor, which turned
    #: off the sweep of the anchor's patterns and left a note.
    anchor: str = ""
    #: Why `pin()` follows this machine's toolchain rather than
    #: upstream's newest release, or None when it follows upstream. Such
    #: a pin is compared with the running version only, and the
    #: toolchain moving past it is the cue to bump.
    follows_local: str | None = None
    #: The crates.io crate `pin()` names, for a standard whose subject
    #: is a library rather than a toolchain; "" for a language standard.
    library: str = ""
    #: The toolchain that runs this skill's examples, or "" for none.
    toolchain: str = ""
    #: how this skill's rust blocks are compiled; required when
    #: `toolchain == "rust"`, because the dependency line and the lint
    #: table differ per skill
    crate: Crate | None = None
    #: above this many hits a pattern enumerates rather than accuses
    judgement: int = 15
    #: rule id -> (corpus lines, the hit's span, in_test) -> "is this
    #: hit the case the rule permits?"
    #:
    #: A `Span`, not an index. It became one when a hit stopped being a
    #: line, and this said `int` for as long afterwards as nobody wrote
    #: a new exemption — the lambdas are untyped, so `ty` could not see
    #: the disagreement, and the next one written against the documented
    #: signature would have indexed `lines[at]` with a dataclass. That
    #: raises only when a rule actually fires.
    exempt: dict[str, Exemption] = field(default_factory=dict)
    not_decisive: dict[str, NotDecisive] = field(default_factory=dict)
    #: Rule id -> snippets containing the defects that rule exists to
    #: catch.
    #:
    #: `selfapply` proves a pattern does not fire on compliant code.
    #: Nothing proved it fires on anything at all, and a pattern that
    #: cannot match looks exactly like a pattern that correctly found
    #: nothing. An entry here is the other half: the pattern must hit
    #: this.
    #:
    #: Several snippets, not one, because a rule's Check may ship
    #: several patterns and one snippet cannot exhibit them all —
    #: `ZS-MIG-12` covers four disjoint families of dead API. While this
    #: was one snippet the assertion could only be `any`, so three of
    #: that rule's four patterns were counted as proven by a fixture
    #: none of them matched.
    #:
    #: Matched as a cover in both directions: every command pattern hits
    #: some snippet, and every snippet is hit by some pattern. The
    #: second direction is what keeps the first honest — without it, a
    #: pattern narrowed until it stops matching can be "fixed" by adding
    #: a snippet nothing relates to the rule.
    fires: dict[str, tuple[str, ...]] = field(default_factory=dict)
    #: A compiler row's phrase -> the smallest source the compiler
    #: rejects with it. A compiler has no lint table to compare a row
    #: against, so each row is proved by a probe, and each probe needs
    #: its row: a probe nothing cites would prove an error the standard
    #: never mentions.
    probes: dict[str, str] = field(default_factory=dict)

    @property
    def all_marked(self) -> tuple[str, ...]:
        """Every fence tag that carries a marker, without repeats."""
        return tuple(dict.fromkeys(self.languages + self.marked_languages))

    def pin(self) -> str:
        """The exact version this standard is verified against.

        The language toolchain for a language standard, the engine for a
        delta standard. The H1 names its major.minor, so the title and
        the harness cannot disagree about what the standard is for. ""
        when there is none.
        """
        return ""

    def running_version(self) -> str:
        """The version of `pin()`'s subject that actually runs here.

        "" if it cannot be asked. Only a pin that follows the local
        toolchain needs it.
        """
        return ""

    def conventions(self, skill: Skill) -> Iterable[Finding]:  # noqa: ARG002 — the default hook; overrides read it
        """This standard's own rules, applied to its own examples."""
        return ()

    def prose(self, skill: Skill) -> Iterable[Finding]:  # noqa: ARG002 — the default hook; overrides read it
        """This standard's own rules, applied to its prose.

        The prose is the text around its examples; `conventions` covers
        the examples themselves.
        """
        return ()

    def inside_tests(self, body: str) -> set[int]:  # noqa: ARG002 — the default hook; overrides read it
        """Body-line indices a rule scoped to test code should look at.

        Which lines those are is a fact about the language, so the
        generic corpus builder asks rather than assumes.
        """
        return set()


_REGISTRY: dict[str, Profile] = {}


def register(profile: Profile) -> Profile:
    """Add `profile` to the registry under its name, and return it."""
    _REGISTRY[profile.name] = profile
    return profile


#: Every module that defines a profile. Importing one is what registers
#: it.
MODULES = ("bevy_style", "python_style", "rust_style", "zig_style")


def _load() -> dict[str, Profile]:
    if not _REGISTRY:
        for module in MODULES:
            importlib.import_module(f"agent_skill.profiles.{module}")
    return _REGISTRY


def registered() -> tuple[Profile, ...]:
    """Every profile this build knows about.

    A check that needs the roster asks for it rather than restating it:
    the empty-corpus guard named rust and zig literally, so a third
    toolchain that silently extracted nothing would have reported clean.
    """
    return tuple(_load().values())


def profile_for(name: str) -> Profile:
    """`name`'s registered profile, or a bare one if it has none."""
    registry = _load()
    if name in registry:
        return registry[name]
    return Profile(name=name, prefix=_guess_prefix(name))


def _guess_prefix(name: str) -> str:
    """`rust-style` -> `RS`.

    Only used for a skill that ships no profile.
    """
    parts = [p for p in name.replace("_", "-").split("-") if p]
    return "".join(p[0] for p in parts[:2]).upper() or "XX"
