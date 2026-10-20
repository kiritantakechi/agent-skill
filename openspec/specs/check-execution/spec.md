# check-execution Specification

## Purpose
How a rule's `**Check:**` is expressed and executed: the one regex dialect every skill writes in,
the one tool that runs it, and the guarantee that rewriting a pattern preserves the exact set of
lines it finds.

## Requirements

### Requirement: One dialect across every skill

Every executable pattern a rule ships SHALL be written in a single regex dialect, and that dialect
SHALL be the one the named tool applies by default. A rule SHALL NOT select a dialect by the
presence or absence of a flag, and the standard SHALL NOT contain two patterns whose meaning depends
on which spelling of the same tool ran them.

#### Scenario: A rule ships an executable pattern

- **WHEN** a rule's Check names a command a reader is expected to run
- **THEN** the pattern is written in the tool's default dialect, and the same text pasted into the
  reader's shell means what the standard says it means

#### Scenario: A pattern uses a construct the dialect does not define

- **WHEN** a pattern relies on syntax outside the single dialect — a backreference, a lookaround, or
  an escape whose meaning is inverted between grammars
- **THEN** the standard is non-conforming, because the pattern's behaviour depends on which engine
  reads it

#### Scenario: Two skills express the same predicate

- **WHEN** two skills ship a check for the same shape of defect
- **THEN** both are written in the same dialect, so a reader who learns one can read the other

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

### Requirement: A dialect translation is performed mechanically

Where patterns are rewritten from one dialect into another in bulk, the rewrite SHALL be produced by
a documented transformation rather than by hand, and that transformation SHALL be verified against
known input/output pairs independently of any corpus.

#### Scenario: A body of patterns is migrated between dialects

- **WHEN** more than a handful of patterns must change dialect
- **THEN** the conversion is expressed as a transformation that is tested in isolation, so that its
  correctness does not rest on any pattern happening to match something

### Requirement: A rewritten pattern finds exactly what it found before

When a pattern's spelling changes without its intent changing, the change SHALL be shown to preserve
behaviour: the old spelling under the old tool and the new spelling under the new tool, run over the
same corpus, SHALL produce identical sets of matched lines. A difference SHALL be treated as a
defect in the rewrite, not as an improvement.

#### Scenario: A pattern is translated between dialects

- **WHEN** a pattern is rewritten from one dialect to another
- **THEN** its matched-line set over the standard's own corpus is compared before and after, and any
  difference fails the migration

#### Scenario: A translation appears to find more

- **WHEN** the rewritten pattern matches lines the original did not
- **THEN** it is a failure, because a translation that broadens is a different check wearing the old
  check's rationale

#### Scenario: A translation appears to find less

- **WHEN** the rewritten pattern matches fewer lines than the original
- **THEN** it is a failure, and specifically the failure this requirement exists to catch, since a
  pattern that silently stops matching reports clean

### Requirement: A pattern is matched against one unit of code at a time

Each example the standard ships SHALL be matched as its own unit. A pattern SHALL NOT be able to
match text spanning two units, and the boundary between units SHALL NOT be expressible in a pattern.
A reported hit SHALL identify the unit it occurred in.

#### Scenario: A multi-line pattern is run over the corpus

- **WHEN** a pattern is capable of matching across line boundaries, and two unrelated examples sit
  adjacent in the corpus
- **THEN** it cannot match text drawn from both, because the units are isolated rather than
  concatenated

#### Scenario: A hit is reported

- **WHEN** a pattern matches
- **THEN** the report names the example the match occurred in and where in that example it began,
  rather than an offset into an aggregate that has no independent meaning

### Requirement: A match is a span, not a line

A hit SHALL be represented as the region of text that matched, which may cover more than one line. A
single-line match SHALL be a span of one line, so that one model serves both cases. Anything that
consumes hits — exemptions, reporting, and the decidability classification — SHALL operate on spans.

#### Scenario: A pattern matches across several lines

- **WHEN** a pattern matches a region covering more than one line
- **THEN** the whole region is the hit, and an exemption or report that examines the hit sees all of
  it rather than only the line it began on

#### Scenario: A pattern matches within one line

- **WHEN** a pattern matches text on a single line
- **THEN** it is a span of one line, handled by the same path as any other span

### Requirement: An invocation is reproducible across machines

Executing a pattern SHALL NOT be influenced by configuration belonging to the machine or the user
running it. Every invocation SHALL neutralise the tool's own configuration mechanisms, and the
result SHALL depend only on the pattern, the corpus, and the pinned tool version.

#### Scenario: The machine carries a personal tool configuration

- **WHEN** verification runs where the executing tool would read a user-level configuration file
- **THEN** that configuration has no effect on the result, because the invocation disables it

#### Scenario: The same corpus is verified on two machines

- **WHEN** the same patterns and corpus are verified in two environments with the same pinned tool
- **THEN** both produce the same hits

### Requirement: The executing tool is named, pinned, and required

Every tool the harness depends on to decide whether a check passes SHALL be named in the standard,
pinned to an exact version, and treated as a required dependency rather than an assumed one. Its
absence SHALL be reported by the same mechanism that reports any other missing required tool. The
same holds for a library the standard's examples are verified against, such as an engine crate. That
library is pinned, and the pin is compared, like a tool's.

The declared pin SHALL be verified against reality in two directions. The version that actually
executes SHALL be compared against the pin, and a mismatch SHALL be reported — a statement that the
standard was verified against a version is false if the harness ran a different one. The pin SHALL
also be compared against the newest release of that tool, and a superseded pin SHALL be reported, so
that moving a pin is a reviewed event rather than a note nobody reads.

A standard MAY instead declare that its pin follows the local toolchain. For such a pin, the second
comparison is not made. The first comparison alone is the signal: once the local toolchain moves
past the pin, the mismatch is what reports the pin as superseded. The declaration SHALL state why
the standard follows the local toolchain.

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

#### Scenario: A language toolchain is unpinned

- **WHEN** a standard's examples are compiled by a toolchain, such as `rustc` or `zig`, that no pin
  names
- **THEN** that is the finding an unfindable pin produces, rather than the toolchain being trusted
  at whatever version is installed

#### Scenario: A pin follows the local toolchain and upstream has moved

- **WHEN** a standard declares that its pin follows the local toolchain, and upstream has released a
  newer version that this machine does not run
- **THEN** nothing is reported, because the standard is verified against what runs here and that
  has not changed

#### Scenario: A pin follows the local toolchain and the local toolchain has moved

- **WHEN** the local toolchain is upgraded past a pin that follows it
- **THEN** the running-version comparison fails, and that failure is the reviewed event that moves
  the pin

#### Scenario: A pin follows the local toolchain without a reason

- **WHEN** a standard declares a local-following pin and gives no reason
- **THEN** the run fails, as an exemption without a reason does

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
