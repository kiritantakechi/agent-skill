## Context

`mutation` (`checks/toolchain.py`) deletes, one at a time, each line `deletable` picks. That is a
line holding one whole statement, outside the block's tests, that no word the language keeps opens.
It then runs the block's tests. A deletion the tests do not notice is a `survivor` note. zig-style
had 11. Each is either a case its example's test does not exercise, or a statement no test in the
process can observe.

## Goals / Non-Goals

**Goals:** every survivor on zig-style is pinned by a test or shown not to be a mutant, with the
reason stated where the harness decides it.

**Non-Goals:**
- Making `survivor` a failure; it stays a note, as `mutate`'s docstring argues.
- The two inconclusive mutants (ZS-CONC-20's `defer q.close(io)`, ZS-CONC-36's
  `defer l.lock.unlock(io)`). Deleting either deadlocks the test, which is the test failing; the
  policy reads a timeout as inconclusive, never as killed.

## Decisions

### 1. Pin by a test wherever the block's test can observe the statement

| Rule | Pinned by |
|---|---|
| ZS-BUILD-33 | a test whose first operand ends flag parsing (`--output=out.txt in.txt -v`), pinning `cli.output = value`, `cli.rest = argv[i..]` and that branch's `return` |
| ZS-CONC-25 | the existing test also asserts `ledger.lock.tryLock()` |
| ZS-INTEROP-01 | `zs_parse_u32("", &value)` is `.invalid_argument` |
| ZS-INTEROP-02 | `zs_open("", 8, 1, &handle)` is `.invalid_argument` |
| ZS-TEST-11 | a second test, "pop on an empty stack returns null" |

Each new expectation is one claim, in the test whose name already states it, or in a test of its own
(ZS-TEST-12).

### 2. ZS-BUILD-33: the parser returns usage errors, and `main` exits

`std.process.fatal` logs and exits 1. A Zig test cannot observe a process exit, so a usage error
reported inside `parseArgs` can only be a subprocess test. The rule's prose already says
`parseArgs` is kept pure so that its cases are unit tests. The example is changed to match:
- `parseArgs(argv, diagnostics: *Diagnostics) error{Usage}!Cli`.
- A refusal fills `diagnostics` (the argument and the reason) and returns `error.Usage`, through one
  helper `refuse`. This is ZS-ERR-28's pattern: the context goes in a `*Diagnostics`, not the error
  set.
- The prose line on `main` becomes the one `std.process.fatal` call, with exactly two arguments:
  `catch std.process.fatal("{s}: {s}\n{s}", .{ d.arg, d.reason, usage })`.
- The rule's statement, "and `std.process.fatal` for usage errors", stays true: it is still what
  reports them.

**Alternative rejected:** keeping `fatal` in the parser and exempting process-ending calls from
mutation. A process exit can be observed from outside the process. The survivor was right that the
example's usage errors were untested.

### 3. ZS-CONC-35: the suspension point waits for a reply

The sleep stood for a call that suspends. Its only effect is time, and a verified block may not
observe the clock. The example becomes a counter bump followed by a wait on an `Io.Queue(u64)` for a
reply, and it returns the bump and the reply. The test puts the reply into the queue first, checks
the sum, and checks that the lock is free. The BAD fragment does the same wait inside the lock. The
rule, its title and its Check already name "a queue operation" among the suspending calls.

### 4. A store of `undefined` is an equivalent mutant, so it is not deleted

ZS-ERR-15 `[M]` ends every `deinit` with `x.* = undefined;`. In Zig, `undefined` means the value
may be anything, and reading it is illegal behaviour. Deleting the store changes only what a later
illegal read would see, so no well-defined run can tell the mutant from the original. That makes it
an equivalent mutant, and an equivalent mutant is not a mutant.
- `Language` gains `equivalent: tuple[str, ...]`, the statement endings each language names this
  way. zig-style's is `(" = undefined;",)`. Python and Rust name none: neither has a store whose
  every read is illegal.
- `deletable` skips a statement whose code ends with one.
- A binding `var x: T = undefined;` is already kept by its `var `.

**Alternative rejected:** a zig-only test in `mutate`. The language record already holds the
vocabulary of what a mutant leaves, and this is one more word of it.
