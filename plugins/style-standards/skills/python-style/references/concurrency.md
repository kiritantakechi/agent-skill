# Free Threading: What the GIL Guaranteed, Shared State, Iterators, and the Build

Scope: writing Python that is correct when threads run in parallel — what the GIL used to make
unlikely, which standard-library objects hold their own locks and which do not, how to share an
iterator, how caches and context behave, when threads beat processes, and what the free-threaded
build and its C extensions require. Choosing between `async` and threads at all is in the async
chapter; the shape of the data being shared is in the data chapter; interpreter and
allocator overhead is in the performance chapter.

Two sources are merged here: the **CPython 3.15 documentation** — PEP 703, PEP 779, the
free-threading HOWTO, and the per-module thread-safety notes, quoted where they are normative — and
the **empirical behaviour of the free-threaded build**, measured on `python3.15t` and cited with the
numbers it produced. Ruff has no rule in any of its 59 linters that mentions the GIL, free
threading, or thread safety, so unlike every other chapter in this standard nothing here can be
delegated to the linter: each rule ships the check that decides it.

Unless a block shows its own imports, it assumes `import threading` and that the module runs on the
free-threaded build. Where a rule depends on the build, the block probes it rather than assuming.

## Contents

- **What the GIL guaranteed, and what it does not**
  - PS-CONC-01 [M] Probe the build with `sys.abi_info` and the runtime with `sys._is_gil_enabled`
  - PS-CONC-02 [M] Never treat a compound assignment as one step
  - PS-CONC-03 [M] Never treat check-then-act as one step
  - PS-CONC-04 [M!] Accumulate per thread and merge, or hold one lock across the whole update
  - PS-CONC-05 [M] Cite the thread-safety guarantees page, never the FAQ's bytecode argument
  - PS-CONC-06 [M] Name the invariant a lock guards, on the line that creates it
  - PS-CONC-07 [M] Never read `frame.f_locals` for a frame executing in another thread
- **Sharing objects between threads**
  - PS-CONC-08 [M] Snapshot a container before iterating what another thread may mutate
  - PS-CONC-09 [S] Send an immutable message rather than sharing a mutable object
  - PS-CONC-10 [M] Hand work between threads with `queue.Queue`
  - PS-CONC-11 [S] Keep a shared object's lock inside the object that owns it
- **Iterators and generators**
  - PS-CONC-12 [M] Serialise a shared iterator with `threading.serialize_iterator`
  - PS-CONC-13 [M] Give each consumer a full stream with `threading.concurrent_tee`
  - PS-CONC-14 [S] Publish a thread-safe iterator factory with `threading.synchronized_iterator`
- **Caches, memoisation, and context**
  - PS-CONC-15 [M] Treat `functools.lru_cache` as coherent but not single-flight
  - PS-CONC-16 [M] Treat `functools.cached_property` as able to run more than once
  - PS-CONC-17 [M!] Put a lock around a memo whose miss is expensive or has an effect
  - PS-CONC-18 [M] Create every `ContextVar` at module scope
  - PS-CONC-19 [M] Never rely on a thread inheriting context; the default differs by build
- **Streams, randomness, and hold times**
  - PS-CONC-20 [M] Never share a `TextIOWrapper` across threads, `print` included
  - PS-CONC-21 [M] Give each thread its own `random.Random`
  - PS-CONC-22 [M] Know that a `contextmanager` decorator now holds across the whole generator
  - PS-CONC-23 [S] Never hold a lock across a call you do not control

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

FREE_THREADED_BUILD = sys.abi_info.free_threaded


def running_in_parallel() -> bool:
    """Is the GIL off at this moment? Guarded: the name is an implementation detail."""
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
and
read each hit: is the target reachable from more than one thread? A module-level name, an attribute
of a shared instance, and any dict or list that a worker was handed all are.

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
for t in threads:
    t.start()
for t in threads:
    t.join()
assert counter <= 80_000, "80000 is the answer only if nothing interleaved"
```

```python
# verified — GOOD
import threading

_lock = threading.Lock()  # guards: counter, read and written as one step
counter = 0


def bump() -> None:
    global counter
    for _ in range(20_000):
        with _lock:
            counter += 1


threads = [threading.Thread(target=bump) for _ in range(4)]
for t in threads:
    t.start()
for t in threads:
    t.join()
assert counter == 80_000
```

### PS-CONC-03 [M] Never treat check-then-act as one step

`if key not in cache: cache[key] = compute(key)` is two operations with a gap. So are
`if not os.path.exists(p): open(p, "w")`, `if q: item = q.pop()`, and every `if x is None: x = ...`
on shared state. `dict.setdefault` performs the whole check-and-insert under one lock; a `Lock` does
the same for anything larger.

**Why:** both halves can be individually atomic and the pair still wrong: the container's lock is
released between them, so two threads both see the key absent and both compute. Whenever `compute`
writes a file, charges an account, or increments a metric, that is a duplicated side effect.

**Check:** `rg -nB2  'if .* not in |if not .*\.(exists|get)\(' src/` — a hit whose next line
writes to the thing just tested is a defect unless a lock spans both.

```python
# verified — GOOD
import threading

_registry: dict[str, int] = {}
_registry_lock = threading.Lock()  # guards: one id per name in _registry


def intern(name: str) -> int:
    """One winner per name, even when two threads miss together."""
    with _registry_lock:
        # setdefault would do for a pure computation; the lock is here because
        # assigning the id must not race with another thread assigning one.
        if name not in _registry:
            _registry[name] = len(_registry)
        return _registry[name]


assert intern("a") == 0
assert intern("b") == 1
assert intern("a") == 0
```

### PS-CONC-04 [M!] Accumulate per thread and merge, or hold one lock across the whole update

A worker that touches shared state on every iteration spends its time on cache-line ping-pong. Give
each thread a local accumulator, and merge once at the end.

*Relaxed form:* a lock held across the whole read-modify-write is correct and is enough for code
that is not hot. The per-thread accumulator is what makes it *scale*; the lock is what makes it
*right*. Never ship the third option, which is neither.

**Why:** every write to an object shared across cores is an atomic operation on its reference count
as well as its value, which the free-threaded build pays on a slow path: a documented four-thread
case took 3.61s against the GIL build's 2.38s, and 0.83s once its shared objects were thread-local.

**Check:** in any function passed to `Thread(target=...)` or an executor's `submit`, every name that
is not a parameter or a local is a candidate. A write to one on the hot path is the finding.

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
for t in threads:
    t.start()
for t in threads:
    t.join()
assert _totals == Counter({"a": 8, "b": 4})
```

### PS-CONC-05 [M] Cite the thread-safety guarantees page, never the FAQ's bytecode argument

A lock-free design rests on *Thread Safety Guarantees*, the page that documents each built-in
type's operations under free threading. There `L.append(x)`, `D[x] = y` and `D1.update(D2)` are
atomic, `L.sort()` is not, and no operation that makes more than one access is. The library FAQ
still lists `L.sort()` and still explains its list by saying each bytecode instruction is atomic.

**Why:** bytecode atomicity was the GIL, and readers generalise from a reason: `d[k] += 1` follows
from it and was never safe. The guarantees page states each operation instead of a reason, and
says outright that read-modify-write and check-then-act are not atomic.

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
    """The bound is the invariant, so the lock spans the test and the append."""

    def __init__(self, limit: int) -> None:
        self._limit = limit
        self._lock = threading.Lock()  # guards: len(self._lines) <= self._limit
        self._lines: list[str] = []

    def add(self, line: str) -> bool:
        with self._lock:
            if len(self._lines) >= self._limit:
                return False
            self._lines.append(line)
            return True


log = BoundedLog(2)
assert [log.add("x"), log.add("y"), log.add("z")] == [True, True, False]
```

### PS-CONC-07 [M] Never read `frame.f_locals` for a frame executing in another thread

Introspecting your own stack is fine. Reaching into a frame another thread is running is not.

**Why:** the free-threading HOWTO states it plainly — doing so "may crash the interpreter". This is
not a data race that yields a wrong answer; it is a segfault. Debuggers, profilers, and error
reporters that walk `sys._current_frames()` and read locals are the code that does this by accident.

**Check:** `rg -n 'f_locals' src/` — every hit whose frame did not come from
`sys._getframe()` on the current thread is a defect.

## Sharing objects between threads

### PS-CONC-08 [M] Snapshot a container before iterating what another thread may mutate

`for key, value in dict(shared).items():` and `for item in list(shared):`. Iterating the live object
while another thread writes to it is the defect.

**Why:** on a GIL build this raised `RuntimeError: dictionary changed size during iteration`. The
free-threaded build's internal locks keep the container intact but do not make your iteration a
transaction, so the loud failure became a quiet one: an element seen twice, or missed entirely.

**Check:** for each `for ... in <name>` where `<name>` is not a local, ask whether any thread writes
to it. `rg -n 'for .+ in (self\.)?[a-z_]+(\.items\(\)|\.keys\(\)|\.values\(\))?:' src/` and read
the hits against the writers.

```python
# verified — GOOD
import threading

_sessions: dict[str, int] = {"a": 1, "b": 2}
_lock = threading.Lock()  # guards: _sessions, copied whole as one snapshot


def active_ids() -> list[int]:
    """The snapshot is taken under the lock; the work happens outside it."""
    with _lock:
        snapshot = dict(_sessions)
    return sorted(v for v in snapshot.values() if v > 0)


assert active_ids() == [1, 2]
```

### PS-CONC-09 [S] Send an immutable message rather than sharing a mutable object

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

Not a shared list with a lock you wrote, and not a deque you poll. End the stream with
`shutdown()`: every blocked `get` then raises `queue.ShutDown` once the queue is drained, so the
producer never counts its consumers to send each a sentinel. Note the documented limit: `Queue` "is
not designed to handle reentrancy within a thread", so never `put` from a callback its consumer ran.

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
for w in workers:
    w.start()
for i in range(9):
    work.put(i)
work.shutdown()  # one call, however many consumers there are
for w in workers:
    w.join()
assert sorted(seen) == list(range(9))
```

### PS-CONC-11 [S] Keep a shared object's lock inside the object that owns it

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
    x: int
    y: int


class Tracker:
    """Mutable holder, immutable value: one lock, one field, no partial reads."""

    def __init__(self) -> None:
        self._lock = threading.Lock()  # guards: self._at is replaced, never edited
        self._at = Position(0, 0)

    def advance(self, dx: int) -> Position:
        with self._lock:
            self._at = replace(self._at, x=self._at.x + dx)
            return self._at


t = Tracker()
assert t.advance(3) == Position(3, 0)
```

## Iterators and generators

### PS-CONC-12 [M] Serialise a shared iterator with `threading.serialize_iterator`

Two threads calling `next()` on one iterator is the defect. `serialize_iterator` hands each item to
exactly one caller, and it neither copies nor buffers. It is a class, not a function: wrap once,
and share the wrapper.

**Why:** a shared generator raises `ValueError: generator already executing`, the good case because
it is loud. With any other iterator, the free-threading HOWTO warns that threads "may see duplicate
or missing elements", so a pool sharing one processes some items twice and drops others.

**Check:** every iterator passed to more than one thread must be wrapped. An unwrapped one is the
finding, and the grep is for the sharing rather than for the call —
`rg -nB3 'Thread\(target=' src/` and read what the target closes over.

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
for t in threads:
    t.start()
for t in threads:
    t.join()
# A generator is caught here. Every other iterator type fails silently instead.
```

```python
# verified — GOOD
import threading

shared = threading.serialize_iterator(iter(range(9)))
got: dict[str, list[int]] = {}


def drain() -> None:
    got[threading.current_thread().name] = list(shared)  # atomic (PS-CONC-05)


threads = [threading.Thread(target=drain) for _ in range(3)]
for t in threads:
    t.start()
for t in threads:
    t.join()
drained = sorted(i for part in got.values() for i in part)
assert drained == list(range(9)), "each item goes to exactly one caller"
```

### PS-CONC-13 [M] Give each consumer a full stream with `threading.concurrent_tee`

When every consumer needs every item — not one each — `concurrent_tee(iterable, n)` is the split.
Its derived iterators are each single-consumer: handing one branch to two threads is PS-CONC-12's
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

left, right = threading.concurrent_tee(iter(range(5)), 2)
sums: dict[str, int] = {}


def total(name: str, stream) -> None:
    value = sum(stream)  # this branch belongs to this thread alone
    sums[name] = value  # atomic (PS-CONC-05)


threads = [
    threading.Thread(target=total, args=("left", left)),
    threading.Thread(target=total, args=("right", right)),
]
for t in threads:
    t.start()
for t in threads:
    t.join()
assert sums == {"left": 10, "right": 10}, "both consumers saw the whole stream"
```

### PS-CONC-14 [S] Publish a thread-safe iterator factory with `threading.synchronized_iterator`

A decorator on a function that returns an iterator, so callers get a safe one without knowing to
wrap it. It applies only where you own the factory; where you are handed an iterator, PS-CONC-12 is
the rule.

**Why:** PS-CONC-12 puts the obligation on every caller, and an obligation every caller must
remember is one some caller will forget. Decorating the factory moves it to the one place that can
discharge it.

**Check:** a function returning a generator that is documented as safe to share, without the
decorator, is the finding.

```python
# verified — GOOD
import threading


@threading.synchronized_iterator
def work_items(n: int):
    """Callers may share the result across threads without wrapping it."""
    yield from range(n)


shared = work_items(30)
got: dict[str, list[int]] = {}


def drain() -> None:
    got[threading.current_thread().name] = list(shared)  # atomic (PS-CONC-05)


threads = [threading.Thread(target=drain) for _ in range(3)]
for t in threads:
    t.start()
for t in threads:
    t.join()
assert sorted(i for part in got.values() for i in part) == list(range(30))
```

## Caches, memoisation, and context

### PS-CONC-15 [M] Treat `functools.lru_cache` as coherent but not single-flight

The cache will not corrupt. The function behind it will run more than once for the same key.

**Why:** the lock is not held across the call, so per the docs "it is possible for the wrapped
function to be called more than once": eight threads hitting one cold key ran it seven times.
Harmless for a pure function; a duplicated charge, write, or connection if the body has an effect.

**Check:** `rg -nB3 '@lru_cache|@cache\b' src/` and read each decorated body for effects — I/O,
writes, metrics, allocation of a scarce resource. A pure function is fine; anything else needs
PS-CONC-17.

### PS-CONC-16 [M] Treat `functools.cached_property` as able to run more than once

It takes no lock. Two threads reaching a cold property both compute it, and one of the two results
is discarded.

**Why:** a lock would serialise every instance behind one class-wide lock, so `cached_property` is
a memo, not a once-only guarantee. A discarded result that only computed costs time; one that
opened a connection or allocated a handle leaks unless something closes it.

**Check:** `rg -nA5 'cached_property' src/` — a getter that constructs anything needing cleanup
is the finding.

### PS-CONC-17 [M!] Put a lock around a memo whose miss is expensive or has an effect

Not around the cache read — around the miss. Memoise an effect only where "once" is what every
caller wants, such as opening a connection: a cached charge or write happens once while each caller
believes it happened for them. `functools.cache` also needs every argument to be hashable.

*Relaxed form:* a pure, cheap function may use the plain decorator and accept duplicate execution;
say so in a comment on the decorator, so the next reader knows it was a decision.

**Why:** PS-CONC-15 and PS-CONC-16 are the same defect with two spellings. The double-checked shape
keeps the common case, a hit, lock-free while making the miss single-flight; without it, "cached"
means "usually computed once", which is not what the word promises the reader.

**Check:** every `@cache`, `@lru_cache` and hand-written memo. Read the body for I/O, mutation,
randomness, or time: an effect a caller expects on every call is the finding, and so is an
effectful miss with no lock.

```python
# verified — GOOD
import threading

_conns: dict[str, str] = {}
_conns_lock = threading.Lock()  # guards: at most one open per dsn in _conns


def connection(dsn: str) -> str:
    """Double-checked: the hit is lock-free, the miss happens exactly once."""
    if (found := _conns.get(dsn)) is not None:
        return found
    with _conns_lock:
        # Re-check: another thread may have filled it while we waited.
        if (found := _conns.get(dsn)) is not None:
            return found
        opened = f"conn:{dsn}"  # stands in for the expensive, effectful call
        _conns[dsn] = opened
        return opened


assert connection("db") == "conn:db"
assert connection("db") == "conn:db"
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
absent on `python3.15`, so code developed on one build takes a different branch on the other with
no diagnostic. A context passed explicitly is visible to the reader and the same on both.

**Check:** `rg -n 'ContextVar|copy_context' src/` in any module that also starts a thread — a
read inside a thread target whose value was set outside it is the finding.

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
    # The context is passed, not inherited: this reads the same on both builds.
    thread = threading.Thread(target=worker, context=contextvars.copy_context())
    thread.start()
    thread.join()
assert seen == ["abc"]
assert request_id.get() == "-", "leaving the block reset the variable"
```

## Streams, randomness, and hold times

### PS-CONC-20 [M] Never share a `TextIOWrapper` across threads, `print` included

`open()` in text mode returns one. So do `sys.stdout` and `sys.stderr`. So `print` from two threads
is the same defect as writing to a shared file from two threads.

**Why:** the `io` docs say buffered streams "protect their internal structures using a lock" but
"`TextIOWrapper` objects are not thread-safe". A write that under the GIL usually finished in one
bytecode window now interleaves, in the encoder's internal state as well as in the output.

**Check:** `rg -n '\bprint\(|sys.stdout.write|sys.stderr.write' src/` inside any thread target.
Logging is the fix: `logging` handlers take a lock around each emit.

### PS-CONC-21 [M] Give each thread its own `random.Random`

The module-level functions all share one instance.

**Why:** the docs warn that concurrent calls to the global generator or one `Random` instance "may
encounter contention and poor performance" on the free-threaded build, and two threads calling
`random.gauss` at once can receive the same return value. Seeded per thread, a run is reproducible.

**Check:** `rg -n '\brandom\.(random|gauss|randint|shuffle|choice|uniform)\(' src/` — every hit
inside a thread target is the finding.

```python
# verified — GOOD
import random
import threading

_local = threading.local()


def rng() -> random.Random:
    """One generator per thread, seeded so each thread is reproducible."""
    existing = getattr(_local, "rng", None)
    if isinstance(existing, random.Random):
        return existing
    # Seeded by the name, not by `hash` of it: string hashes are salted per process.
    made = random.Random(threading.current_thread().name)
    _local.rng = made
    return made


out: list[float] = []


def draw() -> None:
    out.append(rng().random())  # atomic (PS-CONC-05)


threads = [threading.Thread(target=draw, name=f"w{i}") for i in range(4)]
for t in threads:
    t.start()
for t in threads:
    t.join()
assert len(out) == 4
```

### PS-CONC-22 [M] Know that a `contextmanager` decorator now holds across the whole generator

In 3.15 a `@contextmanager`-derived decorator applied to a generator function keeps the context open
until the generator is exhausted. Previously it closed when the generator object was created. The
change is in `ContextDecorator` and `AsyncContextDecorator`, covers coroutine functions and
asynchronous generator functions too, and does not appear in the porting notes.

**Why:** nothing errors on either version; only the *duration* changes, from effectively zero to the
full consumption of the generator, so a lock, a transaction, a `chdir`, or a `contextvars` token it
holds is held longer, silently: under free threading, new contention and a new deadlock shape.

**Check:** `rg -nB2 -A2 '@contextmanager' src/` and find every decorator built from one that is
applied to a `def` containing `yield`. Each is a hold time that changed; each needs the lock it
takes re-examined.

```python
# verified — GOOD: the hold is explicit, so no version changes it
import threading
from contextlib import contextmanager

_lock = threading.Lock()  # guards: held pairs each "in" with its "out"
held: list[str] = []


@contextmanager
def guarded():
    with _lock:
        held.append("in")
        try:
            yield
        finally:
            # Without this the lock is released but the bookkeeping is not, and
            # an exception in the body silently skips it.
            held.append("out")


def rows():
    """Used as a `with` block, the hold is visible and bounded."""
    with guarded():
        yield from (1, 2, 3)


assert list(rows()) == [1, 2, 3]
assert held == ["in", "out"]
```

### PS-CONC-23 [S] Never hold a lock across a call you do not control

A callback, a plugin hook, an I/O call, or anything that can block. Compute under the lock, call
outside it.

**Why:** a lock held across arbitrary code is a lock whose hold time you cannot bound, and one whose
acquisition order you cannot see: the shape of every lock-ordering deadlock. Under PS-CONC-22, a
decorator whose hold time silently grew now spans calls it never used to.

**Check:** read every `with <lock>:` body for a call that is not a local function or a container
operation. A hit is a candidate, not a verdict — the lock may genuinely need to span it, in which
case say so in a comment.
