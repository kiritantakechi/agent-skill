# Async: Tasks, Cancellation, Lifecycle, and the Thread Boundary

Scope: writing `asyncio` code that cancels correctly, owns every task it starts, and does not block
the loop — plus the boundary between an event loop and the threads around it. Whether to use async
at all rather than threads is the concurrency chapter's question; blocking calls that belong in a
thread pool are named here.

Unless a block shows its own imports, it assumes `import asyncio`.

## Contents

- **Entering and leaving**
  - PS-ASYNC-01 [M] Enter with `asyncio.run`, and configure with `loop_factory`
  - PS-ASYNC-02 [M] Never call `get_event_loop`, and never touch the policy API
- **Owning tasks**
  - PS-ASYNC-03 [M] Start every task inside a `TaskGroup`
  - PS-ASYNC-04 [S] End a group early with `TaskGroup.cancel`, not with an exception
- **Cancellation**
  - PS-ASYNC-05 [M] Never swallow `CancelledError`
  - PS-ASYNC-06 [M] Leave no state half-updated across an `await`
  - PS-ASYNC-07 [M!] Shield only what must not be interrupted, and bound it
  - PS-ASYNC-08 [M] Give every wait a timeout, with `asyncio.timeout`
- **Not blocking the loop**
  - PS-ASYNC-09 [M] Never call a blocking function from a coroutine
  - PS-ASYNC-10 [M] Move blocking work with `asyncio.to_thread`
  - PS-ASYNC-11 [S] Keep a coroutine's synchronous stretches short
- **The thread boundary**
  - PS-ASYNC-12 [M] Give each thread its own event loop
  - PS-ASYNC-13 [M] Cross into a loop with `call_soon_threadsafe` or `run_coroutine_threadsafe`
  - PS-ASYNC-14 [M] Use `queue.Queue` between threads and `asyncio.Queue` within a loop
  - PS-ASYNC-15 [M] Never use an `asyncio` primitive across threads
- **Shape**
  - PS-ASYNC-16 [M] Do not mark a function `async` unless it awaits
  - PS-ASYNC-17 [S] Make an async resource a context manager
  - PS-ASYNC-18 [M] Give every async iterator an `aclose`
- Decided by tools

---

## Entering and leaving

### PS-ASYNC-01 [M] Enter with `asyncio.run`, and configure with `loop_factory`

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

### PS-ASYNC-02 [M] Never call `get_event_loop`, and never touch the policy API

Not `get_event_loop`, `set_event_loop_policy`, `AbstractEventLoopPolicy`, or the Windows policy
classes. Inside a coroutine the correct call is `asyncio.get_running_loop()`. To choose a loop, pass
`loop_factory` to `asyncio.run` or `asyncio.Runner` (PS-ASYNC-01), which replaces every policy
class, the Windows ones included.

**Why:** the whole policy system is **removed in 3.16**, and `get_event_loop` raises `RuntimeError`
when no loop is running, so code relying on it to create one is already broken. `get_running_loop`
fails loudly rather than conjuring a second loop nobody will run.

**Check:** `rg -n 'get_event_loop|EventLoopPolicy|set_event_loop' src/` — every hit is the finding.

## Owning tasks

### PS-ASYNC-03 [M] Start every task inside a `TaskGroup`

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

### PS-ASYNC-04 [S] End a group early with `TaskGroup.cancel`, not with an exception

New in 3.15: `tg.cancel()` ends the group without raising. It is idempotent and callable before
entry.

**Why:** the previous way to stop a group early was to raise something and catch it outside, which
conflates "we are done" with "something went wrong" and leaves a `CancelledError` in the traceback
of a successful run.

**Check:** `rg -nB4 'raise .*Done|raise .*Stop' src/` inside a `TaskGroup` — a sentinel exception
used for control flow is what this replaces.

## Cancellation

### PS-ASYNC-05 [M] Never swallow `CancelledError`

Catch it to clean up, then re-raise. It inherits from `BaseException` precisely so that
`except Exception` will not take it.

**Why:** swallowing cancellation makes the task uncancellable, which turns a graceful shutdown into
a hang and a timeout into a lie. `asyncio.run` cancels remaining tasks at exit, so a swallowing task
prevents the process from exiting cleanly.

**Check:** `rg -n 'except.*CancelledError' src/` — every handler must end in `raise`. Ruff `ASYNC`
and `BLE001` catch the `except Exception` variants that would also take it on older code.

### PS-ASYNC-06 [M] Leave no state half-updated across an `await`

Every `await` is a cancellation point: between the line before it and the line after it, the task
may be cancelled and never resume. Make the pair atomic with a context manager, or arrange that the
half-state is valid.

**Why:** this is the async analogue of PS-CONC-02: state you mutate in two steps around an `await`
can be left half-updated forever, and a resource acquired before an `await` and released after it
can leak.

**Check:** every `await` inside a `try`, a lock, or between two writes to the same object.

### PS-ASYNC-07 [M!] Shield only what must not be interrupted, and bound it

`asyncio.shield` around a commit that must complete. Never around a whole operation. Shield the
smallest thing whose partial completion would be unrecoverable: writing the commit record, not
fetching the data that goes in it.

*Relaxed form:* a slightly larger region, provided it has a timeout of its own, so that a shield
cannot become an unbounded wait.

**Why:** shielding defeats cancellation, which is the mechanism timeouts and shutdown are built on.
A shielded region with no timeout of its own is a task that cannot be stopped by any means.

**Check:** every `shield`. Name what would break if it were interrupted; if you cannot, remove it.

### PS-ASYNC-08 [M] Give every wait a timeout, with `asyncio.timeout`

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

## Not blocking the loop

### PS-ASYNC-09 [M] Never call a blocking function from a coroutine

No `requests.get`, no `open(...).read()` on a large file, no `subprocess.run`, no `sleep`.

**Why:** the loop is one thread. A blocking call stops every task in the program, not only the one
that made it — so a 200 ms disk read is 200 ms of latency added to every concurrent request. This is
the single most common async defect and it is invisible in a test with one client.

**Check:** ruff's `ASYNC` family covers the common calls by name — `ASYNC230` for a blocking `open`,
`ASYNC240` for a blocking `pathlib` method, `ASYNC210` and `ASYNC212` for blocking HTTP, `ASYNC220`
through `ASYNC222` for subprocesses, and `ASYNC250` for `input`.

### PS-ASYNC-10 [M] Move blocking work with `asyncio.to_thread`

`await asyncio.to_thread(blocking_call, arg)`. Not a hand-made executor unless you need to bound it;
then `loop.run_in_executor` with your own executor is the escape, and the bound is the point.

**Why:** `to_thread` runs the call on the default thread pool and gives you an awaitable, which is
the whole boundary in one line, and it propagates context variables, which a raw executor does not.

**Check:** every call PS-ASYNC-09's codes report. Each needs `to_thread` or an explicit executor.

### PS-ASYNC-11 [S] Keep a coroutine's synchronous stretches short

CPU work between two `await`s blocks the loop just as I/O does.

**Why:** the loop cannot preempt; a coroutine yields only where it awaits. A long parse or a big
comprehension between awaits is a blocking call that no linter recognises because it calls nothing
blocking. If the stretch is long enough to matter, it belongs in `to_thread`.

**Check:** read each coroutine for a loop or comprehension over a large collection with no `await`
inside it.

## The thread boundary

### PS-ASYNC-12 [M] Give each thread its own event loop

Never share one loop between threads.

**Why:** the asyncio docs say "tasks and futures created in one thread should not be awaited or
manipulated from another". asyncio supports free threading and scales linearly with one loop per
thread, so the shape that is correct is also the fast one.

**Check:** every `asyncio.run` or `Runner` that is reachable from more than one thread.

### PS-ASYNC-13 [M] Cross into a loop with `call_soon_threadsafe` or `run_coroutine_threadsafe`

Those two, and nothing else, are safe to call on a loop from another thread.

**Why:** every other loop method assumes it is called from the loop's own thread, and calling one
from outside corrupts the loop's internal state rather than raising. These two exist precisely
because the boundary needs a door; using anything else is going through the wall.

**Check:** `rg -n 'loop\.' src/` inside a thread target. Anything but those two is the finding.

### PS-ASYNC-14 [M] Use `queue.Queue` between threads and `asyncio.Queue` within a loop

They are not interchangeable and neither substitutes for the other. Each ends its stream the same
way: `shutdown()`, after which a drained queue's `get` raises `queue.ShutDown` or
`asyncio.QueueShutDown` in every consumer, with no sentinel per consumer.

**Why:** `asyncio.Queue` is not thread-safe and belongs to one loop; `queue.Queue` blocks, which is
fatal inside a coroutine. Crossing the boundary means a `queue.Queue` plus a `to_thread` call to
read it, or `call_soon_threadsafe` to push into the loop.

**Check:** `rg -n 'asyncio.Queue' src/` — a hit reachable from a plain thread is the finding.

### PS-ASYNC-15 [M] Never use an `asyncio` primitive across threads

`asyncio.Lock`, `Event`, `Semaphore` and `Condition` are single-loop objects.

**Why:** the docs state that these "are not designed to be used across threads" and that "almost all
asyncio objects are not thread safe". They coordinate by scheduling on the loop, so from another
thread they are simply the wrong mechanism — use `threading.Lock` there.

**Check:** `rg -n 'asyncio\.(Lock|Event|Semaphore|Condition)\b' src/` inside a thread target. The
word boundary matters: without it the pattern also matches `asyncio.EventLoop`, which is not one.

## Shape

### PS-ASYNC-16 [M] Do not mark a function `async` unless it awaits

An `async def` with no `await` is a synchronous function that forces every caller into a coroutine.

**Why:** async is viral: making one function async makes every caller async, up to the entry point.
Paying that cost for a function that never yields buys nothing and makes the code untestable without
a loop. The exception is an interface a protocol requires to be async — say so in the docstring.

**Check:** a review matter. The rule that decides it mechanically is **preview**, and the shipped
configuration runs stable rules only; preview rules move between ruff releases.

### PS-ASYNC-17 [S] Make an async resource a context manager

`__aenter__`/`__aexit__`, used with `async with`.

**Why:** the same argument as PS-ERR-14: acquisition and release in one place, impossible to forget.
For async it matters more, because the release usually has to be awaited and a forgotten one leaves
a connection open until the process ends.

**Check:** every class with an async `close` or `disconnect`. No `__aexit__` is the finding.

### PS-ASYNC-18 [M] Give every async iterator an `aclose`

An async generator holds its frame until closed, and `asyncio.run` closes them at exit — but only
the ones it knows about.

**Why:** an async generator abandoned mid-iteration keeps whatever it was holding, and its cleanup
runs at an unpredictable time or not at all. `contextlib.aclosing` makes the close explicit at the
call site, which is where the reader can see it.

**Check:** `rg -n 'async def.*yield|__anext__' src/` — every async iterator over a resource needs an
`aclose` and a caller using `aclosing`.

## Decided by tools

A tool settles these on its own; the shipped configuration enables each at the level shown.

| Tool | Lint | Level | Forbids |
|---|---|---|---|
| ty | `deprecated` | warn | a deprecated API — `asyncio.iscoroutinefunction` among them; use `inspect.iscoroutinefunction` |
| ruff | `RUF006` | error | a `create_task` result nothing keeps — the loop holds only a weak reference |
| ruff | `ASYNC251` | error | `time.sleep` in a coroutine — `await asyncio.sleep` |
