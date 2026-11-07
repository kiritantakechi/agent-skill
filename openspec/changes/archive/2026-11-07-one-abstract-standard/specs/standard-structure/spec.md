## MODIFIED Requirements

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

## ADDED Requirements

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
