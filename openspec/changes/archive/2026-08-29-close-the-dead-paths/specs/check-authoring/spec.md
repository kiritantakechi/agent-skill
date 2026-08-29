## ADDED Requirements

### Requirement: A Check is runnable as printed

The command a Check shows the reader SHALL be accepted by the pinned tool when invoked the way the
reader would invoke it. A Check SHALL NOT depend for its validity on a flag the harness supplies and
the printed command does not.

The harness runs every pattern with multi-line matching enabled. A pattern the reader's invocation
rejects therefore compiles here, so the standard can ship a command that nobody outside this
repository can run while every check reports clean.

#### Scenario: A command is wrapped across lines in the source

- **WHEN** a Check's command is broken across a line in the markdown, so the quoted pattern contains
  a literal newline
- **THEN** it is reported, because the pinned tool rejects a raw newline in a pattern unless
  multi-line matching is requested, and the printed command does not request it

#### Scenario: A pattern is valid only under a harness flag

- **WHEN** a pattern depends on an option the harness adds and the Check does not print
- **THEN** the standard is non-conforming, whether or not the pattern currently matches anything here

#### Scenario: A harness flag changes what a pattern means

- **WHEN** an option the harness supplies makes a pattern match text the printed command could not
  match
- **THEN** the two are not the same search, and what the reader was told to run is not what the
  standard verified

## MODIFIED Requirements

### Requirement: A pattern that accuses ships with a positive control

Every pattern whose hits are reported as defects SHALL be accompanied by a fixture containing the
defect it exists to catch, and SHALL be shown to match that fixture. Where a rule's Check ships more
than one command pattern, each of them SHALL be shown to fire; one pattern matching SHALL NOT stand
as evidence for the rest. Not matching compliant code SHALL NOT by itself qualify a pattern to
accuse — a pattern that matches nothing anywhere satisfies that test perfectly.

A pattern whose hits are reported as candidates for a person to judge SHALL NOT require a fixture.
The reader is already being asked to look; the cost of a false candidate is a glance, and requiring
a fixture for every one of them was measured to demand 233 hand-written fixtures against 14 existing
defect examples — which would produce fixtures reverse-engineered from patterns, evidence that
proves the fixture rather than the pattern.

#### Scenario: A Check is promoted from candidates to accusations

- **WHEN** a Check that reported candidates is rewritten to report defects
- **THEN** a fixture exhibiting that rule's defect is added with it, and the pattern matching that
  fixture is asserted

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

### Requirement: A Check that narrows rather than decides says so explicitly

A Check whose search produces candidates rather than defects SHALL be marked as such, and the mark
SHALL carry the reason the search cannot decide. The absence of a command SHALL NOT be the only
signal that a Check does not decide.

The recorded reason SHALL name what decides. It SHALL NOT consist of a measurement that nothing
re-measures: a count of how many examples a pattern once hit is true of the corpus on the day it was
taken and is reported to a reader as though it were current.

#### Scenario: A search finds a shape whose defectiveness depends on context

- **WHEN** a pattern reliably finds a construct but something outside the match decides whether that
  construct is wrong
- **THEN** the rule records that, naming what decides, and hits are reported as candidates

#### Scenario: A recorded reason states a measurement

- **WHEN** the reason a Check does not decide is given as a number of examples it was observed to hit
- **THEN** that number is derived at the time it is reported, or omitted, because a figure carried in
  a string is a claim nothing checks and this one is printed to the reader

#### Scenario: A recorded reason no longer matches its rule

- **WHEN** a rule's Check is rewritten and the recorded reason quotes text the Check no longer
  contains
- **THEN** it is reported, because a suppression standing over a rule that changed is a suppression
  nobody re-examined
