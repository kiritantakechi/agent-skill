## 1. The dead path

- [x] 1.1 De-indent the anchor-pattern loop in `_anchor_patterns` so it runs; verify by asserting the
  function's last statement is the `for` and not the `if` (`ast.parse`), and that `agent-skill check`
  still reports `crossref` ok
- [x] 1.2 Record the baseline before the control changes: run the current `crossref` control against
  the fixed code and confirm it still passes for the wrong reason (it trips the citation branch), so
  the replacement has something to be measured against
- [x] 1.3 Find a `rust-style` `[M]` rule whose command pattern is decisive and whose id appears
  nowhere in `bevy-style/SKILL.md`; verify by computing the `named` set the check itself computes and
  asserting the id is absent from it
- [x] 1.4 Replace the `crossref` control with one that injects that rule's defect into a `bevy-style`
  example and leaves `SKILL.md` untouched; verify it passes against the fixed code
- [x] 1.5 Verify the new control **fails** with the loop re-indented under the `return` — Decision 0.
  A control not shown to fail on the reverted code is not accepted
- [x] 1.6 Make `_anchor_patterns` distinguish `find`'s `None` from `[]`, reporting a no-answer search
  as a failure the way `selfapply` does; verify with a unit test that feeds it a pattern `rg` rejects
  and asserts a FAIL rather than a skip

## 2. Guards that were not guarding

- [x] 2.1 Resolve a check's module in `test_a_declaration_is_not_missing_a_tool` via
  `inspect.getsourcefile(c.fn)` and fail on an unresolvable subject; verify by asserting the test now
  covers all six declaring checks, and that reformatting a decorator does not change coverage
- [x] 2.2 Confirm the newly-covered checks (`crossref`, `pins`, `sensitivity`) actually pass the
  cross-check, and declare any tool the source names that they do not — verify `pytest
  tests/test_unrun.py` is green
- [x] 2.3 Make `_sort_key` refuse to answer for a version it did not parse, and have `_tool_pins`
  report that as not-compared; verify with a unit test over `1.2.3.post1`, `0.16.5.dev0` and `2024.1`
  that none of them is read as "the pin is current"
- [x] 2.4 Parse `documented`'s reason column over the whole cell rather than `[^|]*`; verify by
  asserting the `dialect` row's reason reads back in full rather than as `` ` \ ``, that an escaped
  pipe anywhere in a reason does not end the cell, and that a genuinely empty reason is still empty.
  (Reworded during apply: the original clause asked that a reason of *only* `\|` fail, which the
  spec does not require — the scenario is about truncation, not about a minimum reason. Judging `\|`
  as absent would be this check deciding whether a reason is good, which it explicitly does not.)

## 3. A Check the reader can run

- [x] 3.1 Unwrap `PS-FMT-07` and `PS-MIG-05` so each `rg` command sits on one line; verify by
  extracting their patterns and asserting no `\n` survives, and that each still matches the defect it
  names. (`PS-MIG-05` unwrapped to one line is ~185 columns, over `layout`'s limit of 100, so it
  became four commands split on API family — each separately runnable, each family kept whole.
  `PS-FMT-07` fits on one line once its prose moves to its own.)
- [x] 3.2 Extend `dialect` to report a raw newline in an `rg` pattern, with a message naming the rule
  and why the printed command is rejected; verify `agent-skill check` is clean on the unwrapped tree
- [x] 3.3 Add the negative control for the new case — rewrap one of the two commands — and verify it
  fails on the reverted code per Decision 0
- [x] 3.4 Update the `dialect` row in `README.md` so its stated scope covers both cases, and verify
  `documented` still passes

## 4. sensitivity means every

- [x] 4.1 Before writing any fixture: count how many command patterns across all four profiles are
  declared in `fires` but unproven under the every-pattern rule, and record the number in
  `design.md`. If it is beyond this change, report them explicitly rather than absorbing them
- [x] 4.2 Change `fires` to `dict[str, tuple[str, ...]]` and convert the ten existing entries; verify
  each still matches its rule's pattern
- [x] 4.3 Assert the bipartite cover in `sensitivity`: every command pattern matches some fixture, and
  every fixture is matched by some pattern; verify with unit tests for both failure directions —
  an uncovered pattern and an orphan fixture
- [x] 4.4 Write the three further `ZS-MIG-13` fixtures (`pipeToFileSystem|PipeOptions|std.rand.|…`,
  `captureStackTrace|…`, `wtf8Decode|…`), plus whatever 4.1 found; verify `sensitivity` is green
- [x] 4.5 Update the `sensitivity` control so it still fires under the stricter rule, and verify it
  fails on the reverted code. (The existing control narrows a rule's *only* pattern, which `any` and
  every both report — so it could not discriminate. Two were added: one narrowing one pattern of
  four, one shifting a pattern's coverage onto a fixture another already covers so only the orphan
  direction reports. Both yield 0 FAIL under `any`; the pre-existing one still fires, correctly.)
- [x] 4.6 Correct the module docstring and the `sensitivity` row in `README.md` to state what is now
  asserted; verify `documented` passes

## 5. Prepared the same way

- [x] 5.1 Strip comments from a fixture in `matches` when the pattern does not search the raw text,
  mirroring `Corpus.build`; verify with a unit test that a comment-only fixture no longer certifies a
  code-only pattern
- [x] 5.2 Re-run all `fires` entries under the aligned preparation and confirm none regresses —
  `RS-DOC-23` and `RS-DOC-31` are the two whose fixtures are comments, and both pair with patterns
  that search the raw text

## 6. The pin, and the rest

- [x] 6.1 Make `pinned_version` return `None` when the declaration cannot be read, and reword
  `version_mismatch` to tell *no pin in the file* from *no file*; verify by installing the built wheel
  into a clean venv and asserting a complaint string rather than `FileNotFoundError`
- [x] 6.2 Clear the four small ones: the duplicate `return None, pattern.mode` branches in `find`;
  `exempt`'s type and comment (`int` → `Span`); the running total in `Corpus.build`; the frozen hit
  counts in `not_decisive` reasons across three profiles. Verify `ruff check`, `ty check`, and
  that a tier-2 note still prints its live count. (52 reasons, not ~40. Each was rewritten to name
  what the span finds and what decides — the main spec already required "naming what decides", and
  all 52 had been failing it. `ruff check` clean; `ty check` down 20 → 11, all remaining in
  production code this change did not author.)
- [x] 6.3 Full verification, run alone: `agent-skill check` (all checks ok), `pytest` (green), and
  `--fast` re-measured against the 22.3s baseline; record what moved. (Serial, nothing else running:
  full check ALL CHECKS PASSED in 4070.9s including `toolchain` and `mutation`; 208 passed in
  4925.4s; `--fast` 25.4s and 25.7s against a 22.3s baseline. See design.md for what moved.)

## 7. Close out

- [x] 7.1 Re-run the review's thirteen findings against the tree and confirm each is fixed, skipped
  with a reason, or found not to need a change
- [x] 7.2 Record in `design.md` what implementing this found that reading the diff had not
- [x] 7.3 `openspec validate close-the-dead-paths --strict`
