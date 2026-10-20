# RS-PERF — Performance

Rust's promise is that you do not pay for what you do not use, and that you can
have the fast version without giving up safety. Delivering on that requires
discipline about two things: *measuring before optimizing*, and *not being
gratuitously slow in the first place*. The rules below split accordingly — the
first group is about evidence, the rest are defaults that cost nothing to
follow.
## Contents

- **Measure first**
  - RS-PERF-01 [M] Do not optimize without a profile
  - RS-PERF-02 [M] Optimize the algorithm before the constant factor
  - RS-PERF-03 [M] Establish a baseline and report the delta
  - RS-PERF-04 [S] Optimize for the realistic input distribution
  - RS-PERF-05 [M] Measure in release mode with the profile you ship

- **Allocation**
  - RS-PERF-06 [M] Pre-size collections when the size is known
  - RS-PERF-07 [S] Know when `collect()` can pre-size and when it cannot
  - RS-PERF-08 [M] Hoist allocations out of loops
  - RS-PERF-09 [M] Avoid intermediate collections in pipelines
  - RS-PERF-10 [M] Prefer slicing to building new `String`s
  - RS-PERF-12 [M] Write into a reused buffer instead of `format!` in a hot loop
  - RS-PERF-13 [M] Do not `to_string()` something you only compare or search
  - RS-PERF-14 [S] Prefer `Box<str>`/`Box<[T]>`/`Arc<[T]>` for finished data
  - RS-PERF-15 [S] Reach for `SmallVec`/`ArrayVec` only on profiler evidence
  - RS-PERF-16 [S] Use an arena for arena-shaped workloads

- **Data structures and layout**
  - RS-PERF-17 [M] Pick the collection for the access pattern
  - RS-PERF-18 [S] Swap SipHash for a faster hasher only when keys are trusted
  - RS-PERF-20 [S] Prefer struct-of-arrays when you iterate one field over many elements
  - RS-PERF-21 [M] Keep hot structs small and box the rare large variant
  - RS-PERF-22 [M] Watch enum size — it is the largest variant plus a discriminant
  - RS-PERF-24 [S] Escalate bounds-check removal in order, `unsafe` last
  - RS-PERF-25 [M] Choose the right sort: unstable, by-key, cached-key, or select-nth
  - RS-PERF-26 [S] Binary-search a sorted `Vec` for build-once, query-many data

- **I/O and syscalls**
  - RS-PERF-27 [M] Always buffer
  - RS-PERF-28 [M] Lock stdout once and hold the lock
  - RS-PERF-29 [M] Flush explicitly before exiting, and check the result
  - RS-PERF-30 [M] Read in large chunks, never byte-at-a-time
  - RS-PERF-31 [S] Treat memory maps as a per-file runtime choice, not a default
  - RS-PERF-32 [M] Work on `&[u8]` and validate UTF-8 only where required
  - RS-PERF-33 [S] Batch syscalls

- **Codegen and the compiler**
  - RS-PERF-34 [M] Use `#[inline]` for small cross-crate non-generic functions only
  - RS-PERF-36 [S] Keep the generic wrapper thin and put the work in a non-generic inner fn
  - RS-PERF-37 [S] Do not assume static dispatch beats dynamic
  - RS-PERF-38 [M] Hoist loop invariants the compiler cannot
  - RS-PERF-39 [S] Avoid `Rc`/`Arc` clone traffic in hot loops
  - RS-PERF-40 [M] Make overflow behaviour explicit on untrusted or computed sizes
  - RS-PERF-41 [M] Choose integer widths deliberately and convert with `try_from`
  - RS-PERF-42 [M!] Treat SIMD as a last resort with a scalar fallback and a differential test

- **Benchmarking**
  - RS-PERF-43 [M] Benchmark with `criterion` or `divan`, not `Instant` in a loop
  - RS-PERF-44 [M] Keep benchmarks in `benches/` with fixed inputs, built in CI
  - RS-PERF-45 [M] Wrap inputs and results in `black_box`
  - RS-PERF-46 [M] Benchmark realistic sizes
  - RS-PERF-47 [S] Report throughput rather than latency for data-processing code
  - RS-PERF-48 [M] Pin CI benchmark comparisons to one machine class, or distrust them
  - RS-PERF-49 [S] Track binary size and compile time alongside runtime
  - RS-PERF-50 [S] Record every optimization attempt, including the failures
- Decided by tools

---

## Measure first

### RS-PERF-01 [M] Do not optimize without a profile

Do not optimize without a profile. `perf`, `samply`, `cargo flamegraph`, and Instruments all take
minutes to set up and routinely show that the hot spot is somewhere nobody guessed.

**Why:** intuition about hot spots is reliably wrong, because the expensive thing is usually a
syscall, an allocation, or a cache miss rather than the arithmetic you were looking at. Optimizing
without a profile spends real complexity on code that was not the problem.

**Check:** for each optimization in the diff, name the profile that identified it. No profile means
the change is speculative.

```rust
// verified
/// The fast path exists because a profile pointed here, and it says so.
#[must_use]
pub fn first_byte(haystack: &[u8], needle: u8) -> Option<usize> {
    // Profiled: this loop was 60% of the scan, so it stays byte-oriented.
    haystack.iter().position(|&byte| byte == needle)
}
```

### RS-PERF-02 [M] Optimize the algorithm before the constant factor

Optimize the algorithm before the constant factor. Replacing an accidental O(n²) with a `HashMap`
beats every micro-optimization in this file combined, and it is usually less code.

**Why:** constant factors buy percentages; complexity classes buy orders of magnitude, and they are
the only thing that changes what inputs are feasible at all. The algorithmic fix is also usually
simpler, because the quadratic version got that way accidentally.

**Check:** for the hot function, state its complexity in terms of input size. A nested loop over the
same collection is the usual finding.

```rust
// verified
use std::collections::HashSet;

/// A `HashSet` turns an accidental O(n²) membership loop into O(n).
#[must_use]
pub fn duplicates(values: &[u32]) -> Vec<u32> {
    let mut seen = HashSet::new();
    values
        .iter()
        .filter(|&&value| !seen.insert(value))
        .copied()
        .collect()
}
```

### RS-PERF-03 [M] Establish a baseline and report the delta

Establish a baseline number before the change and report the delta after. "Feels faster" is not a
result; "3.4× on the 1 GB corpus, unchanged on small inputs" is.

**Why:** without a baseline you cannot distinguish an improvement from noise, and you cannot tell
whether the complexity you just added bought anything. The delta is also what a reviewer needs to
judge whether the trade was worth it.

**Check:** does the commit message or PR contain before and after numbers with the input described?

### RS-PERF-04 [S] Optimize for the realistic input distribution

Optimize for the realistic input distribution, not the benchmark you happen to have. A search tool
is dominated by files that do not match; a parser by inputs that are valid. Make the common case
fast and the rare case correct.

**Why:** optimizing the wrong distribution can make the real workload slower — a fast path for
matches adds a branch to the non-matching case that dominates. The distribution is a design input,
not a detail.

**Check:** describe the input distribution the benchmark uses and compare it to production. A
benchmark where every input matches is measuring the rare case.

### RS-PERF-05 [M] Measure in release mode with the profile you ship

Measure in release mode with the profile you ship. Debug-build timings are meaningless — bounds
checks, no inlining, and overflow checks make them differ by an order of magnitude.

**Why:** debug builds disable the optimizations the design depends on, so relative costs are
completely different. A debug measurement can rank two implementations in the opposite order from
release.

**Check:** was the measurement taken with `--release` and with the same `[profile.release]` settings
that ship (`RS-BUILD-48`)?

## Allocation

### RS-PERF-06 [M] Pre-size collections when the size is known

Pre-size collections when the size is known: `Vec::with_capacity(n)`, `String::with_capacity(n)`,
`HashMap::with_capacity(n)`. Growth reallocates and copies; each doubling is a memcpy of everything
so far.

**Why:** growth is amortized O(1) but the constant is a full copy, and for a large collection those
copies dominate. When the final size is already known, the reallocation is pure waste.

**Check:** grep for `Vec::new()` followed by a loop with a known bound. Each is a missing
`with_capacity`.

```rust
// verified
/// The final size is known, so the growth reallocation never happens.
#[must_use]
pub fn widen(values: &[u16]) -> Vec<u32> {
    let mut out = Vec::with_capacity(values.len());
    out.extend(values.iter().map(|&value| u32::from(value)));
    out
}
```

### RS-PERF-07 [S] Know when `collect()` can pre-size and when it cannot

`collect()` uses the iterator's `size_hint`, so it pre-sizes correctly for slices, ranges, and `map`
over them — but not after `filter`, `flat_map`, or `chars`. Where the count is known independently,
size it yourself (`RS-FUNC-22`).

**Why:** knowing which adapters preserve an exact `size_hint` is what lets you use `collect` freely
without wondering about allocations. After a `filter` the hint is a range, so `collect` allocates
for the lower bound and grows.

**Check:** for a hot `collect` after `filter`, is the result count knowable? If so, `with_capacity`
plus `extend` avoids the growth.

```rust
// verified
/// After `filter` the size hint is a range, so the count is supplied explicitly.
#[must_use]
pub fn evens(values: &[u32], expected: usize) -> Vec<u32> {
    let mut out = Vec::with_capacity(expected);
    out.extend(values.iter().copied().filter(|value| value % 2 == 0));
    out
}
```

### RS-PERF-08 [M] Hoist allocations out of loops

Do not allocate inside a loop when the allocation can be hoisted. This is the highest-frequency
performance defect in otherwise good Rust.

**Why:** an allocation is a synchronized call into the allocator plus, eventually, a free. Doing it
per iteration converts a linear pass into one dominated by allocator traffic, and it is usually
removable by moving one binding above the loop.

**Check:** look for `Vec::new`, `String::new`, `to_vec`, `to_string`, and `format!` inside loop
bodies.

```rust
// verified
/// The buffer is hoisted, so the loop allocates nothing after the first pass.
#[must_use]
pub fn render_all(rows: &[Vec<u8>]) -> usize {
    let mut scratch = Vec::new();
    let mut total = 0;
    for row in rows {
        scratch.clear();
        scratch.extend_from_slice(row);
        total += scratch.len();
    }
    total
}
```

### RS-PERF-09 [M] Avoid intermediate collections in pipelines

Avoid intermediate collections in pipelines. Each `.collect::<Vec<_>>()` in the middle of a chain is
an allocation plus a full materialization the laziness would have avoided.

**Why:** iterators are lazy precisely so that a chain of adapters is one pass with no storage.
Collecting in the middle forces the whole intermediate to exist, which costs both the allocation and
the cache pressure.

**Check:** grep for `.collect::<Vec<_>>()` followed by `.iter()` or `.into_iter()`. Each pair is a
round trip that can be deleted.

```rust
// verified
/// One lazy chain, no intermediate `Vec` materialized in the middle.
#[must_use]
pub fn longest_word(text: &str) -> Option<&str> {
    text.lines()
        .flat_map(str::split_whitespace)
        .max_by_key(|word| word.len())
}
```

### RS-PERF-10 [M] Prefer slicing to building new `String`s

Prefer `&str`/`&[u8]` slicing to building new `String`s. `trim`, `strip_prefix`, `split_once`, and
`find` all return borrows.

**Why:** these operations are all sub-slicing, which is pointer arithmetic and costs nothing.
Converting to an owned `String` adds an allocation and a copy for a value that is usually read once
and dropped.

**Check:** grep for `to_string()` and `String::from` on the result of a string operation. Most are
avoidable.

```rust
// verified
/// Slicing is pointer arithmetic; building a `String` would allocate for nothing.
#[must_use]
pub fn key_of(line: &str) -> Option<&str> {
    line.split_once('=').map(|(key, _value)| key.trim())
}
```

### RS-PERF-12 [M] Write into a reused buffer instead of `format!` in a hot loop

`format!` allocates. In a hot loop, `write!` into a reused `String` (via `fmt::Write`) or a reused
`Vec<u8>` (via `io::Write`), and reach for `push_str`/`push` where no formatting is needed. For a
bare integer, `format_into` with a reused `NumBuffer` (`core::fmt` since 1.98, `std::fmt` since
1.99) skips the formatting machinery and replaces `itoa`.

**Why:** `format!` is `String::new` plus formatting plus a return by value, so it allocates every
call. `write!` into an existing buffer does the same formatting with no allocation.

**Check:** grep for `format!` inside loops. Each is an allocation that `write!` would avoid.

```rust
// verified
use std::fmt::NumBuffer;

/// One reused `String` and one reused `NumBuffer` instead of `format!` per iteration.
#[must_use]
pub fn join_ids(ids: &[u32]) -> String {
    let mut out = String::with_capacity(ids.len() * 4);
    let mut digits = NumBuffer::new();
    for (index, id) in ids.iter().enumerate() {
        if index > 0 {
            out.push(',');
        }
        out.push_str(id.format_into(&mut digits));
    }
    out
}
```

### RS-PERF-13 [M] Do not `to_string()` something you only compare or search

`to_string()` on something that is already a `&str` you only compare or search is a wasted
allocation (`RS-OWN-16`).

**Why:** comparison, searching, and hashing all work on `&str`, so the owned copy is created and
dropped without ever being needed. It is one of the most common needless allocations in Rust code.

**Check:** for each `to_string()`, find where the owned value is stored or returned. If it is only
read locally, delete the conversion.

```rust
// verified
/// Comparison needs no owned copy at all.
#[must_use]
pub fn count_equal(values: &[String], needle: &str) -> usize {
    values.iter().filter(|value| *value == needle).count()
}
```

### RS-PERF-14 [S] Prefer `Box<str>`/`Box<[T]>`/`Arc<[T]>` for finished data

Prefer `Box<str>`/`Box<[T]>`/`Arc<[T]>` for finished data: one less word per value and no spare
capacity.

**Why:** `String` and `Vec` carry a capacity field and usually over-allocate, which is the right
trade while growing and pure overhead afterwards. For a million small values the difference in
footprint is substantial.

**Check:** for each long-lived collection field that is never mutated after construction, is it
still a `Vec`/`String`?

```rust
// verified
/// Finished data: no spare capacity, one word smaller per value.
#[derive(Debug, Clone)]
pub struct Interned {
    names: Box<[Box<str>]>,
}

impl Interned {
    #[must_use]
    pub fn new(names: Vec<String>) -> Self {
        Self {
            names: names.into_iter().map(String::into_boxed_str).collect(),
        }
    }
}
```

### RS-PERF-15 [S] Reach for `SmallVec`/`ArrayVec` only on profiler evidence

Consider `SmallVec`/`ArrayVec`/`SmallString` when profiling shows many short-lived small collections
— but only then. The complexity and the extra dependency need evidence.

**Why:** inline storage avoids the allocation but enlarges every value, including the ones that
spill, and it complicates the types. It is a real win in the measured case and a pessimization
otherwise.

**Check:** is there a profile showing allocator time dominated by small, short-lived collections?
Without one, the dependency is not earning its place (`RS-BUILD-21`).

### RS-PERF-16 [S] Use an arena for arena-shaped workloads

For arena-shaped workloads (a parser producing a tree, a graph built once and read many times), an
arena (`bumpalo`, or a `Vec` plus index newtypes) turns thousands of allocations into one and
improves locality (`RS-OWN-27`).

**Why:** when everything dies at the same time, individual allocation and freeing is entirely wasted
bookkeeping. An arena replaces it with a pointer bump and one free, and the resulting contiguity
helps every traversal.

**Check:** does the structure have a single collective lifetime? If nothing is freed individually,
the per-node allocation is unnecessary.

```rust
// verified
/// An arena: one allocation for the whole tree, and indices instead of pointers.
#[derive(Debug, Default)]
pub struct Arena {
    nodes: Vec<u32>,
}

impl Arena {
    pub fn alloc(&mut self, value: u32) -> usize {
        self.nodes.push(value);
        self.nodes.len() - 1
    }

    #[must_use]
    pub fn get(&self, index: usize) -> Option<u32> {
        self.nodes.get(index).copied()
    }
}
```

## Data structures and layout

### RS-PERF-17 [M] Pick the collection for the access pattern

Pick the collection for the access pattern: `Vec` for iteration and indexed access, `VecDeque` for
queues, `HashMap` for lookup, `BTreeMap` for ordered iteration and range queries,
`HashSet`/`BTreeSet` for membership. Linear scan of a small `Vec` beats a `HashMap` below roughly a
dozen elements.

**Why:** asymptotics only decide it for large n; below that, contiguity and the absence of hashing
win. Reaching for `HashMap` reflexively for a five-element lookup is slower and uses more memory.

**Check:** for each collection, name the dominant operation. A `HashMap` that is mostly iterated
wants to be a `Vec`.

```rust
// verified
use std::collections::BTreeMap;

/// `BTreeMap` where ordered iteration is the dominant operation.
#[must_use]
pub fn sorted_counts(words: &[&str]) -> BTreeMap<String, usize> {
    let mut counts = BTreeMap::new();
    for word in words {
        *counts.entry((*word).to_owned()).or_insert(0) += 1;
    }
    counts
}
```

### RS-PERF-18 [S] Swap SipHash for a faster hasher only when keys are trusted

`std`'s `HashMap` uses SipHash for DoS resistance. When keys are trusted and hashing is hot, swap in
`rustc-hash`/`FxHashMap` or `ahash` — and document the trade, because it is a security-relevant
decision.

**Why:** the default is chosen so that attacker-controlled keys cannot force collisions and turn a
map into a linked list. Replacing it is a real speedup and a real reduction in robustness, so it
needs to be a recorded decision rather than an unnoticed default.

**Check:** for each non-default hasher, can any key come from outside the process? If so, the swap
is a vulnerability.

### RS-PERF-20 [S] Prefer struct-of-arrays when you iterate one field over many elements

Prefer struct-of-arrays over array-of-structs when you iterate one field over many elements. Cache
lines carry data you actually use.

**Why:** a cache line is 64 bytes regardless of how much of it you read. Iterating one 4-byte field
of a 64-byte struct wastes fifteen sixteenths of every line fetched, and the fix is purely a layout
change.

**Check:** for hot loops touching one field of a large struct, would separate arrays let the loop
read contiguously?

```rust
// verified
/// Struct-of-arrays: iterating one field touches only the cache lines it needs.
#[derive(Debug, Default)]
pub struct Particles {
    x: Vec<f32>,
    y: Vec<f32>,
    alive: Vec<bool>,
}

impl Particles {
    /// Returns `None` for an empty set rather than dividing by zero.
    #[must_use]
    pub fn centre_x(&self) -> Option<f64> {
        let count = u32::try_from(self.x.len()).ok()?;
        let total: f64 = self.x.iter().map(|&value| f64::from(value)).sum();
        (count > 0).then(|| total / f64::from(count))
    }
}
```

### RS-PERF-21 [M] Keep hot structs small and box the rare large variant

Keep hot structs small. A struct that no longer fits in a cache line, or that pushes an enum's size
up for every variant, costs on every access — box the rare large variant instead (`RS-ERR-21`).

**Why:** size is paid on every move, copy, and cache fill, whereas the boxed indirection is paid
only when the rare variant is actually used. Trading a pointer chase in the uncommon case for a
smaller value everywhere is almost always right.

**Check:** `size_of` the hot types. Anything over a cache line wants a look at its largest field.

```rust
// verified
/// The rare large variant is boxed, so the common path stays pointer-sized.
#[derive(Debug)]
pub struct Diagnostics {
    notes: Vec<String>,
    source: String,
}

#[derive(Debug)]
pub enum Outcome {
    Accepted,
    Rejected(Box<Diagnostics>),
}

const _: () = assert!(size_of::<Outcome>() <= 16);
```

### RS-PERF-22 [M] Watch enum size — it is the largest variant plus a discriminant

Enum size is the largest variant plus a discriminant. Check with `size_of` in a test if it matters;
a `Result<(), BigError>` returned from a hot function moves `BigError`-many bytes on every success.

**Why:** the success path pays for the error path's size on every call, which is exactly backwards —
errors are the rare case. Boxing the large variant makes the common return cheap.

**Check:** add a `const` assertion on `size_of` for hot `Result` and enum types (`RS-UNSAFE-34`), so
growth fails the build.

```rust
// verified
/// The enum's size is pinned by a test, so growth fails the build.
#[derive(Debug, Clone, Copy)]
pub enum Token {
    Eof,
    Number(u32),
    Punct(char),
}

const _: () = assert!(size_of::<Token>() == 8);
```

### RS-PERF-24 [S] Escalate bounds-check removal in order, `unsafe` last

Where bounds checks genuinely dominate and the profile proves it, reach for slice patterns,
`as_chunks`, `iter().zip()`, or `get_unchecked` inside a narrowly scoped `unsafe` with a
`// SAFETY:` proof — in that order. At a constant width use `as_chunks::<N>()` rather than
`chunks_exact(N)`: it yields `&[[T; N]]`, so the width is carried by the type and the pattern needs
no `_ =>` arm (`RS-API-39`). `as_array` (a slice of exactly `N`) and `array_windows` (overlapping
windows) carry the width the same way.

**Why:** the safe forms give the optimizer the same proof the `unsafe` would assert, at zero
soundness cost. `get_unchecked` converts a panic into UB, so it waits until the safe forms have
been tried and measured.

**Check:** if `get_unchecked` appears, was `as_chunks` or `zip` tried first, and is there a
benchmark showing the difference? Clippy's `chunks_exact_to_as_chunks` flags a `chunks_exact` with
a literal width.

```rust
// verified
/// `as_chunks` yields `&[[u32; 2]]`, so the pair is proven by the type and needs no fallback arm.
#[must_use]
pub fn sum_pairs(values: &[u32]) -> u64 {
    let (pairs, _remainder) = values.as_chunks::<2>();
    pairs
        .iter()
        .map(|[low, high]| u64::from(*low) + u64::from(*high))
        .sum()
}
```

### RS-PERF-25 [M] Choose the right sort: unstable, by-key, cached-key, or select-nth

Sorting: `sort_unstable` unless stability is required (it is faster and allocation-free),
`sort_unstable_by_key` for projections, `sort_by_cached_key` when the key is expensive to compute,
`select_nth_unstable` when you need only the top k.

**Why:** the stable sort allocates scratch space and does more work to preserve an order most
callers do not depend on. `sort_by_cached_key` exists because a naive key function is called O(n log
n) times rather than n.

**Check:** for each `sort`, is stability actually required? For each `sort_by_key`, is the key
cheap?

```rust
// verified
/// `sort_unstable_by_key` is faster and allocation-free where stability is not required.
pub fn sort_by_len(items: &mut [String]) {
    items.sort_unstable_by_key(String::len);
}
```

### RS-PERF-26 [S] Binary-search a sorted `Vec` for build-once, query-many data

Binary search a sorted `Vec` rather than maintaining a `BTreeMap` when the data is built once and
queried many times: better locality, less memory, and `partition_point` reads well.

**Why:** a `BTreeMap` pays for incremental insertion you are not doing. A sorted `Vec` is
contiguous, so each probe touches fewer cache lines, and it has no per-node overhead.

**Check:** does the map change after construction? If not, sorting once and binary-searching is
usually faster and smaller.

```rust
// verified
/// Built once, queried many: a sorted slice beats a tree for locality.
#[must_use]
pub fn contains(sorted: &[u32], needle: u32) -> bool {
    sorted.binary_search(&needle).is_ok()
}
```

## I/O and syscalls

### RS-PERF-27 [M] Always buffer

Always buffer. `BufReader`/`BufWriter` around files, sockets, and pipes; an unbuffered `Write` in a
loop is one syscall per call and is the most common reason a Rust CLI is slower than its C
equivalent.

**Why:** a syscall costs microseconds against nanoseconds for a memcpy into a buffer. Unbuffered
line-at-a-time I/O makes the kernel the bottleneck for work that never needed to enter it.

**Check:** grep for `File::create`/`File::open` whose handle is written or read directly in a loop.

```rust
// verified
use std::io::{self, BufWriter, Write};

/// Buffered: one syscall per block instead of one per line.
///
/// # Errors
/// Propagates the first write or flush error.
pub fn emit(sink: impl Write, lines: &[String]) -> io::Result<()> {
    let mut out = BufWriter::new(sink);
    for line in lines {
        writeln!(out, "{line}")?;
    }
    out.flush()
}
```

### RS-PERF-28 [M] Lock stdout once and hold the lock

Lock stdout once and hold the lock: `let mut out = io::stdout().lock();` then write to `out`. Every
`println!` locks, formats, and (on line-buffered terminals) flushes.

**Why:** `println!` re-acquires the lock per call, and on a terminal it flushes per line — so a loop
printing a million lines performs a million lock acquisitions and a million syscalls
(`RS-CLI-21`).

**Check:** grep for `println!` inside loops in anything performance-relevant.

```rust
// verified
use std::io::{self, Write};

/// The lock is acquired once for the whole run.
///
/// # Errors
/// Propagates the first write or flush error.
pub fn write_lines(lines: &[String]) -> io::Result<()> {
    let stdout = io::stdout();
    let mut handle = stdout.lock();
    for line in lines {
        writeln!(handle, "{line}")?;
    }
    handle.flush()
}
```

### RS-PERF-29 [M] Flush explicitly before exiting, and check the result

Flush explicitly before exiting, and check the result. `BufWriter` flushes on drop but swallows the
error (`RS-OWN-40`).

**Why:** buffering means the last write is still in memory when `main` returns, and `Drop` cannot
report a failure. A full disk or a closed pipe silently truncates the output — the failure
introduced by the optimization in RS-PERF-27.

**Check:** is there an explicit `flush()` whose `Result` is handled before exit?

### RS-PERF-30 [M] Read in large chunks, never byte-at-a-time

Prefer reading in large chunks over byte-at-a-time. `read_until`, `read_to_end`, and
`fill_buf`/`consume` give you the bytes without a syscall per byte.

**Why:** per-byte reads multiply the per-call overhead by the input size, even with buffering,
because each call still goes through the `Read` machinery. `fill_buf` hands you the whole buffered
slice with no copy at all.

**Check:** grep for `read(&mut [0u8; 1])` and per-byte loops.

```rust
// verified
use std::io::{self, BufRead};

/// Reads by line into a reused buffer rather than a syscall per byte.
///
/// # Errors
/// Propagates any read error.
pub fn count_lines(mut source: impl BufRead) -> io::Result<usize> {
    let mut buf = Vec::new();
    let mut lines = 0;
    loop {
        buf.clear();
        if source.read_until(b'\n', &mut buf)? == 0 {
            break;
        }
        lines += 1;
    }
    Ok(lines)
}
```

### RS-PERF-31 [S] Treat memory maps as a per-file runtime choice, not a default

Memory maps are not automatically faster. They win for large files read repeatedly and lose for
small files, for pipes, and for network filesystems — and they introduce SIGBUS risk if the file is
truncated concurrently. ripgrep chooses per-file at runtime; do the same or default to buffered
reads.

**Why:** mapping has a fixed setup cost in page-table work and takes page faults on access, so for
small files it is slower than a single read. The SIGBUS risk also converts a concurrent truncation
from an error into a process death.

**Check:** is `mmap` used unconditionally? If so, measure it against buffered reads on the
small-file case.

### RS-PERF-32 [M] Work on `&[u8]` and validate UTF-8 only where required

Work on `&[u8]` and validate UTF-8 only where required. `memchr`, `memmem`, and `bstr` operate on
bytes at SIMD speed; forcing every input through `str::from_utf8` costs a pass over the data and
rejects legitimate files.

**Why:** validation is a full scan you often do not need — searching for a byte pattern does not
require knowing the text is valid. It also makes the tool fail on files that are perfectly
processable (`RS-CLI-13`).

**Check:** is UTF-8 validated on a path that only searches or splits? Each is an avoidable pass.

```rust
// verified
/// Bytes throughout; UTF-8 is validated only where text is actually required.
#[must_use]
pub fn first_field(line: &[u8]) -> &[u8] {
    line.split(|&byte| byte == b'\t').next().unwrap_or(line)
}
```

### RS-PERF-33 [S] Batch syscalls

Batch syscalls: `write_vectored` for scattered buffers, one `stat` instead of `exists()` followed by
`metadata()`, and directory traversal via a crate (`ignore`, `walkdir`) that already minimizes them.

**Why:** syscalls dominate metadata-heavy workloads, and the redundant ones are easy to introduce —
`exists()` then `metadata()` is two stats for one question. Traversal crates have already done this
optimization carefully.

**Check:** grep for `exists()` immediately followed by an open or a `metadata` call on the same
path.

## Codegen and the compiler

### RS-PERF-34 [M] Use `#[inline]` for small cross-crate non-generic functions only

`#[inline]` is for small functions that must inline *across crate boundaries* — non-generic
functions in a library. Generic functions are already available for inlining. Applying it everywhere
bloats the binary and slows compilation without helping.

**Why:** without LTO, a non-generic function's body is not visible to other crates, so `#[inline]`
is what makes it available. Generic functions are instantiated in the caller's crate and already
visible, so the attribute adds nothing.

**Check:** grep for `#[inline]` on generic functions and on private ones. Both are usually noise.

### RS-PERF-36 [S] Keep the generic wrapper thin and put the work in a non-generic inner fn

Monomorphization is a size/speed trade. A large generic function instantiated for twenty types is
twenty copies; extract the type-independent body into a non-generic inner function and keep the
generic wrapper thin.

**Why:** the generic part is usually only the conversion at the boundary — `AsRef<Path>` to `&Path`.
The body does not depend on the type parameter, so duplicating it per instantiation buys nothing and
costs compile time and binary size.

**Check:** for each generic function with a large body, does the body actually use the type
parameter?

```rust
// verified
use std::path::Path;

/// The generic wrapper is one line; the body is monomorphized once.
///
/// # Errors
/// Propagates any read error.
pub fn read_config(path: impl AsRef<Path>) -> std::io::Result<String> {
    fn inner(path: &Path) -> std::io::Result<String> {
        std::fs::read_to_string(path)
    }
    inner(path.as_ref())
}
```

### RS-PERF-37 [S] Do not assume static dispatch beats dynamic

Static dispatch is not automatically faster than dynamic: a vtable call is a predictable indirect
branch, while twenty monomorphized copies can evict the i-cache. Measure before converting `dyn` to
generics for speed (`RS-TRAIT-16`).

**Why:** modern branch predictors handle a monomorphic indirect call well, so the vtable cost is
often near zero. The code-size cost of monomorphization, by contrast, is paid in cache misses across
the whole program.

**Check:** was a `dyn` to generic conversion justified by a benchmark, or by the belief that static
is faster?

### RS-PERF-38 [M] Hoist loop invariants the compiler cannot

Hoist invariants out of loops explicitly when the compiler cannot: a regex compiled once outside the
loop rather than per iteration, a `OnceLock` for an expensive global, a length computed once.

**Why:** LLVM can only hoist what it can prove has no side effects and does not change. `Regex::new`
does both allocation and compilation, so it is never hoisted automatically — and compiling a regex
per iteration is one of the largest avoidable costs in practice.

**Check:** grep for `Regex::new`, file opens, and other construction inside loops.

```rust
// verified
use std::sync::OnceLock;

/// The expensive value is built once, outside the loop, not per iteration.
fn separators() -> &'static [char] {
    static SEPARATORS: OnceLock<Vec<char>> = OnceLock::new();
    SEPARATORS.get_or_init(|| vec![',', ';', '\t'])
}

#[must_use]
pub fn field_count(lines: &[String]) -> usize {
    let seps = separators();
    lines.iter().map(|line| line.split(seps).count()).sum()
}
```

### RS-PERF-39 [S] Avoid `Rc`/`Arc` clone traffic in hot loops

Avoid `Rc`/`Arc` clone traffic in hot loops. Atomic increments are cheap but not free, and
contention on a shared refcount across threads is measurable.

**Why:** an `Arc` clone is an atomic RMW, which serializes the cache line holding the count. With
several threads cloning the same `Arc`, that line ping-pongs between cores and can dominate.

**Check:** for hot paths, could the value be borrowed instead of cloned? A clone per iteration
usually can be hoisted (`RS-OWN-13`).

### RS-PERF-40 [M] Make overflow behaviour explicit on untrusted or computed sizes

Integer overflow panics in debug and wraps in release. On any path handling untrusted or computed
sizes, use `checked_*`, `saturating_*`, or `wrapping_*` explicitly — or `strict_*` (1.91), which
panics in both profiles, where overflow is a bug rather than an input — so the behaviour is the
same in both profiles (`RS-ERR-41`).

**Why:** the profile-dependent default means the debug build and the shipped build disagree about a
security-relevant behaviour, and testing happens in the one that panics. An explicit method makes
the intent the same everywhere.

**Check:** grep for arithmetic on lengths, offsets, and parsed numbers. Each on an untrusted path
needs an explicit variant.

```rust
// verified
/// Explicit on untrusted sizes, so debug and release agree.
#[must_use]
pub fn offset(base: usize, delta: usize) -> Option<usize> {
    base.checked_add(delta)
}
```

### RS-PERF-41 [M] Choose integer widths deliberately and convert with `try_from`

Prefer `u32`/`u64` deliberately over `usize` for values that are serialized or bounded, and `usize`
for lengths and indices. Casting with `as` truncates silently — use `try_from` on any conversion
that could lose data. A same-width sign change loses no bits and is not a `try_from` case: spell it
`cast_signed()` or `cast_unsigned()` (1.87) rather than `as`.

**Why:** `usize` varies by platform, so a serialized `usize` has a different width on a 32-bit
target — a portability bug that only appears there. `as` performs the truncation without any
diagnostic, which is why it is the wrong default for narrowing.

**Check:** grep for `as u32`, `as usize`, `as i32` on values that could exceed the target range.
Each wants `try_from`.

```rust
// verified
/// `try_from` on any narrowing conversion; `as` would truncate silently.
///
/// # Errors
/// Returns the conversion error when `len` exceeds `u32::MAX`.
pub fn header_len(len: usize) -> Result<u32, std::num::TryFromIntError> {
    u32::try_from(len)
}
```

### RS-PERF-42 [M!] Treat SIMD as a last resort with a scalar fallback and a differential test

SIMD is a last resort with a scalar fallback and a correctness test comparing the two. Before
hand-writing it, check whether `memchr`, `bstr`, or `regex-automata` already does it for you — they
almost certainly do it better.

**Why:** SIMD code is hard to read, hard to test, and target-specific, so it needs runtime feature
detection and a fallback anyway. The libraries have already absorbed that complexity and have been
fuzzed against their scalar versions for years.

**Check:** is the scalar version still present and compared against in a test? Without it the SIMD
path has no oracle.

*Relaxed form:* in a single-target internal tool you may skip the runtime feature detection and
compile for the known target. The scalar reference implementation and the test that compares against
it are not relaxable — they are what makes the fast path reviewable.

## Benchmarking

### RS-PERF-43 [M] Benchmark with `criterion` or `divan`, not `Instant` in a loop

Benchmark with `criterion` or `divan`, not `std::time::Instant` in a loop. They handle warmup,
outlier detection, and statistical comparison — without which small differences are
indistinguishable from noise.

**Why:** a hand-rolled timing loop measures the first iterations cold, includes scheduler noise, and
reports a single number with no confidence interval. Most reported "10% improvements" from such
loops are noise.

**Check:** does the benchmark report a distribution or a single number? A single number is not a
measurement.

### RS-PERF-44 [M] Keep benchmarks in `benches/` with fixed inputs, built in CI

Keep benchmarks in `benches/` with fixed, reproducible inputs so results are comparable across
commits, and build them in CI even if you do not time them there (`RS-MOD-33`).

**Why:** comparability across commits requires the input to be identical, which a generated or
downloaded corpus is not. Building them in CI keeps them compiling, since they are excluded from a
default `cargo test` (`RS-TEST-32`).

**Check:** are the benchmark inputs checked in or seeded (`RS-TEST-10`), and does CI compile the
benchmarks?

### RS-PERF-45 [M] Wrap inputs and results in `black_box`

Use `std::hint::black_box` around inputs and results so the optimizer cannot delete the work being
measured. A benchmark that got 1000× faster deleted itself.

**Why:** the compiler can see the result is unused and the input is constant, so it is entitled to
remove the entire computation. The resulting number measures an empty loop, and it looks like a
triumph.

**Check:** any benchmark reporting sub-nanosecond times for real work has been optimized away.

```rust
// verified
use std::hint::black_box;

/// `black_box` stops the optimizer deleting the work being measured.
#[must_use]
pub fn bench_once(input: &[u8]) -> u32 {
    let input = black_box(input);
    black_box(
        input
            .iter()
            .fold(0_u32, |acc, &b| acc.wrapping_add(u32::from(b))),
    )
}
```

### RS-PERF-46 [M] Benchmark realistic sizes

Benchmark realistic sizes. Microbenchmarks on ten-element inputs measure function-call overhead; the
algorithmic difference only appears at scale.

**Why:** at n=10 everything fits in L1 and every algorithm looks the same, so the benchmark ranks
implementations by constant factor rather than by the property you are optimizing. The crossover
point is often well above the size people benchmark.

**Check:** does the benchmark sweep several sizes? A single small size cannot show an asymptotic
difference.

### RS-PERF-47 [S] Report throughput rather than latency for data-processing code

Report throughput (`Throughput::Bytes`) rather than latency for data-processing code, so results are
comparable across input sizes.

**Why:** raw times are only comparable at identical input size, so changing the corpus invalidates
the history. Bytes per second normalizes that and makes the number meaningful on its own.

**Check:** are the benchmark results expressed in a unit that survives an input change?

### RS-PERF-48 [M] Pin CI benchmark comparisons to one machine class, or distrust them

Pin CI benchmark comparisons to the same machine class, or do not trust them. Cross-runner
comparisons are noise, and treating them as signal produces a permanent stream of false regressions.

**Why:** shared CI runners vary in CPU model, frequency scaling, and neighbours, which swamps the
differences worth detecting. A regression alert that is usually wrong gets ignored, including when
it is right.

**Check:** does the benchmark job pin the runner type, and does it compare against a baseline from
the same class?

### RS-PERF-49 [S] Track binary size and compile time alongside runtime

Track binary size and compile time alongside runtime if you ship a CLI. Users notice a 40 MB binary
and a five-minute build.

**Why:** these are user-visible performance too, and they degrade invisibly since nothing measures
them. Monomorphization and dependency growth both trade them against runtime, so they need to be on
the same dashboard.

**Check:** is release binary size recorded per release? A number nobody tracks only grows.

### RS-PERF-50 [S] Record every optimization attempt, including the failures

Record the result of every optimization attempt, including the ones that did not work, in the commit
message or a comment. The next person will otherwise try the same thing.

**Why:** a failed optimization is real information — it says the bottleneck is elsewhere — and it is
completely lost unless written down. Without the record, the same experiment gets repeated every
couple of years.

**Check:** does the hot module have a comment or commit history explaining what was tried and
rejected?

## Decided by tools

A tool settles these on its own; the shipped configuration enables each at the level shown.

| Tool | Lint | Level | Forbids |
|---|---|---|---|
| clippy | `map_entry` | warn | `contains_key` then `insert` — one lookup with `entry()` |
| clippy | `needless_range_loop` | warn | a range loop that only indexes — iterate, and the bounds checks go |
| clippy | `inline_always` | warn | `#[inline(always)]` — `#[expect]` it, citing the benchmark that justifies it |
