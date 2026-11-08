# Performance

Scope: deciding what to make faster and proving that it is: measuring before optimising and
estimating on paper first, the complexity and the cost a design commits to, how a benchmark is built
and kept, and the habits of loops, allocation, input and output and data layout that decide cost.
Contention between threads is the concurrency chapter's.

## Contents

- **Deciding what to change**
  - AS-PERF-01 [M] Measure before optimising, and keep a change only for the gain it shows
  - AS-PERF-02 [M] Fix the complexity before the constant
  - AS-PERF-03 [S] Estimate a design's cost on paper before measuring it
  - AS-PERF-04 [S] State the cost of an operation where a caller would otherwise guess
- **Measuring**
  - AS-PERF-05 [M] Measure the build that ships
  - AS-PERF-06 [M] Time a benchmark with a harness that repeats it and keeps the optimiser from deleting the work
  - AS-PERF-07 [M] Keep the benchmark of an optimised workload where it can be run again
- **Work inside a loop**
  - AS-PERF-08 [M] Hoist the work that does not change out of the loop, and do not count on the optimiser to
  - AS-PERF-09 [S] Allocate outside the loop and reuse the storage on each pass
  - AS-PERF-10 [S] Reserve a collection's capacity when its size is known
- **Data and input and output**
  - AS-PERF-11 [M] Batch the operations whose fixed cost dwarfs their work
  - AS-PERF-12 [M] Stream a large sequence rather than materialising it
  - AS-PERF-13 [M] Handle bytes as bytes until text is needed
  - AS-PERF-14 [M] Choose the collection by the access pattern
  - AS-PERF-15 [S] Lay out data by how it is read
  - AS-PERF-16 [S] Map a file into memory only to read a large one at random
  - AS-PERF-17 [S] Keep the generic layer thin and the work in one non-generic core

---

## Deciding what to change

### AS-PERF-01 [M] Measure before optimising, and keep a change only for the gain it shows

An optimisation starts from a measurement of the whole operation that users wait for, not from a
suspicion about one function, and it is kept only if a second measurement of the same workload shows
a difference that matters. A change whose gain is within noise is reverted, because the readable
version is the default and only a measurement overturns it. The expensive part is usually somewhere
nobody looked.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-PERF-01 | realises | [M] | |
| rust-style | RS-PERF-01 | realises | [M] | |
| zig-style | ZS-PERF-28 | realises | [M] | |

### AS-PERF-02 [M] Fix the complexity before the constant

A change of algorithm or of the shape of the work buys orders of magnitude and decides which inputs
are feasible at all, while a change of constant buys a percentage. The class of the cost in the size
of the input is settled first, and a quadratic loop is not made faster by being made cheaper per
step.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-PERF-03 | realises | [M] | |
| rust-style | RS-PERF-02 | realises | [M] | |
| zig-style | ZS-PERF-01 | realises | [M] | |

### AS-PERF-03 [S] Estimate a design's cost on paper before measuring it

Before a design is built or a benchmark is run, the cost is written down as arithmetic: how many
items, how many bytes, how many round trips, at what rate, set against what the machine does in a
step. The estimate usually settles the question in a minute, says what the benchmark should report,
and catches an optimisation aimed at a resource that was never the bottleneck.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-PERF-05 | realises | [S] | |
| rust-style | RS-PERF-03 | realises | [S] | |
| zig-style | ZS-PERF-02 | realises | [S] | |

### AS-PERF-04 [S] State the cost of an operation where a caller would otherwise guess

A function whose cost the signature does not show says so in its documentation, in the units a
caller reasons in: linear in the input, one round trip per call, one allocation. Without the
sentence the careful caller benchmarks the function to learn what one line could have said, and the
careless one calls it in a loop.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-PERF-04 | realises | [S] | |
| rust-style | RS-PERF-04 | realises | [S] | |
| zig-style | ZS-PERF-05 | realises | [S] | |

## Measuring

### AS-PERF-05 [M] Measure the build that ships

A timing is taken from the build that is released, with the optimisations and the settings it ships
with, and a number from an unoptimised build is never quoted. An unoptimised build removes the
optimisations the design depends on, so it can rank two implementations in the opposite order from
the one that ships.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | | absent | | Python code has no optimisation mode to mistake for the shipped one: the interpreter that runs it is the one measured, and which interpreter build to choose is PS-PERF-16's |
| rust-style | RS-PERF-06 | realises | [M] | |
| zig-style | ZS-PERF-21 | realises | [M] | |

### AS-PERF-06 [M] Time a benchmark with a harness that repeats it and keeps the optimiser from deleting the work

A benchmark runs the work more than once, discards or accounts for the cold first run, and reports a
spread rather than one reading. Its inputs and results are passed through something the optimiser
cannot see through, so that a computation whose result is unused or whose input is constant is not
removed or folded away and the number measures the work and not an empty loop.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-PERF-15 | realises | [M] | |
| rust-style | RS-PERF-29 | realises | [M] | |
| zig-style | ZS-PERF-26 | realises | [M] | |

### AS-PERF-07 [M] Keep the benchmark of an optimised workload where it can be run again

The benchmark that justified an optimisation stays in the repository, runnable, with inputs that are
fixed or generated from a seed, so that a later reader can tell whether the trade still holds.
Without a way to measure again, the next reader sees only the cost in readability and cannot judge
the benefit.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-PERF-20 | realises | [M] | |
| rust-style | RS-PERF-30 | realises | [M] | |
| zig-style | ZS-PERF-27 | realises | [M] | |

## Work inside a loop

### AS-PERF-08 [M] Hoist the work that does not change out of the loop, and do not count on the optimiser to

What a loop computes the same way on every pass is computed once above it: a compiled pattern, a
configuration read, a length, a field behind a reference. The optimiser may do this for the code it
can prove safe, and it is not obliged to, so the hoist is written by hand where it matters and the
code does not depend on it being made.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-PERF-11 | realises | [M] | |
| rust-style | RS-PERF-26 | realises | [M] | |
| zig-style | ZS-PERF-13 | realises | [M] | |

### AS-PERF-09 [S] Allocate outside the loop and reuse the storage on each pass

A buffer a loop fills on every pass is created once, outside it, and emptied for the next pass,
rather than allocated and freed each time. Allocation is a call into the allocator with a cost of
its own, and per iteration it turns a linear pass into one dominated by allocator traffic.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-PERF-13 | realises | [S] | |
| rust-style | RS-PERF-08 | realises | [S] | |
| zig-style | ZS-PERF-09 | realises | [S] | |

### AS-PERF-10 [S] Reserve a collection's capacity when its size is known

When the number of elements a collection will hold is known before it is filled, the space is
reserved once, rather than grown by repeated doubling that copies what has been written. The
reservation also moves the one step that can fail out of the loop that fills it.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | | absent | | A list has no capacity to reserve: it grows by itself and offers no call to size it ahead, so the saving is made by building it from a comprehension or a join |
| rust-style | RS-PERF-07 | realises | [S] | |
| zig-style | ZS-PERF-10 | realises | [S] | |

## Data and input and output

### AS-PERF-11 [M] Batch the operations whose fixed cost dwarfs their work

An operation that pays a fixed cost each time it is made, such as a system call, a round trip or a
lock, is made once for many items rather than once per item. The saving is usually two orders of
magnitude and not a few percent, and it is a property of the design: once callers depend on a
per-item interface, moving to a batch one breaks every call site.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-PERF-08 | realises | [M] | |
| rust-style | RS-PERF-19 | realises | [M] | |
| zig-style | ZS-PERF-06 | realises | [M] | |

### AS-PERF-12 [M] Stream a large sequence rather than materialising it

A sequence a caller consumes once is handed over as it is produced, not collected first, and data
that is copied onward is moved in chunks and not read whole. Collecting costs memory in proportion
to the input and delays the first result until the last, which for a large or unbounded input is the
difference between working and not, and a caller who wants all of it can always collect.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-PERF-09 | realises | [M] | |
| rust-style | RS-PERF-22 | realises | [M] | |
| zig-style | ZS-PERF-07 | realises | [M] | |

### AS-PERF-13 [M] Handle bytes as bytes until text is needed

Data that is bytes is read, searched, compared and hashed as bytes, and decoded as text only where
text is what the work needs. Decoding what is not text corrupts it on the way back, and validating
what is only searched costs a pass over the data and rejects input that could have been processed.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-PERF-10 | realises | [M] | |
| rust-style | RS-PERF-21 | realises | [M] | |
| zig-style | | absent | | A Zig string is a byte slice, and there is no decoding step to skip or to get wrong: text is bytes by construction |

### AS-PERF-14 [M] Choose the collection by the access pattern

Each collection makes one access cheap and the others dear: a sequence to iterate and to index, a
hash table to look up by key, a sorted structure to iterate in order. The wrong choice reads the
same as the right one and costs a scan per lookup, which inside a loop turns linear work into
quadratic work, so the access the code makes is named before the collection is picked.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-PERF-07 | realises | [M] | |
| rust-style | RS-PERF-11 | realises | [M] | |
| zig-style | ZS-PERF-16 | realises | [M] | |

### AS-PERF-15 [S] Lay out data by how it is read

When a hot loop reads one field of many records, the fields are stored by column rather than by
record, so that each cache line carries only data the loop uses. A record layout loads the other
fields on every step and gives the loop nothing for them, and the choice is made on a measurement of
the loop that reads.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-PERF-14 | realises | [S] | |
| rust-style | RS-PERF-13 | realises | [S] | |
| zig-style | ZS-PERF-12 | realises | [S] | |

### AS-PERF-16 [S] Map a file into memory only to read a large one at random

A file mapped into memory is cheaper than a read only when it is large and its access jumps about,
since the mapping costs a setup and a page fault on the first touch of each page. A small file, a
linear pass or a stream is read through a buffer instead, so mapping is a choice made for the file
and the access, not a default.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-PERF-12 | realises | [S] | |
| rust-style | RS-PERF-20 | realises | [S] | |
| zig-style | ZS-PERF-08 | realises | [S] | |

### AS-PERF-17 [S] Keep the generic layer thin and the work in one non-generic core

A generic algorithm is compiled once for every type it is used with, so the body that does not
depend on the type is written once, in a core that is not generic, and the generic layer is a thin
wrapper that forwards to it. The cost of the copies is code size and compile time, and a thin
wrapper keeps both in step with the number of entry points and not with their product with the
number of types.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | | absent | | A Python function is compiled once and serves every type, so there are no copies of a generic body to keep small |
| rust-style | RS-PERF-24 | realises | [S] | |
| zig-style | ZS-PERF-15 | realises | [S] | |
