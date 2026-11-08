## Why

The four standards agree in name and differ in structure, and the harness that holds them to one
shape has the same defect one level down: it compares names, not structure. A purist review of the
whole repository, read for isomorphism rather than for lint, found the same failure in both places.

**One concept, many representations.** A rule ID is matched by 25 regular expressions in `checks/`
and 9 more elsewhere, of differing strictness; `Rename.target` dropped the suffix every other one
accepted, and a renumbering then left a rename row pointing at an ID that no longer existed. A tier
is `"M"` on a chapter rule and `"[M]"` on a core rule, which is a tuple rather than a `Rule`. A
location is a free-form string in at least eight shapes. A version has four parsers. "No answer" is
`None` in some functions, `""` in others, and in `_compile_zig` `None` means the opposite: it
compiled. A `## ` boundary is found in 13 places and only the ones in `shared/` know about fences,
so `demote` cut a rule in half at a `## ` line inside its own example and every guard still passed.
`WIDTH = 100` is defined three times, and the two line-filling functions disagree, so
`renumber` followed by its inverse does not restore the text.

**Shapes that agree only by name.** The ~20 checks have two signatures selected by a string, and
reach a `Finding` through five intermediate representations. The three `lang/` modules disagree on
what a unit is (a directory for Rust, a file for the others), on whether a surviving mutant fails or
notes, and on timeouts four different ways — a `zig fmt --check` that times out passes silently.
Language facts live outside `lang/`; skill facts live in generic checks (`ANCHOR = "rust-style"`,
`MIRROR`, `FIXTURES`), against the README's own statement that configuration lives in profiles.

**Maps that should be bijections.** Of 65 negative controls, 17 are shown to fire through the
branch they are named for; stubbing out the named branch, at least three others still fire,
through another branch. `--skill` filters the *input* of cross-skill checks, so `crossref` and
`mirror` pass vacuously while `plugin` fails spuriously.

Phase L0 fixed the false statements and the silent passes these produced. This change removes the
reason they could exist: each concept gets one type, one parser and one printer, and each operation
the harness performs is stated as a map with the laws it must satisfy, and tested against them.

## What Changes

- **One document model.** Every markdown file is read by one fence-aware parser into a tree and
  written by one printer. `fmt` becomes `print ∘ parse`: a projection onto the canonical form, so it
  is idempotent by construction rather than by care. Rules, chapters, contents lists, tool tables
  and rename tables are nodes, not regex matches.
- **One type per concept.** `RuleId`, `Tier`, `Location`, `Version`, `Pin` and `Answer[T]` each
  have exactly one parser and one printer. Every other spelling is deleted.
- **One signature per check.** A check is `Tree → Iterable[Finding]`; a per-skill check is lifted by
  one combinator. Selection (`--skill`) filters findings by location after every check has seen the
  whole tree. **BREAKING** for anyone calling a check function directly.
- **Controls are a bijection onto branches.** Every finding carries the branch that produced it
  (`layout.width`). Every branch has exactly one negative control or one recorded exemption, and a
  control passes only when its own branch fires. `BRANCHES`, the monkeypatching in the tests and the
  module-level `TOUCHED` list go; the two runners become one.
- **A profile is a record.** Profiles become frozen data: pins, toolchain configuration as a tagged
  union, line rules interpreted by one engine, fixtures, probes, the delta anchor, mirror pairs.
  Generic code never branches on a skill or a language name.
- **A toolchain is an extract/restore pair** with `restore ∘ extract = id`, sharing one driver for
  compile, test, format and mutate, with one timeout policy. `fmt` for every language falls out of
  the pair instead of being written per language.
- **Revision is one operation.** `demote` and `renumber` become `revise`: a partial map from old ID
  to what it becomes (an ID, a lint row, a removal with its reason), closed by dense renumbering.
  It is a bijection on ID tokens, refuses to bind a dangling citation, and `revise` followed by its
  inverse restores the bytes. Dense numbering is kept.
- **ID history leaves the reading path.** Each rename table moves from `migration.md` to
  `references/renames.md`, which nothing on the reading path loads; `migration.md` names it once.

## Capabilities

### New Capabilities

- `document-model`: one parser and one printer for every file the harness reads or writes, the
  canonical form they define, and the typed values (`RuleId`, `Tier`, `Location`, `Version`,
  `Answer`) that replace every string spelling.

### Modified Capabilities

- `standard-structure`: removing, merging, demoting and renumbering become one operation with laws;
  rename history moves to `references/renames.md`.
- `harness-integrity`: negative controls become a bijection onto branches; profiles become records;
  generic code carries no skill or language names.
- `check-execution`: one check signature; selection filters findings, never inputs; one toolchain
  driver and one timeout policy.

## Impact

- **Code:** most of `src/agent_skill/` is rewritten against the new model: `model.py`, `text.py`,
  `shared/`, `renumber.py`, `demote.py`, `fmt.py`, `lang/`, `profiles/` and every check. The CLI
  keeps its subcommands; `demote` becomes an alias of `revise`.
- **Skills:** no rule changes meaning. Files are re-printed once in canonical form (whitespace,
  wrapping, element order within a rule), and rename tables move to `references/renames.md`.
- **Tests:** property tests for the laws (round-trip, idempotence, inverse); the control test
  becomes the bijection test.
- **Follow-on:** `normalize-the-standards` builds the L1/L2 content checks on this model, and
  `one-abstract-standard` builds the cross-standard registry on it.
