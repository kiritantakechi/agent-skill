# Performance and the discipline of locality

Scope: performance as a *design-phase* decision — back-of-the-envelope sketches across the four
resources, ranking work by the slowest resource after compensating for frequency, the control-plane
and data-plane split, batching, and giving the CPU predictable work. Then the locality cluster:
smallest scope, no aliases, place-of-check next to place-of-use, centralized state manipulation, and
function shape. Then the 0.17-specific mechanics — build modes, the disabled loop vectorizer,
`@Vector`, `@branchHint`, `@prefetch`, cache lines, `inline` — and finally **how to measure**, since
rules throughout this standard say "unless you have measured" and this is the chapter that says how.

This chapter does not own data layout: struct-of-arrays and `MultiArrayList` are
`references/data.md` ZS-DATA-25, handles-versus-pointers is ZS-DATA-24, and passing large
aggregates as `*const T` is ZS-DATA-18. It does not own I/O batching
(`references/concurrency.md` ZS-CONC-35), assertion cost budgeting
(`references/assertions.md` ZS-ASSERT-20), the optimize-mode table
(`references/build.md` ZS-BUILD-27), or the `@branchHint` reference
(`references/errors.md` ZS-ERR-31). It cites them.

**Read ZS-PERF-24 first if you are tempted to apply this chapter to code that is not hot.** Roughly
half of these rules are about correctness and readability and apply everywhere; the other half
require a measurement before you are allowed to invoke them.

## Contents

- **Part 1 — Performance is decided in the design phase**
  - ZS-PERF-01 [M] Decide the performance-relevant shape of a design before implementing it
  - ZS-PERF-02 [M!] Sketch the cost across the four resources, and write the sketch down
  - ZS-PERF-03 [M] Rank the resources by cost *times frequency*, and optimize the top of that list
  - ZS-PERF-04 [S] Say whether a function is control plane or data plane, and budget it
  - ZS-PERF-05 [M!] Amortize every expensive acquisition over a bounded batch
  - ZS-PERF-06 [S] Give the CPU one long lane; do not make it change lanes per item
  - ZS-PERF-07 [M] Be explicit; never depend on an optimization the compiler is not obliged to make
  - ZS-PERF-08 [S] Hand a measured hot loop its data as slices and integers, not as a receiver
- **Part 2 — The discipline of locality**
  - ZS-PERF-09 [M] Declare every variable at the smallest scope that can hold it
  - ZS-PERF-10 [M] Never duplicate a variable, and never hold an alias to one
  - ZS-PERF-11 [M] Calculate and check a value next to where it is used — avoid POCPOU
  - ZS-PERF-12 [S] Centralize state manipulation: helpers compute the change, the parent applies it
  - ZS-PERF-13 [S] Shape functions like an inverted hourglass: narrow in, narrow out, wide inside
- **Part 3 — Zig 0.17 mechanics**
  - ZS-PERF-14 [M] Measure in the mode you ship, and never quote a `debug` number
  - ZS-PERF-15 [M] Do not rely on auto-vectorization in 0.17 — the loop vectorizer is disabled
  - ZS-PERF-16 [S] Write SIMD explicitly with `@Vector`, sized by `std.simd.suggestVectorLength`
  - ZS-PERF-17 [S] Mark cold and likely paths with `@branchHint`, as the branch's first statement
  - ZS-PERF-18 [M] Spell out every `@prefetch` option; never rely on the defaults
  - ZS-PERF-19 [S] Align independently written concurrent fields to `std.atomic.cache_line`
  - ZS-PERF-20 [S] Use `inline fn` only for the three reasons the langref gives
- **Part 4 — How to measure**
  - ZS-PERF-21 [M] Time with `Io.Timestamp` and `Io.Duration` — `std.time.Timer` no longer exists
  - ZS-PERF-22 [M] Warm up, repeat, and defend the measured expression from dead-code elimination
  - ZS-PERF-23 [M] Add a `bench` step pinned to `.fast` and not installed by default
- **Part 5 — The counterweight**
  - ZS-PERF-24 [M] Apply the always-on rules everywhere; require a number before invoking the rest

---

## Part 1 — Performance is decided in the design phase

### ZS-PERF-01 [M] Decide the performance-relevant shape of a design before implementing it
Before writing a subsystem, state — in the design note, the module doc comment, or the PR
description — what its dominant cost is and what shape of work it does: how many round trips, how
many passes over the data, how much it allocates, how much it copies. Choosing the shape is the
1000x decision; the constant factors you can profile later are the 2x decisions.

**Why:** TigerStyle's claim, and it is empirical: "the best time to solve performance, to get the
huge 1000x wins, is in the design phase, which is precisely when we can't measure or profile." A
profiler tells you which line of the design you committed to is slowest; it cannot tell you that a
different design does not need that line. Once callers depend on a per-item API, converting it to a
batch API is a breaking change to every call site, so the cheapest moment to choose the batch API is
before the first caller exists. Mechanical sympathy is the corrective: like a carpenter, work with
the grain — sequential access, contiguous memory, predictable branches, one syscall per batch.

**Check:** a PR that introduces a new module, a new public API, or a new inner loop names its
dominant cost somewhere a reviewer can read. A PR that has no such statement and adds a per-item
public entry point on a path that will be called in bulk is the specific thing to push back on.

```zig
//! Compaction merges two sorted levels into one.
//!
//! Dominant cost: disk bandwidth. One sequential read of each input level, one sequential
//! write of the output level, no random access, no read amplification beyond 2x. Memory is
//! two 64 KiB streaming buffers, allocated once at startup (ZS-CORE-16).
//!
//! Rejected: an in-memory merge of whole levels. It is simpler and ~1.3x faster per byte,
//! but its memory is O(level size), which removes the static-allocation bound.
// fragment
```

### ZS-PERF-02 [M!] Sketch the cost across the four resources, and write the sketch down
Before a change lands on a hot path, sketch its cost against the four resources — **network, disk,
memory, CPU** — and their two characteristics — **bandwidth** and **latency**. Put the sketch in the
commit message or in a comment above the function. Sketches are cheap and being roughly right lands
you within 90% of the achievable maximum.

**Why:** the sketch is the artifact that makes the rest of this chapter reviewable. Without it, "is
this fast enough?" is a matter of opinion and the review degenerates into taste. With it, a reviewer
can check arithmetic — and arithmetic is checkable. It also catches the common failure where an
optimization targets the resource that was never the bottleneck: a hand-vectorized parser in front
of a synchronous 1 ms `fsync` per record buys nothing, and the sketch says so in one line before
anyone writes the vector code.

Order-of-magnitude anchors for 2026 server hardware. These are correct to within roughly 10x; the
*ratios* are the point, not the digits.

| Resource | Bandwidth | Latency |
|---|---|---|
| Network, same rack | 1–10 GiB/s | ~100 us round trip |
| Network, cross region | window-limited | 50–150 ms round trip |
| Disk, NVMe | 1–7 GiB/s | ~100 us read; ~1 ms `fsync` |
| Memory | 10–50 GiB/s | ~1 ns L1 hit; ~100 ns miss to DRAM |
| CPU | 1–4 instructions/cycle | ~0.3 ns per cycle; ~5 ns branch mispredict |

**`[M!]` trigger:** the code has a stated throughput or latency requirement, or it is on a path
executed per request, per record, per packet, or per block — databases, storage engines, consensus,
codecs, network services, embedded control loops. In those codebases a hot-path PR without a sketch
is not reviewable and should be sent back.

***Relaxed form*** everywhere else: no written sketch is required, but a change that adds work
*inside* an existing loop — an allocation, a syscall, a lock, a hash, a `format` call — states in
one line why that is acceptable at the loop's trip count. A change that adds work outside every loop
needs nothing.

**Check:** grep the diff for new work inside a loop body. If the loop's bound is unbounded or
input-derived and the commit message contains no cost statement, that is the finding.

```zig
// verified
const block_size_bytes = 64 * 1024;

/// Cost sketch, per call, on a 4 KiB-page NVMe device:
///   disk:    1 read of 64 KiB          ~ 60 us  (bandwidth-bound at 1 GiB/s)
///   memory:  1 pass over 64 KiB        ~  6 us  (1024 cache lines, streaming)
///   CPU:     1 byte-wise add per byte  ~ 20 us  (not vectorized: see ZS-PERF-15)
/// Disk dominates. Do not micro-optimize the adder until the read is batched.
fn checksumBlock(block: *const [block_size_bytes]u8) u64 {
    var sum: u64 = 0;
    for (block) |byte| sum +%= byte;
    return sum;
}
```

### ZS-PERF-03 [M] Rank the resources by cost *times frequency*, and optimize the top of that list
Optimize for the slowest resource first — network, then disk, then memory, then CPU — **after**
multiplying each by how often it is used. A faster resource touched many more times can dominate a
slower one.

**Why:** this is the correction that makes the ordering useful rather than a slogan. TigerStyle's
example is exact: a memory cache miss may cost as much as a disk `fsync`, if it happens many times
more. One `fsync` at 1 ms, ten times a second, is 10 ms/s of the budget. A 100 ns DRAM miss, ten
million times a second, is 1000 ms/s — it is *the* bottleneck, and it is invisible to anyone who
ranked "memory is faster than disk" and stopped there. Frequency is the term people drop.

**Check:** the sketch from ZS-PERF-02 must be a product, not a rate: `cost x count`, with the count
named. A sketch that lists per-operation latencies without operation counts has not made the
comparison this rule requires, and a reviewer can say so without knowing anything about the domain.

```
Per second, at the stated target of 10k requests/s:

  disk    fsync        1 ms   x    10 (group commit, 1000 req/batch)  =   10 ms/s
  network round trip 100 us   x 10000                                 = 1000 ms/s   <- dominant
  memory  DRAM miss  100 ns   x  4e6 (400 lookups/req)                =  400 ms/s
  CPU     checksum     2 us   x 10000                                 =   20 ms/s

Conclusion: batch the network round trip before touching anything else. The DRAM misses are
second and worth a layout change (ZS-DATA-25); the checksum is noise.
```

### ZS-PERF-04 [S] Say whether a function is control plane or data plane, and budget it
The **control plane** runs once per batch, per connection, per epoch — it may assert liberally,
including O(N) checks. The **data plane** runs once per item and gets O(1) assertions only. Say
which one a function is in, in its doc comment, when it is not obvious from the name.

**Why:** this is the mechanism by which TigerStyle gets a very high assertion density *and* high
throughput, rather than trading one for the other. Batching creates the control plane: once N items
are handled as one unit, an O(N) verification of that unit costs O(1) *per item*, so the expensive
check becomes affordable exactly because of the batching. Without the split, every assertion is
priced at the per-item rate and the honest options are both bad — either you delete assertions to go
fast, or you keep them and pay per item. TigerBeetle runs 2–3x the two-assertions-per-function floor
in its control plane and gates the O(N) checks behind a verify flag in its data plane; see
`references/assertions.md` ZS-ASSERT-20 for the budgeting rule itself.

**Check:** find the O(N) assertions in the diff and ask what calls them. An O(N) assert reachable
from a per-item function is the finding — either it moves up to the batch boundary or it goes behind
the verify flag.

```zig
// verified
const std = @import("std");
const assert = std.debug.assert;
const Request = struct { key: u32, value: u32 };

const Table = struct {
    entries: []Request,
    count: u32,

    /// Control plane: runs once per batch. Assert freely, including O(N).
    fn apply(table: *Table, batch: []const Request) void {
        assert(batch.len > 0);
        assert(table.count + batch.len <= table.entries.len);
        assert(sortedByKey(batch)); // O(N), amortized over the whole batch.

        for (batch) |request| table.insert(request);

        assert(table.count <= table.entries.len);
    }

    /// Data plane: runs once per entry. O(1) assertions only.
    fn insert(table: *Table, request: Request) void {
        assert(table.count < table.entries.len);
        table.entries[table.count] = request;
        table.count += 1;
    }

    fn sortedByKey(batch: []const Request) bool {
        for (batch[1..], batch[0 .. batch.len - 1]) |next, prev| {
            if (next.key < prev.key) return false;
        }
        return true;
    }
};
```

### ZS-PERF-05 [M!] Amortize every expensive acquisition over a bounded batch
One syscall, one lock acquisition, one allocation, one flush, one round trip **per batch** — never
per item. The batch has a named `_max` constant and the code asserts it (ZS-ASSERT-24).

**Why:** every one of those operations has a fixed cost that dwarfs the per-item work: a syscall is
hundreds of nanoseconds of mode-switch before it does anything; an uncontended lock is tens of
nanoseconds of atomic traffic; a contended one is a scheduler round trip; a `realloc` is a copy of
everything. Batching divides that fixed cost by the batch size, which is why it is the single
highest-leverage transformation available at design time and the reason ZS-PERF-04's assertion
budget works at all. The bound is not optional: an unbounded batch converts a throughput win into an
unbounded-latency and unbounded-memory bug.

The I/O half of this rule — draining an event queue instead of reacting per event, `writeVecAll`
instead of a write per record — is `references/concurrency.md` **ZS-CONC-35**; do not duplicate
it. This rule covers the non-I/O half: locks, allocations, and per-item work inside a lock.

**`[M!]` trigger:** the same criteria as ZS-PERF-02 — a stated throughput or latency requirement, or
per-request/per-record/per-packet execution. ***Relaxed form:*** batch anything whose per-item cost
crosses a process boundary (syscall, lock, allocator), and leave pure in-memory per-item work alone
until measured.

**Check:** for each `lock`, `alloc`, `write`, or `send` in the diff, find the enclosing loop. If the
call is inside the loop and the loop is over items rather than over batches, that is the finding.

```zig
// verified
const std = @import("std");
const assert = std.debug.assert;
const Io = std.Io;
const Sink = struct {
    mutex: Io.Mutex = .init,
    total: u64 = 0,

    const batch_max = 128;

    /// One lock acquisition per batch, not per item.
    fn addBatch(s: *Sink, io: Io, items: []const u64) void {
        assert(items.len <= batch_max);

        s.mutex.lockUncancelable(io);
        defer s.mutex.unlock(io);

        for (items) |item| s.total += item;
    }
};
```

### ZS-PERF-06 [S] Give the CPU one long lane; do not make it change lanes per item
Hoist a loop-invariant condition out of the loop, and group items by kind before processing rather
than branching per item. Let the CPU be a sprinter doing the 100m: predictable, uninterrupted,
straight.

**Why:** a branch whose outcome is the same on every iteration still costs a predictor slot and
blocks the loop from being widened; a branch whose outcome alternates unpredictably costs a full
pipeline flush — around 15–20 cycles, which on a loop body of 5 cycles is a 4x slowdown all by
itself. Splitting the loop by condition gives each resulting loop a perfectly predicted branch. The
memory-layout version of the same argument — do not drag 8 unused bytes into cache per element —
lives in `references/data.md` ZS-DATA-25 (`MultiArrayList`).

**Check:** any `if` inside a loop whose condition does not depend on the loop variable. That is a
mechanical grep and it is almost always a mistake.

```zig
// verified — BAD: the condition is re-tested on every element
fn scaleAllBad(values: []f32, factor: f32, enabled: bool) void {
    for (values) |*v| {
        if (enabled) v.* *= factor;
    }
}
```

```zig
// verified — GOOD: one test, then one straight lane
fn scaleAll(values: []f32, factor: f32, enabled: bool) void {
    if (!enabled) return;
    for (values) |*v| v.* *= factor;
}
```

### ZS-PERF-07 [M] Be explicit; never depend on an optimization the compiler is not obliged to make
Write the hoist, the strength reduction, and the bound yourself when they matter. Treat every
compiler optimization as a bonus, never as a load-bearing assumption.

**Why:** Zig's optimizer is LLVM's, and LLVM's guarantees are best-effort. 0.16 is the proof: loop
vectorization was *disabled outright* in that release, and is still disabled in 0.17 (ZS-PERF-15),
so any code whose performance budget assumed auto-vectorization regressed silently on upgrade. The
same applies to loop-invariant code motion through a pointer — the compiler must prove the loop
body cannot write through it before it may cache a field in a register, and a `*Self` parameter
frequently defeats that proof. Writing
the hoist costs one line, documents the invariant, and makes a redundant computation visible to a
human reviewer, which is the durable benefit.

**Check:** a field load (`x.field`) inside a loop body where the loop also writes through a pointer.
Hoist it to a `const` above the loop, or take the parameters directly (ZS-PERF-08).

```zig
// verified
const std = @import("std");
const assert = std.debug.assert;
const Grid = struct {
    cells: []u8,
    width: u32,
    height: u32,

    fn rowChecksum(grid: *const Grid, row: u32) u32 {
        assert(row < grid.height);

        const width = grid.width; // Hoisted once, by hand, not by hope.
        const start = row * width;

        var sum: u32 = 0;
        for (grid.cells[start..][0..width]) |cell| sum +%= cell;
        return sum;
    }
};
```

### ZS-PERF-08 [S] Hand a measured hot loop its data as slices and integers, not as a receiver
Extract the kernel into a stand-alone function whose parameters are the exact slices and scalars it
reads. The wrapper method stays, and does the field access once.

**Why:** TigerStyle makes this claim narrowly and under *Performance*, not naming: with primitive
arguments "the compiler doesn't need to prove that it can cache struct's fields in registers, and a
human reader can spot redundant computations easier." Aliasing is the mechanism — through a
`*Journal`, a store to `journal.sectors[i]` may in principle alias `journal.sector_count`, so every
iteration must reload the count. Passing the count by value removes the question. The
receiver-naming half of this rule, including the explicit warning not to delete receivers wholesale
on its strength, is `references/naming.md` **ZS-NAME-15**.

**Check:** this rule is only invocable with a profile. In review, the finding is the *reverse*
direction: a PR that converts methods to free functions across a module without a benchmark in the
commit message is over-applying it.

```zig
// verified
const std = @import("std");
const assert = std.debug.assert;
const Journal = struct {
    sectors: []const u8,
    sector_size: u32,
    sector_count: u32,

    /// Thin wrapper: reads the fields once, then gets out of the way.
    fn checksum(journal: *const Journal) u64 {
        return checksumSectors(journal.sectors, journal.sector_size * journal.sector_count);
    }
};

/// Hot loop. Primitives only, so nothing can alias `length`.
fn checksumSectors(bytes: []const u8, length: u32) u64 {
    assert(length <= bytes.len);
    var sum: u64 = 0;
    for (bytes[0..length]) |byte| sum +%= byte;
    return sum;
}
```

---

## Part 2 — The discipline of locality

These five rules are one idea seen from five sides: **the distance between where a fact is
established and where it is used is the space in which bugs live.** They cost nothing, they apply to
all code, and they are the part of TigerStyle most often dropped because none of them look like
performance rules. They are here because TigerStyle files them under performance and developer
experience jointly, and because shrinking that distance is also what makes a value stay in a
register.

### ZS-PERF-09 [M] Declare every variable at the smallest scope that can hold it
Push each declaration down into the innermost block that uses it, and minimize how many variables
are live at any point. A variable that exists in a scope where it is not used is a variable that can
be used by mistake.

**Why:** the number of ways to write a wrong line grows with the number of names in scope. Two
similarly named counters in the same function is how `matches` gets incremented where `previous`
belonged, and the compiler cannot help — both type-check. Shrinking the scope makes the wrong name a
compile error rather than a wrong answer. The performance benefit is real but secondary: a value
whose live range is one block is a value the register allocator can keep in a register.

**Check:** for each `var`/`const` in the diff, find its first and last use. If both are inside a
nested block, the declaration belongs in that block. Count the declarations live at the widest point
of the function; more than about five in a non-trivial function is a smell worth a comment.

```zig
// verified — BAD: three names live for the whole function
fn countMatchesBad(haystack: []const u8, needle: u8) u32 {
    var matches: u32 = 0;
    var previous: u32 = 0;
    var byte_index: usize = 0;
    while (byte_index < haystack.len) : (byte_index += 1) {
        if (haystack[byte_index] == needle) {
            previous = matches;
            matches += 1;
        }
    }
    return matches;
}
```

```zig
// verified — GOOD: `previous` exists only where it means something
const std = @import("std");
const assert = std.debug.assert;
fn countMatches(haystack: []const u8, needle: u8) u32 {
    var matches: u32 = 0;
    for (haystack) |byte| {
        if (byte != needle) continue;

        const previous = matches;
        matches += 1;
        assert(matches == previous + 1);
    }
    return matches;
}
```

### ZS-PERF-10 [M] Never duplicate a variable, and never hold an alias to one
One fact, one storage location. Do not copy a field into a local that outlives a mutation of the
field, and do not keep a pointer into a container across an operation that can move it.

**Why:** two copies of one fact is two things to update and one of them will eventually be missed —
this is the plain form of cache invalidation, and TigerStyle names it as such. In Zig it has a
second edge with teeth: a pointer into `list.items` is invalidated by any append or resize
(`ZS-CORE-15` / `references/data.md` ZS-DATA-23), so a duplicated pointer is not merely
stale, it is a use-after-free. Holding the *index* keeps one source of truth and survives
reallocation. Note the tension with ZS-PERF-07's hoist: hoisting is legal precisely when the loop
cannot mutate the hoisted fact, and the hoisted `const` dies at the end of the loop.

**Check:** every pointer-typed local in the diff — does any call between its creation and its last
use mutate the container it points into? And every local that shadows a field name — is the field
written between them?

```zig
// fragment — BAD: `slot` dangles the moment `append` reallocates
const slot = &pool.slots.items[index];
slot.* += 1;
try pool.slots.append(gpa, 0);
slot.* += 1; // Use-after-free.
```

```zig
// verified — GOOD: hold the index, read through the owner
const std = @import("std");
const Pool = struct {
    slots: std.ArrayList(u32),

    fn bump(pool: *Pool, gpa: std.mem.Allocator, index: usize) !void {
        pool.slots.items[index] += 1;
        try pool.slots.append(gpa, 0); // May reallocate; we hold no pointer.
        pool.slots.items[index] += 1;
    }
};
```

### ZS-PERF-11 [M] Calculate and check a value next to where it is used — avoid POCPOU
Do not introduce a variable before it is needed, and do not leave a check far from the use it
protects. The gap between the place of check and the place of use is a **POCPOU** bug waiting to
happen — place-of-check to place-of-use, the spatial cousin of the temporal TOCTOU.

**Why:** TOCTOU is famous because the *time* between checking a file and opening it lets someone
else change it. POCPOU is the same failure in *space*: the check `offset + length <= buffer.len` is
performed at line 10 and the slice is taken at line 60, and in between someone re-slices `buffer`,
reassigns `header`, or adds an early `continue` that skips the check for one path. Nothing in the
type system connects the two lines; only proximity does. TigerStyle's summary is the reason to care
beyond memory safety: "most bugs come down to a semantic gap, caused by a gap in time or space,
because it's harder to check code that's not contained along those dimensions." Keeping the check
adjacent to the use makes correctness a local property that a reviewer can verify by reading two
consecutive lines instead of reconstructing the whole function.

**Check:** for every bounds check, null check, or validity check in the diff, count the statements
between it and the use it guards. More than a few, or any control flow in between, is the finding.
The fix is to move the check down, or to make the check *produce* the value it validates — a
function that returns the checked slice cannot be separated from its own check.

```zig
// verified — BAD: the check and the slice are separated by everything in between
const Header = struct { length: u32, offset: u32 };

fn readPayloadBad(buffer: []const u8, header: Header) ![]const u8 {
    if (header.offset + header.length > buffer.len) return error.HeaderOutOfRange;

    // ... unrelated work, during which `buffer` may be re-sliced or `header` re-read ...

    return buffer[header.offset..][0..header.length];
}
```

```zig
// verified — GOOD: check and use are adjacent, and the checked value is the return value
const std = @import("std");
const Header = struct { length: u32, offset: u32 };

fn readPayload(buffer: []const u8, header: Header) ![]const u8 {
    const start = header.offset;
    const end = std.math.add(u32, header.offset, header.length) catch
        return error.HeaderOutOfRange;
    if (end > buffer.len) return error.HeaderOutOfRange;
    return buffer[start..end];
}
```

Note the second bug the BAD version hides: `header.offset + header.length` can overflow `u32` before
the comparison, so the check can pass on input that should be rejected. In `debug`/`safe`
that panics; in `fast` it wraps and the slice goes out of bounds. Distance concealed it — see
`references/data.md` ZS-DATA-10 for `std.math.add`.

### ZS-PERF-12 [S] Centralize state manipulation: helpers compute the change, the parent applies it
Let the parent function hold the state in locals or in one receiver, and let helpers *return* what
should change rather than applying it. Keep leaf functions pure.

**Why:** TigerStyle pairs this with "centralize control flow" (ZS-CORE-21, push `if`s up and `for`s
down) for the same reason: if every leaf may mutate, then the set of states reachable at any point
is the product of every leaf's behavior, and no single function can assert the invariant. With one
apply site, there is exactly one place to bracket with `assertInvariants`
(`references/assertions.md` ZS-ASSERT-17), one place to make transactional with `errdefer`,
and one place to read when the invariant breaks. Pure leaves are also directly testable and
trivially reorderable — you can compute all the deltas first and apply them in one pass, which is
what makes batching (ZS-PERF-05) possible in the first place.

**Check:** count the assignments to a given field across the module. If more than one function
mutates the same field, ask whether the inner one could return a value instead. A helper whose only
parameter is `*Self` and whose body assigns to fields is the shape to look for.

```zig
// verified — BAD: two functions mutate, so no one function can assert the invariant
const AccountBad = struct {
    balance: u64,
    reserved: u64,

    fn releaseInner(account: *AccountBad, amount: u64) void {
        account.balance += amount;
    }

    fn release(account: *AccountBad, amount: u64) void {
        account.releaseInner(amount);
        account.reserved -= amount;
    }
};
```

```zig
// verified — GOOD: the leaf is pure, the parent is the single apply site
const std = @import("std");
const assert = std.debug.assert;
const Account = struct {
    balance: u64,
    reserved: u64,

    const Delta = struct { balance: i64, reserved: i64 };

    /// Pure leaf: computes what should change, mutates nothing. Directly testable.
    fn deltaForRelease(account: Account, amount: u64) Delta {
        assert(amount <= account.reserved);
        assert(amount <= std.math.maxInt(i64)); // The delta type must hold it.
        return .{ .balance = @intCast(amount), .reserved = -@as(i64, @intCast(amount)) };
    }

    /// The only mutator. One apply site, so one place to assert the invariant.
    fn release(account: *Account, amount: u64) void {
        // u128: the ledger total may legitimately exceed maxInt(u64), so summing
        // the two columns in their own type would overflow on a valid account.
        const total_before = @as(u128, account.balance) + account.reserved;
        const delta = account.deltaForRelease(amount);

        // A release moves value between columns; it never creates or destroys any.
        assert(delta.balance + delta.reserved == 0);
        account.balance = applyDelta(account.balance, delta.balance);
        account.reserved = applyDelta(account.reserved, delta.reserved);

        // The invariant worth asserting is conservation — a property a wrong
        // mutator can actually violate. `reserved <= balance + reserved` would
        // hold for every u64 pair in existence and so checks nothing.
        assert(@as(u128, account.balance) + account.reserved == total_before);
    }

    /// Applies a signed delta without round-tripping the `u64` through `i64`,
    /// which would panic for any balance above `maxInt(i64)`.
    fn applyDelta(value: u64, delta: i64) u64 {
        if (delta < 0) return value - @as(u64, @intCast(-delta));
        return value + @as(u64, @intCast(delta));
    }
};
```

### ZS-PERF-13 [S] Shape functions like an inverted hourglass: narrow in, narrow out, wide inside
Few parameters, a simple return type, and a lot of meaty logic between the braces. If a function is
mostly signature, it is in the wrong place.

**Why:** this is TigerStyle's rule of thumb for *where* to cut a function that exceeds the 70-line
limit (ZS-CORE-21) — not every split is equal, and the good ones produce inverted hourglasses. The
argument is the same locality argument: a wide signature exports the function's internal state to
every call site, so a change to it is a change everywhere, and each extra return dimension
propagates up the whole call chain (ZS-CORE-24 / `references/data.md` ZS-DATA-30). A
function whose body is three lines and whose signature is eight parameters has not been abstracted;
it has been relocated, and it now costs an argument-marshalling sequence at every call.

**Check:** parameter count above roughly four, or a body shorter than the signature, or a return
type of `!?Something` where the caller must handle three outcomes. Each is a prompt to ask whether
the split was made at the right place.

```zig
// verified — narrow in ([]const u8), narrow out (?Frame), meaty in between
const std = @import("std");
const Frame = struct {
    kind: enum { data, control },
    length: u32,
    payload_checksum: u32,
};

fn parseFrame(bytes: []const u8) ?Frame {
    if (bytes.len < 9) return null;

    const kind: @TypeOf(@as(Frame, undefined).kind) = switch (bytes[0]) {
        0 => .data,
        1 => .control,
        else => return null,
    };
    const length = std.mem.readInt(u32, bytes[1..5], .little);
    const payload_checksum = std.mem.readInt(u32, bytes[5..9], .little);
    if (length > bytes.len - 9) return null;

    return .{ .kind = kind, .length = length, .payload_checksum = payload_checksum };
}
```

---

## Part 3 — Zig 0.17 mechanics

### ZS-PERF-14 [M] Measure in the mode you ship, and never quote a `debug` number
Benchmarks build at `fast` or at the mode you actually ship; a number from a `debug` build is
not evidence of anything. Know what each mode costs before you invoke one in an argument.

**Why:** `debug` applies no optimization at all *and*, for `x86_64-linux`, uses the self-hosted
x86_64 backend, which the 0.16.0 release notes describe as having "significantly faster compilation
speed, superior debug information, and inferior machine code quality"; 0.17.0 keeps that default.
The gap between `debug` and `fast` on a tight loop is routinely 10–50x, which swamps every effect
this chapter discusses; a "2x speedup" measured in `debug` is noise. The mode table and the argument
for shipping `safe` are `references/build.md` **ZS-BUILD-27** — read it before choosing
`fast` for a shipped artifact, because in `fast` every `std.debug.assert` becomes a
licence for the optimizer rather than a check (ZS-CORE-10).

**Check:** any performance claim in a commit message or comment must name the optimize mode. A
`bench` step that inherits `-Doptimize` instead of pinning its own mode is the structural version of
the same bug — see ZS-PERF-23.

```zig
// fragment
const builtin = @import("builtin");

// A benchmark that refuses to produce a meaningless number.
comptime {
    if (builtin.optimize == .debug) @compileError("build benchmarks with -Doptimize=fast");
}
```

### ZS-PERF-15 [M] Do not rely on auto-vectorization in 0.17 — the loop vectorizer is disabled
Zig 0.16.0 disabled LLVM loop vectorization entirely, to work around an LLVM 21 miscompilation that
was corrupting the compiler itself, and Zig 0.17.0 keeps it disabled: the LLVM fix is not in LLVM
22, which 0.17 uses. If a loop must use SIMD, write the vectors yourself (ZS-PERF-16).

**Why:** compiling a scalar `u32` sum loop at `fast` for `aarch64` emits scalar code only (LLVM 22
unrolls it four times, but every load and add is still a 32-bit scalar: `ldp w16, w17` /
`add w13, w16, w13`), while the same file's explicit `@Vector(8, u32)` version emits
`ldp q2, q3, [x8], #32` and `add.4s` — eight lanes per iteration from the same optimizer, in the
same build. So the pessimization is real and it is specifically the *automatic* path that is gone.
The 0.17.0 release notes say the workaround stays until 0.18.0 moves to LLVM 23, so it has now
covered 0.16.x **and** 0.17.x and is not a one-release inconvenience to wait out. The consequence
for review: a performance budget written against Zig 0.14/0.15 measurements does not transfer, and
any comment claiming "the compiler will vectorize this" is now false.

**Check:** search comments and design notes for claims that a loop "vectorizes" or "gets
auto-vectorized". Each one is either wrong or needs to become an explicit `@Vector`.

```
$ zig build-obj vec.zig -O fast -femit-asm=vec.s   # aarch64, Zig 0.17.0

sumScalar (plain while loop over []const u32):
        ldp     w16, w17, [x15, #-8]  <- unrolled 4x, but scalar 32-bit registers
        add     w13, w16, w13
        add     w8, w17, w8
        ldp     w16, w17, [x15], #16
        add     w11, w16, w11
        add     w12, w17, w12

sumManual (explicit @Vector(8, u32)):
        ldp     q2, q3, [x8], #32     <- eight elements per iteration
        add.4s  v0, v3, v0
        add.4s  v1, v2, v1
```

### ZS-PERF-16 [S] Write SIMD explicitly with `@Vector`, sized by `std.simd.suggestVectorLength`
Use `@Vector(len, T)` with `len` from `std.simd.suggestVectorLength(T)`, `@splat` to broadcast,
`@reduce` to fold, `@select` to blend, `@shuffle` to permute — and always keep a scalar tail loop
for the remainder.

**Why:** `suggestVectorLength` returns `?comptime_int` and consults the actual target CPU features.
It picks a register width — 512 bits for AVX-512, 256 for AVX2 or SVE, 128 for SSE or NEON, `null`
for a target with no vector unit — and divides by `@bitSizeOf(T)`, so `suggestVectorLength(u32)` is
16 lanes on AVX-512 and 4 on NEON. The kernel therefore stays portable and cross-compiles correctly
instead of hard-coding a width that degrades to scalar emulation elsewhere. Hand-written vectors are
also the only SIMD available in 0.17 (ZS-PERF-15). Two 0.17 constraints to know: indexing a
`@Vector` with a runtime value, to read or to store, is a compile error (`vector index not comptime
known`), and *in-memory* coercion between arrays and vectors is forbidden — but the by-value
coercion `values[i..][0..lanes].*` used below is fine and is the idiom.

**Check:** a hard-coded lane count (`@Vector(4, f32)`) with no comment explaining the target, or a
vector loop with no scalar tail — the tail is where the off-by-one lives.

```zig
// verified
const std = @import("std");
fn sumVectorized(values: []const u32) u32 {
    const lanes = std.simd.suggestVectorLength(u32) orelse 1;
    const V = @Vector(lanes, u32);

    var accumulator: V = @splat(0);
    var index: usize = 0;
    while (index + lanes <= values.len) : (index += lanes) {
        const chunk: V = values[index..][0..lanes].*; // By-value coercion: legal.
        accumulator +%= chunk;
    }

    var total = @reduce(.Add, accumulator);
    while (index < values.len) : (index += 1) total +%= values[index]; // Scalar tail.
    return total;
}
```

```zig
// verified
const std = @import("std");
test "blend and permute" {
    const V = @Vector(4, i32);
    const a: V = .{ 1, 2, 3, 4 };
    const b: V = .{ 10, 20, 30, 40 };

    const mask: @Vector(4, bool) = .{ true, false, true, false };
    const picked = @select(i32, mask, a, b);
    try std.testing.expectEqual(1, picked[0]);
    try std.testing.expectEqual(20, picked[1]);

    const reversed = @shuffle(i32, a, undefined, @Vector(4, i32){ 3, 2, 1, 0 });
    try std.testing.expectEqual(4, reversed[0]);
}
```

### ZS-PERF-17 [S] Mark cold and likely paths with `@branchHint`, as the branch's first statement
`@branchHint` is **only** legal as the first statement of a function or of a control-flow branch.
Anything else — even one `assert` before it — is a compile error. Use `.cold` on error paths and
`.likely`/`.unlikely` where the distribution is known and skewed.

**Why:** `.cold` lets the optimizer relocate a branch's code away from the hot path, keeping the
instruction cache dense along the path that actually runs; `.unpredictable` asks for branchless
lowering where a mispredict would cost more than doing both sides. The full hint list, std's usage
counts, and the `@setCold` migration are `references/errors.md` **ZS-ERR-31**. The
placement constraint is worth repeating here only because it interacts with this chapter's own
advice: if you follow ZS-CORE-08 and assert at the top of a cold branch, the hint must come *first*,
before the assert.

**Check:** a `@branchHint` that is not the first statement — the compiler catches it, so the real
review finding is a `.likely` on a branch nobody measured. Hints assert a distribution; a wrong one
is worse than none.

```zig
// verified
fn decodeTag(byte: u8) error{ReservedTag}!u8 {
    if (byte < 0x80) {
        @branchHint(.likely);
        return byte;
    } else {
        @branchHint(.cold);
        return error.ReservedTag;
    }
}
```

```zig
// rejected — zig: a `@branchHint` after an if/return is not first in the function
fn decodeTagBad(byte: u8) error{ReservedTag}!u8 {
    if (byte < 0x80) return byte;
    @branchHint(.cold); // error: '@branchHint' must appear as the first statement
    return error.ReservedTag; //        in a function or conditional branch
}
```

### ZS-PERF-18 [M] Spell out every `@prefetch` option; never rely on the defaults
Write `@prefetch(ptr, .{ .cache = .data, .rw = .read, .locality = 3 })`, not `@prefetch(ptr, .{})`.
This is the chapter home of **ZS-CORE-27**, and the principle generalizes: pass options explicitly
at the call site rather than inheriting a library default.

**Why:** TigerStyle's argument is about defaults changing under you — "avoids latent, potentially
catastrophic bugs in case the library ever changes its defaults" — and call sites do not get
re-reviewed when a default moves. `std.lang.PrefetchOptions` today defaults to `.rw = .read,
.locality = 3, .cache = .data`; those are three independent knobs (`Rw`, `u2`, `Cache`) and nothing
pins them. The explicit form is also the only self-documenting one: `.locality = 0` means "stream
it, drop it after one touch" and `.locality = 3` means "keep it, we will come back" — a distinction
the reader cannot see in `.{}`, and one that is worth real cache behavior. The
builtin lowers to a real instruction on 0.17/aarch64: the loop below emits `prfm pldl1keep`.

**Check:** grep for `@prefetch(` with a `.{}` or a partial options literal. Every field spelled out,
or it is a finding — and the prefetch distance should have a comment saying why that stride.

```zig
// verified
fn sumPrefetched(values: []const u64) u64 {
    const stride = 8; // ~1 cache line ahead at 8 bytes/element on a 64-byte line.
    var sum: u64 = 0;
    for (values, 0..) |v, i| {
        if (i + stride < values.len) {
            @prefetch(&values[i + stride], .{ .cache = .data, .rw = .read, .locality = 3 });
        }
        sum +%= v;
    }
    return sum;
}
```

### ZS-PERF-19 [S] Align independently written concurrent fields to `std.atomic.cache_line`
When two threads write two different fields of the same struct, give each its own cache line with
`align(std.atomic.cache_line)`. Do not do this to fields that are read together on one thread — that
wastes cache.

**Why:** false sharing. The coherence protocol works in cache lines, not fields, so two counters in
the same 64- or 128-byte line force every write by one thread to invalidate the other thread's copy;
the result is an uncontended-looking data structure that behaves like a contended lock and gets
slower as you add cores. `std.atomic.cache_line` is a `comptime_int` computed per target CPU
(`cacheLineForCpu`), which is why it is the right constant to write rather than a literal `64` — it
is 128 on several targets. The cost is real: the struct below is at least two cache lines, so
applying this reflexively to a hot read-only struct makes every scan touch more lines.

**Check:** any struct with two or more `std.atomic.Value` fields written by different threads and no
alignment on them. Conversely, an `align(cache_line)` on a field with no concurrent writer is
padding for nothing.

```zig
// verified
const std = @import("std");
const Counters = struct {
    produced: std.atomic.Value(u64) align(std.atomic.cache_line) = .init(0),
    consumed: std.atomic.Value(u64) align(std.atomic.cache_line) = .init(0),
};

test "no false sharing" {
    try std.testing.expect(@sizeOf(Counters) >= 2 * std.atomic.cache_line);
}
```

### ZS-PERF-20 [S] Use `inline fn` only for the three reasons the langref gives
The 0.17.0 langref names them: to ensure certain stack frames are in the call stack, for debugging
or for integrating with assembly; to force arguments that happen to be comptime-known to propagate
to the return value; and to work around limitations of compiler backend implementations. The 0.16.0
langref's third reason was "real world performance measurements demand it"; 0.17 dropped it, so a
performance-motivated `inline` now rests on this chapter's measurement rule alone. Trivial
forwarding shims in generic wrappers are the common legitimate case, sanctioned without a fresh
measurement by `references/comptime.md` ZS-COMPTIME-11 and ZS-COMPTIME-05, which states the
langref's reasons from the comptime side.

**Why:** `inline` in Zig is not a hint — it is semantics. The langref is blunt: "Use of `inline`
restricts what the compiler is allowed to do. This can harm binary size, compilation speed, and even
runtime performance." An inlined body cannot be shared, so a large `inline fn` called from
many sites multiplies code size and evicts the instruction cache — the exact opposite of the effect
intended. LLVM already inlines small functions at `fast`; writing `inline` on them buys
nothing and removes the compiler's ability to decide otherwise when the function grows.

**Check:** every `inline fn` in the diff. If its body is more than a few lines and the commit
message has no measurement, that is the finding. `inline` on a hot loop *body* is nearly always
wrong; on a one-line accessor forwarding into a generic implementation, nearly always right.

```zig
// verified — a one-line shim over a generic implementation: fine
const Ring = struct {
    buffer: [16]u32,
    head: u4,

    inline fn full(ring: *const Ring) bool {
        return ring.head == ring.buffer.len - 1;
    }
};
```

---

## Part 4 — How to measure

Rules across this standard say "unless you have measured". This is what measuring looks like in
0.17.

### ZS-PERF-21 [M] Time with `Io.Timestamp` and `Io.Duration` — `std.time.Timer` no longer exists
`std.time` in 0.17 holds unit constants and `std.time.epoch`, nothing else. Take timestamps with
`Io.Timestamp.now(io, clock)` and differences with `durationTo` or `untilNow`. The monotonic clock
is `.awake`; there is no `.monotonic`.

**Why:** `std.time.Timer.start()` fails with `error: root source file struct 'time' has
no member named 'Timer'`. Time moved into `Io` with the rest of the platform surface, which is what
makes it mockable: a deterministic-simulation `Io` can hand a test a controlled clock, and the same
benchmark code runs against the real one. Clock choice matters for benchmarks: `.awake` excludes
system suspend and never goes backwards, `.real` is settable by NTP and can jump, and
`.cpu_thread`/`.cpu_process` measure CPU rather than wall time — use `.awake` for latency and
`.cpu_thread` when you want to exclude time descheduled.

**Check:** any `std.time.Timer`, `std.time.milliTimestamp`, `std.time.nanoTimestamp`, or
`std.time.sleep` in a diff is pre-0.16 code. Any benchmark timing with `.real` should say why.

```zig
// verified
const std = @import("std");
const Io = std.Io;
test "time a region of code" {
    const io = std.testing.io;

    const started: Io.Timestamp = .now(io, .awake);
    var sink: u64 = 0;
    for (0..1000) |i| sink +%= i;
    std.mem.doNotOptimizeAway(sink);
    const elapsed: Io.Duration = started.untilNow(io, .awake);

    try std.testing.expect(elapsed.toNanoseconds() >= 0);
}
```

`Io.Duration` has a `format` method, so `{f}` prints it human-readably — `3.495ms`, `1.2us`. Per
ZS-CORE-27 and the 0.16 formatting change, it must be `{f}`: a bare `{}` prints the raw struct.

### ZS-PERF-22 [M] Warm up, repeat, and defend the measured expression from dead-code elimination
A benchmark runs the work once to warm caches and the branch predictor, then repeats it a known
number of times, then divides. Feed every result to `std.mem.doNotOptimizeAway` or the optimizer
will delete the code you are timing.

**Why:** at `fast` a pure function whose result is discarded is dead, and LLVM removes it —
the classic result is a "1000x speedup" that is really an empty loop. `std.mem.doNotOptimizeAway`
(std/mem.zig) launders the value through inline assembly so the computation must happen. The warm-up
matters for a different reason: the first iteration pays cold i-cache, cold d-cache, cold TLB, and
an untrained branch predictor, which on a short benchmark can be most of the measured time. Dividing
by the iteration count converts a wall-clock number into the per-operation number the ZS-PERF-02
sketch is written in, which is the only form comparable across machines.

**Check:** a benchmark with no warm-up iteration, no repetition count, or a computed result that is
assigned to `_`. All three are the same bug.

```zig
// verified
const std = @import("std");
const Io = std.Io;
fn measure(io: Io, comptime work: fn ([]const u32) u32, input: []const u32) Io.Duration {
    const iterations = 1000;

    std.mem.doNotOptimizeAway(work(input)); // Warm cache, TLB, and predictor.

    const started: Io.Timestamp = .now(io, .awake);
    for (0..iterations) |_| std.mem.doNotOptimizeAway(work(input));
    const elapsed = started.untilNow(io, .awake);

    return .fromNanoseconds(@divFloor(elapsed.toNanoseconds(), iterations));
}
```

One honest caveat: a mean over N iterations hides the tail. If the requirement is a latency bound
rather than a throughput number, record the per-iteration durations and report a high percentile — a
p99 that is 50x the mean is the normal case for anything that allocates or does I/O, and it is
usually the number that matters.

### ZS-PERF-23 [M] Add a `bench` step pinned to `.fast` and not installed by default
Add a `bench` step whose module hard-codes `.optimize = .fast` rather than inheriting
`-Doptimize`, and wire it up with `addRunArtifact` only — never `installArtifact` — so a bare `zig
build` does not pay for it.

**Why:** two failure modes, one rule. Inheriting `-Doptimize` means `zig build bench` on a developer
machine silently measures a `debug` build (ZS-PERF-14). Installing the artifact puts the benchmark
on the critical path of every `zig build` and every CI smoke test, which is
`references/build.md` **ZS-BUILD-09**'s argument. Pinning the mode also makes the number
comparable across machines and across time, which is the entire value of keeping benchmarks in the
repository rather than in a scratch directory.

**Check:** does `build.zig` have a `bench` step at all? Does its module set `.optimize` explicitly,
or does it pass the shared `optimize` variable? Is the benchmark artifact reachable from the default
step?

```zig
// verified — this build.zig was built and `zig build bench` was run against Zig 0.17.0
const std = @import("std");
pub fn build(b: *std.Build) void {
    const target = b.standardTargetOptions(.{});
    const optimize = b.standardOptimizeOption(.{});

    const mod = b.addModule("proj", .{
        .root_source_file = b.path("src/root.zig"),
        .target = target,
    });

    const exe = b.addExecutable(.{
        .name = "proj",
        .root_module = b.createModule(.{
            .root_source_file = b.path("src/main.zig"),
            .target = target,
            .optimize = optimize,
            .imports = &.{.{ .name = "proj", .module = mod }},
        }),
    });
    b.installArtifact(exe);

    // Benchmarks are always `.fast`, whatever -Doptimize says: a `.debug`
    // number measures the debug build, not the one that ships.
    const bench = b.addExecutable(.{
        .name = "bench",
        .root_module = b.createModule(.{
            .root_source_file = b.path("bench/main.zig"),
            .target = target,
            .optimize = .fast,
            .imports = &.{.{ .name = "proj", .module = mod }},
        }),
    });

    // Run-only: never installArtifact, so a bare `zig build` does not pay for it.
    const bench_run = b.addRunArtifact(bench);
    // Forwards `zig build bench -- <args>`; it also disables caching, so the
    // benchmark runs again on every invocation.
    bench_run.addPassthruArgs();
    const bench_step = b.step("bench", "Run benchmarks (always .fast)");
    bench_step.dependOn(&bench_run.step);
}
```

The benchmark's own `main` follows ZS-PERF-14, ZS-PERF-21 and ZS-PERF-22, and prints per-iteration
cost so the number can be compared with the ZS-PERF-02 sketch:

```zig
// fragment — prints e.g. "sum: 3.495ms total, 3.495us per iteration"
const builtin = @import("builtin");
const std = @import("std");
const Io = std.Io;
const assert = std.debug.assert;
pub fn main(init: std.process.Init) !void {
    const io = init.io;
    comptime assert(builtin.optimize == .fast);

    var out_buffer: [512]u8 = undefined;
    var out_writer: Io.File.Writer = .init(.stdout(), io, &out_buffer);
    const out = &out_writer.interface;

    var input: [4096]u32 = undefined;
    for (&input, 0..) |*v, i| v.* = @intCast(i);

    std.mem.doNotOptimizeAway(proj.sum(&input)); // Warm-up.

    const started: Io.Timestamp = .now(io, .awake);
    for (0..iterations) |_| std.mem.doNotOptimizeAway(proj.sum(&input));
    const elapsed: Io.Duration = started.untilNow(io, .awake);

    const per_iteration: Io.Duration =
        .fromNanoseconds(@divFloor(elapsed.toNanoseconds(), iterations));
    try out.print("sum: {f} total, {f} per iteration\n", .{ elapsed, per_iteration });
    try out.flush(); // ZS-CONC-05: buffered output prints nothing without this.
}
```

---

## Part 5 — The counterweight

### ZS-PERF-24 [M] Apply the always-on rules everywhere; require a number before invoking the rest
Half of this chapter is about correctness and legibility and costs nothing to follow. The other half
trades readability for speed and may only be invoked with a measurement, in the shipped optimize
mode, recorded where a reviewer can see it. Do not use this chapter as licence to micro-optimize.

**Why:** the received wisdom is "premature optimization is the root of all evil"; TigerStyle's
counter-quote is "the lack of back-of-the-envelope performance sketches is the root of all evil."
Both are right about different things, and conflating them is how teams end up either with a design
that cannot be made fast or with unreadable code that is not fast either. The resolution is the
design/implementation split of ZS-PERF-01: **shape is decided up front and cheaply; constants are
decided later and with evidence.** A back-of-the-envelope sketch is not premature — it costs five
minutes and it is reversible. A hand-unrolled SIMD kernel is premature until it is on a profile,
because it costs readability permanently and it is the thing that will be wrong when the
requirements change. Note also that safety outranks performance in this standard's ordering
(SKILL.md §3): where a performance rule here conflicts with an assertion, a bound, or a safety
check, the safety rule wins and the performance rule needs a measurement to overturn it — not the
reverse.

| Rule | When it applies |
|---|---|
| ZS-PERF-01 design shape, ZS-PERF-02 sketch, ZS-PERF-03 frequency | Design phase. Always — the cost is minutes. |
| ZS-PERF-09 – ZS-PERF-13 (the whole locality cluster) | **All code, always.** These are readability and correctness rules that happen to also help the register allocator. Never require a measurement. |
| ZS-PERF-07 be explicit, ZS-PERF-14 measure in the shipped mode, ZS-PERF-21 – ZS-PERF-23 how to measure | All code. Following them costs nothing and not following them produces false numbers. |
| ZS-PERF-04 plane split, ZS-PERF-05 batching, ZS-PERF-15 no auto-vectorization | Any code with a stated throughput or latency requirement. Batching in particular is a design decision, so it is cheap now and expensive later. |
| ZS-PERF-06 branch hoisting, ZS-PERF-08 primitive-argument kernels, ZS-PERF-16 explicit SIMD, ZS-PERF-17 `@branchHint`, ZS-PERF-18 `@prefetch`, ZS-PERF-19 cache-line alignment, ZS-PERF-20 `inline` | **Measured hot paths only.** Each one costs readability. A diff that applies them without a profile in the commit message is over-applying this chapter, and that is a review finding in its own right. |

**Check:** when reviewing a change that cites this chapter, ask which row it is in. If it is in the
last row, ask for the number, the optimize mode, and the machine. If the answer is "it should be
faster", the change is not ready.

```zig
// fragment
// The shape of a justification that makes a last-row rule reviewable.
// Hand-vectorized: 4.1 us -> 0.9 us per 4 KiB block, -Doptimize=fast, aarch64-macos,
// mean of 1000 iterations via `zig build bench`. This loop is 38% of the profile
// under the ingest workload. The scalar version is kept in tests as the oracle.
fn checksumBlockVectorized(block: []const u32) u32 {
    ...
}
```
