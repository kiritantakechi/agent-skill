# Async: the asyncio-only rules and the thread boundary

Scope: what only `asyncio` has — the policy API, ending a `TaskGroup` early, the boundary between an
event loop and the threads around it, and async resources and iterators. Entering a loop, owning
tasks, cancellation and timeouts, and not blocking the loop are the concurrency chapter's, which
holds them beside the thread rules they share a claim with.

Unless a block shows its own imports, it assumes `import asyncio`.

## Contents

- **Entering and leaving**
  - PS-ASYNC-01 [M] Never call `get_event_loop`, and never touch the policy API
- **Owning tasks**
  - PS-ASYNC-02 [S] End a group early with `TaskGroup.cancel`, not with an exception
- **The thread boundary**
  - PS-ASYNC-03 [M] Give each thread its own event loop
  - PS-ASYNC-04 [M] Cross into a loop with `call_soon_threadsafe` or `run_coroutine_threadsafe`
  - PS-ASYNC-05 [M] Use `queue.Queue` between threads and `asyncio.Queue` within a loop
  - PS-ASYNC-06 [M] Never use an `asyncio` primitive across threads
- **Shape**
  - PS-ASYNC-07 [S] Make an async resource a context manager
  - PS-ASYNC-08 [M] Give every async iterator an `aclose`
- Decided by tools

---

## Entering and leaving

### PS-ASYNC-01 [M] Never call `get_event_loop`, and never touch the policy API

Not `get_event_loop`, `set_event_loop_policy`, `AbstractEventLoopPolicy`, or the Windows policy
classes. Inside a coroutine the correct call is `asyncio.get_running_loop()`. To choose a loop, pass
`loop_factory` to `asyncio.run` or `asyncio.Runner` (PS-CONC-24), which replaces every policy class,
the Windows ones included.

**Why:** the whole policy system is **removed in 3.16**, and `get_event_loop` raises `RuntimeError`
when no loop is running, so code relying on it to create one is already broken. `get_running_loop`
fails loudly rather than conjuring a second loop nobody will run.

**Check:** `rg -n 'get_event_loop|EventLoopPolicy|set_event_loop' src/` — every hit is the finding.

## Owning tasks

### PS-ASYNC-02 [S] End a group early with `TaskGroup.cancel`, not with an exception

New in 3.15: `tg.cancel()` ends the group without raising. It is idempotent and callable before
entry.

**Why:** the previous way to stop a group early was to raise something and catch it outside, which
conflates "we are done" with "something went wrong" and leaves a `CancelledError` in the traceback
of a successful run.

**Check:** `rg -nB4 'raise .*Done|raise .*Stop' src/` inside a `TaskGroup` — a sentinel exception
used for control flow is what this replaces.

## The thread boundary

### PS-ASYNC-03 [M] Give each thread its own event loop

Never share one loop between threads.

**Why:** the asyncio docs say "tasks and futures created in one thread should not be awaited or
manipulated from another". asyncio supports free threading and scales linearly with one loop per
thread, so the shape that is correct is also the fast one.

**Check:** every `asyncio.run` or `Runner` that is reachable from more than one thread.

### PS-ASYNC-04 [M] Cross into a loop with `call_soon_threadsafe` or `run_coroutine_threadsafe`

Those two, and nothing else, are safe to call on a loop from another thread.

**Why:** every other loop method assumes it is called from the loop's own thread, and calling one
from outside corrupts the loop's internal state rather than raising. These two exist precisely
because the boundary needs a door; using anything else is going through the wall.

**Check:** `rg -n 'loop\.' src/` inside a thread target. Anything but those two is the finding.

### PS-ASYNC-05 [M] Use `queue.Queue` between threads and `asyncio.Queue` within a loop

They are not interchangeable and neither substitutes for the other. Each ends its stream the same
way: `shutdown()`, after which a drained queue's `get` raises `queue.ShutDown` or
`asyncio.QueueShutDown` in every consumer, with no sentinel per consumer.

**Why:** `asyncio.Queue` is not thread-safe and belongs to one loop; `queue.Queue` blocks, which is
fatal inside a coroutine. Crossing the boundary means a `queue.Queue` plus a `to_thread` call to
read it, or `call_soon_threadsafe` to push into the loop.

**Check:** `rg -n 'asyncio.Queue' src/` — a hit reachable from a plain thread is the finding.

### PS-ASYNC-06 [M] Never use an `asyncio` primitive across threads

`asyncio.Lock`, `Event`, `Semaphore` and `Condition` are single-loop objects.

**Why:** the docs state that these "are not designed to be used across threads" and that "almost all
asyncio objects are not thread safe". They coordinate by scheduling on the loop, so from another
thread they are simply the wrong mechanism — use `threading.Lock` there.

**Check:** `rg -n 'asyncio\.(Lock|Event|Semaphore|Condition)\b' src/` inside a thread target. The
word boundary matters: without it the pattern also matches `asyncio.EventLoop`, which is not one.

## Shape

### PS-ASYNC-07 [S] Make an async resource a context manager

`__aenter__`/`__aexit__`, used with `async with`.

**Why:** the same argument as PS-ERR-14: acquisition and release in one place, impossible to forget.
For async it matters more, because the release usually has to be awaited and a forgotten one leaves
a connection open until the process ends.

**Check:** every class with an async `close` or `disconnect`. No `__aexit__` is the finding.

### PS-ASYNC-08 [M] Give every async iterator an `aclose`

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
| ty | `deprecated` | warn | a deprecated API — `asyncio.iscoroutinefunction` among them; use `inspect.iscoroutinefunction` — listed because it is how PS-API-15's `warnings.deprecated` reaches a caller, and `ty` reports it unasked |
| ruff | `RUF006` | error | a `create_task` result nothing keeps — the loop holds only a weak reference — listed because a task started outside a `TaskGroup` (PS-CONC-25) is collected unless something keeps it |
| ruff | `ASYNC251` | error | `time.sleep` in a coroutine — `await asyncio.sleep` — listed because it is the one blocking call PS-CONC-30's codes leave out |
