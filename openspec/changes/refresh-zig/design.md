## Context

`refresh-skills` converted python-style, rust-style and bevy-style. zig-style was left exempt
deliberately: its pin follows this machine's compiler, so its bump would come when `zig` moved. It
has moved to 0.17.0, and `pins` says so.

What zig-style is, measured with its exemption lifted:

| | |
|---|---|
| Rules | 406 in 13 chapters, plus 29 core rules in `SKILL.md` |
| Structure findings | 323: 297 Whys over three lines, 13 chapter names outside the vocabulary, the severity model, the §2 title, the shared text |
| Markers | about 25 blocks marked `does-not-compile`, the only uses left in any standard |
| Verified blocks on 0.17 | 11 of about 250 fail once the harness wrapper is fixed (`research/zig-0.17.md` §D) |
| Deprecated spellings | listed in `research/zig-0.17.md` §B; a deprecated name compiles, so only a sweep finds them |
| Compiler-decided rules | one clean row, a handful of borderline ones, and about two dozen always-on errors no rule owns (`research/zig-rows.md`) |
| `std` line citations | 46 `file.zig:NNN` citations, and the research found several already moved |

The harness already has every operation this needs: `renumber` (chapter renames, dense IDs, citation
rewrite, the rename table with ranges), `demote` (rows, merges, removals), `fmt` (shared text,
reflow), and the `skeleton` / `shared-text` / `anatomy` / `markers` checks.

## Goals / Non-Goals

**Goals**

- zig-style is verified against 0.17.0, and every spelling it teaches is the 0.17 one.
- zig-style conforms to `standard-structure` with no exemption. Afterwards the exemption machinery is
  removed, along with every branch that only ran for an exempt standard.
- The rules the compiler decides become rows. The harness proves each row with a probe, both ways.

**Non-Goals**

- No new topics. A rule changes because 0.17 or the structure requires it, not because it could be
  better.
- No upstream tracking for zig. The pin keeps following the local toolchain, as the user decided and
  as `check-execution` specifies.
- Other standards change only where a shared harness change reaches them: vocabulary rows are
  added, never renamed.

## Decisions

### D1. The pin, and what "verified" reaches

`ZIG_VERSION` becomes `0.17.0`. `follows_local` keeps its reason, and `pins` compares against the
running compiler only.

**The wrapper names each declaration.** Today the analysis-forcing wrapper loops over
`@typeInfo(@This()).@"struct".decls`. That has two problems:

- 0.17 renamed the field (`decl_names`), so every block failed.
- It lists only `pub` declarations. A private function in a verified block is analysed only if a
  test reaches it. The audit found four verified blocks that fail on 0.17 and pass the harness this
  way (`research/zig-0.17.md` §D.2).

The wrapper therefore becomes a `comptime { _ = &name; … }` over every top-level declaration the
harness reads from the block. Private ones are included without changing their visibility; a block
about `@hasDecl` and `pub` depends on that visibility. The wrapper also no longer depends on how
`std.lang.Type` lays out its fields, which is what broke here.

**`SKILL.md` is extracted too.** `Skill.chapters` covers only `references/`, so a `verified` block in
`SKILL.md` was never compiled. zig-style is the only standard with any: four snippets that do not
compile standalone. Extraction now includes `SKILL.md`, and those four become `fragment`.

### D2. Chapter names and family codes

| Chapter | Becomes | Code |
|---|---|---|
| `assertions-and-limits.md` | `assertions.md` | `ASSERT` (new) |
| `build-and-project.md` | `build.md` | `BUILD` |
| `c-interop-and-targets.md` | `interop.md` | `INTEROP` (new) |
| `comptime-and-generics.md` | `comptime.md` | `COMPTIME` (new) |
| `errors-and-control-flow.md` | `errors.md` | `ERR` |
| `formatting-and-output.md` | `output.md` | `OUT` |
| `io-and-concurrency.md` | `concurrency.md` | `CONC` |
| `memory-and-allocators.md` | `memory.md` | `MEM` (new) |
| `migration-and-dead-apis.md` | `migration.md` | `MIG` |
| `naming-and-files.md` | `naming.md` | `NAME` |
| `performance-and-locality.md` | `performance.md` | `PERF` |
| `testing-and-fuzzing.md` | `testing.md` | `TEST` |
| `types-and-data.md` | `data.md` | `DATA` |

`types-and-data` becomes `data`, not `types`. In python-style, `types` is the annotation and type
checker chapter, and `data` is data modelling. Zig's chapter is about layout, tagged unions,
optionals and integer widths, so it belongs with `data`.

`io-and-concurrency` becomes `concurrency`, because `std.Io` is the concurrency model.

The four new words are concepts no other standard has. Zig has no ownership system, so `memory` is
not `ownership`. `comptime` is neither `traits` nor `macros`.

### D3. Compiler rows

**Shape.** A row is `| zig | <phrase> | error | <forbids> |`. The phrase is the 0.17 error message
with each identifier, type or literal replaced by `…`, for example `value of type … ignored`.
`LEVELS["zig"]` is `{"error"}`, because a compile error has no other level.

**Probes.** `profiles/zig_style.py` gains `probes: dict[str, str]`, which maps each phrase to the
smallest source the compiler rejects with it. A probe is data, like `fires`. Probes come from
`research/zig-rows.md`; every one was compiled on 0.17.

**Verification, in `citations`.**

- Every `zig` row has a probe, and every probe has a row.
- Each probe is compiled with `zig build-obj -fno-emit-bin`, plus the analysis-forcing wrapper.
- A probe that compiles fails the row.
- A probe that fails without an `error:` line matching the phrase also fails the row, and the
  finding prints what the compiler said.
- `…` matches any run of characters. The match is anchored at `error: `, so `unreachable code` does
  not match `reached unreachable code`.
- `citations` adds `zig` to the tools it needs. Without it, the rows are UNRUN.

The probes are the same kind of compile as the examples. `--fast` documents that it skips the
checks that compile a standard's examples, and the probes are not examples.

**Which rules become rows.**

- **ZS-CT-02 (redundant `comptime`)** is the one clean demotion. Its whole content is the error.
- A rule whose error is part of a design point stays a rule, and its Check names the row. Examples
  are ZS-CAPI-01 and -02 (C-ABI signatures), ZS-TYPE-06 (signed division) and the exhaustive-switch
  rules.
- A rule that fails only through a generic "has no member named" is not a row; it is a "gone" row in
  the migration tables. Examples are ZS-CT-18, ZS-FMT-11, ZS-BUILD-02, -06 and ZS-CAPI-05.
- The always-on errors that no rule owns join the chapter that owns their topic:
  - unused names, discards and shadowing go to `naming`;
  - ignored values, error unions, `try` / `catch` / `orelse` misuse, `defer` misuse and duplicate
    switch values go to `errors`;
  - an expired local's address goes to `memory`;
  - removed builtins go to `migration`;
  - the calling-convention error goes to `interop`.

  These rows add content rather than remove it. An agent writing Zig meets these errors first, so the
  row is cheap guidance. The probes keep the guidance true.

### D4. One renumbering

`agent-skill demote` runs first, for the demotion, the gone rules and the premises that no longer
hold. Then one `agent-skill renumber zig-style --chapters …` renames all 13 chapters and renumbers
densely. `migration.md` receives `## Rule IDs before the Zig 0.17.0 revision`, with each old family's
range (`ZS-ASRT-01`–…). Because the pin moves first (D1), the heading names 0.17.0.

### D5. 0.17 content

- Every spelling 0.17 renamed, removed or deprecated is replaced by its 0.17 form, from the audit.
  This covers verified, fragment and prose alike. The largest group is `std.builtin` → `std.lang`.
  - A deprecated alias that still compiles is the one place this matters most. Any `rejected` example
    or BAD side that taught the old name stays only on the dead side of a migration table.
- The rules whose premise 0.17 removed are changed or removed through `demote`:
  - fuzzing now builds (ZS-BUILD-35, ZS-TEST-20, ZS-MIG-11);
  - `Allocator.free` accepts `*[N]T` (ZS-MEM-15, ZS-IO-04, ZS-TEST-09);
  - `Io.Evented.deinit` and `net.Socket.closeMany` compile (ZS-IO-42).
- §2 becomes "Zig 0.17 reality check": the 0.17 changes that make 0.16 code wrong, and those that
  leave it compiling but meaning something else. An example of the second kind is
  `containsAtLeastScalar`'s swapped parameters.
- The migration chapter gains a 0.16 → 0.17 section: one table of renames and removals, with the
  0.17 spelling for each and a `rg` pattern a reader can run. The dead-API denylist drops the patterns
  0.17 already rejects.
- The optimize-mode names follow 0.17: `.debug`, `.safe`, `.fast` and `.small`, and
  `builtin.optimize` in place of `builtin.mode`. TitleCase is parsed only through the deprecated
  `Optimize.fromString`, and `--help` prints the new names. This covers code and CLI arguments, and
  the 157 mentions in prose (`ReleaseSafe` → `safe`).
- The 46 `std/<file>.zig:NNN` citations become declaration names, such as `std.debug.assert`, or a
  module path without a line. A line number is out of date by the next release, as four of them
  already are. A declaration name is checked by the compiler each time an example uses it.

### D6. Structure

- **`SKILL.md`:** the eight sections with their fixed titles. The H1 and §2 are `Zig Style — 0.17`
  and `2. Zig 0.17 reality check`. The design principles move under `3. Design principles` as H3s.
  The shared passages are written by `agent-skill fmt`.
- **The review protocol:** the shared severity model. Zig's **Illegal** becomes the shared
  **Unsound**, and its examples column stays zig's own.
- **Markers:** `does-not-compile` becomes `rejected — zig: <the error the block demonstrates>`. A
  `zon` block that zig rejects says `zig` too.
- **Whys:** three lines at most. Detail moves into the statement, into an example, or out of the
  standard, as in `refresh-skills`. This is editorial, chapter by chapter. Chapters are independent
  files, so the work can be split by chapter, after the renumbering so that file names are final.

### D7. The exemption goes, last

After zig-style conforms, the following are removed:

- `Profile.exempt_from_structure`, `exemption_problem` and the outlived-exemption report in
  `skeleton`;
- the `exempt_from_structure` branches in `anatomy`, `shared`, `fmt` and `renumber`;
- `Profile.markers`: `markers` reads `MARKERS`, and `model.py` no longer parses `does-not-compile`;
- the tests that exercised the exemption (`tests/test_exemption.py`, and the exemption cases in
  `test_skeleton.py`), plus the legacy marker case in `test_model.py`;
- the README paragraphs about zig-style's exemption and its old marker.

Per-rule pattern exemptions (`Profile.exempt`) are a different mechanism and stay.

The removal comes last. Before it, the exempt branches are what keep a run green while zig-style is
part-way through. After it, nothing can be part-way.

## Risks / Trade-offs

- **The summarised release notes can be wrong.** Every rename is checked against the 0.17 std source
  before it is applied (`research/zig-0.17.md` §A marks each one).
- **A probe's message changes between Zig releases.** The row then fails at the bump that changed it,
  which is the intended signal.
- **297 Why rewrites can lose a fact.** The rule is the one `refresh-skills` used: a fact the reader
  acts on moves into the statement. The `anatomy` near-duplicate check guards against two trimmed
  Whys collapsing into one.
- **A cold build cache.** `.cache/target` was cleared, which affects only the Rust skills. The full
  run still runs alone.

## Migration Plan

1. Harness: the pin and wrapper (D1), the four vocabulary words, and `zig` rows with probes (D3).
2. Content: the 11 failing blocks, the 0.17 spelling sweep, the premises, the line citations, §2 and
   the migration section (D5). Then the zig toolchain alone.
3. Structure: `demote`, then one `renumber`, then `fmt`, the severity model, the markers and the
   Whys (D4, D6).
4. Remove the exemption machinery (D7) and update the README. Then one full run alone,
   `openspec validate --strict`, archive, and a fast-forward of `main`.

Rollback is the branch: nothing reaches `main` before step 4 passes.

## Open Questions

None. The user settled the exemption, the compiler rows and the process before planning.
