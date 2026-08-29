## 1. Pin the tool

- [x] 1.1 Add `ripgrep-bin==15.2.0` to the `dev` group, `uv sync`, and verify `uv run rg --version`
  reports 15.2.0 — an exact pin, because `rg` now decides whether 144 checks fire
- [x] 1.2 Register `rg` in the missing-tool path so an environment without it is reported as `UNRUN`
  rather than clean, and verify by probing with a deliberately wrong tool name
- [x] 1.2a Resolve `rg` to the pinned binary rather than to whatever `PATH` offers, and verify the
  engine cannot silently use the host's `rg` — measured: `shutil.which("rg")` resolves to
  `/run/current-system/sw/bin/rg` today, so pinning `ripgrep-bin` in `dev` does not by itself
  determine which binary executes
- [x] 1.2b Assert at run time that the executing `rg --version` matches the pin, and fail loudly on a
  mismatch — the same lesson as a standard claiming verification against a `ruff` the harness was not
  actually running
- [x] 1.3 Verify the `pins` check covers the new pin the way it covers `ruff` and `ty` — a stale
  `rg` pin must fail rather than drift

## 2. Equivalence harness, built before anything moves

- [x] 2.1 Write a migration-only harness that, for one pattern, runs the old spelling the way the
  engine runs it today and the new spelling under `rg` over the same corpus file, and compares
  matched line-number sets
- [x] 2.2 Verify the harness reproduces today's hit sets exactly across all 144 current patterns
  with zero translations applied — if it cannot agree with the present, it cannot judge the future
- [x] 2.3 Record the harness's measured blind spot rather than assuming coverage: 492 of 670
  patterns (97 of 137 command patterns) have empty hit sets, so equality cannot see them. Verify the
  number by counting the captured baseline, and verify the harness passes an injected untranslated
  BRE — it does, and that is the finding, not a bug to fix here

## 2b. Mechanical translation and a syntactic guard

- [x] 2b.1 Write the BRE→ERE transformation as a function — `\(`/`\)`/`\|`/`\{`/`\}` unescaped, the
  bare forms escaped — and verify it against a table of known BRE/ERE pairs, including a bracket
  expression where `\|` is already literal and must not change
- [x] 2b.2 Verify the transformation is an involution on the swapped characters, and that the
  migration therefore dispatches on each command's declared dialect and never applies it to the 61
  already-ERE patterns — running it on an ERE faithfully translates back to BRE, which is correct
  behaviour and the reason it must not be applied blindly
- [x] 2b.3 Add a permanent check that no `rg` pattern contains `\|`, `\(`, or `\{`, decided from the
  pattern text with no corpus and no execution; verify it fires on `rg -n 'A\|B'`
- [x] 2b.4 Add the negative control for 2b.3: inject a BRE escape into a migrated Check and assert
  the check reports it

## 3. Split the corpus, before `-U` makes concatenation dangerous

- [x] 3.1 Rewrite `Corpus.build` to write each advisory block to its own file in the work directory,
  keeping the raw/code distinction, and verify hit sets are unchanged while still executing the old
  way with no `-U` — this step must be invisible in results
- [x] 3.2 Delete the parallel `index` array and derive file, rule, and line from the block's own
  path and local line number; verify reported locations are identical to before
- [x] 3.2a Update `crossref.py`, which is the second consumer of `Corpus` and reads
  `corpus.index[lines[0] - 1]` directly; verify its cross-standard anchor findings are unchanged,
  since deleting the index silently breaks it otherwise
- [x] 3.2b Build each skill's corpus once and share it between `selfapply` and `crossref` instead of
  each constructing its own; verify identical findings and that the work directory is written once —
  604 blocks become 604 files, and building them twice per run is 1208 writes for no gain
- [x] 3.3 Verify the "nothing to check" guard still fires when the split produces no blocks — an
  empty work directory passes every pattern in the library, which is the failure this guard exists
  for
- [x] 3.4 Verify a multi-line pattern cannot match across two blocks: assert that `try:` in one block
  and `finally:` in the next produce zero hits for a pattern that matched them when concatenated

## 4. Rebuild execution on rg's model

- [x] 4.1 Switch execution to `rg` with `--no-config` on every invocation, and verify a
  `RIPGREP_CONFIG_PATH` containing `-i` cannot change a result
- [x] 4.2 Read results from `--json` rather than parsing `-n` text, and verify a matched line
  containing a literal `:` is located correctly — the failure the colon-splitting could produce
- [x] 4.3 Enable `-U` and leave `--multiline-dotall` off. Verify `^`/`$` stay line-anchored and `.`
  stops at a newline, and verify the measured exception: `\s`, `\W`, `\D` and negated classes *do*
  cross a newline, so `^\s+if` collapses three adjacent hits into one three-line span. Equality is
  therefore provable only after 5.0 narrows those sixteen patterns
- [x] 4.4 Convert the hit model from line number to span, and verify a single-line match is a span of
  one line handled by the same path
- [x] 4.5 Change the `exempt` hook signature to take a span, update every existing hook, and verify
  each still suppresses exactly what it suppressed before
- [x] 4.6 Delete the `-F` retry and report a rejected pattern as a failure, per `check-execution`'s
  "a pattern that cannot match is a failure, never a pass"; verify with a pattern `rg` rejects
- [x] 4.7 Collapse `Pattern.mode` from three values to two — default regex for command patterns, `-F`
  for backticked prose spans — and verify `-F` composes with `-U` and `--json` on a prose span
  containing regex metacharacters
- [x] 4.8 Update `selfapply.py`'s module docstring: the BRE/ERE hazard it documents is being removed,
  and the `|x| f(x)` fixed-string history it records must survive

## 5. Translate the patterns, one skill at a time

- [x] 5.0 Narrow the 16 command patterns whose classes can match a newline — `\s` to `[ \t]` where
  horizontal whitespace was meant — and verify the equivalence harness reports no difference for any
  of them under `-U`
- [x] 5.1 `rust-style` — 9 commands, 2 BRE. Smallest surface, so it validates the workflow; verify
  the equivalence harness is green for all 9 before moving on
- [x] 5.2 `bevy-style` — 14 commands, 0 BRE. Mechanical `grep`→`rg` only; verify the harness reports
  no set differences
- [x] 5.3 `zig-style` — 37 commands, 28 BRE. Highest BRE density; verify the harness is green,
  paying particular attention to the `\|` alternations that silently match nothing if missed
- [x] 5.4 `python-style` — 84 commands, 53 BRE. Verify the harness is green
- [x] 5.5 Verify no `grep` command remains in any rule text across all four skills, and that all 144
  sites now read `rg`

## 6. Traversal, decided per Check rather than by default

- [x] 6.1 List every migrated Check whose path argument is a bare `.` or omits a path, and verify
  each still searches what its rule intends now that `rg` skips hidden files and honours ignore files
- [x] 6.2 For each Check that genuinely needs hidden or ignored files, add the explicit flag and
  record why in the rule; verify no blanket `--hidden --no-ignore` was added, which would make every
  check search `target/` and `node_modules/`
- [x] 6.3 Verify Checks naming an explicit hidden path — `.github/` and the like — still match, since
  an explicit path argument overrides the hidden-file rule

## 7. Two guards that do not guard

- [x] 7.1 Change `assets.py`'s two tool-missing paths from `note` to `unrun` — `_zig` when `zig` is
  absent and `_build` when `uv` is absent. Verify that with the tool removed the run withholds the
  pass: `Result.ok` is `not fails and not unrun`, so a `note` lets a run where nothing parsed the
  `build.zig` and nothing built the `pyproject.toml` report ALL CHECKS PASSED. Every other check —
  `citations`, `pins`, `toolchain` — already uses `unrun` here
- [x] 7.2 Verify no other `note` carries "nobody looked" semantics, and add a control that removes a
  required tool and asserts the run does not report success

## 8. Leave no trace

- [x] 8.1 Remove `grep` from `src/agent_skill/checks/selfapply.py`, `crossref.py`, `controls.py`,
  `model.py`, and `text.py`, and verify the full check run passes
- [x] 8.2 Rewrite the `NotDecisive` reasons in all four profiles — these are report text a user
  reads, not comments; verify by reading the rendered output of a run that emits tier-2 notes
- [x] 8.3 Update `README.md`'s description of the harness's decisive greps, and verify the count and
  the tool name it states are both true after this change
- [x] 8.4 Update `tests/test_selfapply.py` and `tests/test_model.py`, and verify the tests assert on
  `rg` behaviour rather than on grep dialect
- [x] 8.5 Verify no `grep` *invocation* and no reference to it as this harness's tool remains. Three
  mentions are correct and stay: `checks/dialect.py`, whose whole subject is the grep-to-rg hazard;
  the comment on `patterns_of`'s trigger, which still recognises the word because 247 Checks phrase
  themselves as "grep for `X`" and rewriting those is a stated non-goal; and the test that pins that
  behaviour

## 9. Land and clean up

- [x] 9.1 Delete the equivalence harness, and record in `design.md` that it passed, over how many
  patterns, and on what corpus
- [x] 9.2 Run `uv run agent-skill check` and verify all checks pass on all four skills
- [x] 9.3 Run the full `pytest` suite on an idle machine with disk space checked first, and verify no
  regression
- [x] 9.4 Verify the negative controls still fire — in particular any control that injects a
  grep-shaped defect must be rewritten to inject an `rg`-shaped one and must still be caught
