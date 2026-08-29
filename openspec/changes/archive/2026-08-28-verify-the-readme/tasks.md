## 1. Settle where the exemption mapping lives

- [x] 1.1 Decide whether `WITHOUT_A_CONTROL` stays in `tests/test_controls.py` or moves beside the
  registry, given that a check now needs to read it too; verify whichever it is has exactly one copy
- [x] 1.2 If it moves, move the two tests that guard it with it — `test_no_exemption_outlives_its_check`
  and `test_every_exemption_gives_a_reason` — and verify both still fail when broken

## 2. The check

- [x] 2.1 Add a `scope="all"` check that parses the README's check table — the backticked name in the
  first column, and whether the third column is non-empty — and nothing else; verify it passes today
- [x] 2.2 Fail when a registered check has no row, and verify by registering a throwaway check
- [x] 2.3 Fail when a row names no registered check, and verify by adding a row for one that does not
  exist
- [x] 2.4 Fail when a row's third column is empty, and verify — this is the assertion that carries
  "every one was added because…", narrowed to what a machine can decide
- [x] 2.5 Verify it does *not* fire on rewording, column reordering, or style: change each in a copy
  and confirm the check stays quiet

## 3. The `controls` row states its real scope

- [x] 3.1 Rewrite the row to state the rule rather than a count — every check except those the
  exemption mapping names — and verify the wording no longer claims "every other check"
- [x] 3.2 Assert the README's phrasing matches the exemption mapping, so the row cannot go stale when
  a check is exempted or un-exempted; verify by exempting a fourth check in a copy
- [x] 3.3 Verify the check's failure message says what it checked and what it did not, so a passing
  run is not read as evidence that the notes are true

## 4. Wire it in

- [x] 4.1 Add the negative control, and verify `test_every_check_has_a_control` passes without a new
  entry in `WITHOUT_A_CONTROL` — there is no reason here that would justify one
- [x] 4.2 Add the new check's own row to the README table, and verify the check accepts it — the
  first thing it does is require itself to be documented
- [x] 4.3 Verify the derived tool-coverage set from `guard-the-guards` is unaffected: the new check
  declares no `needs` and must not appear in it

## 5. Re-verify

- [x] 5.1 Run `uv run agent-skill check` and verify all checks pass on all four skills
- [x] 5.2 Run the full `pytest` suite on an idle machine with disk space checked first, and verify the
  count grew only by the new tests
- [x] 5.3 Verify `--fast` and `controls` wall-clocks are within noise of 22.3s and 12.3s
- [x] 5.4 Record in `design.md` what the check found that reading the file had not
