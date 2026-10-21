# python-style: duplicate rules and newer APIs

Read: `SKILL.md` and all 14 chapters. Probes ran on `cpython-3.15.0+freethreaded` (`-I`); some
were also checked with the pinned `ty` 0.0.90 and `ruff` 0.17.1, on scratch files only.

## A. Duplicates

For each group: the owner, and what the other rule says that the owner must absorb.

| # | Rules | Owner | Absorb from the other |
|---|---|---|---|
| A1 | PS-NAME-10 / PS-API-02 (re-export by alias or `__all__`) | API-02 | NAME-10's `py.typed` condition. Also drop "re-export" from naming's scope and its §6 row. PS-API-01 already mandates `__all__`, so "pick one" is moot. |
| A2 | PS-TYPE-13 / PS-API-08 (take abstract, return concrete) | API-08 | TYPE-13's exception: a mutable parameter is fine when mutating it is the point. Also reword "narrowest", which reads backwards. |
| A3 | PS-ERR-11 / PS-ASYNC-04 (`except*`) | ERR-11 | ASYNC-04's point: the group is raised only after something failed. Also fix ERR-11's Barrier claim: barriers raise `BrokenBarrierError`. `socket.create_connection(all_errors=True)` does raise `ExceptionGroup`. |
| A4 | PS-CONC-25 / PS-MIG-09 (`contextmanager` as decorator) | CONC-25 | nothing; MIG-09 becomes a migration-table row with the grep. |
| A5 | PS-DATA-15 / PS-MIG-10 (`isinstance(x, dict)` vs `frozendict`) | DATA-15 | MIG-10's list of updated stdlib modules, and the silent-rejection consequence. |
| A6 | PS-OUT-02 / PS-OUT-03 / PS-MIG-11 (default encoding) | OUT-02 | OUT-03 stays only as the actionable "use `locale.getencoding()`" (B6). MIG-11 becomes a row. |
| A7 | PS-DOC-06 = PS-PERF-04 + PS-API-13 (cost and ownership) | PERF-04, API-13 | DOC-06's "network round trip that reads like a getter" example, into PERF-04. Then delete DOC-06. |
| A8 | PS-DOC-12 / PS-API-20 (changelog) | DOC-12 | API-20's entry vocabulary and its `__all__`-keyed Check. |
| A9 | PS-DATA-13 / PS-DATA-16 / PS-API-13 (immutable returns, ownership) | DATA-13 | DATA-16's `return self._items` Check, and "a tuple says not to edit it". API-13 keeps view vs copy and closeable resources. |
| A10 | PS-CONC-11 vs PS-DATA-01, -02, PS-PERF-11, PS-CONC-12 | DATA-01 (frozen), CONC-12 (lock ownership) | CONC-11's `Tracker` example, into CONC-12, which has none. Then dissolve CONC-11. |
| A11 | PS-DATA-02 / PS-PERF-11 (slots) | DATA-02 | PERF-11's 32-vs-16-byte header figure and the plain-class `__slots__` spelling. |
| A12 | PS-PERF-13 / PS-CONC-18 / PS-CONC-20 (caches) | CONC-20 with CONC-18 | PERF-13's point that the effect happens once while callers think it is every time, and that args must be hashable. This settles a conflict: PERF-13 forbids impure caching, while CONC-20 shows how to do it. |
| A13 | PS-CONC-13 / PS-CONC-14; PS-CONC-16 / PS-CONC-15 (shared iterators, `tee`) | CONC-14, CONC-15 | CONC-13's generator `ValueError` vs silent drop contrast, as CONC-14's Why. CONC-16's segfault and `RuntimeError` citations and grep, into CONC-15. |
| A14 | PS-NAME-17 / PS-DOC-07 (say why) | NAME-17 | DOC-07's Check targets, and "the next person reverts it". Retitle PS-DOC-13 so it does not mirror DOC-07. |
| A15 | PS-DATA-12 `[S]` / PS-API-07 `[M]` (keyword-only) | API-07 | DATA-12's `KW_ONLY` spelling, example and coordinate exception, plus PS-DATA-11's defaulted-fields clause. This resolves the tier conflict. |
| A16 | PS-DATA-08 / PS-DATA-09 (mutable defaults) | DATA-08 | DATA-09's example, and the gap that only known-unhashable defaults are refused. |
| A17 | PS-ASYNC-01, -02 / PS-MIG-12 (3.16 asyncio) | ASYNC-01, -02 | nothing; MIG-12 becomes linked rows. |
| A18 | PS-TYPE-12 / PS-MIG-07 / PS-MIG-04 and the `UP013`/`UP014` rows | TYPE-12 | MIG-07's tier and its 3.17 removal date, with the replacement from B4. MIG-07 becomes a row. |
| A19 | PS-MIG-01 / PS-MIG-02 (soft deprecation) | MIG-01 | MIG-02's examples (`re.prefixmatch`, `struct` `F`/`D`, `PyGILState`) and its Check. |
| A20 | PS-NAME-19 / PS-DATA-21 (inverse pairs) | DATA-21 | NAME-19 narrows to how the mirror is spelled. |
| A21 | PS-CONC-06 / PS-CONC-03; SKILL.md §2.2 / PS-CONC-05 | CONC-03, CONC-05 | CONC-06 keeps only "name the invariant beside the lock" and is retitled. §2.2 shrinks to one sentence and a pointer. |
| A22 | PS-API-15 ⊂ PS-API-17 (import cycles) | API-17 | API-15's self-import grep and its partially-initialised-module example. |
| A23 | PS-NAME-03 / PS-API-04 (leading underscore) | API-04 | NAME-03 narrows to "two underscores only for mangling". |
| A24 | PS-NAME-11 / PS-API-14 (no import-time work) | NAME-11 | API-14 keeps "re-exports, `__all__` and a docstring only". |
| A25 (low) | PS-NAME-22 / PS-DATA-22 (parallel siblings) | NAME-22, generalised | DATA-22's `Request`/`Response` example. |

**Core rules:** none restates a chapter rule beyond being its summary. PS-CORE-23 inherits A1.

**Orphans:** three topics are stated only in SKILL.md, with no owning chapter rule:

- `singledispatchmethod` dispatching on the second argument (§2.1);
- `@disjoint_base` (§2.4);
- `sum(lists, [])` replaced by `[*sub for sub in lists]`, PEP 798 (§2.3). `RUF017` rewrites it.

### Rules against the lint rows

- **PS-NAME-15**: its docstring and comment half is `W505`, which enforces it. Cite `W505`, and keep
  the row in one chapter.
- **PS-MIG-12**: its `asyncio.iscoroutinefunction` row repeats async.md's `ty deprecated` row.
- **PS-TYPE-12**: its functional `NamedTuple`/`TypedDict` clause is the `UP013`/`UP014` rows.
- **PS-DOC-02** and **PS-NAME-16**: both are wholly the formatter's (`quote-style`,
  `skip-magic-trailing-comma`). They become rows only if a table may name the formatter.
- **Conflict, PS-OUT-15**: `T201` flags `print(..., file=sys.stdout)` too, so the output OUT-15
  prescribes fails the shipped config. Fix the row text, and either add a per-file ignore for the
  entry point or prescribe `sys.stdout.write`.

## B. Newer APIs (all confirmed on 3.15.0t; `ty` is clean on each)

| # | Where | Old | New (version) | Why |
|---|---|---|---|---|
| B1 | PS-CONC-22 example (concurrency.md ~736) | `Thread(target=ctx.run, args=(worker,))` | `Thread(target=worker, context=contextvars.copy_context())` (3.14) | The target stays the real function, and the Check can grep the named parameter. |
| B2 | PS-CONC-01 (title, statement, example, Check); PS-CORE-26; PS-BUILD-19/20 | `sysconfig.get_config_var("Py_GIL_DISABLED") == 1` | `sys.abi_info.free_threaded` (3.15) | A documented, typed bool; the build/runtime split stays. |
| B3 | PS-CONC-10 example (~381–403); PS-ASYNC-15 | `Queue[int \| None]` with one `None` sentinel per consumer | `Queue.shutdown()` and `queue.ShutDown`; `asyncio.Queue.shutdown()` and `QueueShutDown` (3.13) | No `\| None`, one call instead of N sentinels, and the producer need not count consumers. |
| B4 | PS-MIG-07 (~159), PS-TYPE-12 | `bytes \| bytearray \| memoryview` as ByteString's replacement | `collections.abc.Buffer` (PEP 688, 3.12) | Correct: the union rejects `array`, `mmap` and third-party buffers. |
| B5 | PS-DATA-21 example (data.md ~457) | `from_dict(cls, raw: dict[str, int]) -> Point` | `raw: Mapping[str, int]`, `-> Self` | Today `ty` rejects a `frozendict` argument, contradicting PS-DATA-15 and PS-TYPE-13. |
| B6 | PS-OUT-03, MIG-11 | `locale.getpreferredencoding()`, or nothing | `locale.getencoding()` (3.11) | It names the locale's encoding regardless of UTF-8 mode, which makes the rule actionable. |
| B7 | PS-DATA-02 (~78), PS-PERF-11 | dropping `slots=True` to allow weak references | `@dataclass(slots=True, weakref_slot=True)` (3.11) | A weak reference needs a slot, not giving up slots. |
| B8 | PS-CONC-21/22 example (`request_id.set` never reset); SKILL §2.1 | `var.set(v)` with no reset | `with var.set(v): …`, since `Token` is a context manager (3.14) | The scope of a set is visible and cannot leak. |
| B9 | PS-PERF-09; PS-CONC-09 example (`pool.map`) | `Executor.map(fn, it)`, which submits everything | `Executor.map(..., buffersize=n)` (3.14) | Streams through the pool, which is PERF-09's own advice. |
| B10 | PS-TYPE-06 (~132) | "the caller handles the gap", with no API named | `typing.evaluate_forward_ref()`, `ForwardRef.evaluate(format=FORWARDREF)` (3.14) | Gives the prescribed follow-up an API. |
| B11 | PS-PERF-12, PS-PERF-06 | `bytes(buf); buf.clear()`, which copies | `bytearray.take_bytes(n=None)` (3.15) | No copy. |
| B12 | PS-BUILD-19, PS-CORE-26 | names only `cp3XXt` | the `abi3t` free-threaded stable ABI (PEP 803, 3.15) | The same "a tag is not a thread-safety claim" caveat applies to it. |
| B13 (optional) | PS-PERF-17 | threads or processes | `concurrent.futures.InterpreterPoolExecutor` (3.14) | Isolation without starting a process. |

## Other defects

- **PS-CONC-24 example**: `random.Random(hash(thread name) & 0xFFFF)` is not reproducible, because
  string hashing is randomised per process; `random.Random(name)` is.
- **PS-ERR-11's Barrier claim** is wrong (A3).
- **`sys.flags.context_aware_warnings`** is 1 on 3.15t and 0 on the GIL build. PS-CONC-22 names only
  `thread_inherit_context` as differing by build.
- **PS-PERF-18 and PS-PERF-14 against PS-DOC-14**: the first two require a dated comment, and
  DOC-14 forbids dates.
- **PS-TEST-20 against PS-TEST-08**: TEST-20's verified example loops inside a test, which TEST-08
  forbids.
