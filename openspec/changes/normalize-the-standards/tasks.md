## 1. Baseline and carried items

- [x] 1.1 Record, per standard, the counts this change moves: chapters per template, rules per
  element order, restated titles, rules with more than one GOOD or BAD, citation forms, prose
  "grep" Checks, local `[M!]` scopes, `[M]` titles in the mood of advice, core rules and their
  tier mismatches, configured lints without a row and rules whose Check is only a lint, migration
  status values and duplicate old spellings, description length, SKILL.md lines — `1324592`;
  `agent-skill measure` prints them, those a gated check decides counted by running it on the
  standard read as normalised; see "Baseline (measured)"
- [x] 1.2 Carried from `one-parse-one-print`: profile maps (`exempt`, `not_decisive`, `fires`,
  `unproven`, `unless_own`) keyed by `RuleId`; `self-application` and `crossref` hit lists through
  the one location printer — `579520d` (and `Mirror.pairs`; spelled through `keyed`/`rules`),
  `6de405b` (`Corpus.origin` returns a `Location`); findings identical, hit lines re-rendered

## 2. The properties, as checks gated by `normalized`

- [x] 2.1 `Profile.normalized: bool`, default false; every check below applies only where it is true,
  each with a control run against a normalised fixture — `6f895b4`; the fixture is `checks.demo`,
  read with its own profile through `Control.profiles` (design, decision 14); all four stay false
- [x] 2.2 Chapter template and rule shape (decisions 1, 2) in `skeleton`/`anatomy`; `fmt` orders a
  rule's elements — `6f895b4`; `Rule.parts` in the chapter layer, `doc.normal.in_order`;
  `skeleton.title_code`, `no_scope`, `decided_last`, `chapter_named`; `anatomy.restated_title`,
  `element_order`, `stray`, `polarity`, `relaxed_tier`; the how-to-use passage names no path
  (`35d5f73`)
- [x] 2.3 Bare-ID citations (decision 3): `fmt` rewrites quoted and path-qualified forms; `anatomy`
  fails on them — `6f895b4`; `doc.normal.bare`, table cells included; `anatomy.quoted_citation`,
  `path_citation`; `fmt` rewrites a normalised standard only, so it is a no-op on today's tree
- [x] 2.4 A Check that names a pattern runs it (decision 4) — `6f895b4`; `anatomy.prose_grep`
- [x] 2.5 Section 2's three subsections and owners (decision 5) in `skeleton` — `6f895b4`;
  `reality_sections`, `reality_table`, `reality_owner`; an owner is a cited rule ID of the standard
- [x] 2.6 Tier as one predicate (decision 6) in `anatomy` — `6f895b4`; `anatomy.local_scope`,
  `advice_title`
- [x] 2.7 Section 4 as a projection (decision 7): `fmt` renders it from chapter IDs; `skeleton` fails
  on a drifted line and on any `CORE` rule — the IDs section 4's lines name are the source
  (`doc.normal.listed`/`projection`, one `Contents`); `skeleton.core_rule`, `core_drift`; the
  core-citation branches not run for a normalised standard; two shared sentences are slots
- [x] 2.8 Lint bijection (decision 8) in `citations` — `unrowed`, `rowed_twice`, `row_reason`
  (`listed because …` in Forbids), `only_lint`; `Toolchain.configured` gives each lint's level, and
  a delta owes a row only where it departs from its anchor's configuration
- [x] 2.9 Migration as a function (decision 9): the table schema, uniqueness, the generated grep in
  `fmt`, and each toolchain's verifier of `gone` rows (run with `toolchain`) — `| Old | <target> |
  Status | Rule |`, 2.2 the same less Status; `skeleton.migration_table`, `migration_row`,
  `migration_twice`, `migration_command`, `reality_row`; `Toolchain.probe` and
  `toolchain.gone_live` (exempt as `COMPILES`, exercised by `tests/test_gone.py`)
- [x] 2.10 The delta map (decision 10) in `crossref` — `| <anchor> rule | Relation | <delta> rule
  | Tier | Reason |`; `crossref.relation`, `departure_tier`, `departs`, `redefines` (and the table
  read by `delta_no_table`, `override_target`); `mirror.restated`; override cells read bare too
- [x] 2.11 Examples under the shipped configuration minus the allowlist (decision 12) —
  `PythonSnippet.allowlist` (six codes, each with its reason); a normalised standard's advice blocks
  are linted with `--config <shipped ruff.toml> --ignore=<allowlist>`; `citations.allow_reason`
- [x] 2.12 Description template, SKILL.md bound, time-sensitive and provenance phrasing (decision 13)
  — `shared/description.md`, `Use when …. Applies to …. Targets {language} {target}.`;
  `frontmatter.template`, `counted`, `bounded` (500); `skeleton.skill_md_lines`; `prose.dated`

Section 2 as built: FAIL branches 220 → 243, controls 198 → 220, exemptions 22 → 23
(`toolchain.gone_live`, as `COMPILES`); `check --fast --verbose` byte-identical throughout. Each
standard read as normalised now also fails: `core_rule` (bevy 24, python 26, rust 28, zig 29),
`migration_table` (one each), `frontmatter.template`, `counted`, `bounded` (one each),
`skill_md_lines` (zig), and, for bevy, `crossref.delta_no_table` and `redefines`.

## 3. python-style

- [x] 3.1 Normalise python-style to every property in section 2, merging and demoting with
  `revise`; set `normalized`; full suite and its toolchain pass — 26 core rules merged into the
  chapter rules they abbreviated (`revise` learned to take them), a `modules` chapter, one migration
  table, two demotions and three merges; see the design's "As built (task 3.1)". `measure`, before
  → after: rules 236 → 232, chapters with a family code 13 → 14, element orders 5 → 4, out of order
  1 → 0, citations bare/quoted/behind a path 80/8/30 → 204/0/0, prose "grep" Checks 5 → 0, advice
  titles 10 → 0, core rules 26 → 0, unrowed lints 17 of 17 → 0 of 17, only-lint Checks 2 → 0, rows
  saying no reason 46 → 0, migration statuses 0 → 4, section 2 4 subsections, 50 lines → 3, 73,
  laid out otherwise 1 → 0, items naming no rule 17 → 0, description 1011 → 412 characters,
  SKILL.md 312 → 284 lines, dated statements 7 → 0

## 4. rust-style

- [x] 4.1 Normalise rust-style to every property in section 2, merging and removing with `revise`;
  set `normalized`; full suite, its toolchain (every `gone` row probed, the standard library's
  source added as `rust-src`) and its mutation check pass — 28 core rules merged into the chapter
  rules they abbreviated, seven merges and one removal (E0119), one migration table, and an
  attribute probe; see the design's "As built (task 4.1)". `measure`, before → after: rules 605 →
  597, chapter titles carrying a family code 7 → 0, chapters with no `Scope:` 7 → 0, chapters named
  outside §6 1 → 0, element orders 8 → 6, out of order 1 → 0, restated titles 84 → 0, citations
  bare/quoted/behind a path 84/81/101 → 282/0/0, prose "grep" Checks 122 → 0, advice titles 29 →
  0, core rules 28 → 0, core tier mismatches 5 → 0, unrowed lints 3 of 25 → 0 of 25, rows saying no
  reason 47 → 0, migration statuses 0 → 4, section 2 3 subsections, 51 lines → 3, 44, laid out
  otherwise 1 → 0, items naming no rule 11 → 0, description 1020 → 432 characters, SKILL.md 348 →
  267 lines, dated statements 14 → 0

## 5. bevy-style

- [x] 5.1 Normalise bevy-style, including the delta map against rust-style's final IDs; set
  `normalized`; full suite, its toolchain (every `gone` row probed absent in the pinned 0.20.1
  crates, the ones the registry lacked fetched) and its mutation check pass — 24 core rules merged
  into the chapter rules they abbreviated, one departures table of ten rows against rust-style's
  final IDs, two restatements removed as citations, five merges and a split, fourteen migration
  rules merged into the rules owning their rows, one migration table, and two probe fixes; see the
  design's "As built (task 5.1)". `measure`, before → after: rules 194 → 174, element orders 5 → 3,
  chapters named outside §6 8 → 0, citations bare/quoted/behind a path 116/22/46 → 502/0/0, prose
  "grep" Checks 66 → 0, advice titles 4 → 0, core rules 24 → 0, rows saying no reason 3 → 0, rows
  the anchor's 7 → 0, migration statuses 0 → 3, old spellings in two rows 1 → 0, section 2 3, 71
  lines → 3, 212, laid out otherwise 1 → 0, items naming no rule 19 → 0, description 926 → 442
  characters, SKILL.md 338 → 415 lines, dated statements 6 → 0

## 6. zig-style

- [x] 6.1 Normalise zig-style, including section 2's restructuring and SKILL.md under 500 lines; set
  `normalized`; full suite, its toolchain and its mutation check pass — core rules merged, one
  migration table, compiler rows, merges and moves to one owner, every Check run or judged; see the
  design's "As built (task 6.1)". `measure`, before → after: rules 356 → 343, chapters with no
  `Scope:` 5 → 0, chapters named outside §6 36 → 0, element orders 28 → 4, out of order 30 → 0,
  stray blocks 153 → 0, doubled verdicts 21 → 0, relaxed forms off `[M!]` 1 → 0, citations
  bare/quoted/behind a path 426/27/168 → 842/0/0, prose "grep" Checks 49 → 0, `[M!]` scope restated
  30 → 0, advice titles 3 → 0, core rules 29 → 0, core tier mismatches 5 → 0, migration statuses 25
  (3) → 4 (0), old spellings in two rows 9 → 0, section 2 10, 208 lines → 3, 88, laid out otherwise
  1 → 0, items naming no rule 49 → 0, description 1015 → 411 characters, SKILL.md 560 → 326 lines,
  dated statements 27 → 0

## 7. Close

- [x] 7.1 Delete `Profile.normalized` and every condition on it — every check, `fmt` and `measure`
  hold every standard to the normal form; the branches only a standard not yet normalised reached
  went with their controls (the core-citation three and the `mis_cited` note, `map_here`,
  `frontmatter.length` and `rule_count`, the override table's `override_title` and `no_table`), and
  `tests/structure_fixture.py` builds `checks.demo`, the one demo; see the design's "As built (task
  7.1)". FAIL branches 243 → 236, controls 220 → 213, exemptions 23; `fmt` changes nothing in the
  shipped tree, and `check --fast --verbose` is byte-identical
- [x] 7.2 Re-measure section 1.1's counts and record them here; run the full check once — "After
  (measured)" below: every count of the normal form is 0 in every standard; rules 174, 232, 597,
  343; descriptions 442, 412, 432, 411 characters; `SKILL.md` 293, 299, 266, 327 lines. On
  `8c6cc71`: `check`, toolchains and mutation included, all passed in 26 min 34 s; `pytest -q`
  1,116 passed in 42 min 8 s, the toolchain tests among them; `ruff check`, `ruff format --check`
  and `ty check` clean
- [x] 7.3 README sections that describe the standards' shape; `documented` passes — "Every standard
  has one shape" states the normal form (chapter template, rule shape, bare-ID citations, Checks as
  `rg` commands or judgement, tier as one predicate, §4 and §2's 2.1 and 2.2 as projections, the
  migration table's statuses and Since, the lint bijection, the departures table, the description
  template) and what `measure` counts; the command list, `revise`, `fmt`, a Python snippet's
  allowlist, and the `frontmatter`, `anatomy`, `skeleton`, `prose`, `mirror`, `crossref`,
  `toolchain` and `citations` rows say what each checks now; nothing describes the gate, a core rule
  or the override table, and the `mis_cited` note is recorded as gone with §4's own rules

## Baseline (measured)

Taken before any standard is normalised, and printed as `uv run agent-skill measure` prints it. The
tree's content is `74e65a5`'s but for the how-to-use passage, which names no chapter's path since
`35d5f73` (one `chapter_named` fewer per standard). A count of a property a gated check decides is
that check's findings on the standard read as normalised; every row's definition is the docstring
of its function in `agent_skill.measure`, and of the branch it counts.

| Measure | bevy-style | python-style | rust-style | zig-style |
|---|---|---|---|---|
| chapters with a family code | 11 | 13 | 16 | 13 |
| chapter titles carrying a family code | 0 | 0 | 7 | 0 |
| chapters with no `Scope:` paragraph | 0 | 0 | 7 | 5 |
| chapters with a section after `Decided by tools` | 0 | 0 | 0 | 0 |
| chapters named outside §6 and a `Scope:`, no ID after | 8 | 0 | 1 | 36 |
| rules | 194 | 236 | 605 | 356 |
| distinct element orders | 5 | 5 | 8 | 28 |
| rules with their elements out of order | 0 | 1 | 1 | 30 |
| rules holding a block no element holds | 0 | 0 | 0 | 153 |
| restated titles | 0 | 0 | 84 | 0 |
| rules with more than one GOOD or BAD | 0 | 0 | 0 | 21 |
| relaxed forms on a rule that is not `[M!]` | 0 | 0 | 0 | 1 |
| citations bare | 116 | 80 | 84 | 426 |
| citations quoted | 22 | 8 | 81 | 27 |
| citations behind a chapter's path | 46 | 30 | 101 | 168 |
| prose "grep" Checks | 66 | 5 | 122 | 49 |
| rules restating the `[M!]` scope | 0 | 0 | 0 | 30 |
| `[M]` and `[M!]` titles in the mood of advice | 4 | 10 | 29 | 3 |
| core rules | 24 | 26 | 28 | 29 |
| core rules at another tier than a rule they cite | 0 | 0 | 5 | 5 |
| lints the configuration sets one by one with no row | none | 17 of 17 | 3 of 25 | none |
| rules whose Check is only a lint | 0 | 2 | 0 | 0 |
| rows of a lint not set one by one, saying no reason | 3 | 46 | 47 | 0 |
| rows of a lint another row, or the anchor's, lists | 7 | 0 | 0 | 0 |
| migration status values used (declared) | 0 (0) | 0 (0) | 0 (0) | 25 (3) |
| old spellings in two migration rows | 1 | 0 | 0 | 9 |
| section 2 subsections, lines | 3, 71 | 4, 50 | 3, 51 | 10, 208 |
| section 2 laid out otherwise than 2.1-2.3 | 1 | 1 | 1 | 1 |
| a 2.2 subsection that is not one old/new/rule table | 0 | 0 | 0 | 0 |
| section 2 items naming no rule | 19 | 17 | 11 | 49 |
| description characters | 926 | 1011 | 1020 | 1015 |
| SKILL.md lines | 338 | 312 | 348 | 560 |
| statements dated by their writing | 6 | 7 | 14 | 27 |

Where a count differs from the proposal's, the definition differs, and the measure's is the one the
check holds: restated titles 84 against 85 (the statement opens with the title's words); prose
"grep" Checks 66 in bevy against 52 (`grep`, `rg` or "search for" anywhere in a Check outside a code
span, not only "grep for"); local `[M!]` scopes 30 rules in zig against 25 (any `[M!]` in a rule's
prose); rust's Checks that are only a lint 0 against 25 (a Check whose words, its code spans aside,
are tools' names, codes and joining words; the nine rust-style Checks that name a lint each say more
than it); status values 25 used against 28 (distinct cells under `Status`, emphasis and case
ignored); core-rule tier mismatches in two standards, not three (a core rule against every chapter
rule it cites). `fmt` clears the two citation rows and the out-of-order row of a normalised standard
by construction (`tests/test_normal_form.py`); the rest are a person's. bevy's lint row read 16 of 23
when it counted its own rows only; 2.8 decided that a delta owes a row only where its configuration
departs from its anchor's, and bevy-style's two departures are `allow`, so it owes none, and its 7
rows of lints it sets as rust-style does are the anchor's (the two rows 2.8 added count them).
`frontmatter.described` read a description without its last line, as the frontmatter ends without
a newline (846, 924, 940, 948 before 2.10 fixed it; every finding stayed the same).
`check --fast` 23 s, all passed; pytest 1,002 passed, 7 deselected, 2 min 14 s; FAIL branches 203 →
220, controls 181 → 198, exemptions 22.

## After (measured)

Taken after task 7.1 deleted the gate, on `8c6cc71`, and printed as `uv run agent-skill measure`
prints it. Each standard is read as it is, since every check of the normal form now holds every
standard. The baseline's row of a 2.2 subsection that is not one table is two rows here, one per
subsection the migration table renders (design, decision 9).

| Measure | bevy-style | python-style | rust-style | zig-style |
| --- | --- | --- | --- | --- |
| chapters with a family code | 11 | 14 | 16 | 13 |
| chapter titles carrying a family code | 0 | 0 | 0 | 0 |
| chapters with no `Scope:` paragraph | 0 | 0 | 0 | 0 |
| chapters with a section after `Decided by tools` | 0 | 0 | 0 | 0 |
| chapters named outside §6 and a `Scope:`, no ID after | 0 | 0 | 0 | 0 |
| rules | 174 | 232 | 597 | 343 |
| distinct element orders | 3 | 4 | 6 | 4 |
| rules with their elements out of order | 0 | 0 | 0 | 0 |
| rules holding a block no element holds | 0 | 0 | 0 | 0 |
| restated titles | 0 | 0 | 0 | 0 |
| rules with more than one GOOD or BAD | 0 | 0 | 0 | 0 |
| relaxed forms on a rule that is not `[M!]` | 0 | 0 | 0 | 0 |
| citations bare | 381 | 219 | 286 | 842 |
| citations quoted | 0 | 0 | 0 | 0 |
| citations behind a chapter's path | 0 | 0 | 0 | 0 |
| prose "grep" Checks | 0 | 0 | 0 | 0 |
| rules restating the `[M!]` scope | 0 | 0 | 0 | 0 |
| `[M]` and `[M!]` titles in the mood of advice | 0 | 0 | 0 | 0 |
| core rules | 0 | 0 | 0 | 0 |
| core rules at another tier than a rule they cite | 0 | 0 | 0 | 0 |
| lints the configuration sets one by one with no row | none | 0 of 17 | 0 of 25 | none |
| rules whose Check is only a lint | 0 | 0 | 0 | 0 |
| rows of a lint not set one by one, saying no reason | 0 | 0 | 0 | 0 |
| rows of a lint another row, or the anchor's, lists | 0 | 0 | 0 | 0 |
| migration status values used (declared) | 3 (0) | 4 (0) | 4 (0) | 4 (0) |
| old spellings in two migration rows | 0 | 0 | 0 | 0 |
| section 2 subsections, lines | 3, 90 | 3, 88 | 3, 43 | 3, 89 |
| section 2 laid out otherwise than 2.1-2.3 | 0 | 0 | 0 | 0 |
| a 2.1 subsection that is not its rendering | 0 | 0 | 0 | 0 |
| a 2.2 subsection that is not its rendering | 0 | 0 | 0 | 0 |
| section 2 items naming no rule | 0 | 0 | 0 | 0 |
| description characters | 442 | 412 | 432 | 411 |
| SKILL.md lines | 293 | 299 | 266 | 327 |
| statements dated by their writing | 0 | 0 | 0 | 0 |
