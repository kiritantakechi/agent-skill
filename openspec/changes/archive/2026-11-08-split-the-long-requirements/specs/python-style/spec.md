## REMOVED Requirements

### Requirement: Chapter coverage and a reference map

**Reason**: Its text was longer than 500 characters and stated more than one behaviour, and a
MODIFIED requirement cannot hand a scenario to another requirement, so it is split by removing it
and adding its parts.

**Migration**: Every clause and every scenario it held is kept, unchanged, in "The standard is split
into chapters that cover a minimum range of subjects"; "`SKILL.md` carries a reference map and tells
the reader to load one chapter".

### Requirement: The standard names the tools it requires and ships their configuration

**Reason**: Its text was longer than 500 characters and stated more than one behaviour, and a
MODIFIED requirement cannot hand a scenario to another requirement, so it is split by removing it
and adding its parts.

**Migration**: Every clause and every scenario it held is kept, unchanged, in "The standard names,
pins and configures the tools it requires"; "Each tool role is filled by exactly one named tool".

## ADDED Requirements

### Requirement: The standard is split into chapters that cover a minimum range of subjects

The standard SHALL be split into chapters, each owning one rule-ID family and opening with a
contents table listing every rule it owns. Coverage SHALL span at minimum: naming and layout;
typing; data modelling; errors and control flow; free-threading and concurrency; async; API design
and packaging; testing; performance; formatting and output; and a migration chapter carrying the
dead-API tables.

#### Scenario: A rule is filed in the wrong chapter

- **WHEN** a rule's ID prefix does not match the chapter it appears in
- **THEN** the standard is non-conforming

### Requirement: `SKILL.md` carries a reference map and tells the reader to load one chapter

`SKILL.md` SHALL carry a reference map from chapter to rule family to subject matter, and SHALL
instruct the reader to load one chapter rather than all of them.

#### Scenario: A reader needs one rule

- **WHEN** the reader has a rule ID
- **THEN** the reference map resolves the prefix to a chapter, and that chapter's contents table
  resolves the ID to a rule, without reading the chapter through

### Requirement: The standard names, pins and configures the tools it requires

The standard SHALL name the linter, the type checker, the package manager, and the build backend a
conforming project must run, SHALL ship the configuration for each as an asset, and SHALL state the
exact version each is pinned to. Where a required tool offers no stability guarantee, the standard
SHALL say so and SHALL give the procedure for moving the pin.

#### Scenario: A reader adopts the standard

- **WHEN** the reader follows the standard to set up a project
- **THEN** they are told which tools to run, with what configuration, at what version — rather than
  being shipped a configuration file whose use is left unstated

#### Scenario: A required tool offers no API stability

- **WHEN** a mandated tool declares that its behaviour may change between any two releases
- **THEN** the standard states that policy, pins the version exactly, and gives the bump procedure

### Requirement: Each tool role is filled by exactly one named tool

Each role SHALL be filled by exactly one named tool: the standard SHALL NOT offer alternatives for a
role, and SHALL NOT document a tool it does not require.

#### Scenario: A role admits more than one plausible tool

- **WHEN** more than one tool could fill a role the standard names
- **THEN** the standard names exactly one and prescribes it unconditionally, rather than presenting
  a choice it leaves the reader to resolve

#### Scenario: A project runs a second tool as well

- **WHEN** a project runs an additional checker beyond the mandated one
- **THEN** the standard neither forbids it nor promises the two agree, and does not weaken a rule to
  make them agree
