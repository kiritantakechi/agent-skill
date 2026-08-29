## Purpose

The discipline the harness applies to itself: that suppressing one of its own checks justifies
itself the way suppressing a rule does, and that a list of what must be verified is derived from the
thing it verifies rather than maintained beside it.

## ADDED Requirements

### Requirement: A check exempted from a guarantee records why

Where a check is excluded from a property the harness otherwise requires of every check, the
exclusion SHALL name the check and state the reason. An exclusion SHALL NOT be expressed as a bare
list of names. An exclusion naming a check that no longer exists SHALL be reported.

#### Scenario: A check has no negative control

- **WHEN** a check is not covered by any control that proves it can fail
- **THEN** the exclusion records why that check is different, so a reader can tell whether the reason
  still holds

#### Scenario: An exclusion outlives its check

- **WHEN** a check named by an exclusion is renamed or removed
- **THEN** the exclusion is reported, because an exemption standing over nothing is an exemption
  nobody re-examined

#### Scenario: A new check is added

- **WHEN** a check is added and given no control
- **THEN** it fails the guarantee rather than being absorbed by an existing exclusion

### Requirement: What must be verified is derived from what is being verified

A list of subjects a guarantee applies to SHALL be computed from those subjects rather than written
alongside them. A subject that acquires the property the guarantee is about SHALL be covered by that
guarantee without anyone editing a list.

#### Scenario: A check gains a dependency on an external tool

- **WHEN** a check begins to require a tool it did not require before
- **THEN** the guarantee that a missing tool withholds the pass covers it immediately, without a
  separate list being updated

#### Scenario: A derivation produces nothing

- **WHEN** the computed set of subjects is empty, or smaller than the set known to qualify
- **THEN** that is a failure, because a guarantee that applies to nothing passes trivially and reads
  exactly like one that applies to everything

#### Scenario: A category of check needs different treatment

- **WHEN** a guarantee must treat some checks differently — those that read one skill against
  another, for instance
- **THEN** the distinction is declared by the check itself rather than by a set of names maintained
  elsewhere

### Requirement: Machinery that nothing reaches is removed, not carried

Code that nothing calls or reads SHALL be deleted rather than moved. A restructuring SHALL NOT
preserve a member solely because it was there before.

#### Scenario: A refactor moves a module's contents

- **WHEN** code is split or relocated
- **THEN** what nothing reaches is removed as part of the move, because a restructuring that
  relocates without examining has changed where the code is and not what it is

#### Scenario: A member is computed and never read

- **WHEN** a value is assigned and no caller reads it
- **THEN** it is deleted, and the work that produced it with it
