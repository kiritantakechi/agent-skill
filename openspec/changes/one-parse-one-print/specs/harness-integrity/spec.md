## ADDED Requirements

### Requirement: Negative controls are a bijection onto branches

Every place a check can report a failure SHALL be a named branch, and every finding SHALL carry the
branch that produced it. Every branch SHALL have exactly one negative control or exactly one
recorded exemption with its reason, never both. A control SHALL pass only when a failure from its
own branch is reported; a failure from any other branch SHALL NOT satisfy it. The `controls` check
and the test suite SHALL run controls through one runner.

#### Scenario: A control fires through a neighbouring branch

- **WHEN** a control's injected defect is reported only by a branch other than the one it names
- **THEN** the control fails, because the branch it exists to guard could be deleted and it would
  still pass

#### Scenario: A branch is added

- **WHEN** a check gains a new failure site
- **THEN** the suite fails until that branch has a control or a stated exemption

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
