# Performance: Measurement, Allocation, Layout, I/O, and Codegen

Scope: making code fast without making it wrong — measuring first, documenting cost, allocation and
buffer reuse, collection choice and memory layout, buffered I/O and syscalls, lazy iteration,
monomorphization and `#[inline]`, integer widths and casts, SIMD, and benchmarking. What ownership
costs is the ownership chapter's; parallelism is the concurrency chapter's; build profiles are the
build chapter's.

Rust's promise is that you do not pay for what you do not use, and that you can have the fast
version without giving up safety. Delivering on that requires discipline about two things:
*measuring before optimizing*, and *not being gratuitously slow in the first place*. The rules below
split accordingly — the first group is about evidence, the rest are defaults that cost nothing to
follow.

## Contents

- **Measure first**
  - RS-PERF-01 [M] Do not optimize without a profile, and keep a change only for the delta it shows
  - RS-PERF-02 [M] Optimize the algorithm before the constant factor
  - RS-PERF-03 [S] Write the back-of-envelope before the benchmark
  - RS-PERF-04 [S] Document complexity and allocation where users would guess
  - RS-PERF-05 [S] Optimize for the realistic input distribution
  - RS-PERF-06 [M] Measure in release mode with the profile you ship

- **Allocation**
  - RS-PERF-07 [S] Know when `collect()` can pre-size and when it cannot
  - RS-PERF-08 [S] Hoist allocations out of loops, and write into a reused buffer
  - RS-PERF-09 [S] Reach for `SmallVec`/`ArrayVec` only on profiler evidence
  - RS-PERF-10 [S] Use an arena for arena-shaped workloads

- **Data structures and layout**
  - RS-PERF-11 [M] Pick the collection for the access pattern
  - RS-PERF-12 [S] Swap SipHash for a faster hasher only when keys are trusted
  - RS-PERF-13 [S] Prefer struct-of-arrays when you iterate one field over many elements
  - RS-PERF-14 [M] Keep hot structs small, and box a large field the hot path rarely reads
  - RS-PERF-15 [M] Watch enum size — it is the largest variant plus a discriminant
  - RS-PERF-16 [S] Escalate bounds-check removal in order, `unsafe` last
  - RS-PERF-17 [M] Choose the right sort: unstable, by-key, cached-key, or select-nth
  - RS-PERF-18 [S] Binary-search a sorted `Vec` for build-once, query-many data

- **I/O and syscalls**
  - RS-PERF-19 [M] Always buffer, read in large chunks, and batch syscalls
  - RS-PERF-20 [S] Treat memory maps as a per-file runtime choice, not a default
  - RS-PERF-21 [M] Work on `&[u8]` and validate UTF-8 only where required
  - RS-PERF-22 [M] Keep iterators lazy as far up the stack as you can

- **Codegen and the compiler**
  - RS-PERF-23 [M] Use `#[inline]` for small cross-crate non-generic functions only
  - RS-PERF-24 [S] Keep the generic wrapper thin and put the work in a non-generic inner fn
  - RS-PERF-25 [S] Do not assume static dispatch beats dynamic
  - RS-PERF-26 [M] Hoist loop invariants the compiler cannot
  - RS-PERF-27 [S] Avoid `Rc`/`Arc` clone traffic in hot loops
  - RS-PERF-28 [M] Write SIMD only beside a scalar fallback and a differential test

- **Benchmarking**
  - RS-PERF-29 [M] Benchmark with `criterion` or `divan`, and wrap inputs and results in `black_box`
  - RS-PERF-30 [M] Keep benchmarks in `benches/` with fixed inputs, built in CI
  - RS-PERF-31 [M] Benchmark realistic sizes
  - RS-PERF-32 [S] Report throughput rather than latency for data-processing code
  - RS-PERF-33 [M] Pin CI benchmark comparisons to one machine class, or distrust them
  - RS-PERF-34 [S] Track binary size and compile time alongside runtime
  - RS-PERF-35 [S] Record every optimization attempt, including the failures

- Decided by tools

---

## Measure first

### RS-PERF-01 [M] Do not optimize without a profile, and keep a change only for the delta it shows

Take a baseline number before the change with `perf`, `samply`, `cargo flamegraph` or Instruments,
which take minutes to set up and routinely show that the hot spot is somewhere nobody guessed, and
report the delta after. "Feels faster" is not a result; "3.4× on the 1 GB corpus, unchanged on small
inputs" is. A change whose delta is within noise is reverted.

**Why:** intuition about hot spots is reliably wrong: the expensive thing is usually a syscall, an
allocation or a cache miss, not the arithmetic you looked at. Without a profile and a baseline you
spend complexity on the wrong code and cannot tell a gain from noise.

**Check:** for each optimization in the diff, name the profile that identified it, and find the
before and after numbers, with the input described, in the commit message or PR. Neither means the
change is speculative.

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

Replacing an accidental O(n²) with a `HashMap` beats every micro-optimization in this file combined,
and it is usually less code.

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

### RS-PERF-03 [S] Write the back-of-envelope before the benchmark

How many items, how many bytes, how many syscalls or round trips, at what rate, set against what the
hardware does: a syscall costs microseconds, a cache miss around a hundred nanoseconds, an `fsync`
about a millisecond. Put the arithmetic in the design note or the commit message.

**Why:** the arithmetic usually settles the question in a minute, and it says what the benchmark
should report, so a benchmark that disagrees has found something. It also catches an optimization
aimed at a resource that was never the bottleneck, such as SIMD in front of a per-record `fsync`.

**Check:** does the design note or the change describe the expected cost in numbers before any
benchmark is quoted? Prose that says only "should be fast" is the finding.

### RS-PERF-04 [S] Document complexity and allocation where users would guess

Document complexity and allocation behaviour where users would otherwise guess: "runs in O(n log n)
and allocates once", "does not allocate if the input is already normalized". This is what makes a
library usable in a hot loop with confidence.

**Why:** without it, the careful user benchmarks your function to learn what one sentence could have
told them, and the careless user calls it in a loop. Documenting it also pins the behaviour as
something you intend to preserve.

**Check:** for each function on a plausible hot path, does the reader know whether it allocates? If
answering requires reading the body, document it.

```rust
// verified
/// Returns the unique values, in first-seen order.
///
/// Runs in O(n log n) and allocates once for the result and once for the
/// seen-set; the input is left untouched.
#[must_use]
pub fn unique(values: &[u32]) -> Vec<u32> {
    let mut seen = std::collections::BTreeSet::new();
    values
        .iter()
        .filter(|&&value| seen.insert(value))
        .copied()
        .collect()
}
```

### RS-PERF-05 [S] Optimize for the realistic input distribution

The benchmark you happen to have is not it: a search tool is dominated by files that do not match, a
parser by inputs that are valid. Make the common case fast and the rare case correct, and say which
is which: `#[cold]` on a function only the rare case calls, `std::hint::cold_path()` at the top of a
rare branch.

**Why:** optimizing the wrong distribution can make the real workload slower — a fast path for
matches adds a branch to the non-matching case that dominates. The distribution is a design input,
not a detail.

**Check:** describe the input distribution the benchmark uses and compare it to production. A
benchmark where every input matches is measuring the rare case.

### RS-PERF-06 [M] Measure in release mode with the profile you ship

Debug-build timings are meaningless — bounds checks, no inlining, and overflow checks make them
differ by an order of magnitude.

**Why:** debug builds disable the optimizations the design depends on, so relative costs are
completely different. A debug measurement can rank two implementations in the opposite order from
release.

**Check:** was the measurement taken with `--release` and with the same `[profile.release]` settings
that ship (RS-BUILD-40)?

## Allocation

### RS-PERF-07 [S] Know when `collect()` can pre-size and when it cannot

`collect()` uses the iterator's `size_hint`, so it pre-sizes correctly for slices, ranges, and `map`
over them — but not after `filter`, `flat_map`, or `chars`. Where the count is known independently
of the iterator, size the collection yourself: `Vec::with_capacity(n)` plus `extend`, and the same
for `String::with_capacity` and `HashMap::with_capacity`.

**Why:** growth is amortized O(1), but each doubling copies everything so far, and when the final
size is known that copy is pure waste. Knowing which adapters keep an exact `size_hint` is what lets
you use `collect` freely everywhere else.

**Check:** for a hot `collect` after `filter` or `flat_map`, is the result count knowable from
somewhere else? If so, `with_capacity` plus `extend` avoids the growth.

```rust
// verified
/// `flat_map` hides the length, but the total is one cheap pass away.
#[must_use]
pub fn concat(words: &[&str]) -> Vec<u8> {
    let mut out = Vec::with_capacity(words.iter().map(|word| word.len()).sum());
    out.extend(words.iter().flat_map(|word| word.bytes()));
    out
}
```

### RS-PERF-08 [S] Hoist allocations out of loops, and write into a reused buffer

Do not allocate inside a hot loop when the allocation can be hoisted. This is the highest-frequency
performance defect in otherwise good Rust.

For line input, hoist one `String` or `Vec<u8>` and `clear()` it before each `read_line` or
`read_until`: the pattern behind ripgrep and every fast line-oriented tool. `format!` allocates on
every call, so `write!` into a reused `String` (via `fmt::Write`) or `Vec<u8>` (via `io::Write`), or
`push_str` where no formatting is needed. For a bare integer, `format_into` with a reused
`NumBuffer` replaces `itoa`.

**Why:** an allocation is a synchronized call into the allocator plus, eventually, a free. Doing it
per iteration converts a linear pass into one dominated by allocator traffic, and it is usually
removable by moving one binding above the loop.

**Check:** look for `Vec::new`, `String::new`, `to_vec`, `to_string`, and `format!` inside loop
bodies on a path a profile names.

```rust
// verified
use std::io::{self, BufRead};

/// One buffer for the whole run: `clear` keeps the capacity.
///
/// # Errors
/// Propagates any read error from the underlying stream.
pub fn count_matching(mut source: impl BufRead, needle: &str) -> io::Result<usize> {
    let mut line = String::new();
    let mut matches = 0;
    loop {
        line.clear();
        if source.read_line(&mut line)? == 0 {
            break;
        }
        if line.contains(needle) {
            matches += 1;
        }
    }
    Ok(matches)
}
```

### RS-PERF-09 [S] Reach for `SmallVec`/`ArrayVec` only on profiler evidence

Consider `SmallVec`/`ArrayVec`/`SmallString` when profiling shows many short-lived small collections
— but only then. The complexity and the extra dependency need evidence.

**Why:** inline storage avoids the allocation but enlarges every value, including the ones that
spill, and it complicates the types. It is a real win in the case a profile shows and a
pessimization otherwise.

**Check:** is there a profile showing allocator time dominated by small, short-lived collections?
Without one, the dependency is not earning its place (RS-BUILD-18).

### RS-PERF-10 [S] Use an arena for arena-shaped workloads

For arena-shaped workloads (a parser producing a tree, a graph built once and read many times), an
arena (`bumpalo`, or a `Vec` plus index newtypes) turns thousands of allocations into one and
improves locality (RS-DATA-04).

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

### RS-PERF-11 [M] Pick the collection for the access pattern

`Vec` for iteration and indexed access, `VecDeque` for queues, `HashMap` for lookup, `BTreeMap` for
ordered iteration and range queries, `HashSet`/`BTreeSet` for membership. Linear scan of a small
`Vec` beats a `HashMap` below roughly a dozen elements.

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

### RS-PERF-12 [S] Swap SipHash for a faster hasher only when keys are trusted

`std`'s `HashMap` uses SipHash for DoS resistance. When keys are trusted and hashing is hot, swap in
`rustc-hash`/`FxHashMap` or `ahash` — and document the trade, because it is a security-relevant
decision.

**Why:** the default is chosen so that attacker-controlled keys cannot force collisions and turn a
map into a linked list. Replacing it is a real speedup and a real reduction in robustness, so it
needs to be a recorded decision rather than an unnoticed default.

**Check:** for each non-default hasher, can any key come from outside the process? If so, the swap
is a vulnerability.

### RS-PERF-13 [S] Prefer struct-of-arrays when you iterate one field over many elements

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

### RS-PERF-14 [M] Keep hot structs small, and box a large field the hot path rarely reads

A struct that no longer fits in a cache line costs on every access. Box the large field that only
the rare path reads; an enum's largest variant is RS-PERF-15.

**Why:** size is paid on every move, copy, and cache fill, whereas the boxed indirection is paid
only when the rare field is actually read. Trading a pointer chase in the uncommon case for a
smaller value everywhere is almost always right.

**Check:** `size_of` the hot types. Anything over a cache line wants a look at its largest field.

```rust
// verified
/// Notes are rare, so they live behind a pointer and every token stays 24 bytes.
#[derive(Debug)]
pub struct Token {
    kind: u32,
    start: u32,
    end: u32,
    notes: Option<Box<Notes>>,
}

#[derive(Debug)]
pub struct Notes {
    lines: Vec<String>,
    source: String,
}

const _: () = assert!(size_of::<Token>() <= 24);
```

### RS-PERF-15 [M] Watch enum size — it is the largest variant plus a discriminant

Enum size is the largest variant plus a discriminant. Check with `size_of` in a test if it matters;
a `Result<(), BigError>` returned from a hot function moves `BigError`-many bytes on every success.
Box the fat variant: `Parse(Box<ParseError>)`.

**Why:** the success path pays for the error path's size on every call, which is exactly backwards —
errors are the rare case. Boxing the large variant makes the common return cheap.

**Check:** add a `const` assertion on `size_of` for hot `Result` and enum types (RS-UNSAFE-14), so
growth fails the build. clippy's `large_enum_variant` and `result_large_err` catch the gross cases.

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

### RS-PERF-16 [S] Escalate bounds-check removal in order, `unsafe` last

Where bounds checks genuinely dominate and the profile proves it, reach for slice patterns,
`as_chunks`, `iter().zip()`, or `get_unchecked` inside a narrowly scoped `unsafe` with a
`// SAFETY:` proof — in that order. At a constant width use `as_chunks::<N>()` rather than
`chunks_exact(N)`: it yields `&[[T; N]]`, so the width is carried by the type and the pattern needs
no `_ =>` arm (RS-DATA-05). `as_array` (a slice of exactly `N`) and `array_windows` (overlapping
windows) carry the width the same way.

**Why:** the safe forms give the optimizer the same proof the `unsafe` would assert, at zero
soundness cost. `get_unchecked` converts a panic into UB, so it waits until the safe forms have been
tried and profiled.

**Check:** if `get_unchecked` appears, was `as_chunks` or `zip` tried first, and is there a
benchmark showing the difference? Clippy's `chunks_exact_to_as_chunks` flags a `chunks_exact` with a
literal width.

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

### RS-PERF-17 [M] Choose the right sort: unstable, by-key, cached-key, or select-nth

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

### RS-PERF-18 [S] Binary-search a sorted `Vec` for build-once, query-many data

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

### RS-PERF-19 [M] Always buffer, read in large chunks, and batch syscalls

A file, socket, pipe or standard stream read or written more than once goes through a `BufReader` or
`BufWriter`, and stdout is locked once rather than per line: `println!` locks, formats and writes on
every call, and Rust's stdout is line-buffered whether it is a terminal, a pipe or a file. Read in
large chunks, never byte-at-a-time: `read_until`, `read_to_end` and `fill_buf`/`consume` give you
the bytes without a call per byte, and `skip_until` passes over them without copying. Batch the
syscalls that remain: `write_vectored` for scattered buffers, one `stat` instead of `exists()`
followed by `metadata()`, and a traversal crate (`ignore`, `walkdir`) that already minimizes them.

**Why:** a syscall costs microseconds against nanoseconds for a memcpy into a buffer, so a million
unbuffered lines are a million `write`s, and the kernel becomes the bottleneck for work that never
needed it — the most common reason a Rust CLI is slower than its C equivalent.

**Check:** `rg -n -F 'read(&mut [0u8; 1])' -g '*.rs'` finds a one-byte read; each hit is the
finding, and so is any `File`, socket, `stdout()` or `stderr()` handle read or written directly
inside a loop, `println!` called in one, or an `exists()` followed by a `metadata` call on the same
path.

```rust
// verified
use std::io::{self, BufWriter, Write};

/// The lock is taken once and the writer is buffered, not re-locked per line.
///
/// # Errors
/// Propagates the first write or flush error.
pub fn print_all(lines: &[String]) -> io::Result<()> {
    let mut out = BufWriter::new(io::stdout().lock());
    for line in lines {
        writeln!(out, "{line}")?;
    }
    out.flush()
}
```

### RS-PERF-20 [S] Treat memory maps as a per-file runtime choice, not a default

Memory maps are not automatically faster. They win for large files read repeatedly and lose for
small files, for pipes, and for network filesystems — and they introduce SIGBUS risk if the file is
truncated concurrently. ripgrep chooses per-file at runtime; do the same or default to buffered
reads.

**Why:** mapping has a fixed setup cost in page-table work and takes page faults on access, so for
small files it is slower than a single read. The SIGBUS risk also converts a concurrent truncation
from an error into a process death.

**Check:** is `mmap` used unconditionally? If so, measure it against buffered reads on the
small-file case.

### RS-PERF-21 [M] Work on `&[u8]` and validate UTF-8 only where required

`memchr`, `memmem`, and `bstr` operate on bytes at SIMD speed; forcing every input through
`str::from_utf8` costs a pass over the data and rejects legitimate files.

**Why:** validation is a full scan you often do not need — searching for a byte pattern does not
require knowing the text is valid. It also makes the tool fail on files that are perfectly
processable (RS-CLI-11).

**Check:** is UTF-8 validated on a path that only searches or splits? Each is an avoidable pass.

```rust
// verified
/// Bytes throughout; UTF-8 is validated only where text is actually required.
#[must_use]
pub fn first_field(line: &[u8]) -> &[u8] {
    line.split(|&byte| byte == b'\t').next().unwrap_or(line)
}
```

### RS-PERF-22 [M] Keep iterators lazy as far up the stack as you can

Take `impl IntoIterator<Item = T>`, and return an iterator rather than a collection whenever the
caller may consume only part of the sequence or feed it to another adapter; RS-TRAIT-13 spells the
return type.

**Why:** materialization belongs to whoever knows how much of the sequence is needed, which is the
caller. Returning `Vec<T>` decides on their behalf that all of it is computed and all of it stored,
and feeding it to another adapter costs a second allocation.

**Check:** does the function return a collection the caller might only partially consume? Does the
caller immediately `.iter()` or `.into_iter()` it, or index only the first element?

```rust
// verified
/// Nothing is computed until the caller asks, and only as much as it asks for.
pub fn non_empty(lines: &[String]) -> impl Iterator<Item = &str> {
    lines
        .iter()
        .map(String::as_str)
        .filter(|line| !line.is_empty())
}
```

## Codegen and the compiler

### RS-PERF-23 [M] Use `#[inline]` for small cross-crate non-generic functions only

`#[inline]` is for small functions that must inline *across crate boundaries* — non-generic
functions in a library. Generic functions are already available for inlining. Applying it everywhere
bloats the binary and slows compilation without helping.

**Why:** rustc already makes the smallest non-generic functions inlinable downstream, and generic
ones are instantiated in the caller's crate. Anything larger needs `#[inline]` to cross the crate
boundary, which is the one thing the attribute is for.

**Check:** is `#[inline]` on a generic function or a private one? Both are usually noise. For the
rest, is the function non-generic, small, and hot in another crate?

### RS-PERF-24 [S] Keep the generic wrapper thin and put the work in a non-generic inner fn

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

### RS-PERF-25 [S] Do not assume static dispatch beats dynamic

Static dispatch is not automatically faster than dynamic: a vtable call is a predictable indirect
branch, while twenty monomorphized copies can evict the i-cache. Measure before converting `dyn` to
generics for speed (RS-TRAIT-11).

**Why:** modern branch predictors handle a monomorphic indirect call well, so the vtable cost is
often near zero. The code-size cost of monomorphization, by contrast, is paid in cache misses across
the whole program.

**Check:** was a `dyn` to generic conversion justified by a benchmark, or by the belief that static
is faster?

### RS-PERF-26 [M] Hoist loop invariants the compiler cannot

Hoist invariants out of loops explicitly when the compiler cannot: a regex compiled once outside the
loop rather than per iteration, a `LazyLock` for an expensive computed global, a `const` for data
known at compile time, a length computed once.

**Why:** LLVM can only hoist what it can prove has no side effects and does not change. `Regex::new`
does both allocation and compilation, so it is never hoisted automatically — and compiling a regex
per iteration is one of the largest avoidable costs in practice.

**Check:** is a `Regex::new`, a file open, or another construction inside a loop?

```rust
// verified
/// Known at compile time, so it is a `const`: nothing is built per iteration, or at all.
const SEPARATORS: [char; 3] = [',', ';', '\t'];

#[must_use]
pub fn field_count(lines: &[String]) -> usize {
    lines
        .iter()
        .map(|line| line.split(SEPARATORS).count())
        .sum()
}
```

### RS-PERF-27 [S] Avoid `Rc`/`Arc` clone traffic in hot loops

Atomic increments are cheap but not free, and contention on a shared refcount across threads is
measurable.

**Why:** an `Arc` clone is an atomic RMW, which serializes the cache line holding the count. With
several threads cloning the same `Arc`, that line ping-pongs between cores and can dominate.

**Check:** for hot paths, could the value be borrowed instead of cloned? A clone per iteration
usually can be hoisted (RS-OWN-09).

### RS-PERF-28 [M] Write SIMD only beside a scalar fallback and a differential test

Before hand-writing it, check whether `memchr`, `bstr`, or `regex-automata` already does it for you
— they almost certainly do it better. Hand-written SIMD keeps the scalar version as its reference
and a test comparing the two, and detects the CPU's features at run time wherever the binary runs on
more than one target.

**Why:** SIMD code is hard to read, hard to test, and target-specific, so it needs runtime feature
detection and a fallback anyway. The libraries have already absorbed that complexity and have been
fuzzed against their scalar versions for years.

**Check:** is the scalar version still present and compared against in a test? Without it the SIMD
path has no oracle; the comparison is RS-TEST-22's differential test.

## Benchmarking

### RS-PERF-29 [M] Benchmark with `criterion` or `divan`, and wrap inputs and results in `black_box`

Benchmark with `criterion` or `divan`, not `std::time::Instant` in a loop. They handle warmup,
outlier detection, and statistical comparison — without which small differences are
indistinguishable from noise. Use `std::hint::black_box` around inputs and results so the optimizer
cannot delete the work the benchmark times: a benchmark that got 1000× faster deleted itself.

**Why:** a hand-rolled timing loop measures the first iterations cold, includes scheduler noise, and
reports one number with no interval. And the compiler, seeing the result unused and the input
constant, may remove the whole computation, so the number measures an empty loop.

**Check:** does the benchmark report a distribution or a single number? A single number is not a
measurement, and sub-nanosecond times for real work mean it was optimized away.

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

### RS-PERF-30 [M] Keep benchmarks in `benches/` with fixed inputs, built in CI

Keep benchmarks in `benches/` with fixed inputs, checked in or generated from a seed, so results are
comparable across commits. Build them in CI even if you do not time them there.

**Why:** comparability requires the input to be identical; a benchmark that downloads a corpus or
reads the developer's home directory measures the network and the filesystem. Benchmarks are left
out of a default `cargo test`, so uncompiled they rot until the day you need one.

**Check:** are the benchmark inputs checked in or seeded (RS-TEST-09), and does CI run
`cargo build --benches`?

### RS-PERF-31 [M] Benchmark realistic sizes

Microbenchmarks on ten-element inputs measure function-call overhead; the algorithmic difference
only appears at scale.

**Why:** at n=10 everything fits in L1 and every algorithm looks the same, so the benchmark ranks
implementations by constant factor rather than by the property you are optimizing. The crossover
point is often well above the size people benchmark.

**Check:** does the benchmark sweep several sizes? A single small size cannot show an asymptotic
difference.

### RS-PERF-32 [S] Report throughput rather than latency for data-processing code

Report throughput (`Throughput::Bytes`) rather than latency for data-processing code, so results are
comparable across input sizes.

**Why:** raw times are only comparable at identical input size, so changing the corpus invalidates
the history. Bytes per second normalizes that and makes the number meaningful on its own.

**Check:** are the benchmark results expressed in a unit that survives an input change?

### RS-PERF-33 [M] Pin CI benchmark comparisons to one machine class, or distrust them

Pin CI benchmark comparisons to the same machine class, or do not trust them. Cross-runner
comparisons are noise, and treating them as signal produces a permanent stream of false regressions.

**Why:** shared CI runners vary in CPU model, frequency scaling, and neighbours, which swamps the
differences worth detecting. A regression alert that is usually wrong gets ignored, including when
it is right.

**Check:** does the benchmark job pin the runner type, and does it compare against a baseline from
the same class?

### RS-PERF-34 [S] Track binary size and compile time alongside runtime

A CLI's users notice a 40 MB binary and a five-minute build as surely as a slow run.

**Why:** these are user-visible performance too, and they degrade invisibly since nothing measures
them. Monomorphization and dependency growth both trade them against runtime, so they need to be on
the same dashboard.

**Check:** is release binary size recorded per release? A number nobody tracks only grows.

### RS-PERF-35 [S] Record every optimization attempt, including the failures

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
| clippy | `map_entry` | warn | `contains_key` then `insert` — one lookup with `entry()` — listed because one lookup with `entry()` is the rule a revision demoted to it |
| clippy | `needless_range_loop` | warn | a range loop that only indexes — iterate, and the bounds checks go — listed because an iterator in place of indices is the rule a revision demoted to it |
| clippy | `inline_always` | warn | `#[inline(always)]` — `#[expect]` it, citing the benchmark that justifies it — listed because `#[inline]` only with a benchmark (RS-PERF-23) is the rule a revision demoted to it |
| clippy | `cast_possible_truncation` | warn | an `as` cast that can drop high bits |
| clippy | `cast_sign_loss` | warn | an `as` cast from signed to unsigned |
| clippy | `cast_precision_loss` | warn | an `as` cast to a float that cannot hold every value |
