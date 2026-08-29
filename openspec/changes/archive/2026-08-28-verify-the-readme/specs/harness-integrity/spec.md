## ADDED Requirements

### Requirement: A claim the repository makes about its own checks is verified against them

Where the repository states in prose which checks exist, what they cover, or that something holds of
every check, that statement SHALL be compared against the registry and SHALL fail when the two
disagree. A claim written for a reader SHALL NOT be exempt from verification because its audience is
a person.

#### Scenario: A check ships without being documented

- **WHEN** a check is registered and the documented list does not name it
- **THEN** the run fails, because the file that promises a reason for every check is missing one

#### Scenario: Documentation names a check that no longer exists

- **WHEN** the documented list names something the registry does not
- **THEN** the run fails, the same way an exemption outliving its check does

#### Scenario: A universal claim is made about checks

- **WHEN** prose states that something holds of every check
- **THEN** what it quantifies over is derived from the registry, so the claim cannot become false by
  a check being added

#### Scenario: A documented scope is narrower than the claim

- **WHEN** a check covers some checks and not others, and the prose says it covers all of them
- **THEN** the run fails, and the number or the exemptions it names come from the registry rather
  than from what someone typed

#### Scenario: Prose drifts for reasons that are not defects

- **WHEN** wording, column order, or style changes without changing which checks are named or
  whether each carries a note
- **THEN** nothing fails, because the claim has not changed
