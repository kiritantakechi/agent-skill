## Why

`mutation` deletes each statement of a verified example in turn and runs the example's tests. On
zig-style, 11 deletions leave every test passing. A survivor is a note, not a failure, because an
illustrative test pins the case its name describes. But each of these 11 is a line a reader is
taught and no test can fail on. The full check on GitHub's runners reported all of them:

| Rule | Statement | Why no test fails |
|---|---|---|
| ZS-BUILD-33 | `cli.output = value;`, `cli.rest = argv[i..];`, `return cli;` in the operand branch | the one test has no `--output=` and no operand |
| ZS-BUILD-33 | the two `std.process.fatal` usage errors | a call that ends the process cannot be observed by a test inside it |
| ZS-CONC-25 | `defer l.lock.unlock(io);` | nothing checks the lock is free afterwards |
| ZS-CONC-35 | `try io.sleep(...)` | a sleep's only effect is time, which a verified block may not observe |
| ZS-INTEROP-01 | `if (text.len == 0) return error.Invalid;` | no empty input |
| ZS-INTEROP-02 | `if (path_slice.len == 0) return .invalid_argument;` | no empty path |
| ZS-MOD-11 | `journal.* = undefined;` | no correct program can observe it |
| ZS-TEST-11 | `if (s.len == 0) return null;` | no pop on an empty stack |

Two of these are faults in the example, not only gaps in its test:
- **ZS-BUILD-33's prose contradicts its example.** The prose says `parseArgs` is kept pure "that is
  what makes the example's cases a unit test instead of a subprocess test", yet the example's
  `parseArgs` exits the process on a usage error, so those cases can only be subprocess tests.
- **The poison write is required of every example.** ZS-ERR-15 `[M]` requires every `deinit` to end
  with `x.* = undefined;`. Deleting that store changes only what a use after `deinit` would read,
  and such a read is illegal behaviour no correct test performs. So every tested `deinit` the
  standard shows carries a mutant no test can kill. The mutation operator, not the example, is what
  is wrong.

## What Changes

- **Seven statements are pinned by a test case.** ZS-BUILD-33's operand branch and `--output=`,
  ZS-CONC-25's unlock (the lock is free after `add`), ZS-INTEROP-01's empty text, ZS-INTEROP-02's
  empty path, and ZS-TEST-11's empty stack (its own test, per ZS-TEST-12).
- **ZS-BUILD-33's parser reports usage errors instead of exiting.**
  - `parseArgs` returns `error.Usage` and names the refused argument and the reason through a
    `*Diagnostics`, the pattern ZS-ERR-28 gives.
  - Its usage errors become unit tests.
  - `main`, quoted in the prose, is the one `std.process.fatal` call site, with exactly two
    arguments as the rule's Check asks.
- **ZS-CONC-35's suspension point waits for something.**
  - The sleep becomes a wait on an `Io.Queue` for a reply, whose value the function returns.
  - The test checks that value, and that the lock is free. The BAD fragment waits the same way,
    inside the lock.
- **A store of `undefined` is not a mutant.**
  - zig-style's `Language` names the statements whose deletion is an equivalent mutant, one that no
    well-defined run can tell apart from the original. A store of `undefined` is one.
  - `deletable` skips them, as it already skips bindings and assertions.
  - Python and Rust have no such store and name none.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `check-execution`: one requirement added, stating which statements a mutant deletes.

## Impact

- **zig-style:** the examples of ZS-BUILD-33, ZS-CONC-25, ZS-CONC-35, ZS-INTEROP-01, ZS-INTEROP-02
  and ZS-TEST-11, and ZS-BUILD-33's prose line on `main`. No rule's ID, tier or title changes.
- **Harness:** `agent_skill.lang` (a field on `Language`, read by `deletable`), zig's language
  record, and their tests.
- **Measured:** zig-style's `mutation` survivors go from 11 to 0. The two inconclusive mutants
  (ZS-CONC-20, ZS-CONC-36), whose deletion hangs the test, are unchanged.
