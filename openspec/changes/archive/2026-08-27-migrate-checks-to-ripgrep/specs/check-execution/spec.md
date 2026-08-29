## Purpose

How a rule's `**Check:**` is expressed and executed: the one regex dialect every skill writes in,
the one tool that runs it, and the guarantee that rewriting a pattern preserves the exact set of
lines it finds.

## ADDED Requirements

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

#### Scenario: The tool rejects a pattern

- **WHEN** the executing tool exits with its rejected-pattern status
- **THEN** the run reports a failure naming the rule and the pattern, rather than recording zero hits

#### Scenario: The tool is not installed

- **WHEN** the tool that executes patterns is absent from the environment
- **THEN** the run reports that nothing executed, rather than reporting every check clean

#### Scenario: A pattern is syntactically valid but inert

- **WHEN** a pattern parses successfully yet cannot match any input — an escape read as a literal
  where alternation was meant, for example
- **THEN** nothing in the report distinguishes it from a clean check, which is why the dialect is
  singular and why translation is guarded by the requirement below

### Requirement: A pattern carries no syntax from a dialect it will not be read in

A pattern SHALL NOT contain an escape whose meaning is inverted between the dialect it is written in
and the dialect that executes it. This SHALL be decided by inspecting the pattern, without executing
it and without reference to any corpus, so that a pattern which has silently lost the ability to
match is caught by its text rather than by its results.

#### Scenario: A pattern keeps an escape from the previous dialect

- **WHEN** a pattern to be executed as an extended regular expression contains `\|`, `\(`, or `\{`,
  which are alternation and grouping in basic regular expressions and literal characters here
- **THEN** the standard is non-conforming, whether or not the pattern currently matches anything

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

The tool that executes patterns SHALL be named in the standard, pinned to an exact version by the
harness, and treated as a required dependency rather than an assumed one. Its absence SHALL be
reported by the same mechanism that reports any other missing required tool.

#### Scenario: The harness runs where the tool is missing

- **WHEN** verification runs in an environment without the executing tool
- **THEN** it reports the tool as unavailable and the affected checks as not run

#### Scenario: A reader adopts a Check

- **WHEN** a reader copies a Check to run against their own code
- **THEN** the standard has told them which tool to install and which version it was verified
  against
