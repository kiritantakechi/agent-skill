# abstract-standard Specification

## Purpose
States once every concept that two or more standards share, and holds each standard to it: which
rule realises each concept in each standard, at what tier, in which chapter, and why a standard
departs from it or has none.

## Requirements

### Requirement: A shared concept is stated once, in the abstract standard

Every concept that two or more base standards state SHALL be one entry of the abstract standard. An
entry SHALL be headed `AS-<FAMILY>-NN [tier] Title`. Its family SHALL be the vocabulary code of the
chapter file that holds it, and its IDs SHALL be dense. It SHALL give a statement that names no
construct of any one language, then its realisation table. The abstract standard's chapters SHALL
follow the chapter template every standard follows.

#### Scenario: A statement in one language's terms

- **WHEN** an entry's statement holds inline code, such as `` `Result` `` or `` `errdefer` ``
- **THEN** the run fails: the construct belongs to a realising rule, and the concept to all of them

#### Scenario: An entry in the wrong file

- **WHEN** `AS-ERR-04` stands in the abstract standard's `testing.md`
- **THEN** the run fails, naming the code the vocabulary gives `testing`

### Requirement: Every base standard answers every concept

An entry's realisation table SHALL have exactly one row for each base standard, a standard that
names no anchor, and no row for a delta. A row SHALL name the standard, the rule that realises the
concept, the relation, the tier and a reason. A `decided` row SHALL name instead a row of the
standard's `Decided by tools` table, and carry no tier. The rule cell SHALL be empty exactly when the
relation is `absent`, whose reason SHALL say why the standard's domain has no instance.

#### Scenario: A standard missing from an entry

- **WHEN** an entry has rows for python-style and rust-style and none for zig-style
- **THEN** the run fails, naming the entry and the standard

#### Scenario: A concept a tool decides

- **WHEN** python-style realises an entry only by its ruff row for `F403`
- **THEN** the row says `decided` and names `F403`, which must be a row of python-style's table in the
  entry's chapter

#### Scenario: Absent with no reason

- **WHEN** a row's relation is `absent` and its reason cell is empty
- **THEN** the run fails

#### Scenario: A delta given a row

- **WHEN** an entry has a row for bevy-style
- **THEN** the run fails: a delta realises a concept through its anchor

### Requirement: A realisation's relation is decided by its tiers

A row's tier cell SHALL be its rule's tier, rendered by `fmt` from the rule; a `decided` or `absent`
row has none. The relation SHALL be
`realises` or `extends` when that tier equals the entry's, and `tightens` when it is higher. A row
whose rule says something other than the entry, at any tier, SHALL be `overrides`. Every relation but
`realises` SHALL give a reason.

#### Scenario: A silent tier change

- **WHEN** an entry is `[M]`, its python-style rule is `[S]`, and the row says `realises`
- **THEN** the run fails: the row is an `overrides` with its reason, or the rule's tier is wrong

#### Scenario: A tier cell that drifted

- **WHEN** a rule's tier changes and its row still shows the old one
- **THEN** `fmt` renders the cell from the rule, and the run fails until it has

#### Scenario: A departure with no reason

- **WHEN** a row says `tightens` and its reason cell is empty
- **THEN** the run fails

### Requirement: A concept has one realising rule per standard, and a rule realises one concept

No two rows of one standard SHALL name the same rule. No two rules of one standard SHALL realise the
same entry.

#### Scenario: One rule realising two concepts

- **WHEN** PS-ERR-07 is the python-style row of two entries
- **THEN** the run fails: the two entries are one concept, or the rule states two

#### Scenario: Two rules stating one concept

- **WHEN** a sweep finds two python-style rules that each state an entry's concept
- **THEN** they are merged with `revise` before either is named in the row

### Requirement: A delta realises a concept through its anchor

A delta's realisation of an entry SHALL be its anchor's row. When the delta's departures table has a
row for the anchor's realising rule, the delta's realisation SHALL be that row's rule, with its
relation and tier. `measure` SHALL print each delta's realisations derived this way.

#### Scenario: A delta departs from a realising rule

- **WHEN** the rust-style row of `AS-BUILD-NN` is RS-BUILD-21, and bevy-style's departures table has
  RS-BUILD-21 `overrides` BV-BUILD-04
- **THEN** bevy-style realises `AS-BUILD-NN` by BV-BUILD-04 under `overrides`, and no entry names
  bevy-style

### Requirement: Rules that look alike and share no concept are reported

Two rules of different standards whose titles overlap above the detector's threshold, and that do
not realise one entry, SHALL be reported as a note. A delta's rule SHALL be compared with its
anchor's. Every pair of base standards SHALL be compared.

#### Scenario: A pair no entry holds

- **WHEN** PS-NAME-14 and ZS-NAME-28 are both titled "Name the two halves of a pair symmetrically"
  and no entry names both
- **THEN** a note names the two rules

#### Scenario: Two standards neither of which is rust-style

- **WHEN** a python-style rule and a zig-style rule look alike
- **THEN** they are compared and reported, as any other pair is

### Requirement: No shipped file cites the abstract standard

A skill SHALL read completely when installed alone, so no file under a skill directory SHALL cite an
abstract ID. The abstract standard SHALL be revised by `revise` like any standard, and a rename of a
rule it names SHALL rewrite its rows.

#### Scenario: A standard citing a concept

- **WHEN** a rule in rust-style says "as AS-ERR-03 states"
- **THEN** the run fails: the reader of the installed skill has no abstract standard to look in

#### Scenario: A realising rule is renumbered

- **WHEN** `revise` renumbers RS-ERR-12 to RS-ERR-11
- **THEN** every entry that named RS-ERR-12 names RS-ERR-11, in the same operation

### Requirement: Section 3 opens with the abstract design questions

The abstract standard SHALL hold the design questions, in order. Section 3 of every base standard
SHALL open with them, in that order, each question's bold wording verbatim and its answer the
standard's own. A standard's own questions SHALL follow them.

#### Scenario: A question reworded

- **WHEN** zig-style's third question reads "What can be asserted instead of assumed?" where the
  abstract standard's third reads otherwise
- **THEN** the run fails: the question is the abstract standard's, or it is zig-style's own and
  follows the shared ones

#### Scenario: A delta's section 3

- **WHEN** a delta's section 3 holds its departures table
- **THEN** it is not required to restate the questions, which its reader loads with the anchor
