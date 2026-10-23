# zig-style: decisions taken for the apply

What `research/zig.md` left open, decided once, so the chapters edited in parallel agree.

## Merges (the `demote` plan)

Each merged rule's owner first absorbs what `zig.md` says it lacks. Where `zig.md` names a better
home than the pointer's owner, the merge goes there.

| Merged | Into | | Merged | Into |
|---|---|---|---|---|
| ASSERT-19 | ASSERT-21 | | ASSERT-30 | ERR-23 |
| ASSERT-31 | TEST-08 | | PERF-17 | ERR-31 |
| ASSERT-33 | ASSERT-32 | | PERF-20 | COMPTIME-05 |
| BUILD-13 | BUILD-39 | | ERR-29 | COMPTIME-06 |
| BUILD-23 | BUILD-05 | | NAME-15 | PERF-08 |
| COMPTIME-08 | ASSERT-22 | | CONC-17 | COMPTIME-23 |
| COMPTIME-19 | COMPTIME-20 | | PERF-21 | CONC-33 |
| COMPTIME-26 | COMPTIME-12 | | OUT-16 | CONC-05 |
| COMPTIME-27 | MIG-02 | | OUT-17 | ERR-03 |
| CONC-03 | TEST-09 | | NAME-07 | MEM-07 |
| CONC-39 | MIG-03 | | COMPTIME-17 | NAME-12 |
| DATA-21 | ASSERT-22 | | ASSERT-02 | ERR-01 |
| DATA-22 | MEM-26 | | ERR-02 | DATA-31 |
| DATA-23 | MEM-16 | | ASSERT-23 | COMPTIME-10 |
| ERR-12 | MEM-11 | | ASSERT-05 | ASSERT-03 |
| ERR-24 | ASSERT-27 | | COMPTIME-01 | COMPTIME-21 |
| MEM-04 | TEST-05 | | BUILD-35 | INTEROP-17 |
| MEM-19 | TEST-14 | | MIG-04 | OUT-01 |
| NAME-08 | NAME-04 | | OUT-20 | MIG-03 |
| NAME-22 | TEST-02 | | CONC-21 | MIG-05 |
| NAME-26 | ASSERT-09 | | INTEROP-13 | DATA-02 |
| NAME-31 | ERR-22 | | | |
| NAME-32 | MEM-11 | | | |
| TEST-03 | TEST-02 | | | |
| TEST-04 | BUILD-18 | | | |
| TEST-29 | TEST-20 | | | |

Two rules become their compiler rows: COMPTIME-02 (`redundant comptime keyword in already comptime
scope`), with its type-function residue moved to COMPTIME-10; and INTEROP-02 (`… not allowed in
function with calling convention …`), with its slice and `?*T` residue moved to INTEROP-10/11.
ERR-31 loses its `[M]` "replace `@setCold`" half to migration's `invalid builtin function` row, and
keeps the `[S]` hint placement, into which PERF-17 merges.

The overlaps `zig.md` resolves without a merge (ERR-34 with PERF-12/13; CONC-08 with COMPTIME-12;
COMPTIME-09 with NAME-14; ASSERT-06 and OUT-18 with ERR-01's table; ERR-28 with DATA-28/29 and
COMPTIME-25; ERR-08 with ERR-10/11/17; ERR-14 with MEM-12; ASSERT-07 with BUILD-27; ASSERT-24 with
CONC-38; ASSERT-25 with BUILD-19; ASSERT-29 with DATA-26; DATA-24 and MEM-17 with DATA-26; BUILD-42
with DATA-38; BUILD-34 with TEST-27; NAME-23 with BUILD-17; ASSERT-01 with NAME-19; DATA-13 with
MEM-06; DATA-14 with MEM-13; MEM-01 with CONC-01 and MIG-09; NAME-29 with BUILD-31; all of §B2)
are deduplicated in place: the shared part stays in the owner, and the other rule cites it.

## Conflicts (§B5)

1. **A field named `allocator`.** MEM-07 owns: a field is named for its role (`gpa`, `arena`) like
   a parameter. NAME-07 merges into MEM-07 and keeps its parameter-order content.
2. **Tiers.** The owner's tier stands.
   - ASSERT-24 `[M]` over CONC-38: CONC-38 drops its relaxed form, becomes `[M]`, and keeps its list.
   - COMPTIME-10 `[M!]`, with its relaxed form, absorbs ASSERT-23.
   - PERF-08 `[S]` absorbs NAME-15: lifting a hot loop is advice for a measured hot path (PERF-24).
   - COMPTIME-06 `[M]` absorbs ERR-29's `inline else` half.
   - ASSERT-01 `[M]` owns the `assert` alias; NAME-19's Check drops that grep.
3. **`preferred_optimize_mode`.** The build chapter owns build configuration: BUILD-28's plain
   `standardOptimizeOption(.{})` with `-Doptimize=safe` stands, and ASSERT-07 drops the advice and
   its Check.
4. **The `std.fs` shim.** MIG-05 is right: all six declarations, every hit a finding. CONC-21 merges
   into it with its name-mapping sentence.
5. **`zig fmt --check`.** BUILD-31 owns the CI gate. NAME-29's Check names BUILD-31's command.
6. **`std.Thread.setName`** takes `io` in 0.17. CONC-32 is corrected; CONC-39 merges without its
   "survivors" sentence.
7. **`std.heap` in an exported library.** MEM-02 owns: the C-ABI export layer is a library's root,
   the one place that picks an allocator, and MEM-02 says so. INTEROP-16 cites it.
8. **MEM-05's verified `test`** builds its own allocator, which TEST-05 forbids. The example moves
   out of a `test` block.
9. **`readSectorCallback`.** CONC-37 owns retiring callback-driven I/O. NAME-10 uses another
   example name.
10. **`comptime { _ = @import }`.** BUILD-18's spelling stands. TEST-04 and NAME-22 merge without
    their `test { … }` form.
11. **comptime.md's "shim = reason (a)"** is corrected: a shim is its own sanction, beside the three
    reasons (COMPTIME-05, with PERF-20 merged in).
12. **DATA-10's `parsePort`** is the shape OUT-14's Check flags. OUT-14 stands, and DATA-10's
    example keeps showing `std.math.cast` without that shape.
13. **NAME-08 against NAME-04.** naming.md decides whether same-length names align under
    `zig fmt`, by running it, and NAME-04 states the result once.
14. **CONC-07**: a positional writer overwrites a file it was appended to (C1). CONC-07 is turned
    around: program output to stdout is a streaming writer.

The allocator's position (MEM-06 against DATA-13, NAME-07 and SKILL §2.6): the first parameter
after the receiver, which is what each of them means. MEM-06 says it that way.

CORE-27 cites PERF-18 for "pass options explicitly". PERF-18's title and statement widen to that
principle, with `@prefetch` as its example, because INTEROP-04 cites CORE-27 for `ExportOptions`.
