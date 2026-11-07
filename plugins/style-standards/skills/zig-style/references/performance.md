# Performance and the discipline of locality

Scope: performance as a *design-phase* decision — back-of-the-envelope sketches across the four
resources, ranking work by the slowest resource after compensating for frequency, the control-plane
and data-plane split, batching, and giving the CPU predictable work. Then the locality cluster:
smallest scope, no aliases, place-of-check next to place-of-use, centralized state manipulation, and
function shape. Then the 0.17-specific mechanics — build modes, the disabled loop vectorizer,
`@Vector`, explicit options and `@prefetch`, cache lines — and finally **how to measure**, since
rules throughout this standard ask for a profile, and this is the chapter that says how to take one.

This chapter does not own data layout: struct-of-arrays and `MultiArrayList` are ZS-DATA-22,
handles-versus-pointers is ZS-DATA-21, and passing large aggregates as `*const T` is ZS-DATA-18. It
does not own I/O batching (ZS-CONC-41), assertion cost budgeting (ZS-ASSERT-16), the optimize-mode
table (ZS-ASSERT-02), `@branchHint` (ZS-ERR-28), or `inline fn` (ZS-COMPTIME-03). It cites them.

**Read ZS-PERF-21 first if you are tempted to apply this chapter to code that is not hot.** Roughly
half of these rules are about correctness and readability and apply everywhere; the other half
require a measurement before you are allowed to invoke them.

## Contents

- **Part 1 — Performance is decided in the design phase**
  - ZS-PERF-01 [M] Decide the performance-relevant shape of a design before implementing it
  - ZS-PERF-02 [M] Sketch a hot-path change's cost across the four resources, and write it down
  - ZS-PERF-03 [M] Rank the resources by cost *times frequency*, and optimize the top of that list
  - ZS-PERF-04 [S] Say whether a function is control plane or data plane, and budget it
  - ZS-PERF-05 [M] Amortize every expensive acquisition on a hot path over a bounded batch
  - ZS-PERF-06 [S] Give the CPU one long lane; do not make it change lanes per item
  - ZS-PERF-07 [M] Be explicit; never depend on an optimization the compiler is not obliged to make
  - ZS-PERF-08 [S] Hand a hot loop a profile names its data as slices and integers, not as a receiver
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
  - ZS-PERF-17 [M] Spell out the options that decide behavior; never inherit their defaults
  - ZS-PERF-18 [S] Align independently written concurrent fields to `std.atomic.cache_line`
- **Part 4 — How to measure**
  - ZS-PERF-19 [M] Warm up, repeat, and defend the benchmarked expression from dead-code elimination
  - ZS-PERF-20 [M] Add a `bench` step pinned to `.fast` and not installed by default
- **Part 5 — The counterweight**
  - ZS-PERF-21 [M] Apply the always-on rules everywhere; require a number before invoking the rest

---

## Part 1 — Performance is decided in the design phase

### ZS-PERF-01 [M] Decide the performance-relevant shape of a design before implementing it

Before writing a subsystem, state — in the design note, the module doc comment, or the PR
description — what its dominant cost is and what shape of work it does: how many round trips, how
many passes over the data, how much it allocates, how much it copies. Choosing the shape is the
1000x decision; the constant factors you can profile later are the 2x decisions. Work with the grain
of the machine: sequential access, contiguous memory, predictable branches, one syscall per batch.

**Why:** a profiler tells you which line of the committed design is slowest, not that a different
design does not need that line. And once callers depend on a per-item API, moving to a batch API
breaks every call site, so the batch shape is cheapest before the first caller exists.

**Check:** a PR that introduces a new module, a new public API, or a new inner loop names its
dominant cost somewhere a reviewer can read. A PR that has no such statement and adds a per-item
public entry point on a path that will be called in bulk is the specific thing to push back on.

```zig
//! Compaction merges two sorted levels into one.
//!
//! Dominant cost: disk bandwidth. One sequential read of each input level, one sequential
//! write of the output level, no random access, no read amplification beyond 2x. Memory is
//! two 64 KiB streaming buffers, allocated once at startup (ZS-MEM-15).
//!
//! Rejected: an in-memory merge of whole levels. It is simpler and ~1.3x faster per byte,
//! but its memory is O(level size), which removes the static-allocation bound.
// fragment
```

### ZS-PERF-02 [M] Sketch a hot-path change's cost across the four resources, and write it down

Before a change lands on a hot path, sketch its cost against the four resources — **network, disk,
memory, CPU** — and their two characteristics — **bandwidth** and **latency**. Put the sketch in the
commit message or in a comment above the function. Sketches are cheap and being roughly right lands
you within 90% of the achievable maximum.

Order-of-magnitude anchors for server hardware. These are correct to within roughly 10x; the
*ratios* are the point, not the digits.

| Resource | Bandwidth | Latency |
|---|---|---|
| Network, same rack | 1–10 GiB/s | ~100 us round trip |
| Network, cross region | window-limited | 50–150 ms round trip |
| Disk, NVMe | 1–7 GiB/s | ~100 us read; ~1 ms `fsync` |
| Memory | 10–50 GiB/s | ~1 ns L1 hit; ~100 ns miss to DRAM |
| CPU | 1–4 instructions/cycle | ~0.3 ns per cycle; ~5 ns branch mispredict |

A hot path is code with a stated throughput or latency requirement, or code executed per request,
per record, per packet, or per block — a database, a storage engine, a consensus layer, a codec, a
network service, an embedded control loop — and a change to one without a sketch is not reviewable.
Anywhere else, a change that adds work *inside* an existing loop — an allocation, a syscall, a lock,
a hash, a `format` call — states in one line why that is acceptable at the loop's trip count, and a
change that adds work outside every loop needs nothing.

**Why:** without the sketch, "is this fast enough?" is opinion and review degenerates into taste;
with it, a reviewer checks arithmetic. It also catches an optimization aimed at a resource that was
never the bottleneck: a hand-vectorized parser in front of a 1 ms `fsync` per record buys nothing.

**Check:** new work inside a loop body in the diff. If the loop's bound is unbounded or
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
    for (block) |byte| sum += byte;
    return sum;
}
```

### ZS-PERF-03 [M] Rank the resources by cost *times frequency*, and optimize the top of that list

Optimize for the slowest resource first — network, then disk, then memory, then CPU — **after**
multiplying each by how often it is used. A faster resource touched many more times can dominate a
slower one.

**Why:** frequency is the term people drop. One 1 ms `fsync` ten times a second is 10 ms/s of the
budget; one 100 ns DRAM miss ten million times a second is 1000 ms/s — *the* bottleneck, and
invisible to anyone who ranked "memory is faster than disk" and stopped there.

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
second and worth a layout change (ZS-DATA-22); the checksum is noise.
```

### ZS-PERF-04 [S] Say whether a function is control plane or data plane, and budget it

The **control plane** runs once per batch, per connection, per epoch — it may assert liberally,
including O(N) checks. The **data plane** runs once per item and gets O(1) assertions only. Say
which one a function is in, in its doc comment, when it is not obvious from the name. TigerBeetle
runs 2–3x the two-assertions-per-function floor in its control plane and gates the O(N) checks
behind a verify flag in its data plane; the budgeting rule itself is ZS-ASSERT-16.

**Why:** batching creates the control plane: an O(N) check of a batch of N items costs O(1) *per
item*, so it becomes affordable exactly because of the batch. Without the split every assertion is
priced per item, and the only options are to delete assertions or to pay for them on every item.

**Check:** a function whose plane is not obvious from its name and whose doc comment does not say
which. An O(N) assert reachable from a per-item function is ZS-ASSERT-16's finding: it moves up to
the batch boundary or behind the verify flag.

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

### ZS-PERF-05 [M] Amortize every expensive acquisition on a hot path over a bounded batch

One syscall, one lock acquisition, one allocation, one flush, one round trip **per batch** — never
per item. The batch has a named `_max` constant and the code asserts it (ZS-ASSERT-19). The bound is
not optional: an unbounded batch converts a throughput win into an unbounded-latency and
unbounded-memory bug.

The I/O half of this rule — draining an event queue instead of reacting per event, `writeVecAll`
instead of a write per record — is ZS-CONC-41; do not duplicate it. This rule covers the non-I/O
half: locks, allocations, and per-item work inside a lock.

A hot path is ZS-PERF-02's. Anywhere else, batch whatever crosses a process boundary per item — a
syscall, a lock, an allocation — and leave pure in-memory per-item work alone until a profile names
it.

**Why:** each has a fixed cost that dwarfs the per-item work: a syscall's mode switch costs hundreds
of nanoseconds, an uncontended lock tens, a contended one a scheduler round trip, a `realloc` a copy
of everything. Batching divides that cost by the batch size.

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
straight. The memory-layout version of the same argument — do not drag 8 unused bytes into cache per
element — lives in ZS-DATA-22 (`MultiArrayList`).

**Why:** an invariant branch still costs a predictor slot and blocks the loop from being widened; an
unpredictable one costs a pipeline flush of around 15–20 cycles, a 4x slowdown on a 5-cycle loop
body. Splitting the loop by condition gives each resulting loop a perfectly predicted branch.

**Check:** any `if` inside a loop whose condition does not depend on the loop variable. It is almost
always a mistake.

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
compiler optimization as a bonus, never as a load-bearing assumption. Loop-invariant code motion
through a pointer is not guaranteed either: the compiler must prove the loop body cannot write
through the pointer before it may cache a field in a register, and a `*Self` parameter frequently
defeats that proof.

**Why:** LLVM's optimizations are best-effort — 0.17 builds with loop vectorization off
(ZS-PERF-15), and every budget that assumed it regressed silently. A hand-written hoist costs one
line, documents the invariant, and shows a reviewer the redundant work.

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

        var sum: u32 = 0; // A row checksum is defined modulo 2^32 (ZS-DATA-08).
        for (grid.cells[start..][0..width]) |cell| sum +%= cell;
        return sum;
    }
};
```

### ZS-PERF-08 [S] Hand a hot loop a profile names its data as slices and integers, not as a receiver

Extract the kernel into a stand-alone function whose parameters are the exact slices and scalars it
reads. The wrapper method stays, and does the field access once. Without a profile, hoist the field
into a local above the loop instead (ZS-PERF-07). This does not contradict ZS-NAME-13: receivers
stay correct everywhere else, and a codebase does not delete them wholesale on the strength of this
rule. A kernel whose bounds are two integers of one type is exempt from ZS-API-04's options struct,
because a struct would reintroduce the aggregate load the extraction removes; document the order
instead.

**Why:** aliasing. Through a `*Journal`, a store to `journal.sectors[i]` may in principle alias
`journal.sector_count`, so every iteration must reload the count; passed by value, the count cannot
alias anything, and a human reader can spot redundant computation more easily too.

**Check:** this rule is only invocable with a profile. In review, the finding is the *reverse*
direction: a PR that converts methods to free functions across a module without a benchmark in the
commit message is over-applying it. And a kernel that still takes a pointer to a struct the loop
writes through has not made the aliasing argument at all.

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
    for (bytes[0..length]) |byte| sum += byte;
    return sum;
}
```

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

**Why:** each name in scope is one more way to write a wrong line that still type-checks, like
`matches` incremented where `previous` belonged. A smaller scope makes the wrong name a compile
error, and a one-block live range lets the register allocator keep the value in a register.

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
field. ZS-PERF-07's hoist is no exception: hoisting is legal precisely when the loop cannot mutate
the hoisted fact, and the hoisted `const` dies at the end of the loop. A pointer into a container is
the same mistake with a worse failure, and ZS-MEM-12 owns it: hold the index.

**Why:** two copies of one fact are two things to update, and one will eventually be missed — the
plain form of cache invalidation.

**Check:** every local that copies a field — is the field written between the copy and the last use
of the local? A pointer-typed local into a container is the ZS-MEM-12 check.

```zig
// fragment — BAD: `count` is a second copy of `queue.count`, stale after `push`
const count = queue.count;
queue.push(item);
assert(count < queue.capacity); // checks the count from before the push
```

### ZS-PERF-11 [M] Calculate and check a value next to where it is used — avoid POCPOU

Do not introduce a variable before it is needed, and do not leave a check far from the use it
protects. The gap between the place of check and the place of use is a **POCPOU** bug waiting to
happen — place-of-check to place-of-use, the spatial cousin of the temporal TOCTOU.

The BAD example hides a second bug: `header.offset + header.length` can overflow `u32` before the
comparison, so the check can pass on input that should be rejected. In `debug`/`safe` that panics;
in `fast` it wraps and the slice goes out of bounds. Distance concealed it — see ZS-DATA-10 for
`std.math.add`.

**Why:** nothing in the type system connects a check at line 10 to the slice it guards at line 60;
only proximity does, and in between someone re-slices `buffer` or adds a `continue` that skips the
check. Adjacent, they are verified by reading two consecutive lines, not the whole function.

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

### ZS-PERF-12 [S] Centralize state manipulation: helpers compute the change, the parent applies it

Let the parent function hold the state in locals or in one receiver, and let helpers *return* what
should change rather than applying it. Keep leaf functions pure. TigerStyle pairs this with
"centralize control flow" (ZS-ERR-24, push `if`s up and `for`s down). The single apply site is the
one place to bracket with `assertInvariants` (ZS-ASSERT-14) and to make transactional with
`errdefer`; pure leaves let you compute all the deltas first and apply them in one pass, which is
what makes batching (ZS-PERF-05) possible.

**Why:** if every leaf may mutate, the states reachable at any point are the product of every leaf's
behavior, and no single function can assert the invariant. With one apply site there is one place to
assert it and one place to read when it breaks, and the pure leaves are directly testable.

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
        if (delta < 0) return value - @abs(delta);
        return value + @abs(delta);
    }
};
```

### ZS-PERF-13 [S] Shape functions like an inverted hourglass: narrow in, narrow out, wide inside

Few parameters, a simple return type, and a lot of meaty logic between the braces. If a function is
mostly signature, it is in the wrong place: nine parameters around three lines of body is the
hourglass the right way up, and a sign the caller is doing the work. This is TigerStyle's rule of
thumb for *where* to cut a function that exceeds the 70-line limit (ZS-ERR-29): not every split is
equal, and the good ones produce inverted hourglasses.

**Why:** a wide signature exports internal state to every call site, so changing it changes them
all, and each extra return dimension propagates up the call chain (ZS-DATA-27). A signature wider
than its body is relocation, not abstraction.

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

    const kind: @FieldType(Frame, "kind") = switch (bytes[0]) {
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

## Part 3 — Zig 0.17 mechanics

### ZS-PERF-14 [M] Measure in the mode you ship, and never quote a `debug` number

Benchmarks build at `fast` or at the mode you actually ship; a number from a `debug` build is not
evidence of anything. Know what each mode costs before you invoke one in an argument. For
`x86_64-linux`, `debug` also uses the self-hosted x86_64 backend, which trades machine-code quality
for compile speed. The mode table is ZS-ASSERT-02, and the argument for shipping `safe` ZS-ASSERT-04
— read them before choosing `fast` for a shipped artifact, because in `fast` every
`std.debug.assert` becomes a licence for the optimizer rather than a check (ZS-ASSERT-02).

**Why:** `debug` applies no optimization at all, and the gap between `debug` and `fast` on a tight
loop is routinely 10–50x. That swamps every effect this chapter discusses, so a "2x speedup" from a
`debug` run is noise.

**Check:** any performance claim in a commit message or comment must name the optimize mode. A
`bench` step that inherits `-Doptimize` instead of pinning its own mode is the structural version of
the same bug — see ZS-PERF-20.

```zig
// fragment
const builtin = @import("builtin");

// A benchmark that refuses to produce a meaningless number.
comptime {
    if (builtin.optimize == .debug) @compileError("build benchmarks with -Doptimize=fast");
}
```

### ZS-PERF-15 [M] Do not rely on auto-vectorization in 0.17 — the loop vectorizer is disabled

Zig 0.17 builds with LLVM loop vectorization disabled, to work around an LLVM miscompilation that
corrupted the compiler itself. The fix is not in LLVM 22, which 0.17 uses, and the release notes
keep the workaround until the move to LLVM 23 — so this is not an inconvenience to wait out. If a
loop must use SIMD, write the vectors yourself (ZS-PERF-16). A performance budget taken on a
toolchain that vectorized does not transfer.

**Why:** the loss is real and specific to the *automatic* path. At `fast` on `aarch64`, a scalar
`u32` sum loop is unrolled but every load and add stays a 32-bit scalar, while the same file's
explicit `@Vector(8, u32)` loop gets eight lanes per iteration from the same optimizer.

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

`suggestVectorLength` returns `?comptime_int` and consults the actual target CPU features. It picks
a register width — 512 bits for AVX-512, 256 for AVX2 or SVE, 128 for SSE or NEON, `null` for a
target with no vector unit — and divides by `@bitSizeOf(T)`, so `suggestVectorLength(u32)` is 16
lanes on AVX-512 and 4 on NEON. Two 0.17 constraints to know: indexing a `@Vector` with a runtime
value, to read or to store, is a compile error (`vector index not comptime known`), and *in-memory*
coercion between arrays and vectors is forbidden — but the by-value coercion
`values[i..][0..lanes].*` used in the example is fine and is the idiom.

**Why:** a width from the target keeps the kernel portable: it cross-compiles correctly instead of
hard-coding a width that degrades to scalar emulation elsewhere. Hand-written vectors are also the
only SIMD available in 0.17 (ZS-PERF-15).

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
        accumulator +%= chunk; // Modulo 2^32, as `@reduce(.Add)` is (ZS-DATA-08).
    }

    var total = @reduce(.Add, accumulator);
    // The scalar tail, modulo 2^32 like the lanes.
    while (index < values.len) : (index += 1) total +%= values[index];
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

### ZS-PERF-17 [M] Spell out the options that decide behavior; never inherit their defaults

Pass explicitly every field of an options struct whose defaults decide what the machine does, rather
than inheriting a library default:
`@prefetch(ptr, .{ .cache = .data, .rw = .read, .locality = 3 })`, not `@prefetch(ptr, .{})`, and
`@export`'s linkage and visibility (ZS-INTEROP-03). A default that only spares typing, such as
`std.testing.tmpDir(.{})`, is not one of these. `std.lang.PrefetchOptions` defaults to
`.rw = .read, .locality = 3, .cache = .data` — three independent knobs (`Rw`, `u2`, `Cache`), and
nothing pins them. `.locality = 0` means "stream it, drop it after one touch" and `.locality = 3`
means "keep it, we will come back". The builtin lowers to a real instruction on aarch64: the
example's loop emits `prfm pldl1keep`.

**Why:** call sites do not get re-reviewed when a library default moves, so an inherited default is
a latent bug waiting for the library to change. The explicit form is also the only self-documenting
one: `.{}` hides whether the data is streamed once or kept, a difference in real cache behavior.

**Check:** `rg -n '@prefetch\([^,]+, \.\{\}\)' -g '*.zig'` finds a prefetch that inherits every
option; each hit is the finding. A partial options literal, and an options literal elsewhere that
leaves a field deciding codegen, linkage, or memory behavior to its default, are read: every such
field is spelled out, or it is a finding — and the prefetch distance has a comment saying why that
stride.

```zig
// verified
fn sumPrefetched(values: []const u64) u64 {
    const stride = 8; // ~1 cache line ahead at 8 bytes/element on a 64-byte line.
    var sum: u64 = 0;
    for (values, 0..) |v, i| {
        if (i + stride < values.len) {
            @prefetch(&values[i + stride], .{ .cache = .data, .rw = .read, .locality = 3 });
        }
        sum += v;
    }
    return sum;
}
```

### ZS-PERF-18 [S] Align independently written concurrent fields to `std.atomic.cache_line`

When two threads write two different fields of the same struct, give each its own cache line with
`align(std.atomic.cache_line)`. Do not do this to fields that are read together on one thread — that
wastes cache: the example's struct is at least two cache lines, so applying this reflexively to a
hot read-only struct makes every scan touch more lines. `std.atomic.cache_line` is a `comptime_int`
computed per target CPU (`cacheLineForCpu`) and is 128 on several targets, so write it rather than a
literal `64`.

**Why:** false sharing. Coherence works in cache lines, not fields, so two counters in one line make
every write by one thread invalidate the other thread's copy, and a structure that looks uncontended
behaves like a contended lock that gets slower as cores are added.

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

## Part 4 — How to measure

Rules across this standard ask for a profile or a benchmark. This is how to take one in 0.17.

### ZS-PERF-19 [M] Warm up, repeat, and defend the benchmarked expression from dead-code elimination

A benchmark runs the work once to warm caches and the branch predictor, then repeats it a known
number of times, then divides. Feed every result to `std.mem.doNotOptimizeAway` or the optimizer
will delete the code you are timing. `std.mem.doNotOptimizeAway` (std/mem.zig) launders the value
through inline assembly so the computation must happen. Dividing by the iteration count converts a
wall-clock number into the per-operation number the ZS-PERF-02 sketch is written in, which is the
only form comparable across machines.

A mean over N iterations hides the tail. If the requirement is a latency bound rather than a
throughput number, record the per-iteration durations and report a high percentile — a p99 that is
50x the mean is the normal case for anything that allocates or does I/O, and it is usually the
number that matters.

**Why:** at `fast` a discarded pure result is dead code and LLVM removes it — the classic "1000x
speedup" that is really an empty loop. And the first iteration pays a cold i-cache, d-cache and TLB
and an untrained branch predictor, which on a short benchmark can be most of the time it reports.

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

### ZS-PERF-20 [M] Add a `bench` step pinned to `.fast` and not installed by default

Add a `bench` step whose module hard-codes `.optimize = .fast` rather than inheriting `-Doptimize`,
and wire it up with `addRunArtifact` only — never `installArtifact` — so a bare `zig build` does not
pay for it.

The benchmark's own `main` follows ZS-PERF-14, ZS-PERF-19 and ZS-CONC-33, and prints per-iteration
cost so the number can be compared with the ZS-PERF-02 sketch, as the second example shows.

**Why:** an inherited `-Doptimize` makes `zig build bench` silently measure a `debug` build
(ZS-PERF-14); an installed artifact puts the benchmark on the critical path of every `zig build` and
CI smoke test (ZS-BUILD-08). Pinned, the numbers stay comparable.

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

```zig
// fragment — prints e.g. "sum: 3.495ms total, 3.495us per iteration"
const builtin = @import("builtin");
const std = @import("std");
const Io = std.Io;
const assert = std.debug.assert;
pub fn main(init: std.process.Init) !void {
    const io = init.io;
    comptime assert(builtin.optimize == .fast);

    var out_buffer: [stdout_buffer_max]u8 = undefined;
    var out_writer = Io.File.stdout().writerStreaming(io, &out_buffer); // ZS-CONC-05
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
    try out.flush(); // ZS-CONC-04: buffered output prints nothing without this.
}
```

## Part 5 — The counterweight

### ZS-PERF-21 [M] Apply the always-on rules everywhere; require a number before invoking the rest

Half of this chapter is about correctness and legibility and costs nothing to follow. The other half
trades readability for speed and may only be invoked with a measurement, in the shipped optimize
mode, recorded where a reviewer can see it. Do not use this chapter as licence to micro-optimize.
Safety outranks performance in this standard's ordering (SKILL.md §3): where a performance rule here
conflicts with an assertion, a bound, or a safety check, the safety rule wins and the performance
rule needs a measurement to overturn it — not the reverse.

| Rule | When it applies |
|---|---|
| ZS-PERF-01 design shape, ZS-PERF-02 sketch, ZS-PERF-03 frequency | Design phase. Always — the cost is minutes. |
| ZS-PERF-09 – ZS-PERF-13 (the whole locality cluster) | **All code, always.** These are readability and correctness rules that happen to also help the register allocator. Never require a measurement. |
| ZS-PERF-07 be explicit, ZS-PERF-14 measure in the shipped mode, ZS-PERF-17 explicit options, ZS-PERF-19 – ZS-PERF-20 how to measure, ZS-CONC-33's clock choice | All code. Following them costs nothing and not following them produces false numbers. |
| ZS-PERF-04 plane split, ZS-PERF-05 batching, ZS-PERF-15 no auto-vectorization | Any code with a stated throughput or latency requirement. Batching in particular is a design decision, so it is cheap now and expensive later. |
| ZS-PERF-06 branch hoisting, ZS-PERF-08 primitive-argument kernels, ZS-PERF-16 explicit SIMD, `@branchHint` (ZS-ERR-28), adding a `@prefetch` at all (ZS-PERF-17), ZS-PERF-18 cache-line alignment, `inline fn` (ZS-COMPTIME-03) | **Hot paths a profile names, only.** Each one costs readability. A diff that applies them without a profile in the commit message is over-applying this chapter, and that is a review finding in its own right. |

**Why:** shape is decided up front and cheaply; constants are decided later and with evidence
(ZS-PERF-01). A sketch costs five minutes and is reversible, so it is never premature; a
hand-unrolled SIMD kernel costs readability permanently and is premature until it is on a profile.

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
