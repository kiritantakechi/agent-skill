"""What a profile is: frozen records, interpreted by the checks.

A profile is a literal in its standard's module, and holds no behaviour
a check does not interpret, so everything a check knows about one
standard can be read without running anything.
"""

from dataclasses import dataclass, field
lazy from collections.abc import Callable, Iterable, Mapping

from agent_skill.ids import RuleId, Version
lazy from agent_skill.ids import Branch, Pin
lazy from agent_skill.lang import Config
lazy from agent_skill.lang.rust import RustCrate
lazy from agent_skill.model import Block
lazy from agent_skill.report import Finding

#: A rule of a standard's own that reads an example's structure rather
#: than its lines: a derive list, or which of two imports comes first.
#: Named in its standard's module, and each one listed in the design.
type Structural = Callable[[Block], Iterable[Finding]]


def keyed[T](spelled: Mapping[str, T]) -> Mapping[RuleId, T]:
    """`spelled`, each key read as the rule it names.

    A profile is written by hand, so it spells a rule as a reader cites
    one, and the record holds the rule: a key that is not a rule ID
    stops the import, where as a string it was a key no rule would ever
    equal, and a check comparing it with a rule's printed ID was a
    second reader of IDs.
    """
    return {RuleId.parse(key): value for key, value in spelled.items()}


def rules(*spelled: str) -> frozenset[RuleId]:
    """The rules `spelled` names, each read as `keyed` reads a key."""
    return frozenset(RuleId.parse(text) for text in spelled)


@dataclass(frozen=True, slots=True)
class Near:
    """A pattern on a hit's line, or on the lines around it.

    Lines are read as written, comments and all: what excuses a hit is
    as often a comment as code.
    """

    pattern: str
    #: how many lines above the hit's own are read
    above: int = 0
    #: how many lines below it are read
    below: int = 0
    #: reading upward stops at a line this matches: the end of the item
    #: above, whose attributes are not this item's
    stop: str = ""
    #: whether the hit's own line is read
    own: bool = True


@dataclass(frozen=True, slots=True)
class Unless:
    """What, on or around a hit, makes it the case its rule permits."""

    near: tuple[Near, ...] = ()
    #: a hit outside the example's tests is not this rule's subject
    outside_tests: bool = False


@dataclass(frozen=True, slots=True)
class LineRule:
    """One of a standard's own rules, as a pattern each line is held to.

    The profile field a rule sits in is what it reads: `conventions`
    holds each line of the standard's advice examples to it, `prose`
    each line of its prose outside a **Check:**, which hunts the very
    spellings a rule forbids.
    """

    #: declared in the profile's module; its level is the finding's
    branch: Branch
    #: searched in each line
    pattern: str
    #: `{0}` is what the pattern matched and `{1}`, `{2}`… its groups;
    #: a brace meant as itself is doubled
    message: str
    #: read an example's line as written, its comment too, rather than
    #: with its comment taken out
    comments: bool = False
    #: the rule whose own example, or own prose, shows what this forbids
    #: on purpose
    unless_own: RuleId | None = None
    unless: Unless = Unless()
    #: each must be near the hit as well, for it to be one
    needs: tuple[Near, ...] = ()


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
    #: The edition the target compiles under, for a standard about a
    #: language whose changes land in editions as well as releases:
    #: Rust's `2024`. A migration row's Since may name it, and section
    #: 2.2 lists the rows that do (normalize-the-standards, decision 9).
    edition: Version | None = None
    #: above this many hits a pattern enumerates rather than accuses
    judgement: int = 15
    #: Rule id -> what, around a hit of its pattern, makes the hit the
    #: case the rule permits.
    exempt: Mapping[RuleId, Unless] = field(default_factory=dict)
    not_decisive: Mapping[RuleId, NotDecisive] = field(default_factory=dict)
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
    #: several patterns and one snippet cannot exhibit them all — a
    #: migration rule once covered four disjoint families of dead API.
    #: While this was one snippet the assertion could only be `any`, so
    #: three of that rule's four patterns were counted as proven by a
    #: fixture none of them matched.
    #:
    #: Matched as a cover in both directions: every command pattern hits
    #: some snippet, and every snippet is hit by some pattern. The
    #: second direction is what keeps the first honest — without it, a
    #: pattern narrowed until it stops matching can be "fixed" by adding
    #: a snippet nothing relates to the rule.
    fires: Mapping[RuleId, tuple[str, ...]] = field(default_factory=dict)
    #: Rule ids whose Check ships an `rg` pattern that no entry in
    #: `fires` proves yet.
    #:
    #: The gap, stated. `sensitivity` used to skip a rule with no
    #: fixture and say nothing, so most shipped patterns were unproven
    #: while the check read as covering every one. Now each rule that
    #: ships a pattern is either proven or listed here, and an entry
    #: that has stopped being true — the rule is gone, ships no pattern,
    #: or has a fixture now — fails, so the list can only shrink.
    unproven: frozenset[RuleId] = frozenset()
    #: A compiler row's phrase -> the smallest source the compiler
    #: rejects with it. A compiler has no lint table to compare a row
    #: against, so each row is proved by a probe, and each probe needs
    #: its row: a probe nothing cites would prove an error the standard
    #: never mentions.
    probes: Mapping[str, str] = field(default_factory=dict)
    #: Each domain chapter: a chapter whose word names no chapter of the
    #: abstract standard, and the feature of this standard's domain that
    #: owns it — rust-style's `ownership`, the borrow checker. Every
    #: other chapter is an abstract chapter's, and holds the standard's
    #: realisations of its concepts (one-abstract-standard, decision 4).
    domain: Mapping[str, str] = field(default_factory=dict)
    #: Whether the harness is written to this standard: its assets are
    #: the configuration in force in this repository, and each step the
    #: repository's workflows share with its shipped workflow is taken
    #: as that step stands (`self-application`). One profile says so.
    harness: bool = False
    #: This standard's own rules, held to each line of its own examples.
    conventions: tuple[LineRule, ...] = ()
    #: This standard's own rules, held to each line of the prose around
    #: its examples.
    prose: tuple[LineRule, ...] = ()
    #: This standard's own rules that read an example's structure.
    structural: tuple[Structural, ...] = ()

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
    def target(self) -> str:
        """The series `pin` belongs to, `3.15`; "" when there is none.

        What the title, the reality-check section and a revision's
        rename table name: a patch release moves the pin, not the
        target.
        """
        return str(self.pin.version.series) if self.pin is not None else ""

    @property
    def since(self) -> frozenset[Version]:
        """What a migration row's Since names when the target made it.

        The series `pin` belongs to, and the edition, where the language
        has one: Rust 1.99 targets `1.99` and `2024` both, since its
        examples compile under that release and that edition. Section
        2.2 is the migration table's rows whose Since is one of these.
        """
        found = (Version.try_parse(self.target), self.edition)
        return frozenset(v for v in found if v is not None)

    @property
    def anchor(self) -> str:
        """The standard this one is a delta on, or ""."""
        return self.delta.anchor if self.delta is not None else ""

    @property
    def delta_step(self) -> str:
        """A delta's extra reading step, or ""."""
        return self.delta.step if self.delta is not None else ""
