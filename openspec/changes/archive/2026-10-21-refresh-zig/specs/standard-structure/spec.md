# Spec Delta

## ADDED Requirements

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

## MODIFIED Requirements

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

## REMOVED Requirements

### Requirement: A standard that does not yet conform is exempt by declaration

**Reason**: Every standard conforms once zig-style is converted, so the exemption has nothing left to
cover. Code that only runs for an exempt standard is code no run exercises.

**Migration**: A standard added later conforms from its first commit. The shared template and
`agent-skill fmt` write its shared text, the vocabulary names its chapters, and `agent-skill demote`
and `agent-skill renumber` keep its IDs dense.
