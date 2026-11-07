# Tasks

Every task ends with `uv run agent-skill check --fast`, `uv run ruff check .`, `uv run ruff format
--check .` and `uv run ty check` clean, in addition to the verification it names. A task that moves,
merges or adds rules also runs `check --skill <each standard it touched> --only toolchain` once.

## 1. Repository items and harness debts

- [x] 1.1 Update OpenSpec to 1.16.0 with skills as the one delivery (`openspec config set delivery
  skills`, `openspec update`), removing `.claude/commands/opsx/` if the update leaves it; verify with
  a test that every `.claude/skills/openspec-*/SKILL.md` names one `generatedBy`, 1.16.0, that the
  commands directory is absent, that `openspec validate --all` passes, and that this change passes
  `--strict` (the main specs' 15 requirements over 500 characters, a warning 1.15.0 gives too, stay
  whole: OpenSpec splits an existing requirement only when its owner asks)
- [x] 1.2 Move `plugin.json` to 2.0.0; verify `check --only plugin` passes and the README states the
  version's reason (rule IDs renumbered, `CORE` removed)
- [x] 1.3 Give `crossref.apparatus` findings their line (`ids.cited` yields positions); verify its
  control's finding carries the line it injected
- [x] 1.4 Take cargo's lock on the target directory around the post-run cache cleanup; verify with a
  test that cleanup waits on a held lock, and one rust-style toolchain run
- [x] 1.5 Probe the Rust `env::*` rows by compiling the call outside `unsafe` under edition 2024,
  expecting E0133; verify `check --skill rust-style --only toolchain` reports them verified, not
  unprobed
- [x] 1.6 Make `test_control_fires` use the thread-pooled runner `check --only controls` uses;
  verify every control still fires its branch alone and record the time before and after
- [x] 1.7 Make `install` exit non-zero when it leaves a differing directory alone and zero when the
  directory is identical; verify with tests for both, and that no test runs a real install into the
  user's directory

## 2. Machinery

- [x] 2.1 Add `Relation` to `ids` (`realises`, `extends`, `tightens`, `overrides`, `decided`,
  `absent`) and one tier law with its reason rule; make the delta's departures use it; verify the
  law table by unit tests and that every existing `crossref` control still fires
- [x] 2.2 Read the abstract standard: a profile-shaped record (prefix `AS`), chapters in the
  template, entries (heading, statement, realisation table) and `principles.md`; add a demo abstract
  standard beside `checks.demo`; verify `print ∘ parse` is the identity on it, and `fmt` idempotent
- [x] 2.3 Add the `concepts` check (branches of design decision 3) with one control each on the demo,
  and delete `checks/mirror.py`, `profiles.record.Mirror`, every `mirror=` and the mirror controls;
  verify the controls ↔ branches bijection both ways and `check --only concepts`
- [x] 2.4 Make `fmt` render each realisation row's tier cell from its rule; verify the `stale_tier`
  control and `fmt`'s idempotence on `abstract/`
- [x] 2.5 Add `domain` to profiles; create an empty abstract chapter, in the template, for every
  vocabulary word that two or more base standards ship; declare each base standard's other chapters
  as domain chapters with their features, and bevy-style's; verify `check --fast` passes with no
  entries yet, and the `undeclared_domain`, `domain_realises` and `domain_missing` controls
- [x] 2.6 Add `move` to `revise` (target chapter, `after` a rule or a section heading, creation of a
  missing chapter and its section 6 row); verify the move-and-back law by property tests on copies of
  the shipped tree with random moves, beside the existing laws
- [x] 2.7 Write `abstract/principles.md` and the section 3 check; decide zig-style's third question
  (the shared question, answered for Zig, or zig-style's own after the five) and make every base
  standard's section 3 open with the questions; verify the `principles` control and `check --fast`
- [x] 2.8 Add the abstract rows to `measure` (design decision 12) and record the baseline here;
  verify `measure` prints them for all four standards and the demo
- [x] 2.9 Document the abstract standard, `concepts`, domain chapters and `revise` `move` in the
  README; verify `check --only documented`

Baseline (task 2.8), before the sweep: the rows `agent-skill measure` adds for the abstract
standard, as it prints them, and its second table. No entry is registered yet, so every realisation
count is 0; the look-alike pairs count each pair in both standards it joins (14 pairs: 13 between
base standards, 1 of bevy-style with its anchor).

| Measure | bevy-style | python-style | rust-style | zig-style |
| --- | --- | --- | --- | --- |
| realisations `realises` | 0 | 0 | 0 | 0 |
| realisations `extends` | 0 | 0 | 0 | 0 |
| realisations `tightens` | 0 | 0 | 0 | 0 |
| realisations `overrides` | 0 | 0 | 0 | 0 |
| realisations `decided` | 0 | 0 | 0 | 0 |
| realisations `absent` | 0 | 0 | 0 | 0 |
| look-alike pairs no entry holds | 1 | 7 | 9 | 11 |
| domain chapters | 7 | 2 | 6 | 4 |
| rules in abstract chapters realising nothing | 37 | 194 | 378 | 251 |

| Abstract chapter | Entries |
| --- | --- |
| api | 0 |
| build | 0 |
| concurrency | 0 |
| data | 0 |
| documentation | 0 |
| errors | 0 |
| migration | 0 |
| modules | 0 |
| naming | 0 |
| output | 0 |
| performance | 0 |
| testing | 0 |
| all | 0 |

## 3. The sweep

Each task follows design decision 6 and its criteria. In each standard's chapter X, and wherever
else that standard states X's concepts, it does the following:

- register every concept two or more base standards state as an entry in `abstract/X.md`;
- name each standard's realisation, or why its domain has none;
- move realisations into X, and merge duplicates;
- add the rule for each gap;
- settle each tier disagreement.

Each task is verified when `check --fast` passes, each touched standard's toolchain passes, and
bevy-style's departures still resolve. Each task then records its counts here: entries,
realisations by relation, moves, merges, new rules, tier changes, and look-alike notes before and
after. Each is pushed when green.

Seeds. Before task 2.3 deleted `Mirror`, it held these pairs, and its detector noted three more. The
sweep starts from them: each is a concept two standards state, or a recorded reason it is not. The
zig-style pairs were keyed by the rust-style rule's title, resolved here to the rule's ID at the
time of deletion (both tiers `[M]` unless marked):

- zig-style's 12 mirror pairs:
  - ZS-DATA-36 and RS-API-57: give every operation its inverse, or document why there is none
  - ZS-DATA-37 and RS-API-58: keep parameter (argument) order identical across sibling functions
  - ZS-DATA-38 and RS-API-19: split a function rather than adding a mode (`bool`) parameter
  - ZS-ERR-31 and RS-API-59: give the members of one error set (sibling variants) a uniform shape
  - ZS-ERR-32 and RS-MOD-44: absorb a special case into the general path, or give it its own type
  - ZS-NAME-28 and RS-NAME-35: name the two halves of a pair symmetrically
  - ZS-NAME-29 and RS-MOD-43: one concept, one mechanism
  - ZS-NAME-30 and RS-MOD-45 (both `[S]`): keep sibling modules structurally parallel
  - ZS-COMPTIME-15 and RS-TRAIT-01: pick the interface shape (name the capability as a trait)
    before writing the code that provides it
  - ZS-BUILD-21 and RS-MOD-29: count the encapsulation a module boundary (a split) costs, not only
    what it buys
  - ZS-NAME-14 and RS-MOD-31 (both `[S]`): name a directory after what it roots (the crate)
  - ZS-NAME-02 and RS-NAME-01: capitalize acronyms as ordinary English words
- The detector's three notes (`check --only mirror --verbose`):
  - PS-NAME-14 and RS-NAME-35: name the two halves of a pair symmetrically
  - PS-NAME-15 and RS-MOD-43: one concept, one mechanism
  - BV-MIG-03 and RS-MIG-02: do not call an API the target deprecated (a delta and its anchor)

- [x] 3.1 `errors`: 14 entries (`AS-ERR-01` to `-14`); realisations: python-style 12 `realises`, 1
  `overrides`, 1 `absent`; rust-style 13 `realises`, 1 `tightens`; zig-style 11 `realises`, 2
  `overrides`, 1 `absent`. Moves 6: RS-OWN-32, RS-OWN-33, RS-FUNC-02, RS-FUNC-43 into rust-style's
  errors; ZS-MEM-10, ZS-MEM-12 into zig-style's. Merges 2: RS-ERR-16 into RS-ERR-10, RS-ERR-17 into
  RS-ERR-13 (now `[M]`, `[M!]` before). New rules 2: PS-ERR-21 and RS-ERR-37. Tier changes: RS-ERR-13
  only. Look-alike notes 14 → 14. ZS-ERR-33 (with RS-API-59) is left for `api`, ZS-ERR-34 (with
  RS-MOD-44) for `modules`.
- [x] 3.2 `testing`: 14 entries (`AS-TEST-01` to `-14`); realisations: python-style 10 `realises`, 1
  `extends`, 1 `tightens`, 1 `decided`, 1 `absent`; rust-style 14 `realises`; zig-style 14
  `realises`. Moves 0; merges 0. New rules 11: PS-TEST-11, -12, -13, -23, -24, -25 (PS-TEST-11
  split from PS-TEST-06, now only "one claim") and ZS-TEST-11 to -15 (-15: `expectError`). Tier changes 2: PS-TEST-07 to `[S]`,
  ZS-TEST-16 (negative space) to `[M]`, its relaxed form dropped. Look-alike notes 14 → 14. Left for
  `concurrency`: PS-TEST-26 and -27, RS-CONC-42 with PS-TEST-21 (no sleep), RS-FUNC-38 with PS-TEST-22
  (inject the clock). Not registered: RS-TEST-16 with ZS-TEST-20 (a deterministic test), RS-TEST-23
  with ZS-TEST-24 (fuzz targets), as no python rule states either whole.
- [x] 3.3 `build`, including the concept that every third-party CI action is pinned to a commit,
  realised by a new rule in each base standard: 7 entries (`AS-BUILD-01` to `-07`); realisations:
  python-style 7 `realises`; rust-style 7 `realises`; zig-style 5 `realises`, 2 `absent` (no lock
  file, no version ranges). Moves 1: PS-NAME-09 into python-style's build (now PS-BUILD-20). Merges
  0. New rules 5: PS-BUILD-12, -16, -21, RS-BUILD-47, ZS-BUILD-32 (the action pin is PS-BUILD-21,
  RS-BUILD-47, ZS-BUILD-32).
  Tier changes 1: ZS-BUILD-31 to `[M]`, relaxed form folded in. Look-alike notes 14 -> 14. Left for
  `modules`: ZS-BUILD-21 with RS-MOD-29 (the seed: a module boundary's cost). Not registered:
  PS-BUILD-04 / RS-BUILD-02, -31 / ZS-BUILD-34 (the oldest toolchain a library supports; three
  different claims), PS-BUILD-11 (cooldown; no other standard states one), RS-BUILD-28, -29 (audit;
  rust only), RS-BUILD-41 / ZS-BUILD-23 (release profile, for `performance`), PS-BUILD-15 (a build
  from the repository alone; rust-style and zig-style state no rule), RS-BUILD-26 / ZS-BUILD-33
  (denied warnings; different constructs).
- [x] 3.4 `naming`: 12 entries (`AS-NAME-01` to `-12`), in casing, word choice, families of names and a
  layout section (line width, trailing comma; the formatter's CI gate stays AS-BUILD-06);
  realisations: python-style 11 `realises`, 1 `overrides` (acronyms); rust-style 9 `realises`, 1
  `overrides` (units last, word order), 1 `decided` (the casing lints), 1 `absent` (no trailing-comma
  lever); zig-style 12 `realises`. Moves 0. Merges 1: RS-NAME-34 into RS-NAME-08 (associated types
  join the enum variants). New rules 5: PS-NAME-09, PS-NAME-10, RS-NAME-35, ZS-NAME-09, ZS-NAME-06
  (split out of ZS-NAME-05, which keeps the fully qualified name; ZS-NAME-26 loses "run `zig fmt`" to
  ZS-BUILD-26). Tier changes 1: RS-NAME-26 to `[M]`. Look-alike notes 14 -> 7. Left for `modules`:
  PS-NAME-16 / RS-MOD-43 / ZS-NAME-31 (one concept, one mechanism: a design rule, not a name),
  PS-NAME-18 / RS-MOD-45 / ZS-NAME-32 (sibling modules parallel), ZS-NAME-16 / RS-MOD-31 (a directory
  named for what it roots), module and file names (PS-NAME-08, RS-NAME-04, -11, ZS-NAME-15), and
  zig-style's declaration order and `pub` (ZS-NAME-17 to -21). Left for `documentation`: PS-NAME-13,
  -14 and ZS-NAME-22 to -25 (comments), ZS-NAME-29 (commit message). Not registered, stated by one
  standard: the conversion prefixes, getters and iterator names (RS-NAME-12 to -21), RS-NAME-23, -27 to
  -33, the `_` prefix (PS-NAME-03 / ZS-NAME-03), receivers and helper prefixes (ZS-NAME-10, -14).
- [x] 3.5 `documentation`: 12 entries (`AS-DOC-01` to `-12`), in documenting an item, comments, and the
  documents beside the code; realisations: python-style 10 `realises`, 2 `decided` (`D103`, `ERA001`);
  rust-style 11 `realises`, 1 `decided` (`missing_docs`); zig-style 12 `realises`. Moves 6: PS-NAME-13,
  -14 into python-style's documentation (PS-DOC-13, -14); ZS-NAME-22 to -25 into zig-style's new
  `documentation.md` (ZS-DOC-03, -05, -07, -08), with its three doc-comment rows and `ERA001`'s row.
  Merges 3: RS-BUILD-11 into RS-DOC-26 (changelog), RS-DOC-08 into RS-DOC-07 (blank line after the
  summary); RS-DOC-06 demoted to the `missing_docs` row once its example half was split out. New rules
  10: RS-DOC-06 (examples run, split from the old RS-DOC-06), RS-DOC-16 (reasons out of a doc comment),
  RS-DOC-19 (comment as a sentence); ZS-DOC-01, -02, -04, -06, -09, -10, -11, -12 (`pub` documented,
  summary sentence, errors, examples as `test` blocks, commented-out code, comments updated, changelog,
  README). Tier changes 3: PS-DOC-08 to `[M]`, PS-DOC-09 and -10 to `[S]`. Look-alike notes 7 -> 7.
  Left for `modules`: RS-MOD-01 (a module has a documented concept; `//!`, `__init__` docstring, ZS-DOC-03's
  `//!`). Left for `concurrency`/`api`/`types`: RS-CONC-47 (document the threading contract), RS-TRAIT-11 with
  ZS-COMPTIME-11 (document a generic parameter's contract), PS-API-12, RS-API-57 / ZS-DATA-36 (document the
  missing inverse), ZS-MEM-09 (ownership in the doc comment). Not registered, one standard: `# Panics`
  (RS-DOC-10), `# Safety` (RS-UNSAFE-04), the design note, provenance, TODO owner (RS-DOC-26), ZS-NAME-25
  (commit message; belongs to `build` or nowhere, left in naming).
- [x] 3.6 `modules`: 14 entries (`AS-MOD-01` to `-14`), in dividing code into modules, layout, imports
  and the graph, order within a file, and orthogonality; realisations: python-style 10 `realises`, 2
  `tightens` (the `src/` layout, the distribution's name), 2 `decided` (`I001`, `F403`); rust-style 12
  `realises`, 1 `decided` (`wildcard_imports`); zig-style 13 `realises`, 1 `absent` (no wholesale
  import). Moves 16: PS-NAME-08, PS-BUILD-14, PS-NAME-14, -16 into python-style's modules; RS-NAME-04
  into rust-style's; ZS-BUILD-18, -21, -22, ZS-NAME-16 to -20, -27, -28 and ZS-ERR-34 into zig-style's
  new `modules.md` (ZS-MOD-01 to -14 with the new rules; `modules` is abstract, so not in `domain`).
  Merges 0. New rules 8: PS-MOD-01 (a module docstring states one concept), -03 (count the names a
  split makes public), -11 (public names first), -12 (class body order), -15 (absorb a special case);
  ZS-MOD-01 (a `//!` comment), -02 (split on a seam), -04 (a file name of few words). Tier changes 2:
  PS-MOD-04 (ex PS-NAME-08) and ZS-MOD-11 (ex ZS-NAME-19) to `[S]`. Look-alike notes 7 -> 2 pairs
  (RS-API-57 / ZS-DATA-36 for `api`, BV-MIG-03 / RS-MIG-02). Decided: "one concept, one mechanism" and
  "absorb a special case" are `modules`' (rust-style already holds both there, with "sibling modules
  parallel"; principles.md's questions 4 and 5 ask them of every standard). The module names of
  PS-NAME-09 / RS-NAME-05 / ZS-NAME-06 stay `naming`'s (AS-NAME-06); ZS-NAME-15 (a file's casing by
  whether it has fields) and RS-NAME-11 (a file not repeating its directory) stay in `naming`,
  each stated by one standard. Left for `api`: the visibility and surface rules (RS-MOD-10 to -17,
  PS-MOD-07's `__init__` as a table of contents, ZS-NAME-16 `pub`, ZS-BUILD-15, PS-API-01 to -05). Not registered, one standard: do no
  work at import (PS-MOD-08), `lazy import` (PS-MOD-09), crate and workspace layout (RS-MOD-18, -20 to
  -22, -24 to -29, -31, -33, -34), RS-MOD-02, -05 to -09, -36 to -39 and -42, ZS-MOD-08 (the import
  block in one place), ZS-BUILD-16. Not registered, no chapter: function length (RS-MOD-43 `[S]`, "no
  limit worth enforcing", against ZS-ERR-30 `[M!]`, 70 lines; python's `PLR0915` is on) for 3.14.
- [ ] 3.7 `api`
- [ ] 3.8 `data`
- [ ] 3.9 `types`
- [ ] 3.10 `concurrency` (python-style's `async.md` among the candidates)
- [ ] 3.11 `output` (rust-style's `cli.md` streams and exit codes among the candidates)
- [ ] 3.12 `performance`
- [ ] 3.13 `migration`
- [ ] 3.14 Remove an abstract chapter that holds no entry, or record why it stays; declare a chapter
  the sweep emptied of realisations as domain, or remove it; verify every look-alike note left has a
  recorded reason the two rules answer different questions

## 4. Actions and CI

- [x] 4.1 Add the eight action repositories to the session read-only, and pin every `uses:` in the
  four `ci.yml` assets to the commit of its newest release at least seven days old, with the version
  comment; `dtolnay/rust-toolchain` is pinned to a `master` commit and takes `toolchain:`; verify the
  assets' checks and toolchains pass. Pinned: checkout v7.0.1, setup-uv v10.3.3, rust-toolchain master,
  rust-cache v2.9.3, install-action v2.88.1, audit-check v2.0.0, semver-checks-action v2.9, setup-zig v2.2.1
- [ ] 4.2 Add `pins.movable_action` and `pins.unversioned_action`, with controls; verify both fire
  alone and pass on the shipped assets
- [ ] 4.3 Write `.github/workflows/check.yml` (design decision 10), and make `selfapply` hold its
  shared steps to python-style's `ci.yml`; verify `check --fast`, a control for a drifted step, and
  the first run's result on the pull request

## 5. Evals

- [ ] 5.1 Add `Evals` selections to the profiles (two review rules, two old spellings each) and the
  selection-validity branches, with controls; verify each invalid selection fires its branch alone
- [ ] 5.2 Write the generator and `agent-skill evals`, and the `evals` check (`drift`, `extra`), with
  controls; verify by tests that each escaped literal matches itself and nothing else, and that the
  negative case's prompt is another language's
- [ ] 5.3 Generate the suite, ignore `plugins/style-standards/evals/results/`, run the no-case load
  test and record what it showed, and give the owner's command in the README; verify `check --only
  evals` and `documented`

## 6. Close

- [ ] 6.1 Record `measure`'s rows after the change beside the baseline; run the full `agent-skill
  check` once and `pytest -q`; record both results and times here
- [ ] 6.2 Bring the README in line with everything above; verify `check --only documented`

## Workflow follow-up

- Archive with the OpenSpec CLI (`openspec archive one-abstract-standard`), syncing the specs, and
  check `openspec validate --all`, and `--strict` on every requirement this change added.
- Update the pull request's description, then stop for the owner's review of Phase D.
