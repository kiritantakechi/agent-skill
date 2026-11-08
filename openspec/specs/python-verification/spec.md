# python-verification Specification

## Purpose
Lets the skill checker verify a Python standard the way it already verifies the Rust and Zig ones:
every example claiming to be verified is really run, type-checked, and linted, and every check that
could not be run is reported as such rather than counted as a pass.

## Requirements

### Requirement: A verified block is executed on the pinned interpreter

Every fenced Python example marked as verified SHALL be extracted and run on the exact interpreter
the standard names — a free-threaded CPython 3.15 build — and a block that raises SHALL be reported
as a failure located at its source line in the markdown. A block that ships tests SHALL have those
tests run.

#### Scenario: A verified block raises

- **WHEN** an extracted block terminates with a non-zero status
- **THEN** the check reports a failure naming the chapter, the source line, and the owning rule ID

#### Scenario: A verified block ships a test

- **WHEN** the block defines tests
- **THEN** those tests are executed, and a failing test is reported as a failure

#### Scenario: The pinned interpreter is not installed

- **WHEN** the free-threaded 3.15 build is absent from the machine
- **THEN** the check reports that it could not run, and does not report success for any block

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
The configuration SHALL NOT raise the severity of the whole rule set with a single wildcard: a
checker that offers no stability guarantee can add rules in any release, and a wildcard silently
enrols them.

#### Scenario: A tool release adds a rule

- **WHEN** a new version of the pinned checker introduces a rule the configuration never named
- **THEN** the rule is not silently enforced; enabling it is a deliberate edit to the configuration

#### Scenario: Raising a severity would change nothing

- **WHEN** a severity level below error already causes the tool to exit non-zero
- **THEN** promoting those rules is not treated as a strictness increase, because it changes only
  the printed label

### Requirement: Blocks are linted against the shipped rule table

Every verified block SHALL be linted with the configuration the standard ships as an asset, minus a
named allowlist of rules about the shape of a project that a fenced snippet cannot have, each entry
with its reason. Nothing else SHALL differ between the asset and the configuration examples are
linted with, and a divergence SHALL be reported.

#### Scenario: The asset and the verified selection diverge

- **WHEN** the shipped lint configuration enables a rule the verification does not use, other than
  an allowlisted one, or sets a severity the standard's rules do not require
- **THEN** the check reports a failure naming the rule and both settings

#### Scenario: A lint rule fires on an example

- **WHEN** an enabled lint rule reports a diagnostic on an extracted block
- **THEN** the check reports a failure at that block's source line, unless the block is evidence
  rather than advice

#### Scenario: An allowlist entry without a reason

- **WHEN** the allowlist names a rule and gives no reason a snippet cannot satisfy it
- **THEN** the run fails, as any exemption without a reason does

### Requirement: A check that cannot be selected is not a check

Verification SHALL reject a rule that cites a check its tool refuses to select — one withdrawn from
or never present in that tool's catalogue — rather than allowing the citation to stand as
decoration. This SHALL apply to every mandated tool, not only the linter: a name in a shipped
configuration that the tool does not recognise is the same defect wherever it appears.

#### Scenario: A rule cites a withdrawn check

- **WHEN** a rule names a check the tool no longer offers
- **THEN** the citation is reported as a failure, naming the rule and the withdrawn check

#### Scenario: A withdrawn check is present in the shipped configuration

- **WHEN** the shipped configuration would select a withdrawn check
- **THEN** it is reported, because selecting one is a hard failure of the tool rather than a warning

#### Scenario: A tool release renames a check the configuration names

- **WHEN** an upgrade renames or drops a check that the shipped configuration enables by name
- **THEN** it is reported against that tool's own catalogue, so the divergence surfaces as a failing
  check rather than as a setting that silently stopped applying

### Requirement: Formatting is settled by a command, not by a reported diff

The build SHALL offer a command that reformats every example in place using the same extraction the
check uses, so a formatting finding can be resolved without the author reconstructing the
formatter's decision by hand.

#### Scenario: An example is not formatted as the formatter would have it

- **WHEN** the formatting check reports a difference
- **THEN** running the reformat command resolves it, and re-running the check reports no difference

#### Scenario: Extraction context changes formatting

- **WHEN** the extracted form of a block differs from the markdown's indentation or nesting
- **THEN** the reformat command applies the same extraction as the check, so the two cannot
  disagree

### Requirement: The standard's own checks are run against its own examples

Every `**Check:**` that ships a runnable command SHALL be executed over the standard's own verified
examples, and a hit SHALL be reported. Examples that are evidence rather than advice — the `BAD`
side of a rule, and material quoted from elsewhere — SHALL be excluded from that corpus.

#### Scenario: A rule's own check fires on the standard's examples

- **WHEN** a shipped check matches a line in a verified, advisory example
- **THEN** the check reports a failure, naming the rule whose check fired and the line it fired on

#### Scenario: A rule illustrates its own violation

- **WHEN** the matching line is inside a block marked as the `BAD` side of a rule or as quoted
  material
- **THEN** it is not reported, because the block is demonstrating the rule rather than breaking it

#### Scenario: A check cannot decide on its own

- **WHEN** a check's hits are candidates rather than defects — the deciding context is not visible
  in a standalone block
- **THEN** it is recorded as such against a quoted fragment of that rule's own check text, and a
  fragment that no longer appears in the rule is itself reported

### Requirement: Shipped assets are executed, not only parsed

Verification SHALL exercise each shipped asset with the tool that consumes it, rather than only
parsing it or comparing it against the rules that own it. An asset describing a buildable project
SHALL be built, and the resulting artefact SHALL be inspected for whatever the rules claim it
contains.

#### Scenario: The project template is verified

- **WHEN** the shipped project metadata is verified
- **THEN** a package is built from it with the pinned build backend, and a failing build is a
  failure of the standard

#### Scenario: The template parses but does not build

- **WHEN** an asset is valid TOML and agrees with every rule that owns it, yet the backend cannot
  build the project it describes
- **THEN** verification reports a failure, because agreement with the rules is not evidence that the
  file works

#### Scenario: A rule claims the build produces something

- **WHEN** a rule states that the built artefact contains a given file
- **THEN** verification unpacks the artefact and asserts that file is present, rather than trusting
  the backend's documented behaviour

### Requirement: A tool that cannot run is reported, never assumed to pass

No check SHALL report success for work it did not do. An absent interpreter, an absent type checker,
an absent linter, or a tool invoked in a way that cannot produce a failure SHALL be reported
distinctly from a clean run.

#### Scenario: A tool is missing from the machine

- **WHEN** a required tool is not installed
- **THEN** the run reports which check could not be performed, and the overall result is not a clean
  pass

#### Scenario: A tool exits zero on findings

- **WHEN** the tool's exit status is zero but its output contains diagnostics
- **THEN** the check reads the diagnostics rather than the exit status

### Requirement: Tool output is read at the severity the tool assigns

Where a tool offers several output formats, verification SHALL use one that preserves the severity
the tool assigned to each diagnostic, and SHALL NOT use a format that collapses distinct severities
into one. Where a tool can identify a diagnostic by a stable code or by a human-readable name,
verification SHALL read the stable code.

#### Scenario: An output format flattens severities

- **WHEN** a format reports a warning-level and an error-level diagnostic identically
- **THEN** it is not used for verification, because the rules distinguish the two

#### Scenario: A tool changes what it prints by default

- **WHEN** a tool release changes whether it identifies diagnostics by code or by name
- **THEN** verification still reads codes, because the configuration pins that choice rather than
  relying on the default

### Requirement: Every new check carries a negative control

Each check added for Python SHALL have a control that injects the defect it owns into a copy of the
tree and asserts that the check reports a failure. A control that stops firing SHALL itself be a
failure.

#### Scenario: A check is weakened

- **WHEN** a change makes a check unable to detect the defect it owns
- **THEN** that check's control fails

#### Scenario: A control's fixture drifts

- **WHEN** the text a control injects its defect into no longer appears in the skill
- **THEN** the control fails rather than silently injecting nothing
