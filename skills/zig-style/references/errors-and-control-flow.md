# Errors, control flow, assertions vs errors vs panics

Scope: how a Zig 0.16 function reports failure (error sets, optionals, assertions, panics), how a
caller consumes it (`try`, `catch`, `errdefer`, error return traces, `*Diagnostics` out-parameters),
and the shape of the control flow in between (conditions, loops, `switch`, labeled constructs,
`@branchHint`, and the 70-line function limit).

This chapter does not own assertion *density* or the design of bounded limits — those are
`references/assertions-and-limits.md` ZS-ASRT-11 and ZS-ASRT-27. Allocator ownership and OOM
lifetimes are `references/memory-and-allocators.md`; `std.Io` stream errors and cancellation are
`references/io-and-concurrency.md`; error-name formatting with `{t}` is
`references/formatting-and-output.md` ZS-FMT-05. It cites them.

Blocks that do not declare their own imports assume a file opening with
`const std = @import("std");` and `const assert = std.debug.assert;`.
## Contents

- **1. The decision table: error vs assert vs panic vs unreachable vs optional**
  - ZS-ERR-01 [M] Classify a failure as a programmer error or an operating condition first
  - ZS-ERR-02 [M] Return an optional for absence; reserve the error union for failure
  - ZS-ERR-03 [M] A library never panics, never exits, never prints
- **2. Error sets**
  - ZS-ERR-04 [M] Name the error set of every public function; infer only for private helpers
  - ZS-ERR-05 [S] Compose sets with `||`; name a composed set after the verb it belongs to
  - ZS-ERR-06 [M] Never put `anyerror` in a public signature
  - ZS-ERR-07 [S] Use `error{}!T` to state that a path cannot fail
- **3. `try`, `catch`, and `catch unreachable`**
  - ZS-ERR-08 [M] `try` is the default; every `catch {}` or `catch unreachable` carries a comment
  - ZS-ERR-09 [M] Switch on the captured error, and omit `else` when the set is explicit
  - ZS-ERR-10 [M] `catch unreachable` is a latent bug unless the proof is in a comment next to it
  - ZS-ERR-11 [M] Every error is handled somewhere; `catch {}` needs a justification comment
- **4. `defer` and `errdefer`**
  - ZS-ERR-12 [M] Put the release on the line immediately after the acquisition (see ZS-MEM-11)
  - ZS-ERR-13 [M] Order `defer`/`errdefer` so LIFO teardown cannot outrun what a handler reads
  - ZS-ERR-14 [M] Stop the `errdefer` at the point ownership transfers
  - ZS-ERR-15 [M] A `defer` in a loop body runs each iteration, not at function exit
  - ZS-ERR-16 [S] `errdefer |err|` is for diagnostics, not for control flow
- **5. Error return traces**
  - ZS-ERR-17 [M] Propagate with `try` or `return err`; never launder an error through an optional
- **6. Simple, explicit control flow (TigerStyle)**
  - ZS-ERR-18 [M] Split compound conditions into separate checks
  - ZS-ERR-19 [S] Prefer a `switch` to an `else if` chain; if you flatten chains into trees, say why
  - ZS-ERR-20 [M] State invariants positively when an `if`/`else` splits the input space
  - ZS-ERR-21 [S] An `if` with no `else` over a validated domain carries a comment or an assertion
  - ZS-ERR-22 [M] Braces, unless the whole statement fits on one line
  - ZS-ERR-23 [M!] No recursion; where recursion is allowed, bound the depth explicitly
  - ZS-ERR-24 [M] Every loop has a provable upper bound (see ZS-ASRT-27)
  - ZS-ERR-25 [M!] Push `if`s up and `for`s down
- **7. Modern Zig control flow the standard prefers**
  - ZS-ERR-26 [S] Use labeled `switch` with `continue :label` for state machines and dispatch loops
  - ZS-ERR-27 [S] Use a labeled block to compute a value that needs statements
  - ZS-ERR-28 [M] Switch exhaustively with no `else`; use `_` on non-exhaustive enums
  - ZS-ERR-29 [S] Use `inline for` / `inline else` only on a small comptime-known set
  - ZS-ERR-30 [M] Unwrap optionals with `orelse` or a capture, never with `.?`
  - ZS-ERR-31 [M] Replace `@setCold` with `@branchHint`; placing hints on hot paths is `[S]`
- **8. Logging**
  - ZS-ERR-32 [M] A library logs through a scoped `std.log` namespace
  - ZS-ERR-33 [S] Use std's four log levels, configured from the root file
- **9. Function shape, user-facing diagnostics, and stack traces**
  - ZS-ERR-34 [M!] Hard limit of 70 lines per function; shape it like an inverse hourglass
  - ZS-ERR-35 [S] Report position and context through a `*Diagnostics`, not the error set
  - ZS-ERR-36 [S] Capture a stack trace with `captureCurrentStackTrace` into a caller-owned buffer
- **Uniformity of failure and control flow**
  - ZS-ERR-37 [M] Give the members of one error set a uniform shape
  - ZS-ERR-38 [M] Absorb a special case into the general path, or give it its own type

---

## 1. The decision table: error vs assert vs panic vs unreachable vs optional

### ZS-ERR-01 [M] Classify a failure as a programmer error or an operating condition first

TigerStyle's framing is the whole design: **assertions detect programmer errors, which are
unexpected and whose only correct handling is to crash; errors are operating conditions, which are
expected and must be handled.** Pick the mechanism from the classification, not from convenience.

**Why:** the two categories have opposite correct responses. A violated precondition means the
program's model of itself is already wrong, so continuing corrupts more state — crashing converts a
correctness bug into a liveness bug. A failed `open()` means the *world* did not cooperate; crashing
there converts a recoverable situation into an outage.

**Check:** an `assert` on a value that arrived from `read`, `argv`, an environment variable, or a
`pub` parse entry point — that is an operating condition asserted. And the mirror image: an error
set member named `Invariant*`, `Corrupt*`, `Impossible*`, or `ShouldNotHappen` — a programmer
error returned.

| Situation | Mechanism | Notes |
|---|---|---|
| Caller violated a documented precondition (index out of range, unsorted input to a binary search) | `assert(cond)` | Programmer error. `std.debug.assert` is literally `if (!ok) unreachable;` — same UB rules. |
| A state the program's own invariants make impossible (a tag that cannot occur; a `switch` arm the type system cannot rule out) | `unreachable` | Safety-checked panic in Debug/ReleaseSafe, **illegal behavior** in ReleaseFast/ReleaseSmall. |
| A relationship between compile-time constants or type sizes | `comptime assert(cond)` / `@compileError` | Fails before the program runs. Always cheaper than a runtime check. |
| The environment failed: I/O, OOM, parse failure, network, permission, malformed input from outside | **return an error** | Operating condition. Expected. Must be handled by someone. |
| A value is legitimately absent, and absence is not a failure (cache miss, "no such key") | **return an optional `?T`** | An error union here forces callers to write `catch` for a non-event. |
| A library cannot continue | **return an error** | Never `@panic`, never `std.process.exit`. See ZS-ERR-03. |
| An application's top level cannot continue | `std.process.fatal(fmt, args)` | `= std.log.err(fmt, args); exit(1);` (`process.zig:687`). The right CLI failure primitive. |
| An application aborts with a fixed message | `@panic("literal")` | What std does: 363 `@panic(` sites vs only 16 `std.debug.panic(`. |
| An application aborts and the message needs formatting | `std.debug.panic(fmt, args)` | Or `std.debug.panicExtra(ret_addr, fmt, args)` to control the first trace frame. |
| A build script cannot continue | `catch @panic("OOM")` | Sanctioned **only** in `build.zig`; all 181 `@panic("OOM")` sites in std are under `Build.zig`. |
| A check inside a `test` block | `std.testing.expect*` | std's own doc: `assert` may not detect a test failure in ReleaseFast/ReleaseSmall. |

```zig
// verified — GOOD
const std = @import("std");
const assert = std.debug.assert;

/// Asserts `index` is in bounds. Returns null when the slot is vacant.
fn slotAt(slots: []const ?u32, index: usize) ?u32 {
    assert(index < slots.len); // Programmer error: the caller must range-check.
    return slots[index]; // Vacancy is an operating condition: optional, not error.
}

/// Returns error.Truncated when the peer sent a short frame — an operating condition.
fn parseHeader(bytes: []const u8) error{Truncated}!u32 {
    if (bytes.len < 4) return error.Truncated;
    return std.mem.readInt(u32, bytes[0..4], .little);
}
```

Corollary: `std.debug.assert` is an ordinary function — `pub fn assert(ok: bool) void { if (!ok)
unreachable; }` (`std/debug.zig:418`) — so in ReleaseFast/ReleaseSmall the *check* disappears but
the *condition is still evaluated*. `assert(list.pop() != null)` still pops in release; it just
stops verifying the result. Never put a side effect inside an assert. On 0.16.0, a counter
incremented inside an assert condition reaches the same value in all four optimize modes. The full
treatment, including the per-mode table, is `references/assertions-and-limits.md` ZS-ASRT-03.

### ZS-ERR-02 [M] Return an optional for absence; reserve the error union for failure

`?T` when "not there" is a normal outcome; `E!T` when something went wrong. (The general
return-type-dimensionality ladder — `void` before `bool` before `u64` before `?u64` before `!u64` —
is owned by `references/types-and-data.md` ZS-TYPE-30; this rule is only about the `?T`/`E!T`
boundary.)

**Why:** an error union makes absence viral. Every caller must `try` or `catch`, and each `try`
widens *its* inferred error set, propagating a non-event through the whole call chain.

**Check:** an error set member named `NotFound`, `Missing`, `Empty`, `NoSuchKey`, or `Absent` on a
lookup function — almost always a `?T` written as an `E!T`.

```zig
// fragment — BAD: a cache miss is not a failure
fn get(cache: *const Cache, key: u32) error{NotFound}!u32 { ... }
// Every caller now writes `catch |e| switch (e) { error.NotFound => ... }`.
```

```zig
// verified — GOOD
const std = @import("std");
fn findScalar(haystack: []const u8, needle: u8) ?usize {
    return std.mem.findScalar(u8, haystack, needle);
}

test "optional lookup" {
    const index = findScalar("abc", 'z') orelse 0;
    try std.testing.expectEqual(0, index);
    if (findScalar("abc", 'c')) |i| try std.testing.expectEqual(2, i);
}
```

Note `std.mem.findScalar`, not `indexOfScalar` — the whole `indexOf*` family was renamed to `find*`
in 0.16, and the old names survive only as silent aliases.

### ZS-ERR-03 [M] A library never panics, never exits, never prints

A reusable module returns errors. This governs *operating* errors: a library must never convert a
recoverable condition into a process abort. `@panic`, `std.process.exit`, `std.process.fatal`,
`std.debug.print`, and writing to stderr are all reserved for the application's top level (`main`)
or for `build.zig`.

It does **not** govern assertions. A violated internal invariant has exactly one correct response in
any code, library or not, so `assert` and a project-local always-on `assertAlways`
(`references/assertions-and-limits.md` ZS-ASRT-07) are legal in a library — including in allocators
and crypto, which are libraries by construction. What a library may not do is choose its consumer's
optimize mode: document which invariants it asserts and what it costs to run it under ReleaseSafe,
and let the consumer decide (`references/build-and-project.md` ZS-BUILD-27).

**Why:** a library does not know whether its caller can recover. Aborting the process removes the
caller's ability to retry, degrade, or report. It also makes the library untestable — a test cannot
assert on a process that has already exited. An assertion is different in kind: there is no state in
which the caller could usefully continue, so no recovery capability is being taken away.

**Check:** in a non-`main`, non-`build.zig` file, grep for `@panic(`, `process.exit`,
`process.fatal`, and `debug.print`. `assert(`, `unreachable`, and `assertAlways(` are not hits.

```zig
// fragment — BAD
pub fn parse(gpa: Allocator, text: []const u8) Ast {
    return parseInner(gpa, text) catch @panic("bad input"); // Caller had a fallback. Too late.
}
```

```zig
// verified — GOOD
const std = @import("std");

pub fn main(init: std.process.Init) !void {
    const args = init.minimal.args.toSlice(init.arena.allocator()) catch
        std.process.fatal("out of memory reading argv", .{});
    if (args.len < 2) std.process.fatal("usage: {s} <count>", .{args[0]});

    const count = std.fmt.parseInt(u32, args[1], 10) catch |err| switch (err) {
        error.InvalidCharacter => std.process.fatal("'{s}' is not a number", .{args[1]}),
        error.Overflow => std.process.fatal("'{s}' does not fit in u32", .{args[1]}),
    };
    _ = count;
}
```

---

## 2. Error sets

### ZS-ERR-04 [M] Name the error set of every public function; infer only for private helpers

`pub` functions declare `SomeError!T` (or an alias such as `Allocator.Error`, `Io.Writer.Error`,
`Io.Cancelable`). Bare `!T` is for private/internal helpers, `main`, and tests.

**Why:** an inferred error set is part of your ABI that nobody can read. Adding one `try` to a
private callee three levels down silently widens a public signature, and every downstream
`catch |e| switch (e)` that was exhaustive is now non-exhaustive — a compile error in someone
else's repo caused by a change you did not think was public. std is **not** a model here, and
pretending otherwise weakens the rule: counted over single-line signatures at 0.16.0
(`rg 'pub fn \w+\([^)\n]*\) !' -g '*.zig'` for bare; swap the trailing `!` for
`[A-Za-z][A-Za-z0-9_.()]*!` for named), 1157 `pub fn` declare a named set but **416 still return a
bare `!`** — `priority_queue`'s `ensureTotalCapacity` and `pushSlice` among them, though the
flagship containers are clean: every `ArrayList`/`HashMap` `ensureTotalCapacity` returns
`Allocator.Error!void` or `Oom!void` (non-`pub` helpers add another 548 bare). This standard takes
the strict side of that 3:1 split, because the quarter that infer are exactly the ones whose sets
can widen under a caller without warning.

**Check:** grep for `pub fn` lines whose return type begins with a bare `!` — `) ![` , `) !void`,
`) !u`. `main`, `test`, and non-`pub` helpers are not hits.

```zig
// fragment — BAD: the set is invisible and grows silently
pub fn load(gpa: Allocator, path: []const u8) ![]u8 { ... }
```

```zig
// verified — GOOD
const std = @import("std");
const assert = std.debug.assert;

pub const ParseError = error{ InvalidCharacter, Overflow };

pub fn parseDecimal(text: []const u8) ParseError!u32 {
    assert(text.len > 0);
    var value: u32 = 0;
    for (text) |c| {
        if (c < '0' or c > '9') return error.InvalidCharacter;
        const digit: u32 = c - '0';
        value = std.math.mul(u32, value, 10) catch return error.Overflow;
        value = std.math.add(u32, value, digit) catch return error.Overflow;
    }
    return value;
}
```

### ZS-ERR-05 [S] Compose sets with `||`; name a composed set after the verb it belongs to

std's convention across 192 named sets is `pub const <Verb>Error = error{…}` declared next to the
function, merging in reusable sets with `||`.

**Why:** the merge operator keeps one authoritative definition per concern. Re-listing
`error{OutOfMemory}` in fifteen places means the sixteenth will disagree.

**Check:** the same `error{…}` member list spelled out in two places instead of one named set
merged with `||`; and a named set whose identifier does not end in `Error` or is not named after
the verb whose function returns it.

```zig
// verified — GOOD
const std = @import("std");

pub const ParseError = error{ InvalidCharacter, Overflow };
pub const ReadError = error{ EndOfStream, ConnectionResetByPeer };
pub const LoadError = ParseError || ReadError || std.mem.Allocator.Error; // 5 members
```

Give individual members `///` docs when the condition is not obvious from the name — std does this
heavily for platform-specific members. A one-member set is written inline, not hoisted:
`pub const Error = error{OutOfMemory};` (`mem/Allocator.zig:11`).

### ZS-ERR-06 [M] Never put `anyerror` in a public signature

**Why:** `anyerror` is the set of every error in the program, so no caller can ever write an
exhaustive `switch`, and `@typeInfo(anyerror).error_set` is `null` rather than a member list. It
also defeats error-set–based optimisation. std has 43 occurrences in 434 KLOC, and the one notable
public use is `testing.expectError(expected_error: anyerror, …)`.

**Check:** grep `anyerror` — every hit in a `pub fn` signature, a `pub const` type alias, or a
public struct field is the finding. `anyerror` inside a test body or a private helper is not.

### ZS-ERR-07 [S] Use `error{}!T` to state that a path cannot fail

The empty error set makes an error union that no value can inhabit. `try` on it is free, and the
compiler enforces the claim.

**Why:** it lets an interface stay uniform (all implementations return `E!T`) while proving in the
type system that this particular implementation is infallible, instead of documenting it in a
comment nobody reads.

**Check:** a comment saying "cannot fail", "never fails", or "infallible" above a function that is
one implementation of an interface whose other implementations return `E!T` — the claim belongs in
the return type. Also a vtable implementation returning a wide error set every arm of which is
`unreachable`.

```zig
// verified — GOOD
fn cannotFail(x: u8) error{}!u8 {
    return x +| 1;
}
```

---

## 3. `try`, `catch`, and `catch unreachable`

### ZS-ERR-08 [M] `try` is the default; every `catch {}` or `catch unreachable` carries a comment

| Form | Use when |
|---|---|
| `try f()` | The caller is better placed to decide. This is the default and should dominate. |
| `f() catch \|e\| switch (e) { … }` | You can meaningfully handle *some* variants here. |
| `f() catch \|e\| { log.err("…: {t}", .{e}); return e; }` | Add context, then propagate. `{t}` prints the error name. |
| `f() catch default_value` | The operation is genuinely optional and the default is correct. |
| `f() catch blk: { …; break :blk fallback; }` | The fallback needs real logic to compute. |
| `f() catch unreachable` | Only with a written proof. See ZS-ERR-10. |
| `f() catch @panic("msg")`, `catch std.process.fatal(…)` | Application top level only. Never in a library. |
| `f() catch {}` | Almost never. See ZS-ERR-11. |

**Why:** `try` is the only form that preserves the error return trace *and* forces the decision
upward to code that has the context to make it. Each `catch` is a place where information about the
failure stops travelling.

**Check:** in a diff, `try` should outnumber `catch`. Every `catch unreachable` has a proof comment
(ZS-ERR-10) and every `catch {}` has a justification comment (ZS-ERR-11) on an adjacent line; a bare
one with no comment is the defect.

### ZS-ERR-09 [M] Switch on the captured error, and omit `else` when the set is explicit

`catch |err| switch (err)` with one prong per member and **no** `else`. Add `else => |e| return e`
only when the set is inferred, is `anyerror`, or genuinely comes from a third party.

**Why:** an exhaustive switch on an explicit set turns "upstream added a new error" into a compile
error at exactly the site that must decide what to do about it. An `else` prong turns the same event
into a silent behavior change. This is std's dominant shape: 525 `catch |err| switch (err)` sites.

**Check:** an `else =>` prong in a `switch` over an error set that is named and declared in this
repo. Follow the callee's return type: if it is `SomeError!T` rather than `!T` or `anyerror!T`, the
`else` is unnecessary and hides the next added member.

```zig
// fragment — BAD: a new ParseError member is silently swallowed by `else`
_ = parseDecimal(text) catch |err| switch (err) {
    error.InvalidCharacter => return "not a number",
    else => return "unknown",
};
```

```zig
// fragment — GOOD: with `parseDecimal` from ZS-ERR-04 in scope
fn describe(text: []const u8) []const u8 {
    _ = parseDecimal(text) catch |err| switch (err) {
        error.InvalidCharacter => return "not a number",
        error.Overflow => return "too large",
    };
    return "ok";
}
```

The three-way narrowing form is idiomatic std when you must handle some variants, rule out some, and
forward the rest:

```zig
// verified — GOOD
const Wide = error{ WriteFailed, EndOfStream, Canceled, OutOfMemory };

fn drain(err: Wide) error{ Canceled, OutOfMemory }!void {
    return switch (err) {
        // We wrote into a fixed buffer sized by construction; it cannot fail.
        error.WriteFailed => unreachable,
        error.EndOfStream => {}, // Expected termination.
        else => |e| e,
    };
}
```

`@errorCast` also narrows a set, but it asserts rather than proves — use it only directly after an
`assert` that rules out the excluded members.

### ZS-ERR-10 [M] `catch unreachable` is a latent bug unless the proof is in a comment next to it

`catch unreachable` claims *this error is impossible given local invariants*. Write the one-line
proof. If you cannot write it, you have a bug, not an invariant.

**Why:** `unreachable` is a safety-checked panic in Debug/ReleaseSafe and **illegal behavior** in
ReleaseFast/ReleaseSmall. A wrong `catch unreachable` therefore does not crash in production — it
miscompiles the surrounding code. The usual failure is an OOM or an I/O error that "obviously can't
happen" until the machine is under memory pressure or the disk fills. std has 326 uses; each sits
next to a buffer whose size is fixed at compile time.

```zig
// fragment — BAD: allocation can always fail
const copy = gpa.dupe(u8, name) catch unreachable;
```

```zig
// verified — GOOD
const std = @import("std");

fn formatCode(code: u8) []const u8 {
    var buf: [4]u8 = undefined;
    // `buf` holds 4 bytes; a u8 renders in at most 3 decimal digits, so
    // bufPrint cannot fail here.
    return std.fmt.bufPrint(&buf, "{d}", .{code}) catch unreachable;
}
```

**Exempt: `comptime`-evaluated `catch unreachable`.** In a `const` initializer or a `comptime` block
the expression is folded by the compiler, so a failure is `error: reached unreachable code` at build
time and can never be illegal behavior at runtime — there is nothing to prove and no comment is
required. This is why the derived-limit idiom in `references/assertions-and-limits.md`
ZS-ASRT-25/ZS-ASRT-26 is written without one:

```zig
// fragment — GOOD: comptime-evaluated, so failure is a compile error
pub const blocks_per_message_max: u32 =
    std.math.divCeil(u32, message_size_bytes_max, block_size_bytes) catch unreachable;
```

`[M!]` sharpening — in high-reliability code (databases, consensus and replication, crypto,
allocators, kernel and embedded firmware: anywhere a crash or silent corruption is unacceptable), do
not use `catch unreachable` on a *runtime* path at all. Return the error, or restructure so the
fallible call is not on that path; the comptime form above stays legal. The relaxed form elsewhere
is the proof-comment rule above.

**Check:** every runtime `catch unreachable` has a comment on the same or the preceding line
naming the fixed bound that makes failure impossible. The short spelling `.?` has no proof form at
all — ZS-ERR-30 forbids it outright.

### ZS-ERR-11 [M] Every error is handled somewhere; `catch {}` needs a justification comment

No dropped errors. `catch {}`, `_ = f() catch {};`, and `catch null` are all silent discards.

**Why:** Yuan et al. (OSDI '14, *Simple Testing Can Prevent Most Critical Failures*) found that 92%
of catastrophic failures in distributed data-intensive systems came from incorrect handling of
non-fatal errors that the software had already explicitly signalled — the failure was detected and
then thrown away. Empty `catch` blocks are the highest-yield thing to grep for in review.

**Check:** `catch {}`, `catch {};`, `_ = … catch`, `catch null`, and `catch false` with no comment
on the same or the preceding line saying why the failure is genuinely not information. A `catch`
that logs and continues is a different rule (ZS-ERR-08) and is not a hit here — but if the call took
an `io`, it is a hit under ZS-IO-27, which treats log-and-continue as a dropped cancellation.

```zig
// fragment — BAD
writer.flush() catch {}; // Data loss, silently.
```

```zig
// fragment — GOOD
// Best-effort cleanup on a path that is already failing; the original error is
// what the caller needs, and a second failure here adds nothing.
dir.deleteFile(io, scratch_path) catch |err| log.warn("removing scratch file: {t}", .{err});
```

Note the cleanup call has to be one that can actually fail. `Io.File.close` is
`pub fn close(file: File, io: Io) void` — it returns no error at all, so `file.close(io) catch …` is
`error: expected error union type, found 'void'`. Closing is spelled `defer file.close(io);` with no
`try` and no `catch` (ZS-IO-22, ZS-MEM-11).

The cancellation corollary this rule does not own: `deleteFile`'s error set contains
`Io.Cancelable`, so the `catch` above also absorbs `error.Canceled`. That is legal *here* only
because the path is already leaving — as the comment says, it is a failing path, and nothing follows
this line but the `return`. Log an error and then carry on with real work and you strand whoever
requested the cancel just as thoroughly as `catch {}` would. ZS-IO-27 owns that distinction; read it
before copying this shape onto a path that continues.

---

## 4. `defer` and `errdefer`

### ZS-ERR-12 [M] Put the release on the line immediately after the acquisition (see ZS-MEM-11)

Owned by `references/memory-and-allocators.md` ZS-MEM-11. Never separate an acquiring statement from
its `defer`/`errdefer`; anything between the two is a leak window. The rules below cover what
happens *after* the pair is correctly placed: ordering (ZS-ERR-13), ownership transfer (ZS-ERR-14),
and loop scope (ZS-ERR-15).

### ZS-ERR-13 [M] Order `defer`/`errdefer` so LIFO teardown cannot outrun what a handler reads

All `defer` and `errdefer` statements in a block run in **reverse declaration order** when control
leaves the block. On a normal exit only the `defer`s run; on an error exit both kinds run,
interleaved in that same single LIFO sequence. An `errdefer` in a function that cannot return an
error compiles and silently never fires.

**Why:** LIFO is what makes "acquire A, then B" unwind as "release B, then A" with no manual
bookkeeping. The interleaving matters when an `errdefer` needs state that a later-declared `defer`
tears down.

**Check:** an `errdefer` in a function whose return type contains no `!` — it compiles and never
fires. And an `errdefer` whose body reads state that a *later-declared* `defer` tears down: LIFO
runs the `defer` first, so the `errdefer` sees the torn-down value.

```zig
// fragment — GOOD: normal exit records "CA", error exit records "DCBA"
fn ordered(fail: bool) error{Fail}!void {
    defer note('A');
    errdefer note('B');
    defer note('C');
    errdefer note('D');
    if (fail) return error.Fail;
}
```

```zig
// fragment — BAD: compiles, never runs; `noFail` cannot return an error
fn noFail() void {
    errdefer rollback();
    mutate();
}
```

### ZS-ERR-14 [M] Stop the `errdefer` at the point ownership transfers

An `errdefer` covers a resource only from its declaration until something else becomes responsible
for freeing it. Once a value is appended to a container that owns its items, or returned to the
caller, the `errdefer` for it must no longer be in scope.

**Why:** an `errdefer` that outlives the transfer is a double free on the error path — the container
frees the item during its own cleanup, then the stale `errdefer` frees it again. `Allocator.free`
`@memset`s the bytes to `undefined` *before* calling `rawFree`, so the second free faults inside
`free` with a stack trace that points at the allocator, not at your bug.

**Check:** an `errdefer gpa.free(x)` / `errdefer x.deinit(gpa)` declared at *function* scope over a
value that is later passed to `append`, `put`, `toOwnedSlice`, or `return` — the transfer happens
inside a scope the `errdefer` outlives. The correct shape declares it inside the loop body.

```zig
// verified — GOOD: the inner errdefer covers only the rest of this iteration
const std = @import("std");
const Allocator = std.mem.Allocator;

fn takeAll(gpa: Allocator, n: usize) Allocator.Error![][]u8 {
    var owned: std.ArrayList([]u8) = .empty;
    errdefer {
        for (owned.items) |item| gpa.free(item);
        owned.deinit(gpa);
    }
    for (0..n) |i| {
        const item = try gpa.alloc(u8, 1);
        errdefer gpa.free(item); // Ownership moves to `owned` on the next line.
        item[0] = @intCast(i);
        try owned.append(gpa, item);
    }
    return owned.toOwnedSlice(gpa);
}
```

Exercise these paths with `std.testing.checkAllAllocationFailures` — an `errdefer` chain that has
never been driven at every allocation point is untested code.

### ZS-ERR-15 [M] A `defer` in a loop body runs each iteration, not at function exit

If the resource must outlive the loop, hoist the release out and track every instance. If it must
not, keep the `defer` inside the loop body.

**Why:** a function-scope `defer gpa.free(buf)` paired with an in-loop assignment frees only the
*last* buffer and leaks every earlier one; the reverse mistake (an in-loop `defer` on something the
caller keeps) is a use-after-free.

**Check:** a `defer` at function scope naming a variable that is assigned inside a loop below it;
and the converse, a `defer` inside a loop body naming a value that the loop appends to a container
or that the function returns.

```zig
// verified — GOOD: per-iteration lifetime, per-iteration free
const std = @import("std");
const Allocator = std.mem.Allocator;

fn sumFiles(gpa: Allocator, counts: []const usize) Allocator.Error!usize {
    var total: usize = 0;
    for (counts) |n| {
        const buf = try gpa.alloc(u8, n);
        defer gpa.free(buf); // Per-iteration: correct here.
        total += buf.len;
    }
    return total;
}
```

```zig
// fragment — BAD: compiles, leaks every buffer but the last
fn sumFilesLeaky(gpa: Allocator, counts: []const usize) Allocator.Error!usize {
    var buf: []u8 = &.{};
    defer gpa.free(buf); // Function scope: runs once, on the LAST value.
    var total: usize = 0;
    for (counts) |n| {
        buf = try gpa.alloc(u8, n);
        total += buf.len;
    }
    return total;
}
```

### ZS-ERR-16 [S] `errdefer |err|` is for diagnostics, not for control flow

The capture form `errdefer |err| { … }` binds the error that is unwinding. Use it to log or to bump
a metric; do not use it to branch cleanup logic.

**Why:** cleanup that depends on *which* error occurred means the rollback is not uniform, which is
exactly the property that makes unwinding safe to reason about. std uses the capture form once in
the whole tree — treat it as rare.

**Check:** an `errdefer |err| {` whose body contains an `if`, a `switch`, a `free`, a `close`, or a
`deinit`. A body that is only a `log.*` call or a counter increment is the sanctioned use.

```zig
// verified — GOOD
const std = @import("std");
const Allocator = std.mem.Allocator;
const log = std.log.scoped(.doc);

fn openWithLog(gpa: Allocator, n: usize) Allocator.Error![]u8 {
    const buf = try gpa.alloc(u8, n);
    errdefer |err| log.warn("rollback after {t}", .{err});
    errdefer gpa.free(buf);
    if (n > 8) return error.OutOfMemory;
    return buf;
}
```

---

## 5. Error return traces

### ZS-ERR-17 [M] Propagate with `try` or `return err`; never launder an error through an optional

`@errorReturnTrace()` returns `?*std.builtin.StackTrace`: non-null in Debug and ReleaseSafe,
**null** in ReleaseFast and ReleaseSmall. The trace is
built by `try` and by `return err`, and is **destroyed** by any `catch` that does not re-return, and
by converting the error into an optional, a sentinel, or a bool.

**Why:** the trace is the only record of the *chain* of returns — which `try`, at which depth, first
produced the error. Once it has been converted to `null` or `false`, that chain is gone and you are
debugging an absence.

```zig
// verified — GOOD: `return err` keeps the trace intact
const std = @import("std");
const log = std.log.scoped(.loader);

fn readConfig(path: []const u8) error{FileNotFound}!void {
    if (path.len == 0) return error.FileNotFound;
}

fn load(path: []const u8) error{FileNotFound}!void {
    return readConfig(path) catch |err| {
        log.err("reading config '{s}' failed: {t}", .{ path, err });
        return err;
    };
}
```

```zig
// fragment — BAD: compiles, and the trace dies here
fn laundered() ?u32 {
    return fails() catch null;
}
```

Print an error return trace with **`std.debug.dumpErrorReturnTrace(et)`**, whose parameter is
exactly the `*const std.builtin.StackTrace` that `@errorReturnTrace()` yields;
`writeErrorReturnTrace(et, t)` is the same thing against an `Io.Terminal` you supply. Do **not**
reach for `std.debug.dumpStackTrace` here: in 0.16 that takes a `*const std.debug.StackTrace` (`{
return_addresses: []usize, skipped: SkippedAddresses }`), which is a different type from
`std.builtin.StackTrace` (`{ index: usize, instruction_addresses: []usize }`) and will not compile.
Capturing a *stack* trace is ZS-ERR-36.

```zig
// fragment — GOOD
fn caller() void {
    fails() catch {
        if (@errorReturnTrace()) |ert| std.debug.dumpErrorReturnTrace(ert);
        return;
    };
}
```

A `main` that returns `!void` prints the error name and its return trace automatically, which is the
reason to prefer `try` all the way up in application code.

**Check:** a function returning `?T` or `bool` whose body contains `catch null`, `catch false`, or
`catch return null` over a call that had a real error set.

---

## 6. Simple, explicit control flow (TigerStyle)

### ZS-ERR-18 [M] Split compound conditions into separate checks

Prefer a sequence of single-predicate `if`s — usually with early returns — over `a and b and c`.

**Why:** with a compound condition, a reader verifying "is every case handled?" has to evaluate a
truth table in their head, and a debugger stopped on the branch cannot tell you *which* conjunct was
false. One predicate per `if` makes both mechanical.

**Check:** an `if` header or a `return` expression containing two or more ` and `/` or ` operators
over independent predicates. A single `and` joining the two halves of one range check
(`a <= x and x < b`) is not a hit.

```zig
// fragment — BAD
fn acceptCompound(f: Frame) bool {
    return f.len > 0 and f.len <= 4096 and f.crc_ok and f.kind == 1;
}
```

```zig
// verified — GOOD
const Frame = struct { len: u32, crc_ok: bool, kind: u8 };

fn acceptNested(f: Frame) bool {
    if (f.len == 0) return false;
    if (f.len > 4096) return false;
    if (!f.crc_ok) return false;
    if (f.kind != 1) return false;
    return true;
}
```

The same rule applies to assertions: `assert(a); assert(b);` beats `assert(a and b)`, because the
panic then tells you which one failed.

### ZS-ERR-19 [S] Prefer a `switch` to an `else if` chain; if you flatten chains into trees, say why

**Honest disagreement.** TigerStyle mandates rewriting `else if` chains into nested `else { if { }
}` trees. Idiomatic Zig and the standard library do not do this — `else if` chains appear throughout
std, and `zig fmt` formats them as chains. The two positions are irreconcilable as written.

Recommendation, keyed to tiers — `[S]`: when the chain dispatches on one value, convert it to a
`switch`, which buys you exhaustiveness checking that neither `if` form provides. When it dispatches
on unrelated predicates, an `else if` chain is acceptable idiomatic Zig; adopt the nested-tree form
only in a codebase that has adopted TigerStyle wholesale, and be consistent within a file.

**Why:** the `switch` half of this rule buys a compiler check that neither `if` form can: a `switch`
over an enum or tagged union is verified exhaustive at compile time, so adding a variant breaks the
build at every dispatch site (ZS-ERR-28). An `else if` chain over the same values compiles fine and
falls through to the last `else` at runtime. That mechanism exists only when the chain dispatches on
one value, which is why the recommendation is keyed to that case rather than to the chain's shape.
The nested-tree rewrite buys no such check — it is a readability preference, and since `zig fmt`
will not produce it, mixing both spellings in one file costs more than either convention alone.

**Check:** an `else if` chain whose conditions all compare the *same* expression against different
constants or enum tags — that is a `switch` written the long way. Within one file, the chain form
and the nested `else { if { } }` form both present is the consistency finding.

```zig
// verified — GOOD: a switch replaces the chain and is checked for exhaustiveness
const State = enum { idle, running, stopped };

fn label(s: State) []const u8 {
    return switch (s) {
        .idle => "idle",
        .running => "running",
        .stopped => "stopped",
    };
}
```

### ZS-ERR-20 [M] State invariants positively when an `if`/`else` splits the input space

When an `if`/`else` splits the input space, write the branch condition as the invariant that
*holds*: `if (index < length) { … } else { … }`, not `if (index >= length)`.

**Early-return guards are exempt.** `if (index >= items.len) return null;` states the *rejection*
condition, which is the whole point of a guard, and guards are what ZS-ERR-18 asks for. What is
forbidden is a non-guard `if` whose condition negates an invariant that the same function states
positively elsewhere — the reader then has to hold both spellings of one relation in their head.
(Same wording as SKILL.md ZS-CORE-18; the guard form is used by ZS-ERR-25, ZS-NAME-31 and
ZS-ASRT-16.)

**Why:** the positive form matches how the same relation is written in the loop condition (`while
(index < length)`) and in the assertion (`assert(index < length)`), so the reader compares identical
expressions instead of mentally negating one of them. Negations are where off-by-one errors hide.

```zig
// verified — GOOD
fn atIndex(items: []const u32, index: usize) ?u32 {
    if (index < items.len) {
        return items[index];
    } else {
        return null;
    }
}
```

**Check:** an `if (a >= b)` / `if (!ok)` whose body is a block rather than a single early `return`,
`break`, or `continue`, in a function that also writes the same relation the other way round.

### ZS-ERR-21 [S] An `if` with no `else` over a validated domain carries a comment or an assertion

For every `if` without an `else` where the negative case is a deliberate no-op, write that down: a
one-line comment in the empty half, or an assertion stating what is true when the condition is
false.

**Why:** bugs cluster where data crosses the valid/invalid boundary. An `if` with no `else` is a
silent claim that the other half of the input space needs nothing, and silence does not distinguish
"I decided this is a no-op" from "I forgot". A comment or an assertion turns it into a claim a
reviewer can disagree with.

**Check:** in a diff, an added `if` with no `else` whose surrounding block has no comment and no
following `assert` naming the negative case.

```zig
// verified — GOOD
const std = @import("std");
const assert = std.debug.assert;

const Status = enum { normal, draining };

fn admit(status: Status, budget: *u32, inflight: u32) void {
    if (budget.* > 0) budget.* -= 1;
    // No `else`: a spent budget is a deliberate no-op — the caller retries later.

    if (status == .draining) {
        // No `else`: the negative case is stated as an assertion, not a comment.
        assert(inflight > 0);
    }
    if (status == .normal) assert(budget.* < 64);
}
```

### ZS-ERR-22 [M] Braces, unless the whole statement fits on one line

`if (x) return;` on one line is fine. Anything that wraps gets braces. Never a braceless body on the
following line.

**Why:** a braceless multi-line body means adding a second statement silently changes control flow,
and `zig fmt` will not save you — it preserves the braceless form.

**Check:** an `if`/`while`/`for` header line ending in `)` with neither `{` on that line nor the
whole statement on that line — the body has wrapped onto the next line without braces.

```zig
// verified — GOOD
fn clamp(value: u32, limit: u32) u32 {
    if (value > limit) return limit;
    return value;
}
```

Same for implications in assertions: `if (a) assert(b);` on one line is the canonical form.

### ZS-ERR-23 [M!] No recursion; where recursion is allowed, bound the depth explicitly

`[M!]` — mandatory in high-reliability code, meaning any codebase where a crash or memory corruption
is unacceptable: databases, consensus and replication, crypto, allocators, kernel and embedded
firmware, anything running unattended on untrusted input. There, write the iterative form with an
explicit stack of fixed size. Elsewhere the relaxed form is: recursion is permitted only when the
maximum depth is a named constant that is asserted, or is a `comptime` parameter, which makes the
bound a compile-time fact.

**Why:** Zig gives no stack-depth guarantee and no stack-overflow *error* — you get a fault, and on
targets without a guard page you get silent corruption of whatever lies below the stack. A recursive
descent over attacker-controlled nesting depth is a remote crash primitive.

**Check:** a function whose body names itself, or a mutually recursive pair, with no `comptime
depth` parameter and no runtime `depth`/`level` compared against a named `_max` constant. Parsers,
tree walks, and directory traversals are where this hides.

```zig
// verified — GOOD: explicit stack, depth asserted at every push
const std = @import("std");
const assert = std.debug.assert;

const Node = struct { left: ?*const Node, right: ?*const Node, value: u32 };
const depth_max = 8;

fn sumIterative(root: *const Node) u32 {
    var stack: [depth_max]*const Node = undefined;
    var top: usize = 0;
    stack[top] = root;
    top += 1;

    var total: u32 = 0;
    while (top > 0) {
        top -= 1;
        const node = stack[top];
        total += node.value;
        if (node.left) |left| {
            assert(top < depth_max);
            stack[top] = left;
            top += 1;
        }
        if (node.right) |right| {
            assert(top < depth_max);
            stack[top] = right;
            top += 1;
        }
    }
    return total;
}
```

```zig
// verified — GOOD: relaxed tier — depth is a comptime parameter, bounded at compile time
const std = @import("std");
const assert = std.debug.assert;

fn depthSum(comptime depth: u8, values: []const u32) u32 {
    comptime assert(depth <= 4);
    if (depth == 0 or values.len == 0) return 0;
    return values[0] + depthSum(depth - 1, values[1..]);
}
```

### ZS-ERR-24 [M] Every loop has a provable upper bound (see ZS-ASRT-27)

Owned by `references/assertions-and-limits.md` ZS-ASRT-27, which gives the four legitimate loop
shapes and the witness-counter idiom. Prefer `for (slice)` and `for (0..limit)`, which carry the
bound in the syntax; a `while` whose termination is not obvious gets a counter asserted against a
named `_max` constant; a deliberately unbounded event loop says so in a comment and asserts the
reverse property.

### ZS-ERR-25 [M!] Push `if`s up and `for`s down

`[M!]` — mandatory in high-reliability code (databases, consensus, crypto, allocators, kernel and
embedded firmware, parsers on untrusted input), matching SKILL.md ZS-CORE-21 and ZS-ERR-34. Keep
branching in the parent function; give leaf helpers primitive arguments and no control flow.
*Relaxed form elsewhere:* a leaf helper that branches on a condition its caller already knows is a
review comment, not a build failure.

**Why:** it concentrates the decisions in one readable place, and it makes the leaf a straight-line
function that the compiler can vectorise and a reader can check without tracing callers. It is also
the mechanism that keeps parents under the 70-line limit (ZS-ERR-34) without scattering the logic.

```zig
// verified — GOOD
const std = @import("std");
const assert = std.debug.assert;

fn writeAll(target: []u8, source: []const u8) void {
    assert(target.len >= source.len); // Precondition, not a branch.
    for (source, target[0..source.len]) |s, *t| t.* = s;
}

fn copyIfRoom(target: []u8, source: []const u8) bool {
    if (target.len < source.len) return false; // The `if` lives here.
    writeAll(target, source);
    return true;
}
```

**Check:** a private helper called from exactly one site whose first statement is an `if` on a
condition the caller already tested, or a caller that loops calling a helper that could have taken
the whole slice.

---

## 7. Modern Zig control flow the standard prefers

### ZS-ERR-26 [S] Use labeled `switch` with `continue :label` for state machines and dispatch loops

`sw: switch (initial) { .a => { …; continue :sw next; }, … }` replaces
`while (true) { switch (state) { … } }`. A `continue` targeting a switch **must** carry an operand;
`break :sw` exits, and `break :sw value` yields a value.

**Why:** this is a code-generation construct, not sugar. Per the langref: when the `continue`
operand is comptime-known it lowers to an unconditional branch, which is perfectly predicted; when
it is runtime-known, each `continue` embeds its own conditional branch (ideally a jump table), so
the CPU predicts each transition independently. A `while`+`switch` loop funnels every transition
through one dispatch point, which is a branch-prediction bottleneck in exactly the hot loops where
this pattern is used.

**Check:** a `while (true) { switch (state) { … } }` whose arms all end by assigning `state` —
that is a labeled `switch` written the long way. Separately, an unlabeled `break` or `continue`
inside a labeled construct, which silently targets the innermost loop rather than the labeled one.

```zig
// verified — GOOD
const Scan = enum { start, in_word, done };

fn wordCount(text: []const u8) u32 {
    var words: u32 = 0;
    var index: usize = 0;

    sw: switch (Scan.start) {
        .start => {
            if (index == text.len) continue :sw .done;
            if (text[index] == ' ') {
                index += 1;
                continue :sw .start;
            }
            words += 1;
            continue :sw .in_word;
        },
        .in_word => {
            if (index == text.len) continue :sw .done;
            if (text[index] == ' ') continue :sw .start;
            index += 1;
            continue :sw .in_word;
        },
        .done => break :sw,
    }
    return words;
}
```

Label a `break`/`continue` whenever the target is not the innermost loop. An unlabeled `break`
inside a labeled construct is a readability trap.

### ZS-ERR-27 [S] Use a labeled block to compute a value that needs statements

`const x = blk: { …; break :blk value; };` keeps a multi-step computation inside the initializer of
the `const` it produces.

**Why:** it keeps the binding `const` and confines the temporaries to the block, which is
TigerStyle's "smallest possible scope" rule made mechanical. The alternative is a `var` that is
mutated once and then must be read as though it were constant.

**Check:** a `var` that is assigned exactly once after its declaration and never mutated again, plus
the temporaries computed alongside it still live in the enclosing scope. Both collapse into one
labeled-block `const`.

```zig
// fragment — GOOD
const limit = blk: {
    const base: u32 = 16;
    break :blk base * 4;
};
```

The `catch blk: { … break :blk fallback; }` form is the canonical "default value after some logic".

### ZS-ERR-28 [M] Switch exhaustively with no `else`; use `_` on non-exhaustive enums

For your own enums and unions, list every prong and do not add `else`. For a non-exhaustive enum —
one with a trailing `_` field — use a `_ =>` prong rather than `else =>`.

**Why:** exhaustiveness is a design tool. Adding a variant should produce a compile error at every
site that must be updated, which is how you find them all; `else` converts that compile error into a
runtime fallthrough. `_ =>` handles out-of-range values while *still* erroring if you forget a named
tag, whereas `else =>` handles both and therefore checks neither.

**Check:** an `else =>` prong in a `switch` over an enum or tagged union declared in this repo. If
the enum's declaration ends in `_`, the prong should be `_ =>`; if it does not, the prong should not
exist at all.

```zig
// does-not-compile — this is the point
const std = @import("std");

const State = enum { idle, running, stopped };

fn label(s: State) []const u8 {
    return switch (s) {
        .idle => "idle",
        .running => "running",
        // error: switch must handle all possibilities
        // note: unhandled enumeration value: 'stopped'
    };
}

test {
    _ = label(.idle);
}
```

```zig
// verified — GOOD
const Opcode = enum(u8) { get = 1, put = 2, _ };

fn opcodeName(op: Opcode) []const u8 {
    return switch (op) {
        .get => "get",
        .put => "put",
        _ => "unknown",
    };
}
```

### ZS-ERR-29 [S] Use `inline for` / `inline else` only on a small comptime-known set

`inline for` over `@typeInfo(T).@"struct".fields` or over a tuple; `inline else => |tag|` to obtain
a comptime-known tag inside a runtime `switch`.

**Why:** `inline` fully unrolls, so machine code grows linearly with the iteration count. That is
correct when the loop body's *types* differ per iteration — something a runtime loop cannot express
— and wasteful when it is just a small runtime loop you wanted unrolled; let the optimiser decide
that.

**Check:** an `inline for` whose iterable is a plain integer range (`inline for (0..n)`) or an array
of same-typed values rather than `@typeInfo(T).@"struct".fields`, an enum's fields, or a tuple —
nothing in the body needed a comptime-known type, so this is hand-unrolling the optimiser owns.

```zig
// verified — GOOD
const std = @import("std");

const Config = struct { retries: u32, timeout_ms: u32 };
const Op = enum { add, sub, mul };

fn configNonZero(c: Config) bool {
    inline for (@typeInfo(Config).@"struct".fields) |field| {
        if (@field(c, field.name) == 0) return false;
    }
    return true;
}

fn opName(op: Op) []const u8 {
    switch (op) {
        inline else => |tag| return @tagName(tag),
    }
}
```

### ZS-ERR-30 [M] Unwrap optionals with `orelse` or a capture, never with `.?`

`.?` is `orelse unreachable` in four characters. Where the proof rule (ZS-ERR-10) genuinely
licenses an unreachable, write `orelse unreachable` and write the proof beside it; std does that
three times in 434 KLOC. The short spelling has no licensed use.

**Why:** `.?` on a null is a safety-checked panic in Debug/ReleaseSafe and **illegal behavior** in
ReleaseFast/ReleaseSmall — the same trap as `catch unreachable`, in a form so short that it slips
through review. That shortness is the whole objection: the long spelling survives review because it
is visible, and it is the one place a proof comment has to go.

Most sites do not need the escape at all. `std.testing.expectEqual` compares optionals, so
`expectEqual(2, find(...))` needs no unwrap; a `callconv(.c)` callback that returns void can take
`orelse return`; a fallible path can take `orelse error.Something`.

**Check:** grep `.?` — every hit is a defect, including inside `comptime` blocks and `const`
initializers. `orelse unreachable` is the spelling that carries a proof, and ZS-ERR-10 governs it.

```zig
// verified — GOOD
const std = @import("std");
const assert = std.debug.assert;

test "iterate with capture" {
    var it = std.mem.splitScalar(u8, "a,b,c", ',');
    var count: u32 = 0;
    while (it.next()) |part| {
        assert(part.len == 1);
        count += 1;
    }
    try std.testing.expectEqual(3, count);
}
```

`for` and `while` also take an `else` clause, which runs when the loop finished without `break`,
which makes the loop an expression:

```zig
// fragment — GOOD
const found = for (items) |it| {
    if (it == 9) break it;
} else 0;
```

### ZS-ERR-31 [M] Replace `@setCold` with `@branchHint`; placing hints on hot paths is `[S]`

`@branchHint(hint: std.builtin.BranchHint) void`. The hints are exactly `.none`, `.likely`,
`.unlikely`, `.cold`, `.unpredictable` (`std/builtin.zig:1131`). It is **only valid as the first
statement in a control-flow branch, or the first statement in a function**; otherwise the compiler
emits `error: '@branchHint' must appear as the first statement in a function or conditional branch`.

**Why:** `.cold` lets the optimiser move a branch's code to a different page, keeping the hot path's
instruction cache dense; `.unpredictable` tells it to prefer branchless lowering where a mispredict
would cost more than the extra work. std uses it deliberately: `.cold` ×100 on error paths
(including inside `std.log.err` and `std.debug.panic`), `.unlikely` ×65, `.likely` ×56.

**Check:** two findings at two tiers, and do not let the softer one absorb the harder one. `[M]`:
any surviving `@setCold(`, which was removed — the same removed-builtin class as ZS-CT-18 (`@Type`),
ZS-CT-27 (`usingnamespace`), and ZS-TYPE-26 (`std.BoundedArray`), all `[M]` for the same reason.
`[S]`: on a *measured* hot path, an error-returning branch or a `catch` block whose first statement
is not `@branchHint(.cold)` — a recommendation, and deviating needs only the measurement that says
the branch is not hot.

```zig
// verified — GOOD
fn decodeTag(byte: u8) error{ReservedTag}!u8 {
    if (byte < 0x80) {
        @branchHint(.likely);
        return byte;
    } else {
        @branchHint(.cold);
        return error.ReservedTag;
    }
}
```

```zig
// does-not-compile — not the first statement in the branch
const std = @import("std");
const assert = std.debug.assert;

fn f(x: u32) u32 {
    if (x == 0) {
        assert(x == 0);
        @branchHint(.cold); // error: must appear as the first statement
        return 0;
    }
    return x;
}
```

---

## 8. Logging

### ZS-ERR-32 [M] A library logs through a scoped `std.log` namespace

`const log = std.log.scoped(.mylib);` at the top of the file, then `log.warn(…)`. One scope per
module, named for the module.

**Why:** `std.log` routes through `std.options.logFn`, which the *application* owns — so the
application decides format, destination, filtering, and whether the library is audible at all. The
scope is the handle the application filters on (`log_scope_levels`, ZS-ERR-33); an unscoped
`std.log.warn` lands in the `.default` bucket alongside everyone else's and cannot be silenced
independently. std itself logs 35 times in 434 KLOC: the bar is high.

That `std.debug.print` and raw stderr writes are never program output, and never acceptable in a
library, is owned by `references/io-and-concurrency.md` ZS-IO-06 and
`references/formatting-and-output.md` ZS-FMT-16 / ZS-FMT-17. Program *output* is not logging: write
it to a `*std.Io.Writer` you were handed, and `flush()`.

```zig
// verified — GOOD
const std = @import("std");
const log = std.log.scoped(.mylib);

pub fn parseHeader(bytes: []const u8) error{Truncated}!u32 {
    if (bytes.len < 4) {
        log.debug("header truncated: {d} bytes", .{bytes.len});
        return error.Truncated;
    }
    return std.mem.readInt(u32, bytes[0..4], .little);
}
```

**Check:** in a library file, `std.log.warn(` / `std.log.err(` used directly instead of through a
file-level `scoped` alias.

### ZS-ERR-33 [S] Use std's four log levels, configured from the root file

`std.log.Level` is `{ err, warn, info, debug }` (`std/log.zig:30`), documented as: `err` — something
has gone wrong; `warn` — uncertain whether something has gone wrong, but worth investigating; `info`
— general state; `debug` — only useful when debugging. `default_level` is `.debug` in Debug and
`.info` in all three release modes.

**Why:** levels are a filter, not a severity vocabulary you get to redefine. If your library logs at
`err` for a condition it also returns as an error, the application sees it twice and cannot suppress
either copy independently.

**Check:** a `log.err(` on a path that also `return`s an error from the same function — pick one.
And a `pub const std_options` declared anywhere other than the root source file, where it is
silently inert.

```zig
// fragment — GOOD: in the root source file
pub const std_options: std.Options = .{
    .log_level = .info,
    .log_scope_levels = &.{
        .{ .scope = .mylib, .level = .debug },
    },
};
```

Log *or* return, not both, unless you are adding context and re-propagating (ZS-ERR-08). In tests,
`std.testing.log_level` defaults to `.warn`.

---

## 9. Function shape, user-facing diagnostics, and stack traces

### ZS-ERR-34 [M!] Hard limit of 70 lines per function; shape it like an inverse hourglass

`[M!]` — mandatory in high-reliability code (databases, consensus and replication, crypto,
allocators, kernel and embedded firmware, parsers on untrusted input). There, 70 lines between the
braces is a hard ceiling, counted as written including blank lines and comments. *Relaxed form
elsewhere:* a function longer than one screen needs a stated reason in a comment — a `switch` with
one short arm per protocol opcode is the usual honest one. This is SKILL.md ZS-CORE-21; the full
standard is here.

The shape TigerStyle asks for is the **inverse of an hourglass**: a few parameters, a simple return
type, and a lot of meaty logic between the braces. Wide in the middle, narrow at both ends. A
function with nine parameters and three lines of body is the hourglass the right way up, and it is a
sign the caller is doing the work.

Two rules of thumb do most of the cutting:

- **Centralize control flow.** All the `if`s and `switch`es belong to *one* function, the parent;
  the helpers should not care about control flow at all. That is ZS-ERR-25, "push `if`s up and
  `for`s down".
- **Centralize state manipulation.** The parent keeps the relevant state in its own locals and calls
  helpers to *compute* what should change, rather than letting the helper apply the change. Leaf
  functions stay pure, which is what makes them testable in isolation and assertable at both ends
  (`references/assertions-and-limits.md` ZS-ASRT-18).

**Why:** there is a sharp discontinuity between a function that fits on a screen and one you must
scroll to measure. Below the fold you can check "is every case handled?" by looking; above it you
are reconstructing the function from memory, which is where the missed branch lives. The limit is a
forcing function, not an aesthetic: the split that gets you under 70 lines is nearly always the
split that names a concept you had not named.

```zig
// verified — GOOD
const std = @import("std");
const assert = std.debug.assert;

const Frame = struct { kind: u8, payload: []const u8 };
const Counters = struct { data: u64 = 0, control: u64 = 0 };

// Leaf: no parameters beyond the data, no branches, nothing to trace.
fn checksum(payload: []const u8) u32 {
    var sum: u32 = 0;
    for (payload) |byte| sum = sum *% 31 +% byte;
    return sum;
}

// Parent: few parameters, simple return type, and all the control flow.
fn account(frames: []const Frame, counters: *Counters) u32 {
    assert(frames.len > 0);
    var last: u32 = 0;
    for (frames) |frame| {
        switch (frame.kind) {
            0 => counters.control += 1,
            else => counters.data += frame.payload.len,
        }
        last = checksum(frame.payload);
    }
    return last;
}
```

**Check:** any function whose closing brace you cannot see from its signature, and any signature
with more than four parameters that is not a constructor. Mechanically, over a file whose functions
all start in column 0:

```sh
awk '/^(pub )?fn /{s = NR; n = $0}
     /^}$/{if (s && NR - s > 70) print FILENAME":"s"  "NR - s" lines  "n; s = 0}'
```

### ZS-ERR-35 [S] Report position and context through a `*Diagnostics`, not the error set

An error set says *what kind* of thing went wrong; it cannot say *where*. When a user has to fix the
input — a config file, a query, a source file — pair a coarse error set with an optional
`*Diagnostics` out-parameter that the callee fills in on the failure path. This is the pattern std
itself uses: `std.json.Diagnostics` (`getLine`, `getColumn`, `getByteOffset`), `std.zon.parse`'s
`diag: ?*Diagnostics`, `std.tar` and `std.zip`'s `diagnostics: ?*Diagnostics = null` option fields.

Make the parameter optional and default it to `null`, so the fast path pays nothing and callers that
only need to know *whether* it failed do not have to declare a variable.

**Why:** the alternatives are all worse. Encoding the position in the error set is impossible —
error values carry no payload in Zig, so `error.InvalidCharacterAtLine12` does not exist and cannot.
Making every parse function allocate and return a formatted message forces an allocator into a
signature that did not need one, and forces a `[]const u8` lifetime question on every caller.
Logging from the library takes the decision away from the application (ZS-ERR-03, ZS-ERR-32). The
out-parameter leaves the error set small and exhaustively switchable (ZS-ERR-09) while still
allowing "line 12, col 3".

```zig
// verified — GOOD: ZS-ERR-04's `parseDecimal`, now able to point at the byte
const std = @import("std");
const assert = std.debug.assert;

pub const ParseError = error{ InvalidCharacter, Overflow };

/// Position and context for the most recent `ParseError`. Untouched on success.
pub const Diagnostics = struct {
    line: u32 = 1,
    column: u32 = 1,
    byte: u8 = 0,
};

pub fn parseDecimal(text: []const u8, diag: ?*Diagnostics) ParseError!u32 {
    assert(text.len > 0);
    var value: u32 = 0;
    for (text, 0..) |c, i| {
        if (c < '0' or c > '9') {
            if (diag) |d| d.* = .{ .column = @intCast(i + 1), .byte = c };
            return error.InvalidCharacter;
        }
        value = std.math.mul(u32, value, 10) catch return error.Overflow;
        value = std.math.add(u32, value, c - '0') catch return error.Overflow;
    }
    return value;
}

test "diagnostics carry the position the error set cannot" {
    var diag: Diagnostics = .{};
    try std.testing.expectError(error.InvalidCharacter, parseDecimal("12x4", &diag));
    try std.testing.expectEqual(3, diag.column);
    try std.testing.expectEqual('x', diag.byte);
    try std.testing.expectEqual(1234, try parseDecimal("1234", null));
}
```

The application then renders it — `"{s}:{d}:{d}: {t}"` with `{t}` for the error name (see
`references/formatting-and-output.md` ZS-FMT-05). Give `Diagnostics` a `format` method when the
rendering is fixed, as `std.zon.parse.Diagnostics` does.

**Check:** an error set with members like `InvalidCharacterInHeader` or `BadFieldAtLine`, or a parse
function taking an `Allocator` used only to build an error string. Both are a `*Diagnostics` written
the wrong way.

### ZS-ERR-36 [S] Capture a stack trace with `captureCurrentStackTrace` into a caller-owned buffer

To record where you are *without* aborting — a leak tracker, an audit log, a "who called this" probe
— use `std.debug.captureCurrentStackTrace(options: StackUnwindOptions, addr_buf: []usize)
StackTrace`. It writes return addresses into `addr_buf`, which you own and which must outlive the
returned `StackTrace`. To print instead of capture, `dumpCurrentStackTrace(options)` or
`writeCurrentStackTrace(options, t)`; to print one you captured earlier, `dumpStackTrace(&st)` or
`writeStackTrace(&st, t)`.

`StackUnwindOptions` is `{ first_address: ?usize = null, context: ?CpuContextPtr = null,
allow_unsafe_unwind: bool = false }`. Pass `.{ .first_address = @returnAddress() }` to drop your own
frame from the trace — that is what `dumpCurrentStackTrace` does internally.

**Why:** these are the 0.16 spellings and they are easy to get wrong from memory.
`std.debug.StackIterator` is **no longer `pub`** in 0.16 (`std/debug.zig:895` declares it plain
`const`), so hand-rolled unwinding loops from older code no longer compile —
`captureCurrentStackTrace` is the supported replacement. And `std.debug.StackTrace` (`{
return_addresses, skipped }`) is a *different type* from the `std.builtin.StackTrace` (`{ index,
instruction_addresses }`) that `@errorReturnTrace()` returns; mixing the two families is the usual
compile error (ZS-ERR-17).

```zig
// fragment — GOOD
fn captureHere(addr_buf: []usize) std.debug.StackTrace {
    // `first_address` drops this frame, so the trace starts at our caller.
    return std.debug.captureCurrentStackTrace(.{ .first_address = @returnAddress() }, addr_buf);
}
```

Two costs to budget for. `std.options.allow_stack_tracing` gates the whole family: when it is false
every capture returns an empty trace, so a capture-based diagnostic silently produces nothing.
Unwinding is also not cheap — it is a debug-path tool, so keep it off the hot path and behind the
same `verify`-style constant as an O(N) assertion (`references/assertions-and-limits.md`
ZS-ASRT-20).

**Check:** any surviving `std.debug.StackIterator`, `.dumpStackTrace(@errorReturnTrace())`, or a
`dumpCurrentStackTrace(start_addr)` call passing a bare `?usize` — the 0.15 signature.

## Uniformity of failure and control flow

### ZS-ERR-37 [M] Give the members of one error set a uniform shape

Members of one error set describe failures at one level of detail. Do not mix
`error.InvalidByteAtOffset` with a bare `error.Bad` in the same set, and do not let one call site
carry rich diagnostics through a side channel while its siblings carry none.

**Why:** the caller writes one `switch` over the set, and asymmetric members make that switch
asymmetric — some arms can report a position, some cannot, so the reporting code grows special cases
for the deficient members. Uniform shape is what lets one function render every failure.

**Check:** tabulate the set's members against the diagnostic context each one can supply. A column
populated for most members and empty for one is either a missing detail or a member that belongs in
a different set.

### ZS-ERR-38 [M] Absorb a special case into the general path, or give it its own type

A branch that exists for one input is not a feature; it is an unfinished generalization. Either
the general path handles it — usually by widening a parameter or adding a tag — or the case differs
enough to deserve its own type and its own function.

**Why:** special-case branches compound. Each is locally cheap and globally expensive, because every
later change must be checked against every branch and nothing records which combinations are
reachable. It also defeats ZS-CORE-17's simple-control-flow requirement one reasonable-looking patch
at a time.

**Check:** for each `if` whose condition names a specific input — a particular length, an empty
slice treated unlike others, a sentinel value — ask what the general case would need to be for the
branch to disappear. That is usually the correct design.
