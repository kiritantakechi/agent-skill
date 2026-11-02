# Performance: Measuring, Complexity, Allocation, and What the Build Costs

Scope: deciding what to make faster and how to know it worked — the profiling tools 3.15 ships, the
costs that are structural rather than local, and what the free-threaded build charges you. Blocking
the event loop is the async chapter; lock contention is the concurrency chapter.

Two sources are merged here: the **CPython 3.15 documentation**, including PEP 799's new `profiling`
package, and the **published benchmark data for the free-threaded build** — cited with its
measurement date, because the numbers move and a standard that quotes one without a date goes stale
silently. Ruff's `PERF` and `C4` families decide the mechanical half.

Unless a block shows its own imports, it assumes nothing beyond the standard library.

## Contents

- **Deciding what to change**
  - PS-PERF-01 [M] Measure before changing anything, and measure the thing users wait for
  - PS-PERF-02 [M] Profile with the `profiling` package
  - PS-PERF-03 [M] Fix the complexity before fixing the constant
  - PS-PERF-04 [M] State the cost in the units the caller cares about
  - PS-PERF-05 [S] Write the back-of-envelope before the benchmark
- **Structural costs**
  - PS-PERF-06 [M] Never build a string by repeated concatenation
  - PS-PERF-07 [M] Use a set or dict for membership, never a list
  - PS-PERF-08 [M] Batch I/O rather than looping over single operations
  - PS-PERF-09 [M] Stream a large sequence rather than materialising it
  - PS-PERF-10 [S] Hoist the invariant out of the loop
- **Allocation and layout**
  - PS-PERF-11 [S] Reuse a buffer rather than allocating per iteration
- **What the build costs**
  - PS-PERF-12 [M] Budget for the free-threaded build's single-threaded overhead
  - PS-PERF-13 [M] Know that the JIT is unavailable on the free-threaded build
  - PS-PERF-14 [M] Expect higher memory on the free-threaded build
  - PS-PERF-15 [M!] Give shared read-mostly data to threads, not to processes
- **Discipline**
  - PS-PERF-16 [M] Never optimise without leaving the measurement behind
  - PS-PERF-17 [M] Keep the readable version when the fast one is not faster
- Decided by tools

---

## Deciding what to change

### PS-PERF-01 [M] Measure before changing anything, and measure the thing users wait for

A profile of the whole operation, not a microbenchmark of the function you suspect.

**Why:** intuition about Python performance is wrong more often than it is right, and being wrong
costs readability for no gain. Measuring the whole operation catches the common case, where the
function you suspected is 2% of the time and optimising it is pure loss.

**Check:** every performance change in review must arrive with a before and after number for the
same workload. Without one it is a readability change with a performance claim attached.

### PS-PERF-02 [M] Profile with the `profiling` package

New in 3.15: `profiling.tracing` for deterministic call counts, `profiling.sampling` for wall-clock
truth. `cProfile` remains as an alias of `profiling.tracing`, so prefer the name that says what it
does; `profile` is deprecated for removal in 3.17. `profiling.sampling`, called Tachyon, can attach
to an already-running process by PID.

**Why:** a sampler does not instrument, so it does not distort what it measures, while
deterministic tracing inflates call-heavy code — the code you are most likely profiling. So "where
does the time go" and "how many times is this called" need genuinely different tools.

**Check:** `rg -n 'cProfile|import profile' src/` — a `profile` hit is a removal due in 3.17, and a
`cProfile` hit is the old name for `profiling.tracing`.

### PS-PERF-03 [M] Fix the complexity before fixing the constant

An `O(n²)` loop rewritten in C is still `O(n²)`.

**Why:** constant-factor work is bounded by a small multiple; complexity is unbounded in `n`. A
quadratic scan that is fine for the hundred rows in the test becomes the outage at ten thousand, and
no amount of local optimisation moves that.

**Check:** every nested loop over the same collection, and every `in` against a list inside a
loop. A review matter: the ruff rule for excessive nesting is preview, and the shipped
configuration runs stable rules only.

### PS-PERF-04 [M] State the cost in the units the caller cares about

"Linear in the number of rows", "one round trip per call", "allocates a copy of the input". This is
a docstring obligation, not a comment.

**Why:** the cost is not visible from the signature, and a caller needs it to decide whether to
hoist the call out of a loop, batch it, or cache it. A function that does a network round trip and
reads like a property getter is a latency bug in every caller until someone reads the source.

**Check:** every public function that loops, allocates proportionally to its input, or does I/O. A
docstring without a cost sentence is the finding.

### PS-PERF-05 [S] Write the back-of-envelope before the benchmark

How many items, how many bytes, how many round trips, at what rate.

**Why:** the arithmetic usually settles the question in a minute, and it tells you what the
benchmark *should* say — so a benchmark that disagrees means you have found something, rather
than confirming what you assumed. It also catches designs that cannot work before they are built.

**Check:** the design note for any performance-sensitive component should contain numbers.

## Structural costs

### PS-PERF-06 [M] Never build a string by repeated concatenation

`"".join(parts)`. Not `out += piece` in a loop. Bytes are the same: `b"".join(parts)`, or a
`bytearray` you extend and hand on with `take_bytes()`, which moves the bytes out without a copy.

**Why:** strings are immutable, so each `+=` allocates a new string and copies everything so far —
O(n²) for an n-character string. CPython sometimes rescues the simplest case in place, which is
worse than never: fast enough in the test, quadratic in production where the string is aliased.

**Check:** `rg -n '^[ \t]*\w+[ \t]*\+=[ \t]*.*["\x27]' src/` and read each hit for an
enclosing loop.
No ruff rule finds string building in a loop, so this is a grep and a review.

```python
# verified — GOOD
def render(rows: list[str]) -> str:
    # One allocation for the result, not one per row.
    return "\n".join(rows)


assert render(["a", "b"]) == "a\nb"
```

### PS-PERF-07 [M] Use a set or dict for membership, never a list

`if key in allowed_set`. Not `if key in allowed_list`.

**Why:** list membership is a linear scan; set membership is a hash lookup. Inside a loop that turns
`O(n)` into `O(n·m)`, invisibly, since the two spellings are identical — most often in a
module-level constant, where a literal list looks like the obvious thing to write.

**Check:** `rg -n 'in \[' src/` — a literal list on the right of `in` is always the finding.
The ruff rule for it is preview and therefore not enabled here.

### PS-PERF-08 [M] Batch I/O rather than looping over single operations

One query returning a thousand rows, not a thousand queries. One `writelines`, not a thousand
`write`s.

**Why:** each operation pays a fixed cost — a round trip, a syscall, a lock — that dwarfs the work.
Batching amortises it, usually by two orders of magnitude rather than a few percent. It is a design
property rather than a local one, which is why it must be decided early.

**Check:** every I/O call inside a `for`. Each is a candidate for batching, and most are.

### PS-PERF-09 [M] Stream a large sequence rather than materialising it

Yield, or return an iterator. Do not build the whole list when the caller consumes it once. The same
holds through a pool: `pool.map(fn, items, buffersize=n)` keeps at most `n` calls in flight, where a
plain `map` submits every item before the first result comes back.

**Why:** materialising costs memory proportional to the input and delays the first result until the
last one is ready. For anything large or unbounded that is the difference between working and not.
The caller can always call `list()` if they want it all; you cannot un-materialise.

**Check:** every function returning a list built by appending in a loop, whose caller iterates it
once. Ruff `C4` catches the comprehension-around-a-generator cases.

### PS-PERF-10 [S] Hoist the invariant out of the loop

The compiled regex, the attribute lookup, the config read, the `len()` of a thing that does not
change.

**Why:** Python resolves names at runtime, so `self.config.timeout` inside a loop is three
dictionary lookups per iteration. Hoisting is free to read and sometimes a large win. It is `[S]`
because doing it everywhere is noise — do it where a profile says the loop matters.

**Check:** every loop body containing an attribute chain, a `re.compile`, or a call whose arguments
do not vary.

## Allocation and layout

### PS-PERF-11 [S] Reuse a buffer rather than allocating per iteration

A `bytearray` you write into, a list you clear, a `memoryview` over a slice. When bytes must leave
the buffer, `buf.take_bytes(n)` moves the first `n` out and keeps the rest, where `bytes(buf[:n])`
copies them and `del buf[:n]` then moves the rest.

**Why:** allocation is the cost that dominates tight loops in Python, and it is invisible in the
source — `chunk = data[i:i+n]` looks free and copies. Reuse trades readability for it, which is why
this is `[S]`: do it where measured, and comment that it was measured.

**Check:** every slice inside a hot loop. `memoryview` avoids the copy where the consumer accepts
one.

```python
# verified — GOOD
def records(stream: list[bytes], size: int) -> list[bytes]:
    """Split `stream` into records, through one buffer and no copies."""
    out: list[bytes] = []
    buf = bytearray()
    for piece in stream:
        buf.extend(piece)
        while len(buf) >= size:
            out.append(buf.take_bytes(size))
    return out


assert records([b"abc", b"defg", b"h"], 4) == [b"abcd", b"efgh"]
```

## What the build costs

### PS-PERF-12 [M] Budget for the free-threaded build's single-threaded overhead

Somewhere between 5% and 30% depending on the workload, and closer to 30% for allocation-heavy code.
Budget from your own measurement, kept as a benchmark you re-run on each interpreter upgrade: these
numbers move every release.

**Why:** the documentation quotes "about 1% on macOS aarch64 to 8% on x86-64 Linux" for
pyperformance, whose daily runs have sat near 1.10x on Linux x86_64 through 2026. But refcount- and
allocation-heavy code pays much more: every reference to another thread's object takes a slow path.

**Check:** benchmark the same workload on both builds before committing to free threading. A
decision made on the doc's number rather than on yours is the finding.

### PS-PERF-13 [M] Know that the JIT is unavailable on the free-threaded build

`--enable-experimental-jit` with `--disable-gil` builds a JIT that is never used; CPython's own
configure script warns about it.

**Why:** 3.15's JIT is worth single-digit to low-double-digit percent on the default build, so the
comparison is not "free-threaded overhead versus zero" but "overhead plus foregone JIT versus
parallelism". For code that will not use more than one core, that is a straightforwardly bad trade.

**Check:** any project on the free-threaded build whose workload is single-threaded.

### PS-PERF-14 [M] Expect higher memory on the free-threaded build

PEP 779's target is 20%, and measurements sit at 1.19–1.22x.

**Why:** every interned string is immortal so it is never freed, non-GC object headers are larger,
the allocator is mimalloc rather than pymalloc, and QSBR defers frees until a collection. None of
that is a leak or tunable away; `gc.collect()` releasing what QSBR holds is the only lever.

**Check:** measure RSS on both builds before setting a memory limit.

### PS-PERF-15 [M!] Give shared read-mostly data to threads, not to processes

Where workers read a large structure and write only their own results, threads on the free-threaded
build avoid the copy entirely.

*Relaxed form:* isolation remains correct and is the right answer where the payload marshals cheaply
and the workers share nothing. `InterpreterPoolExecutor` gives it inside one process, without a
process per worker — measure both rather than assuming.

**Why:** this is the case free threading was built for: no pickling, no per-process copy of the
data, one interpreter's memory instead of N. Workers that hammer the *same mutable* objects can be
slower as threads, because per-object locking and cross-thread refcounts cost more than isolation.

**Check:** for each parallel workload, name what the workers share. Large and read-mostly favours
threads; small and copied favours processes; large and mutable needs a redesign.

## Discipline

### PS-PERF-16 [M] Never optimise without leaving the measurement behind

A benchmark that re-runs the workload, kept beside the code, and a comment naming the workload and
that benchmark. Not a date: PS-DOC-12 keeps provenance out of comments, and a benchmark answers the
question a date only places in time.

**Why:** an optimisation is a readability cost paid for a speed benefit, and the next reader can see
only the cost. Without a way to re-measure they cannot tell whether the trade still holds — and it
often does not, because the interpreter got faster or the workload changed.

**Check:** every non-obvious construct justified by speed. No benchmark to re-run is the finding.

### PS-PERF-17 [M] Keep the readable version when the fast one is not faster

If the measurement does not show a difference that matters, revert it.

**Why:** without it PS-PERF-01 has no consequences: measuring and then keeping the change anyway —
because it feels faster, or because the work is done — is how a codebase accumulates complexity
with no benefit. The readable version is the default, and only a measurement overturns it.

**Check:** every optimisation in review whose before-and-after numbers are within noise.

## Decided by tools

A tool settles these on its own; the shipped configuration enables each at the level shown.

| Tool | Lint | Level | Forbids |
|---|---|---|---|
| ruff | `PERF401` | error | a loop that only appends — a comprehension |
| ruff | `PERF402` | error | a loop that only copies — `list(…)` or `.copy()` |
| ruff | `RUF017` | error | `sum(lists, [])`, which copies everything added so far at each step — `[*sub for sub in lists]` |
