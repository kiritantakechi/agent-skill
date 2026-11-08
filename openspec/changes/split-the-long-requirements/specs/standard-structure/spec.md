## REMOVED Requirements

### Requirement: A renumbering is one operation that preserves every citation

**Reason**: Its text was longer than 500 characters and stated more than one behaviour, and a
MODIFIED requirement cannot hand a scenario to another requirement, so it is split by removing it
and adding its parts.

**Migration**: Every clause and every scenario it held is kept, unchanged, in "A renumbering is one
operation that rewrites every citation"; "A renumbering that would change what a citation names
fails and leaves the tree unchanged"; "A renumbering is checked by its inverse and by the empty
plan".

### Requirement: A claim a tool decides is a lint-table row, not a rule

**Reason**: Its text was longer than 500 characters and stated more than one behaviour, and a
MODIFIED requirement cannot hand a scenario to another requirement, so it is split by removing it
and adding its parts.

**Migration**: Every clause and every scenario it held is kept, unchanged, in "A claim a tool
decides is a row of the `Decided by tools` table, not a rule"; "Every lint the shipped configuration
sets has exactly one row".

### Requirement: Section 2 has three subsections in one order

**Reason**: Its text was longer than 500 characters and stated more than one behaviour, and a
MODIFIED requirement cannot hand a scenario to another requirement, so it is split by removing it
and adding its parts.

**Migration**: Every clause and every scenario it held is kept, unchanged, in "Section 2 has three
subsections, and each item of the third names its rule"; "The first two subsections of section 2 are
rendered from the migration table".

### Requirement: Migration is a function from old spelling to row

**Reason**: Its text was longer than 500 characters and stated more than one behaviour, and a
MODIFIED requirement cannot hand a scenario to another requirement, so it is split by removing it
and adding its parts.

**Migration**: Every clause and every scenario it held is kept, unchanged, in "A migration chapter
holds one table keyed uniquely by old spelling"; "Since is a release, and the command that finds old
spellings is generated from the table"; "Sections 2.1 and 2.2 of `SKILL.md` are the migration table
restricted to the target's rows".

## ADDED Requirements

### Requirement: A renumbering is one operation that rewrites every citation

Removing, merging, demoting, moving and renumbering rules SHALL be one operation, `revise`, taking a
partial map from old ID to what it becomes and closing it by dense renumbering. A move SHALL take a
rule to another chapter of the same standard, at a stated place among that chapter's rules, and give
it the target family's code. It SHALL rewrite every citation in the repository through the document
model and write the rename table.

#### Scenario: Old and new IDs overlap

- **WHEN** an old ID is reused as the new ID of a different rule, as dense numbering makes routine
- **THEN** citations are still rewritten correctly, because the rewrite is one permutation applied
  to every ID token at once and never a chain of replacements

#### Scenario: A move into a chapter the standard does not have

- **WHEN** a plan moves a zig-style rule into `documentation.md`, which zig-style does not yet ship
- **THEN** the chapter is created in the chapter template, with its contents and its `Scope:` left
  for the author to write, and the run fails until they are written

#### Scenario: A citation is edited in by hand afterwards

- **WHEN** someone later cites an old ID that, under dense numbering, is now a different rule's ID
- **THEN** no check can tell it from a correct citation. This is why the rewrite is never done by
  hand, and the requirement says so rather than implying the run would catch it

### Requirement: A renumbering that would change what a citation names fails and leaves the tree unchanged

It SHALL fail, leaving the tree unchanged, unless every citation refers to the same rule after the
rewrite as before, compared by identity rather than by ID; unless every ID that existed before the
revision is either still the same rule or has a row; and if any cited ID that named no rule before
the revision would name one after it.

#### Scenario: A citation would change meaning

- **WHEN** after the rewrite some citation resolves to a rule other than the one it resolved to before
- **THEN** the operation fails and leaves the tree unchanged

#### Scenario: A dangling citation would be captured

- **WHEN** a file cites an ID that names no rule, and the renumbering would assign that ID to a rule
- **THEN** the operation fails and names the citation, because writing would silently bind it to a
  rule its author never meant

#### Scenario: An old ID is missing from the table

- **WHEN** an ID defined before the renumbering is neither renamed nor recorded as demoted or removed
- **THEN** the operation fails, because a reader holding that ID would have nowhere to look

### Requirement: A renumbering is checked by its inverse and by the empty plan

The operation SHALL satisfy, and the test suite SHALL check: applying a pure renumbering and then
its inverse restores every file byte for byte; applying a move and then the move back to the rule's
old place restores every file byte for byte; applying an empty plan writes nothing and reports
nothing.

#### Scenario: Renumbering and back

- **WHEN** a chapter is renamed and renumbered, and the inverse renaming is applied
- **THEN** every file is byte-identical to the original

#### Scenario: Moving a rule and back

- **WHEN** RS-CLI-07 is moved into `output.md` after RS-OUT-03, and the result is moved back into
  `cli.md` after the rule that preceded it
- **THEN** every file is byte-identical to the original, the rename table included

#### Scenario: Nothing to do

- **WHEN** the plan is empty and the numbering is already dense
- **THEN** no file is written and nothing is reported as written

### Requirement: A claim a tool decides is a row of the `Decided by tools` table, not a rule

When the whole of a rule's actionable content is one lint that the standard's shipped configuration
enables, or one error that the standard's compiler always reports, it SHALL be a row in its
chapter's `Decided by tools` table and not a rule. The row SHALL give the lint or error, its level,
and one line on what it forbids. A rule that says more than its lint or error SHALL stay a rule and
cite it in its **Check**.

#### Scenario: A rule adds a design choice to its lint

- **WHEN** a lint covers part of a rule, but the rule also states when to deviate or a pattern the
  lint cannot see
- **THEN** it stays a rule, with Why and Check, and its Check names the lint

#### Scenario: A rule restates an error the compiler always reports

- **WHEN** a rule's whole content is that the compiler rejects a construct, such as an unused local
  constant
- **THEN** it is a row with the compiler as its tool, and the rename table records the rule's old ID
  against that row

#### Scenario: A rule whose Check is only a lint

- **WHEN** a rule's Check consists of nothing but a lint code the configuration enables
- **THEN** the run fails: the rule is that row

### Requirement: Every lint the shipped configuration sets has exactly one row

Every lint the shipped configuration sets explicitly SHALL have exactly one row, in the chapter that
owns its subject; a row for a lint that is on by default SHALL say why it is listed.

#### Scenario: A row names a lint the shipped configuration does not enable

- **WHEN** a lint-table row names a lint that the standard's shipped configuration leaves off, or
  sets at a different level
- **THEN** the run fails

#### Scenario: A row names a lint the tool does not have

- **WHEN** a row names a lint that the pinned tool does not recognise
- **THEN** the run fails, as a citation of a withdrawn check does

#### Scenario: A configured lint with no row

- **WHEN** the shipped configuration sets a lint that no chapter's table lists
- **THEN** the run fails, because a reader learns what the build forbids from the rows

### Requirement: Section 2 has three subsections, and each item of the third names its rule

Section 2 of every `SKILL.md` SHALL have exactly three subsections, in this order: what compiles and
behaves differently, what no longer compiles, and what the target gained. Every item of the third
SHALL name the rule that owns it.

#### Scenario: An item with no owner

- **WHEN** a section 2 item states a change no rule or migration row holds
- **THEN** the run fails, because section 2 indexes the chapters and holds nothing of its own

### Requirement: The first two subsections of section 2 are rendered from the migration table

The first SHALL be the migration table's `changed` rows whose since is the target's, and the second
its `gone` rows whose since is the target's, each rendered from the table, as the migration
requirement states; so the statuses and the first two subsections are one partition, and a row that
still compiles and means what it did is in neither.

#### Scenario: A rejected spelling under what still compiles

- **WHEN** section 2.1 lists a row whose status is `gone`, or section 2.2 one whose status is
  `changed`, `alias` or `deprecated`
- **THEN** `fmt` renders each from the migration table, and the run fails until it has

### Requirement: A migration chapter holds one table keyed uniquely by old spelling

Each migration chapter SHALL hold one table keyed uniquely by old spelling, with columns old
spelling, target spelling, status, since and owning rule, where status is what the target does with
the old spelling: `gone`, it rejects it (a compile, import or attribute error); `changed`, it
accepts it and it means something else; `alias` or `deprecated`, it accepts it and it means what it
did. An old spelling with `…` in it is a shape, code left out where the `…` stands.

#### Scenario: One old spelling in two rows

- **WHEN** an old spelling appears in two rows
- **THEN** the run fails

### Requirement: Since is a release, and the command that finds old spellings is generated from the table

Since is the release from which the status holds — for a language whose changes land in editions as
well as releases, the edition when the edition made the change — in one form per standard, no later
than the target. The command a reader runs to find old spellings SHALL be generated from the `gone`
and `alias` rows that are no shape, and every `gone` row the toolchain can look up or compile SHALL
be verified rejected by the pinned release.

#### Scenario: A since the target has not reached

- **WHEN** a Python 3.15 standard's row gives since `3.16`, or `3.15.0`
- **THEN** the run fails: since is a release's series, no later than the target's

#### Scenario: A shape in the command

- **WHEN** a `gone` row's old spelling is `TextFont { line_height: … }`
- **THEN** the generated command has no pattern for it, and its owning rule's Check finds it

#### Scenario: A gone row naming a live API

- **WHEN** a row marked `gone` names a symbol the pinned release still provides, or a spelling the
  target edition still compiles
- **THEN** the run fails

### Requirement: Sections 2.1 and 2.2 of `SKILL.md` are the migration table restricted to the target's rows

Sections 2.1 and 2.2 of `SKILL.md` SHALL be the table restricted to the `changed` and to the `gone`
rows whose since is the target's, each with columns old spelling, target spelling and owning rule,
followed by one line saying where that status's other rows are and how a reader finds them, rendered
from the table.

#### Scenario: Section 2.2 kept by hand

- **WHEN** section 2.2 lists a row whose since is an older release, or leaves out a `gone` row whose
  since is the target's
- **THEN** `fmt` renders it from the migration table, and the run fails until it has
