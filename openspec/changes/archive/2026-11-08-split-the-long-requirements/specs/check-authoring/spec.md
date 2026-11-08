## REMOVED Requirements

### Requirement: A pattern that accuses ships with a positive control

**Reason**: Its text was longer than 500 characters and stated more than one behaviour, and a
MODIFIED requirement cannot hand a scenario to another requirement, so it is split by removing it
and adding its parts.

**Migration**: Every clause and every scenario it held is kept, unchanged, in "An accusing pattern
is shown to match a fixture of its defect"; "A pattern that reports candidates needs no fixture".

## ADDED Requirements

### Requirement: An accusing pattern is shown to match a fixture of its defect

Every pattern whose hits are reported as defects SHALL be accompanied by a fixture containing the
defect it exists to catch, and SHALL be shown to match that fixture. Where a rule's Check ships more
than one command pattern, each of them SHALL be shown to fire; one pattern matching SHALL NOT stand
as evidence for the rest. Not matching compliant code SHALL NOT by itself qualify a pattern to
accuse — a pattern that matches nothing anywhere satisfies that test perfectly.

#### Scenario: A rule's Check ships several command patterns

- **WHEN** one Check carries more than one pattern that accuses, and a fixture matches one of them
- **THEN** the others are not covered by it: each is shown to fire against a fixture of its own, or
  is reported as unproven

#### Scenario: A pattern matches nothing anywhere

- **WHEN** a pattern matches neither the compliant corpus nor its own positive control
- **THEN** it is reported as unable to fire, rather than passing on an empty result

#### Scenario: A positive control stops being matched

- **WHEN** a later edit to a pattern makes it stop matching its own fixture
- **THEN** that is a failure, because the pattern has lost the ability to catch what it was written
  for while continuing to report clean

### Requirement: A pattern that reports candidates needs no fixture

A pattern whose hits are reported as candidates for a person to judge SHALL NOT require a fixture.
The reader is already being asked to look; the cost of a false candidate is a glance, and requiring
a fixture for every one of them was measured to demand 233 hand-written fixtures against 14 existing
defect examples — which would produce fixtures reverse-engineered from patterns, evidence that
proves the fixture rather than the pattern.

#### Scenario: A Check is promoted from candidates to accusations

- **WHEN** a Check that reported candidates is rewritten to report defects
- **THEN** a fixture exhibiting that rule's defect is added with it, and the pattern matching that
  fixture is asserted
