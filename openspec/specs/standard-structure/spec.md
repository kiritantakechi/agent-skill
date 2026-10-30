# standard-structure Specification

## Purpose

What every standard this repository ships has in common, and what the harness enforces about that.
The goal is that a reader who has learned one standard can find their way around any other by
position alone, and that the shared shape is held by a check rather than by imitation.

## Requirements

### Requirement: Every SKILL.md follows one skeleton

Every standard's `SKILL.md` SHALL open with an H1 of the form `<Language> Style — <target>`. It SHALL
contain exactly these H2 sections, in this order and with these titles: `How to use this standard`,
`1. Tiers`, `2. <target> reality check`, `3. Design principles`, `4. Core rules`,
`5. Review checklist`, `6. Reference map`, `7. Bundled assets`. Anything else that differs between
standards SHALL be written as an H3 inside one of those sections.

#### Scenario: A section is missing, renamed, or out of order

- **WHEN** a `SKILL.md` lacks one of the eight sections, titles it differently, or places it out of
  order
- **THEN** the run fails, and the finding names the expected section and what was found in its place

#### Scenario: A standard needs a section its siblings do not

- **WHEN** a standard has something to say that only applies to it, such as a delta standard listing
  where it departs from its anchor
- **THEN** it is an H3 inside the section it belongs to (the departures go under `3. Design
  principles`), and the skeleton check passes

#### Scenario: A subtitle is appended to a fixed title

- **WHEN** an H2 carries text after its fixed title, such as `3. Design principles — subtraction and
  symmetry`
- **THEN** the run fails, because two standards would then differ at the one level a reader uses
  to navigate

### Requirement: The target a standard names is the target it is verified against

The version in a standard's H1 and in its §2 title SHALL be the version that its harness pin
declares for that standard's subject: the language toolchain, or the engine crate for a delta
standard.

#### Scenario: The title and the pin disagree

- **WHEN** a `SKILL.md` says `Bevy Style — 0.20` while the verified crate depends on `=0.19.1`
- **THEN** the run fails, naming both versions

#### Scenario: A pin moves

- **WHEN** a pin is moved to a new version and the `SKILL.md` title is not changed with it
- **THEN** the run fails until the title matches, so a version bump cannot ship half-done

### Requirement: Shared text has one source and a verbatim copy in every standard

Text that is the same in every standard SHALL be kept once, as a template in the harness, and
filled in from values each standard declares. That covers the reading procedure, the tier table,
the marker legend, the ID-citation paragraph and the severity table. Each `SKILL.md` and each review
protocol SHALL contain the filled-in copy verbatim, so every skill still installs and loads on its
own.

#### Scenario: A copy drifts from the template

- **WHEN** a shared passage in a standard differs from the template filled in with that standard's
  values
- **THEN** the run fails, naming the standard, the passage, and the first line that differs

#### Scenario: The template changes

- **WHEN** a shared passage is edited in the template
- **THEN** every standard's copy fails until it is rewritten, and one command rewrites every copy
  from the template without hand-editing

#### Scenario: A standard needs one more step in a shared passage

- **WHEN** a delta standard needs an extra instruction in the reading procedure, such as "load the
  anchor standard as well"
- **THEN** the template provides a declared slot for it. The standard fills that slot rather than
  editing its copy, which would fail the equality check

#### Scenario: A skill is installed alone

- **WHEN** one skill directory is installed without the harness or its siblings
- **THEN** it reads completely, because the copy is in its own `SKILL.md` and not behind a reference
  to a shared file

### Requirement: Reference files are named from one vocabulary

Every chapter file SHALL be named by a single word taken from a vocabulary shared by every
standard. `review-checklist.md` is the only fixed exception. Two standards covering the same concept
SHALL use the same file name for it.

#### Scenario: A chapter's name is not in the vocabulary

- **WHEN** a file under `references/` has a name the shared vocabulary does not list
- **THEN** the run fails, naming the file

#### Scenario: A name joins two subjects

- **WHEN** a chapter is named like `errors-and-control-flow.md` or `traits-generics.md`
- **THEN** it is not in the vocabulary, and the run fails

#### Scenario: Two standards cover the same concept

- **WHEN** two standards each have a chapter about building and packaging the project
- **THEN** both name it with the one vocabulary word for that concept

### Requirement: Rule family codes come from one table

Every rule's family code SHALL be the code the shared table assigns to the chapter that holds it.
The same concept SHALL carry the same code in every standard. Core rules in `SKILL.md` SHALL use the
code `CORE`.

#### Scenario: A rule's code does not match its chapter

- **WHEN** a rule in `testing.md` carries a code other than the one the table assigns to `testing`
- **THEN** the run fails, naming the rule and the expected code

#### Scenario: Two standards abbreviate one concept differently

- **WHEN** the same concept would be `TST` in one standard and `TEST` in another
- **THEN** that cannot occur, because both read the code from one table

### Requirement: Every standard ships a review protocol and a migration chapter

Every standard SHALL ship `references/review-checklist.md` and `references/migration.md`. The
review protocol SHALL use one severity model shared by every standard, with the same labels, the
same order, and the same statement of which labels block a merge.

#### Scenario: A standard ships no review protocol

- **WHEN** a standard has no `review-checklist.md` or no `migration.md`
- **THEN** the run fails

#### Scenario: A standard invents its own severity label

- **WHEN** a review protocol's severity table has a label the shared model does not, or lacks one it
  does
- **THEN** the run fails. The examples column is the standard's own; the labels, their meanings and
  the blocking statement are not

### Requirement: Rule IDs are dense, and a renumbering ships its rename table

Within a chapter, rule numbers SHALL run 01, 02, … with no gaps and no letter suffixes. Whenever IDs
change, the standard's `migration.md` SHALL state the range each family ran before the revision, and
SHALL carry a table mapping every old ID that changed to its new ID, or to the lint-table row or
removal that replaced it. An old ID in range that the table does not list is unchanged.

#### Scenario: A chapter has a gap

- **WHEN** a chapter's rules run `…-07`, `…-09`
- **THEN** the run fails

#### Scenario: A rule is removed

- **WHEN** a rule is removed or demoted to a lint-table row
- **THEN** the chapter is renumbered, and the rename table records the old ID with what replaced it,
  so a citation made before the change can still be resolved

#### Scenario: An ID kept its number

- **WHEN** a renumbering leaves an old ID naming the same rule
- **THEN** the table has no row for it, because a row mapping an ID to itself tells the reader
  nothing the stated range does not

#### Scenario: An unlisted ID no longer exists

- **WHEN** an old ID inside a stated range has no row, and no rule carries it any more
- **THEN** the run fails, because the table claims that ID is unchanged

#### Scenario: A rename table names a rule that does not exist

- **WHEN** a row of the rename table maps an old ID to a new ID that no rule carries, or to a
  lint-table row that no chapter contains
- **THEN** the run fails, because a reader following the table would arrive nowhere

### Requirement: A renumbering is one operation that preserves every citation

Renumbering SHALL be performed by one operation. That operation SHALL rewrite every citation in the
repository and write the rename table. It SHALL fail unless every citation refers to the same rule
after the rewrite as before, comparing rules by identity rather than by ID. It SHALL also fail
unless every ID that existed before the revision is either still the same rule or has a row.

#### Scenario: Old and new IDs overlap

- **WHEN** an old ID is reused as the new ID of a different rule, as dense numbering makes routine
- **THEN** citations are still rewritten correctly, because the rewrite is applied in one pass from
  the old numbering and never in a chain of replacements

#### Scenario: A citation would change meaning

- **WHEN** after the rewrite some citation resolves to a rule other than the one it resolved to before
- **THEN** the operation fails and leaves the tree unchanged

#### Scenario: An old ID is missing from the table

- **WHEN** an ID defined before the renumbering is neither renamed nor recorded as demoted or removed
- **THEN** the operation fails, because a reader holding that ID would have nowhere to look

#### Scenario: A citation is edited in by hand afterwards

- **WHEN** someone later cites an old ID that, under dense numbering, is now a different rule's ID
- **THEN** no check can tell it from a correct citation. This is why the rewrite is never done by
  hand, and the requirement says so rather than implying the run would catch it

### Requirement: A claim a tool decides is a lint-table row, not a rule

When the whole of a rule's actionable content is one lint that the standard's shipped configuration
enables, or one error that the standard's compiler always reports, it SHALL be a row in its chapter's
`Decided by tools` table and not a rule. The row SHALL give the lint or error, its level, and one line
on what it forbids. A rule that says more than its lint or error SHALL stay a rule and cite it in its
**Check**.

#### Scenario: A row names a lint the shipped configuration does not enable

- **WHEN** a lint-table row names a lint that the standard's shipped configuration leaves off, or
  sets at a different level
- **THEN** the run fails

#### Scenario: A row names a lint the tool does not have

- **WHEN** a row names a lint that the pinned tool does not recognise
- **THEN** the run fails, as a citation of a withdrawn check does

#### Scenario: A rule adds a design choice to its lint

- **WHEN** a lint covers part of a rule, but the rule also states when to deviate or a pattern the
  lint cannot see
- **THEN** it stays a rule, with Why and Check, and its Check names the lint

#### Scenario: A rule restates an error the compiler always reports

- **WHEN** a rule's whole content is that the compiler rejects a construct, such as an unused local
  constant
- **THEN** it is a row with the compiler as its tool, and the rename table records the rule's old ID
  against that row

### Requirement: A Why is at most three lines

A rule's **Why** SHALL fit in three lines of the file at the standard's line width. Anything longer
SHALL move into the rule's statement, into an example, or out of the standard.

#### Scenario: A Why runs to a fourth line

- **WHEN** a rule's **Why** paragraph occupies more than three lines
- **THEN** the run fails, naming the rule and the line count

### Requirement: One marker vocabulary

Every fenced example SHALL be marked `verified`, `fragment`, or `rejected — <tool>: <reason>`,
where `<tool>` is one of the tools the standard requires. `does-not-compile` SHALL NOT appear in any
standard.

#### Scenario: A rejected block does not name its tool

- **WHEN** a block is marked `rejected` with no tool, or with a tool the standard does not require
- **THEN** the run fails

#### Scenario: A conforming standard uses the old word

- **WHEN** a block in any standard is marked `does-not-compile`
- **THEN** the run fails, and the finding gives the `rejected — <tool>` form

### Requirement: A row the compiler decides is verified by a probe

A `Decided by tools` row whose tool is a compiler with no lint configuration SHALL name, in its Lint
cell, a stable phrase from the error the pinned compiler reports, at level `error`. The harness SHALL
keep one probe per such row: the smallest source the compiler rejects with that error. Every row SHALL
have a probe, and every probe SHALL have a row.

#### Scenario: A probe compiles

- **WHEN** the pinned compiler accepts a row's probe
- **THEN** the run fails, because the row claims an error that the compiler does not report

#### Scenario: A probe fails for another reason

- **WHEN** the compiler rejects a probe and no error it prints contains the row's phrase
- **THEN** the run fails and names the error that was printed, so a row cannot pass on a probe that
  breaks for an unrelated reason

#### Scenario: A row has no probe, or a probe has no row

- **WHEN** a row names an error that no probe exercises, or a probe exercises an error that no row
  names
- **THEN** the run fails in either direction, as a lint table and its shipped configuration are
  compared both ways

#### Scenario: The compiler is not available

- **WHEN** the pinned compiler is not on this machine
- **THEN** the rows are reported as not verified rather than passed

#### Scenario: A compiler release changes the message

- **WHEN** a compiler bump rewords an error so that the row's phrase no longer appears
- **THEN** the run fails until the row and its probe are updated, which is part of the bump

### Requirement: A rule speaks of its target version only

A rule's body SHALL describe its subject as it is at the standard's target version. A version of
that subject below the target SHALL appear only in the migration chapter, in `SKILL.md` §2, and in
the review protocol, which are where a standard keeps its history.

#### Scenario: A rule annotates when its API arrived

- **WHEN** a rule outside the migration chapter says that something became available, changed, or
  was removed in a version below the target, such as "stable since 1.82" in a standard targeting
  Rust 1.99
- **THEN** the run fails, naming the rule and the version, because the reader of a target-version
  standard has that API already and the date of its arrival tells them nothing they act on

#### Scenario: The fact matters to someone porting older code

- **WHEN** the version is the point, such as a call whose meaning changed in the release before the
  target
- **THEN** it belongs in the migration chapter or §2, which may name any version, and the rule
  states the target's behaviour

#### Scenario: A version in an example's code

- **WHEN** a version appears inside a fenced example, such as a manifest's `rust-version`
- **THEN** it is not a finding; the check reads a rule's prose

### Requirement: No rule only points at another

Every rule SHALL state its subject in full, with its own Why and Check. A rule SHALL NOT consist of
a pointer to the rule that owns its topic. Where a chapter needs to mention a rule another chapter
owns, it cites the ID in prose.

#### Scenario: A rule is only a pointer

- **WHEN** a rule's statement says that another rule owns its topic and gives no Why or Check
- **THEN** the run fails as any rule without a Why and a Check does, and the fix is to merge it into
  its owner, recording the merge in the rename table

#### Scenario: A rule restates another

- **WHEN** two rules give the same instruction for the same reason
- **THEN** one owns it and the other is merged into it, so a reader finds the rule once
