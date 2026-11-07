# Concurrency

Scope: work that runs at the same time: who starts and owns a task, how a task is stopped and how
long it may wait, what must not block the thread that runs other tasks, and how state is shared
between threads or tasks, how a lazily built value is made once, and how a file other processes read
is replaced. How a test waits for a task is the testing chapter's; what concurrency costs is the
performance chapter's; where a task's output goes is the output chapter's.

## Contents

- **Starting and owning tasks**
  - AS-CONC-01 [M] Start the runtime once, at the program's entry, and let a library receive it
  - AS-CONC-02 [M] Give every task an owner that waits for it
- **Cancellation and time**
  - AS-CONC-03 [M] Never swallow a cancellation
  - AS-CONC-04 [M] Leave no state half-updated at a point where a task can be cancelled
  - AS-CONC-05 [M] Protect only the step that must finish from cancellation, and bound it
  - AS-CONC-06 [M] Give every wait on an outside party a timeout
- **Not blocking the scheduler**
  - AS-CONC-07 [M] Never block the thread that runs other tasks
  - AS-CONC-08 [M] Do not mark a function asynchronous unless it waits
- **Sharing state**
  - AS-CONC-09 [M] Share data that no task writes without a lock
  - AS-CONC-10 [S] Give each worker its own data, and combine the results once
  - AS-CONC-11 [M] Hand work between tasks through a queue, not a structure behind a lock
  - AS-CONC-12 [M] Bound every queue that a producer can outrun
  - AS-CONC-13 [M] Hold a lock for the shortest span, and never across a call that waits
- **Building and replacing what others share**
  - AS-CONC-14 [M] Build a lazily created shared value once, under synchronisation
  - AS-CONC-15 [M] Replace a file others read by renaming a finished temporary over it

---

## Starting and owning tasks

### AS-CONC-01 [M] Start the runtime once, at the program's entry, and let a library receive it

The program creates the machinery that runs its tasks in one place, at its entry point, and passes
it or its handle down; code below that point neither creates a second one nor requires a particular
one. The entry point knows the thread budget and the runtime the application chose, and a library
that starts its own, or insists on one, cannot be used inside another program's choice without
fighting it.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-CONC-23 | realises | [M] | |
| rust-style | RS-CONC-07 | realises | [M] | |
| zig-style | ZS-CONC-01 | realises | [M] | |

### AS-CONC-02 [M] Give every task an owner that waits for it

A task that is started has a scope that is responsible for it: it waits for the task, receives its
result or its failure, and cancels it on the way out. Nothing is started and forgotten. A task that
nobody waits for loses its failure, outlives the work that asked for it, and is cut off
mid-operation when the program ends.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-CONC-24 | realises | [M] | |
| rust-style | RS-CONC-44 | realises | [M] | |
| zig-style | ZS-CONC-19 | realises | [M] | |

## Cancellation and time

### AS-CONC-03 [M] Never swallow a cancellation

A request to stop a task is a signal the task passes on: it cleans up and lets the signal continue
to its owner. Catching it and carrying on makes the task impossible to stop, so a shutdown becomes a
hang and a timeout never takes effect.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-CONC-25 | realises | [M] | |
| rust-style | | absent | | A future is cancelled by being dropped, and a drop is not a signal the future can catch and carry on from, so there is nothing to swallow; the cleanup it owes is AS-CONC-04's |
| zig-style | ZS-CONC-22 | realises | [M] | |

### AS-CONC-04 [M] Leave no state half-updated at a point where a task can be cancelled

Every point where a task waits is a point where it may be stopped and never resume. A change made in
two steps around such a point is arranged so that the stop leaves the state valid: the waiting comes
before the first step, or the first step is undone on the way out. Whoever shares the state next
sees what was left, and no error reports it.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-CONC-26 | realises | [M] | |
| rust-style | RS-CONC-32 | realises | [M] | |
| zig-style | ZS-CONC-25 | realises | [M] | |

### AS-CONC-05 [M] Protect only the step that must finish from cancellation, and bound it

A step whose partial completion cannot be recovered, such as writing a commit record or releasing
what the task holds, is shielded from cancellation, and nothing around it is. The protected region
is the smallest one, and a large one carries a timeout of its own, since protection defeats the
mechanism that shutdown and timeouts rest on.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-CONC-27 | realises | [M] | |
| rust-style | | absent | | A drop runs no further wait, so a cleanup has no cancellation point to protect; the work that must finish moves to a task that outlives the future or to a synchronous drop, which AS-CONC-02 and AS-CONC-04 already state |
| zig-style | ZS-CONC-24 | realises | [M] | |

### AS-CONC-06 [M] Give every wait on an outside party a timeout

A wait on a peer, a network, a child process or a queue that something else fills is bounded, and
the bound is a parameter the caller supplies, since the caller knows the budget. A wait without one
holds its task, and everything the task holds, for as long as the other side stays silent.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-CONC-28 | realises | [M] | |
| rust-style | RS-CONC-34 | realises | [M] | |
| zig-style | ZS-CONC-31 | realises | [M] | |

## Not blocking the scheduler

### AS-CONC-07 [M] Never block the thread that runs other tasks

Tasks that share a thread take turns by waiting, so a call that blocks the thread stops them all,
not only its caller. Blocking input and output, a lock of the operating system, and a long
computation with no point at which to yield are moved to a thread meant for blocking, or replaced by
the form that waits cooperatively.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-CONC-29 | realises | [M] | |
| rust-style | RS-CONC-29 | realises | [M] | |
| zig-style | ZS-CONC-26 | realises | [M] | |

### AS-CONC-08 [M] Do not mark a function asynchronous unless it waits

A function that never waits is an ordinary function. Declaring it asynchronous forces every caller
to be asynchronous as well, up to the entry point, and buys nothing in return.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-CONC-30 | realises | [M] | |
| rust-style | `unused_async` | decided | | Clippy warns on an `async fn` that never awaits, so the standard states no rule of its own |
| zig-style | | absent | | Zig has no function colour: a task is started with `io.async` on an ordinary function, and a function that does not wait takes no `Io` parameter |

## Sharing state

### AS-CONC-09 [M] Share data that no task writes without a lock

Data built once and only read afterwards is handed to every task as it is, immutable, with no lock
around it. Where a task would otherwise write what others hold, it returns a new value instead. A
value that cannot change has no race, and a lock around it is paid for by every reader.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-CONC-09 | realises | [M] | |
| rust-style | RS-CONC-05 | realises | [M] | |
| zig-style | ZS-CONC-32 | realises | [M] | |

### AS-CONC-10 [S] Give each worker its own data, and combine the results once

Each worker takes its own part of the input and its own place to put a result, and the parts are
merged after the workers have finished. Workers that share nothing while they run do not wait for
each other, and the work scales with them; the merge is a single step.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-CONC-04 | realises | [S] | |
| rust-style | RS-CONC-06 | realises | [S] | |
| zig-style | ZS-CONC-34 | realises | [S] | |

### AS-CONC-11 [M] Hand work between tasks through a queue, not a structure behind a lock

When tasks pass data to one another, the producers put it into a queue and one task takes it out and
acts on it, so that task owns the state the items change. A queue gives each item one owner at a
time, a limit on how much waits, and a way to say that the stream has ended; a container behind a
lock gives up all three and leaves a graph of who may touch what.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-CONC-10 | realises | [M] | |
| rust-style | RS-CONC-04 | realises | [M] | |
| zig-style | ZS-CONC-33 | realises | [M] | |

### AS-CONC-12 [M] Bound every queue that a producer can outrun

A queue fed by input the program does not control, such as requests, messages or lines read, has a
fixed capacity chosen from how much work may wait, and a full queue makes the producer wait. An
unbounded queue turns a burst into memory, and the process fails hours later, far from the cause.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-CONC-11 | realises | [M] | |
| rust-style | RS-CONC-09 | realises | [M] | |
| zig-style | ZS-CONC-40 | realises | [M] | |

### AS-CONC-13 [M] Hold a lock for the shortest span, and never across a call that waits

A lock covers the change to the shared value and nothing else: whatever the later work needs is
copied out and used after the lock is released. A lock still held while the task waits, or while it
calls code it does not control or takes a second lock, makes every other task wait as long as the
slowest peer takes, and is the shape of every deadlock.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-CONC-21 | realises | [M] | |
| rust-style | RS-CONC-20 | realises | [M] | |
| zig-style | ZS-CONC-35 | realises | [M] | |

## Building and replacing what others share

### AS-CONC-14 [M] Build a lazily created shared value once, under synchronisation

A value that the first task to need it builds is built exactly once. Whether it is built yet is
asked under the same synchronisation that guards the build, or by a construct made for the purpose,
and a cache or memo decorator that is not single-flight does not provide it. Two tasks that both see
the value missing both build it, and the second result replaces the first or leaks.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-CONC-16 | realises | [M] | |
| rust-style | RS-CONC-27 | realises | [M] | |
| zig-style | ZS-CONC-36 | realises | [M] | |

### AS-CONC-15 [M] Replace a file others read by renaming a finished temporary over it

A file that another process reads, or that is read, changed and written back, is replaced by writing
the new contents to a temporary file beside it and renaming that over the original. Opening the
original for writing truncates it, so a reader or a crash finds it empty or half-written and the old
contents are gone; a rename within one filesystem is atomic. A file regenerated from scratch on
every run may be written in place.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-CONC-22 | realises | [M] | |
| rust-style | RS-CONC-46 | realises | [M] | |
| zig-style | ZS-CONC-16 | realises | [M] | |
