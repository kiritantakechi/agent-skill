# Performance: Measuring, Complexity, Allocation, and What the Build Costs

Scope: deciding what to make faster and how to know it worked — the profiling tools 3.15 ships, the
costs that are structural rather than local, and what the free-threaded build charges you. Blocking
the event loop is the async chapter; lock contention is the free-threading chapter.

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
  - PS-PERF-11 [M] Give a hot class `__slots__`
  - PS-PERF-12 [S] Reuse a buffer rather than allocating per iteration
  - PS-PERF-13 [M] Cache only what is pure, and say so
  - PS-PERF-14 [S] Prefer a comprehension to an append loop
- **What the build costs**
  - PS-PERF-15 [M] Budget for the free-threaded build's single-threaded overhead
  - PS-PERF-16 [M] Know that the JIT is unavailable on the free-threaded build
  - PS-PERF-17 [M] Expect higher memory on the free-threaded build
  - PS-PERF-18 [M!] Give shared read-mostly data to threads, not to processes
- **Discipline**
  - PS-PERF-19 [M] Never optimise without leaving the measurement behind
  - PS-PERF-20 [M] Keep the readable version when the fast one is not faster

---

## Deciding what to change

### PS-PERF-01 [M] Measure before changing anything, and measure the thing users wait for

A profile of the whole operation, not a microbenchmark of the function you suspect.

**Why:** intuition about Python performance is wrong more often than it is right, and the cost of
being wrong is a change that makes the code harder to read for no gain. Measuring the whole
operation also catches the case where the function you suspected is 2% of the time — which is the
common case, and the one where optimising it is pure loss.

**Check:** every performance change in review must arrive with a before and after number for the
same workload. Without one it is a readability change with a performance claim attached.

### PS-PERF-02 [M] Profile with the `profiling` package

New in 3.15: `profiling.tracing` for deterministic call counts, `profiling.sampling` for wall-clock
truth. `cProfile` remains as an alias of `profiling.tracing`, so prefer the name that says what it
does; `profile` is deprecated for removal in 3.17.

**Why:** `profiling.sampling` — Tachyon — samples without instrumenting, so it does not distort what
it measures, and it can attach to an already-running process by PID. Deterministic tracing inflates
call-heavy code, which is exactly the code you are most likely to be profiling, so the tool that
answers "where does the time go" and the tool that answers "how many times is this called" are
genuinely different tools.

**Check:** `rg -n 'cProfile|import profile' src/` — a `profile` hit is a removal due in 3.17, and a
`cProfile` hit is the old name for `profiling.tracing`.

### PS-PERF-03 [M] Fix the complexity before fixing the constant

An `O(n²)` loop rewritten in C is still `O(n²)`.

**Why:** constant-factor work is bounded by a small multiple; complexity is unbounded in `n`. A
quadratic scan that is fine for the hundred rows in the test becomes the outage at ten thousand, and
no amount of local optimisation moves that. Find the nested loop, the repeated linear scan, the
membership test against a list, before touching anything else.

**Check:** every nested loop over the same collection, and every `in` against a list inside a
loop. A review matter: the ruff rule for excessive nesting is preview, and the shipped
configuration runs stable rules only.

### PS-PERF-04 [M] State the cost in the units the caller cares about

"Linear in the number of rows", "one round trip per call", "allocates a copy of the input".

**Why:** a caller cannot use a function correctly without knowing what it costs, and the cost is not
visible from the signature. Documenting it lets a caller hoist the call out of a loop, batch it, or
cache it — decisions they can only make if you told them. This is a docstring obligation, not a
comment.

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

`"".join(parts)`. Not `out += piece` in a loop.

**Why:** strings are immutable, so each `+=` allocates a new string and copies everything so far —
which makes building an n-character string O(n²). CPython has an optimisation that sometimes rescues
the simplest case in-place, which is worse than no optimisation: it makes the quadratic version fast
enough in the test and quadratic in production where the string is aliased.

**Check:** `rg -n '^[ \t]*\w+[ \t]*\+=[ \t]*.*["\x27]' src/` and read each hit for an
enclosing loop.
The ruff rules that catch the mechanical cases are preview, so this is a grep and a review.

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
`O(n)` into `O(n·m)` and it is invisible at the call site — the two spellings are identical. A
module-level constant is where this is most often wrong, because a literal list looks like the
obvious thing to write.

**Check:** `rg -n 'in \[' src/` — a literal list on the right of `in` is always the finding.
The ruff rule for it is preview and therefore not enabled here.

### PS-PERF-08 [M] Batch I/O rather than looping over single operations

One query returning a thousand rows, not a thousand queries. One `writelines`, not a thousand
`write`s.

**Why:** each operation pays a fixed cost — a round trip, a syscall, a lock — that dwarfs the work.
Batching amortises it, and the difference is usually two orders of magnitude rather than a few
percent. This is the single largest source of real slowness in application code, and it is a design
property rather than a local one, which is why it must be decided early.

**Check:** every I/O call inside a `for`. Each is a candidate for batching, and most are.

### PS-PERF-09 [M] Stream a large sequence rather than materialising it

Yield, or return an iterator. Do not build the whole list when the caller consumes it once.

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

### PS-PERF-11 [M] Give a hot class `__slots__`

Or `@dataclass(slots=True)`, which is the same thing written once.

**Why:** the per-instance `__dict__` is the largest part of a small object, and removing it makes
instances smaller and attribute access faster. On the free-threaded build the saving matters
more, because object headers are already larger there — a non-GC object is 32 bytes where the
default build uses 16. It also catches attribute typos, per PS-DATA-02.

**Check:** every class instantiated more than a few thousand times. No `slots` is the finding.

### PS-PERF-12 [S] Reuse a buffer rather than allocating per iteration

A `bytearray` you write into, a list you clear, a `memoryview` over a slice.

**Why:** allocation is the cost that dominates tight loops in Python, and it is invisible in the
source — `chunk = data[i:i+n]` looks free and copies. Reuse trades readability for it, which is why
this is `[S]`: do it where measured, and comment that it was measured.

**Check:** every slice inside a hot loop. `memoryview` avoids the copy where the consumer accepts
one.

### PS-PERF-13 [M] Cache only what is pure, and say so

`functools.cache` on a function with no arguments you cannot hash and no effects.

**Why:** a cache on an impure function is a bug with a performance justification — it makes the
effect happen once and the caller believe it happened every time. And per PS-CONC-18 the cache is
not single-flight, so under threads the body runs more than once anyway. Purity is the precondition,
not a nicety.

**Check:** every `@cache` and `@lru_cache`. Read the body for I/O, mutation, randomness, or time.

### PS-PERF-14 [S] Prefer a comprehension to an append loop

`[f(x) for x in items]` over building a list with `.append`.

**Why:** the comprehension is a single bytecode-level construct that avoids the repeated attribute
lookup and method call, so it is measurably faster — and it reads as one expression, which is the
better reason. It stops being the right choice when the body needs more than one statement, at which
point the loop is clearer and the difference no longer matters.

**Check:** ruff `PERF401` and `PERF402` rewrite the mechanical cases.

## What the build costs

### PS-PERF-15 [M] Budget for the free-threaded build's single-threaded overhead

Somewhere between 5% and 30% depending on the workload, and closer to 30% for allocation-heavy code.

**Why:** the documentation quotes "about 1% on macOS aarch64 to 8% on x86-64 Linux" from the
pyperformance suite, and the daily benchmark runs on that suite have sat near 1.10x on Linux x86_64
through 2026. A suite geomean is not your workload: refcount- and allocation-heavy code pays much
more, because every reference to an object owned by another thread takes a slow path. So budget from
your own measurement, and cite the date — these numbers move every release.

**Check:** benchmark the same workload on both builds before committing to free threading. A
decision made on the doc's number rather than on yours is the finding.

### PS-PERF-16 [M] Know that the JIT is unavailable on the free-threaded build

`--enable-experimental-jit` with `--disable-gil` builds a JIT that is never used; CPython's own
configure script warns about it.

**Why:** it makes the trade explicit. 3.15's JIT is worth single-digit to low-double-digit
percent on the default build, and choosing free threading forgoes it entirely — so the comparison
is not "free-threaded overhead versus zero", it is "overhead plus foregone JIT versus
parallelism". For code that will not use more than one core, that is a straightforwardly bad
trade.

**Check:** any project on the free-threaded build whose workload is single-threaded.

### PS-PERF-17 [M] Expect higher memory on the free-threaded build

PEP 779's target is 20%, and measurements sit at 1.19–1.22x.

**Why:** every interned string is immortal so it is never freed, non-GC object headers are larger,
the allocator is mimalloc rather than pymalloc, and QSBR defers frees until a collection. None of
that is a leak and none of it is tunable away — `gc.collect()` releases what QSBR is holding, which
is the only lever. Size the container accordingly.

**Check:** measure RSS on both builds before setting a memory limit.

### PS-PERF-18 [M!] Give shared read-mostly data to threads, not to processes

Where workers read a large structure and write only their own results, threads on the free-threaded
build avoid the copy entirely.

*Relaxed form:* processes remain correct and are the right answer where the payload marshals cheaply
and the workers share nothing — measure both rather than assuming.

**Why:** this is the case free threading was built for: no pickling, no per-process copy of the
data, and one interpreter's memory instead of N. Where the workers instead hammer the *same
mutable* objects, threads can be slower than processes, because per-object locking and
cross-thread refcount traffic cost more than the isolation they replace.

**Check:** for each parallel workload, name what the workers share. Large and read-mostly favours
threads; small and copied favours processes; large and mutable needs a redesign.

## Discipline

### PS-PERF-19 [M] Never optimise without leaving the measurement behind

A comment naming the workload, the number, and the date.

**Why:** an optimisation is a readability cost paid for a speed benefit, and the next reader can see
only the cost. Without the number they cannot tell whether the trade still holds — and it often does
not, because the interpreter got faster or the workload changed. The comment is what makes the
optimisation reversible.

**Check:** every non-obvious construct justified by speed. No number and no date is the finding.

### PS-PERF-20 [M] Keep the readable version when the fast one is not faster

If the measurement does not show a difference that matters, revert it.

**Why:** this is the rule that makes PS-PERF-01 have consequences. Measuring and then keeping the
change anyway — because it feels faster, or because the work is done — is how a codebase accumulates
complexity with no benefit. The default is the readable version, and the measurement is what
overturns it.

**Check:** every optimisation in review whose before-and-after numbers are within noise.
