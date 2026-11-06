## 1. Baseline and carried items

- [ ] 1.1 Record, per standard, the counts this change moves: chapters per template, rules per
  element order, restated titles, rules with more than one GOOD or BAD, citation forms, prose
  "grep" Checks, local `[M!]` scopes, `[M]` titles in the mood of advice, core rules and their
  tier mismatches, configured lints without a row and rules whose Check is only a lint, migration
  status values and duplicate old spellings, description length, SKILL.md lines
- [ ] 1.2 Carried from `one-parse-one-print`: profile maps (`exempt`, `not_decisive`, `fires`,
  `unproven`, `unless_own`) keyed by `RuleId`; `self-application` and `crossref` hit lists through
  the one location printer

## 2. The properties, as checks gated by `normalized`

- [ ] 2.1 `Profile.normalized: bool`, default false; every check below applies only where it is true,
  each with a control run against a normalised fixture
- [ ] 2.2 Chapter template and rule shape (decisions 1, 2) in `skeleton`/`anatomy`; `fmt` orders a
  rule's elements
- [ ] 2.3 Bare-ID citations (decision 3): `fmt` rewrites quoted and path-qualified forms; `anatomy`
  fails on them
- [ ] 2.4 A Check that names a pattern runs it (decision 4)
- [ ] 2.5 Section 2's three subsections and owners (decision 5) in `skeleton`
- [ ] 2.6 Tier as one predicate (decision 6) in `anatomy`
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
