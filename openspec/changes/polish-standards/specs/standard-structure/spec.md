# Spec Delta

## ADDED Requirements

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
