## 1. Establish the floor before deriving anything

- [x] 1.1 Record which checks depend on an external tool today and how each depends on it, and verify
  the count is 7 — this is the floor every derivation below is asserted against
- [x] 1.2 Verify the current `test_unrun` passes for the three it covers and would not catch the four
  it misses: remove `rg` and confirm `crossref`, `self-application` and `sensitivity` report `UNRUN`
  while no test asserts it

## 2. Derive the tool-coverage list

- [x] 2.1 Have each check declare the tools it needs, and verify the declaration covers what
  inspection cannot see — `pins` iterates a variable, so inspection reports `uv` while it also needs
  `ruff`, `ty`, `pytest` and `rg`
- [x] 2.2 Cross-check the two: a tool inspection finds that the declaration omits is a failure, and
  the declared set must never be empty or smaller than the 7 checks recorded in 1.1
- [x] 2.3 Parametrize `test_unrun` over the derived set and verify every one of the 7 withholds the
  pass with its tool absent — including `pins` against `ruff`, `ty`, `pytest` and `rg`, which it
  acquired without the list noticing
- [x] 2.4 Verify a check newly given a tool dependency is covered without editing any list: add a
  throwaway check that calls `have`, confirm it appears in the derived set, remove it

## 3. Give every exemption a reason

- [x] 3.1 Replace the bare exemption set in `test_every_check_has_a_control` with a mapping from
  check name to the reason it has no control, and verify the test still passes
- [x] 3.2 Write the reason for `controls`, `toolchain` and `mutation`. Where the reason is not
  knowable from the code, say so rather than inventing one — verify no entry claims a rationale the
  code does not support
- [x] 3.3 Verify an exemption naming a check that no longer exists fails, the way a stale
  `not_decisive` entry does: rename a check in a copy and confirm the failure
- [x] 3.4 Verify a newly added check with no control fails rather than being absorbed by an existing
  exemption

## 4. Move `CROSS_SKILL` onto the check

- [x] 4.1 Read the cross-skill distinction from the check rather than from a set of names in
  `controls.py`, and verify `crossref` and `mirror` are still scoped to the whole skill set
- [x] 4.2 Verify every control still fires after the change — `controls` asserts this, so a scoping
  mistake fails loudly
- [x] 4.3 Verify the `controls` wall-clock has not regressed from 14.9s, since the scoping is what
  bought that

## 5. Delete what nothing reaches

- [x] 5.1 Delete `Span.lines()` and verify nothing referenced it
- [x] 5.2 Delete `Corpus.excluded` and the computation that fills it, and verify the full suite passes
- [x] 5.3 Sweep the four modules extracted last change for anything else assigned and never read, and
  verify the sweep finds nothing further

## 6. Stop special-casing one check by name

- [x] 6.1 Let the check declare that it takes the `fast` argument rather than `cli.py` naming it, and
  verify `--fast` still skips the slow checks inside `controls`
- [x] 6.2 Verify no check name is hardcoded outside the check that owns it and the controls that
  target it, both of which are already validated by `by_name`

## 7. Test the pieces, not just the pipeline

- [x] 7.1 Unit-test `corpus.origin`: a line at a unit boundary, the first line, the last line, and a
  round-trip from a known global line back to its chapter and source line
- [x] 7.2 Unit-test `search.find`'s span arithmetic: a single-line match is a span of one line, a
  multi-line match covers exactly its lines, and text not ending in a newline is handled
- [x] 7.3 Unit-test `search.matches`'s three-valued contract, and verify `None` is distinguishable
  from `False` by a caller — the distinction the whole `UNRUN` level exists for
- [x] 7.4 Unit-test `dialect.outside_brackets`: `\|` as an operator, `\|` inside `[...]`,
  `[[:space:]]` closing on its outer bracket, `[]]` and `[^]]` where `]` is literal
- [x] 7.5 Verify the new tests fail when the logic they cover is broken, by breaking each one in turn

## 8. Re-verify

- [x] 8.1 Run `uv run agent-skill check` and verify all checks pass on all four skills
- [x] 8.2 Run the full `pytest` suite on an idle machine with disk space checked first, and verify the
  count grew by the new tests and nothing else changed
- [x] 8.3 Verify the `--fast` and `controls` wall-clocks are within noise of 22.6s and 14.9s
- [x] 8.4 Record in `design.md` what the derivation found that the hand-written lists did not
