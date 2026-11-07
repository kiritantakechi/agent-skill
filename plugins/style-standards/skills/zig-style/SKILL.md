---
name: zig-style
description: >-
  The modern Zig 0.17 engineering standard — a 356-rule library merging the official Zig style
  guide, the empirical conventions of the 0.17 standard library, and TigerBeetle's TigerStyle.
  Covers naming, types and data layout, errors and control flow, memory and allocators, std.Io
  streams and structured concurrency, assertions and bounded limits, API symmetry, comptime and
  interfaces, testing and fuzzing, formatting and output, performance and locality, C interop and
  cross-target builds, build.zig/build.zig.zon, and the complete 0.13-to-0.17 migration tables. Use
  this whenever writing, reviewing, refactoring, scaffolding, or debugging ANY Zig — a whole
  project, one function, a build.zig, an error set, an allocator choice, a test — even if the user
  never mentions "style", "standards", or "quality". Also use when asked to make Zig "idiomatic",
  "modern", "clean", or "production-grade", when auditing a Zig codebase, when the current spelling
  of a std symbol is uncertain, and when migrating code to Zig 0.17.
---

# Zig Style — 0.17

A single standard formed from three sources: the **official Zig style guide** (naming, formatting),
the **empirical conventions of the 0.17 standard library** (API shape, ownership, decl literals),
and **TigerStyle** (assertions, bounded limits, control-flow discipline). Where they disagree, this
standard picks a side and says why.

**Target: Zig 0.17.0.** Zig changed enormously in 0.15 and 0.16, and again in 0.17. Most Zig you
have seen — including most of what is on the public internet — is stale. Section 2 below is the
single highest-value part of this skill; read it before writing any line of Zig.

## How to use this standard

1. **Read section 2** before emitting Zig code. It is the Zig 0.17 reality check, and some of its
   entries change behaviour without producing an error, so nothing else will catch them.
2. **Apply section 4.** Those core rules bind on their own and reach nearly every file.
3. **Load one chapter** from the reference map in section 6 — the one that matches the task. Each
   opens with a table of contents listing every rule it owns, so you can jump straight to the rule.
   Load a second chapter only when the task genuinely spans two; never load all of them.
4. **Walk section 5** before handing back a diff.

Rules are cited by ID: `ZS-`, then the family of the chapter that owns the rule, then its number.
Section 6 maps each family to its chapter, so cite the ID when justifying a change and the reader
can find the full rule and its rationale. When a rule in a chapter and a rule here appear to
conflict, the chapter is the detailed statement and wins; sections 1 and 3 govern how to break a
genuine tie.

A chapter ends with **Decided by tools** when a tool settles part of its subject on its own: each
lint or compiler error, the level it fails a build at, and what it forbids. Those are not rules —
the tool enforces them, so they carry no Why and no Check. When rules are renumbered, the migration
chapter names the file that maps every old ID to its new one.

Every fenced example carries a marker on its first line. `// verified` — the block compiles as
written against Zig 0.17.0, and any test it ships passes. `// fragment` — shown in context rather
than run as a unit, usually because it uses names the chapter declares around it.
`// rejected — <tool>: …` — the rejection is the point, and the marker names the tool that rejects
it: `zig`. A trailing `— GOOD` or `— BAD` names which side of the rule the block illustrates. A
block in another language carries its marker in that language's comment syntax.

## 1. Tiers

Every rule carries a tier. Apply it literally.

| Tag | Meaning |
|---|---|
| `[M]` | **Mandatory** in all Zig code. No exceptions without an explicit instruction from the user. |
| `[M!]` | **Mandatory in high-reliability code**; strongly recommended elsewhere. Each `[M!]` rule states its relaxed form. |
| `[S]` | **Should.** The default. Deviating is allowed but must be justified in a comment on the line that deviates. |

**A codebase is "high-reliability" — `[M!]` applies as `[M]` — if any of these hold:** it stores
data others cannot reconstruct (databases, filesystems, ledgers); a crash or wrong answer is
unrecoverable or unobservable (embedded, firmware, medical, avionics, consensus); it is a security
boundary (cryptography, parsers on untrusted input, sandboxes, allocators); or it runs unattended
where nobody will read the stack trace. **Otherwise** — CLI tools, build scripts, games, application
code, most libraries — `[M!]` rules are recommendations, and the relaxed form given with each rule
is acceptable.

When you cannot tell which category the code is in, ask, or state your assumption in one line and
proceed with the stricter reading.

## 2. Zig 0.17 reality check

Zig 0.15, 0.16 and 0.17 each broke code written for the release before, and most Zig in circulation
predates all three. The traps come in the order that matters: first the ones that still compile and
now do something else, which no build catches; then the ones the compiler rejects; then the
toolchain. Every snippet here was compiled against Zig 0.17.0.

### 2.1 What 0.17 changed without breaking the build

| Change | What silently differs |
|---|---|
| The optimize modes are `.debug`, `.safe`, `.fast` and `.small` (`std.lang.Optimize`), and `@import("builtin").mode` is now `.optimize` | The old names survive as deprecated declarations, so `.optimize = .ReleaseSafe` and a `.ReleaseFast =>` prong still compile — but `builtin.mode == .Debug` does not. `@tagName` and `{t}` now print `debug` and `safe`, so every artifact name and log line built from a mode changes. To ask whether safety checks are on, write `builtin.optimize.runtimeSafety()`: not a hand-written switch, and not `std.debug.runtime_safety`, which reports std's mode rather than yours. |
| `std.mem.containsAtLeastScalar` takes `(T, list, element, minimum)` | 0.16 took `(minimum, element)`, and its `containsAtLeastScalar2` is gone. For an integer `T` both orders type-check, so a 0.16 call compiles and asks a different question. Re-read every call. |
| `@hasDecl` sees only `pub` declarations, even from the same file | Feature detection over a private declaration — `if (@hasDecl(@This(), "x"))` — turns `false` with no diagnostic. |
| `@bitCast` on an array or a vector reinterprets logical bits, independent of endianness | A big-endian target gets a different result from 0.16. A cast to an enum now compiles and is safety-checked, and a cast of an `extern struct` or `extern union` is now rejected — use `@ptrCast` or an `extern union`. |
| `std.mem.eql` and `findDiff` on floats no longer short-circuit on the same slice | A slice holding NaN is no longer equal to itself. |
| `init.gpa` and `std.testing.allocator` are `std.heap.SafeAllocator` | `init.gpa` is a `SafeAllocator` in `debug` **and** `safe` builds, whether or not libc is linked; 0.16 gave a `ReleaseSafe` build that linked libc the `c_allocator`. A `safe` binary's allocation profile changes, and its leak report still never changes the exit code. |
| `zig fmt` rewrites `@intFromEnum` and `@enumFromInt` | Both are deprecated in favour of `@backingInt` and `@fromBackingInt`, and `zig fmt` does the rewrite, so a `zig fmt --check` gate fails on code nobody touched. The rewrite wraps `@fromBackingInt`'s operand in an `@intCast` even when it already has the backing type; delete that cast. |
| Build-system behavior | `run.addPassthruArgs()`, the replacement for `b.args`, makes the run step uncached, and the build script never sees the arguments. A bare `zig fetch <url>` fills only the global cache; `zig fetch --save` and `zig build` fill `zig-pkg/`. `b.dependency` now fetches a lazy package itself instead of panicking, which makes `b.lazyDependency` a deprecated alias. |

### 2.2 `{}` does not call your `format` method — only `{f}` does

This 0.16 change is still the most dangerous one here, because it produces **wrong output instead of
a compile error**.

```zig
// fragment — prints: [.{ .x = 1 }] [CUSTOM3]
const P = struct {
    x: u32,
    pub fn format(p: P, w: *std.Io.Writer) std.Io.Writer.Error!void {
        try w.print("CUSTOM{d}", .{p.x});
    }
};
try w.print("[{}] [{f}]", .{ P{ .x = 1 }, P{ .x = 3 } });
```

`{}` falls back to the compiler's default struct dump and silently ignores `format`. **Use `{f}` for
any type with a custom `format`.** The signature is
`fn (value, w: *std.Io.Writer) std.Io.Writer.Error!void` — it takes a writer and no longer takes a
format string or options. `{D}` no longer works. 0.17 adds `{q}`, which prints a double-quoted,
escaped string, and `{qf}`, which escapes what `format` writes. Related trap: width or precision on
a bare `{}` over an enum or error set is a **runtime panic**, not a compile error — write `{t:>8}`.
Full specifier set in `references/output.md`.

### 2.3 Deprecated spellings still compile — emit the new ones

This is **silent** staleness: the old names remain as aliases, so nothing fails to build.

| Stale, still compiles | Write |
|---|---|
| `std.builtin.Type`, `std.builtin.CallingConvention`, any `std.builtin.X` | `std.lang.X` |
| `@import("builtin").cpu`, `.os`, `.abi`, `.object_format` | `.target.cpu`, `.target.os`, `.target.abi`, `.target.ofmt` |
| `std.heap.DebugAllocator(.{})`, constructed with `.init` | `std.heap.SafeAllocator`, constructed with `.init(backing, .{})`; its `deinit()` returns the leak count |
| `std.fmt.allocPrint(gpa, f, args)`, `allocPrintSentinel` | `gpa.print(f, args)`, `gpa.printSentinel(f, args, 0)` |
| `std.fmt.bufPrint`, `bufPrintSentinel` | `std.mem.print`, `std.mem.printSentinel` |
| `list.getLastOrNull()`, `list.getLast()` | `list.last()`, which returns `?T`: where `getLast` returned `T`, handle the `null`; the borrow is `list.lastPtr()` |
| `bit_set.IntegerBitSet`, `ArrayBitSet`, `StaticBitSet`, `DynamicBitSetUnmanaged` | `bit_set.Integer`, `Array`, `Static`, `Dynamic` |
| `std.meta.fieldInfo`, `fieldNames`, `fieldTypes` | `@typeInfo`, `@FieldType` |
| `b.lazyDependency(name, args)` | `b.dependency(name, args)`, or `try b.dependencyLazy(name, args)` |
| `std.ArrayListUnmanaged(T)` | `std.ArrayList(T)` — the managed one is now the deprecated one |
| `std.fs.path`, `std.fs.max_path_bytes`, `max_name_bytes` | `std.Io.Dir.path`, `std.Io.Dir.max_path_bytes`, `max_name_bytes` |

`std.mem.indexOf*` was renamed to `find*` in 0.16, and the old names still compile: `indexOf` is
`find`, `lastIndexOfScalar` is `findScalarLast`, and `references/migration.md` ZS-MIG-05 has every
pair. Part 7 there lists what 0.17 deprecated, with a pattern for each row, and ZS-MIG-13 is the
denylist that collects the chapter's alias rows and fails a build on them.

### 2.4 `main` takes a parameter now

```zig
// verified
const std = @import("std");
const Io = std.Io;

/// Bytes of program output held before a write reaches the kernel.
const stdout_buffer_max = 4096;

pub fn main(init: std.process.Init) !void {
    const io = init.io; // Io implementation chosen for the target
    const gpa = init.gpa; // SafeAllocator in debug and safe builds: leaks are reported
    const arena = init.arena.allocator(); // whole-process storage, freed on exit

    var stdout_buffer: [stdout_buffer_max]u8 = undefined;
    var stdout_writer = Io.File.stdout().writerStreaming(io, &stdout_buffer);
    const out = &stdout_writer.interface;

    const args = try init.minimal.args.toSlice(arena); // arena: no free to write
    for (args) |arg| try out.print("{s}\n", .{arg});

    const summary = try gpa.print("{d} argument(s)\n", .{args.len});
    defer gpa.free(summary); // gpa: the free is yours — that is the whole difference
    try out.writeAll(summary);

    try out.flush(); // Output is buffered. Forgetting this prints nothing.
}
```

`std.process.Init` gives you `minimal` (`args`, `environ`), `arena`, `gpa`, `io`, `environ_map`,
`preopens`. It replaces the old `pub fn main() !void` plus manual `GeneralPurposeAllocator` and
`std.process.argsAlloc` boilerplate (`references/migration.md` ZS-MIG-08). Program output to stdout
is a *streaming* writer: a positional one, which `zig init` emits, starts at offset 0 and overwrites
what a `>>` redirect already wrote (`references/concurrency.md` ZS-CONC-06).

### 2.5 There is no `std.io`, and `std.fs` is a deprecation shim

I/O, the filesystem, networking, time, and concurrency all live under `std.Io` now. `std/fs.zig` is
about twenty lines, and every member of it is marked `Deprecated`.

| Dead | Use |
|---|---|
| `std.io.getStdOut().writer()`, `bufferedWriter` | `Io.File.stdout().writerStreaming(io, &buffer)`, then `flush()` |
| `std.io.Writer` / `GenericWriter` / `AnyWriter` | `*std.Io.Writer` (non-generic, buffer supplied by you) |
| `std.fs.cwd()`, `std.fs.File`, `std.fs.Dir` | `std.Io.Dir`, `std.Io.File` — every call takes an `io` |
| `async` / `await` keywords | `io.async(f, args)` → `Future(T)`, then `future.await(io)` |
| `std.heap.GeneralPurposeAllocator` | `std.heap.SafeAllocator` (0.16 called it `DebugAllocator`) |

The full tables are ZS-MIG-03 for streams and ZS-MIG-04 for the filesystem, in
`references/migration.md`.

### 2.6 Containers are unmanaged, except the non-array hash maps

```zig
// fragment
var list: std.ArrayList(i32) = .empty;   // decl literal, not .init(gpa)
defer list.deinit(gpa);                  // gpa passed to deinit
try list.append(gpa, 42);                // ...and to every allocating method
const owned = try list.toOwnedSlice(gpa);
```

The allocator is the **second** parameter, after the receiver. Non-allocating methods (`pop`,
`last`) take no allocator. `std.HashMap`, `std.AutoHashMap`, `std.StringHashMap` and `std.BufMap`
are still managed and not deprecated: they take the allocator once, in `.init(gpa)`, and `deinit()`
takes none; the three `…HashMapUnmanaged` forms take it per call. Every container rename is a row of
`references/migration.md` ZS-MIG-06.

### 2.7 Concurrency is colorless and goes through `Io`

```zig
// fragment
fn fetch(io: Io, id: u32) !u32 {
    try io.sleep(.fromMilliseconds(10), .awake);
    return id * 2;
}

test "run two tasks concurrently and await both" {
    const io = std.testing.io; // tests that do I/O use this

    var a = io.async(fetch, .{ io, 1 });
    var b = io.async(fetch, .{ io, 2 });

    // Await BOTH before inspecting either. A `try` between the spawns and the
    // last await abandons the other future and leaks it — see ZS-CONC-21.
    const first = a.await(io);
    const second = b.await(io);

    try std.testing.expectEqual(2, try first);
    try std.testing.expectEqual(4, try second);
}
```

The *same* function body runs threaded, evented, or single-threaded-blocking depending on which `Io`
you pass. That is the point of the design. Note `Io.Clock` has no `.monotonic` — the variants are
`real`, `awake`, `boot`, `cpu_process`, `cpu_thread`. `Io.Duration` constructors are spelled out in
full: `fromNanoseconds`, `fromMicroseconds`, `fromMilliseconds`, `fromSeconds`. What moved off
`std.Thread` and `std.time` is `references/migration.md` ZS-MIG-09.

### 2.8 Testing moved too

`std.testing.io` is a real `Io` for tests. `expectEqual(expected, actual)` takes `anytype` for both
and peer-resolves, so `@as(T, x)` wrapping is usually unnecessary. Fuzz targets receive
`*std.testing.Smith`, not `[]const u8` (`references/migration.md` ZS-MIG-10).

### 2.9 Things that no longer exist at all

The compiler rejects each of these, so none of them ships by accident; they are here because they
are what a reader reaches for first.

| Gone | Removed | Use |
|---|---|---|
| `@Type` (removed builtin) | by 0.16 | `@Int`, `@Tuple`, `@Pointer`, `@Fn`, `@Struct`, `@Union`, `@Enum`, `@EnumLiteral` |
| `std.Thread.Mutex`/`Condition`/`Semaphore`/`RwLock`/`ResetEvent`/`WaitGroup`/`Pool`/`Futex` | by 0.16 | `Io.Mutex`, `Io.Condition`, `Io.Semaphore`, `Io.RwLock`, `Io.Event`, `io.futexWait`/`futexWake` |
| `std.time.Timer`, `Instant`, `timestamp()`, `sleep()` | by 0.16 | `Io.Timestamp`, `Io.Duration`, `Io.Clock`, `io.sleep(d, clock)` — `std.time` is now only unit constants |
| `std.BoundedArray` | by 0.16 | `var list: std.ArrayList(T) = .initBuffer(&backing);`, then `appendBounded` where `BoundedArray` returned an error, `appendAssumeCapacity` where the capacity is proved |
| `usingnamespace` | by 0.16 | explicit re-export: `pub const foo = @import("foo.zig").foo;` |
| `@typeInfo(T).@"struct".fields`, `.decls` | 0.17 | `.field_names`, `.field_types`, `.field_attrs`, `.decl_names` — every `std.lang.Type` variant is now a struct of arrays |
| `errdefer \|err\|` | 0.17 | split the function, and handle the error at the call's `catch \|err\|` |
| `@cImport` | 0.17 | `b.addTranslateC` in `build.zig`, or the translate-c package |
| `b.args` | 0.17 | `run.addPassthruArgs()` |

The `std.Thread` one is a **correctness** requirement, not a preference: an OS-level mutex blocks
the whole carrier thread and will deadlock green threads under the fiber/evented backends. The rest
of what 0.17 removed — `std.meta.Int`, `bufPrintZ`, `.initEmpty()`, `a ** n`, `stackFallback`,
`std.zon.parse.fromSlice`'s old signature, `b.build_root`, `LazyPath.getPath*` and more — is
`references/migration.md` Part 7, and what 0.16 removed is ZS-MIG-02, ZS-MIG-06 and ZS-MIG-09.

### 2.10 What changed in the toolchain

- `zig build test --fuzz` and `zig reduce` work again; neither built on 0.16.0.
- The new ELF linker — `-fnew-linker`, and so `-fincremental` — emits DWARF and `.eh_frame`, and
  `zig build -fincremental --watch` now works for most `x86_64-linux` projects.
- No ZLS release supports Zig 0.17.0.
- `zig build`: `--zig-lib-dir` is now `--zig-lib=`, and `--global-cache-dir`, `--build-runner`,
  `--debug-rt` and `--verbose-llvm-bc` are gone. `--help` lists the modes as `debug`, `safe`, `fast`
  and `small`; `-Doptimize=ReleaseSafe` still parses, through the deprecated `Optimize.fromString`.
- `zig fmt --complexity` prints a complexity report for each file.
- LLVM 22 still runs with loop vectorization disabled, until 0.18 re-enables it, so write `@Vector`
  by hand where SIMD matters.

## 3. Design principles

**Safety > Performance > Developer experience.** All three matter; when two conflict, the earlier
one wins. This ordering is TigerStyle's and it is the reason for most of the rules below.

Simplicity is not a fourth goal competing with these — it is how the three are achieved at once.
Simplicity is the hardest revision, not the first attempt.

**Symmetry** is how simplicity survives a second contributor. A simple design that is applied
irregularly stops being simple: operations that come in pairs but are named differently, siblings
that take their parameters in a different order, two mechanisms for one concept, a branch that
exists for a single input. None of those is a bug, and each is locally defensible, which is why a
codebase accretes them one reasonable-looking patch at a time, which is why it needs a standing
question in the same pass as the assertion review, not an occasional cleanup.

**Zero technical debt.** Solve a problem in design, where it is cheap, rather than in production,
where it is not. Code, like steel, is least expensive to change while it is hot. In practice this
means: a known showstopper is fixed before the change lands, not filed; an exponential-complexity
algorithm or an unbounded latency spike on a hot path does not ship with a TODO attached; and a
`TODO` in a diff is either resolved or carries a tracking reference and a stated trigger for when it
must be. The point is not perfectionism — it is that the second pass frequently never happens, so
"we will fix it later" is usually a decision to ship it permanently.

When two rules appear to conflict and their tiers are equal, the goal ordering decides it: safety
first, then performance, then developer experience. Where that does not separate them, use these
five questions, in order:

1. **What can be deleted?** Fewer types, fewer parameters, fewer allocations, fewer dependencies,
   fewer states.
2. **What can be made unrepresentable?** Encode the bound in the type and give the limit a name, so
   an invalid value cannot be constructed rather than being caught after the fact (`ZS-DATA-03`,
   `ZS-ASSERT-20`).
3. **What can be asserted instead of assumed?** An invariant the code depends on is checked at the
   boundary or written down as an assumption — never left implicit (`ZS-ERR-01`, `ZS-ASSERT-08`).
4. **What is asymmetric?** If `init` exists, does `deinit`? Do sibling functions take their
   parameters in the same order? Does every operation have its inverse? A missing half is either a
   restriction the documentation must state, or an oversight (`ZS-DATA-36`, `ZS-DATA-37`,
   `ZS-NAME-28`).
5. **What is special-cased?** A branch that exists for one input is a design that has not absorbed
   that input. Fold it into the general path, or give it its own type (`ZS-ERR-34`, `ZS-NAME-29`).

Simplicity outranks all five. A `comptime` construction that makes the reader hold three levels of
type substitution is worse than the duplication it removed (`ZS-COMPTIME-12`), and a symmetry nobody
can see is not worth the name it costs.

## 4. Core rules

- **Naming, Files, Module Layout, Declaration Order, Comments**
  - ZS-NAME-01 [M] Apply the official casing rules exactly
  - ZS-NAME-02 [M] Capitalize acronyms as ordinary English words
  - ZS-NAME-04 [M] Spell names out; abbreviate only as scope tightens
  - ZS-NAME-06 [M] Put units and qualifiers last, sorted by descending significance
  - ZS-NAME-12 [M] Name the receiver after its type; keep `self` for anonymous generic containers
  - ZS-NAME-13 [M] Name a file `TitleCase.zig` if and only if it has top-level fields
  - ZS-NAME-15 [M] Keep the `@This()` alias and the whole import block in one place
  - ZS-NAME-17 [M] Order a struct body: fields → types → `init`/`deinit` → methods → tests
  - ZS-NAME-18 [S] Put the entry point and the most important declarations first
  - ZS-NAME-22 [M] Say why, not what — including at the top of every test
  - ZS-NAME-23 [S] Comment typography: space after the slashes, capital letter, full stop
  - ZS-NAME-24 [M] Run `zig fmt`; the trailing comma is your only formatting lever
  - ZS-NAME-25 [M] Hard-limit every line to 100 columns
- **Type selection, integers, structs, data layout**
  - ZS-DATA-27 [M] Return the lowest-dimensionality type that can carry the answer
- **Errors, control flow, assertions vs errors vs panics**
  - ZS-ERR-01 [M] Classify a failure as a programmer error or an operating condition first
  - ZS-ERR-05 [M] Never put `anyerror` in a public signature
  - ZS-ERR-10 [M] Every error is handled somewhere; `catch {}` needs a justification comment
  - ZS-ERR-16 [M] Split compound conditions into separate checks
  - ZS-ERR-17 [S] Prefer a `switch` to an `else if` chain; if you flatten chains into trees, say why
  - ZS-ERR-18 [M] State invariants positively when an `if`/`else` splits the input space
  - ZS-ERR-19 [S] An `if` with no `else` over a validated domain carries a comment or an assertion
  - ZS-ERR-21 [M!] No recursion; where recursion is allowed, bound the depth explicitly
  - ZS-ERR-22 [M!] Push `if`s up and `for`s down
  - ZS-ERR-30 [M!] Hard limit of 70 lines per function
- **Memory, allocators, ownership lifetimes**
  - ZS-MEM-05 [M] Pass the allocator per call; do not store it in a field
  - ZS-MEM-06 [M] Name the allocator for its role — `gpa`, `arena`, `scratch` — and place it after the receiver
  - ZS-MEM-10 [M] Put `defer` / `errdefer` on the line immediately after the acquisition
  - ZS-MEM-15 [M] Pointers into container storage die on any capacity change
  - ZS-MEM-16 [M] If you need stable pointers, use `std.heap.MemoryPool(T)` or store indices
  - ZS-MEM-18 [M!] Allocate all memory at startup; allocate nothing in steady state
- **Performance and the discipline of locality**
  - ZS-PERF-13 [S] Shape functions like an inverted hourglass: narrow in, narrow out, wide inside
  - ZS-PERF-17 [M] Spell out the options that decide behavior; never inherit their defaults
- **Assertions, invariants, and putting a limit on everything**
  - ZS-ASSERT-02 [M] Never put a side effect in an `assert`, and never claim it is compiled out
  - ZS-ASSERT-05 [M!] Ship `safe` builds, or define a project-local always-on assert
  - ZS-ASSERT-09 [M!] Average at least two assertions per function
  - ZS-ASSERT-10 [M] Split compound assertions
  - ZS-ASSERT-11 [M] Write an implication as a single-line `if (a) assert(b);`
  - ZS-ASSERT-12 [M] Assert the negative space, and mark deliberate non-invariants with `maybe`
  - ZS-ASSERT-13 [M] State a biconditional as one `==` between two booleans
  - ZS-ASSERT-16 [M!] Pair every property across two code paths
  - ZS-ASSERT-20 [M] Put a limit on everything, and give the limit a name ending in `_max`
  - ZS-ASSERT-23 [M] Give every loop a provable bound; an unbounded loop must say so and assert it
  - ZS-ASSERT-24 [M] Fail fast: check the bound at the boundary where untrusted input enters
- **comptime, generics, and interfaces**
  - ZS-COMPTIME-10 [M] A `comptime` parameter the body does not depend on is a bug
  - ZS-COMPTIME-16 [M] Pick the interface shape from this table before writing any dispatch code
  - ZS-COMPTIME-17 [M] The runtime vtable is two fields; recover the impl by `@ptrCast(@alignCast(…))`
  - ZS-COMPTIME-18 [M] Embed a stateful interface as field `interface`; recover owner by `@fieldParentPtr`
  - ZS-COMPTIME-20 [M] A closed set of implementations is a tagged union, not an interface
- **build.zig, build.zig.zon, project layout, CI**
  - ZS-BUILD-25 [M!] Production builds are `safe` unless a measurement says otherwise

## 5. Review checklist

When reviewing or self-reviewing a Zig diff, walk this list. It is the review order of the full
protocol — severity model, mechanical pass, output format — in `references/review-checklist.md`.

1. **Stale API.** Any `std.io.*`, `std.fs.File`/`Dir`/`cwd`, `GeneralPurposeAllocator`,
   `usingnamespace`, `async`/`await` keywords, `@setCold`, `@Type`, `std.Thread.Mutex`,
   `std.time.Timer`, `BoundedArray`, `b.args`, `errdefer |err|`, `@cImport`, or
   `@typeInfo(T).@"struct".fields`? None of them builds on 0.17. `pub fn main() !void` still builds,
   but hands you no `Io`, `gpa` or arguments (ZS-MIG-08). The ones that still **compile** are the
   ones to grep for, because nothing else catches them: `indexOf*`, `ArrayListUnmanaged`,
   `*ArrayHashMapUnmanaged`, `std.fs.path`, `std.builtin`, `builtin.mode` and the TitleCase mode
   names, `DebugAllocator`, `std.fmt.allocPrint`/`bufPrint`, `getLast`, the `*BitSet` names,
   `lazyDependency`, `utf8Decode`/`wtf8Decode`, `std.debug.runtime_safety`. Then re-read every
   `containsAtLeastScalar` call and every `@hasDecl` on a private declaration: both compile and now
   mean something else. `references/migration.md` ZS-MIG-13 carries the complete denylist as one
   runnable `rg`; run that rather than eyeballing this sentence. And any `{}` applied to a type that
   defines `format`: that silently prints a default struct dump instead of calling it — it must be
   `{f}`.
2. **Memory and ownership.** Every allocation paired with a `defer`/`errdefer` at the same nesting
   level, and proved by the test allocator? Any pointer held across a container mutation? Allocators
   named for their lifetime?
3. **Illegal behavior.** Any `@intCast`/`@truncate` that can silently lose data, an index used where
   a count belongs, or division whose intent is not shown with `@divExact`, `@divFloor` or
   `@divCeil`?
4. **Errors.** Every error handled and named? Any `catch unreachable` that can really fire? Any
   `errdefer` missing on a multi-step construction? Every buffered writer flushed on every success
   path?
5. **Assertions and bounds.** Are the preconditions this function relies on asserted, and the
   negative space checked? Any assert with a side effect, or relied on in a `fast` build? Any loop,
   queue, or buffer whose maximum is not established?
6. **Public API.** Units last and descending, receivers named after their type rather than `self`,
   no abbreviations? Unpaired operations, siblings disagreeing on parameter order, error-set members
   with uneven detail, two mechanisms for one concept, a branch that exists for one input
   (`ZS-DATA-36` … `ZS-DATA-38`, `ZS-ERR-33`, `ZS-ERR-34`, `ZS-NAME-28` … `ZS-NAME-30`)?
7. **Concurrency.** Every `Io.async` awaited or cancelled, every `Group` and `Select` closed, and
   nothing held across a suspension point?
8. **Function bodies.** `zig fmt` clean, ≤100 columns, functions that fit on a screen, control flow
   in the parent? Does every non-obvious decision have a comment explaining the reasoning?
9. **Tests.** Does the change ship with the test that would have caught the bug? Does it exercise
   invalid input, not just valid?
10. **Build and project.** Every new dependency justified, `build.zig.zon` `.paths` correct, and
    `zig build check` passing?

## 6. Reference map

Load the chapter you need; do not load all of them. Every chapter opens with a table of contents
listing each rule it owns, so a cited ID can be resolved without reading the chapter through. The 0
`ZS-CORE-*` rules live in section 4 above; the other 356 live here.

| File | Rule IDs | Covers |
|---|---|---|
| `references/naming.md` | `ZS-NAME` (30) | Naming rules in full, file and module layout, declaration order, doc comments, formatting |
| `references/data.md` | `ZS-DATA` (38) | Integer choice, off-by-one discipline, casts, struct design, decl literals, result location semantics, in-place init, layout, data-oriented design |
| `references/errors.md` | `ZS-ERR` (34) | Error sets, `try`/`catch`/`errdefer`, the error-vs-assert-vs-panic decision table, labeled switch, `@branchHint`, logging |
| `references/memory.md` | `ZS-MEM` (26) | Allocator taxonomy, the allocator vtable, ownership rules, arena patterns, the static-allocation tiering |
| `references/concurrency.md` | `ZS-CONC` (44) | `std.Io` in full: `Reader`/`Writer`, custom streams, `Io.Dir`/`Io.File`, `async`/`concurrent`/`Group`/`Select`, cancellation, timeouts |
| `references/output.md` | `ZS-OUT` (17) | `{}` vs `{f}`, the specifier set, custom `format` methods, `std.fmt`, program output vs logging vs `std.debug.print` |
| `references/performance.md` | `ZS-PERF` (21) | Design-phase performance, back-of-envelope sketches, batching, `@prefetch`/`@Vector`, and the locality discipline (smallest scope, no aliasing, POCPOU, pure leaves) |
| `references/interop.md` | `ZS-INTEROP` (21) | `export`/`extern`/`callconv(.c)`, `[*c]` pointers, C strings and integers, callbacks with `userdata`, plus freestanding/WASM/single-threaded targets |
| `references/assertions.md` | `ZS-ASSERT` (26) | Assertion philosophy and density, pair assertions, comptime assertions, build-mode mechanics, `_max` constants |
| `references/comptime.md` | `ZS-COMPTIME` (21) | comptime rules, `anytype` and its costs, type introspection, the three interface shapes, anti-patterns |
| `references/testing.md` | `ZS-TEST` (26) | `std.testing` in 0.17, `Smith` fuzzing, allocation-failure testing, deterministic simulation |
| `references/build.md` | `ZS-BUILD` (39) | Annotated `build.zig` and `build.zig.zon`, dependencies, project layout, build modes, CI |
| `references/migration.md` | `ZS-MIG` (13) | Complete 0.13→0.17 migration tables and a stale-code smell test |
| `references/review-checklist.md` | — | The audit protocol: seven-level severity model, review order, mechanical greps, output format, and the order in which to refactor an existing codebase |

## 7. Bundled assets

Copy these rather than reconstructing them from memory; they encode decisions the rules only
describe. Each is derived from the chapter that owns it rather than written independently, so the
asset and the rule cannot drift apart.

| File | Contents |
|---|---|
| `assets/build.zig` | The complete library + CLI `build.zig` from ZS-BUILD-01, at 0.17.0: module-level `target`/`optimize`, one test binary per module, a separate `test-integration` step, a host-only codegen tool, and the `fmt` and `check` steps (`check` is the build-on-save step ZLS used; no ZLS release supports 0.17.0) |
| `assets/build.zig.zon` | The annotated manifest from ZS-BUILD-10…12: enum-literal `.name`, the `.fingerprint` warning, what `.minimum_zig_version` does and does not do, and `.paths` as the thing that defines the package hash |
| `assets/ci.yml` | The five CI requirements of ZS-BUILD-32 as a workflow — pinned toolchain, `fmt --check --ast-check`, `debug` and `safe`, the cross-compile matrix of ZS-BUILD-31, and a cache key naming every matrix axis. Only the `run:` lines are rules; verify the action versions yourself |
