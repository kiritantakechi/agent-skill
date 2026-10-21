# std.Io: streams, filesystem, and structured concurrency

Everything in Zig 0.17 that can block, fail nondeterministically, or touch the outside world goes
through one value: `std.Io`. This chapter covers obtaining and threading that value, the
buffer-then-flush writing discipline, `Io.Reader`, authoring custom stream implementations, the
`std.Io.Dir`/`std.Io.File` filesystem API that replaced `std.fs`, structured concurrency
(`io.async`, `Io.Group`, `Io.Select`, `Io.Queue`, cancellation, timeouts, `Io` sync primitives),
`std.Io.net`, subprocesses via `std.process.spawn`/`run`, and `Io.Terminal` / `std.Progress`.

This chapter does not own format specifiers — `{f}`, `{t}`, `{?}` and the custom `format` method are
`references/formatting-and-output.md`. Allocator choice and `defer`/`errdefer` layout are
`references/memory-and-allocators.md`; `std.testing.io` and `Io.failing` mechanics are
`references/testing-and-fuzzing.md` ZS-TEST-09; the full 0.13→0.17 migration tables are
`references/migration-and-dead-apis.md`; the non-I/O half of batching is
`references/performance-and-locality.md` ZS-PERF-05; scoped library logging is
`references/errors-and-control-flow.md` ZS-ERR-32. It cites them.

Every example assumes a file opening with
`const std = @import("std"); const Io = std.Io; const net = std.Io.net;`, and
`const assert = std.debug.assert;` where an assertion appears.
## Contents

- **Obtaining and threading `Io`**
  - ZS-IO-01 [M] Obtain `Io` from `main`'s `std.process.Init`, never from a global
  - ZS-IO-02 [M] Thread `io: Io` as an explicit parameter, using std's ordering
  - ZS-IO-03 [M] Use `std.testing.io` in tests and `Io.failing` for error paths (see ZS-TEST-09)
  - ZS-IO-04 [S] Default to `Io.Threaded`; treat `Io.Evented` as experimental
- **Writing: buffer, then flush**
  - ZS-IO-05 [M] Flush every buffered writer before it goes out of scope
  - ZS-IO-06 [M] `std.debug.print` is a debugging tool, never program output
  - ZS-IO-07 [S] `writerStreaming` for pipes and terminals, `writer` for seekable files
  - ZS-IO-08 [M] Reusable code takes `*Io.Writer` and returns `Io.Writer.Error!void`
  - ZS-IO-09 [S] Build in-memory strings with `Io.Writer.Allocating`
  - ZS-IO-10 [M] Recover the real error from the concrete writer/reader
  - ZS-IO-11 [M] Write application stderr through `io.lockStderr`
- **Reading**
  - ZS-IO-12 [M] Size the reader buffer deliberately — it is your maximum token length
  - ZS-IO-13 [M] Iterate lines with `takeDelimiter`, never `takeDelimiterExclusive`
  - ZS-IO-14 [M] Treat slices from `peek`/`take`/`takeDelimiter` as borrowed until the next fill
  - ZS-IO-15 [M] Give every read-all API an explicit `Io.Limit`
  - ZS-IO-16 [S] Stream large data; only read whole objects you have already bounded
- **Authoring custom streams**
  - ZS-IO-17 [M] Embed the interface as a field; recover the parent with `@fieldParentPtr`
  - ZS-IO-18 [M] Implement `drain` to the full contract
  - ZS-IO-19 [M] A custom `Reader` signals end of stream with `error.EndOfStream`, never `0`
  - ZS-IO-20 [M] Pair `writableSliceGreedy` with `advance`; never `advance` after `writableSlice`
- **Filesystem**
  - ZS-IO-21 [M] `std.fs` is a deprecation shim — use `std.Io.Dir` and `std.Io.File`
  - ZS-IO-22 [M] Pair every open with `defer close(io)`, and iterate with the iterator's own buffer
  - ZS-IO-23 [M!] Replace files atomically with `createFileAtomic` + `replace`
- **Structured concurrency**
  - ZS-IO-24 [M] Every started `Future` is awaited or canceled exactly once, on every path
  - ZS-IO-25 [S] Prefer `io.async`; use `io.concurrent` only for simultaneous progress
  - ZS-IO-26 [S] Pick the right aggregate: `Group`, `Select`, or `Queue`
  - ZS-IO-27 [M] Never ignore `error.Canceled`
  - ZS-IO-28 [M!] Call `io.checkCancel()` inside long CPU-bound loops
  - ZS-IO-29 [M] Use the `*Uncancelable` variants in `defer` and cleanup paths
  - ZS-IO-30 [M] Synchronize with the `Io` primitives, never OS primitives
  - ZS-IO-31 [M] Write colorless code: never branch on which backend you were handed
  - ZS-IO-32 [S] Use raw `std.Thread` only for dedicated, long-lived OS threads
  - ZS-IO-33 [M] Time is `Io`: `Io.Timestamp`, `Io.Duration`, `Io.Clock`, `io.sleep`
  - ZS-IO-34 [S] Express a multi-step timeout as one shared deadline, not a duration per call
- **TigerStyle, re-derived for `std.Io`**
  - ZS-IO-35 [M!] Run at your own pace: drain a batch, do not react per event
  - ZS-IO-36 [M!] A suspension point invalidates every entry-time assertion about shared state
  - ZS-IO-37 [M] Retire TigerStyle's completion-callback *style*, not its parameter order
  - ZS-IO-38 [M!] Bound every stream buffer and queue with a named compile-time constant
- **Dead API — never emit these**
  - ZS-IO-39 [M] Reject the 0.13/0.14-era I/O API on sight (see ZS-MIG-03 / ZS-MIG-05 / ZS-MIG-10)
- **Networking**
  - ZS-IO-40 [M] Build the address first; `listen`, `bind`, and `connect` are methods on it
  - ZS-IO-41 [M] A socket is an ordinary stream source — and `.limited` is not optional on one
  - ZS-IO-42 [M] Close every socket on every path; `shutdown` is how you unblock a blocked peer
- **Subprocesses**
  - ZS-IO-43 [M] `std.process.run` for the output; `std.process.spawn` for the stream
  - ZS-IO-44 [M] `child.wait(io)` closes the pipes; never close `child.stdout`/`stderr` yourself
- **Terminals and progress**
  - ZS-IO-45 [S] Decide color with `Io.Terminal`, not with your own `isatty` check
  - ZS-IO-46 [S] Report long work through `std.Progress`, and pass the node to children
- **More of the `Io.Dir` / `Io.File` surface**
  - ZS-IO-47 [S] Pick the traversal API by who decides to descend
  - ZS-IO-48 [M] Say which race you mean: `renamePreserve`, `hardLink`, `createMemoryMap`

---

## Obtaining and threading `Io`

### ZS-IO-01 [M] Obtain `Io` from `main`'s `std.process.Init`, never from a global
`std.start` builds an `Io.Threaded` for you and hands it over in `init.io`. Library code accepts an
`Io` parameter; it never manufactures one and never reaches for
`Io.Threaded.global_single_threaded`.

**Why:** the entire point of the design is that the caller chooses the backend. A library that
constructs its own `Io.Threaded` spawns a second, invisible thread pool, and a library that grabs
the global escape hatch cannot be driven by an evented or fiber-based caller at all.

**Check:** `Io.Threaded.init`, `Io.Evented.init`, or `Io.Threaded.global_single_threaded` anywhere
outside `main`, a benchmark harness, a `build.zig` step, or a test; and a `pub fn main() !void` that
performs I/O, which has no `init` to take `io` from.

```zig
// verified — GOOD
const std = @import("std");
const Io = std.Io;

pub fn main(init: std.process.Init) !void {
    const io = init.io;
    const gpa = init.gpa;

    var stdout_buffer: [4096]u8 = undefined;
    var stdout_writer = Io.File.stdout().writerStreaming(io, &stdout_buffer);
    const stdout = &stdout_writer.interface;

    try emitReport(gpa, stdout, &.{ 3, 1, 4 });
    try stdout.flush(); // buffered bytes are lost without this
}

fn emitReport(gpa: std.mem.Allocator, w: *Io.Writer, values: []const u32) Io.Writer.Error!void {
    _ = gpa;
    for (values, 0..) |v, i| try w.print("{d}: {d}\n", .{ i, v });
    try w.splatByteAll('-', 8);
    try w.writeByte('\n');
}
```

Outside `main` — a custom runtime, a benchmark harness, a `build.zig` step — construct one
explicitly and pair it with `deinit`:

```zig
// fragment
var threaded: Io.Threaded = .init(gpa, .{});
defer threaded.deinit();
const io = threaded.io();
```

`Io.Threaded.init_single_threaded` is the exception: it holds a failing allocator and
`concurrent_limit = .nothing`, so it needs no allocator and no `deinit`.

### ZS-IO-02 [M] Thread `io: Io` as an explicit parameter, using std's ordering
`Io` is a two-field fat pointer (`userdata: ?*anyopaque`, `vtable: *const VTable`) dispatched as
`io.vtable.op(io.userdata, ...)`. Pass it by value, exactly like an `Allocator`. Ordering, measured
against std: on a method of a resource type (`Dir`, `File`, `Mutex`, `Queue`) `io` comes immediately
after the receiver; on a free function `gpa` comes before `io` (12 occurrences to 3 in std), then
domain parameters, then an options struct last.

**Why:** an `Io` parameter is the only thing that makes a function's blocking behavior visible
in its signature, and it is what lets the same function run on a thread pool in production and on
`std.testing.io` or `Io.failing` in tests. Hiding it in a struct field or a global makes the
substitution impossible.

**Check:** a field of type `Io` on any struct that is not the top-level application object; a method
whose `io` parameter does not sit immediately after the receiver; a free function whose `io`
precedes its `gpa`; and an options struct that is not the last parameter.

```zig
// verified — GOOD
// receiver, then io (std's Dir/File convention)
const std = @import("std");
const Io = std.Io;
pub fn load(dir: Io.Dir, io: Io, gpa: std.mem.Allocator) Io.Dir.ReadFileAllocError![]u8 {
    return dir.readFileAlloc(io, "cfg.txt", gpa, .limited(4096));
}

// free function: gpa before io, options last
pub fn render(gpa: std.mem.Allocator, io: Io, w: *Io.Writer, opts: Options) Io.Writer.Error!void {
    _ = .{ gpa, io, w, opts };
}
const Options = struct { verbose: bool = false };
```

```zig
// fragment — BAD: io captured in a field, so the caller cannot substitute a backend
const Server = struct {
    io: std.Io, // now every method silently blocks on *this* backend
    fn tick(s: *Server) !void {
        try s.io.sleep(.fromMilliseconds(10), .awake);
    }
};
```
Capturing `io` in a long-lived struct is acceptable only for a top-level application object
constructed in `main` from `init.io`, where there is exactly one backend by construction. Anything
reusable takes it as a parameter.

### ZS-IO-03 [M] Use `std.testing.io` in tests and `Io.failing` for error paths (see ZS-TEST-09)
Owned by `references/testing-and-fuzzing.md` ZS-TEST-09. A test that performs I/O takes
`std.testing.io` — an `Io.Threaded` instance that is a `@compileError` outside `builtin.is_test` —
and reaches the error paths with `std.Io.failing`, an `Io` whose every operation fails, so error
handling is testable with no filesystem, no network, and no fault-injection harness.

### ZS-IO-04 [S] Default to `Io.Threaded`; treat `Io.Evented` as experimental
`Io.Threaded` is the production backend. `Io.Evented` resolves to `Io.Uring` on Linux, `Io.Kqueue`
on the BSDs, `Io.Dispatch` on Darwin, and `void` elsewhere.

**Why:** no `Io.Evented` backend implements networking in 0.17.0 — `Uring` and `Dispatch` wire the
`net*` vtable slots to `…Unavailable` stubs and `Kqueue`'s `listen` and `accept` are
`@panic("TODO")` — so every rule in the networking section below requires `Io.Threaded` today.
Worse, in 0.17.0 none of the three compiles once a program calls `init`: each backend's vtable
still names a slot that 0.17 removed from `Io.VTable`, so `Dispatch` and `Uring` fail with
`no field named 'processReplacePath' in struct 'Io.VTable'` and `Kqueue` with the same error for
`'fileWriteStreaming'`. Deviating becomes fine once a backend builds again and you have measured
that `Io.Threaded`'s one-thread-per-blocked-task model is your bottleneck — say so in a comment.

**Check:** `Io.Evented`, `Io.Uring`, `Io.Kqueue`, or `Io.Dispatch` named in a diff — each needs a
comment stating the measurement that justified it, and none of them may appear on a code path that
reaches `std.Io.net`, whose vtable slots they do not implement.

> [!NOTE] At 0.17.0 each backend was compiled (`zig build-obj -fno-emit-bin`) in a program that
> calls `init`, `io()`, and `deinit`, for `aarch64-macos`, `x86_64-linux`, and `x86_64-freebsd`;
> none was run, and the networking stubs are read from source. Re-check on a toolchain bump.

---

## Writing: buffer, then flush

### ZS-IO-05 [M] Flush every buffered writer before it goes out of scope
`Io.Writer` buffers into a caller-supplied `[]u8`. Data sitting in that buffer when the writer dies
is silently discarded — no error, no diagnostic, exit code 0.

**Why:** this is the single most common new-code bug since 0.16. The program below compiles cleanly,
runs cleanly, exits 0, and prints nothing.

```zig
// fragment — BAD: compiles, runs, exits 0, prints NOTHING
pub fn main(init: std.process.Init) !void {
    const io = init.io;
    var buf: [4096]u8 = undefined;
    var fw = std.Io.File.stdout().writerStreaming(io, &buf);
    try fw.interface.print("this line is silently lost\n", .{});
}
```

```zig
// fragment — GOOD
var buf: [4096]u8 = undefined;
var fw = Io.File.stdout().writerStreaming(io, &buf);
const stdout = &fw.interface;
try stdout.print("visible\n", .{});
try stdout.flush(); // last statement of the writer's lifetime
```

**Check:** for every `writerStreaming(`, `.writer(io,`, or `Io.File.Writer.init(` in a diff, a
`flush()` on every success path leaving that scope. Also any `defer w.flush() catch {}`, and any
`return` between the last `print`/`writeAll` and the `flush`.

Prefer `try w.flush()` as a real statement over `defer w.flush() catch {}`: the deferred form
swallows `error.WriteFailed`, which is exactly the disk-full / broken-pipe case you needed to know
about. A zero-length buffer (`&.{}`) means unbuffered and makes `flush` a no-op — use it
deliberately, never by accident.

### ZS-IO-06 [M] `std.debug.print` is a debugging tool, never program output
Its own doc comment describes it as "a low-level debugging primitive that bypasses the `Io`
interface": it formats through a 64-byte stack buffer that is flushed on every call, writes with the
most basic syscalls available, does not switch threads or stacks, and `catch return`s every error.

**Why:** it cannot be redirected, cannot be substituted in a test, is one syscall per call, and it
bypasses the `Io` you were handed — so under an evented backend it is the one write that does not
cooperate with the scheduler. Program output goes to a `*Io.Writer` you were given; diagnostics go
through `std.log`, which takes the stderr lock and therefore interleaves correctly with panics and
`std.Progress`.

The three destinations, and the rule for each:

| Kind | Destination | Never |
|---|---|---|
| Program output — what the program exists to produce | a `*Io.Writer` the caller handed you, then `flush()` | `std.debug.print`, `std.log` |
| Diagnostics — progress, warnings, "what is it doing" | `std.log` (scoped in a library, ZS-ERR-32) | `std.debug.print` |
| Temporary debugging you will delete before committing | `std.debug.print` | leaving it in a commit |

The same ban covers raw stderr writes: reaching stderr outside `io.lockStderr` (ZS-IO-11) or
`std.log` interleaves your bytes with a `std.Progress` redraw or a panic trace. In a **library** all
three of `std.debug.print`, `std.debug.lockStderr`, and unscoped `std.log.*` are defects — a library
does not own the process's stderr policy.

**Check:** any `std.debug.print` surviving in a diff **outside a `test` block**. In library and
application code there is no legitimate committed use: if the line is worth keeping it is
`std.log.debug`, and if it is not, delete it. Tests are the one exception — a failure diagnostic on
an `errdefer` line is required there by `references/testing-and-fuzzing.md` ZS-TEST-11, because a
test binary's stderr is captured by the build runner and `std.log` would not be attributed to the
failing test.

```zig
// fragment — BAD: program output on the diagnostic channel
std.debug.print("processed {d} rows\n", .{n});
```

```zig
// fragment — GOOD
try stdout.print("processed {d} rows\n", .{n});   // output
std.log.debug("row cursor now {d}", .{cursor});   // diagnostic
```

`references/errors-and-control-flow.md` ZS-ERR-32 (library logging through a scoped `std.log`
namespace) and `references/formatting-and-output.md` ZS-FMT-16 / ZS-FMT-17 point here for the
"never program output" half of the rule.

### ZS-IO-07 [S] `writerStreaming` for pipes and terminals, `writer` for seekable files
`File.writer(io, &buf)` and `Io.File.Writer.init(file, io, &buf)` are the same constructor and set
`.mode = .positional`. `File.writerStreaming(io, &buf)` / `Io.File.Writer.initStreaming` set
`.mode = .streaming`.

**Why:** positional writes do not disturb the shared file offset and are therefore safer under
concurrency, but a pipe or tty is never seekable. std's own comment on `initStreaming` states the
tradeoff: "Positional is more threadsafe, since the global seek position is not affected, but when
such syscalls are not available, preemptively initializing in streaming mode will skip a failed
syscall."

Both spellings are correct and both appear in std; do not "fix" one out of existence. `zig init`,
SKILL.md §2.4, and the migration chapter use the positional constructor
(`Io.File.Writer = .init(.stdout(), io, &buf)`), and that is right: the fallback to streaming on
`error.Unseekable` is automatic, so the entire cost on a pipe or tty is one failed syscall on the
first write and the output is identical. Prefer `writerStreaming` only when you *know* the handle is
a pipe or a tty and you care about that syscall. Pick by the handle you have; neither choice is a
correctness bug.

**Check:** `writerStreaming` on a handle you opened from the filesystem, or `.init`/`writer` in a
tight loop over a known-pipe handle. Both are style, not defects — a reviewer notes them, does not
block on them.

```zig
// fragment — GOOD
var out_writer = Io.File.stdout().writerStreaming(io, &out_buffer); // known pipe/tty
var log_writer = log_file.writer(io, &log_buffer);                  // seekable
var init_writer: Io.File.Writer = .init(.stdout(), io, &init_buffer); // `zig init`; also correct
```

> [!NOTE] `Io.File.Writer.initDetect(file, io, &buf)` exists in the source and looks like
> the answer to this whole question, but it **does not compile** in 0.17.0: it calls
> `Mode.detect(...)`, and `Io.File.Reader.Mode` has no `detect` member —
> `error: enum 'Io.File.Reader.Mode' has no member named 'detect'`. At 0.17.0; re-check on
> toolchain bump.

### ZS-IO-08 [M] Reusable code takes `*Io.Writer` and returns `Io.Writer.Error!void`
`Io.Writer` is already type-erased and non-generic. Never take a `File`, never take an `Io` just to
write, never make the function generic over a writer type.

**Why:** `std.Io.Writer` is a concrete struct holding `buffer: []u8` plus a vtable, so accepting
`*Io.Writer` costs nothing at the call site and works uniformly for files, sockets, in-memory
buffers, hashers, and test doubles. The 0.14-era `GenericWriter`/`AnyWriter` split no longer exists.

**Check:** a `pub fn` that writes and takes `anytype`, a `comptime Writer: type`, an `Io.File`, or
an `Io` where `*Io.Writer` would do; a write helper returning `anyerror!void` rather than
`Io.Writer.Error!void`; and any surviving `GenericWriter` or `AnyWriter` name.

```zig
// fragment — GOOD
const std = @import("std");
const Io = std.Io;
pub fn writeCsvRow(w: *Io.Writer, fields: []const []const u8) Io.Writer.Error!void {
    for (fields, 0..) |field, i| {
        if (i != 0) try w.writeByte(',');
        try w.writeAll(field);
    }
    try w.writeByte('\n');
}
```

### ZS-IO-09 [S] Build in-memory strings with `Io.Writer.Allocating`
`Allocating` grows its own buffer, exposes `written()`, `toOwnedSlice()`, and `toArrayList()`, and
has a no-op `flush`.

**Why:** it is one allocation strategy and one error path instead of an `ArrayList` plus manual
`appendSlice`/`print` bookkeeping, and it is what `Allocator.print` is implemented in terms of.
Deviate for a single `print` (use `gpa.print`, 0.16's `std.fmt.allocPrint`) or a size you can bound
(use `std.mem.print`, 0.16's `std.fmt.bufPrint`, over a fixed array).

**Check:** an `std.ArrayList(u8)` built up by alternating `appendSlice` with `gpa.print` (or the
deprecated `std.fmt.allocPrint`) results — that is `Allocating` written out longhand, plus a
temporary per `print`. Also `error.WriteFailed` escaping an `Allocating` call site without being
mapped back to `error.OutOfMemory`.

```zig
// verified — GOOD
const std = @import("std");
const Io = std.Io;
test "writer allocating" {
    const gpa = std.testing.allocator;
    var aw: Io.Writer.Allocating = .init(gpa);
    defer aw.deinit();
    try aw.writer.print("{s}={d}\n", .{ "x", 7 });
    try std.testing.expectEqualStrings("x=7\n", aw.written());
}
```

`Allocating`'s error surface is `Io.Writer.Error`, so allocation failure arrives as
`error.WriteFailed`. Map it back at the boundary the way std does:

```zig
// fragment
aw.writer.print(fmt, args) catch |err| switch (err) {
    error.WriteFailed => return error.OutOfMemory,
};
```

### ZS-IO-10 [M] Recover the real error from the concrete writer/reader
`error.WriteFailed` and `error.ReadFailed` are placeholders. The actual OS error is stored on the
concrete struct: `File.Writer.err`, `File.Reader.err`, `net.Stream.Writer.err`.

**Why:** `*Io.Writer` is type-erased, so its error set cannot name `error.NoSpaceLeft` or
`error.BrokenPipe`. Propagating `error.WriteFailed` to the user throws away every actionable
diagnostic. `File.Writer.flush(w)` — the concrete method, not `w.interface.flush()` — does this
unwrapping for you.

**Check:** `error.WriteFailed` or `error.ReadFailed` returned to a caller, logged, or printed in a
diagnostic without the concrete `.err` field being read first; and `fw.interface.flush()` written
where the concrete `fw.flush()` is in scope.

```zig
// verified — GOOD
const std = @import("std");
test "concrete error beats WriteFailed" {
    const io = std.testing.io;
    var tmp = std.testing.tmpDir(.{});
    defer tmp.cleanup();
    const file = try tmp.dir.createFile(io, "log.txt", .{});
    defer file.close(io);

    var buf: [64]u8 = undefined;
    var fw = file.writer(io, &buf);
    fw.interface.writeAll("hi\n") catch |err| switch (err) {
        // `File.Writer.drain` assigns `fw.err` on every path that returns
        // error.WriteFailed, so the fallback is unreachable in practice — and
        // spelling it costs nothing.
        error.WriteFailed => return fw.err orelse error.WriteFailed,
    };
    try fw.flush(); // File.Writer.flush surfaces the concrete error, not WriteFailed
}
```

### ZS-IO-11 [M] Write application stderr through `io.lockStderr`
`io.lockStderr(&buffer, null)` returns a `LockedStderr` with a `file_writer` field;
`io.unlockStderr()` releases it and flushes.

**Why:** `std.log`, the panic handler, and `std.Progress` all take the same lock. Writing to stderr
outside it interleaves your bytes with a progress bar's escape sequences or a panic trace.
`std.debug.lockStderr` is the `Io`-bypassing variant reserved for debugging.

**Check:** any write reaching `Io.File.stderr()` that is not inside an `io.lockStderr` /
`io.unlockStderr` pair, and any `lockStderr` whose `defer io.unlockStderr()` is not on the very next
line (ZS-MEM-11).

```zig
// fragment — GOOD
var stderr_buffer: [256]u8 = undefined;
const locked = try io.lockStderr(&stderr_buffer, null);
defer io.unlockStderr(); // unlockStderr flushes; no manual flush needed
try locked.file_writer.interface.writeAll("done\n");
```

---

## Reading

### ZS-IO-12 [M] Size the reader buffer deliberately — it is your maximum token length
`Io.Reader` reads into a caller-supplied `[]u8`. `takeDelimiter`, `peek`, and friends return
`error.StreamTooLong` when the delimiter is not found within that buffer, leaving the stream
unmodified.

**Why:** the buffer length *is* the bound on a line, a header, or a record. This is where
TigerStyle's "all loops and queues have a fixed upper bound" rule lands in 0.17 I/O code: choosing
`var buf: [4096]u8` is choosing a 4 KiB maximum line, and a hostile 4 GiB line without a newline
becomes `error.StreamTooLong` instead of an OOM.

```zig
// verified — GOOD
const std = @import("std");
const Io = std.Io;
test "StreamTooLong when the reader buffer cannot hold a line" {
    var r: Io.Reader = .fixed("a-very-long-line-with-no-newline-at-all\n");
    var small: [8]u8 = undefined;
    var limited = r.limited(.unlimited, &small);
    try std.testing.expectError(error.StreamTooLong, limited.interface.takeDelimiter('\n'));
}
```

**Check:** any reader buffer whose size is not justified by a comment or a named constant, and any
`takeDelimiter`/`peek` call site that does not handle `error.StreamTooLong` distinctly from a real
I/O failure — silently treating an over-long line as EOF truncates input.

Where that size must come from a *named* compile-time constant rather than a commented literal is
ZS-IO-38 `[M!]`, which owns that requirement for buffers, queues, and every other caller-provided
fixed array.

### ZS-IO-13 [M] Iterate lines with `takeDelimiter`, never `takeDelimiterExclusive`
`takeDelimiter(r, '\n')` returns `?[]u8`, advances *past* the delimiter, treats EOF as a delimiter
(so a final line without a newline is still returned), and has no `EndOfStream` in its error set.

**Why:** `takeDelimiterExclusive` advances *up to but not past* the delimiter. Looping on it yields
the first line and then an infinite stream of zero-length slices — a hang, not a crash.

**Check:** `takeDelimiterExclusive` appearing anywhere inside a `while` — the loop is the bug, not
the call. A single call followed by an explicit discard of the delimiter is the only correct use,
and it needs a comment saying so.

On 0.17.0:

```zig
// fragment — BAD: infinite loop after the first line
var r: Io.Reader = .fixed("alpha\nbeta\n");
try expectEqualStrings("alpha", try r.takeDelimiterExclusive('\n'));
try expectEqualStrings("", try r.takeDelimiterExclusive('\n')); // '\n' still buffered
```

```zig
// verified — GOOD
const std = @import("std");
const Io = std.Io;
test "line iteration" {
    var r: Io.Reader = .fixed("alpha\nbeta\ngamma"); // note: no trailing newline
    var count: usize = 0;
    while (try r.takeDelimiter('\n')) |line| {
        _ = line;
        count += 1;
    }
    try std.testing.expectEqual(3, count); // "gamma" is returned too
}
```

### ZS-IO-14 [M] Treat slices from `peek`/`take`/`takeDelimiter` as borrowed until the next fill
They point into the reader's buffer. The next `fill`, `peek`, `take`, or `rebase` may move or
overwrite them.

**Why:** the reader compacts its buffer in place (`defaultRebase` `@memmove`s the retained bytes to
offset 0). A "line" you stashed from iteration two is silently different bytes by iteration three —
data corruption with no memory-safety violation for the allocator to catch.

**Check:** a slice returned by `peek`, `take`, `takeDelimiter`, or `takeDelimiterExclusive` bound to
a name that survives the next call on that same reader — appended to a list, stored in a field,
returned from the function, or compared across loop iterations — with no `dupe` in between.

```zig
// verified — GOOD
const std = @import("std");
const Io = std.Io;
test "take slices are invalidated by the next fill" {
    const gpa = std.testing.allocator;
    var r: Io.Reader = .fixed("first\nsecond\n");
    // `takeDelimiter` returns null only at end of stream, and this fixed
    // reader still holds "first\n".
    const first = (try r.takeDelimiter('\n')) orelse return error.TestUnexpectedResult;
    // Copy before reading more; `first` points into r.buffer.
    const kept = try gpa.dupe(u8, first);
    defer gpa.free(kept);
    _ = try r.takeDelimiter('\n');
    try std.testing.expectEqualStrings("first", kept);
}
```

### ZS-IO-15 [M] Give every read-all API an explicit `Io.Limit`
`allocRemaining`, `appendRemaining`, `readFileAlloc`, and `Reader.limited` all take an
`Io.Limit`. Spell it `.limited(n)` with a justified `n`; reserve `.unlimited` for data you produced
yourself.

**Why:** `Io.Limit` is the type system forcing TigerStyle's bounded-work rule on you at every
untrusted-input boundary. `.unlimited` on a network stream is an unbounded allocation controlled by
the peer.

**Check:** `.unlimited` passed to `allocRemaining`, `appendRemaining`, `readFileAlloc`, or
`Reader.limited` on bytes this process did not produce itself. A `.limited(n)` whose `n` is a bare
literal rather than a named constant is the milder, separate ZS-IO-38 finding.

```zig
// fragment — GOOD
const text = try tmp.dir.readFileAlloc(io, "cfg.txt", gpa, .limited(1 << 20));
defer gpa.free(text);
```

```zig
// verified — GOOD
const std = @import("std");
const Io = std.Io;
test "limit" {
    var r: Io.Reader = .fixed("0123456789");
    var lim_buf: [4]u8 = undefined;
    var limited = r.limited(.limited(4), &lim_buf);
    const all = try limited.interface.allocRemaining(std.testing.allocator, .unlimited);
    defer std.testing.allocator.free(all);
    try std.testing.expectEqualStrings("0123", all);
}
```

### ZS-IO-16 [S] Stream large data; only read whole objects you have already bounded
`w.sendFileAll(&file_reader, .unlimited)` uses the kernel's fd-to-fd path (sendfile,
copy_file_range, fcopyfile) and falls back to a read/write loop on `error.Unimplemented`
automatically.

**Why:** a copy loop through userspace costs two copies per byte and a peak RSS proportional to the
file. `sendFileAll` costs a bounded buffer. Deviate when you need to inspect or transform the bytes.

**Check:** a hand-written read-into-buffer / write-out loop between two `File`s whose body does
nothing to the bytes — that is `sendFileAll`. Also `readFileAlloc` or `allocRemaining` over a whole
file that is only being copied onward.

```zig
// fragment — GOOD
var read_buffer: [8]u8 = undefined;
var write_buffer: [8]u8 = undefined;
var fr = source.reader(io, &read_buffer);
var fw = target.writer(io, &write_buffer);
_ = try fw.interface.sendFileAll(&fr, .unlimited); // asserts fw buffer is nonempty
try fw.interface.flush();
```

---

## Authoring custom streams

### ZS-IO-17 [M] Embed the interface as a field; recover the parent with `@fieldParentPtr`
Name the field `interface` (std's convention on `File.Writer`, `File.Reader`, `Limited`,
`Decompress`) and cast back with `@alignCast(@fieldParentPtr("interface", w))`.

**Why:** `Io.Writer`/`Io.Reader` carry no userdata pointer — the vtable functions receive only the
interface pointer. `@fieldParentPtr` is the whole mechanism, and it only works if the interface is a
by-value field of your struct rather than a pointer to one.

**Check:** a custom stream type whose interface field is declared `*Io.Writer`/`*Io.Reader` rather
than by value, or named anything but `interface`. A `@fieldParentPtr` with no `@alignCast` is a
**note, not a defect**: 75 of std's 172 call sites omit it at 0.17.0, including
`Io/Reader/Limited.zig`. Ask for it in new code (ZS-CT-23) and let it go on code that already
compiles — the compiler rejects the cases where it was actually required.

### ZS-IO-18 [M] Implement `drain` to the full contract
Only `drain` is required (`sendFile`, `flush`, `rebase` have defaults). A correct `drain`:
(1) emits `w.buffered()` first and clears it via `w.consume(n)`/`w.consumeAll()`;
(2) emits each element of `data` in order; (3) emits the **last** element `splat` additional times;
(4) returns the count consumed **from `data` only**, excluding buffer bytes.

**Why:** each of those four is a real corruption bug if you get it wrong. Skipping (1) reorders the
stream. Assuming `data.len == 1` drops vectored writes. Ignoring `splat` turns
`splatByteAll('-', 1_000_000)` into one dash. Counting buffer bytes in the return value makes the
caller believe more of `data` was written than actually was, silently truncating output.

**Check:** read the `drain` body against the four numbered clauses — no `w.buffered()` before the
first emit; `data[0]` indexed instead of iterated; the `splat` parameter unused (grep: `_ = splat`);
or the returned count accumulating anything emitted from `w.buffered()`. Each is one line to spot.

```zig
// verified — GOOD
/// A `Writer` that uppercases ASCII on its way to `sink`.
const std = @import("std");
const Io = std.Io;
const UpperWriter = struct {
    interface: Io.Writer,
    sink: *Io.Writer,

    fn init(sink: *Io.Writer, buffer: []u8) UpperWriter {
        return .{
            .sink = sink,
            .interface = .{ .vtable = &.{ .drain = drain }, .buffer = buffer },
        };
    }

    fn drain(w: *Io.Writer, data: []const []const u8, splat: usize) Io.Writer.Error!usize {
        const uw: *UpperWriter = @alignCast(@fieldParentPtr("interface", w));
        // 1. The writer's own buffer is logically earlier in the stream: emit it first.
        try uw.emit(w.buffered());
        _ = w.consumeAll();
        // 2. Then every slice of `data` in order...
        var consumed: usize = 0;
        for (data[0 .. data.len - 1]) |bytes| {
            try uw.emit(bytes);
            consumed += bytes.len;
        }
        // 3. ...with the LAST slice repeated `splat` times. `splat` may be 0.
        const pattern = data[data.len - 1];
        for (0..splat) |_| {
            try uw.emit(pattern);
            consumed += pattern.len;
        }
        // 4. Return bytes consumed from `data` only — never counting buffer bytes.
        return consumed;
    }

    fn emit(uw: *UpperWriter, bytes: []const u8) Io.Writer.Error!void {
        for (bytes) |c| try uw.sink.writeByte(std.ascii.toUpper(c));
    }
};
```

Override `flush` with `Io.Writer.noopFlush` only if your sink has no residual state (`Allocating`
does this). Override `rebase` only if your buffer can grow or must never move. Override `sendFile`
only if you have a genuine fd-to-fd fast path; the default returns `error.Unimplemented`, which
callers handle.

### ZS-IO-19 [M] A custom `Reader` signals end of stream with `error.EndOfStream`, never `0`
Only `stream` is required. A `0` return means "no progress this call", typically because the
implementation filled `r.buffer` and bumped `seek`/`end` instead of writing to `w`.

**Why:** `0` and EOF are distinct states in this API. Returning `0` at EOF turns every
`allocRemaining`/`streamRemaining` caller into an infinite loop.

**Check:** a `return 0;` in a `stream` implementation. It is legal only on the path that filled
`r.buffer` and advanced `end`; on any exhaustion path it must be `return error.EndOfStream;`. A
`stream` whose error set does not name `EndOfStream` at all is the same finding.

```zig
// verified — GOOD
const std = @import("std");
const Io = std.Io;
const RepeatReader = struct {
    interface: Io.Reader,
    byte: u8,
    remaining: usize,

    fn init(byte: u8, count: usize, buffer: []u8) RepeatReader {
        return .{
            .byte = byte,
            .remaining = count,
            .interface = .{
                .vtable = &.{ .stream = stream },
                .buffer = buffer,
                .seek = 0,
                .end = 0,
            },
        };
    }

    fn stream(r: *Io.Reader, w: *Io.Writer, limit: Io.Limit) Io.Reader.StreamError!usize {
        const rr: *RepeatReader = @alignCast(@fieldParentPtr("interface", r));
        // End of stream is `error.EndOfStream`, never a 0 return.
        if (rr.remaining == 0) return error.EndOfStream;
        const n = limit.minInt(rr.remaining);
        const written = try w.splatByte(rr.byte, n);
        rr.remaining -= written;
        return written;
    }
};
```

### ZS-IO-20 [M] Pair `writableSliceGreedy` with `advance`; never `advance` after `writableSlice`
`writableArray(len)` and `writableSlice(len)` advance by `len` before returning.
`writableSliceGreedy(min)` returns all unused capacity and does **not** advance — you must call
`w.advance(n)`.

**Why:** getting this backwards either duplicates bytes or writes into a region the writer already
considers written. It is a silent data bug with no compile error.

**Check:** a `writableSliceGreedy` with no `w.advance(n)` before the next write on that writer, and
an `advance` following a `writableSlice`/`writableArray`, both of which advanced already. Grep the
three names and pair each with the presence or absence of `advance`.

```zig
// verified — GOOD
const std = @import("std");
const Io = std.Io;
test "zero copy writes: advance semantics differ" {
    var aw: Io.Writer.Allocating = .init(std.testing.allocator);
    defer aw.deinit();
    const w = &aw.writer;

    const target = try w.writableSlice(4); // already advanced by 4
    @memcpy(target, "1234");

    const greedy = try w.writableSliceGreedy(2); // NOT advanced
    @memcpy(greedy[0..2], "56");
    w.advance(2); // you must advance yourself

    try std.testing.expectEqualStrings("123456", aw.written());
}
```

---

## Filesystem

### ZS-IO-21 [M] `std.fs` is a deprecation shim — use `std.Io.Dir` and `std.Io.File`
`std/fs.zig` is 21 lines, every member marked `/// Deprecated`. `std.fs.Dir`, `std.fs.File`, and
`std.fs.cwd()` do not exist at all: `struct 'fs' has no member named 'cwd'`. Every
filesystem operation now takes an `io`.

**Why:** the filesystem was absorbed into `Io` so that a caller can substitute a backend — an
io_uring ring, a fiber scheduler, `Io.failing` in a test. A `std.fs`-shaped API could not express
that. The surviving aliases are `std.fs.path` → `std.Io.Dir.path`, `std.fs.max_path_bytes` →
`std.Io.Dir.max_path_bytes`, `std.fs.max_name_bytes` → `std.Io.Dir.max_name_bytes`.

**Check:** the prefix `std.fs.` anywhere except those three aliases; the names `makeDir`,
`makePath`, `getEndPos`, `setEndPos`, `realpath`, or `fs.File.Mode`; and any filesystem call that
takes no `io` argument — that alone identifies pre-0.16 code.

```zig
// verified — GOOD
const std = @import("std");
test "filesystem roundtrip" {
    const io = std.testing.io;
    const gpa = std.testing.allocator;
    var tmp = std.testing.tmpDir(.{});
    defer tmp.cleanup();

    try tmp.dir.writeFile(io, .{ .sub_path = "cfg.txt", .data = "a=1\nb=2\n" });
    const text = try tmp.dir.readFileAlloc(io, "cfg.txt", gpa, .limited(1 << 20));
    defer gpa.free(text);
    try std.testing.expectEqualStrings("a=1\nb=2\n", text);
}
```

Name mapping worth memorizing: `makeDir`/`makePath` → `createDir`/`createDirPath`;
`getEndPos`/`setEndPos` → `File.length(io)`/`File.setLength(io, n)`; `realpath` →
`realPathFile(io, sub_path, out_buffer) -> usize`; `fs.File.Mode` → `Io.File.Permissions`.

### ZS-IO-22 [M] Pair every open with `defer close(io)`, and iterate with the iterator's own buffer
`file.close(io)` and `dir.close(io)` both take the `Io`. `dir.iterate()` returns an `Iterator` that
embeds a 2 KiB buffer, so `it.next(io)` takes no buffer argument.

**Why:** a `Dir` is a file descriptor exactly like a `File`; leaking directory handles exhausts the
per-process fd quota just as fast, and the failure surfaces far from the leak as
`error.ProcessFdQuotaExceeded` on some unrelated open. The `Iterator` is ~2 KiB of stack because it
inlines its own `reader_buffer` (`next` re-points `reader.buffer` at it on every call, so the value
is movable) — bind it with `var` in the loop's own scope rather than nesting it inside a recursive
walk. For recursive traversal, and for the allocation-free `Io.Dir.Reader` beneath `Iterator`, see
ZS-IO-47.

**Check:** an `openFile`/`openDir`/`createFile`/`createFileAtomic` result whose next line is not
`defer ….close(io)` or `defer ….deinit(io)`; a `close()` written without an `io` argument; and an
`Io.Dir.Iterator` stored in a struct field or returned from a function rather than bound to a `var`
in the loop's own scope.

```zig
// verified — GOOD
const std = @import("std");
test "directory iteration" {
    const io = std.testing.io;
    var tmp = std.testing.tmpDir(.{});
    defer tmp.cleanup();
    try tmp.dir.writeFile(io, .{ .sub_path = "a.txt", .data = "" });
    try tmp.dir.writeFile(io, .{ .sub_path = "b.txt", .data = "" });

    var it = tmp.dir.iterate(); // ~2 KiB of stack: it inlines its own read buffer
    var count: usize = 0;
    while (try it.next(io)) |entry| {
        if (entry.kind == .file) count += 1;
    }
    try std.testing.expectEqual(2, count);
}
```

### ZS-IO-23 [M!] Replace files atomically with `createFileAtomic` + `replace`
`dir.createFileAtomic(io, sub_path, .{ .replace = true })` returns a `File.Atomic` holding an
unnamed ephemeral file. Write, flush, then `af.replace(io)`. `af.link(io)` is the create-if-absent
variant; `.replace` in the options must match which one you will call, or `replace` asserts.

**Why:** truncating a file in place has a window in which the file is empty or half-written. If the
process dies there, the on-disk state is unrecoverable — the old contents are already gone and the
new ones are not there yet.

**`[M!]` trigger:** the file is authoritative state that some later reader depends on — databases
and WALs, configuration a service reads at boot, key material, lockfiles, anything another process
reads concurrently. ***Relaxed form:*** a file that is regenerated from scratch on every run — a
build artifact, a cache, a scratch file — may use plain `writeFile`; but a file that is *updated*,
meaning read, modified, and written back, still goes through `createFileAtomic` + `replace` at every
tier, because the pre-write contents are the only copy of the data being replaced.

**Check:** a `writeFile` or a truncating `createFile` on a path the program also reads on a later
run. The atomic form has three parts, so also flag a `createFileAtomic` with no `af.replace(io)` or
`af.link(io)` reached, and one whose `.replace` option disagrees with which of the two is called —
that mismatch is an assertion failure, not a compile error.

```zig
// verified — GOOD
const std = @import("std");
test "atomic replace" {
    const io = std.testing.io;
    var tmp = std.testing.tmpDir(.{});
    defer tmp.cleanup();

    try tmp.dir.writeFile(io, .{ .sub_path = "state.json", .data = "old" });

    var af = try tmp.dir.createFileAtomic(io, "state.json", .{ .replace = true });
    defer af.deinit(io);
    var buf: [64]u8 = undefined;
    var fw = af.file.writer(io, &buf);
    try fw.interface.writeAll("new");
    try fw.interface.flush();
    try af.replace(io);

    var read_buf: [16]u8 = undefined;
    try std.testing.expectEqualStrings("new", try tmp.dir.readFile(io, "state.json", &read_buf));
}
```

`af.deinit(io)` is safe to `defer` unconditionally: it removes the ephemeral file if
`replace`/`link` was never reached.

---

## Structured concurrency

### ZS-IO-24 [M] Every started `Future` is awaited or canceled exactly once, on every path
`io.async(f, args)` returns a `Future(R)` — `await` and `cancel` are idempotent but **not**
threadsafe. An early `return` that skips remaining futures abandons them.

**Why:** under `Io.Threaded` each future is a heap allocation plus a claimed slot against
`async_limit`; abandoning it leaks both and leaves a worker writing into a result slot whose stack
frame is gone. The correct fan-out shape awaits *all* futures and only then propagates the first
error.

**Check:** a `try` on the `await` inside a fan-out loop.
`for (&futures) |*f| total += try f.await(io);` is the canonical shape of the bug. More generally,
any `try`, `return`, or `break` between an `io.async` and the `await`/`cancel` of every future it
started, and any `io.async` whose result is discarded with `_ =`.

```zig
// fragment — BAD: `try` inside the loop abandons futures 1..n
for (&futures) |*f| total += try f.await(io);
```

```zig
// verified — GOOD
const std = @import("std");
const assert = std.debug.assert;
const Io = std.Io;
const FetchError = error{Broken} || Io.Cancelable;

fn fetchShard(io: Io, index: u32) FetchError!u32 {
    try io.sleep(.fromMilliseconds(1), .awake);
    if (index == 3) return error.Broken;
    return index * index;
}

/// Spawn N tasks, await ALL of them, propagate the first error.
fn fetchAll(io: Io, out: []u32) FetchError!void {
    var futures: [8]Io.Future(FetchError!u32) = undefined;
    assert(out.len <= futures.len);

    for (out, 0..) |_, i| futures[i] = io.async(fetchShard, .{ io, @as(u32, @intCast(i)) });

    // Every started future must be awaited exactly once, even on the error path,
    // otherwise its task and its args tuple outlive this stack frame.
    var first_error: ?FetchError = null;
    for (out, 0..) |*slot, i| {
        if (futures[i].await(io)) |value| slot.* = value else |err| {
            if (first_error == null) first_error = err;
        }
    }
    if (first_error) |err| return err;
}
```

Note the shape of the call: `io.async(function, args_tuple)` — arguments go in a tuple, `Io` itself
is usually the first of them. `async` and `await` are no longer language keywords, which is why
`io.async` and `f.await(io)` are ordinary declarations.

### ZS-IO-25 [S] Prefer `io.async`; use `io.concurrent` only for simultaneous progress
`io.async` guarantees only "already completed, or assigned a unit of concurrency" — it may run the
function inline before returning. `io.concurrent` demands real concurrency and can fail with
`error.ConcurrencyUnavailable`.

**Why:** `io.async` never fails; `Io.Threaded` degrades to inline execution on OOM or when
`async_limit` is reached (`Io/Threaded.zig`). That makes `async` compatible with
single-threaded stackful backends and with `init_single_threaded`. But it also means a producer
spawned with `async` may run to completion *before* the consumer starts — which deadlocks on a
bounded `Io.Queue`. Any two tasks that must interleave need `concurrent`.

**Check:** an `io.async` on one side of an `Io.Queue`, `Io.Mutex`, `Io.Condition`, or `Io.Event`
whose other side is in the calling task — that deadlocks the moment the backend runs the task
inline. Conversely, an `io.concurrent` used for plain fan-out where nothing has to interleave: that
is `io.async`, which cannot fail.

```zig
// verified — GOOD: producer and consumer must interleave over a 2-slot queue
const std = @import("std");
const Io = std.Io;
fn produce(io: Io, q: *Io.Queue(u32)) void {
    defer q.close(io);
    for (0..4) |i| q.putOne(io, @intCast(i)) catch return;
}

test "queue producer consumer" {
    const io = std.testing.io;

    var storage: [2]u32 = undefined;
    var q: Io.Queue(u32) = .init(&storage);
    var producer = try io.concurrent(produce, .{ io, &q });
    defer producer.await(io);

    var total: u32 = 0;
    while (q.getOne(io)) |item| total += item else |err| switch (err) {
        error.Closed => {},
        error.Canceled => return err,
    }
    try std.testing.expectEqual(6, total);
}
```

### ZS-IO-26 [S] Pick the right aggregate: `Group`, `Select`, or `Queue`
`Io.Group` is an unordered task set whose members return something coercible to `Cancelable!void`;
it is a cancellation-propagation boundary, so a member returning `error.Canceled` is absorbed.
`Io.Select(U)` waits on the first of several heterogeneous tasks, keyed by the fields of a tagged
union. `Io.Queue(T)` is a bounded MPMC channel closed with `q.close(io)`.

**Why:** `Group` releases each task's resources when *that task* returns, not when the group
completes, so a long-lived group is not a leak — but async tasks are not guaranteed to run until
`await`/`cancel`, so an abandoned group is. `Select`'s buffer must be large enough for all
outstanding tasks or `cancel` deadlocks.

**Check:** an `Io.Group` with a path out of its scope that reaches neither `g.await(io)` nor
`g.cancel(io)`; an `Io.Select` whose storage array is shorter than the number of tasks that can be
outstanding at once; and an `Io.Queue` with no `q.close(io)` on the producer's exit path, which
leaves the consumer waiting for an item that will never arrive.

```zig
// verified — GOOD
const std = @import("std");
const Io = std.Io;
fn bump(counter: *std.atomic.Value(u32)) void {
    _ = counter.fetchAdd(1, .monotonic);
}

test "group" {
    const io = std.testing.io;
    var counter: std.atomic.Value(u32) = .init(0);
    var g: Io.Group = .init;
    for (0..8) |_| g.async(io, bump, .{&counter});
    try g.await(io);
    try std.testing.expectEqual(8, counter.load(.monotonic));
}
```

```zig
// verified — GOOD: `cancel` is the abandonment-safe exit
const std = @import("std");
const Io = std.Io;
fn worker(io: Io) Io.Cancelable!void {
    try io.sleep(.fromSeconds(60), .awake);
}

test "cancel a group instead of abandoning it" {
    const io = std.testing.io;

    var g: Io.Group = .init;
    for (0..2) |_| try g.concurrent(io, worker, .{io});
    g.cancel(io); // error.Canceled from members is absorbed by the group
}
```

### ZS-IO-27 [M] Never ignore `error.Canceled`
A cancellation point is any `Io` call whose error set contains `error.Canceled`. After a cancel
request, **only the next** cancellation point signals it; later ones do not re-signal. Respond by
propagating, by `io.recancel()` and continuing, or by entering cancel protection.

One exemption, and only one: a cleanup on a path that is **already leaving** — a `defer`/`errdefer`
body, or a statement on an error path with nothing after it but the `return` — cannot strand anyone,
because no further work follows either way. Log the error there rather than discarding it silently
(ZS-ERR-11), or wrap the cleanup in cancel protection when it must actually happen.

std draws the line in the same place but stops short of logging: a bare `catch {}` on a cancelable
unlink appears in `std.testing.TmpDir.cleanup` (its `deleteTree`), `std.Io.File.Atomic.deinit`, and
the `testGetCurrentFileTimestamp` helper in `std.Build.Cache` — always on a leaving path, never
mid-flow. Read those as evidence for *where* the exemption lies, not as licence for the bare form;
this standard still wants it logged.

**Why:** swallowing the one signal you get converts a cancellation request into a task that runs
forever, and `Group.await`/`Future.cancel` then block indefinitely waiting for it. Note the tell is
not the *shape* of the `catch` — `catch |err| log.warn(…)` strands a canceller exactly as `catch {}`
does, because logging *without propagating* is not responding. (Logging and then returning the error
is fine; that is ZS-ERR-08's "add context, then propagate".) What matters is whether control then
goes on to do more work.

**Check:** any `catch` on an expression taking an `io` — `catch {}`, `catch return`, `catch
continue`, `catch unreachable`, **or `catch |err| log…`** — after which the function keeps working;
and a `switch` over an `Io` error set with an `else => {}` arm, which absorbs `error.Canceled`
without naming it. The legal responses all name it: propagate, `io.recancel()`, or enter cancel
protection. A cleanup on a path that is already leaving is exempt per the exemption above.

```zig
// fragment — BAD
io.sleep(.fromSeconds(1), .awake) catch {}; // cancellation request silently dropped
```

```zig
// verified — GOOD: cleanup that must not be interrupted
const std = @import("std");
const Io = std.Io;
test "cancel protection around cleanup" {
    const io = std.testing.io;
    const old = io.swapCancelProtection(.blocked);
    defer _ = io.swapCancelProtection(old);
    var m: Io.Mutex = .init;
    m.lockUncancelable(io);
    m.unlock(io);
}
```

### ZS-IO-28 [M!] Call `io.checkCancel()` inside long CPU-bound loops
`checkCancel` is a pure cancellation point that performs no I/O.

**Why:** cancellation only takes effect at cancellation points. A loop that does no I/O is
uninterruptible, so a shutdown, a deadline, or a watchdog cannot preempt it — the task keeps burning
a carrier thread while whoever requested the cancel blocks in `await`. Check on a power-of-two
stride so the check itself is not the cost.

**`[M!]` trigger:** the system has a shutdown path, a request deadline, or a watchdog — servers,
databases, consensus nodes, anything long-running that must be able to stop on demand.
***Relaxed form:*** elsewhere, put a `checkCancel` in any loop whose trip count comes from input, a
file, or the network rather than from a compile-time constant; a loop bounded by a named `_max` may
skip it, because its worst-case duration is already known and reviewable.

**Check:** a loop with no `io.*` call anywhere in its body whose bound is not a small compile-time
constant, and no `io.checkCancel()` on a stride inside it. Grep the diff for `while (true)` and for
`for (0..` over a runtime length in a function that takes an `io`.

```zig
// verified — GOOD
const std = @import("std");
const Io = std.Io;
fn grind(io: Io, iterations: usize) Io.Cancelable!u64 {
    var acc: u64 = 0;
    for (0..iterations) |i| {
        if (i % 1024 == 0) try io.checkCancel();
        acc +%= i;
    }
    return acc;
}
```

### ZS-IO-29 [M] Use the `*Uncancelable` variants in `defer` and cleanup paths
`Mutex.lockUncancelable`, `RwLock.lockUncancelable`, `RwLock.lockSharedUncancelable`,
`Condition.waitUncancelable`, `Event.waitUncancelable`, `Semaphore.waitUncancelable`,
`Queue.putUncancelable` / `putOneUncancelable` / `getUncancelable` / `getOneUncancelable`, and
`io.futexWaitUncancelable`. Those 11 names are the whole callable surface for 0.17. A grep counts 14
`pub fn *Uncancelable` — the other three are `TypeErasedQueue.putUncancelable`/`getUncancelable`,
which are the untyped layer `Queue` forwards into rather than separate APIs, and
`noFutexWaitUncancelable`, an internal vtable stub taking `userdata: ?*anyopaque` — from
`Io.zig`, `Io/RwLock.zig`, and `Io/Semaphore.zig`. 0.17 adds `Semaphore.waitTimeout(io, timeout)`,
which is cancelable and has no uncancelable timed form, so it never belongs in a `defer`.

**Why:** a `defer` body cannot propagate an error, so a cancelable blocking call inside one — a lock
acquisition, a queue hand-off, an event wait — has no correct failure handling; you would have to
`catch unreachable` on a reachable condition. The `Uncancelable` variants return `void` (or drop
`Cancelable` from the set, as the `Queue` pair do) and are the intended tool.

**Check:** a `defer` or `errdefer` body calling the *cancelable* spelling of any primitive on the
list above — `m.lock(io)`, `rw.lock(io)`, `rw.lockShared(io)`, `c.wait(io, …)`, `e.wait(io)`,
`sem.wait(io)`, `q.put(io, …)` / `putOne` / `get` / `getOne`, `io.futexWait(…)` — and any
`catch unreachable` or `catch {}` wrapped around one of those calls. Both are the same finding
wearing different clothes: the `catch` is there only to paper over the wrong spelling.

Scope: this rule is about primitives that *have* a correct uncancelable form. A `defer` cleanup with
no such twin — `dir.deleteFile(io, path)`, which has no `deleteFileUncancelable` — is governed by
ZS-IO-27's already-leaving exemption instead, not by this rule. Do not report it here.

### ZS-IO-30 [M] Synchronize with the `Io` primitives, never OS primitives
`std.Thread` has **no** synchronization primitives in 0.17 — no `Mutex`, `Condition`,
`Semaphore`, `RwLock`, `ResetEvent`, `WaitGroup`, `Pool`, or `Futex`. All of them moved to `std.Io`
and take an `io`. There is no `Io.Futex` type — `futexWait`/`futexWake` are free functions on `Io`.

**Why:** this is correctness, not taste. An OS mutex blocks the whole carrier thread. Under an
evented or fiber backend, that thread is running other tasks — including, potentially, the task
holding the lock. The result is a deadlock that only manifests on the non-default backend.
`std.atomic.Mutex` is a lock-free `tryLock`/`unlock` pair with no blocking `lock`; it is not a
substitute.

**Check:** `std.Thread.Mutex`, `.Condition`, `.Semaphore`, `.RwLock`, `.ResetEvent`, `.WaitGroup`,
`.Pool`, or `.Futex` in a diff — all are compile errors in 0.17 (`has no member named 'Mutex'`),
and none of the messages names the `std.Io` replacement, so name it in the review.
`std.atomic.Mutex` is the one that *does* compile and is still the finding: it has no blocking
`lock`, so a `while (!m.tryLock()) {}` around it is a spin that no scheduler can preempt.

```zig
// fragment — GOOD
const std = @import("std");
const Io = std.Io;
fn addLocked(io: Io, m: *Io.Mutex, n: u64) Io.Cancelable!void {
    try m.lock(io);
    defer m.unlock(io);
    shared_total += n;
}
```

### ZS-IO-31 [M] Write colorless code: never branch on which backend you were handed
The same function body must be correct under `Io.Threaded`, `Io.Evented`, `init_single_threaded`,
and `Io.failing`. Do not inspect `io.userdata`, do not compare `io.vtable`, do not gate behavior on
`builtin.single_threaded`.

**Why:** the colorless property — no `async fn` infection, no duplicated sync/async APIs — exists
precisely because the function is written once against the `Io` interface and the *caller* chooses
the execution model. Every backend test (`std.testing.io` today, an io_uring ring tomorrow) depends
on that. The only backend-dependent behavior you may rely on is the documented one:
`io.concurrent` may return `error.ConcurrencyUnavailable`, and you must handle it.

**Check:** `io.userdata`, `io.vtable`, `@TypeOf(io)`, or `builtin.single_threaded` read anywhere
inside a function that also performs I/O; and any `if`/`switch` selecting between two
implementations of the same operation on that basis. The one legal backend-dependent branch is the
`error.ConcurrencyUnavailable` arm of an `io.concurrent`.

### ZS-IO-32 [S] Use raw `std.Thread` only for dedicated, long-lived OS threads
`std.Thread.spawn`/`join`/`detach`/`getCpuCount`/`yield`/`setName` are unchanged and still correct.

**Why:** `Io` tasks are units of work with a scheduler behind them. A thread that must own a
resource for the process lifetime — a signal-handling thread, a real-time audio callback thread, a
thread pinned to a core — is not a unit of work and gains nothing from `Io`. Everything else should
be `io.async`/`Group`, so it stays substitutable. When you do use `std.Thread`, synchronize with
`std.atomic.Value` or an `Io` primitive; there is nothing else left.

**Check:** a `std.Thread.spawn` whose `join` is in the same function — that is a unit of work, so it
is `io.async`. A legitimate use spawns once during startup and either `detach`es or joins during
shutdown, and the entry function's body is a `while (true)` owning one resource.

### ZS-IO-33 [M] Time is `Io`: `Io.Timestamp`, `Io.Duration`, `Io.Clock`, `io.sleep`
`std.time` is unit constants plus `std.time.epoch` and nothing else — no `Timer`, no `Instant`, no
`timestamp()`, no `sleep()`. `Io.Clock` variants are exactly `real`, `awake`, `boot`, `cpu_process`,
`cpu_thread`; the monotonic clock is `.awake` and `.monotonic` is a compile error. Duration
constructors are spelled in full: `fromNanoseconds`, `fromMicroseconds`, `fromMilliseconds`,
`fromSeconds`.

**Why:** a clock is nondeterminism, so it belongs behind the same interface as the rest of it. That
is what makes deterministic simulation testing possible: a test `Io` can advance time by fiat.
Reading the wall clock through a global would defeat it.

**Check:** `std.time.Timer`, `std.time.Instant`, `std.time.timestamp`, `milliTimestamp`,
`nanoTimestamp`, or `std.time.sleep` anywhere in a diff; `.monotonic` used as an `Io.Clock`; and any
abbreviated `Duration` constructor (`fromMs`, `fromNs`) — the 0.17 names are spelled in full.

```zig
// fragment — GOOD
try io.sleep(.fromMilliseconds(1), .awake);
const now: Io.Timestamp = .now(io, .awake);
// Durations print with {f}: `Io.Duration.fromMilliseconds(1500)` renders as "1.5s".
```

### ZS-IO-34 [S] Express a multi-step timeout as one shared deadline, not a duration per call
`Io.Timeout` is `union(enum) { none, duration: Clock.Duration, deadline: Clock.Timestamp }`.

**Why:** N steps each given a 50 ms duration is a 50N ms worst case, which is not the budget anyone
intended. A single `.deadline` computed once bounds the whole operation regardless of how it is
decomposed. Use the `.duration` form only for a genuinely single wait.

**Check:** two or more `.duration` timeouts on the steps of one logical operation — connect, then
write, then read, each given its own budget. The fix is one `.deadline` built with
`Timestamp.fromNow` at entry and threaded through, so grep for the absence of a single shared
`Io.Timeout` value in any function that performs more than one waiting call.

```zig
// verified — GOOD
const std = @import("std");
const Io = std.Io;
test "timeout as a deadline, not a per-call duration" {
    const io = std.testing.io;

    // One deadline shared by every step of a multi-step operation.
    const deadline: Io.Timeout = .{ .deadline = .fromNow(io, .{
        .raw = .fromMilliseconds(50),
        .clock = .awake,
    }) };

    var e: Io.Event = .unset;
    try std.testing.expectError(error.Timeout, e.waitTimeout(io, deadline));
}
```

---

## TigerStyle, re-derived for `std.Io`

### ZS-IO-35 [M!] Run at your own pace: drain a batch, do not react per event
TigerStyle: *don't do things directly in reaction to external events; your program should run at its
own pace.* In 0.17 that means `q.get(io, &batch, 1)` — which returns up to `batch.len` items in one
wake-up — rather than `q.getOne(io)` in a loop, and `writeVecAll`/`sendFileAll` rather than a write
per record.

**Why:** one wake-up per event means one context switch, one scheduler round-trip, and one set of
assertion re-checks per event. Batching amortizes all three and bounds work per time period, which
is what makes the per-batch assertions affordable.

**`[M!]` trigger:** throughput or worst-case latency is a stated requirement, or the code runs
per request, per record, or per packet — databases, consensus, network services, codecs.
***Relaxed form:*** elsewhere, still amortize anything that crosses the process boundary — one
`flush` and one `writeVecAll` per batch of records rather than per record. What relaxes is the
wake-up: a per-event `getOne` loop is acceptable when the event rate is bounded by a human or by a
file the program already holds, rather than by a peer. The non-I/O half of this is
`references/performance-and-locality.md` ZS-PERF-05.

**Check:** `q.getOne(io)` inside a `while`; a `writeAll`/`print` plus a `flush` per record inside a
loop over records; an `io.async` per event rather than per batch. The batched forms are
`q.get(io, &batch, 1)`, `writeVecAll`/`sendFileAll`, and one task per batch — and each batch array
needs the named `_max` of ZS-IO-38 plus an assertion on the returned count.

```zig
// fragment — BAD: one wake-up, one syscall, one round-trip per event
while (true) {
    const event = q.getOne(io) catch break;
    apply(event);
}
```

```zig
// verified — GOOD
const std = @import("std");
const Io = std.Io;
const assert = std.debug.assert;
const Event = struct { id: u32 };

const Batcher = struct {
    queue: Io.Queue(Event),
    applied: u32 = 0,

    const batch_max = 64;

    /// Drain whatever has accumulated, up to `batch_max`, and apply it as one unit.
    /// The loop runs at the consumer's pace: it never wakes once per event.
    fn run(b: *Batcher, io: Io) Io.Cancelable!void {
        var batch: [batch_max]Event = undefined;
        while (true) {
            const n = b.queue.get(io, &batch, 1) catch |err| switch (err) {
                error.Closed => return,
                error.Canceled => |e| return e,
            };
            assert(n >= 1 and n <= batch_max);
            b.applyBatch(batch[0..n]);
        }
    }

    fn applyBatch(b: *Batcher, events: []const Event) void {
        for (events) |e| b.applied += e.id;
    }
};
```

`Io.Batch` + `Io.Operation` is the lowest-level form of the same idea: N operations submitted
together, results collected with `batch.next()`. Reach for it only when `Future`/`Group` measurably
costs too much per operation.

```zig
// fragment — GOOD: two reads submitted as one batch
var storage: [2]Io.Operation.Storage = undefined;
var batch: Io.Batch = .init(&storage);
defer batch.cancel(io);

_ = batch.add(.{ .file_read_streaming = .{ .file = fa, .data = &.{&buf_a} } });
_ = batch.add(.{ .file_read_streaming = .{ .file = fb, .data = &.{&buf_b} } });
try batch.awaitAsync(io);

while (batch.next()) |c| _ = try c.result.file_read_streaming;
```

### ZS-IO-36 [M!] A suspension point invalidates every entry-time assertion about shared state
TigerStyle says: *ensure functions run to completion without suspending, so that precondition
assertions are true throughout the lifetime of the function.* Under `io.async` that rule cannot be
followed literally — any `io.*` call is a suspension point. The 0.17 form of the rule: assert about
shared state only in a region where you hold exclusive access, and re-establish the assertion after
every `io.*` call.

**Why:** TigerStyle was written for TigerBeetle, which pins Zig 0.14.1 and has no `std.Io`; its
"no suspend" rule is a 0.14-era workaround for the absence of an I/O interface, not a law. The
mechanism is unchanged, though: between `try a.lock.lock(io)` and its return, other tasks in the
same `Io` run and mutate `a`. An assertion written before the lock documents a fact that is false by
the time the code below it executes — worse than no assertion, because it reads as a guarantee.

**`[M!]` trigger:** a stale invariant corrupts data rather than merely misbehaving — ledgers,
replicated or persisted state, allocators, anything where the wrong number becomes durable.
***Relaxed form:*** everywhere else, do not write an assertion about shared state *above* a
suspension point at all: move it below the acquisition or delete it. That is weaker than
re-establishing the invariant after every `io.*` call, but it still forbids the specific line that
lies.

**Check:** in any function taking an `io`, an `assert` whose operands are not parameters or locals
and which sits above the first `try io.*` / `try ….lock(io)` / `.await(io)` line in that function.
Line order alone identifies it; no reasoning about the invariant is required.

```zig
// fragment — BAD: the assertion is stale before the mutation it guards
fn debit(a: *Account, io: Io, amount: u64) Io.Cancelable!void {
    assert(a.balance >= amount); // true now; another task may debit during lock()
    try a.lock.lock(io);         // <- suspension point
    defer a.lock.unlock(io);
    a.balance -= amount;         // may underflow
}
```

```zig
// verified — GOOD
const std = @import("std");
const assert = std.debug.assert;
const Io = std.Io;
const Account = struct {
    balance: u64,
    lock: Io.Mutex = .init,

    fn debit(a: *Account, io: Io, amount: u64) Io.Cancelable!void {
        try a.lock.lock(io); // suspension point
        defer a.lock.unlock(io);
        assert(a.balance >= amount); // asserted AFTER acquiring, not before
        a.balance -= amount;
    }
};
```

The pure-function corollary still holds and is now easier to satisfy: a function that takes only its
own inputs and no `io` cannot suspend, so its preconditions hold for its whole body. Push `io` calls
to the edges and keep the computational core `io`-free — that is where TigerStyle's assertion
density belongs.

### ZS-IO-37 [M] Retire TigerStyle's completion-callback *style*, not its parameter order
What `std.Io` kills is the callback-**driven I/O** pattern: the `read_sector()` /
`read_sector_callback()` pair, the continuation threaded through an `on_complete` field, the state
machine that exists only to remember where to resume. Do not write those. `io.async(f, args)`
returns a `Future` and `f.await(io)` resumes in the caller's own lexical scope, so there is no
completion to name and nothing to position.

**Why:** that pattern exists because 0.14 had no I/O interface, so TigerBeetle hand-rolled a
callback-threaded event loop (its `main` still pins 0.14.1). The interface is the replacement, and
it removes the naming problem rather than solving it.

TigerStyle's *other* callback rule — "callbacks go last in the parameter list" — survives, because
std does exactly the same thing for function values passed as data, in
`std/sort.zig` and `std/mem.zig` at 0.17.0: `insertion`, `heap`, `pdq`, `block`, `binarySearch`,
`lowerBound`, `upperBound`, `equalRange`, `argMin`, `argMax`, `isSorted`, `std.mem.sort`, and
`std.mem.sortUnstable` all put the comparator last, after `context`:

```zig
// fragment — from std/mem.zig
pub fn sort(
    comptime T: type,
    items: []T,
    context: anytype,
    comptime lessThanFn: fn (@TypeOf(context), lhs: T, rhs: T) bool,
) void
```

So for a comparator, a visitor, or a predicate, put the function value last and pair it with an
explicit `context` immediately before it. `references/naming-and-files.md` ZS-NAME-12 owns that slot
order in full.

**Check:** in a diff, a `*_callback` parameter or field, an `on_*` completion field, or a function
split into `doThing` / `doThingCallback` — all should be `io.async` + `await`. A function value in a
non-final parameter slot is the separate, milder ZS-NAME-12 finding.

The TigerStyle rules this chapter *does* keep — bounded buffers, bounded queues, batching, assertion
density — are independent of the I/O model and carry over unchanged.

### ZS-IO-38 [M!] Bound every stream buffer and queue with a named compile-time constant
Reader buffers, writer buffers, `Io.Queue` storage, `Io.Select` storage, `Io.Batch` storage, and
`Io.Group` fan-out width are all caller-provided fixed arrays. Size each from a `const` with a name
and a comment, not from a literal at the call site.

**Why:** these arrays are the enforcement points for TigerStyle's fixed-upper-bound rule — the API
already refuses to allocate on your behalf, so the only question is whether the bound is documented
or accidental. A named constant also lets an assertion state the relationship
(`assert(out.len <= futures.len)`) instead of leaving it implicit.

**`[M!]` trigger:** the system must not OOM, or must have a provable worst-case footprint —
embedded and freestanding targets, databases, consensus, anything sized against a fixed memory
budget. ***Relaxed form:*** elsewhere the size may be a literal at the declaration, provided a
comment on that line says what it bounds and what happens when the bound is hit. What never relaxes
is that the bound is stated: an undocumented buffer size is a finding at every tier, because it is
also the maximum line, message, or fan-out width and nobody chose it.

**Check:** an array length written as a bare numeric literal at the point of declaration —
`var buf: [4096]u8`, `[8]Io.Future(…)`, `var storage: [2]u32` feeding `Queue.init` — with no
`const …_max` and no comment. The declarations to sweep are reader and writer buffers, `Io.Queue`
storage, `Io.Select` storage, `Io.Batch` storage, and future arrays.

```zig
// fragment — GOOD
/// Longest line the config parser accepts; longer lines yield error.StreamTooLong.
const config_line_max = 4096;
/// Maximum shards fanned out per request; bounds peak concurrency and stack use.
const shard_max = 8;

var line_buffer: [config_line_max]u8 = undefined;
var futures: [shard_max]Io.Future(FetchError!u32) = undefined;
```

---

## Dead API — never emit these

### ZS-IO-39 [M] Reject the 0.13/0.14-era I/O API on sight (see ZS-MIG-03 / ZS-MIG-05 / ZS-MIG-10)
Owned by `references/migration-and-dead-apis.md`: ZS-MIG-03 for the `std.io` → `std.Io` stream
rewrite, ZS-MIG-05 for `std.fs` → `std.Io.Dir`/`Io.File`, ZS-MIG-09 for `std.process.Child` →
`std.process.spawn`/`run`/`replace`, and ZS-MIG-10 for `std.Thread`'s sync primitives, `std.time`,
and `std.crypto.random` moving onto `std.Io`. That chapter is the single maintained copy of the
mapping table; three copies of it would drift, which is the exact failure this skill exists to
prevent.

`std.Thread.spawn/join/detach/getCpuCount/getCurrentId/yield/setName`, `std.atomic.Value(T)`, and
the atomic builtins are unchanged and still correct (ZS-IO-32).

---

## Networking

`std.net` is gone; networking is `std.Io.net`, and it obeys every rule above — `Io` after the
receiver, `Io.Limit` on reads, `error.Canceled` never swallowed, buffers sized deliberately. Only
`Io.Threaded` implements it in 0.17.0 (ZS-IO-04).

### ZS-IO-40 [M] Build the address first; `listen`, `bind`, and `connect` are methods on it
`net.IpAddress` is `union(enum) { ip4: Ip4Address, ip6: Ip6Address }` and is the entry point for
every connection. `address.listen(io, options) -> Server` for connection-oriented work,
`address.bind(io, options) -> Socket` for datagrams, `address.connect(io, options) -> Stream` for a
client. Note the parameter order: the address is the receiver, `io` comes immediately after it
(ZS-IO-02).

**Why:** there is no free `net.listen(io, "127.0.0.1", 8080)`. Routing everything through a parsed
`IpAddress` means the parse failure and the connect failure are separate error sets at separate call
sites, instead of one function that can fail for either reason. Two constructors, and the difference
matters: `IpAddress.parse(text, port)` is **pure** and cannot handle an IPv6 scope;
`IpAddress.resolve(io, text, port)` takes an `Io` precisely because `fe80::1%eno1` needs a syscall
to turn `eno1` into an interface index. `parseLiteral(text)` handles the combined `addr:port` /
`[v6addr]:port` spellings. For a DNS name, use `net.HostName.connect(host, io, port, options)`,
which is a Happy-Eyeballs racer built on `io.async` + `Io.Queue` — do not hand-roll one.

**Check:** `std.net` anywhere; `IpAddress.parse` on a string that may carry a `%scope`;
`ConnectOptions` left at `.timeout = .none` on an outbound connection to an untrusted host.

```zig
// fragment — GOOD
test "address parsing" {
    const a: net.IpAddress = try .parse("127.0.0.1", 8080);
    try std.testing.expectEqual(8080, a.getPort());
    var buf: [64]u8 = undefined;
    try std.testing.expectEqualStrings("127.0.0.1:8080", try std.mem.print(&buf, "{f}", .{a}));
}
```

`ListenOptions` defaults to `.{ .mode = .stream, .protocol = .tcp, .kernel_backlog = 128 }` and
`reuse_address = false`; `BindOptions` and `ConnectOptions` require `mode` explicitly, because a
datagram socket and a stream socket are not interchangeable and std refuses to guess.

### ZS-IO-41 [M] A socket is an ordinary stream source — and `.limited` is not optional on one
`stream.reader(io, &buf)` and `stream.writer(io, &buf)` return `net.Stream.Reader` /
`net.Stream.Writer`, each with an `interface` field and an `err` field. Everything in the
buffer-then-flush section applies unchanged: flush before the stream dies (ZS-IO-05), take
`*Io.Writer` in reusable code (ZS-IO-08), recover the concrete error from `.err` (ZS-IO-10).

**Why:** the peer chooses how many bytes arrive and when, which makes a socket the canonical
untrusted input boundary of ZS-IO-15: `.unlimited` on `allocRemaining` over a socket is an
attacker-controlled allocation, and an unsized reader buffer is an attacker-controlled maximum
message length (ZS-IO-12). This is also where ZS-IO-27 bites hardest — every socket read and write
is a cancellation point, so a `catch {}` around one converts a shutdown request into a task that
blocks forever on a peer that will never send.

**Check:** `.unlimited` passed to any read over a `net.Stream`; a socket reader buffer sized by a
bare literal; a missing `flush` before `stream.close(io)`.

```zig
// fragment — GOOD
const std = @import("std");
const Io = std.Io;
fn serve(io: Io, server: *net.Server) !void {
    const conn = try server.accept(io);
    defer conn.close(io);

    var buf: [64]u8 = undefined;
    var cw = conn.writer(io, &buf);
    try cw.interface.writeAll("pong\n");
    try cw.interface.flush();
}

test "tcp loopback: listen, connect, read with an explicit limit" {
    const io = std.testing.io;
    const gpa = std.testing.allocator;

    const address: net.IpAddress = .{ .ip4 = .loopback(0) };
    var server = try address.listen(io, .{ .reuse_address = true });
    defer server.deinit(io);

    var accepting = try io.concurrent(serve, .{ io, &server });
    defer if (accepting.await(io)) |_| {} else |err| std.log.err("serve: {t}", .{err});

    // Port 0 asked the kernel for an ephemeral port; read back what it assigned.
    const stream = try server.socket.address.connect(io, .{ .mode = .stream });
    defer stream.close(io);

    var read_buffer: [64]u8 = undefined;
    var sr = stream.reader(io, &read_buffer);
    const line = try sr.interface.allocRemaining(gpa, .limited(1 << 16));
    defer gpa.free(line);
    try std.testing.expectEqualStrings("pong\n", line);
}
```

Note the accept side runs under `io.concurrent`, not `io.async`: the server must make progress while
the client connects, which is exactly the interleaving requirement of ZS-IO-25.
`net.Stream.Writer.sendFile` is `error.Unimplemented` in 0.17.0 (a `TODO` in std), so
`sendFileAll` over a socket silently falls back to the userspace copy loop — the ZS-IO-16 zero-copy
argument does not yet apply to sockets.

### ZS-IO-42 [M] Close every socket on every path; `shutdown` is how you unblock a blocked peer
`stream.close(io)`, `socket.close(io)`, and `server.deinit(io)` each take the `Io`, exactly like
`file.close(io)` — pair each with a `defer` on the acquisition line (ZS-MEM-11). To wake a task
parked in `accept` or a read, call `stream.shutdown(io, .recv/.send/.both)` from another task.

**Why:** a socket is a file descriptor, so a leak exhausts the same per-process quota as a leaked
file and surfaces as `error.ProcessFdQuotaExceeded` on an unrelated open far from the leak. The
`shutdown` half is documented behavior, not a trick: `Server.accept`'s `error.SocketNotListening`
carries the comment "This allows `shutdown` to be used as a concurrent cancellation mechanism."
Under a graceful-shutdown path that is how you get an accept loop to return so its `Group` can be
awaited rather than abandoned (ZS-IO-24).

**Check:** an `accept`/`connect`/`createPair` result whose next line is not a `defer …close(io)`; an
accept loop with no way to be woken.

> [!NOTE] At 0.17.0, re-check on a toolchain bump: `net.Socket.closeMany(io, sockets)` compiles
> and closes a batch in one call (in 0.16.0 it did not compile). `Socket.createPair(io, .{})`
> defaults to `.family = .ip4`, which `socketpair` rejects on Darwin: there it returns
> `error.Unexpected`.

---

## Subprocesses

`std.process.Child.init` + `spawn()` is the 0.14 shape and does not exist. In 0.17 the two entry
points are free functions taking `io`, and the choice between them is whether you want the output or
the stream.

### ZS-IO-43 [M] `std.process.run` for the output; `std.process.spawn` for the stream
Exact signatures, from `std/process.zig`:

```zig
// fragment — from std/process.zig
pub fn spawn(io: Io, options: SpawnOptions) SpawnError!Child;
pub fn run(gpa: Allocator, io: Io, options: RunOptions) RunError!RunResult;
pub fn replace(io: Io, options: ReplaceOptions) ReplaceError; // never returns on success
```

`RunResult` is `{ term: Child.Term, stdout: []u8, stderr: []u8 }` and **the caller owns both
slices**. `RunOptions` carries `exe`, `argv`, `stdout_limit`/`stderr_limit` (`Io.Limit`),
`reserve_amount`, `cwd`, `environ_map`, `progress_node`, and `timeout: Io.Timeout`. `SpawnOptions`
carries `exe`, `argv`, `cwd`, `environ_map`, `progress_node`, `inherit_dirs`/`inherit_files`, and
`stdin`/`stdout`/`stderr`, each a
`StdIo = union(enum) { inherit, file: File, ignore, pipe, close }`. `exe` says how `argv[0]` is
found — `.detect` (the default), `.search` on `PATH`, `.path` relative to a `Dir`, `.file`, or
`.explicit` — and replaces 0.16's `spawnPath(io, dir, options)` and `replacePath`, both removed in
0.17: write `.exe = .{ .path = dir }`. Note the ordering rule holds: `run` is a free function so
`gpa` precedes `io` (ZS-IO-02).

**Why:** `run` is `spawn` with `.stdin = .ignore, .stdout = .pipe, .stderr = .pipe` plus an
`Io.File.MultiReader` that drains both pipes concurrently. Draining concurrently is the whole point:
a child that fills the stderr pipe blocks forever while you read stdout, and hand-rolling `spawn`
plus two sequential reads reintroduces exactly that deadlock. Use `spawn` only when you need the
output *incrementally* — a build tool relaying a compiler's diagnostics as they appear — or need a
`StdIo` shape `run` does not offer.

**Check:** `stdout_limit`/`stderr_limit` left at their `.unlimited` default on a child whose output
is not bounded by construction (ZS-IO-15); `run`'s `result.stdout`/`result.stderr` without a `defer
gpa.free`; any surviving `std.process.Child.init`.

```zig
// verified — GOOD
const std = @import("std");
test "process.run collects stdout with an explicit limit" {
    const gpa = std.testing.allocator;
    const io = std.testing.io;

    const result = try std.process.run(gpa, io, .{
        .argv = &.{ "echo", "hello" },
        .stdout_limit = .limited(1 << 20),
        .stderr_limit = .limited(1 << 16),
    });
    defer gpa.free(result.stdout);
    defer gpa.free(result.stderr);

    try std.testing.expectEqual(std.process.Child.Term{ .exited = 0 }, result.term);
    try std.testing.expectEqualStrings("hello\n", result.stdout);
}
```

### ZS-IO-44 [M] `child.wait(io)` closes the pipes; never close `child.stdout`/`stderr` yourself
`Child` exposes `stdin`, `stdout`, `stderr` as `?File`, populated for each stream you set to
`.pipe`. Read them through a normal `File.Reader`, then call `wait`. `wait` reaps the process
**and** closes every pipe it opened.

**Why:** closing the child's `stdout` before `wait` panics inside `wait`'s own cleanup:
`std.Io.Threaded.closeFd` maps `.BADF => recoverableOsBugDetected()`, which is
`reached unreachable code` in a `debug` build.
It is a double close, and the ownership is not obvious from the type: `?File` looks like a handle
you own. Pair the spawn with `errdefer child.kill(io)` so an error between spawn and `wait` does not
leave an orphan, and let `wait` be the single release point on the success path.

**Check:** any `close(` reached through `child.stdout` or `child.stderr`; a `spawn` with no
`errdefer child.kill(io)`; a `spawn` whose `wait` is skipped on an error path (a zombie plus a
leaked pipe).

```zig
// verified — GOOD
const std = @import("std");
test "process.spawn streams a child's stdout incrementally" {
    const io = std.testing.io;

    var child = try std.process.spawn(io, .{
        .argv = &.{ "printf", "a\nb\n" },
        .stdin = .ignore,
        .stdout = .pipe,
    });
    errdefer _ = child.kill(io);

    var buf: [64]u8 = undefined;
    var stdout = child.stdout orelse return error.TestUnexpectedResult;
    var cr = stdout.readerStreaming(io, &buf);
    var lines: usize = 0;
    while (try cr.interface.takeDelimiter('\n')) |_| lines += 1;

    // `wait` closes the pipe files itself; closing them here is a double close.
    const term = try child.wait(io);
    try std.testing.expectEqual(std.process.Child.Term{ .exited = 0 }, term);
    try std.testing.expectEqual(2, lines);
}
```

`stdin = .pipe` is the mirror image: write to the child's `stdin` through a `File.Writer`,
`flush`, and then let `wait` close it — but a child that is still reading stdin will not exit, so
a program that both feeds and drains a child needs the two directions on separate tasks
(`io.concurrent`, ZS-IO-25), not sequentially.

---

## Terminals and progress

### ZS-IO-45 [S] Decide color with `Io.Terminal`, not with your own `isatty` check
`Io.Terminal` is `{ writer: *Io.Writer, mode: Mode }`. Build the mode with
`Io.Terminal.Mode.detect(io, file, NO_COLOR, CLICOLOR_FORCE)` — the two `bool`s are "the environment
variable is present and non-empty" — and emit with `t.setColor(color)`.

**Why:** it is the 0.16 replacement for the removed `std.io.tty` / `tty.detectConfig`, and it folds
four separate decisions into one call: is the handle a terminal, can ANSI escapes be *enabled* on it
(it calls `file.enableAnsiEscapeCodes`, which on Windows mutates console mode), does the user's
`NO_COLOR` forbid color, does `CLICOLOR_FORCE` demand it anyway. Hand-rolling that gets the Windows
console path and the `NO_COLOR` convention wrong. `Mode` is `union(enum) { no_color, escape_codes,
windows_api }`, so `.no_color` makes `setColor` a no-op and the same code path serves a pipe.

Deviate only if you are emitting a format whose color is part of the data rather than a presentation
choice — say so in a comment.

**Check:** any `isatty`, `std.io.tty`, or hard-coded `"\x1b[31m"` in a diff; reading `NO_COLOR`
without also honoring `CLICOLOR_FORCE`.

```zig
// verified — GOOD
const std = @import("std");
const Io = std.Io;
test "terminal mode detection and color" {
    const io = std.testing.io;
    var buf: [64]u8 = undefined;
    var w: Io.Writer = .fixed(&buf);
    const mode = try Io.Terminal.Mode.detect(io, .stderr(), false, false);
    const t: Io.Terminal = .{ .writer = &w, .mode = mode };
    try t.setColor(.red);
    try t.setColor(.reset);
}
```

### ZS-IO-46 [S] Report long work through `std.Progress`, and pass the node to children
`std.Progress.start(io, .{ .root_name = "…" })` returns the root `Node`; `node.start(name, total)`
opens a child, `completeOne`/`setCompletedItems`/`setEstimatedTotalItems` update it, `node.end()`
closes it. `Node.none` is the do-nothing node, so progress-aware code needs no `?Node`.

**Why:** it is why ZS-IO-11 exists — `Progress` takes the same stderr lock as `std.log` and the
panic handler, so it is the *reason* ad-hoc stderr writes corrupt output, and the thing you should
be using instead of printing "processing 5/100" yourself. It also crosses process boundaries: both
`SpawnOptions` and `RunOptions` carry a `progress_node`, and std wires a pipe through the
`ZIG_PROGRESS` environment variable so the child's tree grafts into the parent's. A build tool that
does not pass its node makes every subprocess a black box in the display.

Deviate for a program with no interactive lifetime — a filter in a pipeline. `start` asserts it is
called once per process, so a library never calls it; a library takes a `Node` parameter and
defaults it to `.none`.

**Check:** a `std.process.spawn`/`run` inside a progress-reporting tool with no `progress_node`; a
manual "N/M" counter printed to stderr; `std.Progress.start` in library code.

```zig
// verified — GOOD: a `main`, because `start` is process-global
/// Maximum shards indexed per run; bounds the progress denominator (ZS-IO-38).
const std = @import("std");
const shard_max = 4;

pub fn main(init: std.process.Init) !void {
    const io = init.io;

    const root = std.Progress.start(io, .{ .root_name = "indexing" });
    defer root.end();

    const shards = root.start("shards", shard_max);
    defer shards.end();

    for (0..shard_max) |_| {
        try io.sleep(.fromMilliseconds(1), .awake);
        shards.completeOne();
    }
}
```

---

## More of the `Io.Dir` / `Io.File` surface

### ZS-IO-47 [S] Pick the traversal API by who decides to descend
Four levels, cheapest first. `Io.Dir.Reader` — you supply a `[Reader.min_buffer_len]u8` aligned to
`usize` and batch entries with `read(io, &entries)`; no allocation. `dir.iterate()` — the ~2 KiB
self-buffering `Iterator` of ZS-IO-22, one entry at a time. `dir.walkSelectively(gpa)` — recursive,
but *you* call `walker.enter(io, entry)` for each directory you want to descend into.
`dir.walk(gpa)` — recursive and descends unconditionally.

**Why:** `walk` is `walkSelectively` with an automatic `enter` on every directory
(`std.Io.Dir.walk`, whose `Walker.next` calls `enter` on each entry), which means it has no way to
skip `.git`, `node_modules`, or a bind mount that loops. Reaching for
`walk` and then filtering the entries it returns still paid for the whole subtree. Choose
`walkSelectively` whenever any subtree can be excluded; choose `Dir.Reader` when the traversal is
hot enough that the `Iterator`'s one-entry-per-call round trip shows up, or when you cannot allocate
at all. Both walkers hand back `Entry.path`/`basename` that are invalidated by the next `next` —
copy before you keep one, exactly as with reader slices (ZS-IO-14).

**Check:** `dir.walk(` followed by a `continue`/`if` that skips a directory subtree — that is
`walkSelectively`. Also any `Entry.path` stored past the loop body without a `dupe`.

```zig
// verified — GOOD
const std = @import("std");
test "walkSelectively prunes a subtree that walk would descend into" {
    const io = std.testing.io;
    const gpa = std.testing.allocator;
    var tmp = std.testing.tmpDir(.{ .iterate = true });
    defer tmp.cleanup();

    try tmp.dir.createDirPath(io, "keep");
    try tmp.dir.createDirPath(io, "skip");
    try tmp.dir.writeFile(io, .{ .sub_path = "keep/a.txt", .data = "" });
    try tmp.dir.writeFile(io, .{ .sub_path = "skip/b.txt", .data = "" });

    var walker = try tmp.dir.walkSelectively(gpa);
    defer walker.deinit();

    var files: usize = 0;
    while (try walker.next(io)) |entry| {
        if (entry.kind == .file) files += 1;
        // Opt in per directory: `walk` would descend unconditionally.
        if (entry.kind == .directory and !std.mem.eql(u8, entry.basename, "skip")) {
            try walker.enter(io, entry);
        }
    }
    try std.testing.expectEqual(1, files);
}
```

```zig
// fragment — GOOD: ; the allocation-free form
var buffer: [Io.Dir.Reader.min_buffer_len]u8 align(@alignOf(usize)) = undefined;
var dr: Io.Dir.Reader = .init(dir, &buffer);
var entries: [8]Io.Dir.Entry = undefined;
var files: usize = 0;
while (true) {
    const n = try dr.read(io, &entries);
    if (n == 0 and dr.state == .finished) break;
    for (entries[0..n]) |e| if (e.kind == .file) {
        files += 1;
    };
}
```

### ZS-IO-48 [M] Say which race you mean: `renamePreserve`, `hardLink`, `createMemoryMap`
`dir.rename(old_sub_path, new_dir, new_sub_path, io)` **replaces** the destination silently.
`dir.renamePreserve(...)` is the same call that returns `error.PathAlreadyExists` instead,
atomically — or `error.OperationUnsupported` where the filesystem cannot do a non-replacing rename.
`dir.hardLink(old_sub_path, new_dir, new_sub_path, io, options)` publishes a second name for one
inode. Note the shape shared by all three: the two path arguments straddle the destination `Dir` and
`io` comes **last**, before the options — this is the one family in `Io.Dir` that breaks the
receiver-then-`io` rule of ZS-IO-02, and getting it wrong is a compile error, not a bug.

**Why:** "create this file only if it does not exist" and "create this file" are different programs,
and doing the check yourself (`if (exists) return error.X;` then rename) is a TOCTOU window that
another process wins. `renamePreserve` pushes the check into the same syscall. `hardLink` is the
primitive behind content-addressed caches and atomic publication — link the new name, then
`rename` over the old one — and unlike a copy it cannot half-succeed. For an in-place replacement of
an existing file, ZS-IO-23's `createFileAtomic` + `replace` remains the answer; these are for the
naming operations around it.

**Check:** a `dir.rename` whose surrounding code first tests for existence; a copy loop used only to
duplicate a name within one filesystem.

```zig
// verified — GOOD
const std = @import("std");
test "renamePreserve refuses to clobber; rename replaces" {
    const io = std.testing.io;
    var tmp = std.testing.tmpDir(.{});
    defer tmp.cleanup();

    try tmp.dir.writeFile(io, .{ .sub_path = "old.txt", .data = "v1" });
    try tmp.dir.writeFile(io, .{ .sub_path = "new.txt", .data = "v2" });

    try std.testing.expectError(
        error.PathAlreadyExists,
        tmp.dir.renamePreserve("old.txt", tmp.dir, "new.txt", io),
    );
    try tmp.dir.rename("old.txt", tmp.dir, "new.txt", io);

    var buf: [8]u8 = undefined;
    try std.testing.expectEqualStrings("v1", try tmp.dir.readFile(io, "new.txt", &buf));
}
```

`file.createMemoryMap(io, options)` is the third primitive: it returns a `MemoryMap` whose `.memory`
is a plain `[]align(page_size_min) u8`, with `mm.read(io)` and `mm.write(io)` as the explicit
synchronization points and `mm.destroy(io)` as the release. `CreateOptions.len` has no alignment
requirement, `offset` must be page-aligned, and `protection` must not exceed the mode the file was
opened with — asking for the default `.{ .read = true, .write = true }` on a read-only handle is
`error.AccessDenied`. Reach for it for random access over a large file that a
`File.Reader` would stream linearly; it is not a substitute for `readFileAlloc` on a small one.
