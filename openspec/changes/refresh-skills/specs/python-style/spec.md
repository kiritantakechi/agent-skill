# Spec Delta

## MODIFIED Requirements

### Requirement: Single target version, with an explicit floor

The standard SHALL target exactly one CPython version — 3.15, free-threaded — and SHALL state that
floor in its own text. It SHALL NOT describe compatibility shims, version guards, or fallbacks for
any interpreter below 3.14t, and SHALL NOT present a pre-3.14 spelling as an acceptable
alternative.

#### Scenario: A rule offers a fallback for an older interpreter

- **WHEN** a rule presents `sys.version_info` branching, a `try: ... except ImportError:` import
  shim, or a "on older Pythons, write it this way" alternative for an interpreter below 3.14t
- **THEN** the standard is non-conforming, and the rule states the 3.15 spelling only

#### Scenario: A reader asks which interpreter the examples were verified against

- **WHEN** the reader reads the standard's opening section
- **THEN** the exact interpreter build is named, including that it is the free-threaded build

#### Scenario: A stale idiom is described

- **WHEN** the standard mentions an idiom that 3.14 or 3.15 superseded — `from __future__ import
  annotations`, a hand-rolled sentinel, `MappingProxyType` for an immutable mapping,
  GIL-dependent thread-safety reasoning
- **THEN** it appears only as the *dead* side of a migration table or a `BAD` example, never as
  advice

#### Scenario: An explicit encoding is described

- **WHEN** a rule passes `encoding="utf-8"` to a text open, although 3.15 made UTF-8 the default
- **THEN** it is advice and not a superseded idiom. The default holds only while UTF-8 mode is on,
  and `PYTHONUTF8=0` or `-X utf8=0` turns it off; What's New in 3.15 itself asks for an explicit
  `encoding`, and `-X warn_default_encoding` still flags every call that omits one

### Requirement: Three attributed sources, with conflicts resolved in the open

The standard SHALL merge exactly three sources and SHALL name them: the normative Python
specifications (PEP 8, PEP 257, PEP 20, and the Python Typing Spec), the empirical conventions of
the CPython 3.15 standard library, and Ruff's rule catalogue as the house standard. Every rule SHALL
be traceable to at least one of them. Where two sources disagree, the rule SHALL state the
disagreement, pick a side, and give the reason.

#### Scenario: A rule restates a Ruff rule

- **WHEN** a rule's whole actionable content is something one code in Ruff's catalogue already
  decides
- **THEN** it is a row in its chapter's `Decided by tools` table rather than a rule. The row gives
  the ruff code, and the shipped lint configuration enables it

#### Scenario: A rule says more than the Ruff rule it relies on

- **WHEN** a Ruff code decides part of a rule, but the rule also states a design choice, a
  when-to-deviate, or a shape the code cannot see
- **THEN** it stays a rule, and its **Check** cites the ruff code, which the shipped lint
  configuration enables

#### Scenario: Two sources disagree

- **WHEN** PEP 8 and Ruff's default, or PEP 8 and the standard library's own practice, prescribe
  different things for the same question
- **THEN** the rule names both positions, states which one this standard takes, and gives the
  reason — rather than silently following one

#### Scenario: A chapter covers ground Ruff cannot reach

- **WHEN** the chapter is about free-threading, concurrency, API and ownership design, async
  lifecycle, or packaging
- **THEN** the chapter states which of the other two sources its rules rest on, and each rule still
  ships a check that decides it

### Requirement: Every rule carries an ID, a rationale, and a decisive check

Every rule SHALL have an ID under a single prefix, a tier tag, a title, a `**Why:**` rationale of at
most three lines, and a `**Check:**` that names how to decide the rule against a diff. A rule that
defers to another rule SHALL point at the owning ID rather than restating it. IDs SHALL be dense
within their chapter. A renumbering SHALL ship a table mapping every old ID to its replacement.

#### Scenario: A rule ships without a rationale or a check

- **WHEN** a rule body has no `**Why:**`, or no `**Check:**` and no pointer at an owning rule
- **THEN** the rule is non-conforming

#### Scenario: A rationale outgrows three lines

- **WHEN** a rule's `**Why:**` runs past three lines
- **THEN** the rule is non-conforming. The excess belongs in the statement, in an example, or
  nowhere

#### Scenario: A check is a runnable command

- **WHEN** the check can be expressed as a `ruff` selection, a `ty` rule, or a pattern
- **THEN** the check is written as that command, so it decides rather than advises

#### Scenario: IDs are cited across chapters

- **WHEN** one rule refers to another
- **THEN** it cites the target by ID, the ID exists, and it lives in the chapter the citation names

#### Scenario: IDs are renumbered

- **WHEN** rules are removed, demoted to lint-table rows, or reordered, and a chapter is renumbered
- **THEN** `references/migration.md` maps every old ID to its new ID or to what replaced it, so a
  citation made before the renumbering can still be resolved
