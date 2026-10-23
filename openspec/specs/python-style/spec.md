# python-style Specification

## Purpose
A single Python engineering standard an agent loads before writing, reviewing, or migrating any
Python, stating the rules of modern CPython with each rule attributed to the source it comes from
and paired with a check that decides it.

The standard's subject is pure Python. Authoring, building, and distributing compiled extension
modules are out of scope and the standard does not cover them; a project that ships an extension
module is served by this standard only for the Python it also contains.

## Requirements

### Requirement: Single target version, with an explicit floor

The standard SHALL target exactly one CPython version — 3.15, free-threaded — and SHALL state that
floor in its own text. It SHALL NOT describe compatibility shims, version guards, or fallbacks for
any interpreter below 3.14t, and SHALL NOT present a pre-3.14 spelling as an acceptable
alternative.

#### Scenario: A rule offers a fallback for an older interpreter

- **WHEN** a rule presents `sys.version_info` branching, a `try: ... except ImportError:` import
  shim, or a "on older Pythons, write it this way" alternative for an interpreter below 3.14t
- **THEN** the standard is non-conforming, and the rule states the 3.15 spelling only

#### Scenario: A reader asks which interpreter the examples were verified against

- **WHEN** the reader reads the standard's opening section
- **THEN** the exact interpreter build is named, including that it is the free-threaded build

#### Scenario: A stale idiom is described

- **WHEN** the standard mentions an idiom that 3.14 or 3.15 superseded — `from __future__ import
  annotations`, a hand-rolled sentinel, `MappingProxyType` for an immutable mapping,
  GIL-dependent thread-safety reasoning
- **THEN** it appears only as the *dead* side of a migration table or a `BAD` example, never as
  advice

#### Scenario: An explicit encoding is described

- **WHEN** a rule passes `encoding="utf-8"` to a text open, although 3.15 made UTF-8 the default
- **THEN** it is advice and not a superseded idiom. The default holds only while UTF-8 mode is on,
  and `PYTHONUTF8=0` or `-X utf8=0` turns it off; What's New in 3.15 itself asks for an explicit
  `encoding`, and `-X warn_default_encoding` still flags every call that omits one

### Requirement: The dead-API discipline distinguishes removal from deprecation

The standard SHALL ship its dead-API table as a runnable command, and that table SHALL separate a
name that no longer exists from a name that still resolves and from a spelling that is merely
discouraged. A name the language documents as soft-deprecated — carrying no warning and no removal
date — SHALL NOT be reported as dead.

#### Scenario: A removed name appears in a diff

- **WHEN** the diff uses a name the target version removed
- **THEN** the shipped command reports it, and the table names the replacement

#### Scenario: A soft-deprecated name appears in a diff

- **WHEN** the diff uses a name the language explicitly states it has no plans to remove
- **THEN** the shipped command does not report it as dead; if the standard prefers a different
  spelling, that is a separate rule at its own tier

#### Scenario: A name is removed from the public listing but still resolves

- **WHEN** a name has been dropped from a module's public listing while remaining importable, with
  actual removal scheduled for a later version
- **THEN** the table records it at a tier distinct from an outright removal, and states the version
  in which it actually disappears

#### Scenario: A spelling is rejected while the name survives

- **WHEN** the target version rejects a call form or construction syntax while keeping the name
- **THEN** the table records the shape rather than the name, because a name-based search cannot
  find it

### Requirement: Three attributed sources, with conflicts resolved in the open

The standard SHALL merge exactly three sources and SHALL name them: the normative Python
specifications (PEP 8, PEP 257, PEP 20, and the Python Typing Spec), the empirical conventions of
the CPython 3.15 standard library, and Ruff's rule catalogue as the house standard. Every rule SHALL
be traceable to at least one of them. Where two sources disagree, the rule SHALL state the
disagreement, pick a side, and give the reason.

#### Scenario: A rule restates a Ruff rule

- **WHEN** a rule's whole actionable content is something one code in Ruff's catalogue already
  decides
- **THEN** it is a row in its chapter's `Decided by tools` table rather than a rule. The row gives
  the ruff code, and the shipped lint configuration enables it

#### Scenario: A rule says more than the Ruff rule it relies on

- **WHEN** a Ruff code decides part of a rule, but the rule also states a design choice, a
  when-to-deviate, or a shape the code cannot see
- **THEN** it stays a rule, and its **Check** cites the ruff code, which the shipped lint
  configuration enables

#### Scenario: Two sources disagree

- **WHEN** PEP 8 and Ruff's default, or PEP 8 and the standard library's own practice, prescribe
  different things for the same question
- **THEN** the rule names both positions, states which one this standard takes, and gives the
  reason — rather than silently following one

#### Scenario: A chapter covers ground Ruff cannot reach

- **WHEN** the chapter is about free-threading, concurrency, API and ownership design, async
  lifecycle, or packaging
- **THEN** the chapter states which of the other two sources its rules rest on, and each rule still
  ships a check that decides it

### Requirement: Rules are portable across conforming tools

Every rule SHALL state a claim that holds under the normative specifications, independently of which
conforming tool checks it. A rule SHALL NOT depend on behaviour that only one checker implements, and
the standard SHALL forbid constructs that no specification defines. A construct that a specification
defines SHALL remain usable even where some tool has not yet implemented it.

#### Scenario: A checker offers an extension the specification does not define

- **WHEN** the pinned type checker supports a construct outside the type-system specification
- **THEN** the standard forbids that construct as non-portable, and no example uses it

#### Scenario: The pinned tool is upgraded and a check changes

- **WHEN** a tool release renames, re-levels, or removes a check a rule cites
- **THEN** the equality invariant fails and a pin is updated; the rule's claim and rationale are
  unchanged, because the claim never rested on that tool

#### Scenario: A rule can only be justified by one tool's inference

- **WHEN** a proposed rule cannot be traced to a normative specification or to the standard library's
  documented behaviour, and holds only because one checker infers it
- **THEN** it is not a rule of this standard

#### Scenario: A specified feature is unimplemented by some tool

- **WHEN** a feature is defined by a specification but one checker has not implemented it yet
- **THEN** the standard may still require it, because the claim rests on the specification — the
  boundary is that specified-but-unimplemented is permitted while implemented-but-unspecified is not

### Requirement: The same tier model as the sibling standards

The standard SHALL use the three tiers `[M]`, `[M!]`, and `[S]` with the meanings the sibling
standards give them, SHALL define what makes a codebase high-reliability, and SHALL give every
`[M!]` rule an explicit relaxed form.

#### Scenario: An `[M!]` rule ships without its relaxed form

- **WHEN** a rule is tagged `[M!]` and its body does not state what the relaxed reading is
- **THEN** the rule is non-conforming

#### Scenario: A rule states the same thing as a rule in a sibling standard

- **WHEN** a `python-style` rule and a `rust-style` or `zig-style` rule express the same engineering
  claim
- **THEN** the two carry the same tier, or the standard records why they differ

### Requirement: Every rule carries an ID, a rationale, and a decisive check

Every rule SHALL have an ID under a single prefix, a tier tag, a title, a `**Why:**` rationale of at
most three lines, and a `**Check:**` that names how to decide the rule against a diff. A rule that
needs another rule's subject SHALL cite that rule's ID in prose rather than restate it, and a rule
that would only point at another SHALL be merged into it. IDs SHALL be dense within their chapter.
A renumbering SHALL ship a table mapping every old ID to its replacement.

#### Scenario: A rule ships without a rationale or a check

- **WHEN** a rule body has no `**Why:**`, or no `**Check:**`
- **THEN** the rule is non-conforming, whether or not it points at another rule

#### Scenario: A rationale outgrows three lines

- **WHEN** a rule's `**Why:**` runs past three lines
- **THEN** the rule is non-conforming. The excess belongs in the statement, in an example, or
  nowhere

#### Scenario: A check is a runnable command

- **WHEN** the check can be expressed as a `ruff` selection, a `ty` rule, or a pattern
- **THEN** the check is written as that command, so it decides rather than advises

#### Scenario: IDs are cited across chapters

- **WHEN** one rule refers to another
- **THEN** it cites the target by ID, the ID exists, and it lives in the chapter the citation names

#### Scenario: IDs are renumbered

- **WHEN** rules are removed, demoted to lint-table rows, or reordered, and a chapter is renumbered
- **THEN** `references/migration.md` maps every old ID to its new ID or to what replaced it, so a
  citation made before the renumbering can still be resolved

### Requirement: A reality-check section that precedes the rules

`SKILL.md` SHALL open with a section covering what changed in 3.14 and 3.15 that makes older Python
wrong, before any rule is stated. It SHALL cover at minimum: free-threading and what it removes as a
correctness assumption, lazy annotations, lazy imports, `frozendict`, `sentinel`, UTF-8 as the
default encoding, unpacking in comprehensions, and the typing additions.

#### Scenario: An agent loads the standard to write new code

- **WHEN** the agent reads only the opening sections of `SKILL.md`
- **THEN** it has enough to avoid every idiom that 3.14 and 3.15 superseded, without loading a
  chapter

#### Scenario: A change produces wrong behaviour rather than an error

- **WHEN** a 3.14 or 3.15 change causes silently different behaviour instead of a failure — for
  example thread-safety that no longer follows from the GIL, or an encoding default that moved
- **THEN** the reality-check section calls it out explicitly as such

### Requirement: Chapter coverage and a reference map

The standard SHALL be split into chapters, each owning one rule-ID family and opening with a
contents table listing every rule it owns. `SKILL.md` SHALL carry a reference map from chapter to
rule family to subject matter, and SHALL instruct the reader to load one chapter rather than all of
them. Coverage SHALL span at minimum: naming and layout; typing; data modelling; errors and control
flow; free-threading and concurrency; async; API design and packaging; testing; performance;
formatting and output; and a migration chapter carrying the dead-API tables.

#### Scenario: A reader needs one rule

- **WHEN** the reader has a rule ID
- **THEN** the reference map resolves the prefix to a chapter, and that chapter's contents table
  resolves the ID to a rule, without reading the chapter through

#### Scenario: A rule is filed in the wrong chapter

- **WHEN** a rule's ID prefix does not match the chapter it appears in
- **THEN** the standard is non-conforming

### Requirement: A review protocol

The standard SHALL ship a review protocol giving a severity model, the order in which to read a
diff, the mechanical commands to run first, and the output format. The severity model SHALL name
which severities block a merge.

#### Scenario: An agent is asked to review existing Python

- **WHEN** the agent loads the review protocol
- **THEN** it has a severity for every finding, an order to read in, and a set of commands to run
  before reading anything

#### Scenario: A mechanical command cannot be run

- **WHEN** the reviewer cannot run one of the protocol's commands
- **THEN** the protocol requires reporting that it could not be run, rather than implying it passed

### Requirement: Bundled assets a reader copies verbatim

The standard SHALL ship the configuration files it prescribes — project metadata, lint
configuration, type-checker configuration, and a CI workflow — and each asset SHALL be derived from
the rules that own it rather than written independently. Every shipped asset SHALL be referenced
from the standard's text. An asset that describes a buildable project SHALL build.

#### Scenario: A shipped project template cannot be built

- **WHEN** the shipped project metadata is used to build the project it describes, and the build
  fails
- **THEN** the standard is non-conforming, however internally consistent that file is with the rules

#### Scenario: The asset and the rule disagree

- **WHEN** a shipped configuration file enables a setting at a level the rule that owns it does not
  require, or omits one the rule does require
- **THEN** the standard is non-conforming

#### Scenario: An asset ships unreferenced

- **WHEN** a file in the asset directory is named by no rule and no table
- **THEN** the standard is non-conforming

### Requirement: The standard names the tools it requires and ships their configuration

The standard SHALL name the linter, the type checker, the package manager, and the build backend a
conforming project must run, SHALL ship the configuration for each as an asset, and SHALL state the
exact version each is pinned to. Where a required tool offers no stability guarantee, the standard
SHALL say so and SHALL give the procedure for moving the pin. Each role SHALL be filled by exactly
one named tool: the standard SHALL NOT offer alternatives for a role, and SHALL NOT document a tool
it does not require.

#### Scenario: A role admits more than one plausible tool

- **WHEN** more than one tool could fill a role the standard names
- **THEN** the standard names exactly one and prescribes it unconditionally, rather than presenting
  a choice it leaves the reader to resolve

#### Scenario: A reader adopts the standard

- **WHEN** the reader follows the standard to set up a project
- **THEN** they are told which tools to run, with what configuration, at what version — rather than
  being shipped a configuration file whose use is left unstated

#### Scenario: A required tool offers no API stability

- **WHEN** a mandated tool declares that its behaviour may change between any two releases
- **THEN** the standard states that policy, pins the version exactly, and gives the bump procedure

#### Scenario: A project runs a second tool as well

- **WHEN** a project runs an additional checker beyond the mandated one
- **THEN** the standard neither forbids it nor promises the two agree, and does not weaken a rule to
  make them agree

### Requirement: The standard states facts, not provenance

The standard SHALL NOT report how it was built, on what date, on which machine, or that anyone
verified anything. It SHALL state the rule and cite the source.

#### Scenario: Prose reports the act of checking

- **WHEN** a line reads "we verified", "we checked", "all examples were tested on", or names a build
  date
- **THEN** the standard is non-conforming, and the line is rewritten to state the fact instead
