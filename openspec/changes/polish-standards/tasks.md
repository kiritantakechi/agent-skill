# Tasks

Work happens on branch `polish-standards`. A slow verification runs only after
`pgrep -f "pytest|cargo|zig (build|test)"` finds nothing. Slow means a standard's `toolchain` or
`mutation` check, or the full run. Every other verification is `--fast` or a targeted `pytest`.

Each standard's work list is its report in `research/`. The IDs there are the IDs before this
change. They stay valid until that standard's renumber, so each standard is done as one unit: what
its owners absorb, one `demote` plan, one renumber. bevy-style comes before rust-style because its
report cites rust-style IDs (D3).

## 1. Harness idioms (D8)

- [x] 1.1 Add one regex-group helper to `text.py`: "" for no match and for a group that took no
  part. It replaces `model._group` and every `str(m.group(…))` and `m.group(…) or ""`. Verify:
  - `rg -n '_group\(|str\([a-z_]+\.group\(|\.group\([^)]*\) or ""' src` finds nothing;
  - `uv run pytest -m "not toolchain"` passes.
- [x] 1.2 Where `None` and `""` mean the same thing, on a profile field, a parameter or a return,
  make the type `str` with `""` as the default, and test it as a plain truth value. `follows_local`
  keeps its `None`, because a blank reason there is a third state and the one that fails. Verify:
  - `rg -n 'not in \(None, ""\)|is not None and .* != ""| or ""' src tests` finds no site where the
    two are equivalent;
  - `uv run pytest -m "not toolchain"` passes.

## 2. Harness: the target-version branch (D1)

- [x] 2.1 Add the branch to `anatomy`'s `structural` checks:
  - the token `\b<major>\.(\d{2,})\b`, with a minor below the target, taken from `profile.pin()`;
  - the scope is the prose of every chapter rule outside `migration.md`, and of every core rule;
  - fenced examples are excluded;
  - the finding names the rule and the version.

  Unit tests:
  - a version below the target in a rule's prose fails;
  - the same version in a fenced block, in `migration.md`, in §2 or in the review protocol does not;
  - the target version and `3.5x` do not.

  Then save the list it reports on the real tree as `research/versions.txt`. That list is the
  annotation work list for groups 3–6. Verify: the four totals match the design's table: 13, 105,
  29 and 44 mentions for python, zig, bevy and rust.
- [x] 2.2 Add the control "(stable since 3.13)" inserted into a python-style rule, and its
  `BRANCHES` entry. Verify: `uv run pytest tests/test_controls.py`.
- [x] 2.3 Add the new branch to the README's `anatomy` row, with the defect it catches. Verify:
  `--fast --only documented`.

## 3. python-style (`research/python.md`)

- [ ] 3.1 Remove every version annotation in `research/versions.txt` for python-style (D2). A fact
  someone porting needs moves to `migration.md`. Verify: `--fast --skill python-style --only
  anatomy` reports no version below the target.
- [ ] 3.2 Merge the duplicates, A1–A25. Each owner first absorbs what its "Absorb" column names.
  Then one `agent-skill demote python-style <plan>` records each merge, and every leftover citation
  it reports is resolved. A core rule that misstates its chapter rule is rewritten (D3). Verify:
  `--fast --skill python-style --only anatomy --only crossref --only skeleton`.
- [ ] 3.3 Settle the lint-row notes. Cite `W505` in PS-NAME-15. Drop MIG-12's repeated
  `iscoroutinefunction` row and TYPE-12's `UP013`/`UP014` clause. Resolve PS-OUT-15 against `T201`,
  either with a per-file ignore for the entry point or by prescribing `sys.stdout.write`. Verify:
  `--fast --skill python-style --only citations --only lints`.
- [ ] 3.4 Apply B1–B13 (D6), each run on `cpython-3.15.0+freethreaded`. Re-read each rule's prose
  against its new example. An item that is only churn is skipped, and its reason added to
  `research/python.md`. Verify: python-style's `toolchain`, run alone.
- [ ] 3.5 Fix the defects (D7): the `random.Random(hash(…))` seed, ERR-11's Barrier claim,
  `context_aware_warnings` differing by build, PERF-18 and PERF-14 against DOC-14, and TEST-20's
  loop against TEST-08. Verify: the toolchain run of 3.4 covers each changed example.
- [ ] 3.6 Remove what §2 repeats from `migration.md` (D5). Verify: §2 keeps only the silent changes
  and the first loud ones, each citing its migration rule; `--fast --skill python-style --only
  skeleton --only anatomy`.
- [ ] 3.7 Run one `agent-skill renumber python-style`. Verify:
  - the table "Rule IDs before the Python 3.15.0 revision" carries every move;
  - `--fast --skill python-style` passes;
  - python-style's `toolchain` and `mutation` pass, run alone.

## 4. zig-style (`research/zig.md`)

- [ ] 4.1 Remove every version annotation in `research/versions.txt` for zig-style (D2). A change
  someone porting needs goes to the migration table for its release, unless it is there already.
  Verify: `--fast --skill zig-style --only anatomy` reports no version below the target.
- [ ] 4.2 Merge the 26 pointer rules of §A into their owners.
  - The ten that carry content first move it into their owners. COMPTIME-08's is the whole subject,
    which widens ASSERT-22.
  - The text of an `[S]` pointer stays advice when its owner is `[M]`.
  - The four conflicts §A names (CONC-39's `setName`, MEM-04 against MEM-05's example, NAME-08
    against NAME-04, and NAME-22/TEST-04 against BUILD-18) are settled first, not carried over.

  In the same plan, merge §B1's duplicates. Replace §B2's shared parts with a citation, rewrite §B3's
  core rules to cite the rule they restate, and demote §B4's rules to their compiler rows, with each
  residue moved to the rule the table names. One `agent-skill demote zig-style <plan>` records it
  all, and every leftover citation is resolved, `assets/build.zig`'s included. Verify:
  - `rg -n 'Owned by' skills/zig-style/references` finds nothing;
  - `--fast --skill zig-style --only anatomy --only crossref --only citations --only skeleton`.
- [ ] 4.3 Settle §B5's conflicts that 4.2 did not (D7), each in the rule that owns its topic: the
  tier clashes, `preferred_optimize_mode`, the `std.fs` aliases, the `zig fmt --check` command,
  `std.heap` in an exported library, and the rest. Verify: `--fast --skill zig-style`.
- [ ] 4.4 Apply §C's items (D6), each compiled on Zig 0.17.0.
  - C1–C13 are corrections. C1 changes the stdout writer everywhere it appears, and turns ZS-CONC-07
    around, because a positional writer overwrites a file it was appended to.
  - C14 (`Io.Clock.Timestamp`) is a trade-off. It is applied only if the examples read better.
  - C36 changes `assets/build.zig` with ZS-BUILD-01, which it mirrors.

  Skipped items get their reason in `research/zig.md`. Fix the defects of "Other defects noticed",
  the review protocol's among them. Verify: zig-style's `toolchain`, run alone.
- [ ] 4.5 Remove what §2 repeats from `migration.md` (D5). ZS-OUT-20's dead-API table and ZS-MIG-04
  become migration rows, with the rows migration.md lacks moved into ZS-MIG-03 (§B1). Verify:
  `--fast --skill zig-style --only skeleton --only anatomy`.
- [ ] 4.6 Run one `agent-skill renumber zig-style`. Verify:
  - the table "Rule IDs before the Zig 0.17.0 revision" carries every move;
  - `--fast --skill zig-style` passes;
  - the zig `toolchain` and `mutation` pass, run alone.

## 5. bevy-style (`research/bevy.md`)

- [ ] 5.1 Remove every version annotation in `research/versions.txt` for bevy-style (D2), such as
  "Since 0.19". Verify: `--fast --skill bevy-style --only anatomy` reports no version below the
  target.
- [ ] 5.2 Merge the duplicates of A.1, remove or shrink the A.2 restatements of rust-style rules,
  rewrite the A.3 core rules to match their chapter rules, and move the A.4 content to the rows
  that decide it (D3). Each owner absorbs first. Then one `agent-skill demote bevy-style <plan>`
  records each, an A.2 removal naming its rust-style rule. Every leftover citation is resolved.
  Verify: `--fast --skill bevy-style --only anatomy --only crossref --only citations --only
  skeleton`.
- [ ] 5.3 Apply B1–B18 (D6), each compiled against Bevy 0.20.0. B2 (`uuid_handle!`) and B6
  (`.matched()`) are corrections, because the current text fails the build. B3 (auto-registration)
  turns BV-ECS-13 around, and BV-BUILD-03's hand-picked list gains `reflect_auto_register`. B4
  (`Single`) corrects the "a skipped frame, not a crash" claim. Skipped items get their reason in
  `research/bevy.md`. Verify: bevy-style's `toolchain`, run alone.
- [ ] 5.4 Remove what §2 repeats from `migration.md` (D5). BV-MIG-19 becomes the migration chapter's
  silent-changes list (A.1 #1). Verify: `--fast --skill bevy-style --only skeleton --only anatomy`.
- [ ] 5.5 Run one `agent-skill renumber bevy-style`. Verify:
  - the table "Rule IDs before the Bevy 0.20.0 revision" carries every move;
  - `--fast --skill bevy-style` passes;
  - bevy-style's `toolchain` and `mutation` pass, run alone.

## 6. rust-style (`research/rust.md`)

- [ ] 6.1 Remove every version annotation in `research/versions.txt` for rust-style (D2), such as
  "(1.96)" and "stable since 1.74". A crate version in prose is reworded to its major. Verify:
  `--fast --skill rust-style --only anatomy` reports no version below the target.
- [ ] 6.2 Merge the duplicates of A.1 (#1–#94). A tier conflict takes the tier the "Owner" column
  names. Rewrite the A.2 core rules to match their chapter rules, and give RS-CORE-27's
  `unsafe_code = "forbid"` a chapter rule that owns it. Each owner absorbs first. Then one
  `agent-skill demote rust-style <plan>` records each merge and A.3 demotion, and every leftover
  citation, bevy-style's included, is resolved. Verify: `--fast --only anatomy --only crossref
  --only citations --only skeleton` for rust-style and bevy-style.
- [ ] 6.3 Add the rows of A.3 ("no row") and B.2 for lints the shipped configuration enables, each
  named by the rule it decides in part. The nursery lints are not rows (D3). OWN-39's BAD fragment
  becomes `rejected — rustc: let_underscore_lock`. Verify: `--fast --skill rust-style --only
  citations --only markers`.
- [ ] 6.4 Apply B.1 #1–#30 (D6), each compiled on Rust 1.99 with the shipped lint set. #1 (`unsafe
  extern`), #2 (`expr` in edition 2024) and #27 (`Box<[T]>::into_iter`) go to §2's silent or
  edition changes. #25's crates go to the MIG-01 table. Skipped items get their reason in
  `research/rust.md`. Verify: rust-style's `toolchain`, run alone.
- [ ] 6.5 Fix the defects (D7):
  - TRAIT-11's Why and TRAIT-17's example;
  - UNSAFE-21's and CONC-05's examples, and CONC-38's no-op filter;
  - CONC-22's statement and CLI-02's count and signature;
  - the FUNC-19, PERF-06 and PERF-07 pre-sizing examples;
  - the DOC-18 and API-81 citations.

  BUILD-38 is fixed with its asset in 8.2. Verify: the toolchain run of 6.4 covers each changed
  example.
- [ ] 6.6 Remove what §2 repeats from `migration.md` (D5). Verify: `--fast --skill rust-style --only
  skeleton --only anatomy`.
- [ ] 6.7 Run one `agent-skill renumber rust-style`. Verify:
  - the table "Rule IDs before the Rust 1.99 revision" carries every move;
  - bevy-style's `RS-` citations resolve;
  - `--fast` passes for every standard;
  - rust-style's `toolchain` and `mutation` pass, run alone.

## 7. Harness: the pointer concept goes (D4)

- [ ] 7.1 Remove `Rule.pointer`, `Rule.owner` and `Rule.owner_chapter`, `anatomy`'s pointer branches
  and `_pointers`, the "pointer rule that grew a Why" control and its `BRANCHES` entry, and the
  tests that existed only for them. A rule without a Why and a Check now fails the existing branch.
  Verify:
  - `rg -n 'pointer|owner_chapter|\.owner\b' src/agent_skill/model.py src/agent_skill/checks/anatomy.py`
    finds nothing about pointer rules;
  - a unit test shows an "Owned by …" rule with no Why fails as any rule without a Why does;
  - `uv run pytest -m "not toolchain"` passes.

## 8. Assets and README (D8)

- [ ] 8.1 Move `skills/zig-style/assets/ci.yml` to `actions/checkout@v7`. Verify: `--fast --skill
  zig-style --only assets --only pins`.
- [ ] 8.2 Ship `skills/rust-style/assets/rust-toolchain.toml` in bevy-style's shape, with channel
  `1.99.1`. List it in rust-style's §7. Correct RS-BUILD-38, whose `channel = "stable"` pins nothing,
  to the asset's form. Verify: `--fast --skill rust-style --only assets --only layout --only
  skeleton`.
- [ ] 8.3 README:
  - remove the pointer clause from the `anatomy` row;
  - remove the `skeleton` row's exemption clause, a leftover of `refresh-zig`;
  - list `rust-toolchain.toml` where the assets are named.

  Verify: `--fast --only documented --only layout`.

## 9. Close

- [ ] 9.1 Run once, alone: `uv run agent-skill check` prints `ALL CHECKS PASSED`, and
  `openspec validate polish-standards --strict` passes.
- [ ] 9.2 Run `uv run agent-skill build` and `uv run agent-skill install`. Verify: the four
  `dist/*.skill` rebuild, and each `~/.claude/skills/<name>` resolves to `skills/<name>`.

## Workflow follow-up

- Archive with `/opsx:archive`, which syncs `standard-structure`. Then fast-forward `main` to
  `polish-standards`.
- The modified files under `.claude/` (the regenerated OpenSpec commands and skills) are not part of
  this change, and stay out of its commits.
