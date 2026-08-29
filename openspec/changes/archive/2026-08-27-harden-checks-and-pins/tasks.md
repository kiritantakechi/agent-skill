## 1. Audit before touching anything

- [x] 1.1 Record the baseline the whole change is judged against: run the full suite and capture the
  current tier counts per skill (tier 1 / tier 2 / tier 3) and the `--fast` wall-clock, so a
  promotion that changes something unintended is visible as a number rather than a feeling
- [x] 1.2 Enumerate every candidate into a working list — rule id, skill, current Check text, which
  of the three classes it falls in — and verify the totals match the measured 186 / 99 / 133 split
- [x] 1.3 Audit the harness for duplication the split should resolve, and verify the two already
  known are in the list: `dialect.py` carries its own `QUOTED` and bracket scanner that
  `patterns_of` also has, and `_HELD` keeps every temporary directory alive for the process
- [x] 1.4 Record what `controls` costs and why — 44.5s of a 77s run, rebuilding a corpus per
  control — and decide from the audit whether it is addressed here or recorded as debt

## 2. Split the harness

- [x] 2.1 Extract `patterns.py` — `Pattern`, `dialect_of`, `patterns_of` — and verify the full suite
  passes with no rule text changed
- [x] 2.2 Extract `corpus.py` — `Unit`, `Corpus`, `corpus_for` — and verify `crossref` imports from
  it rather than from a check module
- [x] 2.3 Extract `search.py` — `Span`, `searcher_problem`, the `rg` invocation — and verify
  `selfapply.py` retains only tiering and rendering
- [x] 2.4 Delete `dialect.py`'s duplicate `QUOTED` and bracket scanner in favour of the extracted
  ones, and verify its negative control still fires on an untranslated BRE alternation
- [x] 2.5 Bound the temporary-directory lifetime so a `controls` run does not accumulate one per
  control, and verify by counting live directories after a full run
- [x] 2.6 Scope each control's check run to the skill it injected into, deriving the scope from the
  control rather than assuming it, and keep the whole set for cross-skill checks (`crossref`,
  `mirror`); verify every control still fires and measure the new `controls` wall-clock against 38.7s
- [x] 2.7 Verify the split changed no behaviour: tier counts per skill identical to 1.1

## 3. Extend `pins` to every tool

- [x] 3.1 Cover `ruff`, `ty`, `pytest` and `rg` alongside the interpreter, reusing `version_mismatch`
  from `proc.py` rather than reimplementing it; verify each reports a failure when the running
  version differs from the pin
- [x] 3.2 Verify an unfindable pin is reported as the finding, not read as agreement — the defect the
  first version of `version_mismatch` shipped with
- [x] 3.3 Report a superseded pin by comparing against the newest release on the index, and verify it
  fires by pinning a deliberately old version
- [x] 3.4 Verify an unreachable index yields `UNRUN`, never "up to date", and verify the run
  withholds its pass
- [x] 3.5 Add the negative controls for 3.1 and 3.3, and verify `test_every_check_has_a_control`
  still passes without an exemption

## 4. Positive controls, before any pattern depends on them

- [x] 4.1 Add the mechanism: a rule may declare a fixture exhibiting its own defect, and the rule's
  pattern is asserted to match it. Verify it passes for one hand-written example
- [x] 4.2 Verify it fails when a pattern stops matching its fixture — edit the pattern to something
  narrower and confirm the failure names the rule
- [x] 4.3 Verify a pattern matching neither the compliant corpus nor its own fixture is reported as
  unable to fire, rather than passing on an empty result
- [x] 4.4 Verify a fixture whose rule no longer exists is reported, the same way a stale
  `not_decisive` entry is

## 5. Land what the measurement decided

- [x] 5.1 Record all 52 spans that fire on compliant examples as non-deciding, each with the measured
  reason — how many compliant examples its promotion accused — rather than a judgement; verify every
  entry's anchor still quotes text its Check contains
- [x] 5.2 Verify the 52 stay tier 2 and that `self-application` reports them with the recorded reason
  rather than the generic "prose span" default
- [x] 5.3 Verify no entry names a rule its skill does not define, the failure mode `not_decisive`
  already guards

## 6. Promote the ones that earn it

- [x] 6.1 From the 134 that passed specificity, promote only those whose Check states the hit *is*
  the finding with no qualifier the pattern cannot see; verify each promotion keeps tier 1 empty
- [x] 6.2 Write a positive control for every promotion, taken from the rule's own `BAD` example where
  one exists; verify `sensitivity` reports each as firing
- [x] 6.3 Verify the `dialect` check passes — no promoted pattern carries BRE syntax
- [x] 6.4 Record the promotion rate: how many of 186 were promoted, and how many of those had an
  existing defect example rather than a fixture written for them

## 7. Record the rest as measured debt

- [x] 7.1 Record in `design.md` the 134-minus-promoted remainder with the number, so a later change
  starts from the measurement rather than repeating it
- [x] 7.2 Record the 99 Checks that name no pattern as untouched, with the reason: authoring 99
  patterns and 99 fixtures is a body of work this change measured but did not take on
- [x] 7.3 Verify the worklist and the recorded numbers agree with a fresh count

## 8. `python-style` — the control group

- [x] 8.1 Verify `python-style` has 0 spans and 3 authorable Checks against 81 existing commands, and
  record it as the evidence that command discipline is possible where the predicates allow it
- [x] 8.2 Verify `python-style`'s tier 1 is still empty and its 81 commands are unchanged

## 9. Re-verify and record

- [x] 9.1 Run `uv run agent-skill check` and verify all checks pass on all four skills
- [x] 9.2 Run the full `pytest` suite on an idle machine with disk space checked first, and verify no
  regression
- [x] 9.3 Compare tier counts against the 1.1 baseline and verify every difference is an intended
  promotion, naming any that is not
- [x] 9.4 Record in `design.md` the final numbers: how many Checks decide now against 133 before, how
  many of the 285 candidates resisted promotion, and what the `--fast` wall-clock became
- [x] 9.5 Verify the rule counts stated in `SKILL.md`, `README.md` and each chapter's contents table
  are still true, since promotion changes no rule count but authoring may add `not_decisive` entries
  that the anatomy check cross-references
