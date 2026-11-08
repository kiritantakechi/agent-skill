# Concurrency: Threads, Channels, Locks, and Async

Scope: choosing a concurrency model and living with it — threads and scoped threads, channels,
shared state and lock discipline, atomics, async fundamentals and cancellation safety, structured
concurrency, data parallelism with `rayon`, and testing concurrent code deterministically. Interior
mutability within one thread is the ownership chapter's; `unsafe impl Send` and `Sync` are the
unsafe chapter's; concurrency as a speed-up to measure is the performance chapter's.

Rust removes data races, not concurrency bugs. Deadlocks, livelocks, lost wakeups, unbounded queues,
and cancellation-safety violations are all still yours to avoid. The best defence is choosing the
simplest model that solves the problem — which is very often "not async" and quite often "not
concurrent".

## Contents

- **Choosing a model**
  - RS-CONC-01 [M] Do not add concurrency until a profile shows the need
  - RS-CONC-02 [M] Match the model to the bottleneck
  - RS-CONC-03 [M] Do not adopt async for a CLI that does a handful of file reads
  - RS-CONC-04 [M] Mutate through a message to one owner wherever a message can do it
  - RS-CONC-05 [M] Lock only data that is written after it is shared
  - RS-CONC-06 [S] Prefer partitioning to synchronization
  - RS-CONC-07 [M] Keep the concurrency at one layer, ideally the top
  - RS-CONC-08 [M] Decide the parallelism model before writing the data structures
  - RS-CONC-09 [M] Bound every queue an open-ended producer feeds
  - RS-CONC-10 [M] Design shutdown at the start

- **Threads**
  - RS-CONC-11 [M] Use `std::thread::scope` for threads that borrow local data
  - RS-CONC-12 [M] Always handle `JoinHandle::join`'s result
  - RS-CONC-13 [M] Clone what a spawned closure needs *before* the closure
  - RS-CONC-14 [S] Size the pool from `available_parallelism()`, and let the user override
  - RS-CONC-15 [M] Do not spawn per item
  - RS-CONC-16 [S] Choose `mpsc` for simple fan-in and `crossbeam-channel` for the rest
  - RS-CONC-17 [M] Close channels deliberately
  - RS-CONC-18 [S] Prefer `park`/`unpark` and condvars to sleep-polling

- **Shared state**
  - RS-CONC-19 [M] Ask three questions before reaching for `Arc<Mutex<…>>`
  - RS-CONC-20 [M] Hold locks briefly, and never across an `.await` or a blocking call
  - RS-CONC-21 [S] Treat lock granularity as a tuning parameter with evidence
  - RS-CONC-22 [S] Use `RwLock` only for read-dominated, long critical sections
  - RS-CONC-23 [M] Establish a lock order and document it
  - RS-CONC-24 [M] Decide deliberately what a poisoned `Mutex` means for your crate
  - RS-CONC-25 [M] Reserve atomics for counters, flags, and provable algorithms
  - RS-CONC-26 [M] Do not hand-build lock-free data structures
  - RS-CONC-27 [M] Use `OnceLock`/`LazyLock` for lazily initialized globals

- **Async fundamentals**
  - RS-CONC-28 [M] Await, spawn or join every future you create
  - RS-CONC-29 [M] Do not block in async
  - RS-CONC-30 [M] Implement `Future` by hand only for a leaf primitive
  - RS-CONC-31 [M] Decide explicitly whether your trait needs `Send` futures
  - RS-CONC-32 [M] Make a future that can be dropped mid-flight correct at every `.await`
  - RS-CONC-33 [M] Do not `select!` over branches that lose data on cancellation
  - RS-CONC-34 [M] Apply a caller-supplied timeout at every boundary that can hang

- **Data parallelism**
  - RS-CONC-35 [S] Reach for `rayon` — it is the highest return-on-effort parallelism in Rust
  - RS-CONC-36 [M] Parallelize at a coarse granularity
  - RS-CONC-37 [M] Keep the closure passed to a parallel iterator pure
  - RS-CONC-38 [M] Reorder or serialize parallel output deliberately

- **Testing and debugging**
  - RS-CONC-39 [M] Test a hand-written synchronization algorithm with `loom`
  - RS-CONC-40 [M] Run code with `unsafe` sharing under ThreadSanitizer before every release
  - RS-CONC-41 [S] Stress-test beyond core count, behind `#[ignore]`
  - RS-CONC-42 [M] Log with a task or thread identifier
  - RS-CONC-43 [S] Reproduce deadlocks by capturing backtraces, not by reasoning
  - RS-CONC-44 [M] Give every task a parent that outlives it and joins it
  - RS-CONC-45 [M] Document the threading contract of every public type

- **Files shared between processes**
  - RS-CONC-46 [M] Write output that cannot be regenerated atomically

- Decided by tools

---

## Choosing a model

### RS-CONC-01 [M] Do not add concurrency until a profile shows the need

It multiplies the state space, complicates every error path, and makes failures non-reproducible.
Sequential code that is fast enough is the right answer.

**Why:** concurrency converts deterministic bugs into intermittent ones, which are orders of
magnitude more expensive to find. That cost is permanent, whereas the speedup is often unnecessary —
the sequential version already met the requirement.

**Check:** what measurement motivated the concurrency? If the sequential version was never timed,
the justification does not exist.

```rust
// verified
/// Sequential and fast enough: no threads, no shared state, no intermittent failures.
#[must_use]
pub fn total(values: &[u64]) -> u64 {
    values.iter().sum()
}
```

### RS-CONC-02 [M] Match the model to the bottleneck

Threads and `rayon` for CPU-bound work, async for I/O-bound work with many concurrent operations,
and a thread pool with blocking I/O for a few dozen connections — which is simpler than async and
competitive at that scale.

**Why:** async solves the problem of holding many waiting operations cheaply; it does nothing for
CPU-bound work and actively hurts it by adding a scheduler. Threads solve CPU parallelism and cost
about a megabyte of stack each, which only matters in the thousands.

**Check:** name the bottleneck — CPU or waiting — and the expected concurrency count. The pair
determines the model.

### RS-CONC-03 [M] Do not adopt async for a CLI that does a handful of file reads

`tokio` brings a runtime, a scheduler, coloured functions, and a large dependency tree; a CLI that
opens fifty files should just open them.

**Why:** async's benefit appears at high concurrency, and fifty sequential file reads have none.
What you do get is a function-colouring constraint through the whole codebase and a much larger
build (RS-BUILD-18). It is RS-CONC-02's choice, made for the commonest case.

**Check:** how many operations are in flight at once? Below a few hundred, blocking I/O on a small
pool is simpler and usually faster.

### RS-CONC-04 [M] Mutate through a message to one owner wherever a message can do it

Channels give you one owner per value, backpressure, and a shutdown protocol; shared mutable state
gives you locks and a graph of who may touch what.

**Why:** a channel makes the ownership transfer explicit and localizes the synchronization to one
well-tested primitive. Shared state distributes the reasoning across every site that takes the lock,
and the correctness argument has to consider all of them.

**Check:** for each `Arc<Mutex<T>>`, ask whether the mutation could be a message to a single owner.

```rust
// verified
use std::{sync::mpsc, thread};

/// One owner per value: the channel moves work, no lock is involved.
#[must_use]
pub fn total(chunks: Vec<Vec<u32>>) -> u32 {
    let (tx, rx) = mpsc::channel();
    thread::scope(|scope| {
        for chunk in chunks {
            let tx = tx.clone();
            scope.spawn(move || {
                let _ignored = tx.send(chunk.iter().sum::<u32>());
            });
        }
        drop(tx);
        rx.iter().sum()
    })
}
```

### RS-CONC-05 [M] Lock only data that is written after it is shared

`Arc<T>` where `T` never changes needs no lock at all — and inside `thread::scope` a plain `&T` does
the same. The vast majority of "shared state" is configuration that is written once at startup.

**Why:** immutable data is `Sync` for free, so there is no critical section, no contention, and no
deadlock risk. Most state that gets wrapped in a mutex is never actually mutated after construction.

**Check:** for each `Mutex`, find the writes after initialization. If there are none, the lock can
be deleted.

```rust
// verified
use std::thread;

/// Shared immutably: every worker reads the same `&str`, so nothing locks.
#[must_use]
pub fn count_matches(haystacks: &[String], needle: &str, workers: usize) -> usize {
    let chunk = haystacks.len().div_ceil(workers.max(1)).max(1);
    thread::scope(|scope| {
        let handles: Vec<_> = haystacks
            .chunks(chunk)
            .map(|slice| {
                scope.spawn(move || slice.iter().filter(|hay| hay.contains(needle)).count())
            })
            .collect();
        handles
            .into_iter()
            .filter_map(|handle| handle.join().ok())
            .sum()
    })
}
```

### RS-CONC-06 [S] Prefer partitioning to synchronization

Give each worker its own slice of the data and merge at the end. No lock is faster than any lock.

**Why:** partitioning removes the shared resource entirely, so it scales linearly instead of
contending. The merge at the end is usually cheap and happens once rather than per operation.

**Check:** can the work be split so that no two workers touch the same data? If so, the lock is
unnecessary.

```rust
// verified
use std::thread;

/// Partitioned: each worker owns its slice, so there is nothing to synchronize.
#[must_use]
pub fn sum_partitioned(values: &[u64], workers: usize) -> u64 {
    let chunk = values.len().div_ceil(workers.max(1));
    thread::scope(|scope| {
        let handles: Vec<_> = values
            .chunks(chunk.max(1))
            .map(|slice| scope.spawn(move || slice.iter().sum::<u64>()))
            .collect();
        handles
            .into_iter()
            .filter_map(|handle| handle.join().ok())
            .sum()
    })
}
```

### RS-CONC-07 [M] Keep the concurrency at one layer, ideally the top

A library that spawns its own threads or requires a specific runtime constrains every application
that uses it. Offer a synchronous API and let the caller parallelize. Where the library must be
async, keep it runtime-agnostic: depend on `futures`/`std` traits rather than `tokio` internals, and
gate runtime-specific code behind features.

**Why:** the application knows its own thread budget and runtime; the library does not. One that
spawns threads oversubscribes inside another parallel context, and one that requires a runtime
cannot be used outside it, since two runtimes cannot generally coexist.

**Check:** does the library spawn threads or require a runtime? If so, can the parallelism be lifted
to the caller, or the runtime dependency feature-gated?

### RS-CONC-08 [M] Decide the parallelism model before writing the data structures

Retrofitting `Send + Sync` onto a design built around `Rc` and `RefCell` is a rewrite, not a
refactor.

**Why:** `Rc` and `RefCell` are not `Send`, and they tend to be load-bearing in the designs that use
them — a graph with parent pointers, a tree with shared nodes. Converting means changing the
ownership model, which touches everything.

**Check:** if the code might ever be parallel, are the shared types `Send`? Deciding later is much
more expensive than deciding now.

### RS-CONC-09 [M] Bound every queue an open-ended producer feeds

A producer that network input or user activity drives can outrun any consumer, and an unbounded
channel converts that backpressure into memory exhaustion, which surfaces as an OOM kill hours later
rather than a slow producer immediately. A queue whose producer is a bounded, known set — a fixed
list of files, a fixed worker count — is bounded by construction.

**Why:** a bounded channel makes a fast producer block, which is the signal that the system is
overloaded, delivered at the point where it can be handled. Unbounded, that signal is deferred until
memory runs out, at which point the process dies with no useful diagnostic.

**Check:** is a queue that network input or user activity feeds built with `mpsc::channel()`, an
`unbounded()` constructor, or a `Vec` a loop fills? Each is the finding.

```rust
// verified
use std::sync::mpsc::{self, SyncSender};

/// A bounded channel turns overload into backpressure instead of memory exhaustion.
#[must_use]
pub fn bounded_queue(capacity: usize) -> (SyncSender<u32>, mpsc::Receiver<u32>) {
    mpsc::sync_channel(capacity)
}
```

### RS-CONC-10 [M] Design shutdown at the start

Settle how workers learn to stop, how in-flight work drains, and how the main thread waits.
Retrofitted shutdown is where hangs live.

**Why:** shutdown is a protocol involving every concurrent component, so it constrains their design.
Added afterwards it becomes a collection of flags and timeouts that mostly work, and the failure
mode is a process that will not exit.

**Check:** can every worker be told to stop, and does the main thread wait for all of them? A
missing answer for one worker is a hang.

```rust
// verified
use std::sync::atomic::{AtomicBool, Ordering};

/// Shutdown is designed in: the flag exists before the worker does.
#[derive(Debug, Default)]
pub struct Shutdown {
    requested: AtomicBool,
}

impl Shutdown {
    pub fn request(&self) {
        self.requested.store(true, Ordering::Release);
    }

    #[must_use]
    pub fn is_requested(&self) -> bool {
        self.requested.load(Ordering::Acquire)
    }
}
```

## Threads

### RS-CONC-11 [M] Use `std::thread::scope` for threads that borrow local data

It removes the `Arc`/`'static` dance and guarantees joins, which is exactly the guarantee that makes
borrowing sound.

**Why:** the scope guarantees every thread is joined before it returns, which is what lets the
borrow checker accept references to local data. Without it, sharing local data requires `Arc` and
cloning even when the data outlives the threads in practice.

**Check:** is an `Arc::new` made just before a `thread::spawn` for data that is local? That is a
`thread::scope`.

```rust
// verified
use std::thread;

/// `scope` guarantees the joins, which is what lets the closures borrow local data.
#[must_use]
pub fn longest(words: &[String]) -> usize {
    thread::scope(|scope| {
        let handle = scope.spawn(|| words.iter().map(String::len).max().unwrap_or(0));
        handle.join().unwrap_or(0)
    })
}
```

### RS-CONC-12 [M] Always handle `JoinHandle::join`'s result

Dropping it discards a panic in the worker, turning a crash into silently missing work.

**Why:** a panicking thread does not propagate anywhere; the panic is captured in the join result.
Ignoring that result means the program continues as if the work succeeded, producing wrong output
rather than an error.

**Check:** is a `join()` result discarded, or a `JoinHandle` bound with `let _ =`? Each loses the
worker's panic.

```rust
// verified
use std::thread;

/// A panicking worker is reported through the join result, never silently dropped.
///
/// # Errors
/// Returns `Panicked` if the worker panicked.
pub fn run<T: Send>(work: impl FnOnce() -> T + Send) -> Result<T, Panicked> {
    thread::scope(|scope| scope.spawn(work).join().map_err(|_| Panicked))
}

/// The worker thread panicked.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Panicked;
```

### RS-CONC-13 [M] Clone what a spawned closure needs *before* the closure

When spawning in a loop, clone what the closure needs *before* the closure and move the clones in.
Relying on `move` to capture the right thing from a surrounding scope is how loop variables get
shared or dropped early.

**Why:** `move` captures whatever the body names, so a body that names the outer binding moves the
original on the first iteration and fails to compile — or, with an `Arc`, captures the wrong one.
Making the clone explicit puts the intent in the source.

**Check:** each spawned closure's captures should be bindings created immediately above it.

```rust
// verified
use std::{sync::Arc, thread};

/// Clone before the closure, so what each thread owns is visible above it.
#[must_use]
pub fn spawn_lengths(names: &Arc<Vec<String>>) -> Vec<thread::JoinHandle<usize>> {
    (0..2)
        .map(|i| {
            let names = Arc::clone(names);
            thread::spawn(move || names.get(i).map_or(0, String::len))
        })
        .collect()
}
```

### RS-CONC-14 [S] Size the pool from `available_parallelism()`, and let the user override

Size the pool from `std::thread::available_parallelism()`, not a hard-coded number, and let the user
override it with a flag or environment variable.

**Why:** a hard-coded count is wrong on every machine except the author's, and it ignores cgroup
limits in containers. `available_parallelism` respects those limits; the override handles the cases
it cannot know about, like sharing a machine with another job.

**Check:** is a thread count a numeric literal? Each is a hard-coded pool size.

```rust
// verified
use std::thread::available_parallelism;

/// Sized from the machine, with an explicit override, never a hard-coded number.
#[must_use]
pub fn worker_count(override_to: Option<usize>) -> usize {
    override_to
        .or_else(|| available_parallelism().ok().map(Into::into))
        .unwrap_or(1)
}
```

### RS-CONC-15 [M] Do not spawn per item

Thread creation costs more than most units of work; use a pool (`rayon`) or chunk the work.

**Why:** spawning costs tens of microseconds and a stack allocation, which exceeds the cost of most
work items. Spawning per item makes the program slower than the sequential version while looking
parallel.

**Check:** is `spawn` inside a loop over data? If so, the loop wants a pool or a chunked split.

```rust
// verified
use std::thread;

/// Chunked, so the thread count is bounded by the worker count, not the item count.
#[must_use]
pub fn lengths(items: &[String], workers: usize) -> usize {
    let chunk = items.len().div_ceil(workers.max(1)).max(1);
    thread::scope(|scope| {
        let handles: Vec<_> = items
            .chunks(chunk)
            .map(|slice| scope.spawn(move || slice.iter().map(String::len).sum::<usize>()))
            .collect();
        handles
            .into_iter()
            .filter_map(|handle| handle.join().ok())
            .sum()
    })
}
```

### RS-CONC-16 [S] Choose `mpsc` for simple fan-in and `crossbeam-channel` for the rest

Use `std::sync::mpsc` for simple fan-in, `crossbeam-channel` when you need `select` or multiple
consumers. Throughput is not a reason: `mpsc` is built on crossbeam's implementation. Both are far
easier to reason about than a shared `Mutex<VecDeque<_>>`.

**Why:** a hand-rolled queue behind a mutex has to re-solve blocking, wakeup, and shutdown, and it
usually gets the lost-wakeup case wrong. The channel types have solved all three.

**Check:** is a `Mutex<VecDeque<` or `Mutex<Vec<` used as a work queue? That is a channel.

### RS-CONC-17 [M] Close channels deliberately

A receiver loop ends when all senders drop; a forgotten clone of the sender in the parent scope is
the classic "program hangs at the end" bug (see the `drop(tx)` above).

**Why:** the channel's closure signal *is* the drop of the last sender, so an extra live sender
means the receiver waits forever. The bug appears only at shutdown, after all the real work
succeeded.

**Check:** for each channel, identify every sender clone and confirm each is dropped. The parent's
original is the one usually forgotten.

```rust
// verified
use std::sync::mpsc;

/// Dropping the original sender is what lets the receiver loop terminate.
#[must_use]
pub fn drain(values: Vec<u32>) -> Vec<u32> {
    let (tx, rx) = mpsc::channel();
    for value in values {
        let _ignored = tx.send(value);
    }
    drop(tx);
    rx.iter().collect()
}
```

### RS-CONC-18 [S] Prefer `park`/`unpark` and condvars to sleep-polling

Prefer `park`/`unpark` and condition variables to sleep-polling.
`thread::sleep(Duration::from_millis(10))` in a loop is both slow to react and wasteful.

**Why:** polling trades latency against CPU with no good setting — short intervals burn cycles, long
ones add latency. A condvar wakes exactly when the condition changes.

**Check:** does a loop call `sleep` to wait for a condition? Each is a poll that wants a wakeup
primitive.

## Shared state

### RS-CONC-19 [M] Ask three questions before reaching for `Arc<Mutex<…>>`

`Arc<Mutex<HashMap<..>>>` should not be the first reflex. Ask in order: can each worker own a
partition? can the map be built once and shared immutably? can updates be a channel to one owner?
Only then reach for the lock.

**Why:** each of the three alternatives eliminates the critical section rather than optimizing it,
and each is simpler to reason about. The lock is the fallback when the data genuinely must be shared
and mutable.

**Check:** for each `Arc<Mutex<_>>`, answer the three questions in writing. Reaching the lock
without answering them is the finding.

### RS-CONC-20 [M] Hold locks briefly, and never across an `.await` or a blocking call

Hold locks for the shortest possible span: never across an `.await`, I/O, a channel send, or a
second lock. Compute outside, mutate inside.

**Why:** the critical section's length is every other thread's wait, and I/O and `.await` are
unbounded; a `std::sync` guard held across an `.await` blocks the executor thread too. Blocking on a
second lock creates the ordering that deadlocks (RS-CONC-23).

**Check:** is there an `.await` between a `lock()` and the end of its scope? Read each critical
section for I/O calls, channel sends, and further lock acquisitions. clippy's `await_holding_lock`
catches the async shape.

```rust
// verified
use std::{collections::HashMap, hash::BuildHasher, sync::Mutex};

/// Compute outside, mutate inside: the critical section holds no I/O and no second lock.
pub fn insert_rendered<S: BuildHasher>(
    cache: &Mutex<HashMap<u32, String, S>>,
    key: u32,
    input: &str,
) {
    let rendered = input.to_uppercase();
    if let Ok(mut guard) = cache.lock() {
        guard.insert(key, rendered);
    }
}
```

### RS-CONC-21 [S] Treat lock granularity as a tuning parameter with evidence

Prefer a `Mutex` per subsystem over one global lock, and per-shard locks over one big map lock when
a profile shows contention. Lock granularity is a tuning parameter with evidence behind it, not a
default.

**Why:** finer locks reduce contention and increase the number of orderings that can deadlock, so
the trade is real in both directions. Sharding without contention a profile shows buys complexity
for nothing.

**Check:** is there a contention measurement justifying the current granularity? Both "one global
lock" and "sharded" need one.

```rust
// verified
use std::sync::Mutex;

/// One lock per subsystem rather than one lock for the whole program.
#[derive(Debug, Default)]
pub struct Server {
    sessions: Mutex<Vec<u64>>,
    metrics: Mutex<u64>,
}

impl Server {
    pub fn record(&self, session: u64) {
        if let Ok(mut guard) = self.sessions.lock() {
            guard.push(session);
        }
        if let Ok(mut guard) = self.metrics.lock() {
            *guard += 1;
        }
    }
}
```

### RS-CONC-22 [S] Use `RwLock` only for read-dominated, long critical sections

`RwLock` helps only when reads vastly outnumber writes and the critical sections are long. Otherwise
its extra bookkeeping loses to a plain `Mutex`, and writer starvation becomes a real risk.

**Why:** an `RwLock` does more atomic work per acquisition than a `Mutex`, so for short critical
sections the bookkeeping exceeds the parallelism gained. Depending on the implementation, continuous
readers can also starve a waiting writer indefinitely.

**Check:** what is the read/write ratio and how long is the critical section? Without both numbers,
`Mutex` is the safer default.

### RS-CONC-23 [M] Establish a lock order and document it

Every deadlock in practice is two code paths taking the same two locks in different orders.

**Why:** deadlock requires a cycle in the acquisition graph, and a global order makes cycles
impossible by construction. It is one of the few concurrency properties that can be checked by
reading.

**Check:** list every place two locks are held simultaneously and confirm the order matches the
documented one.

### RS-CONC-24 [M] Decide deliberately what a poisoned `Mutex` means for your crate

`Mutex::lock` returns a `Result` because of poisoning. In a binary, `.expect("lock poisoned")` is
defensible; in a library, propagate or use a non-poisoning mutex (`parking_lot`) and say so.

**Why:** poisoning means a thread panicked while holding the lock, so the protected invariant may be
broken. A library that unwraps decides on the application's behalf that the process should die.

**Check:** `rg -n -F '.lock().unwrap()' -g '*.rs'` finds a poisoned lock turned into a panic; each
hit in library code is an undocumented panic (RS-DOC-10).

### RS-CONC-25 [M] Reserve atomics for counters, flags, and provable algorithms

Atomics are for counters, flags, and lock-free algorithms written by people who can prove them
correct. Use `Relaxed` for statistics, `Acquire`/`Release` for handoff, and `SeqCst` when you are
not sure — then learn why you were not sure. For a read-modify-write no single `fetch_*` method
covers, call `update` or `try_update` rather than writing a `compare_exchange` loop; `fetch_update`
is deprecated, and its warning fails a build that denies warnings.

**Why:** memory orderings are a formal contract about what other threads observe, and the failure
mode of getting one wrong is a bug that appears only on weakly-ordered hardware. `SeqCst` is the
conservative choice because it is the easiest to reason about.

**Check:** for each non-`SeqCst` ordering, state what it is synchronizing with. `Relaxed` on
anything other than an independent counter needs an argument.

```rust
// verified
use std::sync::atomic::{AtomicU64, Ordering};

/// An independent statistic: `Relaxed` is sufficient and is stated deliberately.
#[derive(Debug, Default)]
pub struct Metrics {
    scanned: AtomicU64,
}

impl Metrics {
    pub fn record(&self, count: u64) {
        self.scanned.fetch_add(count, Ordering::Relaxed);
    }

    #[must_use]
    pub fn scanned(&self) -> u64 {
        self.scanned.load(Ordering::Relaxed)
    }
}
```

### RS-CONC-26 [M] Do not hand-build lock-free data structures

Do not build lock-free data structures by hand. Use `crossbeam`, `dashmap`, or an actor with a
channel. The literature is full of published algorithms that turned out to be wrong.

**Why:** lock-free correctness depends on reclamation and ordering interactions that ordinary
testing cannot observe, and peer-reviewed algorithms have shipped with bugs found years later. The
libraries have been verified with `loom` and used at scale.

**Check:** is there hand-written `compare_exchange` in the crate? If so, is it a published
algorithm, and is it `loom`-tested (RS-CONC-39)? A retry loop that only recomputes one value is an
`update` or `try_update` call (RS-CONC-25).

### RS-CONC-27 [M] Use `OnceLock`/`LazyLock` for lazily initialized globals

Not `static mut`, which edition 2024 denies through `static_mut_refs`, and not a `Mutex<Option<T>>`
(RS-OWN-24). Data known at compile time needs neither: it is a `const`.

**Why:** these types give a safe, race-free single initialization with no lock on the read path
after it. A `Mutex<Option<T>>` pays for a lock on every access to emulate the same thing.

**Check:** `rg -n '^\s*(pub(\(crate\))? )?static mut |Mutex<Option<' -g '*.rs'` finds the two
spellings this rule replaces; each hit is the finding. A `LazyLock` whose initializer is a literal
is a `const`, and clippy's `non_std_lazy_statics` finds `lazy_static!` and `once_cell`.

```rust
// verified
use std::{num::NonZero, sync::LazyLock, thread::available_parallelism};

/// Computed once, on first use, with no lock on the read path afterwards.
static WORKERS: LazyLock<usize> = LazyLock::new(|| available_parallelism().map_or(1, NonZero::get));

#[must_use]
pub fn workers() -> usize {
    *WORKERS
}
```

## Async fundamentals

### RS-CONC-28 [M] Await, spawn or join every future you create

Futures are inert. Nothing happens until they are polled — so building a future and dropping it does
no work, and a `Vec<Future>` runs nothing until you `join_all` or spawn.

**Why:** this is the fundamental difference from languages where calling an async function starts
it. It means an un-awaited future is a silent no-op rather than background work, which is the source
of the most common async surprise.

**Check:** is a call to an `async fn` left neither awaited, spawned, nor collected into a joiner?
The `unused_must_use` warning catches most.

```rust
// verified
use std::future::ready;

/// Futures are inert: `pending` is constructed and does nothing until it is awaited.
pub async fn doubled(value: u32) -> u32 {
    let pending = ready(value * 2);
    pending.await
}
```

### RS-CONC-29 [M] Do not block in async

A synchronous file read, a `std::sync` lock held across a poll, or a CPU-bound loop stalls the whole
executor thread. Use `spawn_blocking` for blocking work and the async equivalents for I/O.

**Why:** an executor thread runs many tasks cooperatively, so a blocking call stops all of them, not
just the caller. On a multi-threaded runtime that is one core lost; if every worker blocks, the
runtime deadlocks.

**Check:** does an async body call `std::fs`, `std::net` or `thread::sleep`, or lock a
`std::sync::Mutex`? Each stalls the executor thread.

### RS-CONC-30 [M] Implement `Future` by hand only for a leaf primitive

Everything else is an `async fn` or an `impl Future` the compiler generates. A hand-written `Future`
respects the contract: it registers the waker on every `Pending` return.

**Why:** the compiler generates a correct state machine, including the waker handling that
hand-written implementations get wrong. A `Pending` return without a registered waker is a task that
never wakes — a hang with no diagnostic.

**Check:** for each manual `impl Future`, confirm every `Pending` path registered the waker first.
Test one without a runtime: `pin!` it and poll it with `Context::from_waker(Waker::noop())`.

### RS-CONC-31 [M] Decide explicitly whether your trait needs `Send` futures

`async fn` in traits does not produce a `Send` future automatically, and is not dyn-compatible.
Decide explicitly whether your trait needs `Send` futures — `trait_variant`, an explicit
`-> impl Future<Output = _> + Send`, or `Pin<Box<dyn Future + Send>>` — and say which in the
rustdoc. The same decision governs an async callback: take an `AsyncFn` bound rather than
`F: Fn() -> Fut, Fut: Future`, unless the callback's future must be `Send` — Rust 1.99 cannot state
that of an `AsyncFn`.

**Why:** a multi-threaded runtime requires `Send` futures to spawn them, and the bound cannot be
added by the caller afterwards. Discovering this after publishing means a breaking change.

**Check:** can a user spawn a call to your trait method on a multi-threaded runtime? If not, that is
a design decision and needs documenting.

```rust
// verified
use std::future::Future;

/// The `Send` bound is stated, so the future can be spawned on a multi-threaded runtime.
pub trait Fetch {
    /// Fetches one record by key.
    fn fetch(&self, key: u32) -> impl Future<Output = Option<String>> + Send;
}
```

### RS-CONC-32 [M] Make a future that can be dropped mid-flight correct at every `.await`

Cancellation in async is a drop, at whichever `.await` the future is suspended. A future that can be
dropped before it completes — inside a `select!`, under a `timeout`, or in a task that can be
aborted — holds no resource across an await that its drop there would corrupt. One cancelled only at
shutdown may leak a temporary.

**Why:** there is no cancellation notification and no async destructor, so cleanup has to work
through ordinary `Drop`. A half-consumed read or a half-sent message dropped mid-operation loses
data silently.

**Check:** for each `.await` in a function holding state, ask what happens if the future is dropped
there. Is the state still consistent?

### RS-CONC-33 [M] Do not `select!` over branches that lose data on cancellation

Do not use `select!` with branches that lose data on cancellation (a partially consumed read, a
half-sent message) unless the future is documented as cancel-safe (RS-CONC-32). Prefer a loop over a
channel with an explicit shutdown signal.

**Why:** `select!` drops the losing branches, so any partial progress inside them is discarded. With
a buffered read that means silently dropped bytes, which shows up much later as a corrupt stream.

**Check:** for each `select!` branch, is the future documented as cancel-safe? `tokio` documents
this per-method; anything undocumented should be assumed unsafe to cancel.

### RS-CONC-34 [M] Apply a caller-supplied timeout at every boundary that can hang

Apply timeouts at the boundary of any operation that can hang — network, IPC, subprocess — and make
the timeout a parameter, not a constant buried in the implementation.

**Why:** a hung operation with no timeout consumes a task or a connection forever, and enough of
them exhaust the pool. Making the value a parameter is what lets the caller — who knows the latency
budget — choose it.

**Check:** for each network or IPC call, find the timeout. A hard-coded constant is a finding, not a
mitigation.

## Data parallelism

### RS-CONC-35 [S] Reach for `rayon` — it is the highest return-on-effort parallelism in Rust

`rayon` turns a functional pipeline into a parallel one by changing `iter()` to `par_iter()`. This
is the highest return-on-effort parallelism available in Rust, and it is available only because the
pipeline was functional to begin with — which argues for the pipeline form even while the data is
small.

**Why:** a one-word change buys work-stealing parallelism with no synchronization to design, because
the iterator formulation already proved the operations are independent. This is the concrete payoff
for writing pipelines rather than loops.

**Check:** for CPU-bound loops over collections, is the body already a pure `map`/`filter`/`fold`?
If so, `par_iter` is nearly free. If `par_iter()` would not compile, what state is shared — and does
it need to be?

### RS-CONC-36 [M] Parallelize at a coarse granularity

`par_iter()` over a million one-microsecond items spends its time in the scheduler; chunk first
(`par_chunks`, `with_min_len`).

**Why:** every work item carries scheduling overhead, so items shorter than that overhead make the
parallel version slower than the sequential one. Chunking amortizes it across many items.

**Check:** estimate the per-item cost. Below roughly a microsecond, chunk before parallelizing.

### RS-CONC-37 [M] Keep the closure passed to a parallel iterator pure

Shared mutation inside means locks, which serialize exactly the thing you parallelized; use `map`
plus `reduce`/`fold` with an identity instead.

**Why:** a mutex inside a parallel closure reintroduces a global serialization point, so the program
pays the parallelism overhead and gets none of the benefit. `reduce` combines per-thread results
without any shared state.

**Check:** does the closure capture anything by mutable reference or take a lock? Both defeat the
parallelism.

### RS-CONC-38 [M] Reorder or serialize parallel output deliberately

Parallel output must be reordered or serialized deliberately. Either collect in order
(`par_iter().map(..).collect::<Vec<_>>()` preserves order) or funnel through a single writer —
ripgrep does the latter so that output for each file stays contiguous.

**Why:** parallel writes to a shared stream interleave at arbitrary boundaries, producing output
that is unusable and non-reproducible. Deciding the strategy up front is what keeps results
deterministic.

**Check:** run the parallel path twice on the same input. Different output ordering means the
strategy was not chosen.

```rust
// verified
use std::thread;

/// Collecting in order makes the parallel result deterministic.
#[must_use]
pub fn lengths(inputs: &[String]) -> Vec<usize> {
    thread::scope(|scope| {
        let handles: Vec<_> = inputs
            .iter()
            .map(|item| scope.spawn(move || item.len()))
            .collect();
        handles
            .into_iter()
            .map(|handle| handle.join().unwrap_or(0))
            .collect()
    })
}
```

## Testing and debugging

### RS-CONC-39 [M] Test a hand-written synchronization algorithm with `loom`

A lock-free structure or synchronization primitive you write yourself, rather than assemble from
`std` and `crossbeam` used in the obvious way, has `loom` tests: `loom` explores interleavings
exhaustively for small models, and ordinary tests pass on broken lock-free code essentially every
time.

**Why:** a race needs a specific interleaving, and the scheduler will not produce it in a normal
test run — so a broken structure passes indefinitely and fails in production. `loom` enumerates the
interleavings instead of sampling them.

**Check:** for each hand-written synchronization primitive, is there a `loom` test?

### RS-CONC-40 [M] Run code with `unsafe` sharing under ThreadSanitizer before every release

CI runs it on every push; where the sanitized run outgrows CI's time, it runs on a schedule and
before every release, and never having run it is the finding. Miri, for the `unsafe` itself, is
RS-UNSAFE-30.

**Why:** ThreadSanitizer detects races the test run happened not to trigger, by checking the
happens-before relation rather than the outcome. That is a categorically stronger observation than
"the assertions passed".

**Check:** does CI run the suite under ThreadSanitizer?

### RS-CONC-41 [S] Stress-test beyond core count, behind `#[ignore]`

Stress-test with more threads than cores and with a loop count high enough to shake out races, but
keep that test behind `#[ignore = "stress test: run with --ignored"]` or a feature so the fast suite
stays fast (RS-TEST-33). The reason is not optional: clippy's `ignore_without_reason` (pedantic)
rejects a bare `#[ignore]`.

**Why:** oversubscription forces preemption at points a well-behaved run never reaches, which is
what makes rare interleavings appear. It is also slow, so it belongs outside the inner loop.

**Check:** is there a stress test, and is it excluded from the default run?

### RS-CONC-42 [M] Log with a task or thread identifier

Interleaved logs without one are unreadable, and `tracing` spans exist precisely to solve this.

**Why:** with several workers the log is an interleaving of independent narratives, and without an
identifier there is no way to separate them. Reconstructing one task's sequence is usually the whole
debugging job.

**Check:** does a log line identify which worker produced it? If not, concurrent logs cannot be
read.

### RS-CONC-43 [S] Reproduce deadlocks by capturing backtraces, not by reasoning

Reproduce deadlocks by capturing all thread backtraces (`gdb -p`, `rust-gdb`, `tokio-console` for
async) rather than by reasoning. The stacks name the two locks.

**Why:** a deadlocked process is frozen with the entire evidence intact — each thread's stack shows
exactly which lock it holds and which it wants. That is a direct answer, whereas reasoning about
possible orderings is a search.

**Check:** when a hang occurs, was a backtrace captured before restarting? Restarting destroys the
evidence.

### RS-CONC-44 [M] Give every task a parent that outlives it and joins it

`thread::scope`, task groups, and `JoinSet` all encode a parent responsible for each task's
shutdown; bare `spawn`-and-forget does not.

Outside a scope, keep each handle and join it: the handle is the only channel for a task's panic or
result (RS-CONC-12). Detach only deliberately, with a comment saying why the work may be lost.

**Why:** a parent that outlives its children makes lifetimes, error propagation, and shutdown all
follow the call structure. A detached thread is killed mid-operation when `main` returns, with no
unwinding and no flush, and a detached task that panics disappears silently.

**Check:** for each spawned task, name the scope responsible for awaiting it. "Nobody" is the
finding, and so is a `spawn(` whose handle is dropped without a comment.

```rust
// verified
use std::thread::{self, JoinHandle};

/// The handles are kept and joined; nothing is detached without a decision.
#[derive(Debug, Default)]
pub struct Workers {
    handles: Vec<JoinHandle<()>>,
}

impl Workers {
    pub fn spawn(&mut self, work: impl FnOnce() + Send + 'static) {
        self.handles.push(thread::spawn(work));
    }

    /// Returns how many workers finished without panicking.
    pub fn join_all(&mut self) -> usize {
        self.handles
            .drain(..)
            .filter_map(|handle| handle.join().ok())
            .count()
    }
}
```

### RS-CONC-45 [M] Document the threading contract of every public type

State whether it is `Send`, whether it is `Sync`, whether methods may be called concurrently, and
whether it spawns anything. Users cannot infer this from the type signature alone, and getting it
wrong is expensive.

**Why:** auto traits appear in the docs but say nothing about whether concurrent method calls are
*sensible* — a `Sync` type can still have methods that must not overlap. Whether the type spawns
threads is invisible entirely.

**Check:** for each public type, do the docs answer all four questions, linking the crate-wide model
(RS-DOC-03)?

```rust
// verified
use std::sync::Mutex;

/// The threading contract is documented, because the signature cannot express it.
///
/// `Registry` is `Send + Sync`; every method may be called concurrently, and it
/// spawns no threads of its own.
#[derive(Debug, Default)]
pub struct Registry {
    entries: Mutex<Vec<String>>,
}

impl Registry {
    pub fn add(&self, name: String) {
        if let Ok(mut guard) = self.entries.lock() {
            guard.push(name);
        }
    }
}
```

## Files shared between processes

### RS-CONC-46 [M] Write output that cannot be regenerated atomically

An output the tool cannot regenerate from inputs it leaves alone — every in-place edit among them —
is written to a temporary file in the same directory, then renamed: a crash mid-write must not
destroy the user's input. Open the temporary with `File::create_new`, which fails rather than
truncate a file that is already there.

**Why:** `rename` within a filesystem is atomic, so readers see either the old file or the new one
and never a half-written one. Writing in place gives up that guarantee for nothing — the temporary
file costs one extra path.

**Check:** for each in-place edit, is there a temp-file-and-rename? Same directory matters, since
`rename` across filesystems is not atomic.

```rust
// verified
use std::{
    fs::File,
    io,
    path::{Path, PathBuf},
};

/// Write to a temporary beside the target, then rename: readers never see a partial file.
#[must_use]
pub fn staging_path(target: &Path) -> PathBuf {
    target.with_added_extension("tmp")
}

/// Opens the temporary exclusively, so it never truncates a file another run left there.
///
/// # Errors
/// Fails with `AlreadyExists` when the temporary is already there.
pub fn create_staging(target: &Path) -> io::Result<File> {
    File::create_new(staging_path(target))
}
```

## Decided by tools

A tool settles these on its own; the shipped configuration enables each at the level shown.

| Tool | Lint | Level | Forbids |
|---|---|---|---|
| clippy | `unused_async` | warn | an `async fn` that never awaits — listed because an `async fn` that never awaits colours every caller for nothing, the rule a revision demoted to it |
