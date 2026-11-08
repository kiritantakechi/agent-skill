# Performance: Measuring, Complexity, Allocation, and What the Build Costs

Scope: deciding what to make faster and how to know it worked — the profiling tools 3.15 ships, how
a benchmark is timed, the costs that are structural rather than local, and what the free-threaded
build charges you. Blocking the event loop is the async chapter; lock contention is the concurrency
chapter.

Unless a block shows its own imports, it assumes nothing beyond the standard library.

## Contents

- **Deciding what to change**
  - PS-PERF-01 [M] Measure before changing anything, and keep the change only for the gain it shows
  - PS-PERF-02 [M] Profile with the `profiling` package
  - PS-PERF-03 [M] Fix the complexity before fixing the constant
  - PS-PERF-04 [S] State the cost in the units the caller cares about
  - PS-PERF-05 [S] Write the back-of-envelope before the benchmark
- **Structural costs**
  - PS-PERF-06 [M] Never build a sequence by repeated concatenation
  - PS-PERF-07 [M] Use a set or dict for membership, never a list
  - PS-PERF-08 [M] Batch I/O rather than looping over single operations
  - PS-PERF-09 [M] Stream a large sequence rather than materialising it
  - PS-PERF-10 [M] Read and write bytes when the data is bytes
  - PS-PERF-11 [M] Hoist the invariant out of the loop
  - PS-PERF-12 [S] Map a file into memory only to read a large one at random
- **Allocation and layout**
  - PS-PERF-13 [S] Reuse a buffer rather than allocating per iteration
  - PS-PERF-14 [S] Keep a column per field when a hot loop reads one field of many records
- **How to measure**
  - PS-PERF-15 [M] Time a benchmark with a harness that repeats it, never with one clock reading
- **What the build costs**
  - PS-PERF-16 [M] Benchmark your workload on both builds before choosing free threading
  - PS-PERF-17 [M] Never run a single-threaded workload on the free-threaded build
  - PS-PERF-18 [M] Set a memory limit from the free-threaded build's own measurement
  - PS-PERF-19 [M!] Give shared read-mostly data to threads, not to processes
- **Discipline**
  - PS-PERF-20 [M] Never optimise without leaving the measurement behind
- Decided by tools

---

## Deciding what to change

### PS-PERF-01 [M] Measure before changing anything, and keep the change only for the gain it shows

A profile of the whole operation, not a microbenchmark of the function you suspect, and a before and
after number for the same workload. If the measurement does not show a difference that matters,
revert the change: the readable version is the default, and only a measurement overturns it.

**Why:** intuition about Python performance is wrong more often than it is right, and being wrong
costs readability for no gain. The function you suspected is often 2% of the time, and a change kept
because it feels faster is how a codebase accumulates complexity with no benefit.

**Check:** every performance change in review must arrive with a before and after number for the
same workload, and a difference within noise is the finding. Without a number it is a readability
change with a performance claim attached.

### PS-PERF-02 [M] Profile with the `profiling` package

New in 3.15: `profiling.tracing` for deterministic call counts, `profiling.sampling` for wall-clock
truth. `cProfile` remains as an alias of `profiling.tracing`, so prefer the name that says what it
does; `profile` is deprecated for removal in 3.17. `profiling.sampling`, called Tachyon, can attach
to an already-running process by PID.

**Why:** a sampler does not instrument, so it does not distort what it measures, while deterministic
tracing inflates call-heavy code — the code you are most likely profiling. So "where does the time
go" and "how many times is this called" need genuinely different tools.

**Check:** `rg -n 'cProfile|import profile' src/` — a `profile` hit is a removal due in 3.17, and a
`cProfile` hit is the old name for `profiling.tracing`.

### PS-PERF-03 [M] Fix the complexity before fixing the constant

An `O(n²)` loop rewritten in C is still `O(n²)`.

**Why:** constant-factor work is bounded by a small multiple; complexity is unbounded in `n`. A
quadratic scan that is fine for the hundred rows in the test becomes the outage at ten thousand, and
no amount of local optimisation moves that.

**Check:** every nested loop over the same collection, and every `in` against a list inside a loop.
A review matter: the ruff rule for excessive nesting is preview, and the shipped configuration runs
stable rules only.

### PS-PERF-04 [S] State the cost in the units the caller cares about

"Linear in the number of rows", "one round trip per call", "allocates a copy of the input". This is
a docstring obligation, not a comment, where a caller would otherwise have to read the source to
learn it.

**Why:** the cost is not visible from the signature, and a caller needs it to decide whether to
hoist the call out of a loop, batch it, or cache it. A function that does a network round trip and
reads like a property getter is a latency bug in every caller until someone reads the source.

**Check:** every public function that loops, allocates proportionally to its input, or does I/O,
where the cost is not obvious from the name. A docstring without a cost sentence is the finding.

### PS-PERF-05 [S] Write the back-of-envelope before the benchmark

How many items, how many bytes, how many round trips, at what rate.

**Why:** the arithmetic usually settles the question in a minute, and it tells you what the
benchmark *should* say — so a benchmark that disagrees means you have found something, rather than
confirming what you assumed. It also catches designs that cannot work before they are built.

**Check:** the design note for any performance-sensitive component should contain numbers.

## Structural costs

### PS-PERF-06 [M] Never build a sequence by repeated concatenation

`"".join(parts)`. Not `out += piece` in a loop. Bytes are the same: `b"".join(parts)`, or a
`bytearray` you extend and hand on with `take_bytes()`, which moves the bytes out without a copy.
Lists too: `[*sub for sub in lists]`, not `sum(lists, [])`.

**Why:** each concatenation allocates a new sequence and copies everything so far — O(n²) for n
items. CPython sometimes rescues the simplest string case in place, which is worse than never: fast
enough in the test, quadratic in production where the string is aliased.

**Check:** `rg -n '^[ \t]*\w+[ \t]*\+=[ \t]*.*["\x27]' src/` — read each hit for an enclosing loop,
which no ruff rule sees; a string built in one is the finding. Ruff `RUF017` finds `sum(lists, [])`.

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

**Check:** `rg -n 'in \[' src/` — a literal list on the right of `in` is always the finding. The
ruff rule for it is preview and therefore not enabled here.

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

### PS-PERF-10 [M] Read and write bytes when the data is bytes

`Path.read_bytes()`, `open(path, "rb")`. Not a text mode with a made-up encoding.

**Why:** decoding binary data as text and re-encoding it does not round-trip, so a "text" read of a
file that is not text is a lossy transformation you did not intend. Any hashing, signing, or
byte-level comparison must be on the bytes.

**Check:** every `open` and `read_text` whose file may not be text. Every `hashlib` call whose input
came from a text read is the finding.

### PS-PERF-11 [M] Hoist the invariant out of the loop

The compiled regex, the attribute lookup, the config read, the `len()` of a thing that does not
change.

**Why:** Python resolves names at runtime and never hoists for you, so `self.config.timeout` inside
a loop is three dictionary lookups per iteration. Hoisting is free to read and sometimes a large
win, so it is not left to a profile.

**Check:** every loop body containing an attribute chain, a `re.compile`, or a call whose arguments
do not vary.

### PS-PERF-12 [S] Map a file into memory only to read a large one at random

A sequential pass reads through a buffered file, which prefetches for you. `mmap.mmap` earns its
setup cost when the file is too large to read whole and the access jumps about: the map is then a
bytes-like object you index and slice, with no seek and read per access.

**Why:** a map pays a page fault on the first touch of each page, and it makes a small file or a
linear scan slower than one `read`. For random access over a large file the seek-and-read loop is
the slower form, so the choice is the access pattern's, not a default.

**Check:** every `mmap.mmap` call: is the file large and its access random? A map over a file read
once from start to end is the finding, and so is a seek-and-read loop over a file too large to read
whole.

```python
# verified — GOOD
import mmap
import tempfile

with tempfile.TemporaryFile() as handle:
    handle.write(bytes(range(256)) * 4)
    handle.flush()
    with mmap.mmap(handle.fileno(), 0, access=mmap.ACCESS_READ) as view:
        assert view[256] == 0
        assert view[1023] == 255
```

## Allocation and layout

### PS-PERF-13 [S] Reuse a buffer rather than allocating per iteration

A `bytearray` you write into, a list you clear, a `memoryview` over a slice. When bytes must leave
the buffer, `buf.take_bytes(n)` moves the first `n` out and keeps the rest, where `bytes(buf[:n])`
copies them and `del buf[:n]` then moves the rest.

**Why:** allocation is the cost that dominates tight loops in Python, and it is invisible in the
source — `chunk = data[i:i+n]` looks free and copies. Reuse trades readability for it, which is why
this is `[S]`: do it where a profile says the loop matters, and say so as PS-PERF-20 asks.

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

### PS-PERF-14 [S] Keep a column per field when a hot loop reads one field of many records

A list of objects is a list of pointers, each to a separate heap allocation with its own header and
every field. A loop over one field follows a pointer per record and drags the other fields through
the cache for nothing. Keep that field in a column of its own, an `array.array` for numbers, which
packs the values unboxed and contiguous, or a plain list per field, and index the columns together.

**Why:** the cache fetches a line whatever the loop reads from it, so a loop over one field of
records fetches the others too, while a column fetches only what the loop uses. A record no longer
travels as one object, so this is `[S]`: do it where a profile says the loop matters (PS-PERF-20).

**Check:** for each hot loop that reads one attribute of every item in a large list of objects,
would a column let the loop read one contiguous buffer, and does a measurement of that loop show it?

```python
# verified — GOOD
from array import array


class Particles:
    """Particles stored by column: a loop over `x` reads only `x`."""

    def __init__(self) -> None:
        """Start with no particles."""
        self.x = array("d")
        self.alive: list[bool] = []

    def add(self, x: float, *, alive: bool) -> None:
        """Append one particle to every column."""
        self.x.append(x)
        self.alive.append(alive)

    def centre_x(self) -> float | None:
        """The mean of `x`, or `None` for no particles."""
        if not self.x:
            return None
        return sum(self.x) / len(self.x)


particles = Particles()
particles.add(1.0, alive=True)
particles.add(3.0, alive=False)
assert particles.centre_x() == 2.0
```

## How to measure

### PS-PERF-15 [M] Time a benchmark with a harness that repeats it, never with one clock reading

`timeit.repeat` or `pyperf`, not two `time.perf_counter()` readings around a single run. Build the
input outside the timed statement and pass it in through `globals` or `setup`, so the compiler
cannot fold it into a constant, and take the minimum of the repeats, not the mean.

**Why:** a single run measures a cold interpreter, a cold cache and whatever else the machine was
doing, and reports one number with no spread. A statement made of constants is folded at compile
time, and the number then times nothing.

**Check:** every benchmark that subtracts two clock readings around one call, and every timed
statement that holds its input as a literal. Either is the finding.

```python
# verified — GOOD
import timeit

data = list(range(1000))
runs = timeit.repeat("sum(data)", globals={"data": data}, number=100, repeat=5)
best = min(runs) / 100
assert best >= 0
```

## What the build costs

### PS-PERF-16 [M] Benchmark your workload on both builds before choosing free threading

The free-threaded build's single-threaded overhead is somewhere between 5% and 30% depending on the
workload, and closer to 30% for allocation-heavy code. Budget from your own measurement, kept as a
benchmark you re-run on each interpreter upgrade: these numbers move every release.

**Why:** the documentation quotes "about 1% on macOS aarch64 to 8% on x86-64 Linux" for
pyperformance, whose daily runs have sat near 1.10x on Linux x86_64 through 2026. But refcount- and
allocation-heavy code pays much more: every reference to another thread's object takes a slow path.

**Check:** benchmark the same workload on both builds before committing to free threading. A
decision made on the doc's number rather than on yours is the finding.

### PS-PERF-17 [M] Never run a single-threaded workload on the free-threaded build

The JIT is unavailable there: `--enable-experimental-jit` with `--disable-gil` builds a JIT that is
never used, and CPython's own configure script warns about it.

**Why:** 3.15's JIT is worth single-digit to low-double-digit percent on the default build, so the
comparison is not "free-threaded overhead versus zero" but "overhead plus foregone JIT versus
parallelism". For code that will not use more than one core, that is a straightforwardly bad trade.

**Check:** any project on the free-threaded build whose workload is single-threaded.

### PS-PERF-18 [M] Set a memory limit from the free-threaded build's own measurement

The free-threaded build uses more memory: PEP 779's target is 20% more, and the build sits at
1.19–1.22x.

**Why:** every interned string is immortal so it is never freed, non-GC object headers are larger,
the allocator is mimalloc rather than pymalloc, and QSBR defers frees until a collection. None of
that is a leak or tunable away; `gc.collect()` releasing what QSBR holds is the only lever.

**Check:** measure RSS on both builds before setting a memory limit.

### PS-PERF-19 [M!] Give shared read-mostly data to threads, not to processes

Where workers read a large structure and write only their own results, threads on the free-threaded
build avoid the copy entirely. Where the payload marshals cheaply and the workers share nothing,
isolation is the right answer instead: `InterpreterPoolExecutor` gives it inside one process,
without a process per worker.

*Relaxed form:* processes for shared read-mostly data too, which stay correct and cost the copy;
measure both rather than assuming.

**Why:** this is the case free threading was built for: no pickling, no per-process copy of the
data, one interpreter's memory instead of N. Workers that hammer the *same mutable* objects can be
slower as threads, because per-object locking and cross-thread refcounts cost more than isolation.

**Check:** for each parallel workload, name what the workers share. Large and read-mostly favours
threads; small and copied favours processes; large and mutable needs a redesign.

## Discipline

### PS-PERF-20 [M] Never optimise without leaving the measurement behind

A benchmark that re-runs the workload, kept beside the code, and a comment naming the workload and
that benchmark. Not a date: PS-DOC-12 keeps provenance out of comments, and a benchmark answers the
question a date only places in time.

**Why:** an optimisation is a readability cost paid for a speed benefit, and the next reader can see
only the cost. Without a way to re-measure they cannot tell whether the trade still holds — and it
often does not, because the interpreter got faster or the workload changed.

**Check:** every non-obvious construct justified by speed. No benchmark to re-run is the finding.

## Decided by tools

A tool settles these on its own; the shipped configuration enables each at the level shown.

| Tool | Lint | Level | Forbids |
|---|---|---|---|
| ruff | `PERF401` | error | a loop that only appends — a comprehension — listed because the comprehension is both the faster and the readable form, so PS-PERF-01 has nothing to weigh |
