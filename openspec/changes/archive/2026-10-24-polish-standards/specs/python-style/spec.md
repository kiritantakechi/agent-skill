# Spec Delta

## MODIFIED Requirements

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
