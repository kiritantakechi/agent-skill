## MODIFIED Requirements

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

Removing, merging, demoting and renumbering rules SHALL be one operation, `revise`, taking a partial
map from old ID to what it becomes and closing it by dense renumbering. It SHALL rewrite every
citation in the repository through the document model and write the rename table. It SHALL fail,
leaving the tree unchanged, unless every citation refers to the same rule after the rewrite as
before, compared by identity rather than by ID; unless every ID that existed before the revision is
either still the same rule or has a row; and if any cited ID that named no rule before the revision
would name one after it.

The operation SHALL satisfy, and the test suite SHALL check: applying a pure renumbering and then its
inverse restores every file byte for byte; applying an empty plan writes nothing and reports
nothing.

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

#### Scenario: Nothing to do

- **WHEN** the plan is empty and the numbering is already dense
- **THEN** no file is written and nothing is reported as written

#### Scenario: A citation is edited in by hand afterwards

- **WHEN** someone later cites an old ID that, under dense numbering, is now a different rule's ID
- **THEN** no check can tell it from a correct citation. This is why the rewrite is never done by
  hand, and the requirement says so rather than implying the run would catch it
