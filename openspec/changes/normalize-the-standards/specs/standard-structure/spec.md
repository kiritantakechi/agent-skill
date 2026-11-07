## MODIFIED Requirements

### Requirement: A claim a tool decides is a lint-table row, not a rule

When the whole of a rule's actionable content is one lint that the standard's shipped configuration
enables, or one error that the standard's compiler always reports, it SHALL be a row in its chapter's
`Decided by tools` table and not a rule. The row SHALL give the lint or error, its level, and one line
on what it forbids. A rule that says more than its lint or error SHALL stay a rule and cite it in its
**Check**. Every lint the shipped configuration sets explicitly SHALL have exactly one row, in the
chapter that owns its subject; a row for a lint that is on by default SHALL say why it is listed.

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

#### Scenario: A configured lint with no row

- **WHEN** the shipped configuration sets a lint that no chapter's table lists
- **THEN** the run fails, because a reader learns what the build forbids from the rows

#### Scenario: A rule whose Check is only a lint

- **WHEN** a rule's Check consists of nothing but a lint code the configuration enables
- **THEN** the run fails: the rule is that row

## ADDED Requirements

### Requirement: A chapter has one template

Every chapter SHALL open with a title naming its concept and no family code, then a `Scope:`
paragraph, then its contents list, then its sections, with a `Decided by tools` section last when it
has one. Outside section 6, a chapter SHALL be named only in a `Scope:` paragraph.

#### Scenario: A title carrying the family code

- **WHEN** a chapter opens `# RS-BUILD — Cargo, dependencies, lints, toolchain`
- **THEN** the run fails; the code belongs to the file, through the vocabulary

#### Scenario: A chapter without a scope

- **WHEN** a chapter has no `Scope:` paragraph before its contents list
- **THEN** the run fails

### Requirement: A rule has one shape

A rule SHALL consist of, in this order: its heading; an optional statement that does not restate
the title; a relaxed form exactly when its tier is `[M!]`; its Why; its Check; and at most one GOOD
and at most one BAD example, with any number of examples that illustrate no side.

#### Scenario: A statement that restates the title

- **WHEN** a rule's first sentence is its title again
- **THEN** the run fails

#### Scenario: Two BAD examples

- **WHEN** a rule carries two blocks marked BAD
- **THEN** the run fails: the second defect is a second rule or a tool row

#### Scenario: Elements out of order

- **WHEN** a rule's Check precedes its Why, or an example precedes its Check
- **THEN** `fmt` reorders them, and the run fails until it has

### Requirement: A rule is cited by its bare ID

A citation of a rule SHALL be its ID, unquoted and unqualified by a path or a chapter name.

#### Scenario: A path-qualified citation

- **WHEN** a passage cites `` `references/memory.md` ZS-MEM-06 ``
- **THEN** `fmt` rewrites it to `ZS-MEM-06`, and the run fails until it has

### Requirement: A Check that names a pattern runs it

A Check SHALL be either judgement in prose, or one or more runnable `rg` commands followed by the
finding they report. Prose that names a pattern to search for without giving a runnable command
SHALL fail.

#### Scenario: A prose grep

- **WHEN** a Check reads "grep for `just_pressed` in a `FixedUpdate` system"
- **THEN** the run fails: the pattern is either a command, with its fixture, or judgement

### Requirement: Section 2 has three subsections in one order

Section 2 of every `SKILL.md` SHALL have exactly three subsections, in this order: what compiles and
behaves differently, what no longer compiles, and what the target gained. The second SHALL be the
migration table's rows whose since is the target's, rendered from it, as the migration requirement
states. Every other item SHALL name the rule or migration row that owns it.

#### Scenario: An item with no owner

- **WHEN** a section 2 item states a change no rule or migration row holds
- **THEN** the run fails, because section 2 indexes the chapters and holds nothing of its own

### Requirement: Tier is one predicate

`[M!]` SHALL mean mandatory within section 1's scope, and its relaxed form SHALL state what applies
outside that scope and nothing else. No rule SHALL restate the scope. An `[M]` or `[M!]` title SHALL
command or prohibit.

#### Scenario: A local restatement of the scope

- **WHEN** a rule says "`[M!]` applies to …" or gives an "`[M!]` trigger"
- **THEN** the run fails; a condition on the subject belongs in the statement

#### Scenario: A mandatory title in the mood of advice

- **WHEN** an `[M]` title begins "Prefer" or "Know"
- **THEN** the run fails

### Requirement: Section 4 is a projection of chapter rules

Section 4 SHALL list chapter rule IDs grouped by chapter in section 6's order, each line rendered
from its chapter rule's tier and title. There SHALL be no `CORE` family.

#### Scenario: A core line that drifted

- **WHEN** a section 4 line's tier or title differs from its chapter rule's
- **THEN** `fmt` re-renders it, and the run fails until it has

### Requirement: Migration is a function from old spelling to row

Each migration chapter SHALL hold one table keyed uniquely by old spelling, with columns old
spelling, target spelling, status, since and owning rule, where status is one of `gone`, `alias`,
`changed` or `deprecated`, and since is the release from which the status holds — for a language
whose changes land in editions as well as releases, the edition when the edition made the change —
in one form per standard, no later than the target. The command a reader runs to find old spellings
SHALL be generated from the `gone` and `alias` rows, and every `gone` row SHALL be verified absent
from the pinned release. Section 2.2 of `SKILL.md` SHALL be the table restricted to the rows whose
since is the target's, with columns old spelling, target spelling and owning rule, followed by one
line saying where the other rows are and naming the command, rendered from the table.

#### Scenario: One old spelling in two rows

- **WHEN** an old spelling appears in two rows
- **THEN** the run fails

#### Scenario: A since the target has not reached

- **WHEN** a Python 3.15 standard's row gives since `3.16`, or `3.15.0`
- **THEN** the run fails: since is a release's series, no later than the target's

#### Scenario: Section 2.2 kept by hand

- **WHEN** section 2.2 lists a row whose since is an older release, or leaves out one whose since is
  the target's
- **THEN** `fmt` renders it from the migration table, and the run fails until it has

#### Scenario: A gone row naming a live API

- **WHEN** a row marked `gone` names a symbol the pinned release still provides
- **THEN** the run fails

### Requirement: A delta's departures are one typed map

A delta standard SHALL list every departure from its anchor in one table of anchor rule, relation
(`overrides`, `tightens` or `extends`), delta rule, tier before and after, and reason. A delta rule
that departs SHALL say from which rule. A delta rule SHALL NOT restate an anchor rule, and SHALL NOT
change an anchor rule's tier without a row.

#### Scenario: A silent downgrade

- **WHEN** a delta rule states an anchor rule's content at a lower tier with no row
- **THEN** the run fails

### Requirement: The frontmatter and SKILL.md are bounded

The description SHALL follow one template shared by every standard — the use case first, the
artifacts that trigger it, the target version — with no rule count and no list of sources, in at
most 500 characters. `SKILL.md` SHALL be under 500 lines. No standard SHALL contain time-sensitive
or build-provenance phrasing.

#### Scenario: A description with a rule count

- **WHEN** a description says "a 262-rule library"
- **THEN** the run fails: the count changes with every revision and tells a reader nothing

#### Scenario: A statement dated by its writing

- **WHEN** a passage says "not yet implemented by every checker" or "measured on 0.17.0"
- **THEN** the run fails
