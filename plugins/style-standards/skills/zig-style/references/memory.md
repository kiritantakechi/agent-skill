# Memory, allocators, ownership lifetimes

Scope: choosing an allocator in Zig 0.17, the `std.mem.Allocator` vtable and its contracts, writing
a custom allocator, expressing and enforcing ownership (who allocates, who frees, what a returned
slice means), `defer`/`errdefer` discipline, pointer-invalidation traps, OOM policy, alignment, raw
memory copies, and the graduated ladder from "allocate freely" to TigerStyle's "no allocation after
startup".

This chapter does not own error-set design, `try`/`catch` selection, or `unreachable`-versus-error —
those are `references/errors.md`. `Io.Reader`/`Io.Writer` buffer sizing is ZS-CONC-11 and
ZS-CONC-35; assertion density and bounded loops are `references/assertions.md`; `MultiArrayList`
layout choices are ZS-DATA-22; allocation-failure testing is ZS-TEST-11. It cites them.

Every example assumes a file opening with `const std = @import("std");` and
`const assert = std.debug.assert;` — assertions are called bare, per ZS-ASSERT-01.

## Contents

- **Choosing an allocator**
  - ZS-MEM-01 [M] Take `std.process.Init` in `main` and use the allocators it hands you
  - ZS-MEM-02 [M] A library never names a concrete allocator
  - ZS-MEM-03 [M] Pick the allocator from the taxonomy, not from habit
  - ZS-MEM-04 [M] If you construct a `SafeAllocator` yourself, consume the leak count from `deinit`
- **Passing and naming the allocator**
  - ZS-MEM-05 [M] Pass the allocator per call; do not store it in a field
  - ZS-MEM-06 [M] Name the allocator for its role — `gpa`, `arena`, `scratch` — and place it after the receiver
  - ZS-MEM-07 [M] Never hand out an `Allocator` whose backing state lives in a frame that returns
  - ZS-MEM-08 [M] One object, one allocator, for its whole lifetime
- **Ownership**
  - ZS-MEM-09 [M] Signal ownership transfer in the name and the doc comment
  - ZS-MEM-10 [M] Put `defer` / `errdefer` on the line immediately after the acquisition
  - ZS-MEM-11 [M] `errdefer` every fallible construction step, until ownership transfers
  - ZS-MEM-12 [M] `deinit` never fails, never allocates, and poisons the struct
  - ZS-MEM-13 [M] Use `toOwnedSlice` to hand a built buffer out of a builder
  - ZS-MEM-14 [M] Free exactly the slice you allocated
- **Invalidation**
  - ZS-MEM-15 [M] Pointers into container storage die on any capacity change
  - ZS-MEM-16 [M] If you need stable pointers, use `std.heap.MemoryPool(T)` or store indices
- **OOM policy**
  - ZS-MEM-17 [M] Libraries propagate `error.OutOfMemory`; only an application's top level may abort
- **Static allocation and the graduated ladder**
  - ZS-MEM-18 [M] Allocate all memory at startup where every bound is known then; otherwise name the rung
  - ZS-MEM-19 [S] Arena per request, per phase, per iteration
  - ZS-MEM-20 [S] Preallocate to the known bound, then use `AssumeCapacity` in the hot path
  - ZS-MEM-21 [S] Impose a hard ceiling with a fixed backing buffer
- **The Allocator interface and custom allocators**
  - ZS-MEM-22 [M] Implement all four vtable members to their exact contracts
  - ZS-MEM-23 [M] Test a custom allocator with std's own conformance helpers
  - ZS-MEM-24 [M] Alignment is `std.mem.Alignment`, never a raw integer
- **Raw memory**
  - ZS-MEM-25 [M] `@memcpy` for disjoint copies, `@memmove` for overlapping ones
  - ZS-MEM-26 [M] Zero padding before it leaves the process, and wipe secrets on the way out
- Decided by tools

---

## Choosing an allocator

### ZS-MEM-01 [M] Take `std.process.Init` in `main` and use the allocators it hands you

`main` may take `std.process.Init` as its first parameter. Use `init.gpa` for temporary/scoped heap
and `init.arena.allocator()` for process-lifetime data. Do not hand-roll GPA boilerplate in `main`.
The `init.gpa` you get is `SafeAllocator` in `debug` and `safe` builds, whether or not libc is
linked; in `fast` and `small` builds `c_allocator` when linking libc and `smp_allocator` when
multi-threaded without it; `wasm_allocator` on wasm. `init.arena` is backed by `page_allocator`.

**Why:** `std/start.zig` already runs the correct selection ladder for the target and optimize mode,
installs leak checking, creates the process arena, and tears all of it down after `main` returns.
Rolling your own reproduces that ladder badly and usually loses the leak report.

**Check:** a `pub fn main` declared with no parameter, or with `Init.Minimal`, in a program that
allocates; and any `SafeAllocator` (or the deprecated `DebugAllocator`), `ArenaAllocator`, or
`std.heap.*` constructed inside `main` itself rather than taken from `init`.

```zig
// rejected — zig: root source file struct 'heap' has no member named 'GeneralPurposeAllocator'
pub fn main() !void {
    var gpa_state = std.heap.GeneralPurposeAllocator(.{}){}; // no such allocator
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
    const gpa = init.gpa; // temporary allocations, leak-checked in debug and safe builds
    const arena = init.arena.allocator(); // process lifetime, threadsafe, freed on exit

    var line: std.ArrayList(u8) = .empty;
    defer line.deinit(gpa);
    try line.appendSlice(gpa, "hello");

    const config_name = try arena.dupe(u8, line.items);
    std.log.info("{s}", .{config_name});
}
```

`std.process.Init` exactly: `minimal: Minimal`, `arena: *std.heap.ArenaAllocator` ("Threadsafe"),
`gpa: Allocator` ("Threadsafe"), `io: Io`, `environ_map: *Environ.Map` ("Not threadsafe"),
`preopens: Preopens`. `Init.Minimal` (`environ`, `args`) is the lighter alternative first parameter;
`pub fn main() !void` still works but gives you nothing.

### ZS-MEM-02 [M] A library never names a concrete allocator

Library code takes `gpa: std.mem.Allocator` as a parameter. `std.heap.*` may not appear anywhere in
a reusable module — not `page_allocator`, not `c_allocator`, not `smp_allocator`, not a
`SafeAllocator` field. A library's C-ABI export layer is its root, the one place that picks an
allocator, because no Zig caller is there to pass one: an `export fn` whose result C releases with
`free()` allocates through `std.heap.c_allocator` (ZS-INTEROP-14).

**Why:** the allocator is the caller's memory policy. Picking `page_allocator` forces a syscall per
allocation on a caller who wanted an arena; picking `c_allocator` forces a libc link. The vtable
costs one indirect call and lets the caller pass an arena, a fixed buffer, or a failing allocator.

**Check:** the token `std.heap.` in any file that is not a `main`, a test, a benchmark harness, a
`build.zig`, or a C-ABI export layer — `page_allocator` and `c_allocator` are the two that actually
show up. Also a `pub fn` that allocates and takes no `Allocator` parameter.

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

| Allocator | Use for | Thread safe | Cost | Gotchas |
|---|---|---|---|---|
| `std.heap.SafeAllocator` | `debug` and `safe` builds; leak, double-free, and foreign-allocation detection | Yes, given a thread-safe backing allocator; there is no single-threaded variant | A checksummed footer on every allocation, a one-byte one included, plus room for two seven-frame stack traces in a `debug` build | Construct with `.init(backing, .{})`; `deinit()` returns the leak count, which must be consumed. Reuses an address only if its backing allocator does. Replaces the deprecated `DebugAllocator` |
| `std.heap.smp_allocator` | `fast`/`small` builds, multi-threaded, no libc | Yes (per-thread freelists) | Fast; per-thread slabs | Process-global singleton; `assert(!builtin.single_threaded)` so it is a compile error under `-fsingle-threaded` |
| `std.heap.c_allocator` | You already link libc, or you need platform `malloc` interop | Yes | libc malloc | `@compileError` unless `builtin.link_libc`, so it forces a libc link on every downstream caller |
| `std.heap.page_allocator` | Backing store for arenas / `SafeAllocator`; rare huge allocations | Yes | "makes a syscall directly for every allocation and free" | Never a general-purpose allocator |
| `std.heap.wasm_allocator` | wasm32/wasm64 | No | Small, fast | `WasmAllocator = if (builtin.single_threaded) BrkAllocator else @compileError("unimplemented")` |
| `std.heap.ArenaAllocator` | Request-scoped / phase-scoped bulk allocation | `alloc` is threadsafe if the child is; `deinit`, `reset`, `queryCapacity` documented "Not threadsafe." | Bump pointer | `deinit` takes the arena **by value**; `free` of a non-last allocation is a no-op |
| `std.heap.FixedBufferAllocator` | Bounded scratch work; a hard memory ceiling | `.allocator()` no; `.threadSafeAllocator()` yes (lock-free) — never mix the two handles | Zero syscalls | `free` reclaims only the last allocation, and `isLastAllocation` "has false negatives" |
| `std.heap.MemoryPool(T)` | Many same-typed nodes needing stable pointers | No | Arena + freelist | `.empty`, `create(gpa)`, `destroy(ptr)`, `deinit(gpa)` |
| `std.heap.BufferFirstAllocator` | Small allocations that usually fit in a buffer you supply | No: the buffer half is a `FixedBufferAllocator` | One caller-owned `[N]u8`, usually on the stack | `var bfa: BufferFirstAllocator = .init(&buffer, fallback)`, then `bfa.allocator()` |
| `std.testing.allocator` | Tests | Yes | `SafeAllocator` cost | Distinct `canary` so mixing it with a default `SafeAllocator` panics |
| `std.testing.failing_allocator` | Injecting OOM at a chosen allocation index | No | None | Prefer `std.testing.checkAllAllocationFailures`, which drives it for you |
| `std.mem.Allocator.failing` | Proving a code path never allocates | n/a | None | `resize`/`remap`/`free` are `unreachable` — it asserts you never free through it |

> [!NOTE]
> `std.heap.ThreadSafeAllocator`, `std.heap.GeneralPurposeAllocator`, and
> `std.heap.LoggingAllocator` do **not** exist in 0.17 — zero hits in std, and
> `std.heap.ThreadSafeAllocator` is a `has no member named` compile error. Use `SafeAllocator`,
> which has no single-threaded variant, or `smp_allocator` for thread safety. `SafeAllocator` has no
> logging option; only the deprecated `DebugAllocator(.{ .verbose_log = true })` still logs.

Defaults by program kind, matching std's own ladder in `std.start`:

| Program | Default |
|---|---|
| CLI / application | `init.gpa` + `init.arena` from `std.process.Init` |
| Server | process gpa from `Init`; **one `ArenaAllocator` per request/connection**, `reset(.retain_capacity)` between requests |
| Library | no default — take `gpa: Allocator` (ZS-MEM-02) |
| Test | `std.testing.allocator` |
| Arena backing | `std.heap.page_allocator` (what `start.zig` uses); the gpa on wasm |

**Why:** each row's cost is a documented property of the implementation, not a matter of taste, and
the penalty for choosing off-niche is order-of-magnitude: picking by habit usually either fails to
build or changes the program's syscall profile by a factor of thousands.

**Check:** `page_allocator` used as anything but backing for an arena or a `SafeAllocator`;
`SafeAllocator` (or the deprecated `DebugAllocator`) on a `fast`/`small` path;
`std.testing.allocator` outside a `test` block; and `std.heap.ThreadSafeAllocator`,
`std.heap.GeneralPurposeAllocator`, or `std.heap.LoggingAllocator`, none of which exist in 0.17.

### ZS-MEM-04 [M] If you construct a `SafeAllocator` yourself, consume the leak count from `deinit`

`SafeAllocator.deinit()` returns the number of leaks as a `usize`. Turn a non-zero count into a
failure — an error or a non-zero exit — and never `_ = sa.deinit();`. Not inside an `assert` either:
`deinit` is a side effect, and an `assert`'s argument must have none (ZS-ASSERT-02). It replaced
`DebugAllocator`, deprecated in 0.17, whose `deinit()` returned `std.heap.Check` (`.ok` / `.leak`)
under the same rule.

**Why:** the leak report is written by `deinit`, but the *decision* is the return value. Discarding
it means a leaking build exits 0 and CI stays green. Construct it with `.init(backing, .{})`: it has
no default value, and it is thread-safe only if `backing` is.

**Check:** `rg -n '_ = .*\.deinit\(\)'` — a discarded leak count is the whole defect — and a
`deinit()` call inside `assert(`.

Applies **only when you cannot take `init.gpa`** (see ZS-MEM-01) — a benchmark harness, a custom
runtime, a `build.zig` step. `main` takes `std.process.Init` and never hand-rolls this, and a test
takes `std.testing.allocator` (ZS-TEST-03):

```zig
// verified — a benchmark harness, not `main` and not a `test`
const std = @import("std");

/// Runs `work` on its own leak-checked heap; a leak fails the run.
pub fn runChecked(work: *const fn (std.mem.Allocator) std.mem.Allocator.Error!void) !void {
    var safe_allocator: std.heap.SafeAllocator = .init(std.heap.page_allocator, .{});
    const result = work(safe_allocator.allocator());
    const leak_count = safe_allocator.deinit(); // the decision is this value
    try result;
    if (leak_count != 0) return error.Leaked;
}
```

`SafeAllocator` prints the three-trace double-free report (allocation, first free, second free) with
no opt-in. Each trace holds seven frames in a `debug` build; a `safe` build records none unless you
set `.stack_trace_frames`. `DebugAllocator` needed `.never_unmap` and `.retain_metadata` plus
`deinitWithoutLeakChecks()` for the same report, and without them a double free of a small
allocation faulted inside `Allocator.free`'s `@memset(bytes, undefined)` first.

---

## Passing and naming the allocator

### ZS-MEM-05 [M] Pass the allocator per call; do not store it in a field

Allocating methods take `gpa: Allocator` as the first parameter after the receiver, including
`deinit` (ZS-MEM-06 gives the order). Reserve allocator *fields* for types that are themselves
allocator wrappers. This is the direction std moved: every allocator-in-a-field container in std is
marked `Deprecated` (`array_list.Managed`, `array_list.AlignedManaged`) or, like
`heap.memory_pool.Managed`, already removed.

**Why:** dropping the field saves 16 bytes per instance, which matters at a million of them; it puts
every allocation point at the call site instead of behind `self.allocator`; and a struct without one
can be memcpy'd, embedded, or moved without carrying a pointer to dead allocator state.

**Check:** a field of type `std.mem.Allocator` on any struct that is not itself an allocator
wrapper, and a `deinit`/`append`/`ensureTotalCapacity` call on an unmanaged container that passes no
allocator. Grep for `self.allocator` / `x.gpa` at an allocation site: that is the field this rule
removes. Do not flag every receiver-only `deinit`: a type that owns its allocator or holds none
declares one, as 47 `pub fn deinit` in 0.17 std do — `Io.Threaded.deinit(t: *Threaded) void`,
`ArenaAllocator.deinit` taking the arena by value, `SafeAllocator.deinit` returning its leak count.

```zig
// rejected — zig: struct 'array_list.Aligned(u8,null)' has no member named 'init'
test "the managed shape" {
    const gpa = std.testing.allocator;
    var list = std.ArrayList(u8).init(gpa); // ArrayList is unmanaged: no `init`
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

### ZS-MEM-06 [M] Name the allocator for its role — `gpa`, `arena`, `scratch` — and place it after the receiver

`gpa` means the caller must free what comes back; `arena` means the result is never freed
individually and dies with the arena. A field holding an allocator is named for its role the same
way. Counted over 0.17 std: `gpa: Allocator` **312**, `allocator: Allocator` **202**,
`arena: Allocator` **41**. `gpa` is the plurality, every rewritten container (`array_list.zig`,
`array_hash_map.zig`, `multi_array_list.zig`) uses it exclusively, and the `allocator:` sites sit in
older files. TigerStyle agrees: "`allocator: Allocator` is a good, if boring name, but
`gpa: Allocator` and `arena: Allocator` are excellent."

Placement follows std: receiver first, then the allocator, then the data — `deinit(self, gpa)`,
`append(self, gpa, item)`. A function with no receiver takes the allocator first.

**Why:** `gpa` vs `arena` tells the reader, at the call site, whether the returned memory must be
individually freed. `allocator: Allocator` carries zero information beyond the type, which is
already in the signature.

**Check:** `rg -n '[(,] *allocator: '` over the diff — anchored, so `debug_allocator` is not
reported — and any field or local of type `std.mem.Allocator` named `allocator`, `alloc`, `ally`, or
a single letter. The three legal names are `gpa`, `arena`, and `scratch`; a fourth needs a comment
saying what lifetime it denotes. Then an `Allocator` parameter that comes after a data parameter.

```zig
// fragment — GOOD: the names say who frees.
pub fn render(gpa: Allocator, arena: Allocator, doc: *const Doc) Allocator.Error![]u8 {
    const scratch = try arena.alloc(u8, doc.size_max); // dies with the arena
    _ = scratch;
    return gpa.dupe(u8, doc.title);                    // caller must free
}
```

### ZS-MEM-07 [M] Never hand out an `Allocator` whose backing state lives in a frame that returns

`ArenaAllocator.allocator()`, `FixedBufferAllocator.allocator()`, and `SafeAllocator.allocator()`
all embed `.ptr = self`. If `self` is a local, the `Allocator` value becomes a dangling pointer the
moment the function returns.

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

### ZS-MEM-08 [M] One object, one allocator, for its whole lifetime

The allocator passed to `deinit`, `append`, `ensureTotalCapacity`, and `free` must be the same one
that performed the original allocation. The `std.ArrayList` doc comment states it: "The same
allocator must be used throughout its entire lifetime."

**Why:** the vtable dispatch will happily route a free into an allocator that never owned the block,
corrupting its metadata. With the allocator a parameter rather than a field (ZS-MEM-05), nothing
enforces this for you: it is a discipline, and the cost of the unmanaged design.

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

### ZS-MEM-09 [M] Signal ownership transfer in the name and the doc comment

A function that returns memory the caller must free says so: `/// Caller owns the returned memory.`
Follow std's vocabulary — `dupe`, `dupeSentinel`, `alloc*`, `create`, `clone`, `toOwnedSlice`, and
an `Alloc` suffix (`currentPathAlloc`) transfer ownership; `items`, `slice()`, `buffered()`,
`written()`, `lastPtr()`, `unusedCapacitySlice()` return a **borrow** valid only until the next
mutation.

**Why:** Zig has no ownership in the type system: `[]u8` from `dupe` and `[]u8` from `list.items`
are the same type and opposite contracts. The name and the one-line doc comment are the entire
enforcement mechanism, which is why std writes it on every such function.

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

### ZS-MEM-10 [M] Put `defer` / `errdefer` on the line immediately after the acquisition

Two requirements, both binding. **Adjacency:** no statement may sit between an acquisition and its
release, and the release names the exact thing acquired (`gpa.free(buffer)`, not
`gpa.free(self.buffer)`). **Grouping:** the acquisition/release pair is separated from surrounding
code by a blank line above and below, so each pair reads as a two-line visual unit.

**Why:** the pairing is verified by eye. Any distance between the lines is where a future `return`,
`try`, or early `break` slips in unnoticed, and the blank lines make the *absence* of a release
visible: a one-line group is an unpaired acquisition, caught without reading the identifiers.

**Check:** in a diff, every `alloc`/`create`/`open`/`lock`/`init` line must be followed on the very
next line by `defer` or `errdefer`, and that two-line pair must be blank-line separated. Also flag a
`defer` whose argument is not textually the value produced on the line above.

```zig
// fragment — BAD: three fallible statements between alloc and defer, and no grouping.
const buffer = try gpa.alloc(u8, n);
try validate(buffer);
try prefill(buffer);
defer gpa.free(buffer);
```

```zig
// fragment — GOOD: adjacent, and blank-line grouped.
var file = try dir.openFile(io, "cfg.txt", .{});
defer file.close(io);

const buffer = try gpa.alloc(u8, n);
defer gpa.free(buffer);

try validate(buffer);
try prefill(buffer);
```

The same shape applies to every acquisition, not just allocation: `Io.File`/`Io.Dir` handles
(`defer file.close(io)`), `Io.Mutex` (`defer m.unlock(io)`), `Io.Group` (`defer g.cancel(io)`), and
`Io.Future` (`defer _ = f.cancel(io);`, which is idempotent, so a later `await` still returns the
result). Where the release itself is fallible or cancelable, use the `*Uncancelable` variant — a
`defer` body cannot propagate an error (see ZS-CONC-26). What happens once the pair is in place —
the order of teardown, the point ownership transfers, the scope inside a loop — is ZS-ERR-11,
ZS-ERR-12 and ZS-ERR-13.

### ZS-MEM-11 [M] `errdefer` every fallible construction step, until ownership transfers

Multi-step `init` puts an `errdefer` after each allocation, up to the point where ownership moves to
a value the caller will `deinit`. Where that point is, and what an `errdefer` covers inside a loop,
are ZS-ERR-12 and ZS-ERR-13.

**Why:** a `try` on step 3 unwinds steps 1 and 2 only if they registered `errdefer`s, and a missing
one is a leak that only appears under memory pressure.

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

        var lines: std.ArrayList([]u8) = try .initCapacity(gpa, 4);
        errdefer lines.deinit(gpa);

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

### ZS-MEM-12 [M] `deinit` never fails, never allocates, and poisons the struct

Signature `pub fn deinit(x: *T, gpa: Allocator) void`. It returns `void`, performs no fallible work,
and ends with `x.* = undefined;`, as std's `MemoryPool.deinit` and `ArrayList.deinit` do. Zig has no
idempotent-deinit convention: calling `deinit` twice is a double free.

**Why:** `deinit` runs from `defer`, where an error has nowhere to go, and from error unwinding,
where allocating may fail for the very reason you are unwinding. `x.* = undefined` turns a
use-after-deinit into a detectable "branch on undefined value" in `debug` and `safe` builds.

**Check:** a `deinit` whose return type is not `void`; a `try`, a `catch`, or an `alloc`/`dupe`/
`create` inside a `deinit` body; and a `deinit` whose last statement is not `x.* = undefined;`.

Exception, and it is a real trap: `ArenaAllocator.deinit` takes the arena **by value**
(`pub fn deinit(arena: ArenaAllocator) void`), not by pointer.

### ZS-MEM-13 [M] Use `toOwnedSlice` to hand a built buffer out of a builder

When a container's job was to build one slice, transfer with `toOwnedSlice(gpa)` and let the
container fall back to `.empty` rather than copying and freeing by hand. On the static-allocation
path use `toOwnedSliceAssert(self)` or `toOwnedSliceSentinelAssert(self, sentinel)`, which take no
allocator and assert the capacity already fits.

**Why:** `toOwnedSlice` shrinks the allocation to the exact length and hands you the pointer,
leaving the list valid and empty so an outstanding `defer list.deinit(gpa)` stays correct. Doing it
by hand (`gpa.dupe(u8, list.items)`) copies the whole buffer.

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

### ZS-MEM-14 [M] Free exactly the slice you allocated

`free`, `resize`, and `remap` require `memory.len` to equal the length requested from the most
recent successful `alloc`/`resize`/`remap`, and the alignment to equal the original. Never free a
sub-slice, a re-sliced view, or a slice whose length you shortened by hand. Track the original
slice, and if you must narrow a view, keep both. Freeing a **zero-length** slice is always legal and
always a no-op (`if (bytes.len == 0) return;`), so `.empty`-style teardown paths need no guard.

**Why:** it is a documented precondition on every vtable member, and allocators use the length to
find the size class: passing `buffer[0..n]` to `free` after allocating `buffer.len > n` returns the
block to the wrong bucket.

**Check:** a `free`, `resize`, or `remap` whose first argument is a slice *expression* rather than
the identifier bound on the allocation line — `gpa.free(buffer[0..n])` and `gpa.free(x[1..])` are
both the finding. Also any `buffer = buffer[0..n]` reassignment above a later `gpa.free(buffer)`.

```zig
// fragment — BAD: the free length is the slice, not the allocation
var buffer = try gpa.alloc(u8, 4096);
const used = buffer[0..n];
defer gpa.free(used);       // wrong length
```

```zig
// fragment — GOOD
var buffer = try gpa.alloc(u8, 4096);
defer gpa.free(buffer);
const used = buffer[0..n];
```

If you genuinely want to shrink, use `gpa.realloc(buffer, n)` (only fails on OOM, does the copy) or
`if (gpa.resize(buffer, n)) buffer = buffer[0..n];` — `resize` is "guaranteed to not move the
pointer", and `remap` may move it, so reassign from its return value.

A related shape the type system does not catch: slicing a `[*]T` with comptime-known bounds produces
a `*[N]T`, not a slice, and `Allocator.free` accepts a pointer to an array as well as a slice,
freeing `N` elements — std's own `Io.Dispatch.deinit` frees
`ev.main_loop_stack[0..main_loop_stack_size]` that way. It compiles, so this rule covers it
unchanged: `N` must be the length you allocated. A bare many-item `[*]T`, which carries no length,
is rejected.

---

## Invalidation

### ZS-MEM-15 [M] Pointers into container storage die on any capacity change

Every allocating container operation may reallocate: `append`, `appendSlice`, `appendNTimes`,
`insert`, `addOne`, `addManyAsSlice`, `ensureTotalCapacity`, `ensureUnusedCapacity`, `resize`,
`getOrPut`, and `put`. Across any of them, never hold `&list.items[i]`, `list.items` itself,
`list.items.ptr`, a `MultiArrayList.Slice`, `map.getPtr(k)`, `map.getEntry(k)`, or a
`GetOrPutResult.key_ptr`/`value_ptr`. Store an index and re-derive.

The full set of container types this covers: `std.ArrayList`, `std.MultiArrayList`, `std.Deque`,
`std.array_hash_map.Auto`/`String`/`Custom`, and `std.HashMap`/`std.AutoHashMap`. Hash maps add a
second invalidation source that `ArrayList` does not have: a `remove`/`swapRemove` reorders or
tombstones entries even when capacity is unchanged, so an entry pointer is dead after *any* removal,
not only after growth. `std.heap.MemoryPool(T)` is the exception — it never moves an existing item
(ZS-MEM-16).

**Why:** growth is a `remap` that falls back to alloc-copy-free, and `Allocator.free` `@memset`s the
old block to `undefined`: a retained element pointer reads poison, or in a `fast` build whatever
reused the page. It is the most common memory bug in Zig code that otherwise has no leaks.

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

ZS-DATA-21 is the structural fix: a handle newtype instead of a pointer.

### ZS-MEM-16 [M] If you need stable pointers, use `std.heap.MemoryPool(T)` or store indices

For "many nodes, pointers must not move", use `MemoryPool(T)`, optionally with the intrusive
`std.SinglyLinkedList` / `std.DoublyLinkedList` (a `Node` holds links only; recover the payload with
`@fieldParentPtr`). ZS-DATA-23 covers the containers std no longer has.

**Why:** `MemoryPool` allocates in arena chunks and never moves an existing item; freed items go on
a freelist and are reused in place. Indices, by contrast, cost a bounds check and survive every
reallocation, and `u32` indices halve the footprint of a graph versus 64-bit pointers.

**Check:** a `*T` derived from container storage that is stored in a field, pushed into a second
container, or returned; and a hand-rolled create/destroy freelist over `ArrayList` element
addresses.

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

### ZS-MEM-17 [M] Libraries propagate `error.OutOfMemory`; only an application's top level may abort

Return `Allocator.Error!T` (or a set containing it). Never `catch @panic`, never
`catch unreachable`, never `catch return null` in reusable code. An application `main` may
`return err`, or a CLI may `std.process.fatal("out of memory", .{})` at the outermost layer.

**Why:** `Allocator.Error` has one member, so `try` costs a branch and one error name. Aborting
takes away the caller's choice to shed load, retry smaller, or fail one request, and breaks the
library under a `FixedBufferAllocator`, where OOM is the *expected* signal that the buffer is full.

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

To bound an application's heap rather than abort on it, give the bounded part a fixed backing buffer
(ZS-MEM-21): allocations past it return `error.OutOfMemory` through the normal path. `SafeAllocator`
has no memory-limit option, and the allocator that had one,
`DebugAllocator(.{ .enable_memory_limit = true })` with `da.requested_memory_limit`, is deprecated
in 0.17.

## Static allocation and the graduated ladder

### ZS-MEM-18 [M] Allocate all memory at startup where every bound is known then; otherwise name the rung

TigerStyle, verbatim: "All memory must be statically allocated at startup. **No memory may be
dynamically allocated (or freed and reallocated) after initialization.**" That is the rule for a
program of which all of these hold: (1) every resource bound is derivable from configuration at
startup — max connections, max message bytes, max in-flight operations; (2) the process is
long-lived and a restart is expensive or externally visible (a replica, a controller, an embedded
device, a hard-real-time loop); (3) rejecting work is a better failure than growing memory — an OOM
kill would cost correctness, quorum, or a machine; (4) you own the dependency tree and call no
library that allocates on your behalf; (5) it is an application or a service, not a library —
forcing this policy on your callers is not your decision to make. Input whose size is unbounded and
user-supplied (compilers, CLIs over arbitrary files, general-purpose servers with variable
payloads), a std subsystem that allocates at use time, or a library is outside it.

Any other program picks exactly one rung of the graduated ladder, in descending strength —
ZS-MEM-21, a hard ceiling from a fixed backing buffer (`ArrayList.initBuffer` or
`FixedBufferAllocator`); ZS-MEM-19, an arena per request or phase, reset at the boundary; ZS-MEM-20,
exactly the bound reserved up front and `*AssumeCapacity` in the hot path — names it in the module's
doc comment, and treats an allocation inside a hot loop or on a request path as a design smell
requiring a justifying comment. Either way, derive the bounds, write them down as `_max` constants,
and `comptime`-assert them.

**Why:** peak RSS is known before the first request, so a spike cannot OOM-kill the process. The
steady state loses `error.OutOfMemory`, use-after-free, fragmentation, and growth-copy latency, and
you must derive every bound (in-flight operations, message size, queue depth), so you can assert it.

**What it costs:**

- You must size everything up front, and getting it wrong converts a soft failure (slower, more RSS)
  into a hard one (reject the work, or `fatal` with an operator-actionable message).
- Over-provisioning is paid in resident memory at all times, not just at peak.
- Large parts of std become unavailable: anything that allocates internally at use time — `std.json`
  parsing, `std.zig.Ast`, hash maps that grow, `Io.Writer.Allocating`. TigerBeetle's own answer was
  to write `src/stdx` and reimplement bounded arrays, bit sets, and PRNGs.
- std has no bounded-array type, so the bounded containers you need are `ArrayList` over a fixed
  buffer (ZS-MEM-21), your own fixed pools, or third-party code.

**Check:** in a program of which the five hold, an `alloc`/`create`/`dupe`/`append`/
`ensureTotalCapacity` reachable from a request path rather than from `init` — and, before that, the
absence of the `StaticAllocator` gate itself, which is what converts this from a review question
into an assertion failure. In any other: an allocation inside a loop or on a per-request path with
no comment naming which rung (ZS-MEM-19, ZS-MEM-20 or ZS-MEM-21) the module chose.

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

    fn resize(ctx: *anyopaque, memory: []u8, a: Alignment, new_len: usize, ra: usize) bool {
        const sa: *StaticAllocator = @ptrCast(@alignCast(ctx));
        assert(sa.state == .init);
        return sa.parent.rawResize(memory, a, new_len, ra);
    }

    fn remap(ctx: *anyopaque, memory: []u8, a: Alignment, new_len: usize, ra: usize) ?[*]u8 {
        const sa: *StaticAllocator = @ptrCast(@alignCast(ctx));
        assert(sa.state == .init);
        return sa.parent.rawRemap(memory, a, new_len, ra);
    }

    fn free(ctx: *anyopaque, memory: []u8, a: Alignment, ra: usize) void {
        const sa: *StaticAllocator = @ptrCast(@alignCast(ctx));
        // `free` stays legal during init so errdefer cleanup can run.
        assert(sa.state == .init or sa.state == .deinit);
        sa.parent.rawFree(memory, a, ra);
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
> allocate at use time, and std has no bounded array, the container that would make "no allocation
> after init" ergonomic. TigerStyle's position is that this is a design smell for systems that must
> not fail. Both are right about their own domain, which is why the five conditions above decide
> between full static allocation with a gate and one rung of the ladder, and why knowing your
> bounds, writing them down as `_max` constants and `comptime`-asserting them holds in either.

TigerStyle's bounded containers `assert(!full())` on push, treating overflow as a programmer error.
std offers both the asserting and the error-returning form, and ZS-DATA-23 says which a call site
picks.

### ZS-MEM-19 [S] Arena per request, per phase, per iteration

Give each unit of work an `ArenaAllocator`; free the whole thing at the end of the unit instead of
freeing individual objects. Reset with `.retain_capacity` between units, or
`.{ .retain_with_limit = N }` on a long-running server. `.retain_capacity` preheats the arena, so
after the largest request the steady state performs no backing allocations at all;
`.retain_with_limit` caps the RSS a single pathological request can pin forever.

**Why:** a request's allocation graph is a tree that dies all at once. An arena turns N frees into
one, removes every intermediate `errdefer` on that path, and makes leaks structurally impossible
within the unit.

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
`deinit`/`reset`/`queryCapacity` concurrently with work — `alloc` is threadsafe in 0.17 but those
three are documented "Not threadsafe.", so quiesce every worker first.

### ZS-MEM-20 [S] Preallocate to the known bound, then use `AssumeCapacity` in the hot path

When you know the count, reserve exactly that count once outside the loop — `.initCapacity(gpa, n)`
for a new list, `ensureTotalCapacityPrecise` for an existing one — and call `appendAssumeCapacity` /
`appendSliceAssumeCapacity` / `addManyAsSliceAssumeCapacity` inside it. `ensureTotalCapacity` passes
the bound through `growCapacity(minimum) = minimum +| (minimum / 2 + init_capacity)`, where
`init_capacity` is `cache_line / @sizeOf(T)`, so it reserves about half again: 1568 for 1024 `u32`s
on a 128-byte cache line. An unprepared 1024-`u32` build grows seven times there, copying what it
has written whenever a block cannot be extended in place.

**Why:** it moves the only fallible operation out of the loop, so the loop body has no error path
and no branch on growth, and it removes the 1.5x-growth memcpy entirely. It is also the exact shape
a later migration to full static allocation needs.

**Check:** a `try list.append(gpa, …)` or `try list.appendSlice(gpa, …)` inside a loop whose trip
count is already known above the loop — it is in the `for` range, or in a `.len` read, or in a named
`_max`. That is one exact reservation plus `appendAssumeCapacity` inside. On the static-allocation
path, an `ensureTotalCapacity` is the finding too: it reserves more than the bound.

```zig
// verified
const std = @import("std");
test "reserve the bound exactly, then AssumeCapacity in the hot path" {
    const gpa = std.testing.allocator;
    var ids: std.ArrayList(u32) = try .initCapacity(gpa, 1024);
    defer ids.deinit(gpa);

    for (0..1024) |i| ids.appendAssumeCapacity(@intCast(i));
    try std.testing.expectEqual(1024, ids.items.len);
    try std.testing.expectEqual(1024, ids.capacity);
}
```

### ZS-MEM-21 [S] Impose a hard ceiling with a fixed backing buffer

For work with a natural bound, allocate from a `[N]u8` — either `ArrayList.initBuffer`, std's
fixed-capacity list (ZS-DATA-23), or `std.heap.FixedBufferAllocator` when a subsystem demands an
`Allocator`. `initBuffer` gives a list with `capacity = buffer.len` and no allocator at all; only
the `*AssumeCapacity` and `*Bounded` methods are legal on it, and the `*Bounded` ones return
`error{OutOfMemory}` without taking a `gpa`.

**Why:** the bound becomes a compile-time constant that the reader can see and the reviewer can
audit, and exhaustion surfaces as `error.OutOfMemory` at a known point instead of as unbounded RSS
growth.

**Check:** a list created with `.initBuffer` and later passed to any `gpa`-taking method — that
allocator never owned the backing array (ZS-MEM-08), so growth corrupts it. Conversely, a fixed
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

    const buffer = try scratch_gpa.alloc(u8, 128);
    try std.testing.expectEqual(128, buffer.len);
    try std.testing.expectError(error.OutOfMemory, scratch_gpa.alloc(u8, 1 << 20));
}
```

Two `FixedBufferAllocator` traps: `free` reclaims only the most recent allocation (and
`isLastAllocation` "has false negatives when the last allocation had an adjusted_index"), so treat
it as reset-only; and `.allocator()` and `.threadSafeAllocator()` must never be used against the
same instance concurrently.

---

## The Allocator interface and custom allocators

### ZS-MEM-22 [M] Implement all four vtable members to their exact contracts

The 0.17 `Allocator.VTable` is `alloc`, `resize`, `remap`, `free`. `remap` is newer than most Zig
material — it is not optional and it is not `resize`. The vtable is a struct literal, so a missing
member is a compile error; a member you cannot implement takes the provided stand-in
(`Allocator.noAlloc` / `noResize` / `noRemap` / `noFree`) rather than an invented behavior.

**Why:** `Allocator.resize` is documented "guaranteed to not move the pointer", which is what makes
interior pointers safe across a successful `resize` and never across a `remap`. A `resize` that
moves leaves every such caller holding a dangling interior pointer far from your code.

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

    fn isLast(b: *Bump, memory: []u8) bool {
        return memory.ptr + memory.len == b.buffer.ptr + b.end;
    }

    fn alloc(ctx: *anyopaque, len: usize, alignment: Alignment, _: usize) ?[*]u8 {
        const b: *Bump = @ptrCast(@alignCast(ctx));
        const base = @intFromPtr(b.buffer.ptr);
        const start = alignment.forward(base + b.end) - base;
        if (start + len > b.buffer.len) return null;
        b.end = start + len;
        return b.buffer.ptr + start;
    }

    fn resize(ctx: *anyopaque, memory: []u8, _: Alignment, new_len: usize, _: usize) bool {
        const b: *Bump = @ptrCast(@alignCast(ctx));
        if (!b.isLast(memory)) return new_len <= memory.len;
        const start = b.end - memory.len;
        if (start + new_len > b.buffer.len) return false;
        b.end = start + new_len;
        return true;
    }

    fn remap(ctx: *anyopaque, memory: []u8, a: Alignment, new_len: usize, ra: usize) ?[*]u8 {
        return if (resize(ctx, memory, a, new_len, ra)) memory.ptr else null;
    }

    fn free(ctx: *anyopaque, memory: []u8, _: Alignment, _: usize) void {
        const b: *Bump = @ptrCast(@alignCast(ctx));
        if (b.isLast(memory)) b.end -= memory.len;
    }
};
```

Hand the `Allocator` out as ZS-COMPTIME-16 hands out any vtable interface: from a method taking
`*Self`, with `.ptr = self` (ZS-MEM-07). A stateless allocator sets `.ptr = undefined` and exposes
`pub const vtable: Allocator.VTable`, as `PageAllocator` and `SmpAllocator` do.

### ZS-MEM-23 [M] Test a custom allocator with std's own conformance helpers

Run `std.heap.testAllocator`, `testAllocatorAligned`, `testAllocatorLargeAlignment`, and
`testAllocatorAlignedShrink` against it, and wrap it in `std.mem.validationWrap` while developing.
`validationWrap` "asserts that allocation sizes are greater than zero and returned pointers have
correct alignment".

**Why:** these are the exact tests std runs against its own allocators, aimed at the
resize/remap/free preconditions you are most likely to get subtly wrong; `validationWrap` checks
both sides of the contract, so it catches a *caller* violating the vtable as well as your allocator.

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

### ZS-MEM-24 [M] Alignment is `std.mem.Alignment`, never a raw integer

`alignedAlloc` takes `comptime alignment: ?Alignment`, where `null` means natural alignment. Build
values with `.of(T)`, `.fromByteUnits(n)`, or the named variants `.@"1"` … `.@"64"`; only those are
named, so larger values must go through `.fromByteUnits`.

**Why:** `Alignment` is `enum(math.Log2Int(usize))`, the log2 of the byte count, so passing `4096`
where one is expected is a compile error rather than a 4096-fold misinterpretation, and its own
operations replace hand-rolled masking.

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
keep the `Alignment` and use its own operations — `forward` (round up), `backward` (round down),
`check`, `order`, `max`, `min` — rather than reconstructing `(x + a - 1) & ~(a - 1)` by hand.
Writing a custom allocator means implementing the vtable against `Alignment` directly (ZS-MEM-22),
never an integer.

**Check:** any `align` or alignment-named parameter, field, or `const` typed as an integer; any
`@alignOf(T)` or `1 << n` passed where an `Alignment` belongs; any hand-rolled `& ~(align - 1)`
masking.

---

## Raw memory

### ZS-MEM-25 [M] `@memcpy` for disjoint copies, `@memmove` for overlapping ones

`@memcpy(dest, source)` requires the regions not to overlap and the lengths to match. When source
and destination may overlap — a ring buffer, an in-place shift — use `@memmove`.
`std.mem.copyForwards` and `std.mem.copyBackwards` are deprecated ("This function is deprecated; use
@memmove instead"). Use `@memset` rather than a zeroing loop, so the optimizer can vectorize the
fill.

**Why:** `@memcpy` on overlapping regions is illegal behavior, not merely wrong output: the
optimizer may assume non-aliasing and vectorize. `copyForwards`/`copyBackwards` made *you* choose
the direction from pointer order, the comparison `@memmove` performs correctly for you.

**Check:** a `@memcpy` whose two arguments are slices of the same base array or the same pointer —
`@memcpy(ring[1..8], ring[0..7])` is the shape. Also `std.mem.copyForwards`/`copyBackwards` anywhere
(both deprecated), and a byte-at-a-time loop that only writes a constant.

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

### ZS-MEM-26 [M] Zero padding before it leaves the process, and wipe secrets on the way out

Any buffer written to disk, sent on the wire, or handed to another process must have every byte
defined — including struct padding and the unused tail of a fixed-size frame. Wipe key material with
`std.crypto.secureZero(T, slice)`, not `@memset`: `@memset(&key, 0)` on a value that is dead
afterwards is dead-store-eliminated by the optimizer, while `secureZero` takes `[]volatile T`, which
"Prevents the store from being optimized out".

Initialize such a buffer with `= @splat(0)` rather than `= undefined`, and give a serialized type
`extern` or `packed` layout with named, `0`-defaulted reserved fields, so padding is a field.

**Why:** this is the Heartbleed class of bug, a buffer *underflow*: unused bytes and padding never
zeroed carry uninitialized heap contents (previous requests, keys) out with the message. It also
breaks the byte-for-byte determinism that checksums, replication, and record-and-replay depend on.

**Check:** an array declared `= undefined` that reaches `writeAll`, a socket write, or a
`MemoryMap`; a plain (non-`extern`, non-`packed`) struct passed to `std.mem.asBytes` for
serialization; a reserved field with no `= 0` default; and `@memset(&key, 0)` on key material, where
`std.crypto.secureZero` is the only form the optimizer is forbidden to delete. Writing a record with
`w.writeStruct(value, endian)` states the byte order, and rejects a plain struct at compile time
(`error: ill-defined memory layout`).

```zig
// fragment — BAD: two bytes of implicit padding after `tag` leave with the frame.
const Header = extern struct { tag: u16, len: u32 };
var frame: [8]u8 = undefined;
const h: Header = .{ .tag = 3, .len = 17 };
@memcpy(&frame, std.mem.asBytes(&h));
try w.writeAll(&frame); // w: *std.Io.Writer — ships 2 bytes of stack
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
    var w: std.Io.Writer = .fixed(&frame);
    try w.writeStruct(Header{ .tag = 3, .len = 17 }, .little);
    try std.testing.expectEqualSlices(u8, &.{ 3, 0, 0, 0, 17, 0, 0, 0 }, w.buffered());
}

test "wipe secrets before the frame returns" {
    var key: [32]u8 = @splat(0xAB);
    defer std.crypto.secureZero(u8, &key);
    try std.testing.expectEqual(0xAB, key[0]);
}
```

Choosing the layout and asserting it are ZS-DATA-19 and ZS-DATA-20 and ZS-ASSERT-19.

## Decided by tools

The compiler rejects each of these on its own; no setting turns one off.

| Tool | Lint | Level | Forbids |
|---|---|---|---|
| zig | `returning address of expired local variable …` | error | returning a pointer to a local, which dies with the frame |
