# RS-CONC — Concurrency and async

Rust removes data races, not concurrency bugs. Deadlocks, livelocks, lost
wakeups, unbounded queues, and cancellation-safety violations are all still
yours to avoid. The best defence is choosing the simplest model that solves the
problem — which is very often "not async" and quite often "not concurrent".
## Contents

- **Choosing a model**
  - RS-CONC-01 [M] Do not add concurrency without a measured reason
  - RS-CONC-02 [M] Match the model to the bottleneck
  - RS-CONC-03 [M] Do not adopt async for a CLI that does a handful of file reads
  - RS-CONC-04 [M] Prefer message passing to shared memory
  - RS-CONC-05 [M] Prefer immutable sharing to synchronized mutation
  - RS-CONC-06 [S] Prefer partitioning to synchronization
  - RS-CONC-07 [M] Keep the concurrency at one layer, ideally the top
  - RS-CONC-08 [M] Decide the parallelism model before writing the data structures
  - RS-CONC-09 [M!] Bound every queue
  - RS-CONC-10 [M] Design shutdown at the start

- **Threads**
  - RS-CONC-11 [M] Use `std::thread::scope` for threads that borrow local data
  - RS-CONC-12 [M] Always handle `JoinHandle::join`'s result
  - RS-CONC-13 [M] Clone what a spawned closure needs *before* the closure
  - RS-CONC-14 [S] Size the pool from `available_parallelism()`, and let the user override
  - RS-CONC-15 [M] Do not spawn per item
  - RS-CONC-16 [S] Choose `mpsc` for simple fan-in and `crossbeam-channel` for the rest
  - RS-CONC-17 [M] Close channels deliberately
  - RS-CONC-18 [M] Never block on I/O, a send, or another lock while holding a lock
  - RS-CONC-19 [S] Prefer `park`/`unpark` and condvars to sleep-polling
  - RS-CONC-20 [M] Give any thread whose work must complete an explicit join

- **Shared state**
  - RS-CONC-21 [M] Ask three questions before reaching for `Arc<Mutex<…>>`
  - RS-CONC-22 [M] Hold locks briefly, and never across an `.await` or a blocking call
  - RS-CONC-23 [S] Treat lock granularity as a tuning parameter with evidence
  - RS-CONC-24 [S] Use `RwLock` only for read-dominated, long critical sections
  - RS-CONC-25 [M] Establish a lock order and document it
  - RS-CONC-26 [M] Decide deliberately what a poisoned `Mutex` means for your crate
  - RS-CONC-27 [M] Reserve atomics for counters, flags, and provable algorithms
  - RS-CONC-28 [M] Do not hand-build lock-free data structures
  - RS-CONC-29 [M] Treat a manual `Send`/`Sync` impl as a proof obligation
  - RS-CONC-30 [M] Use `OnceLock`/`LazyLock` for lazily initialized globals

- **Async fundamentals**
  - RS-CONC-31 [M] Remember futures are inert until polled
  - RS-CONC-32 [M] Keep libraries runtime-agnostic where possible
  - RS-CONC-33 [M] Do not block in async
  - RS-CONC-34 [M] Prefer `async fn` and `impl Future` to hand-written state machines
  - RS-CONC-35 [M] Decide explicitly whether your trait needs `Send` futures
  - RS-CONC-36 [M!] Make every function correct when dropped at an `.await`
  - RS-CONC-37 [M] Do not `select!` over branches that lose data on cancellation
  - RS-CONC-38 [M] Keep, join, or deliberately detach every task handle
  - RS-CONC-39 [M] Apply a caller-supplied timeout at every boundary that can hang

- **Data parallelism**
  - RS-CONC-40 [S] Reach for `rayon` — it is the highest return-on-effort parallelism in Rust
  - RS-CONC-41 [M] Parallelize at a coarse granularity
  - RS-CONC-42 [M] Keep the closure passed to a parallel iterator pure
  - RS-CONC-43 [M] Reorder or serialize parallel output deliberately

- **Testing and debugging**
  - RS-CONC-44 [M!] Test concurrent data structures with `loom`
  - RS-CONC-45 [M!] Run the suite under ThreadSanitizer and Miri where supported
  - RS-CONC-46 [M] Make concurrency tests deterministic — no `sleep`
  - RS-CONC-47 [S] Stress-test beyond core count, behind `#[ignore]`
  - RS-CONC-48 [M] Log with a task or thread identifier
  - RS-CONC-49 [S] Reproduce deadlocks by capturing backtraces, not by reasoning
  - RS-CONC-50 [M] Prefer structured concurrency
  - RS-CONC-51 [M] Document the threading contract of every public type
- Decided by tools

---

## Choosing a model

### RS-CONC-01 [M] Do not add concurrency without a measured reason

Do not add concurrency without a measured reason. It multiplies the state space, complicates every
error path, and makes failures non-reproducible. Sequential code that is fast enough is the right
answer.

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

Match the model to the bottleneck: threads and `rayon` for CPU-bound work, async for I/O-bound work
with many concurrent operations, and a thread pool with blocking I/O for a few dozen connections —
which is simpler than async and competitive at that scale.

**Why:** async solves the problem of holding many waiting operations cheaply; it does nothing for
CPU-bound work and actively hurts it by adding a scheduler. Threads solve CPU parallelism and cost
about a megabyte of stack each, which only matters in the thousands.

**Check:** name the bottleneck — CPU or waiting — and the expected concurrency count. The pair
determines the model.

### RS-CONC-03 [M] Do not adopt async for a CLI that does a handful of file reads

Do not adopt async for a CLI that does a handful of file reads. `tokio` brings a runtime, a
scheduler, coloured functions, and a large dependency tree; a CLI that opens fifty files should just
open them.

**Why:** async's benefit appears at high concurrency, and fifty sequential file reads have none.
What you do get is a function-colouring constraint through the whole codebase and a much larger
build (`RS-BUILD-21`).

**Check:** how many operations are in flight at once? Below a few hundred, blocking I/O on a small
pool is simpler and usually faster.

### RS-CONC-04 [M] Prefer message passing to shared memory

Prefer message passing to shared memory. Channels give you one owner per value, backpressure, and a
shutdown protocol; shared mutable state gives you locks and a graph of who may touch what.

**Why:** a channel makes the ownership transfer explicit and localizes the synchronization to one
well-tested primitive. Shared state distributes the reasoning across every site that takes the lock,
and the correctness argument has to consider all of them.

**Check:** for each `Arc<Mutex<T>>`, ask whether the mutation could be a message to a single owner.

```rust
// verified
use std::sync::mpsc;
use std::thread;

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

### RS-CONC-05 [M] Prefer immutable sharing to synchronized mutation

Prefer immutable sharing to synchronized mutation. `Arc<T>` where `T` never changes needs no lock at
all, and the vast majority of "shared state" is configuration that is written once at startup.

**Why:** immutable data is `Sync` for free, so there is no critical section, no contention, and no
deadlock risk. Most state that gets wrapped in a mutex is never actually mutated after construction.

**Check:** for each `Mutex`, find the writes after initialization. If there are none, the lock can
be deleted.

```rust
// verified
use std::sync::Arc;
use std::thread;

/// Shared immutably: `Arc<T>` where `T` never changes needs no lock at all.
#[must_use]
pub fn count_matches(haystacks: &[String], needle: &Arc<str>) -> usize {
    thread::scope(|scope| {
        let handles: Vec<_> = haystacks
            .iter()
            .map(|hay| {
                let needle = Arc::clone(needle);
                scope.spawn(move || usize::from(hay.contains(&*needle)))
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

Prefer partitioning to synchronization: give each worker its own slice of the data and merge at the
end. No lock is faster than any lock.

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

Keep the concurrency at one layer, ideally the top. A library that spawns its own threads or
requires a specific runtime constrains every application that uses it. Offer a synchronous API and
let the caller parallelize (`RS-CONC-32`).

**Why:** the application knows its own thread budget and runtime; the library does not. A library
that spawns threads cannot be used inside another parallel context without oversubscribing, and one
that requires a runtime cannot be used outside it at all.

**Check:** does the library spawn threads or require a runtime? If so, can the parallelism be lifted
to the caller?

### RS-CONC-08 [M] Decide the parallelism model before writing the data structures

Decide the parallelism model before writing the data structures. Retrofitting `Send + Sync` onto a
design built around `Rc` and `RefCell` is a rewrite, not a refactor.

**Why:** `Rc` and `RefCell` are not `Send`, and they tend to be load-bearing in the designs that use
them — a graph with parent pointers, a tree with shared nodes. Converting means changing the
ownership model, which touches everything.

**Check:** if the code might ever be parallel, are the shared types `Send`? Deciding later is much
more expensive than deciding now.

### RS-CONC-09 [M!] Bound every queue

Bound every queue. An unbounded channel converts backpressure into memory exhaustion, which surfaces
as an OOM kill hours later rather than a slow producer immediately.

**Why:** a bounded channel makes a fast producer block, which is the signal that the system is
overloaded, delivered at the point where it can be handled. Unbounded, that signal is deferred until
memory runs out, at which point the process dies with no useful diagnostic.

**Check:** grep for `unbounded` channel constructors and for `Vec` accumulators fed by a loop with
an external bound.

*Relaxed form:* a queue whose producer is a bounded, known set — a fixed list of files, a fixed
worker count — is already bounded by construction. Any queue fed by network input or user activity
is not.

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

Design shutdown at the start: how workers learn to stop, how in-flight work drains, and how the main
thread waits. Retrofitted shutdown is where hangs live.

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

Use `std::thread::scope` (stable since 1.63) for threads that borrow local data. It removes the
`Arc`/`'static` dance and guarantees joins, which is exactly the guarantee that makes borrowing
sound.

**Why:** the scope guarantees every thread is joined before it returns, which is what lets the
borrow checker accept references to local data. Without it, sharing local data requires `Arc` and
cloning even when the data outlives the threads in practice.

**Check:** grep for `Arc::new` immediately before `thread::spawn` where the data is local.

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

Always handle `JoinHandle::join`'s result. Dropping it discards a panic in the worker, turning a
crash into silently missing work.

**Why:** a panicking thread does not propagate anywhere; the panic is captured in the join result.
Ignoring that result means the program continues as if the work succeeded, producing wrong output
rather than an error.

**Check:** grep for `join()` whose result is discarded, and for `let _ =` on a `JoinHandle`.

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
shared or dropped early (`RS-FUNC-43`).

**Why:** `move` captures whatever the body names, so a body that names the outer binding moves the
original on the first iteration and fails to compile — or, with an `Arc`, captures the wrong one.
Making the clone explicit puts the intent in the source.

**Check:** each spawned closure's captures should be bindings created immediately above it.

### RS-CONC-14 [S] Size the pool from `available_parallelism()`, and let the user override

Size the pool from `std::thread::available_parallelism()`, not a hard-coded number, and let the user
override it with a flag or environment variable.

**Why:** a hard-coded count is wrong on every machine except the author's, and it ignores cgroup
limits in containers. `available_parallelism` respects those limits; the override handles the cases
it cannot know about, like sharing a machine with another job.

**Check:** grep for numeric literals used as thread counts.

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

Do not spawn per item. Thread creation costs more than most units of work; use a pool (`rayon`) or
chunk the work.

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

Use `std::sync::mpsc` for simple fan-in, `crossbeam-channel` when you need `select`, multiple
consumers, or better throughput. Both are far easier to reason about than a shared
`Mutex<VecDeque<_>>`.

**Why:** a hand-rolled queue behind a mutex has to re-solve blocking, wakeup, and shutdown, and it
usually gets the lost-wakeup case wrong. The channel types have solved all three.

**Check:** grep for `Mutex<VecDeque<` and `Mutex<Vec<` used as a work queue.

### RS-CONC-17 [M] Close channels deliberately

Close channels deliberately. A receiver loop ends when all senders drop; a forgotten clone of the
sender in the parent scope is the classic "program hangs at the end" bug (see the `drop(tx)` above).

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

### RS-CONC-18 [M] Never block on I/O, a send, or another lock while holding a lock

Do not block a thread holding a lock on I/O, a channel send, or another lock. Compute the value,
then take the lock, then store it.

**Why:** the critical section's length determines contention for every other thread, and I/O is
unbounded. Blocking on a second lock also creates the ordering that produces deadlock
(`RS-CONC-25`).

**Check:** read each critical section for I/O calls, channel sends, and further lock acquisitions.

```rust
// verified
use std::collections::HashMap;
use std::hash::BuildHasher;
use std::sync::Mutex;

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

### RS-CONC-19 [S] Prefer `park`/`unpark` and condvars to sleep-polling

Prefer `park`/`unpark` and condition variables to sleep-polling.
`thread::sleep(Duration::from_millis(10))` in a loop is both slow to react and wasteful.

**Why:** polling trades latency against CPU with no good setting — short intervals burn cycles, long
ones add latency. A condvar wakes exactly when the condition changes.

**Check:** grep for `sleep` inside loops. Each is a poll that wants a wakeup primitive.

### RS-CONC-20 [M] Give any thread whose work must complete an explicit join

Threads that outlive `main` are terminated abruptly. Any thread doing work that must complete needs
an explicit join or a shutdown handshake.

**Why:** when `main` returns the process exits and detached threads are killed mid-operation, with
no unwinding and no flush. A background writer loses its buffer that way.

**Check:** for each detached thread, ask what happens if the process exits during its work. If the
answer matters, it needs a join (`RS-CONC-50`).

## Shared state

### RS-CONC-21 [M] Ask three questions before reaching for `Arc<Mutex<…>>`

`Arc<Mutex<HashMap<..>>>` should not be the first reflex. Ask in order: can each worker own a
partition? can the map be built once and shared immutably? can updates be a channel to one owner?
Only then reach for the lock.

**Why:** each of the three alternatives eliminates the critical section rather than optimizing it,
and each is simpler to reason about. The lock is the fallback when the data genuinely must be shared
and mutable.

**Check:** for each `Arc<Mutex<_>>`, answer the three questions in writing. Reaching the lock
without answering them is the finding.

### RS-CONC-22 [M] Hold locks briefly, and never across an `.await` or a blocking call

Hold locks for the shortest possible span, and never across an `.await` or a blocking call. Compute
outside, mutate inside:

**Why:** a `std::sync` guard held across an `.await` blocks the executor thread and can deadlock,
since the task may be resumed on a different thread. Even with an async-aware mutex it serializes
every other task for the duration of the awaited operation.

**Check:** grep for `.await` between a `lock()` and the end of its scope. Clippy's
`await_holding_lock` catches the common shape.

### RS-CONC-23 [S] Treat lock granularity as a tuning parameter with evidence

Prefer a `Mutex` per subsystem over one global lock, and per-shard locks over one big map lock when
contention is measured. Lock granularity is a tuning parameter with evidence behind it, not a
default.

**Why:** finer locks reduce contention and increase the number of orderings that can deadlock, so
the trade is real in both directions. Sharding without measured contention buys complexity for
nothing.

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

### RS-CONC-24 [S] Use `RwLock` only for read-dominated, long critical sections

`RwLock` helps only when reads vastly outnumber writes and the critical sections are long. Otherwise
its extra bookkeeping loses to a plain `Mutex`, and writer starvation becomes a real risk.

**Why:** an `RwLock` does more atomic work per acquisition than a `Mutex`, so for short critical
sections the bookkeeping exceeds the parallelism gained. Depending on the implementation, continuous
readers can also starve a waiting writer indefinitely.

**Check:** what is the read/write ratio and how long is the critical section? Without both numbers,
`Mutex` is the safer default.

### RS-CONC-25 [M] Establish a lock order and document it

Establish a lock order and document it. Every deadlock in practice is two code paths taking the same
two locks in different orders.

**Why:** deadlock requires a cycle in the acquisition graph, and a global order makes cycles
impossible by construction. It is one of the few concurrency properties that can be checked by
reading.

**Check:** list every place two locks are held simultaneously and confirm the order matches the
documented one.

### RS-CONC-26 [M] Decide deliberately what a poisoned `Mutex` means for your crate

`Mutex::lock` returns a `Result` because of poisoning. In a binary, `.expect("lock poisoned")` is
defensible; in a library, propagate or use a non-poisoning mutex (`parking_lot`) and say so.

**Why:** poisoning means a thread panicked while holding the lock, so the protected invariant may be
broken. A library that unwraps decides on the application's behalf that the process should die.

**Check:** grep for `.lock().unwrap()` in library code. Each is an undocumented panic (`RS-DOC-13`).

### RS-CONC-27 [M] Reserve atomics for counters, flags, and provable algorithms

Atomics are for counters, flags, and lock-free algorithms written by people who can prove them
correct. Use `Relaxed` for statistics, `Acquire`/`Release` for handoff, and `SeqCst` when you are
not sure — then learn why you were not sure. For a read-modify-write no single `fetch_*` method
covers, call `update` or `try_update` (1.95) rather than writing a `compare_exchange` loop;
`fetch_update` is deprecated since 1.99, and its warning fails a build that denies warnings.

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

### RS-CONC-28 [M] Do not hand-build lock-free data structures

Do not build lock-free data structures by hand. Use `crossbeam`, `dashmap`, or an actor with a
channel. The literature is full of published algorithms that turned out to be wrong.

**Why:** lock-free correctness depends on reclamation and ordering interactions that ordinary
testing cannot observe, and peer-reviewed algorithms have shipped with bugs found years later. The
libraries have been verified with `loom` and used at scale.

**Check:** is there hand-written `compare_exchange` in the crate? If so, is it a published
algorithm, and is it `loom`-tested (`RS-CONC-44`)? A retry loop that only recomputes one value is an
`update` or `try_update` call (`RS-CONC-27`).

### RS-CONC-29 [M] Treat a manual `Send`/`Sync` impl as a proof obligation

`Send` and `Sync` are auto-derived; implementing them manually is `unsafe` and requires a proof
(`RS-UNSAFE-21`). If a type is not `Send`, the compiler is telling you something true.

**Why:** the compiler withheld the impl because of a field it cannot verify — a raw pointer, a
`Cell`. The manual impl asserts you have synchronized it, and if you have not the result is a data
race with no diagnostic.

**Check:** each manual impl has an adjacent comment naming what makes concurrent access sound.

### RS-CONC-30 [M] Use `OnceLock`/`LazyLock` for lazily initialized globals

Use `OnceLock`/`LazyLock` for lazily initialized globals rather than `static mut` (which edition
2024 denies via `static_mut_refs`) or a `Mutex<Option<T>>` (`RS-OWN-27`).

**Why:** these types give a safe, race-free single initialization with no lock on the read path
after it. A `Mutex<Option<T>>` pays for a lock on every access to emulate the same thing.

**Check:** grep for `static mut` and `Mutex<Option<`. Clippy's `non_std_lazy_statics` (pedantic)
already flags `lazy_static!` and `once_cell::sync::Lazy`.

```rust
// verified
use std::sync::LazyLock;

/// `LazyLock` initializes once with no lock on the read path afterwards.
static PREFIXES: LazyLock<Vec<&'static str>> = LazyLock::new(|| vec!["tmp", "cache"]);

#[must_use]
pub fn is_ignored(name: &str) -> bool {
    PREFIXES.iter().any(|prefix| name.starts_with(prefix))
}
```

## Async fundamentals

### RS-CONC-31 [M] Remember futures are inert until polled

Futures are inert. Nothing happens until they are polled — so building a future and dropping it does
no work, and a `Vec<Future>` runs nothing until you `join_all` or spawn.

**Why:** this is the fundamental difference from languages where calling an async function starts
it. It means an un-awaited future is a silent no-op rather than background work, which is the source
of the most common async surprise.

**Check:** grep for calls to `async fn` whose result is not awaited, spawned, or collected into a
joiner. The `unused_must_use` warning catches most.

```rust
// verified
use std::future::ready;

/// Futures are inert: `pending` is constructed and does nothing until it is awaited.
pub async fn doubled(value: u32) -> u32 {
    let pending = ready(value * 2);
    pending.await
}
```

### RS-CONC-32 [M] Keep libraries runtime-agnostic where possible

Libraries should be runtime-agnostic where possible: depend on `futures`/`std` traits rather than
`tokio` internals, and gate runtime-specific code behind features. A library that hard-requires one
runtime excludes half the ecosystem.

**Why:** the runtime is an application-level choice, and two runtimes cannot generally coexist. A
library that picks one makes itself unusable to everyone who picked the other, for a dependency the
library did not need to expose.

**Check:** does the library depend on a runtime unconditionally? If so, can the dependency be
feature-gated?

### RS-CONC-33 [M] Do not block in async

Do not block in async. A synchronous file read, a `std::sync` lock held across a poll, or a
CPU-bound loop stalls the whole executor thread. Use `spawn_blocking` for blocking work and the
async equivalents for I/O.

**Why:** an executor thread runs many tasks cooperatively, so a blocking call stops all of them, not
just the caller. On a multi-threaded runtime that is one core lost; if every worker blocks, the
runtime deadlocks.

**Check:** grep async bodies for `std::fs`, `std::net`, `thread::sleep`, and `std::sync::Mutex`.

### RS-CONC-34 [M] Prefer `async fn` and `impl Future` to hand-written state machines

Prefer `async fn` and `impl Future` over hand-written `Poll` state machines. Implement `Future` by
hand only for leaf primitives — and then respect the contract: register the waker on every `Pending`
return.

**Why:** the compiler generates a correct state machine, including the waker handling that
hand-written implementations get wrong. A `Pending` return without a registered waker is a task that
never wakes — a hang with no diagnostic.

**Check:** for each manual `impl Future`, confirm every `Pending` path registered the waker first.

### RS-CONC-35 [M] Decide explicitly whether your trait needs `Send` futures

`async fn` in traits (stable since 1.75) does not produce a `Send` future automatically, and is not
dyn-compatible. Decide explicitly whether your trait needs `Send` futures (`trait_variant`, or an
explicit `-> impl Future<Output = _> + Send`) and document it (`RS-TRAIT-20`). The same decision
governs an async callback: take an `AsyncFn` bound (1.85) rather than `F: Fn() -> Fut, Fut: Future`,
unless the callback's future must be `Send` — stable Rust cannot yet state that of an `AsyncFn`.

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

### RS-CONC-36 [M!] Make every function correct when dropped at an `.await`

Cancellation in async is a drop, and it can happen at any `.await` point. Any function holding a
resource across an await must be correct when it is dropped there — this is cancellation safety, and
`select!` makes it a routine concern rather than an exotic one.

**Why:** there is no cancellation notification and no async destructor, so cleanup has to work
through ordinary `Drop`. A half-consumed read or a half-sent message dropped mid-operation loses
data silently.

**Check:** for each `.await` in a function holding state, ask what happens if the future is dropped
there. Is the state still consistent?

*Relaxed form:* code that never appears inside a `select!`, a `timeout`, or a task that gets aborted
is cancelled only at shutdown, where a leaked temporary is tolerable. The moment either appears, the
rule is [M].

### RS-CONC-37 [M] Do not `select!` over branches that lose data on cancellation

Do not use `select!` with branches that lose data on cancellation (a partially consumed read, a
half-sent message) unless the future is documented as cancel-safe. Prefer a loop over a channel with
an explicit shutdown signal.

**Why:** `select!` drops the losing branches, so any partial progress inside them is discarded. With
a buffered read that means silently dropped bytes, which shows up much later as a corrupt stream.

**Check:** for each `select!` branch, is the future documented as cancel-safe? `tokio` documents
this per-method; anything undocumented should be assumed unsafe to cancel.

### RS-CONC-38 [M] Keep, join, or deliberately detach every task handle

Every spawned task returns a handle: keep it, join it, or deliberately detach with a comment. A
detached task that panics disappears silently, and its failure becomes an unexplained absence of
output.

**Why:** the handle is the only channel through which a task's panic or result is reported — the
same reason `JoinHandle::join` must be handled (`RS-CONC-12`). Dropping it discards both, so the
failure is indistinguishable from success.

**Check:** grep for `spawn(` whose result is dropped without a comment.

```rust
// verified
use std::thread::{self, JoinHandle};

/// The handle is kept and joined; nothing is detached without a decision.
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
            .filter(|_| true)
            .filter_map(|h| h.join().ok())
            .count()
    }
}
```

### RS-CONC-39 [M] Apply a caller-supplied timeout at every boundary that can hang

Apply timeouts at the boundary of any operation that can hang — network, IPC, subprocess — and make
the timeout a parameter, not a constant buried in the implementation.

**Why:** a hung operation with no timeout consumes a task or a connection forever, and enough of
them exhaust the pool. Making the value a parameter is what lets the caller — who knows the latency
budget — choose it.

**Check:** for each network or IPC call, find the timeout. A hard-coded constant is a finding, not a
mitigation.

## Data parallelism

### RS-CONC-40 [S] Reach for `rayon` — it is the highest return-on-effort parallelism in Rust

`rayon` turns a functional pipeline into a parallel one by changing `iter()` to `par_iter()`. This
is the highest return-on-effort parallelism available in Rust, and it is available only because the
pipeline was functional to begin with (`RS-FUNC-25`).

**Why:** a one-word change buys work-stealing parallelism with no synchronization to design, because
the iterator formulation already proved the operations are independent. This is the concrete payoff
for writing pipelines rather than loops.

**Check:** for CPU-bound loops over collections, is the body already a pure `map`/`filter`/`fold`?
If so, `par_iter` is nearly free.

### RS-CONC-41 [M] Parallelize at a coarse granularity

Parallelize at a coarse granularity. `par_iter()` over a million one-microsecond items spends its
time in the scheduler; chunk first (`par_chunks`, `with_min_len`).

**Why:** every work item carries scheduling overhead, so items shorter than that overhead make the
parallel version slower than the sequential one. Chunking amortizes it across many items.

**Check:** estimate the per-item cost. Below roughly a microsecond, chunk before parallelizing.

### RS-CONC-42 [M] Keep the closure passed to a parallel iterator pure

Keep the closure passed to a parallel iterator pure. Shared mutation inside means locks, which
serialize exactly the thing you parallelized; use `map` plus `reduce`/`fold` with an identity
instead.

**Why:** a mutex inside a parallel closure reintroduces a global serialization point, so the program
pays the parallelism overhead and gets none of the benefit. `reduce` combines per-thread results
without any shared state.

**Check:** does the closure capture anything by mutable reference or take a lock? Both defeat the
parallelism.

### RS-CONC-43 [M] Reorder or serialize parallel output deliberately

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

### RS-CONC-44 [M!] Test concurrent data structures with `loom`

Test concurrent data structures with `loom`, which explores interleavings exhaustively for small
models. Ordinary tests pass on broken lock-free code essentially every time.

**Why:** a race needs a specific interleaving, and the scheduler will not produce it in a normal
test run — so a broken structure passes indefinitely and fails in production. `loom` enumerates the
interleavings instead of sampling them.

**Check:** for each hand-written synchronization primitive, is there a `loom` test?

*Relaxed form:* if all your synchronization comes from `std` and `crossbeam` primitives used in the
obvious way, `loom` buys little. It is mandatory the moment you write the algorithm rather than call
one.

### RS-CONC-45 [M!] Run the suite under ThreadSanitizer and Miri where supported

Run the suite under ThreadSanitizer for anything with `unsafe` sharing, and under Miri where it
supports the operations used (`RS-UNSAFE-30`).

**Why:** these tools detect races the test run happened not to trigger, by checking the
happens-before relation rather than the outcome. That is a categorically stronger observation than
"the assertions passed".

**Check:** does CI include the tool matching what the crate contains?

*Relaxed form:* run them before each release rather than per push. A crate with no `unsafe` sharing
has nothing here to check.

### RS-CONC-46 [M] Make concurrency tests deterministic — no `sleep`

Make concurrency tests deterministic: fixed seeds, injected clocks, and explicit synchronization
points instead of `sleep`. A test that sleeps to "let the thread finish" is a flake with a timer.

**Why:** a sleep encodes an assumption about timing that holds on your machine and fails on a loaded
CI runner. The resulting flake is then "fixed" by increasing the sleep, which makes the suite slower
without making it correct (`RS-TEST-17`).

**Check:** grep tests for `sleep`. Each wants a barrier, a channel, or a condvar instead.

### RS-CONC-47 [S] Stress-test beyond core count, behind `#[ignore]`

Stress-test with more threads than cores and with a loop count high enough to shake out races, but
keep that test behind `#[ignore = "stress test: run with --ignored"]` or a feature so the fast suite
stays fast (`RS-TEST-39`). The reason is not optional: clippy's `ignore_without_reason` (pedantic)
rejects a bare `#[ignore]`.

**Why:** oversubscription forces preemption at points a well-behaved run never reaches, which is
what makes rare interleavings appear. It is also slow, so it belongs outside the inner loop.

**Check:** is there a stress test, and is it excluded from the default run?

### RS-CONC-48 [M] Log with a task or thread identifier

Log with a task or thread identifier. Interleaved logs without one are unreadable, and `tracing`
spans exist precisely to solve this.

**Why:** with several workers the log is an interleaving of independent narratives, and without an
identifier there is no way to separate them. Reconstructing one task's sequence is usually the whole
debugging job.

**Check:** does a log line identify which worker produced it? If not, concurrent logs cannot be
read.

### RS-CONC-49 [S] Reproduce deadlocks by capturing backtraces, not by reasoning

Reproduce deadlocks by capturing all thread backtraces (`gdb -p`, `rust-gdb`, `tokio-console` for
async) rather than by reasoning. The stacks name the two locks.

**Why:** a deadlocked process is frozen with the entire evidence intact — each thread's stack shows
exactly which lock it holds and which it wants. That is a direct answer, whereas reasoning about
possible orderings is a search.

**Check:** when a hang occurs, was a backtrace captured before restarting? Restarting destroys the
evidence.

### RS-CONC-50 [M] Prefer structured concurrency

Prefer structured concurrency: every task has a parent that outlives it and is responsible for its
shutdown. `thread::scope`, task groups, and `JoinSet` all encode this; bare `spawn`-and-forget does
not.

**Why:** a parent that outlives its children makes lifetimes, error propagation, and shutdown all
follow the call structure, so they can be reasoned about locally. Detached tasks have none of those
properties and no owner to fix them.

**Check:** for each spawned task, name the scope responsible for awaiting it. "Nobody" is the
finding.

### RS-CONC-51 [M] Document the threading contract of every public type

Document the threading contract of every public type: whether it is `Send`, whether it is `Sync`,
whether methods may be called concurrently, and whether it spawns anything. Users cannot infer this
from the type signature alone, and getting it wrong is expensive.

**Why:** auto traits appear in the docs but say nothing about whether concurrent method calls are
*sensible* — a `Sync` type can still have methods that must not overlap. Whether the type spawns
threads is invisible entirely.

**Check:** for each public type, do the docs answer all four questions (`RS-DOC-05`)?

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

## Decided by tools

A tool settles these on its own; the shipped configuration enables each at the level shown.

| Tool | Lint | Level | Forbids |
|---|---|---|---|
| clippy | `unused_async` | warn | an `async fn` that never awaits |
