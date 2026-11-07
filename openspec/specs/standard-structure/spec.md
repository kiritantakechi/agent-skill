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
The same concept SHALL carry the same code in every standard.

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
change, the standard's `references/renames.md` SHALL state the range each family ran before the
revision, and SHALL carry a table mapping every old ID that changed to its new ID, or to the
lint-table row or removal that replaced it. An old ID in range that the table does not list is
unchanged. `migration.md` SHALL name `renames.md` once; nothing on the reading path in SKILL.md
SHALL name it.

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

#### Scenario: A reader consults the migration chapter

- **WHEN** an agent loads `migration.md` to translate an old spelling
- **THEN** it does not load the rename history, which lives in `renames.md`

### Requirement: A renumbering is one operation that preserves every citation

Removing, merging, demoting, moving and renumbering rules SHALL be one operation, `revise`, taking a
partial map from old ID to what it becomes and closing it by dense renumbering. A move SHALL take a
rule to another chapter of the same standard, at a stated place among that chapter's rules, and give
it the target family's code. It SHALL rewrite every citation in the repository through the document
model and write the rename table. It SHALL fail, leaving the tree unchanged, unless every citation
refers to the same rule after the rewrite as before, compared by identity rather than by ID; unless
every ID that existed before the revision is either still the same rule or has a row; and if any
cited ID that named no rule before the revision would name one after it.

The operation SHALL satisfy, and the test suite SHALL check: applying a pure renumbering and then its
inverse restores every file byte for byte; applying a move and then the move back to the rule's old
place restores every file byte for byte; applying an empty plan writes nothing and reports nothing.

#### Scenario: Old and new IDs overlap

- **WHEN** an old ID is reused as the new ID of a different rule, as dense numbering makes routine
- **THEN** citations are still rewritten correctly, because the rewrite is one permutation applied
  to every ID token at once and never a chain of replacements

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

#### Scenario: Renumbering and back

- **WHEN** a chapter is renamed and renumbered, and the inverse renaming is applied
- **THEN** every file is byte-identical to the original

#### Scenario: Moving a rule and back

- **WHEN** RS-CLI-07 is moved into `output.md` after RS-OUT-03, and the result is moved back into
  `cli.md` after the rule that preceded it
- **THEN** every file is byte-identical to the original, the rename table included

#### Scenario: A move into a chapter the standard does not have

- **WHEN** a plan moves a zig-style rule into `documentation.md`, which zig-style does not yet ship
- **THEN** the chapter is created in the chapter template, with its contents and its `Scope:` left
  for the author to write, and the run fails until they are written

#### Scenario: Nothing to do

- **WHEN** the plan is empty and the numbering is already dense
- **THEN** no file is written and nothing is reported as written

#### Scenario: A citation is edited in by hand afterwards

- **WHEN** someone later cites an old ID that, under dense numbering, is now a different rule's ID
- **THEN** no check can tell it from a correct citation. This is why the rewrite is never done by
  hand, and the requirement says so rather than implying the run would catch it

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
behaves differently, what no longer compiles, and what the target gained. The first SHALL be the
migration table's `changed` rows whose since is the target's, and the second its `gone` rows whose
since is the target's, each rendered from the table, as the migration requirement states; so the
statuses and the first two subsections are one partition, and a row that still compiles and means
what it did is in neither. Every item of the third SHALL name the rule that owns it.

#### Scenario: An item with no owner

- **WHEN** a section 2 item states a change no rule or migration row holds
- **THEN** the run fails, because section 2 indexes the chapters and holds nothing of its own

#### Scenario: A rejected spelling under what still compiles

- **WHEN** section 2.1 lists a row whose status is `gone`, or section 2.2 one whose status is
  `changed`, `alias` or `deprecated`
- **THEN** `fmt` renders each from the migration table, and the run fails until it has

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
spelling, target spelling, status, since and owning rule, where status is what the target does with
the old spelling: `gone`, it rejects it (a compile, import or attribute error); `changed`, it
accepts it and it means something else; `alias` or `deprecated`, it accepts it and it means what it
did. Since is the release from which the status holds — for a language whose changes land in
editions as well as releases, the edition when the edition made the change — in one form per
standard, no later than the target. An old spelling with `…` in it is a shape, code left out where
the `…` stands. The command a reader runs to find old spellings SHALL be generated from the `gone`
and `alias` rows that are no shape, and every `gone` row the toolchain can look up or compile SHALL
be verified rejected by the pinned release. Sections 2.1 and 2.2 of `SKILL.md` SHALL be the table
restricted to the `changed` and to the `gone` rows whose since is the target's, each with columns
old spelling, target spelling and owning rule, followed by one line saying where that status's
other rows are and how a reader finds them, rendered from the table.

#### Scenario: One old spelling in two rows

- **WHEN** an old spelling appears in two rows
- **THEN** the run fails

#### Scenario: A since the target has not reached

- **WHEN** a Python 3.15 standard's row gives since `3.16`, or `3.15.0`
- **THEN** the run fails: since is a release's series, no later than the target's

#### Scenario: Section 2.2 kept by hand

- **WHEN** section 2.2 lists a row whose since is an older release, or leaves out a `gone` row whose
  since is the target's
- **THEN** `fmt` renders it from the migration table, and the run fails until it has

#### Scenario: A shape in the command

- **WHEN** a `gone` row's old spelling is `TextFont { line_height: … }`
- **THEN** the generated command has no pattern for it, and its owning rule's Check finds it

#### Scenario: A gone row naming a live API

- **WHEN** a row marked `gone` names a symbol the pinned release still provides, or a spelling the
  target edition still compiles
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

### Requirement: A concept lives in the same chapter in every standard

A rule that realises an entry of the abstract standard SHALL stand in the chapter whose vocabulary
word holds that entry in the abstract standard. Every base standard SHALL ship each chapter in which
it realises an entry.

#### Scenario: A realisation in another chapter

- **WHEN** zig-style's rule realising a documentation entry stands in `naming.md`
- **THEN** the run fails, naming the rule and `documentation.md`; `revise` moves it

#### Scenario: A concern split across two chapters

- **WHEN** python-style keeps an output entry's realisation in `output.md` and rust-style keeps it
  in `cli.md`
- **THEN** the run fails for rust-style; one concept has one address in every standard

### Requirement: A chapter that realises no concept is owned by a domain feature

A chapter of a standard that holds no realisation of any entry, and whose word names no chapter of
the abstract standard, SHALL be declared in the standard's profile with the domain feature that owns
it. A declared domain chapter SHALL exist, and SHALL realise no entry.

#### Scenario: An undeclared chapter

- **WHEN** rust-style ships `macros.md`, realising no entry, and its profile declares no domain
  feature for it
- **THEN** the run fails, naming the chapter

#### Scenario: A domain chapter that realises a concept

- **WHEN** a rule in a declared domain chapter realises an entry
- **THEN** the run fails: the entry's chapter is its address, and the rule moves there

### Requirement: A shipped CI asset pins every action to a commit

Every `uses:` in a shipped workflow SHALL name its action by a full 40-hexadecimal commit, followed
by a comment giving the release that commit is, or the branch it was taken from for an action that
publishes no releases. A tag, a branch or a short hash SHALL fail. A toolchain an action selects by
its ref SHALL be passed as that action's input instead.

#### Scenario: An action by tag

- **WHEN** an asset says `uses: actions/checkout@v7`
- **THEN** the run fails: a tag can be moved after review, and the commit it names with it

#### Scenario: A toolchain chosen by branch

- **WHEN** an asset says `uses: dtolnay/rust-toolchain@1.99.1`
- **THEN** the run fails; the step names the action's commit and passes `toolchain: 1.99.1`

#### Scenario: A pin with no version

- **WHEN** a `uses:` names a full commit with no version comment
- **THEN** the run fails: a reader cannot tell which release a bump moves from
