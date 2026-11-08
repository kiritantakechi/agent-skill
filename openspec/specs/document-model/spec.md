# document-model Specification

## Purpose
One parser and one printer for every file the harness reads or writes, the canonical form
they define, and the typed values that replace every string spelling of a rule ID, a tier, a
location, a version, a pin and the absence of an answer.

## Requirements

### Requirement: Every file is read by one parser and written by one printer

The harness SHALL read every markdown file it checks or rewrites through one parser into a tree, and
SHALL write every file it rewrites through one printer. No check, command or helper SHALL locate
headings, sections, rules, tables, fences or rule IDs in raw text by any other means.

The parser SHALL recognise fenced blocks before any other structure, so that no line inside a fence
is ever read as a heading, a table row or a rule boundary.

#### Scenario: A heading inside an example

- **WHEN** a rule's example contains a line beginning `## `
- **THEN** the line is part of the fence, and the rule, its section and every operation that edits
  them treat the whole example as one block

#### Scenario: A second parser is introduced

- **WHEN** a module outside the document model compiles a regular expression that matches a rule ID,
  a heading or a fence delimiter
- **THEN** the test suite fails and names the module

### Requirement: The printer defines the canonical form, and formatting is its projection

The canonical form of a file SHALL be `print(parse(file))`. Formatting SHALL be that projection
followed by the toolchain formatters, and SHALL therefore be idempotent. Printing SHALL invert
parsing: `parse(print(tree)) == tree` for every tree.

Paragraphs SHALL be filled by one function at one width. Inline code spans and links SHALL never be
split; a single atom wider than the limit SHALL occupy its own line.

#### Scenario: Formatting twice

- **WHEN** `fmt` runs on its own output
- **THEN** nothing changes

#### Scenario: A file not in canonical form

- **WHEN** a shipped file differs from `print(parse(file))`
- **THEN** the run fails and names the first differing line, and `fmt` rewrites it

#### Scenario: A round trip through the tree

- **WHEN** any tree the parser can produce is printed and parsed again
- **THEN** the result equals the original tree

### Requirement: Each concept has one type, one parser and one printer

Rule IDs, tiers, locations, versions, pins and the absence of an answer SHALL each be represented by
exactly one type with exactly one parser and one printer. No string, tuple or sentinel SHALL stand
in for any of them, and "no answer" SHALL be a value distinct from every answer.

#### Scenario: A core rule and a chapter rule

- **WHEN** the harness reads a rule from SKILL.md section 4 and a rule from a chapter
- **THEN** both are the same type, with the same tier type

#### Scenario: A tool that did not answer

- **WHEN** a version query, a compile or a network request produces no answer
- **THEN** the result is a no-answer value carrying the reason, which no comparison treats as a
  version, a success or an empty result

#### Scenario: A location is reported

- **WHEN** any finding is made
- **THEN** its location is a typed value naming the skill, file, line and rule it knows, and it is
  rendered by one printer
