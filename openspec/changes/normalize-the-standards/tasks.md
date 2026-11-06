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
- [ ] 2.7 Section 4 as a projection (decision 7): `fmt` renders it from chapter IDs; `skeleton` fails
  on a drifted line and on any `CORE` rule
- [ ] 2.8 Lint bijection (decision 8) in `citations`
- [ ] 2.9 Migration as a function (decision 9): the table schema, uniqueness, the generated grep in
  `fmt`, and each toolchain's verifier of `gone` rows (run with `toolchain`)
- [ ] 2.10 The delta map (decision 10) in `crossref`
- [ ] 2.11 Examples under the shipped configuration minus the allowlist (decision 12)
- [ ] 2.12 Description template, SKILL.md bound, time-sensitive and provenance phrasing (decision 13)

## 3. python-style

- [ ] 3.1 Normalise python-style to every property in section 2, merging and demoting with
  `revise`; set `normalized`; full suite and its toolchain pass

## 4. rust-style

- [ ] 4.1 Normalise rust-style; set `normalized`; full suite and its toolchain pass

## 5. bevy-style

- [ ] 5.1 Normalise bevy-style, including the delta map against rust-style's final IDs; set
  `normalized`; full suite and its toolchain pass

## 6. zig-style

- [ ] 6.1 Normalise zig-style, including section 2's restructuring and SKILL.md under 500 lines; set
  `normalized`; full suite and its toolchain pass

## 7. Close

- [ ] 7.1 Delete `Profile.normalized` and every condition on it
- [ ] 7.2 Re-measure section 1.1's counts and record them here; run the full check once
- [ ] 7.3 README sections that describe the standards' shape; `documented` passes

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
| lints the configuration sets one by one with no row | 16 of 23 | 17 of 17 | 3 of 25 | none |
| rules whose Check is only a lint | 0 | 2 | 0 | 0 |
| migration status values used (declared) | 0 (0) | 0 (0) | 0 (0) | 25 (3) |
| old spellings in two migration rows | 1 | 0 | 0 | 9 |
| section 2 subsections, lines | 3, 71 | 4, 50 | 3, 51 | 10, 208 |
| section 2 laid out otherwise than 2.1-2.3 | 1 | 1 | 1 | 1 |
| a 2.2 subsection that is not one old/new/rule table | 0 | 0 | 0 | 0 |
| section 2 items naming no rule | 19 | 17 | 11 | 49 |
| description characters | 846 | 924 | 940 | 948 |
| SKILL.md lines | 338 | 312 | 348 | 560 |

Where a count differs from the proposal's, the definition differs, and the measure's is the one the
check holds: restated titles 84 against 85 (the statement opens with the title's words); prose
"grep" Checks 66 in bevy against 52 (`grep`, `rg` or "search for" anywhere in a Check outside a code
span, not only "grep for"); local `[M!]` scopes 30 rules in zig against 25 (any `[M!]` in a rule's
prose); rust's Checks that are only a lint 0 against 25 (a Check whose words, its code spans aside,
are tools' names, codes and joining words; the nine rust-style Checks that name a lint each say more
than it); status values 25 used against 28 (distinct cells under `Status`, emphasis and case
ignored); core-rule tier mismatches in two standards, not three (a core rule against every chapter
rule it cites). `fmt` clears the two citation rows and the out-of-order row of a normalised standard
by construction (`tests/test_normal_form.py`); the rest are a person's. bevy's lint row counts its
own rows only: whether a delta owes a row its anchor already states is 2.8's and 2.10's to decide.
`check --fast` 23 s, all passed; pytest 1,002 passed, 7 deselected, 2 min 14 s; FAIL branches 203 →
220, controls 181 → 198, exemptions 22.
