# Concurrency: Threads, Tasks, Shared State, Cancellation, Iterators, Caches, and Context

Scope: writing Python that is correct when work runs at the same time — what the GIL used to make
unlikely, which standard-library objects hold their own locks and which do not, how to share an
iterator, how caches and context behave, how to ask which build is running, and, for `asyncio`, how
a program starts and owns its tasks, cancels them, bounds its waits and keeps blocking work off the
loop. The shape of the data being shared is in the data chapter; interpreter and allocator overhead,
and when threads beat processes, are in the performance chapter; what a free-threaded wheel declares
is in the build chapter; what only `asyncio` has is in the async chapter.

Unless a block shows its own imports, it assumes `import threading` and that the module runs on the
free-threaded build. Where a rule depends on the build, the block probes it rather than assuming.

## Contents

- **What the GIL guaranteed, and what it does not**
  - PS-CONC-01 [M] Probe the build with `sys.abi_info` and the runtime with `sys._is_gil_enabled`
  - PS-CONC-02 [M] Never treat a compound assignment as one step
  - PS-CONC-03 [M] Never treat check-then-act as one step
  - PS-CONC-04 [S] Accumulate per thread on a hot path, and merge once
  - PS-CONC-05 [M] Cite the thread-safety guarantees page, never the FAQ's bytecode argument
  - PS-CONC-06 [M] Name the invariant a lock guards, on the line that creates it
  - PS-CONC-07 [M] Never read `frame.f_locals` for a frame executing in another thread
- **Sharing objects between threads**
  - PS-CONC-08 [M] Snapshot a container before iterating what another thread may mutate
  - PS-CONC-09 [M] Send an immutable message rather than sharing a mutable object
  - PS-CONC-10 [M] Hand work between threads with `queue.Queue`
  - PS-CONC-11 [M] Bound every `queue.Queue` that a producer can outrun with `maxsize`
  - PS-CONC-12 [S] Keep a shared object's lock inside the object that owns it
- **Iterators and generators**
  - PS-CONC-13 [M] Serialise a shared iterator with `threading.serialize_iterator`
  - PS-CONC-14 [M] Give each consumer a full stream with `threading.concurrent_tee`
  - PS-CONC-15 [S] Publish a thread-safe iterator factory with `threading.synchronized_iterator`
- **Caches, memoisation, and context**
  - PS-CONC-16 [M] Never rely on `lru_cache` or `cached_property` to run a body once
  - PS-CONC-17 [M!] Put a lock around a memo whose miss is expensive or has an effect
  - PS-CONC-18 [M] Create every `ContextVar` at module scope
  - PS-CONC-19 [M] Never rely on a thread inheriting context; the default differs by build
- **Streams, randomness, and hold times**
  - PS-CONC-20 [M] Write each record to a shared text stream in one call, never with `print`
  - PS-CONC-21 [M] Give each thread its own `random.Random`
  - PS-CONC-22 [M] Hold a context in a generator with `with`, not with a decorator
  - PS-CONC-23 [M] Never hold a lock across a call you do not control
- **Starting and owning tasks**
  - PS-CONC-24 [M] Enter with `asyncio.run`, and configure with `loop_factory`
  - PS-CONC-25 [M] Start every task inside a `TaskGroup`
- **Cancellation and timeouts**
  - PS-CONC-26 [M] Never swallow `CancelledError`
  - PS-CONC-27 [M] Leave no state half-updated across an `await`
  - PS-CONC-28 [M] Shield only what must not be interrupted, and bound it
  - PS-CONC-29 [M] Give every wait a timeout, with `asyncio.timeout`
- **Blocking and colour**
  - PS-CONC-30 [M] Never run blocking work on the event loop; move it with `asyncio.to_thread`
  - PS-CONC-31 [M] Do not mark a function `async` unless it awaits

---

## What the GIL guaranteed, and what it does not

### PS-CONC-01 [M] Probe the build with `sys.abi_info` and the runtime with `sys._is_gil_enabled`

They answer different questions. `sys.abi_info.free_threaded` says how the interpreter was built, as
a documented `bool`, and is fixed for the process. `sys._is_gil_enabled()` says whether the GIL is
off *right now*, which can change after startup. It returns `True` unconditionally on a GIL build,
so it cannot identify the build on its own, and the leading underscore is load-bearing: the docs
mark it a CPython implementation detail that is "not guaranteed to exist in all implementations".

**Why:** a free-threaded build can re-enable the GIL at import time, process-wide and for the life
of the process: one dependency is enough, and only a `RuntimeWarning` says so. So the build answers
"which wheel do I need"; only the runtime probe answers "am I actually running in parallel".

**Check:** every use of `sys._is_gil_enabled` in packaging, build, or wheel-selection code is a
defect — that decision belongs to `sys.abi_info`. Every bare call without a `getattr` guard is a
defect in code that must run on another implementation. So is comparing
`sysconfig.get_config_var("Py_GIL_DISABLED")`, an untyped `0` or `1`, where the `bool` is there.

```python
# verified — GOOD
import sys
from typing import Final

FREE_THREADED_BUILD: Final = sys.abi_info.free_threaded


def running_in_parallel() -> bool:
    """Is the GIL off now? Guarded: the probe is a CPython detail."""
    probe = getattr(sys, "_is_gil_enabled", None)
    if not FREE_THREADED_BUILD or probe is None:
        return False
    return not probe()


assert isinstance(running_in_parallel(), bool)
```

### PS-CONC-02 [M] Never treat a compound assignment as one step

`counter += 1`, `totals[key] += 1`, `self.seen |= other` are each a read, a computation, and a
write. Another thread can land between any two of them.

**Why:** this was never atomic; what changed is the odds. Under the GIL a switch had to fall in a
window a few bytecodes wide, so the bug survived for years. On the free-threaded build, eight
threads each adding one to a shared attribute 200,000 times finish around 73% short, silently.

**Check:** `rg -n '^[ \t]*(self\.)?[A-Za-z_][A-Za-z0-9_]*(\[[^]\n]*\])?[ \t]*([+*|&^-]|//)=' src/`
and read each hit: is the target reachable from more than one thread? A module-level name, an
attribute of a shared instance, and any dict or list that a worker was handed all are.

```python
# verified — BAD: this is the measured 73% loss, made deterministic
import threading

counter = 0
start = threading.Barrier(4)


def bump() -> None:
    global counter
    start.wait()
    for _ in range(20_000):
        seen = counter  # the read and the write are separate steps, and
        counter = seen + 1  # another thread writes between them


threads = [threading.Thread(target=bump) for _ in range(4)]
for thread in threads:
    thread.start()
for thread in threads:
    thread.join()
assert counter <= 80_000, "80000 is the answer only if nothing interleaved"
```

```python
# verified — GOOD
import threading

_lock = threading.Lock()  # guards: totals, each update read and written as one step
totals = {"bumps": 0}


def bump() -> None:
    for _ in range(20_000):
        with _lock:
            totals["bumps"] += 1


threads = [threading.Thread(target=bump) for _ in range(4)]
for thread in threads:
    thread.start()
for thread in threads:
    thread.join()
assert totals["bumps"] == 80_000
```

### PS-CONC-03 [M] Never treat check-then-act as one step

`if key not in cache: cache[key] = compute(key)` is two operations with a gap. So are
`if not os.path.exists(p): open(p, "w")`, `if q: item = q.pop()`, and every `if x is None: x = ...`
on shared state. `dict.setdefault` performs the whole check-and-insert under one lock; a `Lock` does
the same for anything larger.

**Why:** both halves can be individually atomic and the pair still wrong: the container's lock is
released between them, so two threads both see the key absent and both compute. Whenever `compute`
writes a file, charges an account, or increments a metric, that is a duplicated side effect.

**Check:** `rg -nB2  'if .* not in |if not .*\.(exists|get)\(' src/` — a hit whose next line writes
to the thing just tested is a defect unless a lock spans both.

```python
# verified — GOOD
import threading

_registry: dict[str, int] = {}
_registry_lock = threading.Lock()  # guards: one id per name in _registry


def register(name: str) -> None:
    """Give `name` the next id, unless it already has one."""
    with _registry_lock:
        # setdefault would do for a pure computation; the lock is here
        # because the id is the count, which another thread may be
        # assigning from at the same moment.
        if name not in _registry:
            _registry[name] = len(_registry)


def id_of(name: str) -> int:
    """Return the id `register` gave `name`; does not assign one."""
    return _registry[name]


for name in ("a", "b", "a"):
    register(name)
assert (id_of("a"), id_of("b")) == (0, 1)
```

### PS-CONC-04 [S] Accumulate per thread on a hot path, and merge once

A worker that touches shared state on every iteration spends its time on cache-line ping-pong: give
each thread a local accumulator, and merge once at the end. Off the hot path, one lock held across
the whole read-modify-write is enough. The lock is what makes an update *right* and the accumulator
what makes it *scale*; an update with neither is PS-CONC-02's defect. One lock held across the whole
update on a hot path too is correct and only slower.

**Why:** every write to an object shared across cores is an atomic operation on its reference count
as well as its value, which the free-threaded build pays on a slow path: a documented four-thread
case took 3.61s against the GIL build's 2.38s, and 0.83s once its shared objects were thread-local.

**Check:** in any function passed to `Thread(target=...)` or an executor's `submit`, every name that
is not a parameter or a local is a candidate. A write to one on a hot path, rather than to a local
accumulator merged once, is the finding.

```python
# verified — GOOD
import threading
from collections import Counter

_totals: Counter[str] = Counter()
_totals_lock = threading.Lock()  # guards: _totals, merged one tally at a time


def tally(words: list[str]) -> None:
    """One lock acquisition per thread, not one per word."""
    local: Counter[str] = Counter()
    for word in words:
        local[word] += 1  # local: no other thread can see it
    with _totals_lock:
        _totals.update(local)


threads = [threading.Thread(target=tally, args=(["a", "b", "a"],)) for _ in range(4)]
for thread in threads:
    thread.start()
for thread in threads:
    thread.join()
assert _totals == Counter({"a": 8, "b": 4})
```

### PS-CONC-05 [M] Cite the thread-safety guarantees page, never the FAQ's bytecode argument

A lock-free design rests on *Thread Safety Guarantees*, the page that documents each built-in type's
operations under free threading. There `L.append(x)`, `D[x] = y` and `D1.update(D2)` are atomic,
`L.sort()` is not, and no operation that makes more than one access is. The library FAQ still lists
`L.sort()` and still explains its list by saying each bytecode instruction is atomic.

**Why:** bytecode atomicity was the GIL, and readers generalise from a reason: `d[k] += 1` follows
from it and was never safe. The guarantees page states each operation instead of a reason, and says
outright that read-modify-write and check-then-act are not atomic.

**Check:** a comment or docstring justifying the absence of a lock by appealing to the GIL, to
bytecode atomicity, or to "CPython guarantees" is the finding.
`rg -ni 'gil (makes|means|guarantees)|atomic (because|since)|bytecode is atomic' src/`

### PS-CONC-06 [M] Name the invariant a lock guards, on the line that creates it

`self._lock = threading.Lock()  # guards: len(self._lines) <= self._limit`. An invariant spanning
two operations, such as "the list and the counter agree", is yours to hold: a container's own lock
covers one operation (PS-CONC-05), and the gap between two is PS-CONC-03's.

**Why:** the invariant decides which operations the lock must span, and a reader can check that only
when it is written down. A lock whose invariant has no name drifts too narrow, reopening the gap, or
too wide, serialising work it never needed to.

**Check:** every `Lock()`, `RLock()` and `Condition()`. One with no `# guards:` comment naming its
invariant is the finding; a lock whose invariant cannot be named is unnecessary or too narrow.

```python
# verified — GOOD
import threading


class BoundedLog:
    """The newest lines, at most `limit` of them."""

    def __init__(self, limit: int) -> None:
        """Hold no more than `limit` lines."""
        self._limit = limit
        self._lock = threading.Lock()  # guards: len(self._lines) <= self._limit
        self._lines: list[str] = []

    def add(self, line: str) -> None:
        """Append `line`, dropping the oldest once the log is full."""
        # The bound is the invariant, so the lock spans the test and the
        # append.
        with self._lock:
            if len(self._lines) >= self._limit:
                del self._lines[0]
            self._lines.append(line)

    def lines(self) -> tuple[str, ...]:
        """Return a snapshot, oldest first."""
        with self._lock:
            return tuple(self._lines)


recent = BoundedLog(2)
for line in ("x", "y", "z"):
    recent.add(line)
assert recent.lines() == ("y", "z")
```

### PS-CONC-07 [M] Never read `frame.f_locals` for a frame executing in another thread

Introspecting your own stack is fine. Reaching into a frame another thread is running is not.

**Why:** the free-threading HOWTO states it plainly — doing so "may crash the interpreter". This is
not a data race that yields a wrong answer; it is a segfault. Debuggers, profilers, and error
reporters that walk `sys._current_frames()` and read locals are the code that does this by accident.

**Check:** `rg -n 'f_locals' src/` — every hit whose frame did not come from `sys._getframe()` on
the current thread is a defect.

## Sharing objects between threads

### PS-CONC-08 [M] Snapshot a container before iterating what another thread may mutate

`for key, value in dict(shared).items():` and `for item in list(shared):`. Iterating the live object
while another thread writes to it is the defect.

**Why:** on a GIL build this raised `RuntimeError: dictionary changed size during iteration`. The
free-threaded build's internal locks keep the container intact but do not make your iteration a
transaction, so the loud failure became a quiet one: an element seen twice, or missed entirely.

**Check:** for each `for ... in <name>` where `<name>` is not a local, ask whether any thread writes
to it. `rg -n 'for .+ in (self\.)?[a-z_]+(\.items\(\)|\.keys\(\)|\.values\(\))?:' src/` and read the
hits against the writers.

```python
# verified — GOOD
import threading

_sessions: dict[str, int] = {"a": 1, "b": 2}
_lock = threading.Lock()  # guards: _sessions, copied whole as one snapshot


def active_ids() -> list[int]:
    """Snapshot under the lock, then work outside it."""
    with _lock:
        snapshot = dict(_sessions)
    return sorted(v for v in snapshot.values() if v > 0)


assert active_ids() == [1, 2]
```

### PS-CONC-09 [M] Send an immutable message rather than sharing a mutable object

Hand a worker a `frozenset`, a `tuple`, a frozen dataclass, or a `frozendict`. Let it return a value
rather than write into something you both hold.

**Why:** an object that cannot change needs no lock, and its reference count is the only thing two
threads contend on. That removes a class of bug rather than guarding against it; the alternative is
to reason, at every call site and forever, about who may write when.

**Check:** every argument passed to a thread target or `submit`. A `list`, `dict`, `set`, or
non-frozen dataclass among them is the finding unless the receiver is documented as its new owner.

```python
# verified — GOOD
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Request:
    """One unit of work, handed over whole."""

    path: str
    retries: int


def handle(request: Request) -> str:
    """Nothing here can write anything the caller can see."""
    return f"{request.path}:{request.retries}"


with ThreadPoolExecutor(max_workers=2) as pool:
    out = sorted(pool.map(handle, [Request("/a", 1), Request("/b", 2)]))
assert out == ["/a:1", "/b:2"]
```

### PS-CONC-10 [M] Hand work between threads with `queue.Queue`

Not a shared list with a lock you wrote, and not a deque you poll. End the stream with `shutdown()`:
every blocked `get` then raises `queue.ShutDown` once the queue is drained, so the producer never
counts its consumers to send each a sentinel. Note the documented limit: `Queue` "is not designed to
handle reentrancy within a thread", so never `put` from a callback its consumer ran.

**Why:** `queue.Queue` implements "all of the required locking semantics" per its own docs, and it
carries the blocking, the shutdown, and the `task_done`/`join` accounting a hand-rolled equivalent
gets wrong. The classic hand-rolled bug is PS-CONC-03's: `if q: item = q.pop()` with two consumers.

**Check:** `rg -n '\.pop\(0\)|\.pop\(\)' src/` inside anything threaded, and every
`while ...: sleep(...)` polling a shared container.

```python
# verified — GOOD
import queue
import threading
from contextlib import suppress

work: queue.Queue[int] = queue.Queue()
seen: list[int] = []


def consume() -> None:
    with suppress(queue.ShutDown):  # raised once the queue is drained and shut down
        while True:
            item = work.get()
            seen.append(item)  # atomic (PS-CONC-05)
            work.task_done()


workers = [threading.Thread(target=consume) for _ in range(3)]
for worker in workers:
    worker.start()
for i in range(9):
    work.put(i)
work.shutdown()  # one call, however many consumers there are
for worker in workers:
    worker.join()
assert sorted(seen) == list(range(9))
```

### PS-CONC-11 [M] Bound every `queue.Queue` that a producer can outrun with `maxsize`

`queue.Queue()` with no `maxsize` has no limit, and `put` never blocks. Give a queue that is fed by
input the program does not control, such as requests, messages or lines read, a `maxsize`, so that
`put` blocks the producer while the queue is full. Choose the number from how much work may wait,
not from how much memory is free.

**Why:** a producer that outruns its consumers converts the lag into memory, and the process is
killed for it hours later, far from the cause. A bounded queue turns the same lag into a producer
that waits.

**Check:** every `queue.Queue()` and `queue.SimpleQueue()` fed from outside the process. No
`maxsize` is the finding; `SimpleQueue` has no bound to give.

```python
# fragment — BAD: a burst of input becomes memory
jobs: queue.Queue[bytes] = queue.Queue()
```

```python
# verified — GOOD
import queue
import threading

jobs: queue.Queue[int] = queue.Queue(maxsize=2)


def produce() -> None:
    for number in range(6):
        jobs.put(number)  # blocks while two items wait, so the consumer sets the pace
    jobs.shutdown()


def consume() -> int:
    total = 0
    while True:
        try:
            total += jobs.get()
        except queue.ShutDown:
            return total


producer = threading.Thread(target=produce)
producer.start()
assert consume() == 15
producer.join()
```

### PS-CONC-12 [S] Keep a shared object's lock inside the object that owns it

A module-level `_lock` beside a module-level `_cache` works until a second cache appears and takes
the same lock. Put the lock on the class whose invariant it protects, and route every write through
a method that takes it. Holding a frozen value (PS-DATA-01) and replacing it whole under the lock
keeps every read whole too.

**Why:** one process-wide lock guarding everything serialises unrelated work, which on the
free-threaded build is the difference between scaling and not, and it makes lock-ordering deadlocks
possible between operations that never needed to interact.

**Check:** two or more module-level `Lock()` objects in one module, or one lock referenced by
functions that touch different state, is the finding.

```python
# verified — GOOD
import threading
from dataclasses import dataclass, replace


@dataclass(frozen=True, slots=True)
class Position:
    """A point the tracker replaces, never edits."""

    x: int
    y: int


class Tracker:
    """Mutable holder, immutable value: no partial reads."""

    def __init__(self) -> None:
        """Start at the origin."""
        self._lock = threading.Lock()  # guards: self._at is replaced, never edited
        self._at = Position(0, 0)

    def advance(self, steps: int) -> None:
        """Move `steps` along x."""
        with self._lock:
            self._at = replace(self._at, x=self._at.x + steps)

    def position(self) -> Position:
        """Return where the tracker is; a frozen value, whole."""
        return self._at


tracker = Tracker()
tracker.advance(3)
assert tracker.position() == Position(3, 0)
```

## Iterators and generators

### PS-CONC-13 [M] Serialise a shared iterator with `threading.serialize_iterator`

Two threads calling `next()` on one iterator is the defect. `serialize_iterator` hands each item to
exactly one caller, and it neither copies nor buffers. It is a class, not a function: wrap once, and
share the wrapper.

**Why:** a shared generator raises `ValueError: generator already executing`, the good case because
it is loud. With any other iterator, the free-threading HOWTO warns that threads "may see duplicate
or missing elements", so a pool sharing one processes some items twice and drops others.

**Check:** every iterator passed to more than one thread must be wrapped, and an unwrapped one is
the finding. The sharing is the defect, not the call: `rg -nB3 'Thread\(target=' src/` and read what
the target closes over.

```python
# verified — BAD: the loud half of the failure
import threading


def numbers():
    yield from range(1000)


shared = numbers()
errors: list[str] = []


def drain() -> None:
    try:
        for _ in shared:
            pass
    except ValueError as exc:  # "generator already executing"
        errors.append(str(exc))


threads = [threading.Thread(target=drain) for _ in range(4)]
for thread in threads:
    thread.start()
for thread in threads:
    thread.join()
# A generator is caught here; every other iterator fails silently.
```

```python
# verified — GOOD
import threading

shared = threading.serialize_iterator(iter(range(9)))
got: dict[str, list[int]] = {}


def drain() -> None:
    got[threading.current_thread().name] = list(shared)  # atomic (PS-CONC-05)


threads = [threading.Thread(target=drain) for _ in range(3)]
for thread in threads:
    thread.start()
for thread in threads:
    thread.join()
drained = sorted(i for part in got.values() for i in part)
assert drained == list(range(9)), "each item goes to exactly one caller"
```

### PS-CONC-14 [M] Give each consumer a full stream with `threading.concurrent_tee`

When every consumer needs every item — not one each — `concurrent_tee(iterable, n)` is the split.
Its derived iterators are each single-consumer: handing one branch to two threads is PS-CONC-13's
defect again. `itertools.tee` is not a substitute, and its name is one word from the safe one: its
docs say a `RuntimeError` "may be raised when simultaneously using iterators returned by the same
`tee()` call, even if the original iterable is threadsafe", and concurrent use has segfaulted in
`teedataobject_clear`.

**Why:** `serialize_iterator` partitions and `concurrent_tee` duplicates; choosing the wrong one is
a silent correctness bug, not a performance one. `concurrent_tee` buffers each item until every
derived iterator has consumed it, so a slow consumer costs memory rather than correctness.

**Check:** any place where several threads must each see the whole stream. A shared iterator there
is the finding; so is passing one `concurrent_tee` branch to more than one thread. And
`rg -n 'itertools.tee|from itertools import.*tee' src/` — every hit in a module that also imports
`threading` or `concurrent.futures` is the finding.

```python
# verified — GOOD
import threading
lazy from collections.abc import Iterator

left, right = threading.concurrent_tee(iter(range(5)), 2)
sums: dict[str, int] = {}


def total(name: str, stream: Iterator[int]) -> None:
    value = sum(stream)  # this branch belongs to this thread alone
    sums[name] = value  # atomic (PS-CONC-05)


threads = [
    threading.Thread(target=total, args=("left", left)),
    threading.Thread(target=total, args=("right", right)),
]
for thread in threads:
    thread.start()
for thread in threads:
    thread.join()
assert sums == {"left": 10, "right": 10}, "both consumers saw the whole stream"
```

### PS-CONC-15 [S] Publish a thread-safe iterator factory with `threading.synchronized_iterator`

A decorator on a function that returns an iterator, so callers get a safe one without knowing to
wrap it. It applies only where you own the factory; where you are handed an iterator, PS-CONC-13 is
the rule.

**Why:** PS-CONC-13 puts the obligation on every caller, and an obligation every caller must
remember is one some caller will forget. Decorating the factory moves it to the one place that can
discharge it.

**Check:** a function returning a generator that is documented as safe to share, without the
decorator, is the finding.

```python
# verified — GOOD
import threading
lazy from collections.abc import Iterator


@threading.synchronized_iterator
def work_items(n: int) -> Iterator[int]:
    """Yield `range(n)`, safe to share across threads unwrapped."""
    yield from range(n)


shared = work_items(30)
got: dict[str, list[int]] = {}


def drain() -> None:
    got[threading.current_thread().name] = list(shared)  # atomic (PS-CONC-05)


threads = [threading.Thread(target=drain) for _ in range(3)]
for thread in threads:
    thread.start()
for thread in threads:
    thread.join()
assert sorted(i for part in got.values() for i in part) == list(range(30))
```

## Caches, memoisation, and context

### PS-CONC-16 [M] Never rely on `lru_cache` or `cached_property` to run a body once

Both are coherent — neither cache corrupts — and neither is single-flight. `functools.lru_cache`
does not hold its lock across the call, so eight threads hitting one cold key ran the body seven
times. `functools.cached_property` takes no lock at all, so two threads reaching a cold property
both compute it, and one of the two results is discarded.

**Why:** per the docs "it is possible for the wrapped function to be called more than once", and a
lock in `cached_property` would serialise every instance behind one. Harmless for a pure body; a
duplicated charge, write or connection, or a leaked handle, for one with an effect.

**Check:** `rg -nB3 -A5 '@lru_cache|@cache\b|cached_property' src/` and read each decorated body for
effects — I/O, writes, metrics, anything needing cleanup. A pure function is fine; anything else
needs PS-CONC-17.

### PS-CONC-17 [M!] Put a lock around a memo whose miss is expensive or has an effect

Not around the cache read — around the miss. Memoise an effect only where "once" is what every
caller wants, such as opening a connection: a cached charge or write happens once while each caller
believes it happened for them. `functools.cache` also needs every argument to be hashable. A pure,
cheap function needs no lock: its plain decorator, with a comment saying duplicate runs were
accepted, so the next reader knows it was a decision.

*Relaxed form:* an expensive miss with no effect may run more than once, with that comment.

**Why:** PS-CONC-16's two decorators are one defect with two spellings. The double-checked shape
keeps the common case, a hit, lock-free while making the miss single-flight; without it, "cached"
means "usually computed once", which is not what the word promises the reader.

**Check:** every `@cache`, `@lru_cache` and hand-written memo. Read the body for I/O, mutation,
randomness, or time: an effect a caller expects on every call is the finding, and so is an effectful
miss with no lock.

```python
# verified — GOOD
import threading

_conns: dict[str, str] = {}
_conns_lock = threading.Lock()  # guards: at most one open per dsn in _conns


def connect(dsn: str) -> None:
    """Open `dsn` once, however many threads ask at the same moment."""
    # Double-checked: the hit takes no lock, and the miss runs once.
    if dsn in _conns:
        return
    with _conns_lock:
        # Re-check: another thread may have filled it while we waited.
        if dsn in _conns:
            return
        _conns[dsn] = f"conn:{dsn}"  # stands in for the effectful open


def connection(dsn: str) -> str:
    """Return the connection `connect` opened; does not open one."""
    return _conns[dsn]


connect("db")
connect("db")
assert connection("db") == "conn:db"
assert len(_conns) == 1
```

### PS-CONC-18 [M] Create every `ContextVar` at module scope

Never inside a function, a method, or a loop.

**Why:** a `ContextVar` created per call is a new variable each time, so a value one caller sets is
invisible to every other: the lookup silently returns the default and the bug looks like "context
does not work".

**Check:** `rg -nB5 'ContextVar\(' src/` — any hit whose preceding lines are inside a `def` or
`class` body is the finding.

### PS-CONC-19 [M] Never rely on a thread inheriting context; the default differs by build

`sys.flags.thread_inherit_context` is 1 on the free-threaded build and 0 on the GIL build, and so is
`sys.flags.context_aware_warnings`, which makes `warnings.catch_warnings` context-local. Pass the
context explicitly, with `Thread(target=work, context=contextvars.copy_context())`, or set the flags
deliberately.

**Why:** a `ContextVar` set before starting a thread is visible inside it on `python3.15t` and
absent on `python3.15`, so code developed on one build takes a different branch on the other with no
diagnostic. A context passed explicitly is visible to the reader and the same on both.

**Check:** `rg -n 'ContextVar|copy_context' src/` in any module that also starts a thread — a read
inside a thread target whose value was set outside it is the finding.

```python
# verified — GOOD
import contextvars
import threading

request_id: contextvars.ContextVar[str] = contextvars.ContextVar(
    "request_id", default="-"
)
seen: list[str] = []


def worker() -> None:
    seen.append(request_id.get())


with request_id.set("abc"):
    # The context is passed, not inherited, so both builds agree.
    thread = threading.Thread(target=worker, context=contextvars.copy_context())
    thread.start()
    thread.join()
assert seen == ["abc"]
assert request_id.get() == "-", "leaving the block reset the variable"
```

## Streams, randomness, and hold times

### PS-CONC-20 [M] Write each record to a shared text stream in one call, never with `print`

`open()` in text mode returns a `TextIOWrapper`, and so do `sys.stdout` and `sys.stderr`, which
every thread that prints already shares. `print` is not one call to it: it writes each argument,
each separator and then `end` separately, so another thread's output lands inside the line. Send a
record as one `write` of the whole line, or through `logging`, whose handlers lock around each emit.

**Why:** the `io` docs call `TextIOWrapper` "not thread-safe" and promise nothing finer. On `3.15t`
eight threads printing 20,000 lines each garbled thousands of the 160,000, while the same lines sent
as single `write` calls arrived whole; under the GIL, `print` garbled a handful.

**Check:** `rg -n '\bprint\(|\.write\(' src/` inside any thread target. A `print` is the finding,
and so is a `write` that sends part of a record.

### PS-CONC-21 [M] Give each thread its own `random.Random`

The module-level functions all share one instance. Seed each thread's from the operating system, as
`random.Random()` does with no argument: one fixed seed would give every thread the same stream.

**Why:** the docs warn that concurrent calls to the global generator or one `Random` instance "may
encounter contention and poor performance" on the free-threaded build, and two threads calling
`random.gauss` at once can receive the same return value.

**Check:** `rg -n '\brandom\.(random|gauss|randint|shuffle|choice|uniform)\(' src/` — every hit
inside a thread target is the finding.

```python
# verified — GOOD
import random
import threading

_local = threading.local()


def rng() -> random.Random:
    """Return this thread's generator, made on first use."""
    existing = getattr(_local, "rng", None)
    if isinstance(existing, random.Random):
        return existing
    # No seed: the operating system's, so no two threads share a stream.
    made = random.Random()  # noqa: S311 — a sampling stream, not a secret
    _local.rng = made
    return made


draws: list[float] = []


def draw() -> None:
    draws.append(rng().random())  # atomic (PS-CONC-05)


threads = [threading.Thread(target=draw) for _ in range(4)]
for thread in threads:
    thread.start()
for thread in threads:
    thread.join()
assert len(set(draws)) == 4, "four threads, four independent streams"
```

### PS-CONC-22 [M] Hold a context in a generator with `with`, not with a decorator

In 3.15 a `@contextmanager`-derived decorator applied to a generator function keeps the context open
until the generator is exhausted. Previously it closed when the generator object was created. The
change is in `ContextDecorator` and `AsyncContextDecorator`, covers coroutine functions and
asynchronous generator functions too, and does not appear in the porting notes.

**Why:** nothing errors on either version; only the *duration* changes, from effectively zero to the
full consumption of the generator, so a lock, a transaction, a `chdir`, or a `contextvars` token it
holds is held longer, silently: under free threading, new contention and a new deadlock shape.

**Check:** `rg -nB2 -A2 '@contextmanager' src/` and find every decorator built from one that is
applied to a `def` containing `yield`. Each is the finding: its hold time changed, and a `with`
inside the generator, as below, states the hold where it is taken.

```python
# verified — GOOD: the hold is explicit, so no version changes it
import threading
from contextlib import contextmanager
lazy from collections.abc import Generator, Iterator

_lock = threading.Lock()  # guards: held pairs each "in" with its "out"
held: list[str] = []


@contextmanager
def guarded() -> Generator[None]:
    """Hold the lock for the body, recording entry and exit."""
    with _lock:
        held.append("in")
        try:
            yield
        finally:
            # Without this the lock is released but the bookkeeping is
            # not, and an exception in the body silently skips it.
            held.append("out")


def rows() -> Iterator[int]:
    """Yield the rows under a hold the `with` block makes visible."""
    with guarded():
        yield from (1, 2, 3)


assert list(rows()) == [1, 2, 3]
assert held == ["in", "out"]
```

### PS-CONC-23 [M] Never hold a lock across a call you do not control

A callback, a plugin hook, an I/O call, or anything that can block. Compute under the lock, call
outside it.

**Why:** a lock held across arbitrary code is a lock whose hold time you cannot bound, and one whose
acquisition order you cannot see: the shape of every lock-ordering deadlock. Under PS-CONC-22, a
decorator whose hold time silently grew now spans calls it never used to.

**Check:** read every `with <lock>:` body for a call that is not a local function or a container
operation. A hit is a candidate, not a verdict — the lock may genuinely need to span it, in which
case say so in a comment.

## Starting and owning tasks

### PS-CONC-24 [M] Enter with `asyncio.run`, and configure with `loop_factory`

`asyncio.run(main())`, or `asyncio.Runner` when you need several entries into one loop. Where the
loop needs configuring, `loop_factory` is the supported hook and is what survives 3.16.

**Why:** `asyncio.run` creates the loop, runs the coroutine, cancels what is left, shuts down async
generators and the default executor, and closes the loop, in that order. Hand-rolled lifecycles get
the shutdown half wrong, which is where "task was destroyed but it is pending" comes from.

**Check:** `rg -n 'new_event_loop|run_until_complete|loop.close\(\)' src/` — every hit is
hand-rolled lifecycle.

```python
# verified — GOOD
import asyncio


async def main() -> str:
    await asyncio.sleep(0)
    return "done"


# `loop_factory` is the hook that survives the 3.16 policy removal.
assert asyncio.run(main(), loop_factory=asyncio.EventLoop) == "done"
```

### PS-CONC-25 [M] Start every task inside a `TaskGroup`

`async with asyncio.TaskGroup() as tg: tg.create_task(...)`.

**Why:** nothing escapes the block: if one task raises, the rest are cancelled and the group
re-raises as an `ExceptionGroup`, which `except*` catches (PS-ERR-11); if it exits normally, every
task has finished. A loose task has neither, so its failure surfaces, if at all, at shutdown.

**Check:** `rg -n 'create_task|ensure_future' src/` — every hit outside a `TaskGroup` needs a
reference kept to the task, which ruff `RUF006` checks.

```python
# verified — GOOD
import asyncio


async def work(n: int) -> int:
    await asyncio.sleep(0)
    return n * 2


async def main() -> list[int]:
    async with asyncio.TaskGroup() as tg:
        tasks = [tg.create_task(work(i)) for i in range(3)]
    # Past the block, every task is done: the group guarantees it.
    return [t.result() for t in tasks]


assert asyncio.run(main()) == [0, 2, 4]
```

## Cancellation and timeouts

### PS-CONC-26 [M] Never swallow `CancelledError`

Catch it to clean up, then re-raise. It inherits from `BaseException` precisely so that
`except Exception` will not take it.

**Why:** swallowing cancellation makes the task uncancellable, which turns a graceful shutdown into
a hang and a timeout into a lie. `asyncio.run` cancels remaining tasks at exit, so a swallowing task
prevents the process from exiting cleanly.

**Check:** `rg -n 'except.*CancelledError' src/` — every handler must end in `raise`. Ruff `ASYNC`
and `BLE001` catch the `except Exception` variants that would also take it on older code.

### PS-CONC-27 [M] Leave no state half-updated across an `await`

Every `await` is a cancellation point: between the line before it and the line after it, the task
may be cancelled and never resume. Make the pair atomic with a context manager, or arrange that the
half-state is valid.

**Why:** this is the async analogue of PS-CONC-02: state you mutate in two steps around an `await`
can be left half-updated forever, and a resource acquired before an `await` and released after it
can leak.

**Check:** every `await` inside a `try`, a lock, or between two writes to the same object.

### PS-CONC-28 [M] Shield only what must not be interrupted, and bound it

`asyncio.shield` around a commit that must complete. Never around a whole operation. Shield the
smallest thing whose partial completion would be unrecoverable: writing the commit record, not
fetching the data that goes in it. Give the shielded region a timeout of its own, so that a shield
cannot become an unbounded wait.

**Why:** shielding defeats cancellation, which is the mechanism timeouts and shutdown are built on.
A shielded region with no timeout of its own is a task that cannot be stopped by any means.

**Check:** every `shield`. Name what would break if it were interrupted; if you cannot, remove it.

### PS-CONC-29 [M] Give every wait a timeout, with `asyncio.timeout`

`async with asyncio.timeout(5):`. Not `wait_for`, which is the older spelling.

**Why:** a wait with no bound is a hang with extra steps, and in an async program one hung task
holds its whole logical operation open. `asyncio.timeout` is a context manager, so it composes with
`TaskGroup` and applies to everything inside it rather than to one awaitable.

**Check:** every `await` on network, subprocess, or queue I/O. No enclosing `timeout` is the
finding.

```python
# verified — GOOD
import asyncio


async def slow() -> None:
    await asyncio.sleep(10)


async def main() -> str:
    try:
        async with asyncio.timeout(0.01):
            await slow()
    except TimeoutError:
        return "bounded"
    return "finished"


assert asyncio.run(main()) == "bounded"
```

## Blocking and colour

### PS-CONC-30 [M] Never run blocking work on the event loop; move it with `asyncio.to_thread`

No `requests.get`, no `open(...).read()` on a large file, no `subprocess.run`, no `sleep`. Move the
call with `await asyncio.to_thread(blocking_call, arg)`, not a hand-made executor unless you need to
bound it; then `loop.run_in_executor` with your own executor is the escape, and the bound is the
point. CPU work between two `await`s blocks the loop just as I/O does, so a long parse or a big
comprehension belongs in `to_thread` too, and a stretch short enough not to matter stays inline.

**Why:** the loop is one thread and cannot preempt, so a blocking call stops every task, not only
the one that made it: a 200 ms disk read adds 200 ms to every concurrent request. A long stretch
with no `await` calls nothing blocking, so no linter recognises it.

**Check:** ruff's `ASYNC` family covers the common calls by name — `ASYNC230` for a blocking `open`,
`ASYNC240` for a blocking `pathlib` method, `ASYNC210` and `ASYNC212` for blocking HTTP, `ASYNC220`
through `ASYNC222` for subprocesses, and `ASYNC250` for `input`; each hit needs `to_thread` or an
explicit executor. For the stretch with no call to name, read each coroutine for a loop or
comprehension over a large collection with no `await` inside it.

### PS-CONC-31 [M] Do not mark a function `async` unless it awaits

An `async def` with no `await` is a synchronous function that forces every caller into a coroutine.

**Why:** async is viral: making one function async makes every caller async, up to the entry point.
Paying that cost for a function that never yields buys nothing and makes the code untestable without
a loop. The exception is an interface a protocol requires to be async — say so in the docstring.

**Check:** a review matter. The rule that decides it mechanically is **preview**, and the shipped
configuration runs stable rules only; preview rules move between ruff releases.
