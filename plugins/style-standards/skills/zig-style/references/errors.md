# Errors, control flow, assertions vs errors vs panics

Scope: how a Zig 0.17 function reports failure (error sets, optionals, assertions, panics), how a
caller consumes it (`try`, `catch`, `errdefer`, error return traces, `*Diagnostics` out-parameters),
and the shape of the control flow in between (conditions, loops, `switch`, labeled constructs,
`@branchHint`, and the 70-line function limit).

This chapter does not own assertion *density* or the design of bounded limits — those are
ZS-ASSERT-09 and ZS-ASSERT-23. Allocator ownership and OOM lifetimes are `references/memory.md`;
`std.Io` stream errors and cancellation are `references/concurrency.md`; error-name formatting with
`{t}` is ZS-OUT-05. It cites them.

Blocks that do not declare their own imports assume a file opening with
`const std = @import("std");` and `const assert = std.debug.assert;`.

## Contents

- **1. The decision table: error vs assert vs panic vs unreachable vs optional**
  - ZS-ERR-01 [M] Classify a failure as a programmer error or an operating condition first
  - ZS-ERR-02 [M] A library never panics, never exits, never prints
- **2. Error sets**
  - ZS-ERR-03 [M] Name the error set of every public function; infer only for private helpers
  - ZS-ERR-04 [S] Compose sets with `||`; name a composed set after the verb it belongs to
  - ZS-ERR-05 [M] Never put `anyerror` in a public signature
  - ZS-ERR-06 [S] Use `error{}!T` to state that a path cannot fail
- **3. `try`, `catch`, and `catch unreachable`**
  - ZS-ERR-07 [M] Make `try` the default, and take every other form from this table
  - ZS-ERR-08 [M] Switch on the captured error, and omit `else` when the set is explicit
  - ZS-ERR-09 [M!] Keep `catch unreachable` off every runtime path
  - ZS-ERR-10 [M] Every error is handled somewhere; `catch {}` needs a justification comment
- **4. `defer` and `errdefer`**
  - ZS-ERR-11 [M] Order `defer`/`errdefer` so LIFO teardown cannot outrun what a handler reads
  - ZS-ERR-12 [M] Stop the `errdefer` at the point ownership transfers
  - ZS-ERR-13 [M] A `defer` in a loop body runs each iteration, not at function exit
  - ZS-ERR-14 [S] Log the unwinding error in the caller's `catch`; keep `errdefer` uniform
- **5. Error return traces**
  - ZS-ERR-15 [M] Propagate with `try` or `return err`; never launder an error through an optional
- **6. Simple, explicit control flow (TigerStyle)**
  - ZS-ERR-16 [M] Split compound conditions into separate checks
  - ZS-ERR-17 [S] Prefer a `switch` to an `else if` chain; if you flatten chains into trees, say why
  - ZS-ERR-18 [M] State invariants positively when an `if`/`else` splits the input space
  - ZS-ERR-19 [S] An `if` with no `else` over a validated domain carries a comment or an assertion
  - ZS-ERR-20 [M] Braces, unless the whole statement fits on one line
  - ZS-ERR-21 [M!] No recursion; where recursion is allowed, bound the depth explicitly
  - ZS-ERR-22 [M!] Push `if`s up and `for`s down
- **7. Modern Zig control flow the standard prefers**
  - ZS-ERR-23 [S] Use labeled `switch` with `continue :label` for state machines and dispatch loops
  - ZS-ERR-24 [S] Use a labeled block to compute a value that needs statements
  - ZS-ERR-25 [M] Switch exhaustively with no `else`; use `_` on non-exhaustive enums
  - ZS-ERR-26 [M] Unwrap optionals with `orelse` or a capture, never with `.?`
  - ZS-ERR-27 [S] Mark cold and likely paths with `@branchHint`
- **8. Logging**
  - ZS-ERR-28 [M] A library logs through a scoped `std.log` namespace
  - ZS-ERR-29 [S] Use std's four log levels, configured from the root file
- **9. Function shape, user-facing diagnostics, and stack traces**
  - ZS-ERR-30 [M!] Hard limit of 70 lines per function
  - ZS-ERR-31 [S] Report position and context through a `*Diagnostics`, not the error set
  - ZS-ERR-32 [S] Capture a stack trace with `captureCurrentStackTrace` into a caller-owned buffer
- **Uniformity of failure and control flow**
  - ZS-ERR-33 [M] Give the members of one error set a uniform shape
  - ZS-ERR-34 [M] Absorb a special case into the general path, or give it its own type
- Decided by tools

---

## 1. The decision table: error vs assert vs panic vs unreachable vs optional

### ZS-ERR-01 [M] Classify a failure as a programmer error or an operating condition first

TigerStyle's framing is the whole design: **assertions detect programmer errors, which are
unexpected and whose only correct handling is to crash; errors are operating conditions, which are
expected and must be handled.** Pick the mechanism from the classification, not from convenience.

The test is who can violate the condition. If anything outside your process can — a peer, a file, a
user, the network, the disk — it is an operating condition and an error union. If only your own code
being wrong can, it is an assertion. An assertion that fires on hostile input is a remote denial of
service, and in a `fast` build a remote memory-safety bug (ZS-ASSERT-03).

**Why:** the two have opposite correct responses. After a violated precondition the program's model
of itself is wrong, and continuing corrupts more state; a failed `open()` means the *world* did not
cooperate, and crashing there turns a recoverable situation into an outage.

**Check:** an `assert` on a value that arrived from a socket or file read, `argv`, an environment
variable, or a `pub` parse entry point — anything the process did not compute itself — is an
operating condition asserted. And the mirror image: an error set member named `Invariant*`,
`Corrupt*`, `Impossible*`, or `ShouldNotHappen` returned from a private helper — a programmer error
returned.

| Situation | Mechanism | Notes |
|---|---|---|
| Caller violated a documented precondition (index out of range, unsorted input to a binary search) | `assert(cond)` | Programmer error. `std.debug.assert` is literally `if (!ok) unreachable;` — same UB rules. |
| A state the program's own invariants make impossible (a tag that cannot occur; a `switch` arm the type system cannot rule out) | `unreachable` | Safety-checked panic in `debug`/`safe` builds, **illegal behavior** in `fast`/`small` builds. |
| A relationship between compile-time constants or type sizes | `comptime assert(cond)` / `@compileError` | Fails before the program runs. Always cheaper than a runtime check. |
| The environment failed: I/O, OOM, parse failure, network, permission, malformed input from outside | **return an error** | Operating condition. Expected. Must be handled by someone. |
| A value is legitimately absent, and absence is not a failure (cache miss, "no such key") | **return an optional `?T`** | An error union here forces callers to write `catch` for a non-event. |
| A library cannot continue | **return an error** | Never `@panic`, never `std.process.exit`. See ZS-ERR-02. |
| An application's top level cannot continue | `std.process.fatal(fmt, args)` | `= std.log.err(fmt, args); exit(1);` (the body of `std.process.fatal`). The right CLI failure primitive. It takes exactly two parameters, `(comptime format: []const u8, format_arguments: anytype)`; TigerBeetle's `fatal` with a leading `reason` enum is a project-local helper. |
| An application aborts with a fixed message | `@panic("literal")` | What std does: 352 `@panic(` sites vs only 7 `std.debug.panic(`. |
| An application aborts and the message needs formatting | `std.debug.panic(fmt, args)` | Or `std.debug.panicExtra(ret_addr, fmt, args)` to control the first trace frame. |
| A build script cannot continue | `catch @panic("OOM")` | Sanctioned **only** in `build.zig`; all 174 `@panic("OOM")` sites in std are under `Build.zig`. |
| A check inside a `test` block | `std.testing.expect*` | std's own doc: `assert` may not detect a test failure in `fast`/`small` builds. |

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

Both mechanisms meet at a boundary. With `Header`, `HeaderInvalid` and `readBlock` from
ZS-ASSERT-16, and `message_size_bytes_max` from ZS-ASSERT-21:

```zig
// fragment — BAD
fn messageParse(bytes: []const u8) HeaderInvalid!Header {
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

### ZS-ERR-02 [M] A library never panics, never exits, never prints

A reusable module returns errors. This governs *operating* errors: a library must never convert a
recoverable condition into a process abort. `@panic`, `std.process.exit`, `std.process.fatal`,
`std.debug.print`, and writing to stderr are all reserved for the application's top level (`main`)
or for `build.zig`. Output follows the same split: a library renders into the caller's
`w: *Io.Writer`, returning `Io.Writer.Error!void`, or returns an owned `[]u8` the caller frees. It
never opens stdout, and never decides where its output goes.

It does **not** govern assertions. A violated internal invariant has exactly one correct response in
any code, library or not, so `assert` and a project-local always-on `assertAlways` (ZS-ASSERT-05)
are legal in a library — including in allocators and crypto, which are libraries by construction.
What a library may not do is choose its consumer's optimize mode: document which invariants it
asserts and what it costs to run it in a `safe` build, and let the consumer decide (ZS-BUILD-24).

**Why:** a library does not know whether its caller can recover. Aborting the process removes the
caller's ability to retry, degrade, or report, and makes the library untestable — a test cannot
assert on a process that has already exited.

**Check:** in a non-`main`, non-`build.zig` file, grep for `@panic(`, `process.exit`,
`process.fatal`, `debug.print`, `.stdout()`, and `.stderr()`. `assert(`, `unreachable`, and
`assertAlways(` are not hits. The milder form is a `pub fn` that renders a value and returns `void`
without taking a `w: *Io.Writer`.

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

### ZS-ERR-03 [M] Name the error set of every public function; infer only for private helpers

`pub` functions declare `SomeError!T` (or an alias such as `Allocator.Error`, `Io.Writer.Error`,
`Io.Cancelable`). Bare `!T` is for private/internal helpers, `main`, and tests.

std is **not** a model here, and pretending otherwise weakens the rule. Counted over single-line
signatures at 0.17.0, outside the generated `zig/parser_generated_oracle.zig`
(`rg 'pub fn \w+\([^)\n]*\) !' -g '*.zig'` for bare; swap the trailing `!` for
`[A-Za-z][A-Za-z0-9_.()]*!` for named), 1189 `pub fn` declare a named set but **407 still return a
bare `!`** — `priority_queue`'s `ensureTotalCapacity` and `pushSlice` among them, though the
flagship containers are clean: every `ArrayList`/`HashMap` `ensureTotalCapacity` returns
`Allocator.Error!void` or `Oom!void` (non-`pub` helpers add another 475 bare). This standard takes
the strict side of that 3:1 split, because the quarter that infer are exactly the ones whose sets
can widen under a caller without warning.

**Why:** an inferred error set is part of your ABI that nobody can read. One `try` added to a
private callee three levels down silently widens a public signature, and every downstream exhaustive
`catch |e| switch (e)` breaks — in someone else's repo.

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
        const digit = try std.fmt.charToDigit(c, 10);
        value = try std.math.mul(u32, value, 10);
        value = try std.math.add(u32, value, digit);
    }
    return value;
}
```

`std.math.mul` and `std.math.add` return `error{Overflow}!u32`, a subset of `ParseError`, so `try`
passes the error up with its trace; a `catch return error.Overflow` would re-raise the same error
and restart the trace (ZS-ERR-15).

### ZS-ERR-04 [S] Compose sets with `||`; name a composed set after the verb it belongs to

std's convention across 194 named sets is `pub const <Verb>Error = error{…}` declared next to the
function, merging in reusable sets with `||`.

**Why:** the merge operator keeps one authoritative definition per concern. Re-listing
`error{OutOfMemory}` in fifteen places means the sixteenth will disagree.

**Check:** the same `error{…}` member list spelled out in two places instead of one named set merged
with `||`; and a named set whose identifier does not end in `Error` or is not named after the verb
whose function returns it.

```zig
// verified — GOOD
const std = @import("std");

pub const ParseError = error{ InvalidCharacter, Overflow };
pub const ReadError = error{ EndOfStream, ConnectionResetByPeer };
pub const LoadError = ParseError || ReadError || std.mem.Allocator.Error; // 5 members
```

Give individual members `///` docs when the condition is not obvious from the name — std does this
heavily for platform-specific members. A one-member set is written inline, not hoisted:
`pub const Error = error{OutOfMemory};` (`std.mem.Allocator.Error`).

### ZS-ERR-05 [M] Never put `anyerror` in a public signature

std has 43 occurrences of `anyerror` in 456 KLOC, and the one notable public use is
`testing.expectError(expected_error: anyerror, …)`.

**Why:** `anyerror` is the set of every error in the program, so no caller can ever write an
exhaustive `switch`, and `@typeInfo(anyerror).error_set` is `null` rather than a member list. It
also defeats error-set–based optimisation.

**Check:** grep `anyerror` — every hit in a `pub fn` signature, a `pub const` type alias, or a
public struct field is the finding. `anyerror` inside a test body or a private helper is not.

### ZS-ERR-06 [S] Use `error{}!T` to state that a path cannot fail

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

### ZS-ERR-07 [M] Make `try` the default, and take every other form from this table

| Form | Use when |
|---|---|
| `try f()` | The caller is better placed to decide. This is the default and should dominate. |
| `f() catch \|e\| switch (e) { … }` | You can meaningfully handle *some* variants here. |
| `f() catch \|e\| { log.err("…: {t}", .{e}); return e; }` | Add context, then propagate. `{t}` prints the error name. |
| `f() catch default_value` | The operation is genuinely optional and the default is correct. |
| `f() catch blk: { …; break :blk fallback; }` | The fallback needs real logic to compute. |
| `f() catch unreachable` | Only with a written proof. See ZS-ERR-09. |
| `f() catch @panic("msg")`, `catch std.process.fatal(…)` | Application top level only. Never in a library. |
| `f() catch {}` | Almost never. See ZS-ERR-10. |

**Why:** `try` is the only form that preserves the error return trace *and* forces the decision
upward to code that has the context to make it. Each `catch` is a place where information about the
failure stops travelling.

**Check:** in a diff, `try` should outnumber `catch`, and every `catch` should be one of the forms
in the table. The comment a `catch unreachable` or a `catch {}` owes is judged by ZS-ERR-09 and
ZS-ERR-10.

### ZS-ERR-08 [M] Switch on the captured error, and omit `else` when the set is explicit

`catch |err| switch (err)` with one prong per member and **no** `else`. Add `else => |e| return e`
only when the set is inferred, is `anyerror`, or genuinely comes from a third party.

**Why:** an exhaustive switch on an explicit set turns "upstream added a new error" into a compile
error at exactly the site that must decide what to do about it. An `else` prong turns the same event
into a silent behavior change. This is std's dominant shape: 552 `catch |err| switch (err)` sites.

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
// fragment — GOOD: with `parseDecimal` from ZS-ERR-03 in scope
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

### ZS-ERR-09 [M!] Keep `catch unreachable` off every runtime path

`catch unreachable` claims *this error is impossible given local invariants*. On a runtime path,
return the error instead, or restructure so the fallible call is not on that path; the `comptime`
form exempted below stays legal. *Relaxed form:* a `catch unreachable` carries its one-line proof in
a comment next to it. If you cannot write the proof, you have a bug, not an invariant: the usual
false claim is an OOM or an I/O error that "obviously can't happen" until the machine is under
memory pressure or the disk fills. std's uses each sit next to a buffer whose size is fixed at
compile time.

**Why:** `unreachable` is a safety-checked panic in `debug`/`safe` builds and **illegal behavior**
in `fast`/`small` builds. A wrong `catch unreachable` therefore does not crash in production — it
miscompiles the surrounding code.

```zig
// fragment — BAD: allocation can always fail
const copy = gpa.dupe(u8, name) catch unreachable;
```

```zig
// verified — GOOD
const std = @import("std");

/// Renders `code` into the caller's `buffer`, which outlives the slice.
fn formatCode(buffer: *[3]u8, code: u8) []const u8 {
    // A u8 renders in at most 3 decimal digits and `buffer` holds 3, so
    // `std.mem.print` cannot fail here.
    return std.mem.print(buffer, "{d}", .{code}) catch unreachable;
}

test formatCode {
    var buffer: [3]u8 = undefined;
    try std.testing.expectEqualStrings("255", formatCode(&buffer, 255));
}
```

**Exempt: `comptime`-evaluated `catch unreachable`.** In a `const` initializer or a `comptime` block
the expression is folded by the compiler, so a failure is
`error: caught unexpected error 'Overflow'` at build time and can never be illegal behavior at
runtime — there is nothing to prove and no comment is required. This is why a derived limit
(ZS-ASSERT-21/ZS-ASSERT-22) whose derivation has a fallible `std.math` step is written without one:

```zig
// fragment — GOOD: comptime-evaluated, so failure is a compile error
pub const blocks_total_max: u32 =
    std.math.mul(u32, blocks_per_message_max, messages_max) catch unreachable;
```

**Check:** every runtime `catch unreachable` has a comment on the same or the preceding line naming
the fixed bound that makes failure impossible. The short spelling `.?` has no proof form at all —
ZS-ERR-26 forbids it outright.

### ZS-ERR-10 [M] Every error is handled somewhere; `catch {}` needs a justification comment

No dropped errors. `catch {}` and `_ = f() catch {};` are silent discards, and empty `catch` blocks
are the highest-yield thing to grep for in review. Turning the error into `null` or `false` instead
is laundering, which ZS-ERR-15 owns.

**Why:** Yuan et al. (OSDI '14, *Simple Testing Can Prevent Most Critical Failures*) found that 92%
of catastrophic failures in distributed data-intensive systems came from mishandled non-fatal errors
the software had already signalled: detected, then thrown away.

**Check:** `catch {}`, `catch {};`, and `_ = … catch` with no comment on the same or the preceding
line saying why the failure is genuinely not information. A `catch` that logs and continues is a
different rule (ZS-ERR-07) and is not a hit here — but if the call took an `io`, it is a hit under
ZS-CONC-24, which treats log-and-continue as a dropped cancellation.

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
`try` and no `catch` (ZS-CONC-19, ZS-MEM-10).

`deleteFile`'s error set contains `Io.Cancelable`, so the `catch` above also absorbs
`error.Canceled`. That is legal only on a path that is already leaving, a distinction ZS-CONC-24
owns: read it before copying this shape onto a path that continues.

---

## 4. `defer` and `errdefer`

### ZS-ERR-11 [M] Order `defer`/`errdefer` so LIFO teardown cannot outrun what a handler reads

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

### ZS-ERR-12 [M] Stop the `errdefer` at the point ownership transfers

An `errdefer` covers a resource only from its declaration until something else becomes responsible
for freeing it. Once a value is appended to a container that owns its items, or returned to the
caller, the `errdefer` for it must no longer be in scope.

The symptom misleads: `Allocator.free` `@memset`s the bytes to `undefined` *before* calling
`rawFree`, so freeing an item twice faults inside `free`, with a stack trace that points at the
allocator, not at your bug.

**Why:** an `errdefer` that outlives the transfer is a double free on the error path — the container
frees the item during its own cleanup, then the stale `errdefer` frees it again.

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

### ZS-ERR-13 [M] A `defer` in a loop body runs each iteration, not at function exit

If the resource must outlive the loop, hoist the release out and track every instance. If it must
not, keep the `defer` inside the loop body.

**Why:** a function-scope `defer gpa.free(buffer)` paired with an in-loop assignment frees only the
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
        const buffer = try gpa.alloc(u8, n);
        defer gpa.free(buffer); // Per-iteration: correct here.
        total += buffer.len;
    }
    return total;
}
```

```zig
// fragment — BAD: compiles, leaks every buffer but the last
fn sumFilesLeaky(gpa: Allocator, counts: []const usize) Allocator.Error!usize {
    var buffer: []u8 = &.{};
    defer gpa.free(buffer); // Function scope: runs once, on the LAST value.
    var total: usize = 0;
    for (counts) |n| {
        buffer = try gpa.alloc(u8, n);
        total += buffer.len;
    }
    return total;
}
```

### ZS-ERR-14 [S] Log the unwinding error in the caller's `catch`; keep `errdefer` uniform

`errdefer` takes no error capture. To record which error is unwinding, give the fallible body its
own function and log in the caller's `catch |err|`; the `errdefer` that remains releases resources
and branches on nothing.

**Why:** cleanup that depends on *which* error occurred makes the rollback non-uniform, and uniform
rollback is what makes unwinding safe to reason about. With no capture, the split is also the only
place the error can be seen.

**Check:** an `errdefer` body containing an `if` or a `switch`. An `errdefer |err|` is a parse
error; its log moves to the caller's `catch |err|`.

```zig
// verified — GOOD: `errdefer` has no capture, so the log moves to the caller's `catch`
const std = @import("std");
const Allocator = std.mem.Allocator;
const log = std.log.scoped(.doc);

fn openWithLog(gpa: Allocator, n: usize) Allocator.Error![]u8 {
    return openInner(gpa, n) catch |err| {
        log.warn("rollback after {t}", .{err});
        return err;
    };
}

fn openInner(gpa: Allocator, n: usize) Allocator.Error![]u8 {
    const buffer = try gpa.alloc(u8, n);
    errdefer gpa.free(buffer);
    if (n > 8) return error.OutOfMemory;
    return buffer;
}
```

---

## 5. Error return traces

### ZS-ERR-15 [M] Propagate with `try` or `return err`; never launder an error through an optional

`@errorReturnTrace()` returns `?*std.lang.StackTrace`: non-null in `debug` builds, **null** in
`safe`, `fast` and `small` builds unless they are compiled with `-ferror-tracing`. The trace is
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
exactly the `*const std.lang.StackTrace` that `@errorReturnTrace()` yields;
`writeErrorReturnTrace(et, t)` is the same thing against an `Io.Terminal` you supply. Do **not**
reach for `std.debug.dumpStackTrace` here: in 0.17 that takes a `*const std.debug.StackTrace`
(`{ return_addresses: []usize, skipped: SkippedAddresses }`), which is a different type from
`std.lang.StackTrace` (`{ index: usize, instruction_addresses: []usize }`) and will not compile:
`error: expected type '*const debug.StackTrace', found '*lang.StackTrace'`. Capturing a *stack*
trace is ZS-ERR-32.

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

### ZS-ERR-16 [M] Split compound conditions into separate checks

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

Assertions follow the same rule: ZS-ASSERT-10.

### ZS-ERR-17 [S] Prefer a `switch` to an `else if` chain; if you flatten chains into trees, say why

**Honest disagreement.** TigerStyle mandates rewriting `else if` chains into nested
`else { if { } }` trees. Idiomatic Zig and the standard library do not do this — `else if` chains
appear throughout std, and `zig fmt` formats them as chains. The two positions are irreconcilable as
written.

Recommendation, keyed to tiers — `[S]`: when the chain dispatches on one value, convert it to a
`switch`, which buys you exhaustiveness checking that neither `if` form provides. When it dispatches
on unrelated predicates, an `else if` chain is acceptable idiomatic Zig; adopt the nested-tree form
only in a codebase that has adopted TigerStyle wholesale, and be consistent within a file. The
nested tree is a readability preference that buys no compiler check, and since `zig fmt` will not
produce it, mixing both spellings in one file costs more than either convention alone.

**Why:** a `switch` over an enum or tagged union is verified exhaustive at compile time, so adding a
variant breaks the build at every dispatch site (ZS-ERR-25), while an `else if` chain over the same
values compiles and falls through to its last `else` at runtime.

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

### ZS-ERR-18 [M] State invariants positively when an `if`/`else` splits the input space

When an `if`/`else` splits the input space, write the branch condition as the invariant that
*holds*: `if (index < length) { … } else { … }`, not `if (index >= length)`.

**Early-return guards are exempt.** `if (index >= items.len) return null;` states the *rejection*
condition, which is the whole point of a guard, and guards are what ZS-ERR-16 asks for. What is
forbidden is a non-guard `if` whose condition negates an invariant that the same function states
positively elsewhere — the reader then has to hold both spellings of one relation in their head. The
guard form is used by ZS-ERR-20, ZS-ERR-22 and ZS-ASSERT-14.

**Why:** the positive form matches how the same relation is written in the loop condition
(`while (index < length)`) and in the assertion (`assert(index < length)`), so the reader compares
identical expressions instead of mentally negating one. Negations are where off-by-one errors hide.

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

### ZS-ERR-19 [S] An `if` with no `else` over a validated domain carries a comment or an assertion

For every `if` without an `else` where the negative case is a deliberate no-op, write that down: a
one-line comment in the empty half, or an assertion stating what is true when the condition is
false.

**Why:** an `if` with no `else` claims the other half of the input space needs nothing, and silence
cannot tell a decision from an oversight — the negative space of ZS-ASSERT-12. A comment or an
assertion is a claim a reviewer can dispute.

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

### ZS-ERR-20 [M] Braces, unless the whole statement fits on one line

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

Implications in assertions take the same one-line form: ZS-ASSERT-11.

### ZS-ERR-21 [M!] No recursion; where recursion is allowed, bound the depth explicitly

Write the iterative form, with an explicit worklist of fixed size. *Relaxed form:* recursion is
permitted only when the maximum depth is a named constant asserted at entry, or a `comptime`
parameter, which makes the bound a compile-time fact. A recursive descent over attacker-controlled
nesting depth is a remote crash primitive.

**Why:** without recursion the call graph is acyclic, so a bound on stack use can be derived
statically. With it, stack exhaustion is the one failure Zig's safety checks do not catch: a fault
with a truncated trace, or, on a target with no guard page, silent corruption below the stack.

**Check:** a function whose body names itself, or a mutually recursive pair, with no
`comptime depth` parameter and no runtime `depth`/`level` compared against a named `_max` constant.
A tree, JSON, expression, or directory walk written without an explicit worklist is where this
hides.

```zig
// verified — GOOD: an explicit worklist on a fixed buffer; std asserts the room on every push
const std = @import("std");

const Node = struct { left: ?*const Node, right: ?*const Node, value: u32 };
const depth_max = 8;

fn sumIterative(root: *const Node) u32 {
    var buffer: [depth_max]*const Node = undefined;
    var stack: std.ArrayList(*const Node) = .initBuffer(&buffer);
    stack.appendAssumeCapacity(root);

    var total: u32 = 0;
    while (stack.pop()) |node| {
        total += node.value;
        if (node.left) |left| stack.appendAssumeCapacity(left);
        if (node.right) |right| stack.appendAssumeCapacity(right);
    }
    return total;
}

test sumIterative {
    const leaf: Node = .{ .left = null, .right = null, .value = 2 };
    const root: Node = .{ .left = &leaf, .right = &leaf, .value = 1 };
    try std.testing.expectEqual(5, sumIterative(&root));
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

### ZS-ERR-22 [M!] Push `if`s up and `for`s down

Keep branching in the parent function; give leaf helpers primitive arguments and no control flow.
*Relaxed form:* a leaf helper that branches on a condition its caller already knows is a review
comment, not a build failure.

**Why:** it concentrates the decisions in one readable place, and it makes the leaf a straight-line
function that the compiler can vectorise and a reader can check without tracing callers. It is also
the mechanism that keeps parents under the 70-line limit (ZS-ERR-30) without scattering the logic.

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

### ZS-ERR-23 [S] Use labeled `switch` with `continue :label` for state machines and dispatch loops

`sw: switch (initial) { .a => { …; continue :sw next; }, … }` replaces
`while (true) { switch (state) { … } }`. A `continue` targeting a switch **must** carry an operand;
`break :sw` exits, and `break :sw value` yields a value. Per the langref, a comptime-known
`continue` operand lowers to an unconditional branch, which is perfectly predicted, and a
runtime-known one embeds its own conditional branch (ideally a jump table).

**Why:** this is a code-generation construct, not sugar. Each `continue` carries its own branch, so
the CPU predicts each transition independently; a `while`+`switch` loop funnels every transition
through one dispatch point, a bottleneck in the hot loops that use it.

**Check:** a `while (true) { switch (state) { … } }` whose arms all end by assigning `state` — that
is a labeled `switch` written the long way. Separately, an unlabeled `break` or `continue` inside a
labeled construct, which silently targets the innermost loop rather than the labeled one.

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

### ZS-ERR-24 [S] Use a labeled block to compute a value that needs statements

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

### ZS-ERR-25 [M] Switch exhaustively with no `else`; use `_` on non-exhaustive enums

For your own enums and unions, list every prong and do not add `else`. For a non-exhaustive enum —
one with a trailing `_` field — use a `_ =>` prong rather than `else =>`: `_ =>` handles
out-of-range values while *still* erroring if you forget a named tag, whereas `else =>` handles both
and therefore checks neither.

**Why:** exhaustiveness is a design tool. Adding a variant should produce a compile error at every
site that must be updated, which is how you find them all; `else` converts that compile error into a
runtime fallthrough.

**Check:** an `else =>` prong in a `switch` over an enum or tagged union declared in this repo. If
the enum's declaration ends in `_`, the prong should be `_ =>`; if it does not, the prong should not
exist at all.

```zig
// rejected — zig: switch must handle all possibilities
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

### ZS-ERR-26 [M] Unwrap optionals with `orelse` or a capture, never with `.?`

`.?` is `orelse unreachable` in four characters. Where the proof rule (ZS-ERR-09) genuinely licenses
an unreachable, write `orelse unreachable` and write the proof beside it; std does that three times
in 456 KLOC. The short spelling has no licensed use.

Most sites do not need the escape at all. `std.testing.expectEqual` compares optionals, so
`expectEqual(2, find(...))` needs no unwrap; a `callconv(.c)` callback that returns void can take
`orelse return`; a fallible path can take `orelse error.Something`.

**Why:** `.?` on a null is the same trap as `catch unreachable` — a panic in `debug`/`safe`, illegal
behavior in `fast`/`small` — in a form short enough to slip through review. The long spelling is
visible, and it is the one place a proof comment has to go.

**Check:** grep `.?` — every hit is a defect, including inside `comptime` blocks and `const`
initializers. `orelse unreachable` is the spelling that carries a proof, and ZS-ERR-09 governs it.

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

### ZS-ERR-27 [S] Mark cold and likely paths with `@branchHint`

`@branchHint(hint: std.lang.BranchHint) void`. The hints are exactly `.none`, `.likely`,
`.unlikely`, `.cold`, `.unpredictable` (`std.lang.BranchHint`). Where it may stand is the compiler's
(the `'@branchHint' must appear…` row below), so on a cold branch that also asserts (ZS-ASSERT-09),
the hint comes first and the assertion after it.

**Why:** `.cold` lets the optimizer move a branch's code to a different page, keeping the hot path's
instruction cache dense; `.unpredictable` tells it to prefer branchless lowering where a mispredict
would cost more than the extra work.

**Check:** on a hot path a profile names, an error-returning branch or a `catch` block whose first
statement is not `@branchHint(.cold)`; deviating needs only the profile that says the branch is not
hot. And the converse: a `.likely` or `.unlikely` on a branch no profile names. A hint asserts a
distribution, and a wrong one is worse than none.

```zig
// verified — GOOD
fn decodeTag(byte: u8) error{ReservedTag}!u8 {
    if (byte < 0x80) {
        return byte;
    } else {
        @branchHint(.cold);
        return error.ReservedTag;
    }
}
```

---

## 8. Logging

### ZS-ERR-28 [M] A library logs through a scoped `std.log` namespace

`const log = std.log.scoped(.mylib);` at the top of the file, then `log.warn(…)`. One scope per
module, named for the module. std itself logs 29 times in 456 KLOC: the bar is high.

That `std.debug.print` and raw stderr writes are never program output is owned by ZS-CONC-04 and
ZS-CONC-05; that they are never acceptable in a library, by ZS-ERR-02. Program *output* is not
logging: write it to a `*std.Io.Writer` you were handed, and `flush()`.

**Why:** `std.log` routes through `std.options.logFn`, so the *application* decides format,
destination, filtering, and whether a library is audible at all. `log_scope_levels` filters by scope
(ZS-ERR-29); an unscoped log lands in `.default` and cannot be silenced alone.

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

### ZS-ERR-29 [S] Use std's four log levels, configured from the root file

`std.log.Level` is `{ err, warn, info, debug }`, documented as: `err` — something has gone wrong;
`warn` — uncertain whether something has gone wrong, but worth investigating; `info` — general
state; `debug` — only useful when debugging. `std.log.default_level` is `.debug` in `debug` builds
and `.info` in `safe`, `fast` and `small` builds.

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

Log *or* return, not both, unless you are adding context and re-propagating (ZS-ERR-07). In tests,
`std.testing.log_level` defaults to `.warn`.

---

## 9. Function shape, user-facing diagnostics, and stack traces

### ZS-ERR-30 [M!] Hard limit of 70 lines per function

70 lines between the braces is a hard ceiling, counted as written, blank lines and comments
included. *Relaxed form:* a function longer than one screen needs a stated reason in a comment — a
`switch` with one short arm per protocol opcode is the usual honest one.

Where to cut is what the shape rules decide: the control flow stays in the parent (ZS-ERR-22), so
does the state it manipulates (ZS-PERF-12), and each piece comes out narrow at both ends and wide
inside (ZS-PERF-13).

**Why:** a function that fits on a screen can be checked for "is every case handled?" by looking;
one you must scroll is reconstructed from memory, which is where the missed branch lives. The split
that gets you under 70 lines nearly always names a concept you had not named.

**Check:** any function whose closing brace you cannot see from its signature. Mechanically, over a
file whose functions all start in column 0:

```sh
awk '/^(pub )?fn /{s = NR; n = $0}
     /^}$/{if (s && NR - s > 70) print FILENAME":"s"  "NR - s" lines  "n; s = 0}'
```

### ZS-ERR-31 [S] Report position and context through a `*Diagnostics`, not the error set

An error set says *what kind* of thing went wrong; it cannot say *where*. When a user has to fix the
input — a config file, a query, a source file — pair a coarse error set with an optional
`*Diagnostics` out-parameter that the callee fills in on the failure path. This is the pattern std
itself uses: `std.json.Diagnostics` (`getLine`, `getColumn`, `getByteOffset`), and `std.tar` and
`std.zip`'s `diagnostics: ?*Diagnostics = null` option fields. `std.zon.parse` is the exception
since 0.17: its `Options` make `diagnostics: *Diagnostics` required, filled into the parse's arena.

Make the parameter optional and default it to `null`, so the fast path pays nothing and callers that
only need to know *whether* it failed do not have to declare a variable.

The other alternatives are worse. A parse function that allocates and returns a formatted message
forces an allocator into a signature that did not need one, and a `[]const u8` lifetime question on
every caller; logging from the library takes the decision away from the application (ZS-ERR-02,
ZS-ERR-28).

**Why:** the out-parameter leaves the error set small and exhaustively switchable (ZS-ERR-08) while
still allowing "line 12, col 3", which the set cannot carry: Zig error values have no payload, so
`error.InvalidCharacterAtLine12` does not exist and cannot.

```zig
// verified — GOOD: ZS-ERR-03's `parseDecimal`, now able to point at the byte
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
        value = try std.math.mul(u32, value, 10);
        value = try std.math.add(u32, value, c - '0');
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
ZS-OUT-05). Give `Diagnostics` a rendering method when the rendering is fixed, as
`std.zon.parse.Diagnostics` does: its `fmt(path)` returns a value printed with `{f}`, and
`log(path)` and `fatal(path)` print it for you.

**Check:** an error set with members like `InvalidCharacterInHeader` or `BadFieldAtLine`, or a parse
function taking an `Allocator` used only to build an error string. Both are a `*Diagnostics` written
the wrong way.

### ZS-ERR-32 [S] Capture a stack trace with `captureCurrentStackTrace` into a caller-owned buffer

To record where you are *without* aborting — a leak tracker, an audit log, a "who called this" probe
— use
`std.debug.captureCurrentStackTrace(options: StackUnwindOptions, addr_buf: []usize) StackTrace`. It
writes return addresses into `addr_buf`, which you own and which must outlive the returned
`StackTrace`. To print instead of capture, `dumpCurrentStackTrace(options)` or
`writeCurrentStackTrace(options, t)`; to print one you captured earlier, `dumpStackTrace(&st)` or
`writeStackTrace(&st, t)`.

`StackUnwindOptions` is
`{ first_address: ?usize = null, context: ?CpuContextPtr = null, allow_unsafe_unwind: bool = false }`.
Pass `.{ .first_address = @returnAddress() }` to drop your own frame from the trace — that is what
`dumpCurrentStackTrace` does internally.

`std.debug.StackIterator` is **not `pub`** (`std/debug.zig` declares it plain `const`), so a
hand-rolled unwinding loop does not compile; `captureCurrentStackTrace` is the supported way. And
`std.debug.StackTrace` (`{ return_addresses, skipped }`) is a *different type* from the
`std.lang.StackTrace` (`{ index, instruction_addresses }`) that `@errorReturnTrace()` returns;
mixing the two families is the usual compile error (ZS-ERR-15).

**Why:** this family is easy to get wrong from memory: older code reaches for an iterator that is
private, and for a trace type that is not the one an error return trace uses.

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
same `verify`-style constant as an O(N) assertion (ZS-ASSERT-17).

**Check:** any surviving `std.debug.StackIterator`, `.dumpStackTrace(@errorReturnTrace())`, or a
`dumpCurrentStackTrace(start_addr)` call passing a bare `?usize` where it takes
`StackUnwindOptions`.

## Uniformity of failure and control flow

### ZS-ERR-33 [M] Give the members of one error set a uniform shape

Members of one error set describe failures at one level of detail. Do not mix
`error.InvalidByteAtOffset` with a bare `error.Bad` in the same set, and do not let one call site
carry rich diagnostics through a side channel while its siblings carry none.

**Why:** the caller writes one `switch` over the set, and asymmetric members make that switch
asymmetric — some arms can report a position, some cannot, so the reporting code grows special cases
for the deficient members. Uniform shape is what lets one function render every failure.

**Check:** tabulate the set's members against the diagnostic context each one can supply. A column
populated for most members and empty for one is either a missing detail or a member that belongs in
a different set.

### ZS-ERR-34 [M] Absorb a special case into the general path, or give it its own type

A branch that exists for one input is not a feature; it is an unfinished generalization. Either the
general path handles it — usually by widening a parameter or adding a tag — or the case differs
enough to deserve its own type and its own function.

**Why:** special-case branches compound. Each is locally cheap and globally expensive: every later
change must be checked against every branch, nothing records which combinations are reachable, and
ZS-ERR-16's simple control flow erodes one plausible patch at a time.

**Check:** for each `if` whose condition names a specific input — a particular length, an empty
slice treated unlike others, a sentinel value — ask what the general case would need to be for the
branch to disappear. That is usually the correct design.

## Decided by tools

The compiler rejects each of these on its own; no setting turns one off.

| Tool | Lint | Level | Forbids |
|---|---|---|---|
| zig | `error … of type … is ignored` | error | a call that can fail, without `try`, `catch` or `if` |
| zig | `error union is discarded` | error | `_ = f();` on a call that can fail |
| zig | `value of type … ignored` | error | a non-void result neither used nor discarded |
| zig | `expected error union type, found …` | error | `try` or `catch` on a call that cannot fail |
| zig | `expected optional type, found …` | error | `orelse` on a value that is not optional |
| zig | `operator == not allowed for type …` | error | comparing an error union with a value before unwrapping it |
| zig | `duplicate switch value …` | error | two prongs for one value |
| zig | `'try' not allowed inside defer expression` | error | `try` in a `defer`, which has nowhere to return the error |
| zig | `cannot return from defer expression` | error | `return` inside a `defer` |
| zig | `unreachable code` | error | a statement after `return`, `break` or another diverging one |
| zig | `'@branchHint' must appear as the first statement in a function or conditional branch` | error | a `@branchHint` after another statement of its branch |
