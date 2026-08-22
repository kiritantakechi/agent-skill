# Memory, allocators, ownership lifetimes

Scope: choosing an allocator in Zig 0.16, the `std.mem.Allocator` vtable and its contracts, writing
a custom allocator, expressing and enforcing ownership (who allocates, who frees, what a returned
slice means), `defer`/`errdefer` discipline, pointer-invalidation traps, OOM policy, alignment, raw
memory copies, and the graduated ladder from "allocate freely" to TigerStyle's "no allocation after
startup".

This chapter does not own error-set design, `try`/`catch` selection, or `unreachable`-versus-error —
those are `references/errors-and-control-flow.md`. `Io.Reader`/`Io.Writer` buffer sizing is
`references/io-and-concurrency.md` ZS-IO-12 and ZS-IO-38; assertion density and bounded loops are
`references/assertions-and-limits.md`; `MultiArrayList` layout choices are
`references/types-and-data.md` ZS-TYPE-25; allocation-failure testing is
`references/testing-and-fuzzing.md` ZS-TEST-13. It cites them.

Every example assumes a file opening with `const std = @import("std");` and
`const assert = std.debug.assert;` — assertions are called bare, per ZS-ASRT-01.
## Contents

- **Choosing an allocator**
  - ZS-MEM-01 [M] Take `std.process.Init` in `main` and use the allocators it hands you
  - ZS-MEM-02 [M] A library never names a concrete allocator
  - ZS-MEM-03 [M] Pick the allocator from the taxonomy, not from habit
  - ZS-MEM-04 [M] Tests allocate through `std.testing.allocator` (see ZS-TEST-05)
  - ZS-MEM-05 [M] If you construct a `DebugAllocator` yourself, consume the `Check` from `deinit`
- **Passing and naming the allocator**
  - ZS-MEM-06 [M] Pass the allocator per call; do not store it in a field
  - ZS-MEM-07 [M] Name the allocator parameter for its role: `gpa`, `arena`, `scratch`
  - ZS-MEM-08 [M] Never hand out an `Allocator` whose backing state lives in a frame that returns
  - ZS-MEM-09 [M] One object, one allocator, for its whole lifetime
- **Ownership**
  - ZS-MEM-10 [M] Signal ownership transfer in the name and the doc comment
  - ZS-MEM-11 [M] Put `defer` / `errdefer` on the line immediately after the acquisition
  - ZS-MEM-12 [M] `errdefer` every fallible construction step, until ownership transfers
  - ZS-MEM-13 [M] `deinit` never fails, never allocates, and poisons the struct
  - ZS-MEM-14 [M] Use `toOwnedSlice` to hand a built buffer out of a builder
  - ZS-MEM-15 [M] Free exactly the slice you allocated
- **Invalidation**
  - ZS-MEM-16 [M] Pointers into container storage die on any capacity change
  - ZS-MEM-17 [M] If you need stable pointers, use `std.heap.MemoryPool(T)` or store indices
- **OOM policy**
  - ZS-MEM-18 [M] Libraries propagate `error.OutOfMemory`; only an application's top level may abort
  - ZS-MEM-19 [M!] Test allocating constructors with `checkAllAllocationFailures` (see ZS-TEST-13)
- **Static allocation and the graduated ladder**
  - ZS-MEM-20 [M!] Allocate all memory at startup; allocate nothing in steady state
  - ZS-MEM-21 [S] Arena per request, per phase, per iteration
  - ZS-MEM-22 [S] Preallocate to the known bound, then use `AssumeCapacity` in the hot path
  - ZS-MEM-23 [S] Impose a hard ceiling with a fixed backing buffer
- **The Allocator interface and custom allocators**
  - ZS-MEM-24 [M] Implement all four vtable members to their exact contracts
  - ZS-MEM-25 [M] Test a custom allocator with std's own conformance helpers
  - ZS-MEM-26 [M] Alignment is `std.mem.Alignment`, never a raw integer
- **Raw memory**
  - ZS-MEM-27 [M] `@memcpy` for disjoint copies, `@memmove` for overlapping ones
  - ZS-MEM-28 [M!] Zero padding before it leaves the process, and wipe secrets on the way out

---

## Choosing an allocator

### ZS-MEM-01 [M] Take `std.process.Init` in `main` and use the allocators it hands you
In Zig 0.16 `main` may take `std.process.Init` as its first parameter. Use `init.gpa` for
temporary/scoped heap and `init.arena.allocator()` for process-lifetime data. Do not hand-roll GPA
boilerplate in `main`.

**Why:** `std/start.zig` already runs the correct selection ladder for the target and optimize mode
(`DebugAllocator` in Debug, `c_allocator` when linking libc, `wasm_allocator` on wasm,
`smp_allocator` when multi-threaded and freestanding of libc), installs leak checking, creates the
process arena over `page_allocator`, and tears all of it down after `main` returns. Rolling your own
reproduces that ladder badly and usually loses the Debug-mode leak report.

**Check:** a `pub fn main` declared with no parameter, or with `Init.Minimal`, in a program that
allocates; and any `DebugAllocator`, `ArenaAllocator`, or `std.heap.*` constructed inside `main`
itself rather than taken from `init`.

```zig
// does-not-compile
pub fn main() !void {
    var gpa_state = std.heap.GeneralPurposeAllocator(.{}){}; // removed in 0.16
    defer _ = gpa_state.deinit();
    const gpa = gpa_state.allocator();
    _ = gpa;
}
comptime {
    _ = &main;
}
```

```zig
// verified
const std = @import("std");
pub fn main(init: std.process.Init) !void {
    const gpa = init.gpa; // temporary allocations, leak-checked in Debug
    const arena = init.arena.allocator(); // process lifetime, threadsafe, freed on exit

    var line: std.ArrayList(u8) = .empty;
    defer line.deinit(gpa);
    try line.appendSlice(gpa, "hello");

    const config_name = try arena.dupe(u8, line.items);
    std.log.info("{s}", .{config_name});
}
```

`std.process.Init` exactly (std/process.zig:30): `minimal: Minimal`, `arena:
*std.heap.ArenaAllocator` ("Threadsafe"), `gpa: Allocator` ("Threadsafe"), `io: Io`, `environ_map:
*Environ.Map` ("Not threadsafe"), `preopens: Preopens`. `Init.Minimal` (`environ`, `args`) is the
lighter alternative first parameter; `pub fn main() !void` still works but gives you nothing.

### ZS-MEM-02 [M] A library never names a concrete allocator
Library code takes `gpa: std.mem.Allocator` as a parameter. `std.heap.*` may not appear anywhere in
a reusable module — not `page_allocator`, not `c_allocator`, not `smp_allocator`, not a
`DebugAllocator` field.

**Why:** the allocator is the caller's memory policy. A library that picks `page_allocator` forces a
syscall per allocation on a caller who wanted an arena; a library that picks `c_allocator` forces a
libc link. Type-erasing behind the `Allocator` vtable costs one indirect call and lets the caller
supply an arena, a fixed buffer, or a failing allocator for tests.

**Check:** the token `std.heap.` in any file that is not a `main`, a test, a benchmark harness, or a
`build.zig` — `page_allocator` and `c_allocator` are the two that actually show up. Also a `pub fn`
that allocates and takes no `Allocator` parameter.

```zig
// fragment — BAD: the library chose for its caller.
pub fn parse(source: []const u8) !Ast {
    return parseInner(std.heap.page_allocator, source);
}
```

```zig
// fragment — GOOD
pub fn parse(gpa: std.mem.Allocator, source: []const u8) std.mem.Allocator.Error!Ast {
    return parseInner(gpa, source);
}
```

### ZS-MEM-03 [M] Pick the allocator from the taxonomy, not from habit
Every allocator in the table below has a specific niche. Choosing outside it is a defect, not a
preference.

**Why:** each row's cost is a documented property of the implementation, not a matter of taste, and
the penalty for choosing off-niche is order-of-magnitude rather than marginal. `page_allocator`
"makes a syscall directly for every allocation and free"; `DebugAllocator` spends "more than 100
bytes of overhead" on a one-byte allocation; `c_allocator` is a `@compileError` without
`builtin.link_libc` and forces a libc link on every downstream caller; `smp_allocator` asserts
`!builtin.single_threaded`; `FixedBufferAllocator`'s `free` reclaims only the last allocation.
Picking by habit therefore does not perform slightly worse — it usually either fails to build or
changes the program's syscall profile by a factor of thousands.

| Allocator | Use for | Thread safe | Cost | Gotchas |
|---|---|---|---|---|
| `std.heap.DebugAllocator(Config)` | Debug/ReleaseSafe builds; leak + double-free detection | Yes; `thread_safe = !builtin.single_threaded` | "when allocating a single byte, the efficiency is less than 1%; it requires more than 100 bytes of overhead" | Construct with `.init`; `deinit()` returns `Check` and must be consumed. Never reuses addresses |
| `std.heap.smp_allocator` | ReleaseFast/Small, multi-threaded, no libc | Yes (per-thread freelists) | Fast; per-thread slabs | Process-global singleton; `assert(!builtin.single_threaded)` so it is a compile error under `-fsingle-threaded` |
| `std.heap.c_allocator` | You already link libc, or you need platform `malloc` interop | Yes | libc malloc | `@compileError` unless `builtin.link_libc` |
| `std.heap.page_allocator` | Backing store for arenas / `DebugAllocator`; rare huge allocations | Yes | "makes a syscall directly for every allocation and free" | Never a general-purpose allocator |
| `std.heap.wasm_allocator` | wasm32/wasm64 | No | Small, fast | `WasmAllocator = if (builtin.single_threaded) BrkAllocator else @compileError("unimplemented")` |
| `std.heap.ArenaAllocator` | Request-scoped / phase-scoped bulk allocation | `alloc` is threadsafe if the child is; `deinit`, `reset`, `queryCapacity` documented "Not threadsafe." | Bump pointer | `deinit` takes the arena **by value**; `free` of a non-last allocation is a no-op |
| `std.heap.FixedBufferAllocator` | Bounded scratch work; a hard memory ceiling | `.allocator()` no; `.threadSafeAllocator()` yes (lock-free) — never mix the two handles | Zero syscalls | `free` reclaims only the last allocation, and `isLastAllocation` "has false negatives" |
| `std.heap.MemoryPool(T)` | Many same-typed nodes needing stable pointers | No | Arena + freelist | `.empty`, `create(gpa)`, `destroy(ptr)`, `deinit(gpa)` |
| `std.heap.stackFallback(N, fb)` | Small allocations that usually fit on the stack | Inherits fallback | One `[N]u8` stack array | `.allocator` is a `@compileError`; call `.get()`, which asserts it is called exactly once |
| `std.testing.allocator` | Tests | Yes | Debug-allocator cost | Distinct `canary` so mixing it with a default `DebugAllocator` panics |
| `std.testing.failing_allocator` | Injecting OOM at a chosen allocation index | No | None | Prefer `std.testing.checkAllAllocationFailures`, which drives it for you |
| `std.mem.Allocator.failing` | Proving a code path never allocates | n/a | None | `resize`/`remap`/`free` are `unreachable` — it asserts you never free through it |

> [!NOTE]
> `std.heap.ThreadSafeAllocator`, `std.heap.GeneralPurposeAllocator`, and
> `std.heap.LoggingAllocator` do **not** exist in 0.16 — zero hits in std, and
> `std.heap.ThreadSafeAllocator` is a `has no member named` compile error. Use
> `DebugAllocator(.{ .thread_safe = true })` or `smp_allocator` for thread safety, and
> `DebugAllocator(.{ .verbose_log = true })` for logging.

Defaults by program kind, matching std's own ladder in `std/start.zig:689`:

| Program | Default |
|---|---|
| CLI / application | `init.gpa` + `init.arena` from `std.process.Init` |
| Server | process gpa from `Init`; **one `ArenaAllocator` per request/connection**, `reset(.retain_capacity)` between requests |
| Library | no default — take `gpa: Allocator` (ZS-MEM-02) |
| Test | `std.testing.allocator` |
| Arena backing | `std.heap.page_allocator` (what `start.zig` uses); the gpa on wasm |

**Check:** `page_allocator` used as anything but backing for an arena or a `DebugAllocator`;
`DebugAllocator` on a `ReleaseFast`/`ReleaseSmall` path; `std.testing.allocator` outside a `test`
block; and `std.heap.ThreadSafeAllocator`, `std.heap.GeneralPurposeAllocator`, or
`std.heap.LoggingAllocator`, none of which exist in 0.16.

### ZS-MEM-04 [M] Tests allocate through `std.testing.allocator` (see ZS-TEST-05)
Owned by `references/testing-and-fuzzing.md` ZS-TEST-05. A `test` block allocates only from
`std.testing.allocator` — never `page_allocator`, never a locally constructed `DebugAllocator`,
never an arena that hides leaks — because the test runner inspects `allocator_instance` after each
test and fails the run on a leak, with the allocation site's stack trace.

### ZS-MEM-05 [M] If you construct a `DebugAllocator` yourself, consume the `Check` from `deinit`
`DebugAllocator.deinit()` returns `std.heap.Check` (`.ok` / `.leak`). Assert on it or turn it into a
non-zero exit; never `_ = da.deinit();`.

**Why:** the leak report is written by `deinit`, but the *decision* is the return value. Discarding
it means a leaking build exits 0 and CI stays green. Also construct with the decl literal `.init` —
default struct initialization is marked deprecated in the source.

**Check:** `grep -n '_ = .*\.deinit()'` — a discarded `Check` is the whole defect.

Applies **only when you cannot take `init.gpa`** (see ZS-MEM-01) — a benchmark harness, a custom
runtime, a `build.zig` step, a test that must exercise a non-default config. `main` takes
`std.process.Init` and never hand-rolls this:

```zig
// verified — a harness, not `main`
const std = @import("std");
const assert = std.debug.assert;
test "a self-constructed DebugAllocator must have its Check consumed" {
    var debug_allocator: std.heap.DebugAllocator(.{}) = .init;
    defer assert(debug_allocator.deinit() == .ok);
    const gpa = debug_allocator.allocator();

    const buf = try gpa.alloc(u8, 16);
    defer gpa.free(buf);
    @memset(buf, 0);
}
```

To get the three-trace double-free report (allocation, first free, second free), you must opt in:
`DebugAllocator(.{ .never_unmap = true, .retain_metadata = true })` plus
`deinitWithoutLeakChecks()`. With the default config a double free of a small allocation faults
inside `Allocator.free`'s `@memset(bytes, undefined)` before the detector can run.

---

## Passing and naming the allocator

### ZS-MEM-06 [M] Pass the allocator per call; do not store it in a field
Allocating methods take `gpa: Allocator` as their first parameter, including `deinit`. Reserve
allocator *fields* for types that are themselves allocator wrappers.

**Why:** this is the direction std moved and every allocator-in-a-field container in std is now
marked `Deprecated` (`array_list.Managed`, `heap.memory_pool.Managed`, `ArrayListAligned`). Three
concrete mechanisms: (1) it removes 16 bytes per instance, which matters when you hold a million of
them; (2) it makes every allocation point visible at the call site instead of hidden behind
`self.allocator`; (3) a struct with no allocator field can be memcpy'd, embedded, or moved without
carrying a pointer to a possibly-dead allocator state.

**Check:** a field of type `std.mem.Allocator` on any struct that is not itself an allocator
wrapper, and a `deinit`/`append`/`ensureTotalCapacity` call that passes no allocator. Grep for
`self.allocator` / `x.gpa` at an allocation site: that is the field this rule removes.

```zig
// does-not-compile
test "the 0.13 managed shape" {
    const gpa = std.testing.allocator;
    var list = std.ArrayList(u8).init(gpa); // ArrayList is unmanaged in 0.16: no `init`
    defer list.deinit();
    try list.append('x');
}
```

```zig
// verified
const std = @import("std");
test "the unmanaged shape" {
    const gpa = std.testing.allocator;
    var list: std.ArrayList(u8) = .empty; // decl literal
    defer list.deinit(gpa); // gpa on deinit too
    try list.append(gpa, 'x'); // gpa is the SECOND parameter of append
}
```

Legitimate exceptions: a type that *is* an allocator wrapper (`ArenaAllocator.child_allocator`,
`Io.Writer.Allocating`), and a top-level application context whose lifetime provably outlives
everything it hands memory to. Document the invariant in a doc comment when you take the exception.

### ZS-MEM-07 [M] Name the allocator parameter for its role: `gpa`, `arena`, `scratch`
`gpa` is the plurality name in std (345 occurrences vs 216 for `allocator`) and is TigerStyle's
recommendation too — one of the few places the two agree without qualification.

**Why:** `gpa` vs `arena` tells the reader, at the call site, whether the returned memory must be
individually freed. `allocator: Allocator` carries zero information beyond the type, which is
already in the signature. TigerStyle: "`allocator: Allocator` is a good, if boring name, but `gpa:
Allocator` and `arena: Allocator` are excellent."

**Check:** any parameter, field, or local of type `std.mem.Allocator` named `allocator`, `alloc`,
`ally`, or a single letter. The three legal names are `gpa`, `arena`, and `scratch`; a fourth needs
a comment saying what lifetime it denotes.

```zig
// fragment — GOOD: the names say who frees.
pub fn render(gpa: Allocator, arena: Allocator, doc: *const Doc) Allocator.Error![]u8 {
    const scratch = try arena.alloc(u8, doc.size_max); // dies with the arena
    _ = scratch;
    return gpa.dupe(u8, doc.title);                    // caller must free
}
```

### ZS-MEM-08 [M] Never hand out an `Allocator` whose backing state lives in a frame that returns
`ArenaAllocator.allocator()`, `FixedBufferAllocator.allocator()`, and
`DebugAllocator.allocator()` all embed `.ptr = self`. If `self` is a local, the `Allocator` value
becomes a dangling pointer the moment the function returns.

**Why:** the `Allocator` interface is `{ ptr: *anyopaque, vtable: *const VTable }`. Copying the
`Allocator` copies the pointer, not the state. Returning one from a function that owns the state on
its stack is a use-after-free that survives to the first allocation, arbitrarily far away.

**Check:** any function whose return type is `Allocator` — or a struct containing one — where the
backing state is a local `var` in that same function. Grep for `.allocator()` inside a `return`
expression and look at where its receiver was declared.

```zig
// fragment — BAD: `arena` dies at the closing brace; the returned Allocator dangles.
fn makeScratch(child: Allocator) Allocator {
    var arena: std.heap.ArenaAllocator = .init(child);
    return arena.allocator();
}
```

```zig
// fragment — GOOD: the caller owns the state; the interface never outlives it.
fn withScratch(child: Allocator, work: *const fn (Allocator) anyerror!void) !void {
    var arena: std.heap.ArenaAllocator = .init(child);
    defer arena.deinit();
    try work(arena.allocator());
}
```

The same applies to storing `*ArenaAllocator` (as `std.process.Init` does): store the pointer to
state whose lifetime you can name, and document it.

### ZS-MEM-09 [M] One object, one allocator, for its whole lifetime
The allocator passed to `deinit`, `append`, `ensureTotalCapacity`, and `free` must be the same one
that performed the original allocation.

**Why:** `std.zig:46` states it for `ArrayList`: "The same allocator must be used throughout its
entire lifetime." The vtable dispatch will happily route a free into an allocator that never owned
the block, corrupting its metadata. Because the allocator is now a parameter rather than a field
(ZS-MEM-06), nothing enforces this for you — it is a discipline, and it is the cost of the
unmanaged design.

**Check:** two different allocator names reaching one variable — `list.append(gpa, …)` above
`list.deinit(arena)`. Mechanically: for each `deinit`/`free`/`resize` in the diff, compare its
allocator argument textually with the one on the line that created the value; a mismatch is the
finding.

```zig
// fragment — BAD: allocated from `gpa`, freed through an arena that never owned it.
var list: std.ArrayList(u8) = .empty;
try list.append(gpa, 'x');
list.deinit(arena.allocator());
```

---

## Ownership

### ZS-MEM-10 [M] Signal ownership transfer in the name and the doc comment
A function that returns memory the caller must free says so: `/// Caller owns the returned memory.`
Follow std's vocabulary — `dupe`, `dupeSentinel`, `alloc*`, `create`, `clone`, `toOwnedSlice`, and
an `Alloc` suffix (`currentPathAlloc`) transfer ownership; `items`, `slice()`, `buffered()`,
`written()`, `getLast()`, `unusedCapacitySlice()` return a **borrow** valid only until the next
mutation.

**Why:** Zig has no ownership in the type system. `[]u8` returned from `dupe` and `[]u8` returned
from `list.items` are the same type and opposite contracts. The name and the one-line doc comment
are the entire enforcement mechanism, which is why std writes it on every such function
(`Allocator.dupe`: "Copies `m` to newly allocated memory. Caller owns the memory.").

**Check:** a `pub fn` returning `[]T`, `[]const T`, or `*T` whose doc comment says neither "Caller
owns" nor "Invalidated by"; and a function whose name comes from the borrow vocabulary (`items`,
`slice`, `written`, `buffered`, `view`) but whose body allocates.

```zig
// fragment
/// Caller owns the returned slice; free it with `gpa`.
pub fn renderTitle(gpa: Allocator, doc: *const Doc) Allocator.Error![]u8 {
    return gpa.dupe(u8, doc.title);
}

/// Borrowed view of the internal buffer. Invalidated by the next call to
/// `append` or `deinit`.
pub fn titleView(doc: *const Doc) []const u8 {
    return doc.title;
}
```

Corollary: take `[]const u8` for borrowed input. Take `[]u8` only when you will mutate or free it —
a `[]u8` parameter is a claim.

### ZS-MEM-11 [M] Put `defer` / `errdefer` on the line immediately after the acquisition
Two requirements, both binding. **Adjacency:** no statement may sit between an acquisition and its
release, and the release names the exact thing acquired (`gpa.free(buf)`, not `gpa.free(self.buf)`).
**Grouping:** the acquisition/release pair is separated from surrounding code by a blank line above
and below, so each pair reads as a two-line visual unit.

**Why:** the pairing is verified by eye, and both halves of the rule serve that. Any distance
between the two lines is a place where a future `return`, `try`, or early `break` can be inserted
without the reviewer noticing there is now a leak. The blank lines are what make the *absence* of a
release visible: in a blank-line-delimited group, a one-line group is an unpaired acquisition, and
the eye catches it without reading the identifiers. This is TigerStyle's formulation and it is the
reason the rule is about layout rather than only about order.

**Check:** in a diff, every `alloc`/`create`/`open`/`lock`/`init` line must be followed on the very
next line by `defer` or `errdefer`, and that two-line pair must be blank-line separated. Also flag a
`defer` whose argument is not textually the value produced on the line above.

```zig
// fragment — BAD: three fallible statements between alloc and defer, and no grouping.
const buf = try gpa.alloc(u8, n);
try validate(buf);
try prefill(buf);
defer gpa.free(buf);
```

```zig
// fragment — GOOD: adjacent, and blank-line grouped.
var file = try dir.openFile(io, "cfg.txt", .{});
defer file.close(io);

const buf = try gpa.alloc(u8, n);
defer gpa.free(buf);

try validate(buf);
try prefill(buf);
```

The same shape applies to every acquisition, not just allocation: `Io.File`/`Io.Dir` handles
(`defer file.close(io)`), `Io.Mutex` (`defer m.unlock(io)`), `Io.Group` (`defer g.cancel(io)`), and
`Io.Future` (`defer f.await(io)`). Where the release itself is fallible or cancelable, use the
`*Uncancelable` variant — a `defer` body cannot propagate an error (see
`references/io-and-concurrency.md` ZS-IO-29).

### ZS-MEM-12 [M] `errdefer` every fallible construction step, until ownership transfers
Multi-step `init` puts an `errdefer` after each allocation. The `errdefer`s stop where ownership
moves to a value that the caller will `deinit`.

**Why:** a `try` on step 3 unwinds steps 1 and 2 only if they registered `errdefer`s. Note the
semantics precisely: an `errdefer` fires only when an error leaves its *enclosing block*, it covers
only statements after it in the current iteration when it is inside a loop, and it does not fire on
a normal return. Getting this wrong produces leaks that only appear under memory pressure.

**Check:** in an `init`/`create` that performs two or more allocations, count `errdefer`s against
allocations: every allocation except the last needs one, minus any whose ownership provably moved on
the following line. A `try` sitting below an un-`errdefer`ed acquisition inside such a constructor
is the finding.

```zig
// verified
const std = @import("std");
const Allocator = std.mem.Allocator;

const Doc = struct {
    title: []u8,
    lines: std.ArrayList([]u8),

    /// Caller owns the returned `Doc`; release it with `deinit`.
    pub fn init(gpa: Allocator, title: []const u8) Allocator.Error!Doc {
        const owned_title = try gpa.dupe(u8, title);
        errdefer gpa.free(owned_title);

        var lines: std.ArrayList([]u8) = .empty;
        errdefer lines.deinit(gpa);
        try lines.ensureTotalCapacity(gpa, 4);

        return .{ .title = owned_title, .lines = lines };
    }

    pub fn deinit(doc: *Doc, gpa: Allocator) void {
        for (doc.lines.items) |line| gpa.free(line);
        doc.lines.deinit(gpa);
        gpa.free(doc.title);
        doc.* = undefined;
    }
};
```

Handing an item to a container is a transfer, so the `errdefer` covers only the gap:

```zig
// fragment
fn buildDoc(gpa: Allocator) !void {
    var doc: Doc = try .init(gpa, "hello");
    defer doc.deinit(gpa);

    const line = try gpa.dupe(u8, "world");
    errdefer gpa.free(line);        // only until append succeeds
    try doc.lines.append(gpa, line);
}
```

### ZS-MEM-13 [M] `deinit` never fails, never allocates, and poisons the struct
Signature `pub fn deinit(x: *T, gpa: Allocator) void`. It returns `void`, performs no fallible work,
and ends with `x.* = undefined;`.

**Why:** `deinit` is called from `defer`, where an error has nowhere to go, and from error
unwinding, where allocating again may fail for the same reason you are unwinding. `x.* = undefined`
turns a use-after-deinit into a detectable "branch on undefined value" in Debug/ReleaseSafe instead
of silent reuse of freed pointers; std does exactly this in `MemoryPool.deinit` and
`DebugAllocator.deinitWithoutLeakChecks`. It also makes `deinit` non-idempotent *loudly* — Zig has
no idempotent-deinit convention, and calling it twice is a double free.

**Check:** a `deinit` whose return type is not `void`; a `try`, a `catch`, or an `alloc`/`dupe`/
`create` inside a `deinit` body; and a `deinit` whose last statement is not `x.* = undefined;`.

Exception, and it is a real trap: `ArenaAllocator.deinit` takes the arena **by value**
(`pub fn deinit(arena: ArenaAllocator) void`), not by pointer.

### ZS-MEM-14 [M] Use `toOwnedSlice` to hand a built buffer out of a builder
When a container's job was to build one slice, transfer with `toOwnedSlice(gpa)` and let the
container fall back to `.empty` rather than copying and freeing by hand.

**Why:** `toOwnedSlice` shrinks the allocation to the exact length and hands you the pointer,
leaving the list valid and empty so an outstanding `defer list.deinit(gpa)` remains correct. Doing
it by hand (`const out = try gpa.dupe(u8, list.items)`) copies the whole buffer for nothing. 0.16
also offers `toOwnedSliceAssert(self)` and `toOwnedSliceSentinelAssert(self, sentinel)`, which take
no allocator and assert the capacity already fits — use those on the static-allocation path.

**Check:** a `gpa.dupe(…, list.items)` — or an `alloc` plus `@memcpy` from `.items` — followed by a
`list.deinit(gpa)`. That pair is `toOwnedSlice` written out longhand, and it copies the buffer for
nothing.

```zig
// verified
const std = @import("std");
test "toOwnedSlice transfers ownership" {
    const gpa = std.testing.allocator;
    var list: std.ArrayList(u8) = .empty;
    defer list.deinit(gpa); // Stays correct: toOwnedSlice leaves the list `.empty`.
    try list.appendSlice(gpa, "abc");

    const owned: []u8 = try list.toOwnedSlice(gpa);
    defer gpa.free(owned);
    try std.testing.expectEqualStrings("abc", owned);
}
```

### ZS-MEM-15 [M] Free exactly the slice you allocated
`free`, `resize`, and `remap` require `memory.len` to equal the length requested from the most
recent successful `alloc`/`resize`/`remap`, and the alignment to equal the original. Never free a
sub-slice, a re-sliced view, or a slice whose length you shortened by hand.

**Why:** it is a documented precondition on every vtable member, and allocators use the length to
find the size class. Passing `buf[0..n]` to `free` after allocating `buf.len > n` will return the
block to the wrong bucket. Track the original slice, and if you must narrow a view, keep both.
Freeing a **zero-length** slice is always legal and always a no-op (`if (bytes.len == 0) return;`),
so `.empty`-style teardown paths need no guard.

**Check:** a `free`, `resize`, or `remap` whose first argument is a slice *expression* rather than
the identifier bound on the allocation line — `gpa.free(buf[0..n])` and `gpa.free(x[1..])` are both
the finding. Also any `buf = buf[0..n]` reassignment above a later `gpa.free(buf)`.

```zig
// fragment — BAD: the free length is the slice, not the allocation
var buf = try gpa.alloc(u8, 4096);
const used = buf[0..n];
defer gpa.free(used);       // wrong length
```

```zig
// fragment — GOOD
var buf = try gpa.alloc(u8, 4096);
defer gpa.free(buf);
const used = buf[0..n];
```

If you genuinely want to shrink, use `gpa.realloc(buf, n)` (only fails on OOM, does the copy) or
`if (gpa.resize(buf, n)) buf = buf[0..n];` — `resize` is "guaranteed to not move the pointer", and
`remap` may move it, so reassign from its return value.

A related trap the type system does catch: `free` takes a **slice**, and slicing a `[*]T` with
comptime-known bounds produces a `*[N]T`, not a slice. `Allocator.free` opens with
`comptime assert(slice_info.size == .slice)`, so the mistake is a compile error rather than a
corruption — and it is a mistake std itself makes:

> [!NOTE] **At Zig 0.16.0 — re-check on a toolchain bump.**
> `Io.Dispatch.deinit()` — reached as `Io.Evented.deinit()` on macOS — does not compile.
> `Io/Dispatch.zig:584` is
> `ev.backing_allocator.free(ev.main_loop_stack[0..main_loop_stack_size])`, and
> `main_loop_stack` is `[*]align(...) u8` with `main_loop_stack_size` a `const`, so the slice
> expression is a `*[8192]u8`. The failure is `error: reached unreachable code` from the
> `comptime assert(slice_info.size == .slice)` at `mem/Allocator.zig:445`, referenced from
> `Dispatch.zig:584`.
> The backend itself runs; only tearing it down is a hard compile error, so a program that
> constructs `Io.Evented` and never calls `deinit` builds and works. This is a std bug, not a rule:
> do not design around it, just do not spend an afternoon on it. See
> `references/io-and-concurrency.md` ZS-IO-04 for the backend-choice rule.

---

## Invalidation

### ZS-MEM-16 [M] Pointers into container storage die on any capacity change
Every allocating container operation may reallocate: `append`, `appendSlice`, `appendNTimes`,
`insert`, `addOne`, `addManyAsSlice`, `ensureTotalCapacity`, `ensureUnusedCapacity`, `resize`,
`getOrPut`, and `put`. Across any of them, never hold `&list.items[i]`, `list.items` itself,
`list.items.ptr`, a `MultiArrayList.Slice`, `map.getPtr(k)`, `map.getEntry(k)`, or a
`GetOrPutResult.key_ptr`/`value_ptr`. Store an index and re-derive.

The full set of container types this covers: `std.ArrayList`, `std.MultiArrayList`, `std.Deque`,
`std.ArrayHashMap`/`std.array_hash_map.*`, and `std.HashMap`/`std.AutoHashMap`. Hash maps add a
second invalidation source that `ArrayList` does not have: a `remove`/`swapRemove` reorders or
tombstones entries even when capacity is unchanged, so an entry pointer is dead after *any*
removal, not only after growth. `std.heap.MemoryPool(T)` is the exception — it never moves an
existing item (ZS-MEM-17).

**Why:** `ArrayList` grows with `growCapacity(minimum) = minimum +| (minimum / 2 + init_capacity)`,
implemented as `remap` and falling back to alloc-copy-free. When it falls back, the old block is
handed to `Allocator.free`, which `@memset`s it to `undefined` before releasing it — so a retained
element pointer does not merely read stale data, it reads poison, and in ReleaseFast it reads
whatever the allocator reused the page for. This is the single most common memory bug in Zig code
that otherwise has no leaks.

```zig
// fragment — BAD
var list: std.ArrayList(u32) = .empty;
try list.append(gpa, 1);
const first = &list.items[0];
try list.append(gpa, 2);   // may reallocate
first.* = 3;               // use-after-free
```

```zig
// verified
const std = @import("std");
test "element pointers die on append; indices do not" {
    const gpa = std.testing.allocator;
    var list: std.ArrayList(u32) = .empty;
    defer list.deinit(gpa);

    try list.ensureTotalCapacity(gpa, 4);
    try list.append(gpa, 1);
    const index: usize = list.items.len - 1; // index, not pointer
    for (0..1000) |i| try list.append(gpa, @intCast(i));
    try std.testing.expectEqual(1, list.items[index]);
}
```

`MultiArrayList.slice()` must likewise be re-taken after any capacity change — it caches `ptrs`, one
base pointer per field, so a stale `Slice` is *N* dangling pointers rather than one.

**Check:** in a diff, any `&…items[`, `.getPtr(`, `.value_ptr`, `.items.ptr`, or `.slice()` whose
result is bound to a `const`/`var` that outlives the next container call. The safe shape binds the
pointer, uses it, and lets it die inside one statement or one tight block with no mutation in
between.

`references/types-and-data.md` ZS-TYPE-23 points here; ZS-TYPE-24 is the structural fix (a handle
newtype instead of a pointer).

### ZS-MEM-17 [M] If you need stable pointers, use `std.heap.MemoryPool(T)` or store indices
`std.SegmentedList` and `std.BoundedArray` no longer exist in 0.16. For "many nodes, pointers must
not move", the replacement is `MemoryPool(T)`, optionally with the intrusive `std.SinglyLinkedList`
/ `std.DoublyLinkedList` (a `Node` holds links only; recover the payload with `@fieldParentPtr`).

**Why:** `MemoryPool` allocates in arena chunks and never moves an existing item; freed items go on
a freelist and are reused in place. Indices, by contrast, cost a bounds check and survive every
reallocation, and `u32` indices halve the footprint of a graph versus 64-bit pointers.

**Check:** `std.SegmentedList` or `std.BoundedArray` in a diff — neither exists in 0.16, so both are
compile errors that point at exactly this decision. Then: a `*T` derived from container storage that
is stored in a field, pushed into a second container, or returned; and a hand-rolled
create/destroy freelist over `ArrayList` element addresses.

```zig
// verified
const std = @import("std");
test "MemoryPool gives stable pointers" {
    const gpa = std.testing.allocator;
    const Node = struct { value: u32 };
    var pool: std.heap.MemoryPool(Node) = .empty;
    defer pool.deinit(gpa);

    const first = try pool.create(gpa);
    first.* = .{ .value = 1 };
    for (0..1000) |_| _ = try pool.create(gpa);
    try std.testing.expectEqual(1, first.value);
}
```

---

## OOM policy

### ZS-MEM-18 [M] Libraries propagate `error.OutOfMemory`; only an application's top level may abort
Return `Allocator.Error!T` (or a set containing it). Never `catch @panic`, never `catch
unreachable`, never `catch return null` in reusable code. An application `main` may `return err`, or
a CLI may `std.process.fatal("out of memory", .{})` at the outermost layer.

**Why:** `Allocator.Error` has exactly one member, so `try` costs a single branch and the caller's
error set grows by one name. Aborting inside a library removes the caller's ability to shed load,
retry with a smaller batch, or fail one request instead of the process — and it makes the library
unusable inside a `FixedBufferAllocator`, where OOM is the *expected* signal that a bounded buffer
is full, not a fatal condition.

**Check:** `catch @panic`, `catch unreachable`, `catch return null`, or `catch return .{}` on any
expression whose error set contains `error.OutOfMemory`, in a file that is neither a `main` nor a
test. Also a `pub fn` that allocates and whose return type is not an error union.

```zig
// fragment — BAD: in a library
pub fn parse(gpa: Allocator, source: []const u8) Ast {
    return parseInner(gpa, source) catch @panic("OOM");
}
```

```zig
// fragment — GOOD
pub const ParseError = Allocator.Error || error{ UnexpectedToken, Truncated };
pub fn parse(gpa: Allocator, source: []const u8) ParseError!Ast {
    return parseInner(gpa, source);
}
```

To bound an application's heap rather than abort on it, use
`DebugAllocator(.{ .enable_memory_limit = true })` and set `da.requested_memory_limit` — allocations
past the limit return `error.OutOfMemory` through the normal path.

### ZS-MEM-19 [M!] Test allocating constructors with `checkAllAllocationFailures` (see ZS-TEST-13)
Owned by `references/testing-and-fuzzing.md` ZS-TEST-13. The `errdefer` chains built under ZS-MEM-12
are dead code in every normal test run, so drive them with
`std.testing.checkAllAllocationFailures(backing, test_fn, extra_args)`, which re-runs `test_fn`
failing allocation *i* for every *i*. `[M!]` triggers and the relaxed form live with the owner.

The memory-side corollary the owner does not cover: to prove a path allocates *nothing*, pass
`std.mem.Allocator.failing` — its `resize`, `remap`, and `free` are `unreachable`, so it also
catches a stray free through the wrong allocator (ZS-MEM-09).

---

## Static allocation and the graduated ladder

### ZS-MEM-20 [M!] Allocate all memory at startup; allocate nothing in steady state
TigerStyle, verbatim: "All memory must be statically allocated at startup. **No memory may be
dynamically allocated (or freed and reallocated) after initialization.**" Adopt this in full only
when the criteria below hold; otherwise adopt the graduated forms ZS-MEM-21 through ZS-MEM-23, which
are `[S]` for all code.

**Why:** five separate guarantees, each of which holds on its own.
- Peak RSS is known before the first request, so the process cannot be OOM-killed by a workload
  spike and the operator can size the machine exactly.
- `error.OutOfMemory` disappears from the steady-state error sets, deleting an entire class of
  partially-initialized-object bugs and the `errdefer` chains that handle them.
- Use-after-free becomes impossible for anything in the static set: nothing is freed, so nothing
  dangles. Fragmentation is impossible: there is no allocator to fragment.
- Latency loses its worst tail. No `mmap`, no page fault on first touch during a request, no
  1.5x-growth memcpy of a 100 MB list in the middle of a hot loop.
- The design pressure is the real payoff: you cannot write "allocate as needed", so you must derive
  the maximum number of in-flight operations, the maximum message size, and the maximum queue depth
  — and having derived them, you can assert them.

**What it costs:**
- You must size everything up front, and getting it wrong converts a soft failure (slower, more RSS)
  into a hard one (reject the work, or `fatal` with an operator-actionable message).
- Over-provisioning is paid in resident memory at all times, not just at peak.
- Large parts of std become unavailable: anything that allocates internally at use time —
  `std.json` parsing, `std.zig.Ast`, hash maps that grow, `Io.Writer.Allocating`. TigerBeetle's own
  answer was to write `src/stdx` and reimplement bounded arrays, bit sets, and PRNGs.
- `std.BoundedArray` was removed in 0.16, so the bounded containers you need are `ArrayList` over a
  fixed buffer (ZS-MEM-23), your own fixed pools, or third-party code.

**`[M!]` trigger — adopt it in full only when all of these hold:** (1) every resource bound is
derivable from configuration at startup — max connections, max message bytes, max in-flight
operations; (2) the process is long-lived and a restart is expensive or externally visible (a
replica, a controller, an embedded device, a hard-real-time loop); (3) rejecting work is a better
failure than growing memory — i.e. an OOM kill would cost correctness, quorum, or a machine; (4) you
own the dependency tree and are not calling into libraries that allocate on your behalf; (5) it is
an application or a service, not a library — forcing this policy on your callers is not your
decision to make.

**Do not adopt it when:** input size is unbounded and user-supplied (compilers, CLIs over arbitrary
files, general-purpose servers with variable payloads), or you depend on std subsystems that
allocate at use time, or you are writing a library.

***Relaxed form:*** the graduated ladder below, in descending strength — ZS-MEM-23, a hard ceiling
from a fixed backing buffer (`ArrayList.initBuffer` or `FixedBufferAllocator`); ZS-MEM-21, an arena
per request or phase, reset at the boundary; ZS-MEM-22, `ensureTotalCapacity` up front and
`*AssumeCapacity` in the hot path. Pick exactly one rung, name it in the module's doc comment, and
treat an allocation inside a hot loop or on a request path as a design smell requiring a justifying
comment. What does not relax at any tier: derive the bounds, write them down as `_max` constants,
and `comptime`-assert them.

**Check:** under the trigger, an `alloc`/`create`/`dupe`/`append`/`ensureTotalCapacity` reachable
from a request path rather than from `init` — and, before that, the absence of the `StaticAllocator`
gate itself, which is what converts this from a review question into an assertion failure. Under the
relaxed form: an allocation inside a loop or on a per-request path with no comment naming which rung
of ZS-MEM-21..23 the module chose.

The enforcement mechanism that turns the policy into an invariant is an allocator gate: allocate
during `init`, then flip a state flag so that any later `alloc` trips an assert.

```zig
// verified
const std = @import("std");
const assert = std.debug.assert;
const Allocator = std.mem.Allocator;
const Alignment = std.mem.Alignment;

const StaticAllocator = struct {
    parent: Allocator,
    state: State,

    const State = enum { init, static, deinit };

    pub fn init(parent: Allocator) StaticAllocator {
        return .{ .parent = parent, .state = .init };
    }

    pub fn allocator(sa: *StaticAllocator) Allocator {
        return .{ .ptr = sa, .vtable = &.{
            .alloc = alloc,
            .resize = resize,
            .remap = remap,
            .free = free,
        } };
    }

    pub fn transitionToStatic(sa: *StaticAllocator) void {
        assert(sa.state == .init);
        sa.state = .static;
    }

    pub fn transitionToDeinit(sa: *StaticAllocator) void {
        assert(sa.state == .static);
        sa.state = .deinit;
    }

    fn alloc(ctx: *anyopaque, len: usize, alignment: Alignment, ra: usize) ?[*]u8 {
        const sa: *StaticAllocator = @ptrCast(@alignCast(ctx));
        assert(sa.state == .init);
        return sa.parent.rawAlloc(len, alignment, ra);
    }

    fn resize(ctx: *anyopaque, buf: []u8, a: Alignment, new_len: usize, ra: usize) bool {
        const sa: *StaticAllocator = @ptrCast(@alignCast(ctx));
        assert(sa.state == .init);
        return sa.parent.rawResize(buf, a, new_len, ra);
    }

    fn remap(ctx: *anyopaque, buf: []u8, a: Alignment, new_len: usize, ra: usize) ?[*]u8 {
        const sa: *StaticAllocator = @ptrCast(@alignCast(ctx));
        assert(sa.state == .init);
        return sa.parent.rawRemap(buf, a, new_len, ra);
    }

    fn free(ctx: *anyopaque, buf: []u8, a: Alignment, ra: usize) void {
        const sa: *StaticAllocator = @ptrCast(@alignCast(ctx));
        // `free` stays legal during init so errdefer cleanup can run.
        assert(sa.state == .init or sa.state == .deinit);
        sa.parent.rawFree(buf, a, ra);
    }
};

test "allocation is a startup-only privilege" {
    var sa: StaticAllocator = .init(std.testing.allocator);
    const gpa = sa.allocator();

    const buffers = try gpa.alloc(u8, 1024);
    sa.transitionToStatic();
    @memset(buffers, 0); // steady state: any alloc through `gpa` trips the assert

    sa.transitionToDeinit();
    gpa.free(buffers);
}
```

> **Where TigerStyle and idiomatic std genuinely disagree.** Std's entire culture is
> allocator-passing: `ArrayList`, every hash map, `std.json`, and `Io.Writer.Allocating` all
> allocate at use time, and 0.16 removed `std.BoundedArray`, the one container that made "no
> allocation after init" ergonomic. TigerStyle's position is that this is a design smell for systems
> that must not fail. Both are right about their own domain. The recommendation, keyed to the tiers:
> `[M!]` full static allocation with a gate for high-reliability systems meeting the five criteria
> above; `[S]` for everyone else, meaning **allocate during `init`, treat an allocation inside a hot
> loop or on a request path as a design smell requiring a justifying comment**, and use
> ZS-MEM-21..23 where a bound is natural. What you keep in every case is the cultural payoff: know
> your bounds, write them down as `_max` constants, and `comptime`-assert them.

Related TigerStyle position worth naming: their bounded containers `assert(!full())` on push rather
than returning an error, on the grounds that overflow is a programmer error. Std's equivalents
(`appendBounded`, `appendSliceBounded`, `addManyAsSliceBounded`) return `error.OutOfMemory`. Use the
std form at any boundary where the length comes from outside your control; the asserting form only
when the bound is provable locally.

### ZS-MEM-21 [S] Arena per request, per phase, per iteration
Give each unit of work an `ArenaAllocator`; free the whole thing at the end of the unit instead of
freeing individual objects. Reset with `.retain_capacity` between units, or
`.{ .retain_with_limit = N }` on a long-running server.

**Why:** a request's allocation graph is a tree that dies all at once. An arena turns N frees into
one, removes every intermediate `errdefer` on that path, and makes leaks structurally impossible
within the unit. `.retain_capacity` preheats the arena so that after the largest request, steady
state performs no backing allocations at all — which is static allocation arrived at empirically.
`.retain_with_limit` caps the RSS a single pathological request can pin forever.

**Check:** an `ArenaAllocator` constructed *inside* the loop or handler it serves rather than
outside it with a `reset` at the boundary; a pointer derived from arena memory that is stored
somewhere outliving the `reset`/`deinit`; and any `reset`, `deinit`, or `queryCapacity` on an arena
that another task can still be allocating from — those three are documented "Not threadsafe."

```zig
// verified
const std = @import("std");
test "arena per phase" {
    var arena: std.heap.ArenaAllocator = .init(std.heap.page_allocator);
    defer arena.deinit();

    for (0..3) |_| {
        defer _ = arena.reset(.{ .retain_with_limit = 1 << 20 });
        const a = arena.allocator();
        const scratch = try a.alloc(u8, 512);
        @memset(scratch, 0);
    }
}
```

Rules that come with it: never return arena memory past the reset point; never mix arena-owned and
gpa-owned pointers in one struct without a doc comment saying which is which; never call
`deinit`/`reset`/`queryCapacity` concurrently with work — `alloc` is threadsafe in 0.16 but those
three are documented "Not threadsafe.", so quiesce every worker first.

### ZS-MEM-22 [S] Preallocate to the known bound, then use `AssumeCapacity` in the hot path
When you know the count, `ensureTotalCapacity` once outside the loop and call
`appendAssumeCapacity` / `appendSliceAssumeCapacity` / `addManyAsSliceAssumeCapacity` inside it.

**Why:** it moves the only fallible operation out of the loop, so the loop body has no error path
and no branch on growth; and it removes the 1.5x-growth memcpy entirely. `growCapacity` is `minimum
+| (minimum / 2 + init_capacity)`, so an unprepared 1024-element build performs ~17 reallocations
and copies roughly 3 KB of already-written data. `AssumeCapacity` is also the exact shape a later
migration to full static allocation needs.

**Check:** a `try list.append(gpa, …)` or `try list.appendSlice(gpa, …)` inside a loop whose trip
count is already known above the loop — it is in the `for` range, or in a `.len` read, or in a named
`_max`. That is `ensureTotalCapacity` once plus `appendAssumeCapacity` inside.

```zig
// verified
const std = @import("std");
test "preallocate then AssumeCapacity in the hot path" {
    const gpa = std.testing.allocator;
    var ids: std.ArrayList(u32) = .empty;
    defer ids.deinit(gpa);

    try ids.ensureTotalCapacity(gpa, 1024);
    for (0..1024) |i| ids.appendAssumeCapacity(@intCast(i));
    try std.testing.expectEqual(1024, ids.items.len);
}
```

### ZS-MEM-23 [S] Impose a hard ceiling with a fixed backing buffer
For work with a natural bound, allocate from a `[N]u8` — either `ArrayList.initBuffer` (the 0.16
replacement for the removed `std.BoundedArray`) or `std.heap.FixedBufferAllocator` when a subsystem
demands an `Allocator`.

**Why:** the bound becomes a compile-time constant that the reader can see and the reviewer can
audit, and exhaustion surfaces as `error.OutOfMemory` at a known point instead of as unbounded RSS
growth. `initBuffer` gives a list with `capacity = buffer.len` and no allocator at all; only the
`*AssumeCapacity` and `*Bounded` methods are legal on it, and the `*Bounded` ones return
`error{OutOfMemory}` without taking a `gpa`.

**Check:** a list created with `.initBuffer` and later passed to any `gpa`-taking method — that
allocator never owned the backing array (ZS-MEM-09), so growth corrupts it. Conversely, a fixed
`[N]u8` declared beside a list that is nevertheless fed through a `gpa`, and any
`FixedBufferAllocator` whose `free` is relied on for anything but the most recent allocation.

```zig
// verified
const std = @import("std");
test "fixed backing buffer, no allocator" {
    var backing: [64]u8 = undefined;
    var line: std.ArrayList(u8) = .initBuffer(&backing);
    line.appendSliceAssumeCapacity("id=");
    try line.appendBounded('7');
    try std.testing.expectEqualStrings("id=7", line.items);
}

test "FixedBufferAllocator as a hard memory ceiling" {
    var scratch: [4096]u8 = undefined;
    var fba: std.heap.FixedBufferAllocator = .init(&scratch);
    const scratch_gpa = fba.allocator();

    const buf = try scratch_gpa.alloc(u8, 128);
    try std.testing.expectEqual(128, buf.len);
    try std.testing.expectError(error.OutOfMemory, scratch_gpa.alloc(u8, 1 << 20));
}
```

Two `FixedBufferAllocator` traps: `free` reclaims only the most recent allocation (and
`isLastAllocation` "has false negatives when the last allocation had an adjusted_index"), so treat
it as reset-only; and `.allocator()` and `.threadSafeAllocator()` must never be used against the
same instance concurrently.

---

## The Allocator interface and custom allocators

### ZS-MEM-24 [M] Implement all four vtable members to their exact contracts
The 0.16 `Allocator.VTable` is `alloc`, `resize`, `remap`, `free`. `remap` is newer than most
Zig material — it is not optional and it is not `resize`.

**Why:** `Allocator.resize` is documented "guaranteed to not move the pointer", and that guarantee
is load-bearing: it is what makes it safe to keep interior pointers across a successful `resize` and
never across a `remap`. An allocator that returns a moved pointer from `resize` silently breaks
every caller relying on it, and the breakage surfaces as a dangling interior pointer far from your
code. The four members are also not independently optional — the vtable is a struct literal, so a
missing member is a compile error, and a member you cannot implement has a provided stand-in
(`Allocator.noAlloc` / `noResize` / `noRemap` / `noFree`) rather than an invented behavior.

**Check:** a `resize` implementation with any path that relocates before returning `true`; a `remap`
that returns a pointer it did not obtain from the same block without copying; a hand-written
always-fail stub where `Allocator.noAlloc`/`noResize`/`noRemap`/`noFree` exists; and a vtable
literal assembled by copying `resize` into the `remap` slot without adjusting its return type.

```zig
// fragment
pub const VTable = struct {
    alloc: *const fn (*anyopaque, len: usize, alignment: Alignment, ret_addr: usize) ?[*]u8,
    resize: *const fn (*anyopaque, memory: []u8, alignment: Alignment,
        new_len: usize, ret_addr: usize) bool,
    remap: *const fn (*anyopaque, memory: []u8, alignment: Alignment,
        new_len: usize, ret_addr: usize) ?[*]u8,
    free: *const fn (*anyopaque, memory: []u8, alignment: Alignment, ret_addr: usize) void,
};
```

Contracts, from the doc comments:
- **`alloc`** — return `len` bytes satisfying `alignment`, or `null`. `ret_addr == 0` means no
  return address was provided. Callers never request `len == 0`.
- **`resize`** — `memory.len` must equal the length from the most recent successful
  `alloc`/`resize`/`remap`; `alignment` must equal the original. `true` means success **at the same
  address**; `false` means it could not be done in place. `new_len > 0`.
- **`remap`** — same preconditions. Non-`null` means success and **the address may have changed**.
  `null` means "the resize would be equivalent to allocating new memory, copying the bytes, and
  freeing the old memory. In such case, it is more efficient for the caller to perform the copy" —
  so returning `null` is a *correct, cheap* answer, not a failure to be avoided.
- **`free`** — same preconditions; invalidates the region.

```zig
// verified
const std = @import("std");
const Allocator = std.mem.Allocator;
const Alignment = std.mem.Alignment;

const Bump = struct {
    buffer: []u8,
    end: usize = 0,

    pub fn allocator(b: *Bump) Allocator {
        return .{ .ptr = b, .vtable = &.{
            .alloc = alloc,
            .resize = resize,
            .remap = remap,
            .free = free,
        } };
    }

    fn isLast(b: *Bump, buf: []u8) bool {
        return buf.ptr + buf.len == b.buffer.ptr + b.end;
    }

    fn alloc(ctx: *anyopaque, len: usize, alignment: Alignment, _: usize) ?[*]u8 {
        const b: *Bump = @ptrCast(@alignCast(ctx));
        const base = @intFromPtr(b.buffer.ptr);
        const start = alignment.forward(base + b.end) - base;
        if (start + len > b.buffer.len) return null;
        b.end = start + len;
        return b.buffer.ptr + start;
    }

    fn resize(ctx: *anyopaque, buf: []u8, _: Alignment, new_len: usize, _: usize) bool {
        const b: *Bump = @ptrCast(@alignCast(ctx));
        if (!b.isLast(buf)) return new_len <= buf.len;
        const start = b.end - buf.len;
        if (start + new_len > b.buffer.len) return false;
        b.end = start + new_len;
        return true;
    }

    fn remap(ctx: *anyopaque, buf: []u8, a: Alignment, new_len: usize, ra: usize) ?[*]u8 {
        return if (resize(ctx, buf, a, new_len, ra)) buf.ptr else null;
    }

    fn free(ctx: *anyopaque, buf: []u8, _: Alignment, _: usize) void {
        const b: *Bump = @ptrCast(@alignCast(ctx));
        if (b.isLast(buf)) b.end -= buf.len;
    }
};
```

Two structural rules: return the `Allocator` from a method taking `*Self` and set `.ptr = self`
(never from a value about to be copied — see ZS-MEM-08); and if the allocator is stateless, set
`.ptr = undefined` and expose `pub const vtable: Allocator.VTable`, as `PageAllocator` and
`SmpAllocator` do — but then any comparison of `.ptr` is illegal behavior.

### ZS-MEM-25 [M] Test a custom allocator with std's own conformance helpers
Run `std.heap.testAllocator`, `testAllocatorAligned`, `testAllocatorLargeAlignment`, and
`testAllocatorAlignedShrink` against it, and wrap it in `std.mem.validationWrap` while developing.

**Why:** these are the exact tests std runs against its own allocators; they exercise the
resize/remap/free preconditions you are most likely to get subtly wrong. `validationWrap` "asserts
that allocation sizes are greater than zero and returned pointers have correct alignment" — it
checks both sides of the contract, so it catches a *caller* violating the vtable as well as your
allocator.

**Check:** a type with an `allocator()` method and no `std.heap.testAllocator*` call anywhere in its
tests. All four helpers are cheap to add at once, so one of them present and the other three missing
is also a finding.

```zig
// fragment
test "Bump obeys the Allocator contract" {
    var backing: [1 << 20]u8 = undefined;
    var bump: Bump = .{ .buffer = &backing };
    try std.heap.testAllocator(bump.allocator());
    bump.end = 0;
    try std.heap.testAllocatorAligned(bump.allocator());
}
```

### ZS-MEM-26 [M] Alignment is `std.mem.Alignment`, never a raw integer
`alignedAlloc` takes `comptime alignment: ?Alignment`, where `null` means natural alignment. Build
values with `.of(T)`, `.fromByteUnits(n)`, or the named variants `.@"1"` … `.@"64"`.

**Why:** `Alignment` is `enum(math.Log2Int(usize))`, i.e. the log2 of the byte count, so passing
`4096` where an `Alignment` is expected is a compile error rather than a 4096-fold
misinterpretation. It also carries the operations you actually need — `forward` (round up),
`backward` (round down), `check`, `order`, `max`, `min`, `toByteUnits` — so alignment arithmetic
stops being hand-rolled masking. Only `.@"1"` through `.@"64"` are named; larger values must go
through `.fromByteUnits`.

```zig
// verified
const std = @import("std");
test "alignment is mem.Alignment, not an integer" {
    const gpa = std.testing.allocator;
    const page: []align(4096) u8 = try gpa.alignedAlloc(u8, .fromByteUnits(4096), 4096);
    defer gpa.free(page);
    const a: std.mem.Alignment = .fromByteUnits(4096);
    try std.testing.expect(a.check(@intFromPtr(page.ptr)));

    const nodes = try gpa.alignedAlloc(u64, .of(u64), 8);
    defer gpa.free(nodes);
}
```

`gpa.alloc(T, n)` is already naturally aligned; reach for `alignedAlloc` only for O_DIRECT buffers,
DMA, SIMD loads, or cache-line-isolated shared state (`std.atomic.cache_line`).

Convert only at the boundary. An `Alignment` reaches a C API or a syscall through `.toByteUnits()`
and arrives from one through `.fromByteUnits(n)` (which asserts `n` is a power of two); in between,
keep the `Alignment` and use its own operations — `forward`, `backward`, `check`, `order`, `max`,
`min` — rather than reconstructing `(x + a - 1) & ~(a - 1)` by hand. Writing a custom allocator
means implementing the vtable against `Alignment` directly (ZS-MEM-24), never an integer.

**Check:** any `align` or alignment-named parameter, field, or `const` typed as an integer; any
`@alignOf(T)` or `1 << n` passed where an `Alignment` belongs; any hand-rolled `& ~(align - 1)`
masking. `references/types-and-data.md` ZS-TYPE-22 points here.

---

## Raw memory

### ZS-MEM-27 [M] `@memcpy` for disjoint copies, `@memmove` for overlapping ones
`@memcpy(dest, source)` requires the regions not to overlap and the lengths to match. When source
and destination may overlap — a ring buffer, an in-place shift — use `@memmove`.
`std.mem.copyForwards` and `std.mem.copyBackwards` are marked deprecated in 0.16 ("This function is
deprecated; use @memmove instead").

**Why:** `@memcpy` on overlapping regions is illegal behavior, not merely wrong output — the
optimizer is allowed to assume non-aliasing and vectorize. The old `copyForwards`/`copyBackwards`
pair made *you* responsible for choosing the direction based on pointer order, which is exactly the
comparison `@memmove` performs correctly for you. Use `@memset` rather than a zeroing loop for the
same vectorization reason.

**Check:** a `@memcpy` whose two arguments are slices of the same base array or the same pointer —
`@memcpy(ring[1..8], ring[0..7])` is the shape. Also `std.mem.copyForwards`/`copyBackwards`
anywhere (both deprecated in 0.16), and a byte-at-a-time loop that only writes a constant.

```zig
// verified
const std = @import("std");
test "disjoint copy vs overlapping copy" {
    var ring: [8]u8 = "abcdefgh".*;
    @memmove(ring[1..8], ring[0..7]); // overlapping
    try std.testing.expectEqualStrings("aabcdefg", &ring);

    var out: [4]u8 = undefined;
    @memcpy(&out, ring[0..4]); // disjoint, equal lengths
    try std.testing.expectEqualStrings("aabc", &out);
}
```

### ZS-MEM-28 [M!] Zero padding before it leaves the process, and wipe secrets on the way out
Any buffer written to disk, sent on the wire, or handed to another process must have every byte
defined — including struct padding and the unused tail of a fixed-size frame. Wipe key material with
`std.crypto.secureZero(T, slice)`, not `@memset`.

**Why:** this is the Heartbleed class of bug — a buffer *underflow*, where the buffer is not fully
utilized and the padding is not zeroed, so uninitialized heap contents (previous requests, keys)
travel out with the message. It also breaks byte-for-byte determinism, which anything doing
checksums, replication, or record-and-replay depends on. `@memset(&key, 0)` on a value that is dead
afterwards is dead-store-eliminated by the optimizer; `secureZero` takes `[]volatile T`, which
"Prevents the store from being optimized out".

**`[M!]` trigger:** the bytes cross a trust or durability boundary — key material and other secrets,
anything sent to a peer you do not control, anything persisted, and anything checksummed,
replicated, or record-and-replayed. ***Relaxed form:*** everywhere else, initialize any buffer that
leaves the process with `= @splat(0)` rather than `= undefined`, and give serialized types `extern`
or `packed` layout with named, `0`-defaulted reserved fields. `secureZero` is required only where
key material is involved; nothing relaxes the requirement that padding be a named field.

**Check:** an array declared `= undefined` that reaches `writeAll`, a socket write, or a
`MemoryMap`; a plain (non-`extern`, non-`packed`) struct passed to `std.mem.asBytes` for
serialization; a reserved field with no `= 0` default; and `@memset(&key, 0)` on key material, where
`std.crypto.secureZero` is the only form the optimizer is forbidden to delete.

```zig
// fragment — BAD: `_reserved` is never written, and `frame` is `undefined`.
var frame: [8]u8 = undefined;
const h: Header = .{ .tag = 3, .len = 17 }; // no default for `_reserved`
@memcpy(&frame, std.mem.asBytes(&h));
try w.writeAll(&frame);                     // w: *std.Io.Writer — ships 2 bytes of heap
```

```zig
// verified
const std = @import("std");
const assert = std.debug.assert;
const Header = extern struct {
    tag: u16,
    _reserved: u16 = 0, // explicit default: padding is a field, and it is zero
    len: u32,
};

test "no padding bleed on the wire" {
    comptime assert(@sizeOf(Header) == 8);
    var frame: [@sizeOf(Header)]u8 = @splat(0);
    const h: Header = .{ .tag = 3, .len = 17 };
    @memcpy(&frame, std.mem.asBytes(&h));
    try std.testing.expectEqual(0, frame[2]);
    try std.testing.expectEqual(0, frame[3]);
}

test "wipe secrets before the frame returns" {
    var key: [32]u8 = @splat(0xAB);
    defer std.crypto.secureZero(u8, &key);
    try std.testing.expectEqual(0xAB, key[0]);
}
```

Make padding explicit rather than implicit: give serialized types `extern` or `packed` layout, name
the reserved fields, default them to `0`, and `comptime`-assert `@sizeOf`. A plain `struct` may
reorder fields and its padding is not yours to control.
