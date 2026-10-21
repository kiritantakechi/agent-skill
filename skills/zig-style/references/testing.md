# Tests, fuzzing, and deterministic simulation

Scope: how tests are written, named, located, and wired into `build.zig`; the `std.testing` surface
in Zig 0.17 (`testing.allocator`, `testing.io`, the `expect*` family, `tmpDir`,
`checkAllAllocationFailures`); coverage-guided fuzzing with `std.testing.fuzz` and
`std.testing.Smith`; and the discipline layer — negative-space testing, seeded determinism,
model-based swarm tests, deterministic simulation, and snapshot tests. Assertions in production code
live in the assertions chapter; allocator selection and lifetime rules live in the memory chapter;
`Io.Reader`/`Io.Writer` mechanics live in the std.Io chapter; the general `build.zig` shape lives in
the build chapter (only test-step wiring appears here).

Every snippet assumes the preamble `const std = @import("std");`, and `...` stands for the body
the rule is not about.
## Contents

- **Part 1 — Where tests live and what they are called**
  - ZS-TEST-01 [M] Put unit tests at the bottom of the file that contains the code under test
  - ZS-TEST-02 [M] Use the decltest form `test declName` when a test targets exactly one declaration
  - ZS-TEST-03 [S] Name string tests after the behavior and the precondition (see ZS-TEST-02)
  - ZS-TEST-04 [M] Every source file must be reachable from a test binary (see ZS-BUILD-18)
- **Part 2 — Writing a unit test**
  - ZS-TEST-05 [M] Allocate from `std.testing.allocator`; a leak fails the run
  - ZS-TEST-06 [M] Call `expectEqual(expected, actual)` in that order, and drop the `@as` wrapper
  - ZS-TEST-07 [M] Never compare slice or string *contents* with `expectEqual`
  - ZS-TEST-08 [M] Use the narrowest matcher `std.testing` offers, and never `assert` inside a test
  - ZS-TEST-09 [M] Tests that perform I/O must use `std.testing.io`
  - ZS-TEST-10 [M] Filesystem tests use `testing.tmpDir(.{})` with `defer tmp.cleanup()`
  - ZS-TEST-11 [M] A passing test writes nothing to stderr; diagnostics go in `errdefer`
- **Part 3 — Negative space and allocation failure**
  - ZS-TEST-12 [M!] Test the negative space, not just the happy path
  - ZS-TEST-13 [M!] Every allocating API gets a `checkAllAllocationFailures` test
  - ZS-TEST-14 [S] Use `failing_allocator` or `FailingAllocator` for one targeted OOM path
- **Part 4 — Randomised, model-based, and simulation testing**
  - ZS-TEST-15 [M] Seed randomised tests from `std.testing.random_seed`; print the seed on failure
  - ZS-TEST-16 [M] A seeded test must be a pure function of its seed
  - ZS-TEST-17 [S] Give every container and state machine a model-based swarm test
  - ZS-TEST-18 [M!] Test stateful systems by deterministic simulation with injected faults
  - ZS-TEST-19 [S] Snapshot-test complex output against an inline multiline literal
- **Part 5 — Fuzzing with `Smith`**
  - ZS-TEST-20 [M] Write fuzz targets with `std.testing.fuzz` and `*std.testing.Smith`
  - ZS-TEST-21 [M] Pin every fuzz-found failure into the target's `.corpus`
  - ZS-TEST-22 [M] Never ask `Smith` for a type without a fixed bit size
  - ZS-TEST-23 [S] Steer `Smith` with ranges and weights instead of generating-then-rejecting
- **Part 6 — Running and maintaining the suite**
  - ZS-TEST-24 [M] `refAllDecls` is a compile smoke test, not coverage
  - ZS-TEST-25 [S] `error.SkipZigTest` marks inapplicable tests, never known-failing ones
  - ZS-TEST-26 [S] Set `std.testing.log_level` only around the test that needs it, and restore it
  - ZS-TEST-27 [M] Run the whole suite in `safe` as well as `debug`
  - ZS-TEST-28 [M] Every bug fix ships with the test that would have caught it
  - ZS-TEST-29 [S] Keep unit, integration, and fuzz targets in their proper places (see ZS-BUILD-05)

---

## Part 1 — Where tests live and what they are called

### ZS-TEST-01 [M] Put unit tests at the bottom of the file that contains the code under test
A unit `test` block belongs in the same file as the declaration it exercises, below the
implementation — never shadowed into a parallel `tests/` tree that mirrors `src/` file for file.
This is a rule about unit tests only: **integration tests live outside `src/`** in their own
directory, with their own `addTest` and their own build step (ZS-BUILD-20, ZS-BUILD-05), because
their whole purpose is to exercise the published module surface rather than internals.

Within the file, tests come last in the struct body (ZS-NAME-20). Prefer the decltest form
(ZS-TEST-02); note that `test <name>` resolves file-scope declarations only (ZS-NAME-22).

**Why:** a test in the same file can reach private declarations without widening their visibility,
so you test the real internal invariants instead of inventing `pub` accessors for the test's
benefit. It also means a file is self-contained: deleting the file deletes its tests, and a reviewer
reading a function sees its contract immediately below it. `zig test` compiles the file plus
everything it transitively `@import`s, so co-located tests are picked up with zero wiring. The
mirror-tree layout loses all three properties at once and adds a second file to keep in sync.

**Check:** a `tests/` directory whose files correspond one-to-one with `src/` files is the smell;
a `tests/` directory whose files `@import("myproj")` by module name is correct.

```zig
// verified — GOOD
const std = @import("std");

pub fn add(a: i32, b: i32) i32 {
    return a + b;
}

test add {
    try std.testing.expectEqual(10, add(3, 7));
    try std.testing.expectEqual(-1, add(-4, 3));
}
```

> TigerStyle divergence: TigerBeetle also co-locates tests, but additionally maintains
> `src/unit_tests.zig`, a `comptime { _ = @import("..."); }` block naming every file, because its
> test binary has a single root module. That is an aggregation mechanism (see ZS-TEST-04), not an
> argument for separate test files.

### ZS-TEST-02 [M] Use the decltest form `test declName` when a test targets exactly one declaration
Write `test add { ... }` — an identifier, not a string — when the test is about one function, type,
or constant. Use a string name only when the test spans several declarations or describes a
scenario.

**Why:** the decltest form is a compile-checked reference. Rename or delete `add` and the test stops
compiling instead of silently drifting into a test named after a function that no longer exists. std
uses this form throughout (`test expectApproxEqAbs`, `test FailingAllocator`, `test
baselineWeights`), and the runner reports it distinctly as `file.decltest.add` rather than
`file.test.<name>`.

```zig
// fragment — BAD
test "add" { // string that merely repeats a name; nothing checks it still exists
    try std.testing.expectEqual(10, add(3, 7));
}
```

```zig
// fragment — GOOD
test add {
    try std.testing.expectEqual(10, add(3, 7));
}
```

`test <name>` resolves **file-scope declarations only**, so a struct method cannot be named:

```zig
// does-not-compile
const S = struct {
    pub fn go() void {}
};
test go { // error: use of undeclared identifier 'go'
    _ = S;
}
```

**Check:** `rg 'test "'` in a diff — each hit must span several declarations or describe a
scenario; a string that merely repeats an identifier should be a decltest.

When a string name *is* right, make it read as a claim that can be true or false — what happens,
under what precondition — because that string is all a CI log shows on failure. `test "parse"` tells
the reader nothing; `test "parse rejects a length prefix that exceeds the buffer"` names the
invariant that broke without opening the file.

```zig
// fragment — GOOD
test "decode rejects a frame whose length prefix exceeds the remaining bytes" { ... }
test "flush after crash recovers exactly the durable prefix" { ... }
```

### ZS-TEST-03 [S] Name string tests after the behavior and the precondition (see ZS-TEST-02)
Owned by ZS-TEST-02, which covers test naming and prefers the decltest form outright. A string name
is used only when no single declaration is the subject, and then it states what happens under what
condition.

### ZS-TEST-04 [M] Every source file must be reachable from a test binary (see ZS-BUILD-18)
Owned by `references/build.md` ZS-BUILD-18: a `test` block in a file reached only
through a lazily-analyzed declaration is never collected, so the suite goes green with untested
code. Reference each such file explicitly from the module root (`test { _ = @import("codec.zig");
}`). A test binary tests one module at a time, so a lib+exe project needs at least two `b.addTest`
calls wired into the same `test` step — ZS-BUILD-05.

## Part 2 — Writing a unit test

### ZS-TEST-05 [M] Allocate from `std.testing.allocator`; a leak fails the run
Any test that allocates uses `std.testing.allocator`, pairs every allocation with `defer` /
`errdefer`, and never falls back to `std.heap.page_allocator`, `std.heap.smp_allocator`, or a
private arena "to keep it simple". This is the only allocator a test should name; other chapters
reduce to this rule.

The surface at 0.17.0, `std.testing.allocator` and `std.testing.allocator_instance`:

- `pub const allocator` — `allocator_instance.allocator()`, an `std.mem.Allocator` interface value,
  and the allocator you pass as the *backing* allocator to `checkAllAllocationFailures`
  (ZS-TEST-13) and `FailingAllocator` (ZS-TEST-14). Outside `builtin.is_test` it is
  `@compileError("not testing")`, so it cannot leak into production.
- `pub var allocator_instance: std.heap.SafeAllocator` — the backing instance (a `DebugAllocator`
  in 0.16). It has no `detectLeaks`: the runner calls `allocator_instance.deinit()` after each test,
  and the `usize` it returns is the leak count.
- The runner re-initialises it before every test with `.canary = 0xc3a701ba` and
  `.check_write_after_free = true`. Stack traces come from `SafeAllocator`'s default
  `stack_trace_frames`: 7 in a `debug` build that can unwind, and 0 otherwise.

**Why:** `testing.allocator` reports the leaked address *with the stack trace of the allocation that
leaked* (in a `debug` build; a `safe` test build prints `(empty stack trace)`), and makes the whole
test command exit non-zero. Note the exact behavior: the individual test still prints `OK`, and the
failure surfaces afterwards as `1 tests leaked memory` plus a non-zero exit — so leaks are caught by
CI, not by eyeballing per-test output. The canary is why mixing it up with a default-constructed
`SafeAllocator` panics (`foreign allocation from canary 0xc3a701ba`) instead of silently
corrupting: the two instances are distinguishable at free time. An arena hides exactly the bug the
suite exists to find, because every missing `free` is absorbed by `arena.deinit()`.

**Check:** in a diff, any allocator named inside a `test` block other than `std.testing.allocator`,
`std.testing.failing_allocator`, or a `FailingAllocator` wrapping one of them. `page_allocator` and
`ArenaAllocator` in a test are the two common offenders.

```zig
// fragment — BAD
test "join" {
    const gpa = std.heap.page_allocator; // leaks are invisible
    const s = try joinAlloc(gpa, ",", &.{ "a", "b" });
    _ = s;
}
```

```zig
// verified — GOOD
const std = @import("std");
test "expectEqual: expected first, no @as wrapping needed" {
    var list: std.ArrayList(i32) = .empty;
    defer list.deinit(std.testing.allocator);
    try list.append(std.testing.allocator, 42);
    try std.testing.expectEqual(42, list.pop());
}
```

### ZS-TEST-06 [M] Call `expectEqual(expected, actual)` in that order, and drop the `@as` wrapper
In 0.17 the signature is `pub inline fn expectEqual(expected: anytype, actual: anytype) !void` —
both parameters are `anytype` and the common type comes from `@TypeOf(expected, actual)` peer
resolution. Pass the bare literal.

**Why:** peer resolution makes `@as(usize, 3)` redundant for literals, enum literals, and `null` —
`expectEqual(3, len)`, `expectEqual(.red, pick(0))`, and `expectEqual(null, pick(9))` all compile.
Order still matters because the diagnostic prints `expected X, found Y`; swapping the arguments
makes every failure message lie. Peer resolution is not universal: `expectEqual(Color.a, some_u8)`
is a hard compile error inside `std.testing.expectEqual` (`incompatible types: 'Color' and 'u8'`),
and there you must convert explicitly rather than reach back for `@as` reflexively.

**Check:** an `expectEqual` whose *first* argument is a call, a field access, or a local and whose
second is a literal — the arguments are swapped and every failure message will read backwards.
Second grep: `@as(` inside an `expectEqual` argument where the other side is a literal, which peer
resolution already handles.

```zig
// fragment — BAD
try std.testing.expectEqual(list.pop(), @as(?i32, 42)); // actual first; message reads backwards
```

```zig
// fragment — GOOD
try std.testing.expectEqual(42, list.pop());
try std.testing.expectEqual(null, pick(9));
try std.testing.expectEqual(3, @as(usize, 3));
```

### ZS-TEST-07 [M] Never compare slice or string *contents* with `expectEqual`
`expectEqual` on a slice compares `.ptr` and `.len`, not bytes. Use `expectEqualStrings` for
`[]const u8` text, `expectEqualSlices(T, ...)` for other element types, or `expectEqualDeep` when
you genuinely want structural equality through pointers.

**Why:** in `std.testing.expectEqual` the `.slice` branch does `if (actual.ptr !=
expected.ptr) return error.TestExpectedEqual;`. Two slices holding identical bytes at different
addresses fail, and the diagnostic is `expected slice ptr u8@102c3328c, found u8@16d321880`, which
reads like a memory bug rather than what it is: the wrong matcher.

**Check:** `rg -n 'expectEqual\('` and read the argument types. A string literal, a `[]const u8`, a
`[]T`, or a many-pointer on either side is the finding. A failure message containing the words
`slice ptr` is the same bug found the slow way.

```zig
// fragment — BAD
const actual = try renderAlloc(gpa);
try std.testing.expectEqual("hello", actual); // compares addresses
```

```zig
// fragment — GOOD
const a: []const u8 = "hello";
var buf: [5]u8 = "hello".*;
const b: []const u8 = &buf;
try std.testing.expectEqualStrings(a, b);
try std.testing.expectError(error.TestExpectedEqual, std.testing.expectEqual(a, b));
```

### ZS-TEST-08 [M] Use the narrowest matcher `std.testing` offers, and never `assert` inside a test
The 0.17 surface, from `std.testing`: `expect`, `expectEqual`, `expectEqualDeep`,
`expectError`, `expectFmt`, `expectEqualStrings`, `expectEqualSlices`, `expectEqualSentinel`,
`expectStringStartsWith`, `expectStringEndsWith`, `expectApproxEqAbs`, `expectApproxEqRel`. Reach
for the one that matches the type; fall back to `expect(bool)` only for genuine predicates.

**Why:** the narrow matchers print a diff. `expectEqualSlices` renders a hex/ASCII dump with the
differing bytes colored and the first differing index called out; `expectEqualStrings` shows the
line and column of the first divergence. `expect(a == b)` prints `error.TestUnexpectedResult` and
nothing else.

**This rule owns the ban on `std.debug.assert` inside a `test` block.** It is strictly worse than
every matcher above: it lowers to `unreachable`, panics, and **kills the whole test binary** —
the remaining tests never execute, so one broken invariant costs you the signal from every
test scheduled after it. A `try testing.expect*` failure is attributed to its test, counted, and the
run continues. The same applies to `unreachable`, `@panic`, and `std.debug.panic` written in test
code. Assertions in *production* code are the assertions chapter's subject and are unaffected — the
ban is on assertions written in the test itself. The one documented deviation is the simulation loop
below, where stopping the process at the first divergence is the point.

**Check:** `rg -n 'assert\('` inside `test` blocks in the diff; also `expect(std.mem.eql(`, which
is `expectEqualSlices` spelled the lossy way.

```zig
// fragment — BAD
try std.testing.expect(std.mem.eql(u8, expected, actual)); // no diff on failure
std.debug.assert(count == 3);                              // aborts the binary
```

```zig
// fragment — GOOD
try std.testing.expectEqualStrings("abc", "abc");
try std.testing.expectEqualSlices(u16, &.{ 1, 2, 3 }, &.{ 1, 2, 3 });
try std.testing.expectEqualSentinel(u8, 0, "abc", "abc");
try std.testing.expectStringStartsWith("hello world", "hello");
try std.testing.expectStringEndsWith("hello world", "world");
try std.testing.expectError(error.Overflow, parsePort("65536"));
```

> TigerStyle divergence: TigerBeetle's model tests use bare `assert(a == b)` inside `test` blocks,
> because in that codebase the test binary crashing *is* the desired signal. For general code prefer
> `try testing.expect*`: it keeps the remaining tests running and gives you a diff. Use `assert` in
> a test only inside a simulation loop where you want the process to stop at the first divergence
> with a full stack trace.

### ZS-TEST-09 [M] Tests that perform I/O must use `std.testing.io`
`std.testing.io` is new in 0.16 and is the only `Io` a test may name. Pass it wherever an `Io` is
required — `tmp.dir.writeFile(io, …)`, `Io.Timestamp.now(io, …)`, `io.async(…)`. Do not construct
your own backend (`Io.Threaded`, `Io.Uring`, `Io.Kqueue`) or a hand-rolled test double.

The surface at 0.17.0, `std.testing.io_instance` and `std.testing.io`:

```zig
// fragment — (quoted from std/testing.zig)
pub var io_instance: Io.Threaded = undefined;
pub const io = if (builtin.is_test) io_instance.io() else @compileError("not testing");
```

`io_instance` is an `Io.Threaded` the test runner initializes with `testing.allocator` before each
test and tears down after; `testing.io` is the `std.Io` interface value taken from it.

**Why:** the runner leak-checks that backing allocator around every test, so an `Io` resource you
fail to close is reported like any other leak, with the allocating stack trace (ZS-TEST-05). A
privately constructed backend allocates outside that window and escapes the check entirely (and on
0.16.0, some backends' `deinit` did not even compile). The `builtin.is_test` guard means a
`testing.io` reference that drifts into production code is a compile error rather than a runtime
surprise. Filesystem access additionally goes through `testing.tmpDir` (ZS-TEST-10), which is where
the `io` argument usually first appears.

**Check:** `rg -n 'Io.Threaded|Io.Uring|Io.Kqueue'` in test files — any hit is a privately
constructed backend that the runner's leak check cannot see.

```zig
// verified — GOOD
const std = @import("std");
test "testing.io is a real Io" {
    const start: std.Io.Timestamp = .now(std.testing.io, .awake);
    try std.testing.io.sleep(.fromMilliseconds(1), .awake);
    const end: std.Io.Timestamp = .now(std.testing.io, .awake);
    try std.testing.expect(start.durationTo(end).toNanoseconds() >= 0);
}
```

### ZS-TEST-10 [M] Filesystem tests use `testing.tmpDir(.{})` with `defer tmp.cleanup()`
`pub fn tmpDir(opts: Io.Dir.OpenOptions) TmpDir` — the parameter is `Io.Dir.OpenOptions` in 0.17
(fields `access_sub_paths`, `iterate`, `follow_symlinks`), not the old `std.fs` options. Never touch
the real cwd, `/tmp`, or a hardcoded path.

**Why:** `tmpDir` creates `.zig-cache/tmp/<12 random bytes, base64url>` using `io.random`, so
parallel test binaries and reruns cannot collide. `cleanup()` closes the dir, `deleteTree`s it, and
sets the struct to `undefined` so a use-after-cleanup trips safety checks instead of silently
operating on a closed handle.

**Check:** inside a `test` block, any `Io.Dir.cwd()`, any absolute path literal, any string
containing `/tmp` or `zig-cache`, and any `tmpDir(` without `defer tmp.cleanup();` on the following
line. A test that passes locally and fails when two test binaries run in parallel is this bug.

```zig
// verified — GOOD
const std = @import("std");
test "config round-trips through the filesystem" {
    var tmp = std.testing.tmpDir(.{});
    defer tmp.cleanup();

    const io = std.testing.io;
    const gpa = std.testing.allocator;
    try tmp.dir.writeFile(io, .{ .sub_path = "cfg.txt", .data = "port=8080\n" });
    const text = try tmp.dir.readFileAlloc(io, "cfg.txt", gpa, .limited(4096));
    defer gpa.free(text);
    try std.testing.expectEqualStrings("port=8080\n", text);
}
```

### ZS-TEST-11 [M] A passing test writes nothing to stderr; diagnostics go in `errdefer`
No unconditional `std.debug.print` in a test. Put the diagnostic behind `errdefer` so it fires only
on the failure path.

**Why:** under `zig build test` the test binary runs with `--listen=-`, so the build
runner captures its stderr and replays it above a line beginning `failed command:` even though
the step succeeded and the build exits 0. Every stray `print` therefore produces output that reads
like a failure and is not attributed to the test that emitted it. `errdefer` inverts this:
the message appears directly above the failing test's stack trace in the runner's report, and the
build runner's own footer echoes the same `--seed`, so the reproduction command you printed and the
one the tool printed agree.

**Check:** `rg -n 'std.debug.print|std.log\.'` inside `test` blocks — every hit must be on an
`errdefer` line or inside a function only an `errdefer` reaches. A green `zig build test` that emits
anything with a `failed command:` line is the same finding observed at runtime.

```zig
// fragment — BAD
test "swarm" {
    // Surfaces under a misleading `failed command:` line on every green run.
    std.debug.print("seed=0x{x}\n", .{std.testing.random_seed});
    ...
}
```

```zig
// fragment — GOOD
test "seeded randomness, seed reported on failure" {
    const seed: u64 = std.testing.random_seed;
    errdefer std.debug.print("reproduce with: zig build test --seed=0x{x}\n", .{seed});
    var prng: std.Random.DefaultPrng = .init(seed);
    ...
}
```

## Part 3 — Negative space and allocation failure

### ZS-TEST-12 [M!] Test the negative space, not just the happy path
For every input domain, test invalid data *and* valid data crossing into invalid — the boundary, one
past it, the empty case, the maximum case, and the truncated case.

`[M!]` applies to code that parses untrusted bytes, manages durable state, or enforces a security or
consistency invariant — decoders, wire formats, journals, allocators, permission checks.
*Relaxed form:* one `expectError` for every variant in the function's declared error set, plus the
empty input and the maximum input; the boundary, one-past-the-boundary, and truncated cases drop
to `[S]`.

**Why:** this is TigerStyle's golden rule of assertions applied to tests: bugs cluster where data
crosses the valid/invalid boundary, because that is where the code changes its mind about what the
data means. A suite that only feeds valid input verifies the parser's optimism, not its rejection
logic — and the rejection logic is the part attackers and corrupt disks exercise. Concretely, an
`expectError` per error variant proves the error is reachable, which also proves it is not dead
code.

**Check:** list the variants of the function's declared error set and count `expectError` calls in
its tests; a variant with no test is the finding. Then look for the three literal inputs — the
empty one, the `_max` one, and one past `_max`. A test in which every input is valid is the shape
this rule names.

```zig
// fragment — BAD
test parsePort {
    try std.testing.expectEqual(8080, try parsePort("8080")); // only the happy path
}
```

```zig
// fragment — GOOD
test parsePort {
    try std.testing.expectEqual(8080, try parsePort("8080"));
    try std.testing.expectEqual(0, try parsePort("0"));
    try std.testing.expectEqual(65535, try parsePort("65535"));
    try std.testing.expectError(error.Overflow, parsePort("65536"));
    try std.testing.expectError(error.InvalidCharacter, parsePort("80o80"));
    try std.testing.expectError(error.InvalidCharacter, parsePort(""));
}
```

### ZS-TEST-13 [M!] Every allocating API gets a `checkAllAllocationFailures` test
`checkAllAllocationFailures(backing_allocator, test_fn, extra_args)` runs `test_fn` once to count
its allocations, then re-runs it N times failing allocation *i* each time, asserting each run
returns `error.OutOfMemory` and leaks nothing. `test_fn` must take `std.mem.Allocator` as its first
parameter and return `!void`.

`[M!]` applies wherever an OOM must not corrupt state or lose data — databases, storage engines,
allocators, long-running network servers. *Relaxed form:* one `checkAllAllocationFailures` test per
**public** allocating entry point of the module, and for everything private, an `errdefer` audit
instead: every function with two or more `try` allocations must free the earlier ones on the failure
path of the later ones.

**Why:** the bug it finds is invisible to normal tests: a function that allocates twice and frees
both on the success path but forgets `errdefer` on the first. That leaks only when the *second*
allocation fails, which never happens with a real allocator during testing. The tool exercises
exactly that path, and on failure prints `fail_index: 1/2`, the byte counts, and the stack trace of
the allocation that was made to fail. Two of its errors are diagnostic in their
own right: `error.SwallowedOutOfMemoryError` means the function absorbed an OOM it should have
propagated, and `error.NondeterministicMemoryUsage` means the allocation count varies between runs,
which usually means hidden global state.

The backing allocator you pass is `std.testing.allocator` (ZS-TEST-05) — the tool wraps it in a
`FailingAllocator` per run, so leak detection still applies to every one of the N re-runs. Extra
arguments are forwarded as a tuple after the allocator, which is why `test_fn` must take
`std.mem.Allocator` first and cannot close over the test's locals. For a single targeted OOM path
rather than the exhaustive sweep, use `FailingAllocator` directly (ZS-TEST-14).

**Check:** every `pub fn …Alloc`/`init` in the diff that can return `error.OutOfMemory` should have
a `checkAllAllocationFailures` test, or a comment saying why not. A function with two `try
gpa.alloc` calls and no `errdefer` between them is the exact shape this catches.

```zig
// verified — BAD: reported as MemoryLeakDetected at fail_index 1/2
const std = @import("std");
fn buggy(gpa: std.mem.Allocator, n: usize) ![]u8 {
    const a = try gpa.alloc(u8, n);
    const b = try gpa.alloc(u8, n); // if this fails, `a` leaks
    gpa.free(b);
    return a;
}
```

```zig
// verified — GOOD
const std = @import("std");
const Allocator = std.mem.Allocator;

pub fn joinAlloc(gpa: Allocator, sep: []const u8, parts: []const []const u8) Allocator.Error![]u8 {
    var out: std.ArrayList(u8) = .empty;
    errdefer out.deinit(gpa); // the line checkAllAllocationFailures exists to verify
    for (parts, 0..) |part, i| {
        if (i != 0) try out.appendSlice(gpa, sep);
        try out.appendSlice(gpa, part);
    }
    return out.toOwnedSlice(gpa);
}

fn joinCase(gpa: Allocator, parts: []const []const u8) !void {
    const joined = try joinAlloc(gpa, ",", parts);
    defer gpa.free(joined);
    try std.testing.expect(joined.len >= parts.len -| 1);
}

test "joinAlloc survives every allocation failure point" {
    try std.testing.checkAllAllocationFailures(
        std.testing.allocator,
        joinCase,
        .{&[_][]const u8{ "alpha", "beta", "gamma" }},
    );
}
```

> Under TigerStyle's static-allocation rule this test is moot, because nothing allocates after
> startup. The graduated form for codebases that do allocate at runtime is this rule; the graduated
> form for codebases that do not is a fixed backing buffer plus `assumeCapacity` methods, where OOM
> is impossible by construction and the corresponding test is a capacity assertion instead.

### ZS-TEST-14 [S] Use `failing_allocator` or `FailingAllocator` for one targeted OOM path
`std.testing.failing_allocator` fails on allocation index 0 — every allocation. For a specific
index, construct `testing.FailingAllocator.init(backing, .{ .fail_index = n })`, or use
`.resize_fail_index` to force the resize path.

**Why:** `checkAllAllocationFailures` is exhaustive but requires a deterministic allocation count
and a `!void` helper. When you want a single, readable assertion — "constructing this with no memory
returns `error.OutOfMemory` rather than panicking" — the failing allocator says it in one line. Note
`failing_allocator` is backed by a zero-length `FixedBufferAllocator`, so it cannot serve any
request.

**Check:** a `FailingAllocator.init` whose backing allocator is not `std.testing.allocator` — the
wrapper does not leak-check by itself, so the N-th run's leak goes unseen. And `failing_allocator`
used where the code under test must complete an earlier allocation first: it serves nothing, so the
test proves only that the *first* allocation is checked.

```zig
// fragment — GOOD
const std = @import("std");
test "failing_allocator: the first allocation always fails" {
    try std.testing.expectError(
        error.OutOfMemory,
        joinAlloc(std.testing.failing_allocator, ",", &.{ "a", "b" }),
    );
}

test "explicit FailingAllocator at a chosen index" {
    var fa: std.testing.FailingAllocator = .init(std.testing.allocator, .{ .fail_index = 1 });
    try std.testing.expectError(error.OutOfMemory, joinAlloc(fa.allocator(), ",", &.{ "a", "b" }));
}
```

## Part 4 — Randomised, model-based, and simulation testing

### ZS-TEST-15 [M] Seed randomised tests from `std.testing.random_seed`; print the seed on failure
Never call an unseeded RNG in a test. Take `std.testing.random_seed` (a `u32`, set by the runner
from its `--seed=` argument), feed it to `std.Random.DefaultPrng`, and emit the reproduction command
from an `errdefer`.

**Why:** both `zig test` and `zig build test` pass a *freshly randomised* `--seed=0x…` on
every invocation, so a randomised test explores new inputs each run. That is the point, and it is
also why an un-reported seed is useless: the failure will not reproduce. Passing `--seed=0x1234` to
`zig build` pins it, and the build runner echoes the seed in its footer, so the errdefer line and
the tool's own output agree. Write the `=`: 0.17's `zig build` rejects `--seed 0x1234` with
`unrecognized argument: --seed`, though its `--help` prints that form.

**Check:** `rg -n 'DefaultPrng|Xoshiro|std.crypto.random'` in test files. Any `.init(` argument
that is a literal, a timestamp, or anything other than `std.testing.random_seed` is the finding, as
is a seeded test with no `errdefer` printing the seed.

```zig
// fragment — BAD
// Fixed seed: explores exactly one path forever.
var prng: std.Random.DefaultPrng = .init(0xdeadbeef);
// Wall clock: every run differs and no run can be replayed.
const wall: std.Io.Timestamp = .now(std.testing.io, .real);
var prng2: std.Random.DefaultPrng = .init(@bitCast(wall.toMilliseconds()));
```

```zig
// verified — GOOD
const std = @import("std");
test "seeded randomness, seed reported on failure" {
    const seed: u64 = std.testing.random_seed;
    errdefer std.debug.print("reproduce with: zig build test --seed=0x{x}\n", .{seed});

    var prng: std.Random.DefaultPrng = .init(seed);
    const rand = prng.random();
    for (0..1000) |_| {
        const a = rand.intRangeAtMost(i32, -1000, 1000);
        const b = rand.intRangeAtMost(i32, -1000, 1000);
        try std.testing.expectEqual(a + b, b + a);
    }
}
```

### ZS-TEST-16 [M] A seeded test must be a pure function of its seed
Given the same seed, a test must take the same path every time. That forbids, inside the tested
region: wall-clock or monotonic time, thread scheduling, address-order iteration (`HashMap`
iteration order, pointer comparison, `@intFromPtr` in a hash), environment variables, and real
network or disk.

**Why:** a seed that does not reproduce the failure is a seed that costs you a day. The usual
culprit is not obvious randomness but incidental nondeterminism, and hash-map iteration is the
classic case: the order is unspecified, and it shifts with insertion order, with capacity (so with
one extra `put` anywhere upstream), and with any std version bump — so a test that asserts on "the
first element" can start failing on a change that touched neither the test nor the code under it.
For a map keyed on pointers, or hashed via `@intFromPtr`, ASLR makes the order vary per *process*
as well, so the same seed disagrees run to run. (Zig's string hashing is content-based —
`hashString` seeds Wyhash with a literal `0` — so string keys are stable within a build; the order
is still unspecified and still must not be asserted on.) Substituting a simulated clock and a
simulated disk (ZS-TEST-18) is what makes a seed a complete description of a run.

**Check:** inside a seeded test, grep for a `HashMap`/`ArrayHashMap` iterator whose result feeds an
assertion, `@intFromPtr`, a pointer comparison, `Io.Timestamp.now`, `getEnvVarOwned`, `io.async`,
and any real `Io.Dir`/`Io.File`. Each one reintroduces an ordering the seed does not control.

```zig
// fragment — BAD
// Iteration order is unspecified: it shifts with insertion order, capacity, and
// std version — and per-process too when the key is a pointer.
var it = map.iterator();
const first = it.next().?;
try std.testing.expectEqualStrings("alice", first.key_ptr.*);
```

```zig
// fragment — GOOD
// Collect and sort into a canonical order before asserting.
var names: std.ArrayList([]const u8) = .empty;
defer names.deinit(gpa);
var it = map.iterator();
while (it.next()) |entry| try names.append(gpa, entry.key_ptr.*);
std.mem.sortUnstable([]const u8, names.items, {}, struct {
    fn lessThan(_: void, a: []const u8, b: []const u8) bool {
        return std.mem.order(u8, a, b) == .lt;
    }
}.lessThan);
try std.testing.expectEqualStrings("alice", names.items[0]);
```

### ZS-TEST-17 [S] Give every container and state machine a model-based swarm test
Pick a simpler reference implementation (usually a `std` container), drive both with a seeded random
sequence of actions chosen from an enum, and compare after every action and at the end.

**Why:** hand-written cases test the sequences you thought of. A swarm test tests sequences you did
not — the interleavings, the empty-then-refill, the pop-past-empty — and the model is the oracle so
you do not have to predict the expected value. Deriving the action enum from the type
(`std.meta.DeclEnum(T)`, TigerBeetle's technique) makes adding a method automatically add fuzz
coverage for it.

**Check:** for each container or state machine added in the diff, is there a test containing
`rand.enumValue(` driving both it and a `std` model? A type whose only tests are hand-written call
sequences is the gap; so is a swarm test whose action enum omits a public method.

```zig
// fragment — GOOD
const std = @import("std");
test "Stack matches an ArrayList model under a random action swarm" {
    const seed: u64 = std.testing.random_seed;
    errdefer std.debug.print("reproduce with: zig build test --seed=0x{x}\n", .{seed});

    var prng: std.Random.DefaultPrng = .init(seed);
    const rand = prng.random();
    const gpa = std.testing.allocator;
    var backing: [32]u8 = undefined;

    for (0..64) |_| {
        var stack: Stack = .init(&backing);
        var model: std.ArrayList(u8) = .empty;
        defer model.deinit(gpa);

        for (0..512) |_| switch (rand.enumValue(enum { push, pop, count })) {
            .push => {
                if (model.items.len == backing.len) continue;
                const byte = rand.int(u8);
                stack.push(byte);
                try model.append(gpa, byte);
            },
            .pop => try std.testing.expectEqual(model.pop(), stack.pop()),
            .count => try std.testing.expectEqual(model.items.len, stack.count()),
        };
        try std.testing.expectEqualSlices(u8, model.items, stack.items.items);
    }
}
```

Two refinements worth adopting: run several *swarms* (outer loop) where each swarm disables some
actions entirely and re-weights the rest, so rare interleavings become common in some swarms; and
scale the action count by an `events_max` knob so CI can run long and local runs can run short.

### ZS-TEST-18 [M!] Test stateful systems by deterministic simulation with injected faults
Replace every source of nondeterminism — clock, disk, network, thread scheduling — with a simulated
implementation driven by the one seeded PRNG. Run the system in a single thread, inject faults
(crash, partition, delay, corruption) on schedule, and assert the safety invariant after every
fault.

`[M!]` applies to systems with durable state or multiple participants — storage engines,
replication, queues, consensus, embedded firmware with persistence. *Relaxed form:* ZS-TEST-17's
seeded model-based swarm test against an in-memory model, with no simulated clock and no fault
injection, plus one hand-written test per failure mode you can name (a crash between two writes,
a short read, a duplicated message).

**Why:** this is what TigerBeetle's VOPR does, and the reason it works is that a whole cluster's
history collapses into a single `u64`. Real concurrency and real disks produce failures you cannot
replay; a simulated one produces failures you can replay exactly, shrink, and step through in a
debugger. Structure it as three parts a general project can actually build: a **seeded deterministic
driver** (one PRNG, one thread, an explicit tick budget), a **reference model** that encodes only
what the specification promises must survive, and a **state comparison** after every fault. Split
the run into a safety phase (arbitrary faults; the invariant must never break) and a liveness phase
(faults stop; the system must converge within a bounded number of ticks). Print every knob at
startup, and print the seed on failure.

**Check:** the simulation test must name exactly one PRNG and no real resource. Grep its body for a
second `.init(seed)`, for `io.async`/`Thread.spawn`, for `Io.Dir`/`Io.File`/`Io.Timestamp.now`, and
for an unbounded `while (true)` with no tick budget. Then confirm the invariant is asserted inside
the fault branch, not only after the loop.

```zig
// fragment — GOOD
/// Fully deterministic stand-in for a real disk: no syscalls, no clock, no threads.
const std = @import("std");
const assert = std.debug.assert;
pub const SimDisk = struct {
    durable: [1024]u8 = undefined,
    durable_len: usize = 0,

    pub fn write(disk: *SimDisk, bytes: []const u8) void {
        assert(disk.durable_len + bytes.len <= disk.durable.len);
        @memcpy(disk.durable[disk.durable_len..][0..bytes.len], bytes);
        disk.durable_len += bytes.len;
    }

    pub fn recover(disk: *const SimDisk) []const u8 {
        return disk.durable[0..disk.durable_len];
    }
};

test "simulation: recovery yields exactly the flushed prefix" {
    const seed: u64 = std.testing.random_seed;
    errdefer std.debug.print("reproduce with: zig build test --seed=0x{x}\n", .{seed});

    var prng: std.Random.DefaultPrng = .init(seed);
    const rand = prng.random();
    const gpa = std.testing.allocator;

    for (0..256) |_| {
        var disk: SimDisk = .{};
        var log: Log = .{ .disk = &disk, .pending = .empty };
        defer log.pending.deinit(gpa);

        // The model records only what the specification says must survive a crash.
        var model: std.ArrayList(u8) = .empty;
        defer model.deinit(gpa);
        var unflushed: std.ArrayList(u8) = .empty;
        defer unflushed.deinit(gpa);

        const steps = rand.intRangeAtMost(u32, 0, 200); // explicit tick budget
        for (0..steps) |_| switch (rand.enumValue(enum { append, flush, crash })) {
            .append => {
                if (model.items.len + unflushed.items.len == disk.durable.len) continue;
                const record = rand.int(u8);
                try log.append(gpa, record);
                try unflushed.append(gpa, record);
            },
            .flush => {
                log.flush();
                try model.appendSlice(gpa, unflushed.items);
                unflushed.clearRetainingCapacity();
            },
            .crash => { // injected fault: unflushed records are lost
                log.pending.clearRetainingCapacity();
                unflushed.clearRetainingCapacity();
                try std.testing.expectEqualSlices(u8, model.items, disk.recover());
            },
        };
        try std.testing.expectEqualSlices(u8, model.items, disk.recover());
    }
}
```

### ZS-TEST-19 [S] Snapshot-test complex output against an inline multiline literal
When the expected value is a structure whose readable form is a block of text — a formatted tree, a
disassembly, a diagnostic — render it to an `Io.Writer` and compare with `expectEqualStrings`
against a `\\` multiline literal in the test.

**Why:** `expectEqual` on a 12-field nested struct tells you "they differ"; a rendered snapshot
tells you *where*, because `expectEqualStrings` prints the first differing line and column. It also
makes refactors cheap: one visual diff to review instead of thirty field assertions to rewrite. Keep
the literal inline in the test file, never in a sidecar `.txt` — a snapshot you cannot see while
reading the test is a snapshot nobody reviews. If you add an updater (an env var that rewrites the
literal in place, as TigerBeetle's `snaptest` does with `SNAP_UPDATE=1`), the review discipline is
the same: regenerated snapshots must be read, not rubber-stamped.

**Check:** an expected value pulled from outside the test block — `@embedFile`, `readFileAlloc`, a
path under `testdata/` — and a rendered snapshot compared with `expectEqual` or
`expect(std.mem.eql(` rather than `expectEqualStrings`. A diff that changes only sidecar snapshot
files is the review failure this rule is guarding against.

```zig
// fragment — GOOD
test "snapshot: tree layout" {
    const tree: Tree = .{ .label = "root", .children = &.{
        .{ .label = "a", .children = &.{.{ .label = "a1", .children = &.{} }} },
        .{ .label = "b", .children = &.{} },
    } };

    var buf: [256]u8 = undefined;
    var w: std.Io.Writer = .fixed(&buf);
    try tree.dump(&w, 0);

    try std.testing.expectEqualStrings(
        \\root
        \\  a
        \\    a1
        \\  b
        \\
    , w.buffered());
}
```

## Part 5 — Fuzzing with `Smith`

### ZS-TEST-20 [M] Write fuzz targets with `std.testing.fuzz` and `*std.testing.Smith`
The 0.17 shape, unchanged from 0.16, is `try std.testing.fuzz(context, testOne, .{})`, where the
target is declared `fn testOne(context: C, smith: *std.testing.Smith) !void`. `Smith` replaces the
old `[]const u8` fuzz input entirely. Its surface, from `std.testing.Smith`: `eos()`, `value(T)`,
`valueRangeAtMost(T, lo, hi)`, `valueRangeLessThan(T, lo, hi)`, `index(len)`, `bytes(out)`,
`slice(buf) u32`, `boolWeighted(false_w, true_w)`, plus the weighted variants `valueWeighted`,
`eosWeighted`, `eosWeightedSimple`, `bytesWeighted`, `sliceWeighted`, `sliceWeightedBytes`, and
`baselineWeights(T)`.

**Why:** `Smith` is a *structured* input source, not a byte buffer. Each call site is identified by
its return address, so the coverage-guided fuzzer learns which decision points matter and mutates
them independently — you get "make the length field large" rather than "flip byte 7". `value(T)`
works on ints, floats, bools, enums, optionals, arrays, vectors, structs and tagged unions, so you
generate typed operations directly instead of hand-decoding bytes. Run the targets by passing
`--fuzz` to `zig build test`; `--fuzz=20K` bounds the iteration count, and a bare `--fuzz` with no
limit implies `--webui`.

**Check:** a fuzz target whose second parameter is `[]const u8` rather than `*std.testing.Smith`, or
a `std.testing.fuzz` call with the pre-0.16 two-argument shape (no `context`, no
`FuzzInputOptions`). Both are stale-API findings, not style ones.

```zig
// fragment — GOOD
const std = @import("std");
test "fuzz: encode then decode is the identity" {
    try std.testing.fuzz({}, fuzzRoundTrip, .{ .corpus = &.{ "", "\x00\x00", "\x03\x00abc" } });
}

fn fuzzRoundTrip(context: void, smith: *std.testing.Smith) !void {
    _ = context;
    var payload: [256]u8 = undefined;
    var encoded: [512]u8 = undefined;

    while (!smith.eos()) {
        const len = smith.slice(&payload);
        const n = try Frame.encode(&encoded, payload[0..len]);
        const decoded = try Frame.decode(encoded[0..n]);
        try std.testing.expectEqualSlices(u8, payload[0..len], decoded);

        // Negative space: any truncation of a valid frame must be rejected,
        // never silently accepted and never a panic.
        const cut = smith.valueRangeLessThan(u32, 0, @intCast(n));
        try std.testing.expectError(error.Truncated, Frame.decode(encoded[0..cut]));
    }
}
```

### ZS-TEST-21 [M] Pin every fuzz-found failure into the target's `.corpus`
`FuzzInputOptions` has one field, `corpus: []const []const u8`. When a fuzz run finds a crashing
input, add its bytes to that slice in the same commit as the fix.

**Why:** in the test runner, when the binary is *not* built in fuzz mode,
`std.testing.fuzz` runs `testOne` once per corpus entry, plus once with an empty input as a smoke
test. So the corpus is not fuzzer scaffolding: it is your regression suite, executed by every plain
`zig build test`. A fuzz target with an empty corpus contributes exactly one input to normal CI.

**Check:** any `std.testing.fuzz` call whose options are `.{}` or whose `.corpus` is `&.{}`. And any
commit that fixes a fuzzer-reported crash without adding bytes to a `.corpus` slice in the same
diff — the fix is then protected by nothing.

```zig
// fragment — GOOD
const std = @import("std");
test "fuzz: encode then decode is the identity" {
    try std.testing.fuzz({}, fuzzRoundTrip, .{ .corpus = &.{
        "",              // smoke
        "\x00\x00",      // zero-length frame
        "\x03\x00abc",   // regression: issue #412, off-by-one in the length prefix
    } });
}
```

### ZS-TEST-22 [M] Never ask `Smith` for a type without a fixed bit size
`Smith.value`, `valueRangeAtMost`, and `valueRangeLessThan` reject `usize`, `isize`, `c_int`,
`c_long`, `c_longdouble`, and the rest of the C types, with a `@compileError` reading
"type does not have a fixed bitsize". Generate a `u32` or `u64` and `@intCast`.

**Why:** the fuzzer serialises inputs to a corpus file that must be reproducible across targets. A
`usize` is 32 bits on wasm32 and 64 on x86_64, so a corpus entry would decode differently per target
and a crash found on one machine would not reproduce on another. `Smith.index(len)` is the escape
hatch when you want an in-bounds index: it takes a `usize` length and returns a `usize`.

**Check:** `usize`, `isize`, or any `c_*` type as the type argument to `smith.value`,
`valueRangeAtMost`, or `valueRangeLessThan`. The compiler catches it, so the reviewable form is the
near miss: a draw whose result is immediately `@intCast` to `usize` where `smith.index(len)` was the
right call.

```zig
// does-not-compile — BAD
const cut = smith.valueRangeLessThan(usize, 0, n);
// error: type does not have a fixed bitsize: usize
```

```zig
// fragment — GOOD
const cut = smith.valueRangeLessThan(u32, 0, @intCast(n));
const i = smith.index(items.len); // usize in, usize out, always in bounds
```

### ZS-TEST-23 [S] Steer `Smith` with ranges and weights instead of generating-then-rejecting
Prefer `valueRangeAtMost`/`index`/`bytesWeighted`/`sliceWeighted` over drawing an arbitrary value
and `continue`-ing when it is out of range.

**Why:** every rejected draw is a wasted fuzzer iteration and, worse, a coverage signal that teaches
the fuzzer nothing. Weights let you do swarm testing at the input level: `baselineWeights(T)` gives
the uniform distribution over `T`, and a narrowed weight list biases generation toward the values
that actually reach interesting code. `eos()` is the correct loop terminator rather than
`value(bool)` — it is guaranteed to eventually return `true`, so the target cannot loop forever.

**Check:** a `continue`, `break`, or early `return` inside a fuzz target that discards a draw as
out-of-range, and `while (smith.value(bool))` used as the loop condition instead of
`while (!smith.eos())`.

```zig
// fragment — BAD
const index = smith.value(u32);
if (idx >= items.len) continue; // most draws discarded once items.len is small
```

```zig
// fragment — GOOD
const index = smith.index(items.len);
const letters: []const std.testing.Smith.Weight = &.{.rangeAtMost(u8, 'a', 'z', 1)};
var name: [16]u8 = undefined;
smith.bytesWeighted(&name, letters);
```

## Part 6 — Running and maintaining the suite

### ZS-TEST-24 [M] `refAllDecls` is a compile smoke test, not coverage
`std.testing.refAllDecls(@This())` forces semantic analysis of every declaration in a container. Use
it at most once per module root, and never count it as testing.

**Why:** Zig is lazy — an unused `pub fn` in a module is never analyzed, so it can contain a type
error and still ship. `refAllDecls` closes that gap. What it does *not* do is execute anything: a
module whose only test is `refAllDecls` has zero behavioral coverage while showing a green test
count, which is worse than having no test at all because it looks covered. It is also shallow — it
references the declarations of `T` only, not of nested containers.

**Check:** a file whose only `test` block calls `refAllDecls`, and more than one `refAllDecls` call
in the same module. Count the module's `test` blocks: one is the failure this rule names.

```zig
// fragment — BAD
test { // the module's entire test suite
    std.testing.refAllDecls(@This());
}
```

```zig
// fragment — GOOD
const std = @import("std");
test { // ensures unused pub decls still compile; behavior is tested below
    std.testing.refAllDecls(@This());
}

test add {
    try std.testing.expectEqual(10, add(3, 7));
    try std.testing.expectEqual(-1, add(-4, 3));
}
```

### ZS-TEST-25 [S] `error.SkipZigTest` marks inapplicable tests, never known-failing ones
Return `error.SkipZigTest` when the test cannot meaningfully run here — wrong OS, missing hardware
feature, unsupported backend. Never use it to park a failing test.

**Why:** the runner counts skips separately from passes, so the signal is honest only if "skipped"
means "not applicable" and not "broken". A skipped failing test is a deleted failing test with extra
steps, and it will stay skipped forever. Note `std.testing.fuzz`'s `testOne` also honours
`error.SkipZigTest`: in fuzz mode, returning it means "this input is uninteresting" and the fuzzer
moves on instead of recording a failure — but in ordinary corpus mode it propagates and skips the
whole test, so do not use it as a per-input filter for logic you actually want covered.

**Check:** `rg -n 'SkipZigTest'` — every hit must sit under a condition on `builtin.target` (its
`.os`, `.cpu`, or `.abi`) or a backend capability. A skip guarded by nothing, by a build option, or
by a `TODO` comment is a parked failure wearing a skip.

```zig
// fragment — GOOD
test "skip when the environment cannot support the test" {
    if (@import("builtin").target.os.tag == .wasi) return error.SkipZigTest;
    ...
}
```

### ZS-TEST-26 [S] Set `std.testing.log_level` only around the test that needs it, and restore it
`testing.log_level` defaults to `.warn`; the runner resets it before each test. If a test needs to
observe or suppress log output, save the old value and restore it with `defer`.

**Why:** it is a mutable global shared by every test in the binary. A test that raises it to
`.debug` and does not restore it floods the output of every test that runs afterwards, and under
`zig build test` that output is replayed with a misleading `failed command:` line (ZS-TEST-11) with
no indication of which test produced it.

**Check:** every assignment to `std.testing.log_level` must be preceded by a saved `prev` and a
`defer std.testing.log_level = previous;`. An assignment at file scope, outside any `test` block, is
the worse form of the same finding.

```zig
// fragment — GOOD
test "log_level lets a noisy module be quieted" {
    const previous = std.testing.log_level;
    defer std.testing.log_level = previous;
    std.testing.log_level = .err;
    ...
}
```

### ZS-TEST-27 [M] Run the whole suite in `safe` as well as `debug`
The suite MUST execute in both modes. Drive it from a CI matrix over `-Doptimize` — the canonical
shape in ZS-BUILD-34, `matrix: optimize: [debug, safe]`, which is also how the OS matrix
already works — keeping `build.zig` on a single `optimize` from `b.standardOptimizeOption` as in
ZS-BUILD-01. For a project with no CI, loop both modes inside the `test` step instead. What is
forbidden is a pipeline that only ever runs one mode.

**Why:** the two modes execute different programs. A `debug` build keeps all runtime safety checks
and does no inlining or reordering; a `safe` build keeps the safety checks but applies the full
optimizer, so it catches illegal behavior that only manifests once code is inlined, and it catches
performance regressions and stack-overflow-in-release bugs. Meanwhile `undefined` memory is filled
with `0xaa` in `debug` and `safe` builds but not in `fast` or `small` ones, so a read of
uninitialised memory can pass in one mode and produce garbage in another. Long-running simulation
tests (ZS-TEST-18) should run in `safe` specifically, because that is the only mode where you get
both safety checks and enough speed to explore a meaningful number of seeds.

The matrix is preferred over an in-build loop because it parallelizes across runners and composes
with the OS dimension, so `os × optimize` costs one wall-clock test run rather than two serially:

```yaml
# GOOD — CI, the primary form (full workflow in ZS-BUILD-34)
strategy:
  fail-fast: false
  matrix:
    os: [ubuntu-latest, macos-latest, windows-latest]
    optimize: [debug, safe]
steps:
  - run: zig build test -Doptimize=${{ matrix.optimize }} --summary all
```

**Check:** the CI config must name both `debug` and `safe` (or the TitleCase `Debug` and
`ReleaseSafe` that 0.17 still parses), or `build.zig` must construct two `addTest` artifacts. One
`zig build test` invocation with no `-Doptimize` axis anywhere is the failure this rule names.

```zig
// fragment — GOOD: the fallback for a project with no CI
// build.zig
const test_step = b.step("test", "Run unit tests in debug and safe");
for ([_]std.lang.Optimize{ .debug, .safe }) |mode| {
    const unit_tests = b.addTest(.{
        .name = b.fmt("test-{t}", .{mode}), // test-debug, test-safe
        .root_module = b.createModule(.{
            .root_source_file = b.path("src/root.zig"),
            .target = target,
            .optimize = mode,
        }),
    });
    test_step.dependOn(&b.addRunArtifact(unit_tests).step);
}
```

### ZS-TEST-28 [M] Every bug fix ships with the test that would have caught it
A fix commit contains both the change and a test that fails before it and passes after. If the bug
came from a fuzzer, the failing input goes into `.corpus` (ZS-TEST-21); if from production, the
minimal reproduction goes into a named test referencing the issue.

**Why:** the test is the only artifact that prevents the regression; the fix alone prevents it
exactly once. Writing the test first also verifies you found the actual cause rather than a symptom
— if the test passes before your change, you have not reproduced the bug. Name the test after the
invariant that was violated, not the ticket number, and put the ticket number in a comment.

**Check:** a commit whose message says "fix" and whose diff touches no `test` block and no `.corpus`
entry. The stronger check is executable: `git stash` the non-test half of the diff and run the suite
— if it still passes, the test does not cover the bug.

```zig
// fragment — GOOD
// Regression for #412: a length prefix of 0xFFFF with 2 bytes of payload used to
// read past the end of the input instead of returning error.Truncated.
test "decode rejects a length prefix larger than the remaining input" {
    try std.testing.expectError(error.Truncated, Frame.decode("\xff\xffab"));
}
```

### ZS-TEST-29 [S] Keep unit, integration, and fuzz targets in their proper places (see ZS-BUILD-05)
Owned by `references/build.md` ZS-BUILD-05 and ZS-BUILD-01: integration tests get their
own `addTest` and their own build step, so `zig build test` stays fast and `zig build
test-integration` runs the slow set. Unit tests are co-located (ZS-TEST-01); fuzz targets sit beside
the parser or state machine they target, with a corpus (ZS-TEST-20, ZS-TEST-21).
