## ADDED Requirements

### Requirement: Every check has one signature, and selection filters findings

Every check SHALL be a function from the whole tree to findings. A check about one skill SHALL be
lifted to that signature by one shared combinator. Selecting skills on the command line SHALL run
every check over the whole tree and then keep the findings located in the selected skills or in no
skill; it SHALL NOT change what any check reads. Naming a check or a skill that does not exist SHALL
be an error, never an empty selection.

#### Scenario: A cross-skill check under a selection

- **WHEN** `check --skill bevy-style` runs
- **THEN** `crossref` reads `rust-style` exactly as in an unselected run, and its findings in
  `bevy-style` are reported

#### Scenario: A misspelt check name

- **WHEN** `check --only no-such-check` runs
- **THEN** it exits with a usage error listing the valid names, and never prints that all checks
  passed

### Requirement: Every toolchain runs through one driver

Each toolchain SHALL be an extraction and its inverse, such that restoring an extraction reproduces
every block body exactly, plus the steps and mutants for a unit. One driver SHALL run every step of
every toolchain with one policy: a step that fails or times out is a failure naming the step and the
tool's first error line; a mutant that times out is inconclusive and never counted as killed; a
missing tool or an empty extraction is reported as not run. Formatting an example SHALL be the
composition of extraction, the toolchain's formatter and restoration, for every toolchain.

#### Scenario: A formatter times out

- **WHEN** a toolchain's format step exceeds its timeout
- **THEN** it is reported as a failure, never as clean

#### Scenario: Extraction round trip

- **WHEN** any skill's blocks are extracted and immediately restored
- **THEN** every block body is byte-identical to the source

#### Scenario: A new toolchain

- **WHEN** a toolchain is added with an extraction, its inverse and its steps
- **THEN** verification, mutation and formatting work for it with no further code
