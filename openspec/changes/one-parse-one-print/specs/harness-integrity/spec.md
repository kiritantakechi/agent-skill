## ADDED Requirements

### Requirement: Negative controls are a bijection onto branches

Every place a check can report a finding SHALL be a named branch, declared with the one level it
reports at, and every finding SHALL carry the branch that produced it. Every branch that can report
a failure SHALL have exactly one negative control or exactly one recorded exemption with its
reason, never both. A control SHALL pass only when a failure from its own branch is reported; a
failure from any other branch SHALL NOT satisfy it, and a failure from another branch beside it
SHALL fail the control unless the control states why the defect reaches that branch too. Every
branch that reports that a check could not look SHALL be reached by making a tool the check
declares absent, or be listed with the reason no absence reaches it. A branch that only informs
SHALL fail no run, and is outside both. The `controls` check and the test suite SHALL run controls
through one runner.

#### Scenario: A control fires through a neighbouring branch

- **WHEN** a control's injected defect is reported only by a branch other than the one it names
- **THEN** the control fails, because the branch it exists to guard could be deleted and it would
  still pass

#### Scenario: A control fires a neighbour as well

- **WHEN** a control's own branch fires, and another branch of the same check fires beside it
- **THEN** the control fails, unless it names that branch with the reason its defect cannot help
  reaching it

#### Scenario: A branch is added

- **WHEN** a check gains a new failure site
- **THEN** the suite fails until that branch has a control or a stated exemption

#### Scenario: A branch reports that a check could not look

- **WHEN** a check gains a branch at `UNRUN`
- **THEN** the suite fails until making some declared tool absent reaches it, or it is listed with
  the reason none does

#### Scenario: A branch is removed

- **WHEN** a control or exemption names a branch no check declares
- **THEN** the suite fails, because an exemption standing over nothing is one nobody re-examined

### Requirement: Per-skill facts live only in profiles, and profiles are data

Everything the harness knows about one skill or one toolchain SHALL be declared in that skill's
profile or that toolchain's module, as data. Generic code SHALL NOT branch on a skill name, a
language name or a check name, and SHALL NOT hold a table keyed by any of them. Profiles SHALL have
no behaviour beyond what one shared engine interprets.

#### Scenario: A delta's anchor

- **WHEN** a check needs to know which standard a delta extends
- **THEN** it reads the profile's declared anchor, never a constant in the check and never a value
  derived from the content under check

#### Scenario: A skill name in generic code

- **WHEN** a module outside `profiles/` and `lang/` contains a skill or toolchain name as a literal
- **THEN** the test suite fails and names the module
