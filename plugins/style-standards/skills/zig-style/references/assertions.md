# Assertions, invariants, and putting a limit on everything

Scope: what to assert, where to put the assertion, what `std.debug.assert` compiles to in each
optimize mode, how to keep assertions alive in a release build, and the discipline of bounding every
loop, buffer, queue and retry count with a named comptime constant. Error-union design, `errdefer`
and the operating-error side of the split are the errors chapter's; allocator lifetime and
`undefined` poisoning the memory chapter's; test structure the testing chapter's, and the
`build.zig` wiring of fuzz steps the build chapter's. A limit's name (`connection_count_max`, not
`max_connections`) is ZS-NAME-06's, applied here.

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
assertion turns into a crash, so assertion density is the ceiling on what any amount of fuzzing will
ever find.

## Contents

- **Part 1 — What an assertion is, and what it compiles to**
  - ZS-ASSERT-01 [M] Alias `assert` at the top of the file, never call it qualified
  - ZS-ASSERT-02 [M] Never put a side effect in an `assert`, and never claim it is compiled out
  - ZS-ASSERT-03 [M] Never make an assertion the last line of defense for memory or security safety
  - ZS-ASSERT-04 [M!] Ship `safe` builds, or define a project-local always-on assert
  - ZS-ASSERT-05 [S] Confine `@setRuntimeSafety(false)` to the narrowest block, and prove it
  - ZS-ASSERT-06 [M] In doc comments, "assert" means safety-checked and "assume" means unchecked
- **Part 2 — Where the assertions go**
  - ZS-ASSERT-07 [M!] Assert arguments at entry and results before return
  - ZS-ASSERT-08 [M!] Average at least two assertions per function
  - ZS-ASSERT-09 [M] Split compound assertions
  - ZS-ASSERT-10 [M] Write an implication as a single-line `if (a) assert(b);`
  - ZS-ASSERT-11 [M] Assert the negative space, and mark deliberate non-invariants with `maybe`
  - ZS-ASSERT-12 [M] State a biconditional as one `==` between two booleans
  - ZS-ASSERT-13 [M] Re-assert the narrowed state after every early-return guard
  - ZS-ASSERT-14 [S] Give each stateful type one `assertInvariants`, and bracket mutators with it
  - ZS-ASSERT-15 [M] Check every persisted or transmitted structure on its write path and its read path
  - ZS-ASSERT-16 [M] Assert unconditionally when O(1), and gate an O(N) check of O(1) work behind `verify`
- **Part 3 — Compile-time contracts**
  - ZS-ASSERT-17 [M] Assert the relationships between compile-time constants in a `comptime` block
  - ZS-ASSERT-18 [M] Give every wire, disk, C-ABI, and comptime-built type a layout `comptime` block
- **Part 4 — Put a limit on everything**
  - ZS-ASSERT-19 [M] Put a limit on everything, and give the limit a name ending in `_max`
  - ZS-ASSERT-20 [M] Keep all limits in one `constants.zig`: why, value, comptime relationships
  - ZS-ASSERT-21 [M] Derive dependent limits; never hand-copy a number
  - ZS-ASSERT-22 [M] Give every loop a provable bound; an unbounded loop must say so and assert it
  - ZS-ASSERT-23 [M] Fail fast: check the bound at the boundary where untrusted input enters
  - ZS-ASSERT-24 [S] Bounded containers assert on overflow; only caller-supplied sizes return errors
- **Part 5 — Assertions, tests, and fuzzing**
  - ZS-ASSERT-25 [M] A fuzzer finds only what an assertion can catch — write the assertion first

---

## Part 1 — What an assertion is, and what it compiles to

### ZS-ASSERT-01 [M] Alias `assert` at the top of the file, never call it qualified

Write `const assert = std.debug.assert;` in the import block and call `assert(...)` bare.

**Why:** assertions must be visually cheap, so that adding the fourth one costs nothing; the
`std.debug.` prefix is ten characters of noise on every line and pushes conditions past 100 columns.
TigerBeetle's linter (`src/tidy.zig`) bans the literal `"debug.assert("` for this reason.

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

### ZS-ASSERT-02 [M] Never put a side effect in an `assert`, and never claim it is compiled out

`std.debug.assert` is an *ordinary function* —
`pub fn assert(ok: bool) void { if (!ok) unreachable; }` (`std/debug.zig`). Two separate
consequences follow, and conflating them is the usual mistake:

1. **The check is deleted in `fast` and `small`, and is replaced by an assumption.** `unreachable`
   is a panic in `debug` and `safe`, and an *optimizer assumption* in `fast` and `small`.
2. **The condition is still evaluated in all four modes.** `ok` is a function argument, so it is
   computed at the call site in every mode; `fast` discards the result, it does not skip the work.
   The assert is **not** compiled away — only the check is. On 0.17.0, a global counter incremented
   inside an assert condition reaches the same value under `-O debug`, `-O safe`, `-O fast` and
   `-O small`. So `assert(list.pop() != null)` still pops in release, it just stops verifying the
   result.

| Mode | Optimization | Safety checks | Condition evaluated | A false `assert(cond)` |
|---|---|---|---|---|
| `.debug` | none | on: overflow, bounds, `unreachable`, alignment, bad casts | yes | panic: `reached unreachable code` |
| `.safe` | full | on | yes | panic: `reached unreachable code` |
| `.fast` | full | off: each is illegal behavior | **yes** | illegal behavior; the optimizer treats `cond` as proven |
| `.small` | for size | off | **yes** | illegal behavior; the optimizer treats `cond` as proven |

TigerStyle's claim that assertions downgrade correctness bugs into liveness bugs therefore holds
only in `debug` and `safe`; in `fast` a violated assertion *upgrades* a correctness bug into
arbitrary miscompilation. Called with `sink == 0`, the first example's `classify` panics under
`-O safe` with `reached unreachable code` in `std.debug.assert`, exit 134, the stack trace pointing
at the violated assertion; under `-O fast` it gives no diagnostic of any kind and dies on a trap
instruction, SIGTRAP, exit 133 — the branch that would have returned `"zero"` is gone.

So keep the condition pure and cheap: hoist a side effect into a statement of its own, and gate an
expensive condition behind `verify` (ZS-ASSERT-16). The optimizer is entitled to treat the result as
`true` — the std doc comment says it "is able to use the assertion in its heuristics" — so after
inlining, a side-effecting call whose result is asserted can be specialized on that assumption.

**Why:** in the bottom two rows an assertion actively *removes* protection: LLVM propagates the
assumed fact and deletes code that contradicts it. And because the condition still runs, any side
effect in it still happens and its full cost is paid in release, for nothing.

**Check:** an `assert(` whose condition contains `pop(`, `next(`, `orderedRemove(`, `fetch`, `++`,
an assignment, or a call whose name starts with a mutating verb; one containing a scan (`find`,
`indexOf`, `contains`, a loop) that is not wrapped in `if (verify)`; and any comment or design
document claiming the assert "is compiled out" or "costs nothing in release".

```zig
// verified
const std = @import("std");
const assert = std.debug.assert;
var sink: u32 = 0;

noinline fn classify(x: u32) []const u8 {
    assert(x != 0); // In `fast` this is not a check, it is a promise.
    if (x == 0) return "zero"; // ... so the optimizer deletes this branch.
    return "nonzero";
}
```

```zig
// fragment — BAD
assert(queue.pop() != null); // The pop happens in release too, unchecked.
assert(std.mem.findScalar(u32, list.items, item) != null); // O(N), paid in `fast` for nothing.
```

```zig
// fragment — GOOD
const popped = queue.pop();
assert(popped != null);

if (verify) assert(std.mem.findScalar(u32, list.items, item) != null); // Whole statement gated.
```

### ZS-ASSERT-03 [M] Never make an assertion the last line of defense for memory or security safety

An `assert` before an unchecked index, an `@intCast`, a `@ptrCast`, a length arithmetic, or a
crypto-boundary check is documentation, not enforcement. If the invariant must hold in the shipped
binary, enforce it with a construct that survives: an `if` + error, `assertAlways` (ZS-ASSERT-04),
`std.math.cast`, or a checked slice operation.

**Why:** by ZS-ASSERT-02 the check is erased in `fast` *and* replaced by an assumption, so an
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

### ZS-ASSERT-04 [M!] Ship `safe` builds, or define a project-local always-on assert

Ship `-Doptimize=safe`, and decide the shipping mode before you adopt assertion density:
TigerStyle's density assumes a `safe` deployment, which idiomatic std never does. A release artifact
built `fast` or `small` records at its `-Doptimize=` site the benchmark number or the constraint
that chose it — `safe` costs real throughput on bounds-heavy inner loops — and routes every
invariant that must halt the process through a project-local assertion that survives `fast`:
`assertAlways`, below, which under `-O fast` panics with its message where the equivalent `assert`
dies on a bare trap. A library does not choose its consumer's mode: it is correct in all four, and
documents which invariants it asserts and what running it in a `safe` build costs. What each mode
does with an assertion is ZS-ASSERT-02's table; how a build script selects the mode is ZS-BUILD-23.

*Relaxed form:* `fast` or `small` with `std.debug.assert` alone, provided the tests and a staging
build run in `safe` and the README names the shipping optimize mode.

**Why:** a `fast` build turns each assertion into a licence for the optimizer to assume its
condition, so an assertion that would have caught corruption becomes how corrupt state is optimized
into arbitrary behavior; and std ships no assertion that survives `fast`.

**Check:** the release command in CI or the release script names an explicit `-Doptimize=`. If it
names `fast` or `small`, the same commit carries a benchmark number or a one-line comment naming the
constraint, and an invariant that must halt is checked by `assertAlways`, not `assert`. A README or
release script that names no shipping mode, in a repository whose source averages more than one
`assert` per function, is a finding too.
`rg -n 'ReleaseFast|ReleaseSmall' .github/ build.zig scripts/` finds the TitleCase spellings, which
0.17 still parses.

```zig
// verified — GOOD
/// Assertion that is present in every optimize mode, including `fast` and
/// `small`. Use where a violated invariant must halt the process rather
/// than become an optimizer assumption.
pub fn assertAlways(ok: bool, comptime message: []const u8) void {
    if (!ok) @panic(message);
}
```

### ZS-ASSERT-05 [S] Confine `@setRuntimeSafety(false)` to the narrowest block, and prove it

Never reach for `fast` whole-binary to speed up one loop. Keep the build `safe` and disable safety
in the smallest scope that contains the hot arithmetic, with a comment proving the check is
redundant. `@optimizeFor`, which the langref names as `@setRuntimeSafety`'s planned replacement, is
no 0.17 builtin: it is `error: invalid builtin function: '@optimizeFor'`.

**Why:** `@setRuntimeSafety` sets safety for the scope containing the call and is overridable at any
nested scope, so the blast radius is exactly what you write — whereas `fast`'s blast radius is every
assertion in the program (ZS-ASSERT-02).

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

### ZS-ASSERT-06 [M] In doc comments, "assert" means safety-checked and "assume" means unchecked

The langref style guide makes this a lexical rule: use the word **assert** to describe an invariant
whose violation is safety-checked illegal behavior, and **assume** for one whose violation is
unchecked illegal behavior. Never swap them.

**Why:** a reader who sees "asserts" will test the failure path and expect a panic; one who sees
"assumes" knows there is nothing to test and that they own the proof. Swapping the words hides which
side of the memory-safety line a function sits on.

**Check:** read each doc comment that says "asserts" or "assumes" against the body below it.
"Asserts" with no `assert(`, no safety-checked index, and no checked cast in the body is a lie;
"assumes" above a body that does check is merely stale, and both mislead in the same direction.

```zig
// fragment — GOOD
/// Asserts that `index < count`.
pub fn get(ring: *const Ring, index: u32) u8 { ... }

/// Assumes `bytes` is aligned to `@alignOf(Header)`; misalignment is unchecked.
pub fn headerCast(bytes: []align(@alignOf(Header)) const u8) *const Header { ... }
```

## Part 2 — Where the assertions go

### ZS-ASSERT-07 [M!] Assert arguments at entry and results before return

Preconditions first, before any early return. Postconditions on the computed value, immediately
before returning it. A function must not operate blindly on data it has not checked.

*Relaxed form:* stated once, by ZS-ASSERT-08 — assert the contract of every function whose parameter
types do not already enforce it. A boundary taking untrusted input gets `if` + error, never an
assert (ZS-ERR-01, ZS-ASSERT-23).

**Why:** a precondition at the top of the callee fires at the first wrong caller, with that caller
on the stack, not three frames deeper in code that is behaving correctly. A postcondition catches
fine arguments and a wrong body, which no caller-side check can find.

**Check:** placement, not count — which assertions a function needs is ZS-ASSERT-08's Check. A
precondition `assert` below the function's first early return or first use of the parameter it
checks, and a postcondition separated from the `return` of the value it checks.

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

### ZS-ASSERT-08 [M!] Average at least two assertions per function

The assertion density of the codebase averages at least two assertions per function. TigerBeetle's
control plane runs well above that floor: at its commit 97c7a8e, `rg -c 'assert\('` over
`rg -c '^[ \t]*(pub )?fn '` gives `src/vsr/replica.zig` 5.90 per function (1582/268, one per 7.8
lines), `src/vsr/journal.zig` 4.15 and `src/state_machine.zig` 3.87.

std is far sparser than two per function, and deliberately so — it prefers error unions and
documented illegal behavior at public boundaries. Do not "fix" std-style code by sprinkling asserts
into public API entry points where the input is untrusted (ZS-ERR-01); add them to the internal
helpers where the input is your own.

*Relaxed form:* in ordinary application code the honest rule is: **every function whose contract is
not already enforced by its parameter types asserts that contract, and every function that computes
a value with a checkable property asserts it.** A pure function from `Color` to `[]const u8` needs
none. A function taking `(offset: usize, len: usize)` into a buffer needs two.

**Why:** the count is a proxy, not the goal — the goal is that every unencoded assumption is written
down. But the count is the only proxy that survives code review, and it forces the question "what do
I actually know here?" on every function rather than only the scary ones.

**Check:** ratio of `rg -c '\bassert\('` to `rg -c '^[ \t]*(pub )?fn '` over the module. Per diff,
the finding is any added function that takes a relationship between two parameters — an `offset` and
a `len`, an index and a count, two slices that must be the same length — and asserts none of it.

### ZS-ASSERT-09 [M] Split compound assertions

Prefer `assert(a); assert(b);` over `assert(a and b);`.

**Why:** the panic reports a line and a column. With `assert(a and b)` you learn that one of two
things failed and must re-run to find out which; with two statements the stack trace names the exact
predicate. The cost is zero — the generated code is identical.

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

### ZS-ASSERT-10 [M] Write an implication as a single-line `if (a) assert(b);`

Keep it on one line, so it is visually an assertion, not control flow.

**Why:** `assert(!a or b)` is the same predicate written as a negation, and negations are exactly
where reviewers stop being able to check logic by inspection. The `if` form reads the way the domain
does ("if the transfer is pending, it has a timeout") and greps cleanly.

**Check:** an `assert(!` whose condition also contains ` or ` — that is an implication written as a
negated disjunction. Also an `if (…) {` block whose entire body is one `assert(…);`, which should
have been the one-line form.

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

### ZS-ASSERT-11 [M] Assert the negative space, and mark deliberate non-invariants with `maybe`

The golden rule: assert the positive space you *do* expect **and** the negative space you do *not*.
Then, for every state variable a reader might reasonably assume is pinned at this program point but
is not, write `maybe(...)`.

**Why:** bugs cluster where data crosses the valid/invalid boundary, and only a negative-space
assertion sits on it. Silence is ambiguous — did you know `status` could be `.recovering_head` here,
or never think of it? `maybe` compiles to nothing and turns that silence into a claim.

**Check:** a range asserted on one side only — an `assert(index < count)` with no companion bound
below, an `assert(x != null)` with no arm for the null case — and any enum-valued or optional field
the function reads without either asserting or `maybe`-ing it. A module whose diff adds `assert` and
never `maybe` is the aggregate smell.

```zig
// verified
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

### ZS-ASSERT-12 [M] State a biconditional as one `==` between two booleans

When two representations must agree, assert the equality of the two predicates rather than writing
two one-directional assertions or, worse, one.

**Why:** `assert((count == 0) == (head == null))` catches both a non-empty count with a null head
*and* a zero count with a live head, in one line. Two separate implication assertions catch the same
thing at twice the length; a single implication catches half the bugs.

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

### ZS-ASSERT-13 [M] Re-assert the narrowed state after every early-return guard

Each guard clause buys you a stronger fact about the rest of the function. Write it down.

**Why:** after `if (status != .normal) return;` the rest of the function relies on
`status == .normal` without saying so, and a refactor that moves the guard silently invalidates that
reasoning. The re-assertion makes the refactor fail loudly where the assumption is used.

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

### ZS-ASSERT-14 [S] Give each stateful type one `assertInvariants`, and bracket mutators with it

Collect the type's whole-object invariants in one private function taking `*const T`. Every public
mutator opens with `x.assertInvariants(); defer x.assertInvariants();`. TigerBeetle's
`src/vsr/repair_budget.zig` uses this shape 19 times in 464 lines (tigerbeetle 97c7a8e — spelled
`assert_invariants` there, TigerBeetle's snake_case function convention; this standard follows std's
`camelCase` for callables, ZS-NAME-01). State the same invariants in prose in the type's doc comment
as well, as the second example does — prose alone rots, code alone is unreadable.

**Why:** `defer` runs on *every* exit path, including early returns and error returns, so one line
covers exits you have not written yet. The invariant also gets a single home: adding a field means
editing one function rather than auditing every method.

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

```zig
// fragment
/// Invariant: suspend_size <= process_size <= advance_size <= receive_size.
pub const MessageBuffer = struct { ... };
```

### ZS-ASSERT-15 [M] Check every persisted or transmitted structure on its write path and its read path

Every structure written to disk or sent over a wire is checked by an assertion right before it is
written and again right after it is read back: two *different* code paths for one property, since
its stored bytes outlive the process and a silent encoding bug becomes permanent corruption.

Note that pairing a property does **not** mean pairing the *mechanism*. The write path owns bytes
this process just built, so it asserts; the read path owns bytes a peer chose, so it validates and
returns an error (ZS-ERR-01). Asserting on the read path would turn every corrupt or hostile frame
into a remote panic — and in `fast` into an optimizer assumption that deletes the very bounds check
a later `connections[header.replica_index]` depends on. Same predicates, two mechanisms, chosen by
who controls the bytes.

**Why:** a write-path assertion proves only that the *in-memory* value was sane, not the encoder,
the padding, the storage layer or bit rot. The read side checks a different byte sequence, so it
catches every bug between the two, and when only one of the pair fires, the failure is localized.

**Check:** a `*Validate` or `*Verify` helper called from exactly one of an encode/decode,
serialize/deserialize, or write/read pair: a validator with one caller leaves half the property
unchecked.

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
/// rejected, never asserted (ZS-ERR-01) — an assert here is a remote DoS.
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

    const header = std.mem.bytesToValue(Header, source[0..@sizeOf(Header)]);
    try headerCheck(&header); // <- path 2: validate, never assert, on peer bytes.

    if (source.len != @sizeOf(Header) + header.size_bytes) return error.HeaderInvalid;
    return header;
}
```

### ZS-ASSERT-16 [M] Assert unconditionally when O(1), and gate an O(N) check of O(1) work behind `verify`

Two tiers. In the control plane — anything batched, where per-operation overhead is amortized —
assert unconditionally; it is acceptable to spend O(N) verifying an O(1) computation there. In the
data plane, do an unconditional O(1) check before an O(N) loop, and gate any O(N) whole-structure
verification behind a `verify` constant.

The gate must be `if (verify)` around the *whole statement*, not the assert alone: by ZS-ASSERT-02
the condition inside an `assert` still runs in `fast`, so `assert(queue.contains(link))` pays the
O(N) scan in release and gets nothing for it. Define `verify` from your own module's
`@import("builtin").optimize.runtimeSafety()` — `std.debug.runtime_safety` is deprecated in its
favour because it reports the *standard library's* optimize mode, not your module's.

**Why:** slow assertions reduce total coverage. Randomized testing finds bugs in proportion to the
iterations it can run, so an O(N) check on an O(1) hot-path mutation makes the fuzzer quadratically
weaker at finding the very bug the check was written for.

**Check:** an `assert(` containing a loop, a `contains`, or a whole-structure walk that is not
preceded by `if (verify)` on the same line.

```zig
// verified
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

## Part 3 — Compile-time contracts

### ZS-ASSERT-17 [M] Assert the relationships between compile-time constants in a `comptime` block

Every derived or co-dependent constant gets a `comptime {}` block stating the relationship that must
hold.

You **may** also assert a fact that is blatantly true today, where a comment would be weaker:
`assert(KiB == 1024)` cannot drift the way `// KiB is 1024` can, and it is free. The permission is
not limited to constants: any load-bearing fact that is obvious *today* is better asserted than
commented, at runtime too, because the assertion cannot go out of date. It is a permission, not an
obligation. This deliberately contradicts NASA's Power of Ten rule 5, which forbids assertions a
static checker can prove always hold; TigerStyle overrides that because the value here is
communicative and drift-proofing, not detection. Reserve it for load-bearing facts — an
`assert(true)` next to trivia is noise.

Be aware of the diagnostic quality: a failing `comptime assert` reports
`error: reached unreachable code` inside `std.debug.assert` with a `note: called at comptime here`
pointing at your line. You get the location but not the reason — which is why caller-facing
contracts use `@compileError` instead (ZS-COMPTIME-07).

**Why:** a comptime assertion is free, and it is the one kind that is **always on in every optimize
mode**, because it never reaches codegen. It also fails the build on the edit that breaks the
relationship, not on the machine where the ratio finally mattered.

**Check:** a file declaring two or more `pub const` numbers where one's correctness depends on the
other — a `%`, an `@divExact`, a power-of-two assumption, or a ceiling relied on at some call site —
with no `comptime {}` block anywhere in the file asserting that relation.

```zig
// fragment — GOOD
comptime {
    assert(std.math.isPowerOfTwo(sector_size_bytes));
    assert(block_size_bytes % sector_size_bytes == 0);
    assert(message_size_bytes_max % sector_size_bytes == 0);
    assert(connection_count_max > 0);
}
```

### ZS-ASSERT-18 [M] Give every wire, disk, C-ABI, and comptime-built type a layout `comptime` block

Any `extern struct` or `packed struct` that is serialized, persisted, hashed, or passed across a C
boundary carries a `comptime {}` asserting `@sizeOf`, `@alignOf`, the `@offsetOf` of each field a
foreign reader locates by offset, and the absence of padding. That covers every type built under
ZS-DATA-19 and ZS-DATA-20.

Everything comptime generates gets the same block: a comptime-built table, or a type whose layout
comptime derives, asserts its size. A table sized from a `comptime_int` grows from 1 KiB to 16 MiB
of `.rodata` when someone bumps that constant, and nothing in the build output says so; bounding the
generation itself is ZS-COMPTIME-05.

For the padding check on an `extern struct` use `std.meta.hasUniqueRepresentation(T)`, which
compares `@sizeOf(T)` against the sum of the field sizes, and which also decides whether hashing or
comparing the struct's raw bytes is sound. It is false for any `bool`, float or slice field too,
padding or not, so a struct holding one asserts the size sum by hand. Do **not** reach for
`@bitSizeOf(T) == @sizeOf(T) * 8` there: `@bitSizeOf` of a struct that is not packed is a compile
error (`no bit size available for type …`). That identity is meaningful only on a
`packed struct(uN)`, where it checks that the backing integer fills its bytes.

**Why:** the compiler decides field layout from the field list, so one added `u16` silently changes
`@sizeOf` and the on-disk format, corrupting every existing file with no compile error; the comptime
block fails the commit that does it. Padding bytes are also a buffer-bleed vector.

**Check:** an `extern struct` or `packed struct` that appears in a `@memcpy`, `std.mem.asBytes`,
`bytesAsValue`, a `read`/`write` call, or an `extern fn` signature, with no `comptime {}` block
asserting `@sizeOf`; and a comptime-built table or comptime-derived type with no size assertion
beside it.

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
        assert(@offsetOf(Header, "size_bytes") == 48);
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

/// One entry per byte value, built at compile time.
const square_table: [256]u16 = blk: {
    var table: [256]u16 = undefined;
    for (&table, 0..) |*entry, index| entry.* = @intCast(index * index); // 255² < 2¹⁶
    break :blk table;
};

comptime {
    // 512 bytes of `.rodata`: a longer table fails here, not in a binary-size report.
    assert(@sizeOf(@TypeOf(square_table)) == 512);
}
```

## Part 4 — Put a limit on everything

### ZS-ASSERT-19 [M] Put a limit on everything, and give the limit a name ending in `_max`

Every buffer, queue, batch, connection table, retry count, timeout, recursion depth, and message
size has a fixed upper bound expressed as a named comptime constant. No bare literals at the use
site; no "it grows as needed" without a stated ceiling. The name follows ZS-NAME-06:
`latency_ms_max`, not `max_latency_ms`.

**Why:** everything has a limit; the only question is whether you chose it or production discovers
it as an OOM, an unbounded queue, or a tail-latency spike. A named constant is assertable
(ZS-ASSERT-23) and reviewable: `connection_count_max = 64` invites "is 64 right?"

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

### ZS-ASSERT-20 [M] Keep all limits in one `constants.zig`: why, value, comptime relationships

One file holds every configured and derived limit. Each constant carries a `///` comment saying *why
that number*, and each group of related limits ends with the `comptime {}` block ZS-ASSERT-17 asks
for.

**Why:** limits are not independent: the ceiling that matters, such as fitting the cgroup, is a
property of a combination like `request_memory_bytes`, and scattered numbers mean nobody can check
it. One file also answers "what does this process cost at maximum load?"

**Check:** `rg -n 'pub const \w+_(max|min)\b' src/ -g '*.zig'` returns hits only from
`constants.zig`; each there has a `///` comment giving the reason for that number, and a group of
related limits has a trailing `comptime {}` block asserting the relationships between them.

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

### ZS-ASSERT-21 [M] Derive dependent limits; never hand-copy a number

If limit B is a function of limit A, compute B from A. A literal that *happens* to equal the
quotient today is a latent bug waiting for someone to change the divisor. Use a labelled block when
the derivation needs locals, and keep the derived constant next to its inputs in `constants.zig`
(ZS-ASSERT-20).

The *rounding* half — `@divExact` / `@divFloor` / `@divTrunc` / `@divCeil` (new in 0.17), never a
bare `/` — is owned by ZS-DATA-06. `@divExact` is the strongest of the four because it asserts the
remainder is zero, which is usually the claim a derived limit means to make.

**Why:** a hand-copied `16` beside a computed `message_size_bytes_max / block_size_bytes` is
invisible in review, because both are right on the day they are written. Deriving it makes a
forgotten update impossible and makes the *relationship* the reviewable artifact.

**Check:** two `pub const … _max` declarations in `constants.zig` where one is an integer literal
that equals an arithmetic combination of the others.

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

### ZS-ASSERT-22 [M] Give every loop a provable bound; an unbounded loop must say so and assert it

This rule owns loop bounds for the whole standard. It is NASA's Power of Ten rule 2, adopted
verbatim by TigerStyle: it must be trivially provable that a preset upper bound on iterations cannot
be exceeded.

**Reach for `for` first.** `for (slice)` and `for (0..limit)` carry their bound in the syntax, so
there is nothing left to prove. A `while` is a claim that the termination argument does not fit in a
range, and that claim has to be paid for. Four shapes, all legitimate:

- (a) iterate a counted range and close with `else unreachable` when the loop must exit early;
- (b) iterate a counted range and close with `else` + a panic naming the exceeded limit;
- (c) keep a `while` and a witness counter, and assert the counter against a named `_max` constant
  *inside* the loop, so it fires on the offending iteration rather than after the hang;
- (d) a loop that genuinely cannot terminate — an event loop — is commented as intentional, and the
  reverse property (that it does not exit early, or that shutdown was observed) is asserted.

The `else` clause on a Zig `for` runs only when the loop was *not* broken out of, which is precisely
the "bound exceeded" condition. The same discipline applies to anything that grows per iteration —
queues, buffers, retry counts, backlogs. Everything has a limit; name it (ZS-ASSERT-19).

**Why:** an unbounded loop over a data structure turns a corrupt pointer — a cycle, a stale index —
from a crash into a hang or a tail-latency spike, harder to diagnose and, in a replicated system,
worse than crashing. A bound converts both into a crash with a stack trace.

**Check:** a `while` whose condition is not `it.next()`, `stack.pop()`, or a counter comparison,
with no `_max` constant asserted in its body; and any `while (true)` with no comment saying it is
intended.

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
        _, rest = std.mem.cut(u8, rest, "@import(") orelse break;
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

### ZS-ASSERT-23 [M] Fail fast: check the bound at the boundary where untrusted input enters

Reject an over-limit value at the point of entry — the socket read, the CLI parse, the file header —
not at the point of use. After the boundary check, the bound becomes an asserted invariant
everywhere downstream. This is the shape ZS-ERR-01's `messageParse` shows: `if` + error at the door,
`assert` immediately after.

**Why:** the distance between where a bad value is admitted and where it does damage is the whole
difficulty of debugging. A boundary check leaves one function reasoning about hostile input; every
function past it asserts, which makes ZS-ASSERT-08's density affordable.

**Check:** a `_max` constant that appears only at the point of use and never in the function that
first reads the socket, opens the file, or parses `argv`.

### ZS-ASSERT-24 [S] Bounded containers assert on overflow; only caller-supplied sizes return errors

A fixed-capacity `push` asserts `!full()` rather than returning `error.Overflow`. Return an error
only from operations whose length comes from *outside* — `fromSlice`, `resize`, a decoder. On a
fixed backing array (ZS-DATA-23) the two are `ArrayList`'s two method families, neither of which
allocates: `appendAssumeCapacity` and its siblings where your design guarantees the room, and
`appendBounded`, `appendSliceBounded`, `addOneBounded` and `insertBounded`, which return
`error.OutOfMemory`, where the caller chose the length.

**Why:** when the capacity is a comptime constant chosen to be big enough, pushing past it is a
design error in your code (ZS-ERR-01), and an error return makes every call site handle a case that
cannot happen — the "dimensionality" tax that propagates up the call chain.

**Check:** a method on a fixed-capacity container returning `error.Overflow` or `error.OutOfMemory`
when that capacity is a comptime constant; and the converse — a `fromSlice`, `resize`, or decoder
that asserts on a length supplied by its caller instead of returning an error, such as an
`*AssumeCapacity` call where the `*Bounded` form belongs.

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

/// The caller chose `blocks.len`, so overflowing the batch is an error to return.
fn batchFrom(backing: *[blocks_per_batch_max]u32, blocks: []const u32) error{OutOfMemory}!u32 {
    var batch: std.ArrayList(u32) = .initBuffer(backing);
    try batch.appendSliceBounded(blocks);
    return @intCast(batch.items.len);
}
```

## Part 5 — Assertions, tests, and fuzzing

### ZS-ASSERT-25 [M] A fuzzer finds only what an assertion can catch — write the assertion first

Before adding a fuzz target, ask what failure it could possibly report. A fuzzer detects a crash; if
no assertion turns "wrong answer" into a crash, the fuzzer will run for a week and report success.
Every fuzz target is paired with the assertions or the model oracle that give it teeth, and those
come first: assertions written *after* the code tend to restate what it does rather than what it
must do, a tautology that catches nothing. TigerStyle's order — mental model, then assertions, then
code, then the fuzzer — is the process form of the same claim, offered as advice. Writing the target
itself, `std.testing.fuzz` over a `*std.testing.Smith`, is ZS-TEST-23.

In the example, the signal comes entirely from the assertions `messageParse` (ZS-ERR-01) and
`readBlock` (ZS-ASSERT-15) make once their guards have passed — remove them and this target proves
nothing. Note also that fuzz builds must have assertions enabled: run them in `debug` or `safe`, and
make `verify` true (ZS-ASSERT-16).

**Why:** coverage-guided input generation explores paths; assertions are what convert an explored
path into a signal. A fuzz target over a parser with no postconditions tests only that the parser
does not segfault.

**Check:** a `std.testing.fuzz` call whose target function — and the code it reaches — contains no
`assert`, no `expect*`, and no comparison against a model. That target can report only a segfault.

```zig
// fragment — GOOD
test "fuzz the parser against its own assertions" {
    try std.testing.fuzz({}, fuzzOne, .{});
}

fn fuzzOne(context: void, smith: *std.testing.Smith) !void {
    _ = context;
    var buffer: [64]u8 = undefined;
    while (!smith.eos()) {
        const len = smith.slice(&buffer);
        _ = messageParse(buffer[0..len]) catch continue;
    }
}
```
