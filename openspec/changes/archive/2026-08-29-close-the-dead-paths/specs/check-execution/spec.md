## ADDED Requirements

### Requirement: A positive control is prepared the way the corpus is

A fixture a pattern is asserted to match SHALL be subjected to the same preparation as the corpus the
same pattern is run over. Where the corpus is transformed before matching — comments removed, a line
rewritten, a marker blanked — the fixture SHALL be transformed identically before the assertion is
made.

The two halves answer one question between them: the corpus proves a pattern does not fire on
compliant code, the fixture proves it fires on the defect. If they are prepared differently, a
pattern can pass both while being unable to fire on anything the corpus could contain.

#### Scenario: The corpus is stripped of comments and the fixture is not

- **WHEN** a pattern is run against the corpus with comments removed, and asserted against a fixture
  written verbatim
- **THEN** a fixture whose match depends on comment text certifies a pattern the corpus path could
  never fire on, so the fixture is stripped the same way before the assertion

#### Scenario: A pattern declares it searches the unstripped text

- **WHEN** a pattern is one that searches the raw text rather than the transformed text
- **THEN** its fixture is left untransformed too, because the rule is that the two agree, not that
  either is always transformed

## MODIFIED Requirements

### Requirement: A pattern that cannot match is a failure, never a pass

Execution SHALL distinguish *a pattern that ran and found nothing* from *a pattern that could not
run or could not match*. A pattern the engine rejects, a pattern that times out, and a pattern whose
tool is absent SHALL each be reported as a failure. Silence SHALL NOT be reported as cleanliness.

The distinction SHALL hold at every place a search result is consumed. A search that could not answer
and a search that answered *nothing* are both falsy, so a caller testing the result for emptiness
collapses them; every consumer SHALL test for the absence of an answer explicitly.

#### Scenario: The tool rejects a pattern

- **WHEN** the executing tool exits with its rejected-pattern status
- **THEN** the run reports a failure naming the rule and the pattern, rather than recording zero hits

#### Scenario: The tool is not installed

- **WHEN** the tool that executes patterns is absent from the environment
- **THEN** the run reports that nothing executed, rather than reporting every check clean

#### Scenario: A second check consumes the same search

- **WHEN** more than one check runs patterns through the same search, and one of them tests the
  result for emptiness
- **THEN** that check reports the no-answer case as a failure too, because the guarantee belongs to
  the search's contract and not to whichever caller remembered it

#### Scenario: A pattern is syntactically valid but inert

- **WHEN** a pattern parses successfully yet cannot match any input — an escape read as a literal
  where alternation was meant, for example
- **THEN** nothing in the report distinguishes it from a clean check, which is why the dialect is
  singular and why translation is guarded by the requirement below

### Requirement: The executing tool is named, pinned, and required

Every tool the harness depends on to decide whether a check passes SHALL be named in the standard,
pinned to an exact version, and treated as a required dependency rather than an assumed one. Its
absence SHALL be reported by the same mechanism that reports any other missing required tool.

The declared pin SHALL be verified against reality in two directions. The version that actually
executes SHALL be compared against the pin, and a mismatch SHALL be reported — a statement that the
standard was verified against a version is false if the harness ran a different one. The pin SHALL
also be compared against the newest release of that tool, and a superseded pin SHALL be reported, so
that moving a pin is a reviewed event rather than a note nobody reads.

Neither comparison SHALL answer for input it did not understand. A pin whose source cannot be read
and a version that cannot be parsed SHALL each be reported, and SHALL NOT be resolved to a value that
happens to compare as agreement.

#### Scenario: The harness runs where the tool is missing

- **WHEN** verification runs in an environment without a required tool
- **THEN** it reports the tool as unavailable and the affected checks as not run

#### Scenario: A reader adopts a Check

- **WHEN** a reader copies a Check to run against their own code
- **THEN** the standard has told them which tool to install and which version it was verified
  against

#### Scenario: The running version is not the pinned version

- **WHEN** the tool that executes is a different version from the one the pin declares
- **THEN** it is reported as a failure, whichever direction the difference runs, because every claim
  the standard makes about what was verified rests on the two agreeing

#### Scenario: The pin cannot be found

- **WHEN** a tool the harness requires has no pin to compare against
- **THEN** that is itself the finding; an unfindable pin SHALL NOT be read as agreement

#### Scenario: The declaration holding the pins cannot be read

- **WHEN** the harness runs where the file the pins are declared in is not present — installed as a
  distribution rather than run from its source tree
- **THEN** it reports that the pins could not be consulted, by the same mechanism as an unfindable
  pin, rather than raising

#### Scenario: A version cannot be parsed

- **WHEN** a version reported by a tool or an index does not fit the form the comparison expects
- **THEN** it is reported as not compared, because a value that fails to parse and sorts below every
  real version turns "could not tell" into "the pin is current"

#### Scenario: A newer release of a pinned tool exists

- **WHEN** the tool's newest released version is higher than the pinned one
- **THEN** it is reported, naming the available version and what moving the pin requires

#### Scenario: The release list cannot be consulted

- **WHEN** the newest released version cannot be determined — no network, or the index does not
  answer
- **THEN** it is reported as not run rather than as up to date

### Requirement: A pattern carries no syntax from a dialect it will not be read in

A pattern SHALL NOT contain an escape whose meaning is inverted between the dialect it is written in
and the dialect that executes it, and SHALL NOT contain a character the executing tool rejects under
the invocation the standard prints. This SHALL be decided by inspecting the pattern, without
executing it and without reference to any corpus, so that a pattern which has silently lost the
ability to match is caught by its text rather than by its results.

#### Scenario: A pattern keeps an escape from the previous dialect

- **WHEN** a pattern to be executed as an extended regular expression contains `\|`, `\(`, or `\{`,
  which are alternation and grouping in basic regular expressions and literal characters here
- **THEN** the standard is non-conforming, whether or not the pattern currently matches anything

#### Scenario: A pattern contains a raw newline

- **WHEN** a pattern carries a literal newline, because the command it was written in was wrapped
  across a line of the source
- **THEN** the standard is non-conforming: the printed invocation is rejected by the tool, and the
  harness's own invocation accepts it while the alternative that follows the newline can never match

#### Scenario: The pattern matches nothing either way

- **WHEN** a pattern's hit set is empty both before and after a rewrite
- **THEN** emptiness is not evidence the rewrite was faithful, and conformance is decided by the
  pattern's syntax rather than by its results
