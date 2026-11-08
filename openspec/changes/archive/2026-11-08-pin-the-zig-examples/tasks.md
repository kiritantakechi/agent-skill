## 1. Harness

- [x] 1.1 Add `equivalent` to `Language`; make `deletable` skip a statement ending with one; give
  zig `(" = undefined;",)`; extend `test_one_grammar_zig` with a poison write and a binding of
  `undefined`; verify `test_extraction.py`, ruff, ruff format and ty. Result: the test's body holds
  `s.* = undefined;` and `s.field = undefined;`, which are not deleted, beside `scratch = 0;`, which
  is; under the old grammar both stores were mutants. 18 extraction tests pass; ruff, ruff format
  and ty are clean.

## 2. zig-style examples

- [x] 2.1 ZS-BUILD-33: `parseArgs` returns `error.Usage` through a `*Diagnostics`, with tests for
  the operand branch and every refusal; the prose line on `main` is the one `std.process.fatal`
  call. Result: three tests ("flags, --, and operands", "the first operand ends flag parsing", "a
  usage error names the argument and why"); every refusal goes through `refuse`, which fills the
  `Diagnostics` and returns `error.Usage`. `conventions` refused a `.?` in the operand test
  (ZS-ERR-26), so it compares `cli.output orelse ""`.
- [x] 2.2 ZS-CONC-25: the test checks the lock is free after `add` (`ledger.lock.tryLock()`), and
  its name says so
- [x] 2.3 ZS-CONC-35: the suspension point is a wait on an `Io.Queue` for a reply, in the GOOD
  example and the BAD fragment; the test checks the reply and the free lock. Result:
  `bumpThenAwait` returns `(Io.QueueClosedError || Io.Cancelable)!u64`, a named set, though
  ZS-ERR-02 lets a private helper infer one; the Check names a queue's `getOne(io)` and
  `putOne(io, …)` among the calls that take `io`
- [x] 2.4 ZS-INTEROP-01 and ZS-INTEROP-02: an empty input is `.invalid_argument`
- [x] 2.5 ZS-TEST-11: a test that pops an empty stack ("pop on an empty stack returns null")

## 3. Verify

- [x] 3.1 `agent-skill fmt`, `check --fast`, `check --skill zig-style --only toolchain` and
  `--only mutation` (survivors 11 → 0), the non-toolchain tests; record the results here. Result:
  `fmt` changes nothing; `check --fast` passes; zig-style's `toolchain` and `mutation` pass in 5 min
  11 s, `mutation` with no survivor (11 before) and the two inconclusive mutants the design leaves
  (ZS-CONC-20, ZS-CONC-36); `pytest -m "not toolchain"` passes 1011 tests.
