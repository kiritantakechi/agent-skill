# Tasks

Work happens on branch `zig-0.17`. A slow verification runs only after
`pgrep -f "pytest|cargo|zig (build|test)"` finds nothing. That means the zig `toolchain` alone, or
the full run. Every other verification is `--fast` or a targeted `pytest`.

## 1. Harness: the pin, the wrapper, extraction

- [x] 1.1 Pin `ZIG_VERSION = "0.17.0"`. Reword the `follows_local` reason in
  `profiles/zig_style.py` so it names no version. Verify: `--fast --skill zig-style --only pins`
  passes.
- [x] 1.2 Make the analysis-forcing wrapper reference every top-level declaration by name,
  private ones included, and stop reading `@typeInfo` (D1). Verify: a unit test shows a verified
  block whose private, untested function has a type error now fails. The four blocks in
  `research/zig-0.17.md` §D.2 then fail under the zig toolchain run alone until 3.1 fixes them.
- [x] 1.3 Extract `verified` blocks from `SKILL.md` as well as `references/` (D1). Verify: a unit
  test extracts a `SKILL.md` block, and `--fast` passes for the three other skills, which have none.
- [x] 1.4 Add the vocabulary rows `assertions` → `ASSERT`, `comptime` → `COMPTIME`, `memory` → `MEM`
  and `interop` → `INTEROP`. Verify: `tests/test_vocabulary.py`.

## 2. Harness: compiler rows

- [x] 2.1 Implement D3:
  - `LEVELS["zig"] = {"error"}`;
  - `Profile.probes` (empty by default);
  - phrase matching (`…` matches any run of characters, anchored at `error: `);
  - a `zig` branch in `citations` that compiles each probe with `build-obj -fno-emit-bin` plus the
    wrapper, both directions;
  - `zig` added to the tools `citations` needs.

  Verify with unit tests, each producing its own message:
  - a probe that compiles fails the row;
  - a probe that fails with another error fails and prints that error;
  - a row with no probe fails;
  - a probe with no row fails;
  - with `zig` absent, the rows are UNRUN (`tests/test_unrun.py`).
- [ ] 2.2 Add a control on the real tree: editing a zig row's phrase fails `citations`. Give it its
  `BRANCHES` entry. It lands after 4.3, when the tree has zig rows and the final chapter names.
  Verify: `tests/test_controls.py`.
- [x] 2.3 README:
  - document the compiler row kind under the checks;
  - `--fast` skips the checks that compile a standard's examples, and the probes are not examples.

  Verify: `--fast --only documented --only layout`.

## 3. Zig 0.17: what changed

Each item comes from `research/zig-0.17.md`, and is checked against the 0.17 std source before it is
applied.

- [x] 3.1 Fix every verified block that fails on 0.17:
  - the 11 in §D.1 and the 5 in §D.2;
  - the 6 fragments now rejected (§D.2);
  - the 4 `zig fmt` diffs.

  Verify: the zig `toolchain`, run alone, passes.
- [x] 3.2 Replace every `gone`, `alias`, `semantics`, `new` and `cite` hit in §B with its 0.17 form.
  This includes `std.builtin` → `std.lang`, and the optimize-mode names in code, CLI arguments and
  prose (D5). Verify:
  - `rg` for each old spelling over `skills/zig-style` finds it only on the dead side of a
    migration table;
  - the zig `toolchain` passes alone.
- [ ] 3.3 Correct every `claim` hit in §B and the status flips in §C.4. Where 0.17 removed a rule's
  whole premise (fuzzing builds; `Allocator.free` takes `*[N]T`; `Io.Evented.deinit` and
  `net.Socket.closeMany` compile), change the rule, or remove it through the 4.2 `demote` plan with
  the reason. Verify: `--fast`.
- [x] 3.4 Replace the 46 `std/<file>.zig:NNN` citations with declaration names (D5). Verify:
  `rg '[A-Za-z_/]+\.zig:[0-9]+' skills/zig-style/SKILL.md skills/zig-style/references` finds nothing.
- [x] 3.5 Make §2 the 0.17 reality check, silent changes first (§C.2). Give the migration chapter its
  0.16 → 0.17 section (§C.3), and drop the denylist patterns 0.17 rejects (§C.5). Make the
  description say 0.17. Verify: `--fast`, and the zig `toolchain` alone.
- [x] 3.6 Bring the assets to 0.17:
  - `build.zig`, kept the mirror of ZS-BUILD-01;
  - `build.zig.zon`'s `minimum_zig_version`;
  - `ci.yml`, for the zig version and the mode names.

  Verify: `--fast --only assets`, and `zig build --help` in a copy of the assets.

## 4. Structure

- [ ] 4.1 Lift zig-style's exemption (`exempt_from_structure = None`) and take the full list of
  findings. This is the work list for the rest of group 4. Verify: the list is saved, and each
  finding belongs to a task below.
- [ ] 4.2 Run one `agent-skill demote zig-style <plan>`:
  - ZS-CT-02 becomes its `zig` row;
  - the rules 0.17 removed and the rules whose premise is gone (3.3) are removed with their reasons;
  - the generic "gone" rules of `research/zig-rows.md` §A′ fold into migration rows.

  Then add the always-on rows that remove no rule (§A2) to the chapters that own them (D3), each with
  its probe in `profiles/zig_style.py`. A rule that keeps its error names the row in its Check.
  Verify: `--fast --only citations --only skeleton`.
- [ ] 4.3 Run one `agent-skill renumber zig-style` with the D2 chapter mapping. Verify:
  - `migration.md` has `## Rule IDs before the Zig 0.17.0 revision` with every old family's range;
  - `--fast --only crossref --only anatomy --only skeleton` reports no dangling citation and no
    unresolved row.
- [ ] 4.4 Give `SKILL.md` the eight-section skeleton: the H1 and §2 titles, and the design
  principles as H3s under §3. Then run `agent-skill fmt --skill zig-style` for the shared text.
  Verify: `--fast --only skeleton --only shared-text`.
- [ ] 4.5 Make the review protocol use the shared severity model (Illegal → Unsound, examples kept).
  Turn every `does-not-compile` into `rejected — zig: <error>`, and the four `SKILL.md` snippets into
  `fragment` (1.3). Remove zig-style's `markers` override. Verify:
  `--fast --only markers --only skeleton`.
- [ ] 4.6 Every Why is three lines at most, chapter by chapter, with each fact moved rather than lost
  (D6). Verify: `--fast --only anatomy` reports no Why over three lines for zig-style.
- [ ] 4.7 Verify the converted standard: `--fast` passes for zig-style, and the zig `toolchain` and
  `mutation` checks pass, run alone.

## 5. Remove the exemption machinery

- [ ] 5.1 Remove everything listed in D7, including the controls and tests that existed only for
  it. Verify:
  - `rg -n "exempt_from_structure|exemption_problem|does-not-compile" src tests` finds nothing;
  - `uv run pytest -m "not toolchain"` passes, `tests/test_own_standard.py` included.
- [ ] 5.2 Remove the README's zig-style exemption and old-marker paragraphs. Verify:
  `--fast --only documented`.

## 6. Close

- [ ] 6.1 Run once, alone: `uv run agent-skill check` prints `ALL CHECKS PASSED`, and
  `openspec validate refresh-zig --strict` passes.
- [ ] 6.2 Run `uv run agent-skill build` and `uv run agent-skill install`. Verify: `dist/zig-style.skill`
  rebuilds, and `~/.claude/skills/zig-style` resolves to `skills/zig-style`.

## Workflow follow-up

- Archive with `/opsx:archive`, which syncs `standard-structure` and `check-execution`. Then
  fast-forward `main` to `zig-0.17`.
- The modified files under `.claude/` (the regenerated OpenSpec commands and skills) are not part of
  this change, and stay out of its commits.
