## REMOVED Requirements

### Requirement: Blocks are type-checked under a pinned strict configuration

**Reason**: Its text was longer than 500 characters and stated more than one behaviour, and a
MODIFIED requirement cannot hand a scenario to another requirement, so it is split by removing it
and adding its parts.

**Migration**: Every clause and every scenario it held is kept, unchanged, in "Every verified block
is type-checked under a pinned configuration"; "The type-checking configuration enables rules by
name, never by wildcard".

## ADDED Requirements

### Requirement: Every verified block is type-checked under a pinned configuration

Every verified block SHALL be type-checked, and the configuration SHALL be pinned in the repository
rather than left to the tool's defaults.

#### Scenario: A block fails type checking

- **WHEN** the type checker reports a diagnostic on an extracted block
- **THEN** the check reports a failure at that block's source line in the markdown

#### Scenario: The type checker's defaults would have passed it

- **WHEN** a diagnostic is only produced under the pinned configuration and not under the tool's
  defaults
- **THEN** it is still a failure — the pinned configuration is the standard, not the default

#### Scenario: Annotations are absent

- **WHEN** a block defines a function or method with no annotation on a parameter or return
- **THEN** it is reported, since the type checker alone does not require annotations and the lint
  configuration is what supplies that requirement

### Requirement: The type-checking configuration enables rules by name, never by wildcard

Because the chosen type checker ships no strict preset, the configuration SHALL enable the opt-in
soundness rules by naming each one, and SHALL set the analysis version to the target Python version.
It SHALL NOT raise the severity of the whole rule set with a single wildcard: a checker that offers
no stability guarantee can add rules in any release, and a wildcard silently enrols them.

#### Scenario: A tool release adds a rule

- **WHEN** a new version of the pinned checker introduces a rule the configuration never named
- **THEN** the rule is not silently enforced; enabling it is a deliberate edit to the configuration

#### Scenario: Raising a severity would change nothing

- **WHEN** a severity level below error already causes the tool to exit non-zero
- **THEN** promoting those rules is not treated as a strictness increase, because it changes only
  the printed label
