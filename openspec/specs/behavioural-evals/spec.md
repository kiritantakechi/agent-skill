# behavioural-evals Specification

## Purpose
Tests what the standards do to a model rather than what their text says: whether a skill fires on
the work it is for and only on it, cites the rule it applies, and rewrites a spelling its target
removed. The suite is generated from the standards, so it cannot drift from them.

## Requirements

### Requirement: The eval suite is generated from the standards

The `claude plugin eval` suite under the plugin's eval directory SHALL be a function of the standards
and of each profile's eval selection. One command SHALL write it. The run SHALL fail when a file of
the suite on disk differs from its generation, or when the directory holds a case the generation
does not.

#### Scenario: A case edited by hand

- **WHEN** a case's prompt is edited by hand
- **THEN** the run fails, naming the case, until the command rewrites it

#### Scenario: A rule an eval was built from changes

- **WHEN** the BAD example a review case was built from is rewritten
- **THEN** the run fails until the suite is regenerated, so no case tests a rule as it once read

### Requirement: Every standard has a review, a migration and a negative case

For each standard, the suite SHALL hold a review case per selected rule, a migration case per
selected old spelling, and one negative case, each tagged with the standard's name and the case's
kind, so `--tag` selects them.

#### Scenario: A review case

- **WHEN** a selected rule's review case is generated
- **THEN** it asks for a review of the rule's verified BAD example, and is graded on whether the
  response cites the rule's ID

#### Scenario: A migration case

- **WHEN** a selected old spelling's migration case is generated
- **THEN** it asks what the target calls in its place, and is graded on the target spelling and
  the owning rule's ID

#### Scenario: A negative case

- **WHEN** python-style's negative case runs with the plugin loaded
- **THEN** its grader fails if python-style's skill is invoked, in both arms of the run

### Requirement: Grading is deterministic

Every grader SHALL be decided from the transcript without a model call. A grader that checks text
SHALL match a literal, escaped so that it means the same in JavaScript as written. Each case SHALL
have at least one grader that counts toward its score when the run compares the plugin with no
plugin. A grader that checks that the case's skill fired SHALL be reported but not scored.

#### Scenario: A judge grader

- **WHEN** a generated case would carry an `llm` or `baseline` grader
- **THEN** the run fails: no case calls a judge

#### Scenario: A target spelling with a metacharacter

- **WHEN** a migration row's target spelling is `Query::single()`
- **THEN** its grader matches the parentheses and the colons literally

### Requirement: A selection names only what a case can be built from

A profile's eval selection SHALL name rules and old spellings of its own standard. A selected rule
SHALL have a verified BAD example. A selected old spelling SHALL be a `gone` row of the target
release, and SHALL NOT be a shape.

#### Scenario: A rule with no BAD example

- **WHEN** a selection names a rule whose only example is GOOD
- **THEN** the run fails, naming the rule

#### Scenario: A shape selected

- **WHEN** a selection names `TextFont { line_height: … }`
- **THEN** the run fails: no literal grader can find a shape's target

### Requirement: Running the suite is the owner's decision

No check and no test SHALL run the suite: each run is a full model session on the owner's
credential. The README SHALL give the command that runs it, with a cost ceiling. The suite's results
directory SHALL be ignored by git.

#### Scenario: The full check

- **WHEN** `agent-skill check` runs, toolchains included
- **THEN** it validates the suite and starts no model session

#### Scenario: The owner runs it

- **WHEN** the owner runs the README's command
- **THEN** each case runs with and without the plugin, and the report gives each standard's score
  and its difference from the no-plugin baseline
