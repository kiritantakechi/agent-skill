"""What a profile is: frozen records, interpreted by the checks.

A profile is a literal in its standard's module, and holds no behaviour
a check does not interpret, so everything a check knows about one
standard can be read without running anything.
"""

from dataclasses import dataclass, field
lazy from collections.abc import Callable, Iterable, Mapping

lazy from agent_skill.checks.search import Span
lazy from agent_skill.ids import Pin
lazy from agent_skill.lang import Config
lazy from agent_skill.lang.rust import RustCrate
lazy from agent_skill.model import Skill
lazy from agent_skill.report import Finding

#: Whether a hit is the case its rule permits, given the corpus lines,
#: the hit's span, and the lines that sit inside tests.
type Exemption = Callable[[list[str], Span, set[int]], bool]

#: A standard's own rules, applied to one skill.
type Rules = Callable[[Skill], Iterable[Finding]]


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


@dataclass(frozen=True, slots=True)
class Delta:
    """A standard that defers to another except where it departs.

    Both halves at once, so a delta cannot declare one without the
    other: the anchor without the reading step left `SKILL.md` silent
    about the second standard, and the step without the anchor turned
    off the sweep of the anchor's patterns.
    """

    #: The standard this one is a delta on, by name.
    #:
    #: Declared rather than read from the override table, because the
    #: table is what `crossref` checks: deriving the anchor from its
    #: rows meant deleting the table deleted the anchor, which turned
    #: off the sweep of the anchor's patterns and left a note.
    anchor: str
    #: The extra reading step in `SKILL.md`.
    step: str


@dataclass(frozen=True, slots=True)
class Mirror:
    """Rules that say what another standard's rules say, at their tier.

    Each pair names a rule here and the **title** of its counterpart in
    the anchor: titles survive renumbering, and a renumbering pass twice
    pointed an ID-keyed table at unrelated rules. A rule here that
    looks like an anchor rule and is in no pair is noted, so a standard
    with no pairs still declares which standard it is compared with.
    """

    anchor: str
    pairs: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True, slots=True)
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
    #: filled with the release `pin` names and `{toolchain}` with the
    #: release the toolchain's own pin names, so the sentence cannot
    #: name a version the harness does not verify against.
    verified_as: str = ""
    #: The code in which `[M!]` binds as `[M]`: "library and
    #: high-reliability".
    strict_scope: str = ""
    #: The standard this one is a delta on, or None for one that stands
    #: alone.
    delta: Delta | None = None
    #: How the examples are built: which toolchain, and its settings for
    #: this skill. None for a skill whose examples nothing compiles.
    toolchain: Config | None = None
    #: What the standard is verified against when that is not its
    #: toolchain's own release: the library a delta is about.
    subject: Pin | None = None
    #: above this many hits a pattern enumerates rather than accuses
    judgement: int = 15
    #: rule id -> (corpus lines, the hit's span, in_test) -> "is this
    #: hit the case the rule permits?"
    exempt: Mapping[str, Exemption] = field(default_factory=dict)
    not_decisive: Mapping[str, NotDecisive] = field(default_factory=dict)
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
    fires: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    #: Rule ids whose Check ships an `rg` pattern that no entry in
    #: `fires` proves yet.
    #:
    #: The gap, stated. `sensitivity` used to skip a rule with no
    #: fixture and say nothing, so most shipped patterns were unproven
    #: while the check read as covering every one. Now each rule that
    #: ships a pattern is either proven or listed here, and an entry
    #: that has stopped being true — the rule is gone, ships no pattern,
    #: or has a fixture now — fails, so the list can only shrink.
    unproven: frozenset[str] = frozenset()
    #: A compiler row's phrase -> the smallest source the compiler
    #: rejects with it. A compiler has no lint table to compare a row
    #: against, so each row is proved by a probe, and each probe needs
    #: its row: a probe nothing cites would prove an error the standard
    #: never mentions.
    probes: Mapping[str, str] = field(default_factory=dict)
    #: The standard this one's rules are compared with for tier, and the
    #: pairs it holds.
    mirror: Mirror | None = None
    #: This standard's own rules, applied to its own examples.
    conventions: Rules | None = None
    #: This standard's own rules, applied to the prose around its
    #: examples.
    prose: Rules | None = None

    @property
    def all_marked(self) -> tuple[str, ...]:
        """Every fence tag that carries a marker, without repeats."""
        return tuple(dict.fromkeys(self.languages + self.marked_languages))

    @property
    def crate(self) -> RustCrate | None:
        """The crate the examples compile as, for a Rust toolchain."""
        return self.toolchain if isinstance(self.toolchain, RustCrate) else None

    @property
    def pin(self) -> Pin | None:
        """What this standard is verified against, exactly.

        The library a delta is about, else its toolchain's own release.
        The H1 names its major.minor, so the title and the harness
        cannot disagree about what the standard is for.
        """
        if self.subject is not None:
            return self.subject
        return self.toolchain.pin if self.toolchain is not None else None

    @property
    def release(self) -> str:
        """`pin`'s public release, `3.15.2`; "" when there is none."""
        return str(self.pin.version.public) if self.pin is not None else ""

    @property
    def anchor(self) -> str:
        """The standard this one is a delta on, or ""."""
        return self.delta.anchor if self.delta is not None else ""

    @property
    def delta_step(self) -> str:
        """A delta's extra reading step, or ""."""
        return self.delta.step if self.delta is not None else ""
