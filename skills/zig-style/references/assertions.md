# Assertions, invariants, and putting a limit on everything

This chapter covers what to assert, where to put the assertion, what `std.debug.assert` actually
compiles to in each optimize mode, how to keep assertions alive in a release build, and the
discipline of bounding every loop, buffer, queue and retry count with a named comptime constant.
It does **not** own error-union design, `errdefer`, or the operating-error side of the split —
that is `references/errors.md`. Allocator lifetime and `undefined` poisoning are
`references/memory.md`; test structure and the `build.zig` wiring of fuzz steps are
`references/testing.md` and `references/build.md`; the optimize-mode table
is `references/build.md` ZS-BUILD-27. Naming (`connection_count_max`, not
`max_connections`) is specified in `references/naming.md` and applied here without
re-deriving it.

A `// fragment` block here uses types and constants declared elsewhere in this chapter. Every
example assumes a file opening with `const std = @import("std");`,
`const builtin = @import("builtin");` and `const assert = std.debug.assert;`. Examples use the
langref naming convention (`camelCase` functions); a codebase that has chosen TigerStyle's uniform
`snake_case` spells the helpers below `assert_always`, `assert_invariants`, and `maybe`.

**The thesis, from TigerStyle, stated once:** assertions detect *programmer* errors. Operating
errors are expected and must be handled; a corrupt program has exactly one correct response, which
is to stop. Assertions downgrade catastrophic correctness bugs into liveness bugs — a process that
halts loudly is recoverable, a process that silently writes wrong bytes to disk is not. And
assertions are a force multiplier for fuzzing: a fuzzer can only report a failure that some
assertion turns into a crash, so assertion density is the ceiling on what any amount of fuzzing
will ever find.

## Contents

- **Part 1 — What an assertion is, and what it compiles to**
  - ZS-ASSERT-01 [M] Alias `assert` at the top of the file, never call it qualified
  - ZS-ASSERT-02 [M] Assert programmer errors; return errors for operating errors
  - ZS-ASSERT-03 [M] Never put a side effect in an `assert`, and never claim it is compiled out
  - ZS-ASSERT-04 [M] Never make an assertion the last line of defense for memory or security safety
  - ZS-ASSERT-05 [M] Keep assertion conditions pure, cheap, and free of side effects
  - ZS-ASSERT-06 [M] Pick deliberately among `assert`, `unreachable`, `@panic`, and `fatal`
  - ZS-ASSERT-07 [M!] Ship `safe` builds, or define a project-local always-on assert
  - ZS-ASSERT-08 [S] Confine `@setRuntimeSafety(false)` to the narrowest block, and prove it
  - ZS-ASSERT-09 [M] In doc comments, "assert" means safety-checked and "assume" means unchecked
- **Part 2 — Where the assertions go**
  - ZS-ASSERT-10 [M!] Assert arguments at entry and results before return
  - ZS-ASSERT-11 [M!] Average at least two assertions per function
  - ZS-ASSERT-12 [M] Split compound assertions
  - ZS-ASSERT-13 [M] Write an implication as a single-line `if (a) assert(b);`
  - ZS-ASSERT-14 [M] Assert the negative space, and mark deliberate non-invariants with `maybe`
  - ZS-ASSERT-15 [M] State a biconditional as one `==` between two booleans
  - ZS-ASSERT-16 [M] Re-assert the narrowed state after every early-return guard
  - ZS-ASSERT-17 [S] Give each stateful type one `assertInvariants`, and bracket mutators with it
  - ZS-ASSERT-18 [M!] Pair every property across two code paths
  - ZS-ASSERT-19 [S] Use a blatantly true assertion where a comment would be weaker (see ZS-ASSERT-21)
  - ZS-ASSERT-20 [M] Budget assertion cost: unconditional when O(1), gated when O(N) over O(1)
- **Part 3 — Compile-time contracts**
  - ZS-ASSERT-21 [M] Assert the relationships between compile-time constants in a `comptime` block
  - ZS-ASSERT-22 [M] Give every wire, disk, and C-ABI type a layout `comptime` block
  - ZS-ASSERT-23 [M] Use `@compileError` for contracts the caller can violate
- **Part 4 — Put a limit on everything**
  - ZS-ASSERT-24 [M] Put a limit on everything, and give the limit a name ending in `_max`
  - ZS-ASSERT-25 [M] Keep all limits in one `constants.zig`: why, value, comptime relationships
  - ZS-ASSERT-26 [M] Derive dependent limits; never hand-copy a number
  - ZS-ASSERT-27 [M] Give every loop a provable bound; an unbounded loop must say so and assert it
  - ZS-ASSERT-28 [M] Fail fast: check the bound at the boundary where untrusted input enters
  - ZS-ASSERT-29 [S] Bounded containers assert on overflow; only caller-supplied sizes return errors
  - ZS-ASSERT-30 [M!] Do not recurse on unbounded data; bound the depth and assert it
- **Part 5 — Assertions, tests, and fuzzing**
  - ZS-ASSERT-31 [M] Inside `test` blocks use `std.testing.expect*`, not `assert` (see ZS-TEST-08)
  - ZS-ASSERT-32 [M] A fuzzer finds only what an assertion can catch — write the assertion first
  - ZS-ASSERT-33 [S] Write the assertions before the implementation (see ZS-ASSERT-32)

---

## Part 1 — What an assertion is, and what it compiles to

### ZS-ASSERT-01 [M] Alias `assert` at the top of the file, never call it qualified

Write `const assert = std.debug.assert;` in the import block and call `assert(...)` bare.

**Why:** assertions must be visually cheap, so that adding the fourth one to a function costs
nothing. The `std.debug.` prefix is ten characters of noise on every assertion line and pushes
real conditions past the 100-column limit. TigerBeetle's linter (`src/tidy.zig`) hard-bans the
literal string `"debug.assert("` for exactly this reason.

**Check:** the literal string `debug.assert(` anywhere below the import block, or a file that calls
`assert(` with no `const assert = std.debug.assert;` in its imports.

```zig
// fragment — BAD
std.debug.assert(header.size_bytes <= message_size_bytes_max);
```

```zig
// fragment — GOOD
const assert = std.debug.assert;
// ...
assert(header.size_bytes <= message_size_bytes_max);
```

### ZS-ASSERT-02 [M] Assert programmer errors; return errors for operating errors

If the condition can be violated by anything outside your process — a peer, a file, a user, the
network, the disk — it is an operating error and must be an error union. If it can only be
violated by your own code being wrong, it is an assertion.

**Why:** an assertion that fires on hostile input is a remote denial of service, and in a
`fast` build it is a remote memory-safety bug (ZS-ASSERT-04). Conversely, returning
`error.InvariantViolated` for a broken internal invariant asks the caller to handle a situation
that has no correct handling, and propagates a corrupt process instead of stopping it.

**Check:** an `assert` whose condition reads a value that arrived from a socket read, a file read,
`argv`, an environment variable, or a `pub fn` parameter on a parser — anything the process did
not compute itself. Conversely, an error set member named `Invariant*`, `Corrupt*`, or
`Impossible*` returned from a private helper.

```zig
// fragment — BAD
fn messageParse(bytes: []const u8) Header {
    assert(bytes.len <= message_size_bytes_max); // The peer chooses `bytes.len`.
    return readBlock(bytes);
}
```

```zig
// fragment — GOOD
const ParseError = error{ MessageTooLarge, MessageTooSmall, MessageEmpty } || HeaderInvalid;

fn messageParse(bytes: []const u8) ParseError!Header {
    // Operating errors: the peer chooses the length, so EVERY bound it can
    // violate is an error — including the lower bound. Asserting the lower
    // bound instead would make a 1..@sizeOf(Header)-1 byte frame a remote panic.
    if (bytes.len == 0) return error.MessageEmpty;
    if (bytes.len > message_size_bytes_max) return error.MessageTooLarge;
    if (bytes.len < @sizeOf(Header)) return error.MessageTooSmall;

    // From here down both bounds are programmer-error invariants: the guards
    // above established them, so a violation means this function is wrong.
    assert(bytes.len <= message_size_bytes_max);
    assert(bytes.len >= @sizeOf(Header));
    return try readBlock(bytes);
}
```

### ZS-ASSERT-03 [M] Never put a side effect in an `assert`, and never claim it is compiled out

**This rule is the single authoritative treatment of assert-under-optimization in the standard.**
ZS-ASSERT-04, -05, -07, -08 and -20 all rest on it and cite it rather than restating it.

`std.debug.assert` is an *ordinary function* — `pub fn assert(ok: bool) void { if (!ok) unreachable;
}` (`std/debug.zig`). Two separate consequences follow, and conflating them is the usual
mistake:

1. **The check is deleted in `fast` and `small`, and is replaced by an assumption.**
   `unreachable` is a panic in `debug` and `safe`, and an *optimizer assumption* in `fast` and
   `small`.
2. **The condition is still evaluated in all four modes.** `ok` is a function argument, so it is
   computed at the call site in every mode; `fast` discards the result, it does not skip the
   work. The assert is **not** compiled away — only the check is. On 0.17.0, a global
   counter incremented inside an assert condition reaches the same value under `-O debug`,
   `-O safe`, `-O fast` and `-O small`. So `assert(list.pop() != null)` still pops
   in release, it just stops verifying the result — see ZS-ASSERT-05.

| Mode | Safety checks | Condition evaluated | A false `assert(cond)` |
|---|---|---|---|
| `.debug` | on | yes | panic: `reached unreachable code` |
| `.safe` | on | yes | panic: `reached unreachable code` |
| `.fast` | off | **yes** | illegal behavior; the optimizer treats `cond` as proven |
| `.small` | off | **yes** | illegal behavior; the optimizer treats `cond` as proven |

**Why:** in the bottom two rows an assertion does not merely stop protecting you — it actively
*removes* protection, because LLVM propagates the assumed fact and deletes code that contradicts
it. TigerStyle's claim that assertions downgrade correctness bugs into liveness bugs is true only
in `debug` and `safe`. In `fast` a violated assertion *upgrades* a correctness bug into
arbitrary miscompilation. And because the condition still runs, you pay its full cost in release
while buying nothing.

**Check:** any `assert` whose condition mutates state or is worse than O(1); any comment or design
document claiming the assert "is compiled out" or "costs nothing in release".

```zig
// verified — BAD
const std = @import("std");
const assert = std.debug.assert;
var sink: u32 = 0;

noinline fn classify(x: u32) []const u8 {
    assert(x != 0); // In `fast` this is not a check, it is a promise.
    if (x == 0) return "zero"; // ... so the optimizer deletes this branch.
    return "nonzero";
}
```

Calling `classify(sink)` with `sink == 0` on Zig 0.17.0, observed:

- `-O safe`: `thread N panic: reached unreachable code` in `std.debug.assert`, exit 134 —
  the stack trace points straight at the violated assertion.
- `-O fast`: no diagnostic of any kind. The process dies on a trap instruction, SIGTRAP, exit
  133 — the branch that would have returned `"zero"` was gone.

### ZS-ASSERT-04 [M] Never make an assertion the last line of defense for memory or security safety

An `assert` before an unchecked index, an `@intCast`, a `@ptrCast`, a length arithmetic, or a
crypto-boundary check is documentation, not enforcement. If the invariant must hold in the shipped
binary, enforce it with a construct that survives: an `if` + error, `assertAlways` (ZS-ASSERT-07),
`std.math.cast`, or a checked slice operation.

**Why:** by ZS-ASSERT-03 the check is erased in `fast` *and* replaced by an assumption, so an
attacker who can violate it gets both the out-of-bounds access and the deleted bounds check that
would have caught it.

**Check:** an `assert` on the line immediately before `.ptr[`, `@intCast`, `@ptrCast`, `@alignCast`,
or pointer arithmetic, in code that ships anything but `safe`.

```zig
// fragment — BAD
fn read(buffer: []const u8, offset: usize) u8 {
    assert(offset < buffer.len); // Check gone in `fast`; now an assumption.
    return buffer.ptr[offset]; // Unchecked: `.ptr` skips the slice bounds check.
}
```

```zig
// fragment — GOOD
fn read(buffer: []const u8, offset: usize) u8 {
    assert(offset < buffer.len); // Keep it: it documents and it fires in test builds.
    return buffer[offset]; // Slice indexing is safety-checked in `debug`/`safe`.
}
```

### ZS-ASSERT-05 [M] Keep assertion conditions pure, cheap, and free of side effects

The condition is evaluated in every optimize mode (ZS-ASSERT-03, consequence 2), so a side effect
inside it is a side effect in release, and an expensive condition is a release-mode cost that buys
nothing. Hoist the effect out; gate the expense behind `verify` (ZS-ASSERT-20).

**Why:** on top of the cost, the optimizer is entitled to assume the result was `true` — the std doc
comment says it "is able to use the assertion in its heuristics" — so after inlining, a
side-effecting function whose result is asserted can be specialized on that assumption.

**Check:** an `assert(` whose condition contains `pop(`, `next(`, `orderedRemove(`, `fetch`, `++`,
an assignment, or a call whose name starts with a mutating verb; or one containing a scan
(`indexOf`, `contains`, a loop) that is not wrapped in `if (verify)`.

```zig
// fragment — BAD
assert(queue.pop() != null); // The pop happens in release too, unchecked.
assert(list.indexOfSlow(item) != null); // O(N) cost paid in `fast` for nothing.
```

```zig
// fragment — GOOD
const popped = queue.pop();
assert(popped != null);

if (verify) assert(list.indexOfSlow(item) != null); // Whole statement compiled out.
```

### ZS-ASSERT-06 [M] Pick deliberately among `assert`, `unreachable`, `@panic`, and `fatal`

| Construct | Survives `fast`? | On violation | Use for |
|---|---|---|---|
| `assert(cond)` | no | panic in `debug`/`safe`, UB otherwise | internal invariants |
| `unreachable` | no | same as above | a branch the types cannot rule out |
| `x catch unreachable` (never `.?` — ZS-ERR-30) | check removed | same as above | "this call cannot fail *here*" |
| `assertAlways(cond, msg)` | **yes** | always panics with `msg` | invariants that must halt |
| `@panic(msg)` | **yes** | always panics | a reached-corrupt-state branch |
| `std.debug.panic(fmt, args)` | **yes** | always panics, formatted | same, plus the values |
| `std.process.fatal(fmt, args)` | **yes** | `log.err` then `exit(1)` | operator-fixable |
| `@compileError(msg)` | n/a | compile error, your message | contracts violated at comptime |

**Why:** these are four genuinely different outcomes and blurring them costs debuggability.
`unreachable` prints `reached unreachable code` and nothing else; `@panic("checkpoint diverged")`
names the invariant; `std.debug.panic("op {d} exceeds {d}", .{ op, op_max })` names the values;
`std.process.fatal` exits with status 1 and an operator-actionable log message instead of a crash
dump, which is the right answer when the "impossible" state is really "the operator gave us too
little memory". (TigerBeetle's own `fatal` takes a leading `reason` enum so exit codes are
distinguishable per failure — that is a project-local helper, not std. std's is
`pub fn fatal(comptime format: []const u8, format_arguments: anytype) noreturn`, two parameters.)
`std.debug.panic` is `pub fn panic(comptime format: []const u8, args: anytype) noreturn`;
`@panic` accepts a runtime `[]const u8`.

**Check:** a `@panic(` whose message names no invariant (`@panic("unreachable")`, `@panic("bug")`,
`@panic("error")`); a bare `unreachable` on a branch a reader cannot rule out by inspection; and
any `std.process.exit(1)` not preceded by a logged reason — `std.process.fatal` does both in one
call.

```zig
// fragment — GOOD
// Resource exhaustion the operator can fix: orderly exit, not a crash.
const node_index = pool.free.findFirstSet() orelse std.process.fatal(
    "out of memory for manifest, restart with a larger --memory-lsm-manifest",
    .{},
);

// Corrupt state: log the evidence, then panic with the headline.
if (checkpoint_local != checkpoint_remote) {
    log.err("checkpoint diverged: local={x} remote={x}", .{ checkpoint_local, checkpoint_remote });
    @panic("checkpoint diverged");
}
```

### ZS-ASSERT-07 [M!] Ship `safe` builds, or define a project-local always-on assert

Decide the shipping optimize mode *before* you adopt assertion density.

`[M!]` applies to databases, consensus and replication, allocators, crypto, and embedded or kernel
control loops — anywhere a corrupt write or a silent miscompilation is unacceptable. There the
shipped binary must either be built with `-O safe` or route its critical invariants through
an assertion that survives `fast`. *Relaxed form:* `std.debug.assert` plus a `safe` test
and staging build is acceptable, provided the README names the shipping optimize mode explicitly
instead of leaving it implicit.

**Why:** std ships no always-on assert; `std.debug.assert` is the only one and its check does not
survive `fast` (ZS-ASSERT-03). TigerBeetle's answer is to ship `safe`
(`b.standardOptimizeOption(.{ .preferred_optimize_mode = .safe })` in 0.17; see
`references/build.md` ZS-BUILD-27). If you cannot pay `safe`'s cost, the
alternative is a two-line helper, which panics under `-O fast` on 0.17.0 where the
equivalent `assert` died on a bare trap. `assertAlways` is legal in a library: it reports a violated
invariant, not an operating error, so it does not take a recovery option away from the caller
(`references/errors.md` ZS-ERR-03).

```zig
// verified — GOOD
/// Assertion that is present in every optimize mode, including `fast` and
/// `small`. Use where a violated invariant must halt the process rather
/// than become an optimizer assumption.
pub fn assertAlways(ok: bool, comptime message: []const u8) void {
    if (!ok) @panic(message);
}
```

> Honest divergence: idiomatic std uses `assert` sparingly, for genuine internal invariants, and
> reaches for error unions or documented illegal behavior at API boundaries; it never assumes a
> `safe` deployment. TigerStyle assumes one. If you follow TigerStyle's density target while
> shipping `fast` without an `assertAlways` escape hatch, you have the worst of both: the
> code reads as if it is checked, and none of it is.

**Check:** a `build.zig` with no `preferred_optimize_mode` and a README that does not name the
shipping mode, in a repo whose source averages more than one `assert` per function.

### ZS-ASSERT-08 [S] Confine `@setRuntimeSafety(false)` to the narrowest block, and prove it

Never reach for `fast` whole-binary to speed up one loop. Keep the build `safe` and
disable safety in the smallest scope that contains the hot arithmetic, with a comment proving the
check is redundant.

**Why:** `@setRuntimeSafety` sets safety for the scope containing the call and is overridable at
any nested scope, so the blast radius is exactly what you write — whereas `fast`'s blast radius
is every assertion in the program (ZS-ASSERT-03).

**Check:** a `@setRuntimeSafety(false)` that is the first statement of a function or a file's
top-level block rather than of the innermost block containing the arithmetic, or one with no comment
on an adjacent line proving the removed check is redundant.

```zig
// verified — GOOD
const std = @import("std");
const assert = std.debug.assert;
fn sumUnchecked(values: []const u8) u32 {
    assert(values.len <= 1024);
    var total: u32 = 0;
    for (values) |value| {
        // Bound proven above: 1024 * 255 < maxInt(u32), so overflow is impossible.
        @setRuntimeSafety(false);
        total += value;
    }
    return total;
}
```

> [!NOTE] The 0.17.0 langref, like 0.16.0's, states that `@setRuntimeSafety` is *planned* to be
> replaced by `@optimizeFor`. `@optimizeFor` does not exist in 0.17.0: it is
> `error: invalid builtin function: '@optimizeFor'`.

### ZS-ASSERT-09 [M] In doc comments, "assert" means safety-checked and "assume" means unchecked

The langref style guide makes this a lexical rule: use the word **assert** to describe an invariant
whose violation is safety-checked illegal behavior, and **assume** for one whose violation is
unchecked illegal behavior. Never swap them.

**Why:** the reader of `/// Asserts that `index` is in bounds.` will test the failure path and
expect a panic. The reader of `/// Assumes `ptr` is aligned.` knows there is nothing to test and
that they own the proof. Blurring the two words makes it impossible to tell from a doc comment
which side of the memory-safety line a function sits on.

**Check:** grep `///` lines for `ssert` and `ssume`, then match each against the body. "Asserts"
with no `assert(`, no safety-checked index, and no checked cast in the body is a lie; "assumes"
above a body that does check is merely stale, and both mislead in the same direction.

```zig
// fragment — GOOD
/// Asserts that `index < count`.
pub fn get(ring: *const Ring, index: u32) u8 { ... }

/// Assumes `bytes` is aligned to `@alignOf(Header)`; misalignment is unchecked.
pub fn headerCast(bytes: []align(@alignOf(Header)) const u8) *const Header { ... }
```

---

## Part 2 — Where the assertions go

### ZS-ASSERT-10 [M!] Assert arguments at entry and results before return

Preconditions first, before any early return. Postconditions on the computed value, immediately
before returning it. A function must not operate blindly on data it has not checked.

`[M!]` applies to databases, storage engines, consensus and replication, allocators, crypto,
parsers on untrusted input, and embedded control — anywhere a wrong answer outlives the process or
goes unobserved. *Relaxed form:* stated once, by ZS-ASSERT-11 — assert the contract of every
function whose parameter types do not already enforce it. A boundary taking untrusted input gets
`if` + error, never an assert (ZS-ASSERT-02, ZS-ASSERT-28).

**Why:** a precondition asserted at the top of the callee fires at the first caller that is wrong,
with that caller on the stack. The same bug caught three frames deeper gives you a stack trace
through code that is behaving correctly. Postconditions catch the case where the arguments were
fine and the body is wrong, which no caller-side check can find.

**Check:** a function taking two or more independent integer/slice parameters with a relationship
between them (`offset` and `len`, `target` and `source`) and no `assert` on line one.

```zig
// fragment — GOOD
fn writeBlock(target: []u8, header: *const Header, body: []const u8) void {
    assert(body.len == header.size_bytes);
    assert(target.len == @sizeOf(Header) + body.len);
    headerValidate(header);

    @memcpy(target[0..@sizeOf(Header)], std.mem.asBytes(header));
    @memcpy(target[@sizeOf(Header)..], body);

    assert(std.mem.eql(u8, target[@sizeOf(Header)..], body));
}
```

### ZS-ASSERT-11 [M!] Average at least two assertions per function

`[M!]` applies to databases, storage engines, consensus and replication, allocators, crypto, and
embedded or kernel firmware — anything where a crash beats a wrong answer. There the assertion
density of the codebase must average a minimum of two assertions per function. Measured in real
TigerBeetle source the control plane runs well above that floor — counted at tigerbeetle 97c7a8e,
`rg -c 'assert\('` over `rg -c '^[ \t]*(pub )?fn '`: `src/vsr/replica.zig` 5.90 per function
(1582/268, one per 7.8 lines), `src/vsr/journal.zig` 4.15, `src/state_machine.zig` 3.87.

*Relaxed form:* in ordinary application code the honest rule is: **every function whose contract is
not already enforced by its parameter types asserts that contract, and every function that computes
a value with a checkable property asserts it.** A pure function from `Color` to `[]const u8` needs
none. A function taking `(offset: usize, len: usize)` into a buffer needs two.

**Why:** the count is a proxy, not the goal — the goal is that every unencoded assumption is
written down. But the count is the only proxy that survives code review, and it forces the
question "what do I actually know here?" on every function rather than only the scary ones.

**Check:** ratio of `rg -c '\bassert\('` to `rg -c '^[ \t]*(pub )?fn '` over the module. Per diff,
the
finding is any added function that takes a relationship between two parameters — an `offset` and a
`len`, an index and a count, two slices that must be the same length — and asserts none of it.

> Honest divergence: std is far sparser than two per function and deliberately so — it prefers
> error unions and documented illegal behavior at public boundaries. Do not "fix" std-style code
> by sprinkling asserts into public API entry points where the input is untrusted (ZS-ASSERT-02);
> add them to the internal helpers where the input is your own.

### ZS-ASSERT-12 [M] Split compound assertions

Prefer `assert(a); assert(b);` over `assert(a and b);`.

**Why:** the panic reports a line and a column. With `assert(a and b)` you learn that one of two
things failed and must re-run to find out which; with two statements the stack trace names the
exact predicate. The cost is zero — the generated code is identical.

**Check:** an `assert(` whose condition contains a top-level ` and `. (A ` and ` nested inside an
`if (a) assert(b);` implication or inside a parenthesised sub-expression is not a hit.)

```zig
// fragment — BAD
assert(budget.capacity > 0 and budget.available <= budget.capacity);
```

```zig
// fragment — GOOD
assert(budget.capacity > 0);
assert(budget.available <= budget.capacity);
```

### ZS-ASSERT-13 [M] Write an implication as a single-line `if (a) assert(b);`

**Why:** `assert(!a or b)` is the same predicate written as a negation, and negations are exactly
where reviewers stop being able to check the logic by inspection. The `if` form also reads in the
direction the domain reads ("if the transfer is pending, then it has a timeout") and greps
cleanly. Keep it on one line so it is visually an assertion, not control flow.

**Check:** an `assert(!` whose condition also contains ` or ` — that is an implication written as
a negated disjunction. Also an `if (…) {` block whose entire body is one `assert(…);`, which
should have been the one-line form.

```zig
// fragment — BAD
assert(!pending or timeout_ms > 0);
```

```zig
// fragment — GOOD
fn transferValidate(amount: u64, pending: bool, timeout_ms: u32) void {
    assert(amount > 0);
    assert(amount <= std.math.maxInt(u64) / 2);
    if (pending) assert(timeout_ms > 0);
    if (!pending) assert(timeout_ms == 0);
    maybe(amount == 1);
}
```

### ZS-ASSERT-14 [M] Assert the negative space, and mark deliberate non-invariants with `maybe`

The golden rule: assert the positive space you *do* expect **and** the negative space you do
*not*. Then, for every state variable a reader might reasonably assume is pinned at this program
point but is not, write `maybe(...)`.

**Why:** bugs cluster where data crosses the valid/invalid boundary, and only a negative-space
assertion sits on that boundary. `maybe` closes the other half: silence is ambiguous — the reader
cannot tell whether you knew `status` could be `.recovering_head` here or simply never thought
about it. `maybe` compiles to nothing and turns that silence into a claim.

**Check:** a range asserted on one side only — an `assert(index < count)` with no companion bound
below, an `assert(x != null)` with no arm for the null case — and any enum-valued or optional
field the function reads without either asserting or `maybe`-ing it. A module whose diff adds
`assert` and never `maybe` is the aggregate smell.

```zig
// verified — GOOD
/// The dual of `assert`: this condition is sometimes true and sometimes false
/// here. Documents the negative space; compiles to nothing.
const std = @import("std");
const assert = std.debug.assert;
pub fn maybe(ok: bool) void {
    assert(ok or !ok);
}
```

```zig
// fragment — GOOD
// Negative before, positive after: the pair brackets the mutation.
if (verify) assert(!level.contains(table));
level.insert(table);
if (verify) assert(level.contains(table));
```

### ZS-ASSERT-15 [M] State a biconditional as one `==` between two booleans

When two representations must agree, assert the equality of the two predicates rather than writing
two one-directional assertions or, worse, one.

**Why:** `assert((count == 0) == (head == null))` catches both a non-empty count with a null head
*and* a zero count with a live head, in one line. Two separate implication assertions catch the
same thing at twice the length; a single implication catches half the bugs.

**Check:** a lone `if (a) assert(b);` between two fields that are two spellings of one fact — a
count and a head pointer, a length and a sentinel, a flag and the field it guards. One direction
asserted where both must hold is the defect; the fix is `assert((a) == (b));`.

```zig
// verified — GOOD
const std = @import("std");
const assert = std.debug.assert;
const Stack = struct {
    head: ?*Link,
    count: u32,

    const Link = struct { next: ?*Link };

    fn assertInvariants(stack: *const Stack) void {
        assert((stack.count == 0) == (stack.head == null));
    }
};
```

### ZS-ASSERT-16 [M] Re-assert the narrowed state after every early-return guard

Each guard clause buys you a stronger fact about the rest of the function. Write it down.

**Why:** after `if (status != .normal) return;` the remainder of the function knows
`status == .normal`, but nothing in the source says so, so a later refactor that moves the guard
or adds a path around it silently invalidates ten lines of reasoning. Re-asserting makes the
refactor fail loudly at the exact point where the assumption was used.

**Check:** a run of early-return guards (`if (cond) return …;`) with no `assert` restating the
negation of each `cond` on the line after the last guard.

```zig
// fragment — GOOD
fn sendPrepareOk(status: Status, view: u32, op: u64, op_max: u64) bool {
    assert(view > 0);
    maybe(op > op_max);

    if (status != .normal) return false;
    if (op > op_max) return false;

    assert(status == .normal);
    assert(op <= op_max);
    return true;
}
```

### ZS-ASSERT-17 [S] Give each stateful type one `assertInvariants`, and bracket mutators with it

Collect the type's whole-object invariants in one private function taking `*const T`. Every public
mutator opens with `x.assertInvariants(); defer x.assertInvariants();`.

**Why:** `defer` runs on *every* exit path including early returns and error returns, so one line
covers exits you have not written yet. It also gives the invariant a single home, so adding a
field means editing one function rather than auditing every method. TigerBeetle's
`src/vsr/repair_budget.zig` uses this shape 19 times in 464 lines (tigerbeetle 97c7a8e — spelled
`assert_invariants` there, TigerBeetle's snake_case function convention; this standard follows
std's `camelCase` for callables, ZS-NAME-01).

**Check:** in a type that declares `assertInvariants`, a `pub fn` taking `*T` that writes any field
without the `x.assertInvariants(); defer x.assertInvariants();` opening pair. A new field added to
such a type with no corresponding line in `assertInvariants` is the same finding one level up.

```zig
// verified — GOOD
const std = @import("std");
const assert = std.debug.assert;
const RepairBudget = struct {
    capacity: u32,
    available: u32,
    outstanding: u32,

    fn assertInvariants(budget: *const RepairBudget) void {
        assert(budget.capacity > 0);
        assert(budget.available <= budget.capacity);
        assert(budget.capacity - budget.available == budget.outstanding);
    }

    pub fn decrement(budget: *RepairBudget) ?u32 {
        budget.assertInvariants();
        defer budget.assertInvariants();

        if (budget.available == 0) return null;
        budget.available -= 1;
        budget.outstanding += 1;
        return budget.available;
    }
};
```

State the same invariant in prose in the type's doc comment as well as in code — prose alone rots,
code alone is unreadable:

```zig
// fragment — GOOD
/// Invariant: suspend_size <= process_size <= advance_size <= receive_size.
pub const MessageBuffer = struct { ... };
```

### ZS-ASSERT-18 [M!] Pair every property across two code paths

For every property you want to enforce, find at least two *different* code paths where an
assertion can check it. The canonical pair is: assert validity right before writing to disk, and
again immediately after reading back.

`[M!]` applies to databases, filesystems, ledgers, replication and consensus, wire codecs, and
crypto — anything whose stored or transmitted bytes outlive the process, so that a silent encoding
bug becomes permanent corruption. There, every serialized or persisted structure is checked on both
paths. *Relaxed form:* pair the property for at least the formats you cannot change later —
anything persisted or sent over a wire.

**Why:** a single assertion on the write path proves only that the writer's *in-memory* value was
sane. It says nothing about the encoder, the padding, the alignment, the sector boundary, the
storage layer, or bit rot. The read-side assertion is checking a different function of a different
byte sequence, so it catches the entire class of bugs between the two — and when only one of the
pair fires, the failure has already been localized to that half.

**Check:** a `*Validate` or `*Verify` helper called from exactly one of an encode/decode,
serialize/deserialize, or write/read pair. Grep the callers of the validator: one call site means
half the property is unchecked.

```zig
// fragment — GOOD
const HeaderInvalid = error{HeaderInvalid};

/// Path 1 runs on a header this process just built, so a violation is a
/// programmer error and asserting is correct.
fn headerValidate(header: *const Header) void {
    assert(header.checksum != 0);
    assert(header.size_bytes > 0);
    assert(header.size_bytes <= message_size_bytes_max);
    assert(header.replica_index < connection_count_max);
    for (header.reserved) |byte| assert(byte == 0);
}

/// Path 2 checks the SAME properties on bytes that came from outside the
/// process. Same predicates, different mechanism: peer data is validated and
/// rejected, never asserted (ZS-ASSERT-02) — an assert here is a remote DoS.
fn headerCheck(header: *const Header) HeaderInvalid!void {
    if (header.checksum == 0) return error.HeaderInvalid;
    if (header.size_bytes == 0) return error.HeaderInvalid;
    if (header.size_bytes > message_size_bytes_max) return error.HeaderInvalid;
    if (header.replica_index >= connection_count_max) return error.HeaderInvalid;
    for (header.reserved) |byte| if (byte != 0) return error.HeaderInvalid;
}

fn writeBlock(target: []u8, header: *const Header, body: []const u8) void {
    assert(body.len == header.size_bytes);
    assert(target.len == @sizeOf(Header) + body.len);
    headerValidate(header); // <- path 1: before the bytes leave memory.

    @memcpy(target[0..@sizeOf(Header)], std.mem.asBytes(header));
    @memcpy(target[@sizeOf(Header)..], body);

    assert(std.mem.eql(u8, target[@sizeOf(Header)..], body));
}

fn readBlock(source: []const u8) HeaderInvalid!Header {
    assert(source.len >= @sizeOf(Header)); // The caller's guard established this.

    var header: Header = undefined;
    @memcpy(std.mem.asBytes(&header), source[0..@sizeOf(Header)]);
    try headerCheck(&header); // <- path 2: validate, never assert, on peer bytes.

    if (source.len != @sizeOf(Header) + header.size_bytes) return error.HeaderInvalid;
    return header;
}
```

Note that pairing a property does **not** mean pairing the *mechanism*. The write path owns bytes
this process just built, so it asserts; the read path owns bytes a peer chose, so it validates and
returns an error (ZS-ASSERT-02). Asserting on the read path would turn every corrupt or hostile
frame into a remote panic — and in `fast` into an optimizer assumption that deletes the very bounds
check a later `connections[header.replica_index]` depends on. Same predicates, two mechanisms,
chosen by who controls the bytes.

The same idea inside one function: assert the structural invariant at both ends, so a bug in the
middle is bracketed rather than merely detected somewhere downstream.

### ZS-ASSERT-19 [S] Use a blatantly true assertion where a comment would be weaker (see ZS-ASSERT-21)

Owned by ZS-ASSERT-21. A permission, not an obligation: where a
load-bearing fact is obvious *today*, asserting it is stronger documentation than a comment, because
the assertion cannot drift out of date.

### ZS-ASSERT-20 [M] Budget assertion cost: unconditional when O(1), gated when O(N) over O(1)

Two tiers. In the control plane — anything batched, where per-operation overhead is amortized —
assert unconditionally; it is acceptable to spend O(N) verifying an O(1) computation there. In the
data plane, do an unconditional O(1) check before an O(N) loop, and gate any O(N) whole-structure
verification behind a `verify` constant.

**Why:** slow assertions reduce total coverage. Randomized testing coverage is proportional to the
number of iterations you can run, so an O(N) invariant check on an O(1) hot-path mutation makes
the fuzzer quadratically weaker at finding the bug it was meant to catch. The gate must be `if
(verify)` around the *whole statement*, not the assert alone: by ZS-ASSERT-03 the condition inside an
`assert` still runs in `fast`, so `assert(queue.contains(link))` pays the O(N) scan in release
and gets nothing for it. Define `verify` from your own module's
`@import("builtin").optimize.runtimeSafety()` — `std.debug.runtime_safety` is deprecated in its
favour (to be removed after 0.18.0) because it reports the *standard library's* optimize mode, not
your module's.

**Check:** an `assert(` containing a loop, a `contains`, or a whole-structure walk that is not
preceded by `if (verify)` on the same line.

```zig
// verified — GOOD
/// Expensive O(N) checks are compiled only when `verify` is true.
const builtin = @import("builtin");
pub const verify = builtin.optimize.runtimeSafety();
```

```zig
// fragment — GOOD
pub fn push(queue: *Queue, link: *Link) void {
    if (verify) assert(!queue.contains(link)); // O(N) whole-list scan: gated.
    assert(link.next == null); // O(1): unconditional.
    // ...
}
```

---

## Part 3 — Compile-time contracts

### ZS-ASSERT-21 [M] Assert the relationships between compile-time constants in a `comptime` block

Every derived or co-dependent constant gets a `comptime {}` block stating the relationship that
must hold.

**Why:** compile-time assertions check the program's design integrity *before* the program runs,
they are free, and — this is the part that matters in Zig — they are the one kind of assertion
that is **always on in every optimize mode**, because they never reach codegen. This makes them
the highest value-per-character construct in the whole standard. A comptime assert also catches
the failure at the moment someone edits the constant, not on the machine where the ratio finally
mattered.

**Check:** a file declaring two or more `pub const` numbers where one's correctness depends on the
other — a `%`, an `@divExact`, a power-of-two assumption, or a ceiling relied on at some call
site — with no `comptime {}` block anywhere in the file asserting that relation.

```zig
// fragment — GOOD
comptime {
    assert(std.math.isPowerOfTwo(sector_size_bytes));
    assert(block_size_bytes % sector_size_bytes == 0);
    assert(message_size_bytes_max % sector_size_bytes == 0);
    assert(connection_count_max > 0);
}
```

You **may** also assert a fact that is blatantly true today, where a comment would be weaker
(ZS-ASSERT-19): `assert(KiB == 1024)` cannot drift the way `// KiB is 1024` can, and it is free.
This deliberately contradicts NASA's Power of Ten rule 5, which forbids assertions a static checker
can prove always hold; TigerStyle overrides that because the value here is communicative and
drift-proofing, not detection. Reserve it for load-bearing facts — an `assert(true)` next to trivia
is noise.

Be aware of the diagnostic quality: a failing `comptime assert` reports
`error: reached unreachable code` inside `std.debug.assert` with a `note: called at comptime here`
pointing at your line. You get the location but not the reason — which is why caller-facing
contracts use `@compileError` instead (ZS-ASSERT-23).

### ZS-ASSERT-22 [M] Give every wire, disk, and C-ABI type a layout `comptime` block

Any `extern struct` or `packed struct` that is serialized, persisted, hashed, or passed across a C
boundary carries a `comptime {}` asserting `@sizeOf`, `@alignOf`, and the absence of padding.

**Why:** field layout is decided by the compiler from the field list. Adding one `u16` silently
changes `@sizeOf`, which silently changes the on-disk format, which corrupts every existing file —
with no compile error anywhere. The comptime block turns that into a build failure on the commit
that introduces it. Padding bytes are also the buffer-bleed vector, so assert their absence: for an
`extern struct` use `std.meta.hasUniqueRepresentation(T)`, which compares `@sizeOf(T)` against the
sum of the field sizes. Do **not** use `@bitSizeOf(T) == @sizeOf(T) * 8` for that on an `extern
struct` — on 0.17.0 `@bitSizeOf` of any struct that is not packed is a compile error
(`no bit size available for type …`), and on 0.16 it *included* padding, so
`extern struct { a: u8, b: u64 }` passed it. That identity is only meaningful on a
`packed struct(uN)`, where it checks that the backing integer fills its bytes.

**Check:** an `extern struct` or `packed struct` that appears in a `@memcpy`, `std.mem.asBytes`,
`bytesAsValue`, a `read`/`write` call, or an `extern fn` signature, with no `comptime {}` block
asserting `@sizeOf`. Separately, any `@bitSizeOf(T) == @sizeOf(T) * 8` applied to an `extern
struct` — 0.17 rejects it, and on 0.16 it passed with padding present and so proved nothing.

```zig
// verified — GOOD
const std = @import("std");
const assert = std.debug.assert;
const Header = extern struct {
    checksum: u128,
    cluster: u128,
    op: u64,
    timestamp_ns: u64,
    size_bytes: u32,
    replica_index: u8,
    reserved: [75]u8 = @splat(0),

    comptime {
        assert(@sizeOf(Header) == 128);
        assert(@alignOf(Header) == 16);
        // No implicit padding: every byte of the struct belongs to a field.
        assert(std.meta.hasUniqueRepresentation(Header));
    }
};

const Flags = packed struct(u16) {
    linked: bool = false,
    pending: bool = false,
    padding: u14 = 0,

    comptime {
        assert(@sizeOf(Flags) == @sizeOf(u16));
        assert(@bitSizeOf(Flags) == @sizeOf(Flags) * 8);
    }
};
```

### ZS-ASSERT-23 [M] Use `@compileError` for contracts the caller can violate

When a generic function or a `comptime` parameter has a precondition that a *user* of your code
can break, state it with `@compileError` and an explanatory message. Reserve `comptime assert` for
relationships internal to your own module.

**Why:** the two produce very different diagnostics. `@compileError` prints your sentence at the
offending call site; a failing `comptime assert` prints `reached unreachable code` inside
`std/debug.zig` and makes the caller reverse-engineer the contract.
Use the same construct to document a deliberately absent API:
`pub const intExclusive = @compileError("intentionally not implemented: ranges are closed");`

**Check:** a `comptime assert(` inside a `fn Foo(comptime …) type` or a function with a `comptime`
parameter, whose condition constrains that caller-supplied parameter rather than the module's own
constants. Every such assert should be an `if (…) @compileError("<sentence>");`.

```zig
// verified — GOOD
const std = @import("std");
const assert = std.debug.assert;
fn RingBuffer(comptime T: type, comptime capacity: u32) type {
    if (capacity == 0) @compileError("RingBuffer capacity must be non-zero");
    if (!std.math.isPowerOfTwo(capacity)) {
        @compileError("RingBuffer capacity must be a power of two, so that " ++
            "index wrapping is a mask rather than a division");
    }
    return struct {
        items: [capacity]T,
        head: u32,
        count: u32,

        const Self = @This();
        const mask: u32 = capacity - 1;

        pub fn get(self: *const Self, index: u32) T {
            assert(index < self.count);
            return self.items[(self.head + index) & mask];
        }
    };
}
```

`RingBuffer(u8, 3)` reports, verbatim:
`error: RingBuffer capacity must be a power of two, so that index wrapping is a mask rather than a
division`, with a note at the call site.

---

## Part 4 — Put a limit on everything

### ZS-ASSERT-24 [M] Put a limit on everything, and give the limit a name ending in `_max`

Every buffer, queue, batch, connection table, retry count, timeout, recursion depth, and message
size has a fixed upper bound expressed as a named comptime constant. No bare literals at the use
site; no "it grows as needed" without a stated ceiling.

**Why:** in reality everything has a limit — the only question is whether you chose it or whether
it is discovered in production as an OOM, an unbounded queue, or a tail-latency spike. A named
constant also makes the bound assertable (ZS-ASSERT-28) and reviewable: `connection_count_max = 64`
invites the question "is 64 right?", while `try list.append(gpa, conn)` invites nothing. Names use
big-endian ordering — `latency_ms_max`, not `max_latency_ms` — so related limits sort and group
together (see `references/naming.md`).

**Check:** an `alloc`, `ensureTotalCapacity`, `@memcpy` length, retry loop, or timeout whose size
comes from a runtime value with no `_max` constant asserted against it on a preceding line; and any
bare integer literal at a use site that is really a limit rather than an offset.

```zig
// fragment — BAD
var buffer = try gpa.alloc(u8, header.size_bytes); // Bounded by nothing.
```

```zig
// fragment — GOOD
assert(header.size_bytes <= message_size_bytes_max);
var buffer = try gpa.alloc(u8, header.size_bytes);
```

### ZS-ASSERT-25 [M] Keep all limits in one `constants.zig`: why, value, comptime relationships

One file holds every configured and derived limit. Each constant carries a `///` comment saying
*why that number*, and the file ends each group with a `comptime {}` block asserting the
relationships between them.

**Why:** limits are not independent. `request_memory_bytes` is a function of three other constants,
and the ceiling that actually matters (fits in the cgroup) is a property of the combination, not
of any one of them. Scattering the numbers across the modules that use them means nobody can ever
check the combination. Centralizing also makes "what does this process cost at maximum load?" a
question you can answer by reading one file.

**Check:** a `pub const … _max` declared in any file other than `constants.zig`, or one declared
there with no `///` comment giving the reason for that number, or a group of related limits with no
trailing `comptime {}` block asserting the relationships between them.

```zig
//! Every limit in the system, with the reason for its value and the
//! relationships that must hold between limits.
// fragment — GOOD: this is the head of its own file

/// Physical sector size we assume for atomic writes on all supported storage.
pub const sector_size_bytes: u32 = 4096;

/// One LSM block. Chosen so that a block read is one sequential I/O.
pub const block_size_bytes: u32 = 64 * 1024;

/// The largest message a peer may send us. Anything larger is rejected at the
/// socket, before a single byte is copied into a request buffer.
pub const message_size_bytes_max: u32 = 1024 * 1024;

/// Concurrent client connections. Bounds the connection table, which is
/// allocated once at startup.
pub const connection_count_max: u32 = 64;

/// Requests queued per connection. Bounds worst-case memory:
/// connection_count_max * request_queue_count_max * message_size_bytes_max.
pub const request_queue_count_max: u32 = 8;

/// Derived: total request buffer memory reserved at startup.
pub const request_memory_bytes: u64 =
    @as(u64, connection_count_max) * request_queue_count_max * message_size_bytes_max;

/// Derived: blocks per message, rounding up so a partial block still fits.
pub const blocks_per_message_max: u32 = @divCeil(message_size_bytes_max, block_size_bytes);

comptime {
    assert(std.math.isPowerOfTwo(sector_size_bytes));
    assert(std.math.isPowerOfTwo(block_size_bytes));
    assert(block_size_bytes % sector_size_bytes == 0);
    assert(message_size_bytes_max % sector_size_bytes == 0);

    assert(connection_count_max > 0);
    assert(request_queue_count_max > 0);

    // A single message must never exceed the memory we reserved for one slot.
    assert(message_size_bytes_max <= request_memory_bytes);
    // Keep startup memory under 1 GiB so the process fits its cgroup budget.
    assert(request_memory_bytes <= 1024 * 1024 * 1024);

    assert(blocks_per_message_max >= 1);
    assert(blocks_per_message_max * block_size_bytes >= message_size_bytes_max);
}
```

### ZS-ASSERT-26 [M] Derive dependent limits; never hand-copy a number

If limit B is a function of limit A, compute B from A. A literal that *happens* to equal the
quotient today is a latent bug waiting for someone to change the divisor. Use a labelled block when
the derivation needs locals, and keep the derived constant next to its inputs in `constants.zig`
(ZS-ASSERT-25).

The *rounding* half — `@divExact` / `@divFloor` / `@divTrunc` / `@divCeil` (new in 0.17), never a
bare `/` — is owned by `references/data.md` ZS-DATA-06. `@divExact` is the strongest of
the four because it asserts the remainder is zero, which is usually the claim a derived limit means
to make.

**Why:** a hand-copied `16` beside a computed `message_size_bytes_max / block_size_bytes` is
invisible in review, because both are correct on the day they are written. Deriving it turns
"someone forgot to update the other number" into an impossibility rather than a code-review
responsibility, and it makes the *relationship* the reviewable artifact rather than the value.

```zig
// fragment — BAD
pub const blocks_per_message_max: u32 = 16; // Wrong the moment block_size_bytes changes.
```

```zig
// fragment — GOOD
// `@divCeil` needs no `catch unreachable`, unlike `std.math.divCeil`: it returns the
// quotient, and this is comptime-evaluated, so a zero divisor is a compile error.
pub const blocks_per_message_max: u32 = @divCeil(message_size_bytes_max, block_size_bytes);

pub const sectors_per_block: u32 = @divExact(block_size_bytes, sector_size_bytes);
```

**Check:** two `pub const … _max` declarations in `constants.zig` where one is an integer literal
that equals an arithmetic combination of the others.

### ZS-ASSERT-27 [M] Give every loop a provable bound; an unbounded loop must say so and assert it

This rule owns loop bounds for the whole standard; `references/errors.md` ZS-ERR-24
points here.

**Reach for `for` first.** `for (slice)` and `for (0..limit)` carry their bound in the syntax, so
there is nothing left to prove. A `while` is a claim that the termination argument does not fit in a
range, and that claim has to be paid for. Four shapes, all legitimate:

- (a) iterate a counted range and close with `else unreachable` when the loop must exit early;
- (b) iterate a counted range and close with `else` + a panic naming the exceeded limit;
- (c) keep a `while` and a witness counter, and assert the counter against a named `_max` constant
  *inside* the loop, so it fires on the offending iteration rather than after the hang;
- (d) a loop that genuinely cannot terminate — an event loop — is commented as intentional, and the
  reverse property (that it does not exit early, or that shutdown was observed) is asserted.

**Why:** NASA's Power of Ten rule 2, adopted verbatim by TigerStyle: it must be trivially provable
that a preset upper bound on iterations cannot be exceeded. An unbounded `while (true)` over a data
structure turns a corrupt pointer — a cycle in a linked list, a stale index — from a crash into a
hang, which is strictly harder to diagnose and, in a replicated system, strictly worse than
crashing. Unbounded is also not only "forever": it is an unbounded tail-latency spike, which
presents in production as the same undiagnosable stall. The counter converts both into a crash with
a stack trace. The `else` clause on a Zig `for` runs only when the loop was *not* broken out of,
which is precisely the "bound exceeded" condition.

The same reasoning applies to anything that grows per iteration — queues, buffers, retry counts,
backlogs. Everything has a limit; name it (ZS-ASSERT-24).

```zig
// verified — GOOD
const std = @import("std");
const assert = std.debug.assert;
const ListNode = struct { next: ?*ListNode = null };

// (a) Counted range; falling through the range is impossible by construction.
fn listContains(head: ?*ListNode, count: u32, needle: *const ListNode) bool {
    var next = head;
    for (0..count + 1) |_| {
        const node = next orelse return false;
        if (node == needle) return true;
        next = node.next;
    } else unreachable; // The list is `count` long, so the loop always exits early.
}

// (b) Counted range; exceeding the bound is a real, reportable condition.
fn parseImports(text: []const u8) u32 {
    const imports_count_max = 1024;
    var rest = text;
    var count: u32 = 0;
    for (0..imports_count_max + 1) |_| { // +1: exactly `_max` imports is legal.
        const at = std.mem.find(u8, rest, "@import(") orelse break;
        rest = rest[at + "@import(".len ..];
        count += 1;
    } else {
        std.debug.panic("more than {d} imports in one file", .{imports_count_max});
    }
    assert(count <= imports_count_max);
    return count;
}

// (c) A `while` whose termination is not syntactic: witness counter, asserted
// inside the loop so it fires on the offending iteration rather than after a hang.
const halvings_max = 64;

fn converge(start: f64) f64 {
    var value = start;
    var halvings: u32 = 0;
    while (@abs(value) > 0.001) {
        value /= 2.0;
        halvings += 1;
        assert(halvings <= halvings_max);
    }
    return value;
}

// (d) Deliberately unbounded, stated as such, with a witness asserted after.
fn eventLoopIterations(budget: u32) u32 {
    var ticks: u32 = 0;
    while (true) {
        // This loop is intentionally unbounded: it is the process event loop.
        ticks += 1;
        if (ticks == budget) break;
    }
    assert(ticks == budget);
    return ticks;
}
```

Note `std.mem.find` — in 0.16 the whole `indexOf*` family was renamed to `find*`; the old names
still compile as deprecated aliases, so this is a silent staleness rather than a build error.

**Check:** a `while` whose condition is not `it.next()`, `stack.pop()`, or a counter comparison,
with no `_max` constant asserted in its body; and any `while (true)` with no comment saying it is
intended.

### ZS-ASSERT-28 [M] Fail fast: check the bound at the boundary where untrusted input enters

Reject an over-limit value at the point of entry — the socket read, the CLI parse, the file
header — not at the point of use. After the boundary check, the bound becomes an asserted
invariant everywhere downstream.

**Why:** the distance between where a bad value is admitted and where it does damage is the whole
difficulty of debugging. Checking at the boundary also means exactly one function has to reason
about hostile input; every function past it gets to assert rather than validate, which is what
makes the density target in ZS-ASSERT-11 affordable. This is the shape already shown in
ZS-ASSERT-02: `if` + error at the door, `assert` immediately after.

**Check:** a `_max` constant that appears only at the point of use and never in the function that
first reads the socket, opens the file, or parses `argv`; and, in that boundary function, an
`assert` where an `if (…) return error.…;` belongs.

### ZS-ASSERT-29 [S] Bounded containers assert on overflow; only caller-supplied sizes return errors

A fixed-capacity `push` asserts `!full()` rather than returning `error.Overflow`. Return an error
only from operations whose length comes from *outside* — `fromSlice`, `resize`, a decoder.

**Why:** if the container's capacity is a comptime constant chosen to be big enough, then pushing
past it is a design error in your code, not a runtime condition (ZS-ASSERT-02), and returning an
error forces every call site to handle a case that cannot happen — the "dimensionality" tax that
propagates up the call chain. Note `std.BoundedArray` has not existed since 0.16; the replacement is
a fixed backing array plus `initBuffer` and the `AssumeCapacity` methods, which never allocate and
cannot fail.

**Check:** a method on a fixed-capacity container returning `error.Overflow` or
`error.OutOfMemory` when that capacity is a comptime constant; and the converse — a `fromSlice`,
`resize`, or decoder that asserts on a length supplied by its caller instead of returning an error.

```zig
// verified — GOOD
const std = @import("std");
const assert = std.debug.assert;
const blocks_per_batch_max: u32 = 8;

fn bounded() u32 {
    var backing: [blocks_per_batch_max]u32 = undefined;
    var batch: std.ArrayList(u32) = .initBuffer(&backing);
    assert(batch.capacity == blocks_per_batch_max);

    for (0..4) |i| {
        assert(batch.items.len < batch.capacity);
        batch.appendAssumeCapacity(@intCast(i));
    }
    assert(batch.items.len == 4);
    return batch.items[3];
}
```

### ZS-ASSERT-30 [M!] Do not recurse on unbounded data; bound the depth and assert it

`[M!]` applies to embedded and kernel code with no growable stack, parsers and decoders on
untrusted input, allocators, crypto, and consensus — anywhere a crash or silent stack corruption
is unacceptable. There, use iteration with an explicit worklist. *Relaxed form:* recursion is
permitted only where the maximum depth is a named constant or a `comptime` parameter, and that
bound is asserted at entry.

**Why:** without recursion the call graph is acyclic and an upper bound on stack usage can be
derived statically; with it, stack exhaustion is the one failure mode Zig's safety checks do not
catch, and it manifests as a `SIGSEGV` with a truncated, useless stack trace. TigerBeetle's I/O
layer pushes completions onto a queue specifically to avoid "recursion through
`flush_submissions()`", "unbounded stack usage", and "confusing stack traces".

**Check:** a function whose body names itself, or a mutually recursive pair, with no `depth`
parameter compared against a `_max` constant and no `comptime` depth. Any tree, JSON, expression,
or directory walk written without an explicit worklist is the shape to look for.

```zig
// fragment — GOOD
fn walk(root: *Node, stack: *std.ArrayList(*Node), gpa: std.mem.Allocator) !void {
    try stack.append(gpa, root);
    while (stack.pop()) |node| {
        assert(stack.items.len <= tree_depth_max * children_max);
        for (node.children) |child| try stack.append(gpa, child);
    }
}
```

---

## Part 5 — Assertions, tests, and fuzzing

### ZS-ASSERT-31 [M] Inside `test` blocks use `std.testing.expect*`, not `assert` (see ZS-TEST-08)

Owned by `references/testing.md` ZS-TEST-08, which also lists the matchers and their
signatures. Assertions belong in the code *under* test; the test body checks with the narrowest
`std.testing.expect*` matcher — `std/debug.zig`'s own doc comment says `assert` "may not detect a
test failure in fast and small mode" (ZS-ASSERT-03).

### ZS-ASSERT-32 [M] A fuzzer finds only what an assertion can catch — write the assertion first

Before adding a fuzz target, ask what failure it could possibly report. A fuzzer detects a crash;
if no assertion turns "wrong answer" into a crash, the fuzzer will run for a week and report
success. Every fuzz target is paired with the assertions or the model oracle that give it teeth.

**Why:** this is the mechanism behind TigerStyle's "assertions are a force multiplier for
discovering bugs by fuzzing". Coverage-guided input generation explores paths; assertions are what
convert an explored path into a signal. A fuzz target over a parser with no postconditions tests
only that the parser does not segfault. Since 0.16 the fuzz input is `*std.testing.Smith`, not the
old `[]const u8`: `pub inline fn fuzz(context: anytype, comptime testOne: fn (context:
@TypeOf(context), smith: *Smith) anyerror!void, options: FuzzInputOptions) anyerror!void`.

**Check:** a `std.testing.fuzz` call whose target function — and the code it reaches — contains
no `assert`, no `expect*`, and no comparison against a model. That target can report only a
segfault.

```zig
// fragment — GOOD
test "fuzz the parser against its own assertions" {
    try std.testing.fuzz({}, fuzzOne, .{});
}

fn fuzzOne(context: void, smith: *std.testing.Smith) !void {
    _ = context;
    var buffer: [64]u8 = undefined;
    while (!smith.eos()) {
        const len = smith.valueRangeAtMost(u32, 0, buffer.len);
        smith.bytes(buffer[0..len]);
        _ = messageParse(buffer[0..len]) catch continue;
    }
}
```

The signal here comes entirely from `headerValidate` inside `readBlock` (ZS-ASSERT-18) — remove
those assertions and this target proves nothing. Note also that fuzz builds must have assertions
enabled: run them in `debug` or `safe`, and make `verify` true (ZS-ASSERT-20).

### ZS-ASSERT-33 [S] Write the assertions before the implementation (see ZS-ASSERT-32)

Owned by ZS-ASSERT-32: a fuzz target with no oracle proves nothing, so the assertions come first.
TigerStyle's prescribed order — mental model, then assertions, then code, then the fuzzer — is the
process form of that same claim, and it is advice rather than a rule: no diff can violate it. The
one mechanical consequence worth keeping is that assertions written *after* the code tend to restate
what the code does rather than what it must do, which is a tautology that catches nothing.
