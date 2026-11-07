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
- [x] 3.7 `api`: 11 entries (`AS-API-01` to `-11`), in the public surface (private until needed, decided in
  one place, enumerated), signatures (general in and specific out, transposable parameters, no mode
  flag, ownership of a return), the asymmetry cluster (inverse, argument order, uniform sibling
  failures) and deprecation; realisations: python-style 11 `realises`; rust-style 9 `realises`, 1
  `extends` (RS-API-26: newtypes, of which transposable parameters are one case), 1 `absent` (the
  signature states ownership); zig-style 10 `realises`, 1 `absent` (no wildcard export). Moves 18:
  PS-MOD-07 and PS-DATA-18 into python-style's api; RS-MOD-10 to -17 into rust-style's; ZS-NAME-16,
  ZS-BUILD-15, ZS-NAME-11, ZS-MEM-09, ZS-DATA-36 to -38 and ZS-ERR-33 into zig-style's new `api.md`
  (ZS-API-01 to -10; `api` is abstract, so not in `domain`). Merges 0. New rules 4: PS-API-18 (argument
  order), PS-API-19 (sibling exceptions); ZS-API-06 (take the slice or the interface), ZS-API-10
  (deprecation). Tier changes 1: PS-API-10 (no mode flag) to `[M]`, its `[S]` toggle clause folded in.
  PS-DATA-18 retitled to the other two's words. Look-alike notes 2 -> 1 (BV-MIG-03 / RS-MIG-02, for
  `migration`). Not registered, one standard: PS-API-02 (typing spec's re-export), -04, -06, -07, -11,
  -12 (return or effect), -13 (document what is not done), -16 (add a keyword-only parameter);
  RS-API-02, -03 (no `pub` for a test), -05, -07, -08, -09, -10 to -14, -16 to -18, RS-API-62 and -64
  (breaking changes, additive evolution), -68, -69. Left for `data` and `types`: the
  rest of rust-style's encapsulation, type-safety, trait and constructor rules (RS-API-19 to -60,
  -61), PS-API-07 (annotations), PS-DATA-05 / RS-API-17 (a tuple return), ZS-DATA-27 (the weakest
  return). ZS-ERR-03 (name a public error set) is stated by one standard; ZS-ERR-05 is AS-ERR-09's.
- [x] 3.8 `data`: 10 entries (`AS-DATA-01` to `-10`), in the shape of a value (alternatives as one type, a
  type of its own for a unit or domain, a record over a tuple, a handle over a pointer), validity
  (unrepresentable first, refused at construction, a view never the container), equality and hashing,
  and numbers (a fixed width for what is stored, a chosen overflow behaviour); realisations: python-style
  7 `realises`, 3 `absent` (a handle, integer width, overflow: unbounded integers and a collected heap);
  rust-style 9 `realises`, 1 `extends` (RS-DATA-09 also checks narrowing conversions); zig-style 9
  `realises`, 1 `overrides` (ZS-DATA-04: no operator overloading, so the role travels in the name).
  Moves 10: RS-API-17, -20, -21, -22, -30, -31, -43, RS-OWN-21, RS-ERR-26, RS-PERF-30 into rust-style's
  new `data.md` (RS-DATA-01 to -10; `data` is abstract, so not in `domain`). Merges 4: RS-API-31 and
  RS-API-33 into the newtype rule (units, index spaces), RS-API-29 into the enum rule (correlated
  fields), RS-API-21 into RS-API-20 (no `&mut` to invariant-bearing state). New rules 6: RS-API-18
  (split off the newtype rule: adjacent parameters of one type, now AS-API-05's rust row); ZS-DATA-30
  (named struct over tuple), -31 (unrepresentable first), -32 (validate in `init`), -33 (const view),
  -34 (`eql` and `hash` agree). Tier changes 4: PS-DATA-15 to `[M]` (relaxed form dropped), RS-DATA-03
  (ex RS-API-17) to `[S]`, ZS-DATA-10 to `[M!]` with a relaxed form; PS-DATA-03 and ZS-DATA-25 gained
  the payload and flag clauses. Look-alike notes 1 -> 1 (BV-MIG-03 / RS-MIG-02, for `migration`).
  Not registered, one standard: python-style's dataclass shape rules (PS-DATA-01, -02, -04, -06, -07,
  -08 to -10, -12, -13: frozen record, `slots`, `StrEnum`, `TypedDict`, `Protocol`, mutable default,
  import-time default, field order, `replace`, `frozendict`), rust-style's `Default`, builder and
  constructor rules (RS-API-35 to -40 at the time, -54 to -60) and RS-API-28 (an enum over an `Option`
  with meaning), zig-style's decl literals and `init`/`deinit` (ZS-DATA-12 to -17), integer and cast
  rules (ZS-DATA-01, -03, -05 to -09, -11), layout (ZS-DATA-19, -20) and text (ZS-DATA-30 to -32 at
  the time). Decided: ZS-DATA-27 and -28 (the weakest return, absence) are `errors`' absence ladder
  (AS-ERR-03, RS-API-58 / RS-ERR-23), not AS-API-04's return side, which asks for the most specific
  type, and stay unregistered; defaults and builders are each a language's spelling (mutable default,
  `Default`, decl literal) and share no claim. Left for `performance`: ZS-DATA-22 and RS-PERF-13
  (struct of arrays), ZS-DATA-24 (fixed array), ZS-DATA-18 (pass by pointer). Left for `types`: PS-DATA-07
  (a `Protocol`) with RS-TRAIT, PS-TYPE-15.
- [x] 3.9 `types`: 5 entries (`AS-TYPE-01` to `-05`), in interfaces and closed sets (the capability named as
  an interface before what provides it, a closed set a sum type and not an interface, handled with no
  catch-all) and generics (the contract a signature cannot state, generic only where used); realisations:
  python-style 5 `realises`; rust-style 4 `realises`, 1 `decided` (clippy `wildcard_enum_match_arm`, added
  to the shipped lints); zig-style 4 `realises`, 1 `extends` (ZS-TYPE-04 also requires a compile-time
  guard). `types` is abstract now, so it left python-style's `domain` map. Moves 10: RS-TRAIT-01, -11, -18,
  -32 into rust-style's new `types.md` (RS-TYPE-01 to -04); ZS-COMPTIME-11, -12, -15, -19 and ZS-ERR-27 into
  zig-style's new `types.md` (ZS-TYPE-01 to -05); PS-DATA-07 into python-style's types (PS-TYPE-21). The
  `traits` and `comptime` chapters stay domain chapters, their Scope and opening prose rewritten. Merges 0.
  New rules 3, all python-style, `Protocol` having no counterpart of the others: PS-TYPE-22 (a closed set is
  a union), -23 (a protocol's contract), -24 (a type parameter relates two positions); and one `Decided by
  tools` row (rust-style, `wildcard_enum_match_arm`). Tier changes 0; PS-DATA-07 retitled and widened to
  the seam it names (PS-TYPE-21). Look-alike notes 1 -> 1 (BV-MIG-03 / RS-MIG-02, for `migration`). Not
  registered, one standard or another chapter's subject: PS-API-07 (annotate every public signature; Rust
  and Zig signatures are typed by the language, so there is no second statement), PS-TYPE-12 (`Any` only
  with a reason) and PS-TYPE-03 (suppress with a code) against rust-style's `allow_attributes*` rows in
  `build`: suppressing a diagnostic is a build and lint concept, not type discipline, and left there;
  ZS-COMPTIME-07 (validate comptime parameters), -13 (`std.meta` predicates) and RS-TRAIT bounds rules
  (RS-TRAIT-29 to -31: where and how many bounds), each one language's mechanism; the rest of PS-TYPE
  (checker, lazy annotations, spellings) python-only; casts (ZS-DATA-09, RS-UNSAFE-15) stay `data` and
  the domain chapter `unsafe`. Left for `performance`: RS-TRAIT-12, -13 (static versus dynamic dispatch
  cost) and ZS-COMPTIME-08.
- [x] 3.10 `concurrency`: 15 entries (`AS-CONC-01` to `-15`) and one in `testing` (`AS-TEST-15`), in starting and
  owning tasks (the runtime started once at the entry, every task with an owner), cancellation and time
  (never swallowed, no state half-updated, protect only the step that must finish, every outside wait
  bounded), not blocking the scheduler (and no `async` that never waits) and sharing state (immutable
  without a lock, own data merged once, a queue over a locked structure, bounded queues, the shortest lock
  span, a lazily built value made once, a file replaced by renaming a temporary over it); realisations:
  python-style 15 `realises`; rust-style 12 `realises`, 2 `absent` (cancellation is a
  drop, so nothing to swallow or shield), 1 `decided` (clippy `unused_async`); zig-style 14 `realises`, 1
  `absent` (no function colour). Moves 10: PS-ASYNC-01, -03, -05 to -09 and -16 into python-style's
  concurrency (PS-CONC-24 to -31; `async.md` stays a domain chapter of 8 asyncio-only rules); RS-CONC-42
  into rust-style's testing (RS-TEST-17); RS-CLI-27 into rust-style's concurrency (RS-CONC-46). Merges 4: PS-CONC-16 into -17 (one memo claim, now PS-CONC-16, `[M!]` to `[M]`), PS-ASYNC-10 and -11 into -09 (never block the loop),
  RS-CONC-29 into RS-CONC-07 (the library takes the runtime). New rules 10: PS-CONC-11 (bound a
  `queue.Queue`), PS-CONC-23 (replace a file by renaming a temporary); ZS-CONC-40 (build a lazy value once); ZS-CONC-29 (state consistent at a cancellation point), -35 (every outside wait times
  out), -36 (share `const`), -37 (an `Io.Queue`), -38 (own accumulator, merge once), -39 (shortest
  `Io.Mutex` span); ZS-TEST-16 (never sleep in a test). Tier changes 4: PS-CONC-04 (ex `[M!]`) to `[S]`,
  PS-CONC-09 and -22 to `[M]`, PS-CONC-28 (ex PS-ASYNC-07) to `[M]` with its relaxed form folded in.
  Look-alike notes 1 -> 1 (BV-MIG-03 / RS-MIG-02, for `migration`). Not registered, one standard or
  another chapter's subject: the GIL and free-threading rules of python-style (PS-CONC-01 to -03, -05 to
  -08, -13 to -22), iterators, and RS-CONC-11 to -18,
  -21 to -28, -33 to -45 (scoped threads, pools, poisoning, atomics, rayon, loom), RS-CONC-23 (lock
  order), the asyncio thread boundary (PS-ASYNC-03 to -06), ZS-CONC-27, -31 to -34, -40 to -42 (checkCancel
  in a loop, colourless code, deadline, batching, assertions at a suspension, callbacks); PS-TEST-22 /
  RS-FUNC-38 / ZS-CONC-33 (the clock as a parameter: a test rule, a functional-core rule and std's time API
  answer different questions); PS-TEST-26, -27 (python's threaded-test hazards). Left for `output`: PS-CONC-20
  (one `write` per record), ZS-CONC-09 (`io.lockStderr`), RS-CONC-42 (log with a task id); the Zig
  readers, writers, files, sockets and subprocesses (ZS-CONC-04 to -22, -44 to -49) are `output`'s or
  no entry's. Decided: PS-CONC-03 (check-then-act) and ZS-CONC-21 (which rename) are not
  the replace-by-rename claim and stay unregistered; Zig has no `Once` in std 0.17, so its lazy-value
  rule builds under an `Io.Mutex`. Left for `performance`: PS-PERF-12 to -15 and ZS-PERF-18 (model by workload,
  cache-line alignment).
- [x] 3.11 `output`: 12 entries (`AS-OUT-01` to `-12`), in where output goes (stdout against stderr, a
  record written whole, a library neither prints nor ends the process, an explicit checked flush, colour
  for a terminal honouring `NO_COLOR`), logging (diagnostics through the facade, a library logs under its
  own name and configures nothing), failure and exit status (a message, not a dump; a non-zero code of its
  own per class) and rendering a value (a programmer's rendering, kept from the user's, a second one
  named); realisations: python-style 10 `realises`, 1 `decided` (ruff `T201`), 1 `overrides` (PS-OUT-20:
  `str` falls back to `repr`); rust-style 12 `realises`; zig-style 11 `realises`, 1 `absent` (`{any}`
  renders every value, so no per-type programmer's rendering). Moves 14: RS-CLI-17, -20, -24, RS-PERF-20,
  RS-ERR-28, -29, RS-API-35, -36, -37 into rust-style's new `output.md` (RS-OUT-01 to -12; `output` is
  abstract, so not in `domain`; `cli` stays a domain chapter of argument parsing, a closed pipe,
  terminal-adaptive presentation, progress and signals); PS-CONC-19 into PS-OUT-15; ZS-CONC-09, -04,
  ZS-ERR-02 (retitled: a library never ends the process and never prints), ZS-CONC-50 into ZS-OUT-17 to
  -20. Merges 2: RS-ERR-30 into RS-ERR-28 (the cause chain in prose, no `Debug`, no backtrace), PS-OUT-12
  into PS-OUT-13 (a library's logger by `__name__`, configured by nothing). New rules 10: PS-OUT-16
  (library), -17 (flush), -18 (colour), -21 (second rendering), -23 (failure message), -24 (exit status);
  RS-OUT-02 (record in one locked call), -03 (library), -07 (library logs through the facade, installs no
  logger; `log` added to the rust verify crate's dependencies); ZS-OUT-22 (exit status). Tier changes 4:
  RS-ERR-28 to `[M]` (merged with `[S]` and `[S]`), ZS-OUT-07, -20, -24 to `[M]` (drift from `[S]`; the
  deviation clause folded into the statement). Look-alike notes 1 -> 1 (BV-MIG-03 / RS-MIG-02, for
  `migration`). Not registered, one standard: python-style's encoding, interpolation and locale rules
  (PS-OUT-01 to -11, -13, -22: Python alone names an encoding per open), rust-style's `BrokenPipe`
  (RS-CLI-18), terminal-adaptive presentation, machine-readable and stable format, progress (RS-CLI-19 to
  -23), `anyhow` in binaries and reporting every failure of a run (RS-ERR-27, -31), RS-CONC-42 (log with
  a task id), zig-style's specifier set, `std.fmt` API and `logFn` (ZS-OUT-01 to -15, -25), the writer
  and reader mechanics (ZS-CONC-04 to -22 at the time) and `std.Progress`. Decided: ZS-MEM-14 (a library
  propagates `error.OutOfMemory`) is the memory chapter's, as one case of AS-ERR-05, and stays. Left for
  `performance`: RS-PERF-19 (always buffer), RS-PERF-21, -23 and PS-OUT-05 (bytes when the data is bytes).
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
