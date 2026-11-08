## 1. Harness

- [ ] 1.1 Add `equivalent` to `Language`; make `deletable` skip a statement ending with one; give
  zig `(" = undefined;",)`; extend `test_one_grammar_zig` with a poison write and a binding of
  `undefined`; verify `test_extraction.py`, ruff, ruff format and ty

## 2. zig-style examples

- [ ] 2.1 ZS-BUILD-33: `parseArgs` returns `error.Usage` through a `*Diagnostics`, with tests for the
  operand branch and every refusal; the prose line on `main` is the one `std.process.fatal` call
- [ ] 2.2 ZS-CONC-25: the test checks the lock is free after `add`
- [ ] 2.3 ZS-CONC-35: the suspension point is a wait on an `Io.Queue` for a reply, in the GOOD
  example and the BAD fragment; the test checks the reply and the free lock
- [ ] 2.4 ZS-INTEROP-01 and ZS-INTEROP-02: an empty input is `.invalid_argument`
- [ ] 2.5 ZS-TEST-11: a test that pops an empty stack

## 3. Verify

- [ ] 3.1 `agent-skill fmt`, `check --fast`, `check --skill zig-style --only toolchain` and
  `--only mutation` (survivors 11 → 0), the non-toolchain tests; record the results here
