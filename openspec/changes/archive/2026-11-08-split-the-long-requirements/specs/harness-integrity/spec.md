## REMOVED Requirements

### Requirement: A claim the repository makes about its own checks is verified against them

**Reason**: Its text was longer than 500 characters and stated more than one behaviour, and a
MODIFIED requirement cannot hand a scenario to another requirement, so it is split by removing it
and adding its parts.

**Migration**: Every clause and every scenario it held is kept, unchanged, in "A claim the
repository makes about its own checks is compared against the registry"; "A verification of a
field's presence reads the whole field".

### Requirement: A negative control exercises the mechanism it names

**Reason**: Its text was longer than 500 characters and stated more than one behaviour, and a
MODIFIED requirement cannot hand a scenario to another requirement, so it is split by removing it
and adding its parts.

**Migration**: Every clause and every scenario it held is kept, unchanged, in "A negative control
fails when the mechanism it is named for stops working"; "A control for one branch of a check
injects a defect only that branch reports".

### Requirement: Negative controls are a bijection onto branches

**Reason**: Its text was longer than 500 characters and stated more than one behaviour, and a
MODIFIED requirement cannot hand a scenario to another requirement, so it is split by removing it
and adding its parts.

**Migration**: Every clause and every scenario it held is kept, unchanged, in "Every branch that can
fail has one negative control or one recorded exemption"; "A control passes only through the branch
it names"; "A branch that reports that a check could not look is reached by an absent tool".

## ADDED Requirements

### Requirement: A claim the repository makes about its own checks is compared against the registry

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

### Requirement: A verification of a field's presence reads the whole field

Where the verification asks whether a field is present, it SHALL read the whole field. A parse that
truncates the field it is judging can find content in what is empty, or emptiness in what is not,
and either way it decides something other than the question it was asked.

#### Scenario: A documented field contains the delimiter of the format it is written in

- **WHEN** a recorded reason contains a character the surrounding format uses as a separator, escaped
  the way that format requires
- **THEN** the whole reason is read, because a check that stops at the escape judges a fragment and
  reports that a reason is present when only its first character is

### Requirement: A negative control fails when the mechanism it is named for stops working

A control SHALL fail when the mechanism it is named for stops working, and SHALL NOT be satisfied by
a different part of the same check reporting on the same injected defect.

A control is the evidence that a check can fail. A control that passes through a sibling branch
proves that the check can fail, which was never in doubt, and proves nothing about the branch it
claims to cover — so the branch can be deleted, made unreachable, or narrowed to nothing while the
control stays green.

#### Scenario: The named mechanism is made unreachable

- **WHEN** the code path a control covers stops executing — by a restructuring, a misplaced early
  return, or a narrowed condition
- **THEN** that control fails, rather than continuing to pass because the injected defect also trips
  something else

#### Scenario: A control is written or rewritten

- **WHEN** a control is added for a branch of an existing check
- **THEN** it is verified against the working code and against the code with that branch disabled,
  and it must fail in the second case before it is accepted

### Requirement: A control for one branch of a check injects a defect only that branch reports

Where a check reaches its verdict by more than one branch, the injected defect SHALL be one that
only the named branch can report.

#### Scenario: A check reaches its verdict by several branches

- **WHEN** a check reports on more than one property of its input, and a control is written for one
  of them
- **THEN** the injected defect is one the other branches do not report, so the control's passing is
  evidence about the branch it names

### Requirement: Every branch that can fail has one negative control or one recorded exemption

Every place a check can report a finding SHALL be a named branch, declared with the one level it
reports at, and every finding SHALL carry the branch that produced it. Every branch that can report
a failure SHALL have exactly one negative control or exactly one recorded exemption with its reason,
never both. The `controls` check and the test suite SHALL run controls through one runner.

#### Scenario: A branch is added

- **WHEN** a check gains a new failure site
- **THEN** the suite fails until that branch has a control or a stated exemption

#### Scenario: A branch is removed

- **WHEN** a control or exemption names a branch no check declares
- **THEN** the suite fails, because an exemption standing over nothing is one nobody re-examined

### Requirement: A control passes only through the branch it names

A control SHALL pass only when a failure from its own branch is reported; a failure from any other
branch SHALL NOT satisfy it, and a failure from another branch beside it SHALL fail the control
unless the control states why the defect reaches that branch too.

#### Scenario: A control fires through a neighbouring branch

- **WHEN** a control's injected defect is reported only by a branch other than the one it names
- **THEN** the control fails, because the branch it exists to guard could be deleted and it would
  still pass

#### Scenario: A control fires a neighbour as well

- **WHEN** a control's own branch fires, and another branch of the same check fires beside it
- **THEN** the control fails, unless it names that branch with the reason its defect cannot help
  reaching it

### Requirement: A branch that reports that a check could not look is reached by an absent tool

Every branch that reports that a check could not look SHALL be reached by making a tool the check
declares absent, or be listed with the reason no absence reaches it. A branch that only informs
SHALL fail no run, and is outside both the rule that a branch has one control or one exemption and
the rule that a could-not-look branch is reached by an absent tool.

#### Scenario: A branch reports that a check could not look

- **WHEN** a check gains a branch at `UNRUN`
- **THEN** the suite fails until making some declared tool absent reaches it, or it is listed with
  the reason none does
