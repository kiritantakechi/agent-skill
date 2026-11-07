# std.Io: streams, filesystem, and structured concurrency

Scope: everything in Zig 0.17 that can block, fail nondeterministically, or touch the outside world,
all of which goes through one value, `std.Io` — obtaining and threading that value, the
buffer-then-flush writing discipline, `Io.Reader`, authoring custom stream implementations, the
`std.Io.Dir`/`std.Io.File` filesystem API that replaced `std.fs`, structured concurrency
(`io.async`, `Io.Group`, `Io.Select`, `Io.Queue`, cancellation, timeouts, `Io` sync primitives),
`std.Io.net`, subprocesses via `std.process.spawn`/`run`, and `Io.Terminal` / `std.Progress`. Format
specifiers — `{f}`, `{t}`, `{?}` and the custom `format` method — and which bytes are program output
and which are diagnostics (ZS-OUT-16) are the output chapter's; allocator choice and
`defer`/`errdefer` layout the memory chapter's; `std.testing.io` and `Io.failing` mechanics are
ZS-TEST-08; every 0.13 to 0.17 spelling is a row of the migration table; the non-I/O half of
batching is ZS-PERF-05; scoped library logging is ZS-OUT-18.

Every example assumes a file opening with
`const std = @import("std"); const Io = std.Io; const net = std.Io.net;`, and
`const assert = std.debug.assert;` where an assertion appears.

## Contents

- **Obtaining and threading `Io`**
  - ZS-CONC-01 [M] Obtain `Io` from `main`'s `std.process.Init`, never from a global
  - ZS-CONC-02 [M] Thread `io: Io` as an explicit parameter, using std's ordering
  - ZS-CONC-03 [S] Default to `Io.Threaded`; treat `Io.Evented` as experimental
- **Writing: buffer, then flush**
  - ZS-CONC-04 [M] Flush every buffered writer before it goes out of scope
  - ZS-CONC-05 [M] Stream to stdout; keep the positional `writer` for files you opened
  - ZS-CONC-06 [M] Reusable code takes `*Io.Writer` and returns `Io.Writer.Error!void`
  - ZS-CONC-07 [S] Build in-memory strings with `Io.Writer.Allocating`
  - ZS-CONC-08 [M] Recover the real error from the concrete writer/reader
  - ZS-CONC-09 [M] Write application stderr through `io.lockStderr`
- **Reading**
  - ZS-CONC-10 [M] Size the reader buffer deliberately — it is your maximum token length
  - ZS-CONC-11 [M] Iterate lines with `takeDelimiter`, never `takeDelimiterExclusive`
  - ZS-CONC-12 [M] Never keep a slice from `peek`/`take`/`takeDelimiter` past the reader's next call
  - ZS-CONC-13 [M] Give every read-all API an explicit `Io.Limit`
  - ZS-CONC-14 [S] Stream large data; only read whole objects you have already bounded
- **Authoring custom streams**
  - ZS-CONC-15 [M] Implement `drain` to the full contract
  - ZS-CONC-16 [M] A custom `Reader` signals end of stream with `error.EndOfStream`, never `0`
  - ZS-CONC-17 [M] Pair `writableSliceGreedy` with `advance`; never `advance` after `writableSlice`
- **Filesystem**
  - ZS-CONC-18 [M] Pair every open with `defer close(io)`, and iterate with the iterator's own buffer
  - ZS-CONC-19 [M] Replace a file another reader depends on atomically, with `createFileAtomic`
  - ZS-CONC-20 [S] Pick the traversal API by who decides to descend
  - ZS-CONC-21 [M] Say which race you mean: `rename`, `renamePreserve` or `hardLink`
  - ZS-CONC-22 [S] Map a large file you access at random with `createMemoryMap`
- **Structured concurrency**
  - ZS-CONC-23 [M] Every started `Future` is awaited or canceled exactly once, on every path
  - ZS-CONC-24 [S] Prefer `io.async`; use `io.concurrent` only for simultaneous progress
  - ZS-CONC-25 [S] Pick the right aggregate: `Group`, `Select`, or `Queue`
  - ZS-CONC-26 [M] Never ignore `error.Canceled`
  - ZS-CONC-27 [M] Call `io.checkCancel()` inside long CPU-bound loops
  - ZS-CONC-28 [M] Use the `*Uncancelable` variants in `defer` and cleanup paths
  - ZS-CONC-29 [M] Synchronize with the `Io` primitives, never OS primitives
  - ZS-CONC-30 [M] Write colorless code: never branch on which backend you were handed
  - ZS-CONC-31 [S] Use raw `std.Thread` only for dedicated, long-lived OS threads
  - ZS-CONC-32 [M] Time is `Io`: `Io.Timestamp`, `Io.Duration`, `Io.Clock`, `io.sleep`
  - ZS-CONC-33 [S] Express a multi-step timeout as one shared deadline, not a duration per call
- **TigerStyle, re-derived for `std.Io`**
  - ZS-CONC-34 [M] Drain a batch of what a peer sends; do not wake once per event
  - ZS-CONC-35 [M!] A suspension point invalidates every entry-time assertion about shared state
  - ZS-CONC-36 [M] Replace completion callbacks with `io.async` and `await`
  - ZS-CONC-37 [M] Bound every stream buffer and queue with a named compile-time constant
- **Networking**
  - ZS-CONC-38 [M] Build the address first; `listen`, `bind`, and `connect` are methods on it
  - ZS-CONC-39 [M] A socket is an ordinary stream source — and `.limited` is not optional on one
  - ZS-CONC-40 [M] Close every socket on every path; `shutdown` is how you unblock a blocked peer
- **Subprocesses**
  - ZS-CONC-41 [M] `std.process.run` for the output; `std.process.spawn` for the stream
  - ZS-CONC-42 [M] `child.wait(io)` closes the pipes; never close `child.stdout`/`stderr` yourself
- **Terminals and progress**
  - ZS-CONC-43 [S] Decide color with `Io.Terminal`, not with your own `isatty` check
  - ZS-CONC-44 [S] Report long work through `std.Progress`, and pass the node to children

---

## Obtaining and threading `Io`

### ZS-CONC-01 [M] Obtain `Io` from `main`'s `std.process.Init`, never from a global

`std.start` builds an `Io.Threaded` for you and hands it over in `init.io`. Library code accepts an
`Io` parameter; it never manufactures one and never reaches for
`Io.Threaded.global_single_threaded`.

Outside `main` — a custom runtime, a benchmark harness, a `build.zig` step — construct one
explicitly and pair it with `deinit`, as the second example does.

`Io.Threaded.init_single_threaded` is the exception: it holds a failing allocator and
`concurrent_limit = .nothing`, so it needs no allocator and no `deinit`.

**Why:** the entire point of the design is that the caller chooses the backend. A library that
constructs its own `Io.Threaded` spawns a second, invisible thread pool, and a library that grabs
the global escape hatch cannot be driven by an evented or fiber-based caller at all.

**Check:** `Io.Threaded.init`, `Io.Evented.init`, or `Io.Threaded.global_single_threaded` anywhere
outside `main`, a benchmark harness, a `build.zig` step, or a test; and a `main` that performs I/O
without taking `std.process.Init`, the signature ZS-MEM-01 owns.

```zig
// verified — GOOD
const std = @import("std");
const Io = std.Io;
/// Bytes of program output held before a write reaches the kernel.
const stdout_buffer_max = 4096;

pub fn main(init: std.process.Init) !void {
    const io = init.io;
    const gpa = init.gpa;

    var stdout_buffer: [stdout_buffer_max]u8 = undefined;
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

```zig
// fragment
var threaded: Io.Threaded = .init(gpa, .{});
defer threaded.deinit();
const io = threaded.io();
```

### ZS-CONC-02 [M] Thread `io: Io` as an explicit parameter, using std's ordering

`Io` is a two-field fat pointer (`userdata: ?*anyopaque`, `vtable: *const VTable`) dispatched as
`io.vtable.op(io.userdata, ...)`. Pass it by value, exactly like an `Allocator`. Ordering, as std
writes it: on a method of a resource type (`Dir`, `File`, `Mutex`, `Queue`) `io` comes immediately
after the receiver; on a free function `gpa` comes before `io`, then domain parameters, then an
options struct last.

Capturing `io` in a long-lived struct is acceptable only for a top-level application object
constructed in `main` from `init.io`, where there is exactly one backend by construction. Anything
reusable takes it as a parameter.

**Why:** an `Io` parameter is the only thing that makes a function's blocking behavior visible in
its signature, and it lets the same function run on a thread pool in production and on
`std.testing.io` or `Io.failing` in tests; a field or a global makes that substitution impossible.

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

### ZS-CONC-03 [S] Default to `Io.Threaded`; treat `Io.Evented` as experimental

`Io.Threaded` is the production backend. `Io.Evented` resolves to `Io.Uring` on Linux, `Io.Kqueue`
on the BSDs, `Io.Dispatch` on Darwin, and `void` elsewhere.

In 0.17.0 none of the three compiles once a program calls `init`: each backend's vtable still names
a slot that 0.17 removed from `Io.VTable`, so `Dispatch` and `Uring` fail with
`no field named 'processReplacePath' in struct 'Io.VTable'` and `Kqueue` with the same error for
`'fileWriteStreaming'`. None implements networking either — `Uring` and `Dispatch` wire the `net*`
vtable slots to `…Unavailable` stubs and `Kqueue`'s `listen` and `accept` are `@panic("TODO")` — so
every rule in the networking section requires `Io.Threaded` in 0.17. Deviate only for a backend that
builds and implements `std.Io.net`, once a profile shows `Io.Threaded`'s one-thread-per-blocked-task
model is your bottleneck, and say so in a comment.

**Why:** in 0.17.0 `Io.Threaded` is the only backend that both builds and implements `std.Io.net`,
so it is the only one a default can rest on; an evented backend earns its place by a measurement.

**Check:** `Io.Evented`, `Io.Uring`, `Io.Kqueue`, or `Io.Dispatch` named in a diff — each needs a
comment stating the measurement that justified it, and none of them may appear on a code path that
reaches `std.Io.net`, whose vtable slots they do not implement.

## Writing: buffer, then flush

### ZS-CONC-04 [M] Flush every buffered writer before it goes out of scope

`Io.Writer` buffers into a caller-supplied `[]u8`. Data sitting in that buffer when the writer dies
is silently discarded — no error, no diagnostic, exit code 0.

Prefer `try w.flush()` as a real statement over `defer w.flush() catch {}`: the deferred form
swallows `error.WriteFailed`, which is exactly the disk-full / broken-pipe case you needed to know
about. A zero-length buffer (`&.{}`) means unbuffered and makes `flush` a no-op — use it
deliberately, never by accident.

**Why:** it is the commonest bug in new code. The program below compiles cleanly, runs cleanly,
exits 0, and prints nothing.

**Check:** for every `writerStreaming(`, `.writer(io,`, or `Io.File.Writer.init(` in a diff, a
`flush()` on every success path leaving that scope. Also any `defer w.flush() catch {}`, and any
`return` between the last `print`/`writeAll` and the `flush`.

```zig
// fragment — BAD: compiles, runs, exits 0, prints NOTHING
pub fn main(init: std.process.Init) !void {
    const io = init.io;
    var buffer: [stdout_buffer_max]u8 = undefined;
    var fw = std.Io.File.stdout().writerStreaming(io, &buffer);
    try fw.interface.print("this line is silently lost\n", .{});
}
```

```zig
// fragment — GOOD
var buffer: [stdout_buffer_max]u8 = undefined;
var fw = Io.File.stdout().writerStreaming(io, &buffer);
const stdout = &fw.interface;
try stdout.print("visible\n", .{});
try stdout.flush(); // last statement of the writer's lifetime
```

### ZS-CONC-05 [M] Stream to stdout; keep the positional `writer` for files you opened

`File.writer(io, &buffer)` and `Io.File.Writer.init(file, io, &buffer)` are the same constructor and
set `.mode = .positional`: every write goes to an explicit offset, starting at 0.
`File.writerStreaming(io, &buffer)` / `Io.File.Writer.initStreaming` set `.mode = .streaming` and
write at the descriptor's own offset. Program output to stdout or stderr is always streaming; the
positional constructor is for a file this program opened and whose offset it owns.
`Io.File.Writer.initDetect(file, io, &buffer)` looks like it would pick the mode for you, but it
**does not compile** in 0.17: it calls `Mode.detect(...)`, and `Io.File.Reader.Mode` has no `detect`
member — `error: enum 'Io.File.Reader.Mode' has no member named 'detect'`.

**Why:** stdout may be a regular file someone already wrote to. A positional writer starts at offset
0, so `(echo header; prog) > f` overwrites the header, as does `prog >> f` on macOS; a pipe or a tty
hides the bug, because positional writes fall back to streaming on `error.Unseekable`.

**Check:** `.init(.stdout(), …)`, `.init(.stderr(), …)`, or `stdout().writer(` and
`stderr().writer(`, which is the positional constructor on a handle this program did not open —
including in code copied from `zig init`, which uses it.

```zig
// fragment — GOOD
var out_writer = Io.File.stdout().writerStreaming(io, &out_buffer); // stdout: streaming, always
var log_writer = log_file.writer(io, &log_buffer); // a file we opened: positional is safe
```

```zig
// fragment — BAD: under `(echo header; prog) > report.txt`, this overwrites the header
var stdout_writer: Io.File.Writer = .init(.stdout(), io, &stdout_buffer);
```

### ZS-CONC-06 [M] Reusable code takes `*Io.Writer` and returns `Io.Writer.Error!void`

`Io.Writer` is already type-erased and non-generic. Never take a `File`, never take an `Io` just to
write, never make the function generic over a writer type.

**Why:** `std.Io.Writer` is a concrete struct holding `buffer: []u8` plus a vtable, so accepting
`*Io.Writer` costs nothing at the call site and works uniformly for files, sockets, in-memory
buffers, hashers, and test doubles — which is what makes a function's exact output testable.

**Check:** a `pub fn` that writes and takes `anytype`, a `comptime Writer: type`, an `Io.File`, or
an `Io` where `*Io.Writer` would do; a write helper returning `anyerror!void` rather than
`Io.Writer.Error!void`; and any `GenericWriter` or `AnyWriter`, names that do not exist. The general
form of this rule, for every std interface, is ZS-COMPTIME-09.

```zig
// verified — GOOD: the same function writes to stdout in `main` and to memory under test
const std = @import("std");
const Io = std.Io;
pub fn writeCsvRow(w: *Io.Writer, fields: []const []const u8) Io.Writer.Error!void {
    for (fields, 0..) |field, i| {
        if (i != 0) try w.writeByte(',');
        try w.writeAll(field);
    }
    try w.writeByte('\n');
}

test "the exact bytes, with no process and no files" {
    var aw: Io.Writer.Allocating = .init(std.testing.allocator);
    defer aw.deinit();
    try writeCsvRow(&aw.writer, &.{ "id", "name" });
    try std.testing.expectEqualStrings("id,name\n", aw.written());
}
```

### ZS-CONC-07 [S] Build in-memory strings with `Io.Writer.Allocating`

`Allocating` grows its own buffer, exposes `written()`, `toOwnedSlice()`, and `toArrayList()`, and
has a no-op `flush`. Deviate for a single `print` (use `gpa.print`) or a size you can bound (use
`std.mem.print` over a fixed array).

`Allocating`'s error surface is `Io.Writer.Error`, so allocation failure arrives as
`error.WriteFailed`. Map it back at the boundary the way std does, as the second example shows.

**Why:** it is one allocation strategy and one error path instead of an `ArrayList` plus manual
`appendSlice`/`print` bookkeeping, and it is what `Allocator.print` is implemented in terms of.

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

```zig
// fragment
aw.writer.print(fmt, args) catch |err| switch (err) {
    error.WriteFailed => return error.OutOfMemory,
};
```

### ZS-CONC-08 [M] Recover the real error from the concrete writer/reader

`error.WriteFailed` and `error.ReadFailed` are placeholders. The actual OS error is stored on the
concrete struct: `File.Writer.err`, `File.Reader.err`, `net.Stream.Writer.err`.
`File.Writer.flush(w)` — the concrete method, not `w.interface.flush()` — does this unwrapping for
you.

**Why:** `*Io.Writer` is type-erased, so its error set cannot name `error.NoSpaceLeft` or
`error.BrokenPipe`. Propagating `error.WriteFailed` to the user throws away every actionable
diagnostic.

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

    var buffer: [64]u8 = undefined;
    var fw = file.writer(io, &buffer);
    fw.interface.writeAll("hi\n") catch |err| switch (err) {
        // `File.Writer.drain` assigns `fw.err` on every path that returns
        // error.WriteFailed, so the fallback is unreachable in practice — and
        // spelling it costs nothing.
        error.WriteFailed => return fw.err orelse error.WriteFailed,
    };
    try fw.flush(); // File.Writer.flush surfaces the concrete error, not WriteFailed
}
```

### ZS-CONC-09 [M] Write application stderr through `io.lockStderr`

`io.lockStderr(&buffer, null)` returns a `LockedStderr` with a `file_writer` field;
`io.unlockStderr()` releases it and flushes.

**Why:** `std.log`, the panic handler, and `std.Progress` all take the same lock. Writing to stderr
outside it interleaves your bytes with a progress bar's escape sequences or a panic trace.
`std.debug.lockStderr` is the `Io`-bypassing variant reserved for debugging.

**Check:** any write reaching `Io.File.stderr()` that is not inside an `io.lockStderr` /
`io.unlockStderr` pair, and any `lockStderr` whose `defer io.unlockStderr()` is not on the very next
line (ZS-MEM-10).

```zig
// fragment — GOOD
var stderr_buffer: [stderr_buffer_max]u8 = undefined;
const locked = try io.lockStderr(&stderr_buffer, null);
defer io.unlockStderr(); // unlockStderr flushes; no manual flush needed
try locked.file_writer.interface.writeAll("done\n");
```

## Reading

### ZS-CONC-10 [M] Size the reader buffer deliberately — it is your maximum token length

`Io.Reader` reads into a caller-supplied `[]u8`. `takeDelimiter`, `peek`, and friends return
`error.StreamTooLong` when the delimiter is not found within that buffer, leaving the stream
unmodified.

**Why:** the buffer length *is* the bound on a line, a header, or a record: choosing
`var buffer: [4096]u8` is choosing a 4 KiB maximum line, and a hostile 4 GiB line without a newline
becomes `error.StreamTooLong` instead of an OOM.

**Check:** any `takeDelimiter`/`peek` call site that does not handle `error.StreamTooLong`
distinctly from a real I/O failure — silently treating an over-long line as EOF truncates input.
That the size comes from a named constant is ZS-CONC-37, which owns it for buffers, queues, and
every other caller-provided fixed array.

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

### ZS-CONC-11 [M] Iterate lines with `takeDelimiter`, never `takeDelimiterExclusive`

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

### ZS-CONC-12 [M] Never keep a slice from `peek`/`take`/`takeDelimiter` past the reader's next call

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

### ZS-CONC-13 [M] Give every read-all API an explicit `Io.Limit`

`allocRemaining`, `appendRemaining`, `readFileAlloc`, and `Reader.limited` all take an `Io.Limit`.
Spell it `.limited(n)` with a justified `n`; reserve `.unlimited` for data you produced yourself.

**Why:** `Io.Limit` is the type system forcing TigerStyle's bounded-work rule on you at every
untrusted-input boundary. `.unlimited` on a network stream is an unbounded allocation controlled by
the peer.

**Check:** `.unlimited` passed to `allocRemaining`, `appendRemaining`, `readFileAlloc`, or
`Reader.limited` on bytes this process did not produce itself. A `.limited(n)` whose `n` is a bare
literal rather than a named constant is the separate ZS-CONC-37 finding.

```zig
// fragment — GOOD
const text = try tmp.dir.readFileAlloc(io, "cfg.txt", gpa, .limited(1 << 20));
defer gpa.free(text);
```

```zig
// verified — the limit on the reader bounds a read-all through it
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

### ZS-CONC-14 [S] Stream large data; only read whole objects you have already bounded

`w.sendFileAll(&file_reader, .unlimited)` uses the kernel's fd-to-fd path (sendfile,
copy_file_range, fcopyfile) and falls back to a read/write loop on `error.Unimplemented`
automatically. From one path to another, `dir.copyFile(source_path, dest_dir, dest_path, io, .{})`
is the whole operation: it streams the same way, flushes, and replaces the destination atomically.

**Why:** a copy loop through userspace costs two copies per byte and a peak RSS proportional to the
file. `sendFileAll` costs a bounded buffer. Deviate when you need to inspect or transform the bytes.

**Check:** a hand-written read-into-buffer / write-out loop between two `File`s whose body does
nothing to the bytes — that is `sendFileAll`, or `copyFile` when both ends are paths. Also
`readFileAlloc` or `allocRemaining` over a whole file that is only being copied onward.

```zig
// fragment — GOOD: path to path
try source_dir.copyFile("input.bin", dest_dir, "output.bin", io, .{});
```

```zig
// fragment — between handles already open
var read_buffer: [copy_buffer_max]u8 = undefined;
var write_buffer: [copy_buffer_max]u8 = undefined;
var fr = source.reader(io, &read_buffer);
var fw = target.writer(io, &write_buffer);
_ = try fw.interface.sendFileAll(&fr, .unlimited); // asserts fw buffer is nonempty
try fw.flush(); // the concrete flush reports the real error (ZS-CONC-08)
```

## Authoring custom streams

### ZS-CONC-15 [M] Implement `drain` to the full contract

Only `drain` is required (`sendFile`, `flush`, `rebase` have defaults). A correct `drain`: (1) emits
`w.buffered()` first and clears it via `w.consume(n)`/`w.consumeAll()`; (2) emits each element of
`data` but the last, in order; (3) emits the **last** element `splat` times in total, which may be
zero; (4) returns the count consumed **from `data` only**, excluding buffer bytes.

Override `flush` with `Io.Writer.noopFlush` only if your sink has no residual state (`Allocating`
does this). Override `rebase` only if your buffer can grow or must never move. Override `sendFile`
only if you have a genuine fd-to-fd fast path; the default returns `error.Unimplemented`, which
callers handle.

**Why:** each broken clause corrupts output: skipping (1) reorders the stream, assuming
`data.len == 1` drops vectored writes, ignoring `splat` turns `splatByteAll('-', 1_000_000)` into
one dash, and counting buffer bytes makes the caller skip bytes of `data` never written.

**Check:** read the `drain` body against the four numbered clauses — no `w.buffered()` before the
first emit; `data[0]` indexed instead of iterated; or the returned count accumulating anything
emitted from `w.buffered()`. Each is one line to spot. `rg -n '_ = splat;' -g '*.zig'` finds the
`splat` parameter discarded; each hit in a `drain` is the finding.

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

### ZS-CONC-16 [M] A custom `Reader` signals end of stream with `error.EndOfStream`, never `0`

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

### ZS-CONC-17 [M] Pair `writableSliceGreedy` with `advance`; never `advance` after `writableSlice`

`writableArray(len)` and `writableSlice(len)` advance by `len` before returning.
`writableSliceGreedy(min)` returns all unused capacity and does **not** advance — you must call
`w.advance(n)`.

**Why:** getting this backwards either duplicates bytes or writes into a region the writer already
considers written. It is a silent data bug with no compile error.

**Check:** a `writableSliceGreedy` with no `w.advance(n)` before the next write on that writer, and
an `advance` following a `writableSlice`/`writableArray`, both of which advanced already.

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

## Filesystem

### ZS-CONC-18 [M] Pair every open with `defer close(io)`, and iterate with the iterator's own buffer

`file.close(io)` and `dir.close(io)` both take the `Io`. `dir.iterate()` returns an `Iterator` that
embeds a 2 KiB buffer, so `it.next(io)` takes no buffer argument. The `Iterator` is ~2 KiB of stack
because it inlines its own `reader_buffer` (`next` re-points `reader.buffer` at it on every call, so
the value is movable) — bind it with `var` in the loop's own scope rather than nesting it inside a
recursive walk. Open a directory you will iterate with `.iterate = true`: without it Linux returns
an `O_PATH` descriptor and the first `next` fails with `BADF`, while macOS iterates it anyway. For
recursive traversal, and for the allocation-free `Io.Dir.Reader` beneath `Iterator`, see ZS-CONC-20.

**Why:** a `Dir` is a file descriptor exactly like a `File`; leaking directory handles exhausts the
per-process fd quota just as fast, and the failure surfaces far from the leak as
`error.ProcessFdQuotaExceeded` on some unrelated open.

**Check:** an `openFile`/`openDir`/`createFile`/`createFileAtomic` result not followed by its
`defer ….close(io)` or `defer ….deinit(io)` the way ZS-MEM-10 requires; a `close()` written without
an `io` argument; an `Io.Dir.Iterator` stored in a struct field or returned from a function rather
than bound to a `var` in the loop's own scope; and an `iterate()`, `walk(` or `walkSelectively(` on
a directory opened without `.iterate = true`.

```zig
// verified — GOOD
const std = @import("std");
test "directory iteration" {
    const io = std.testing.io;
    var tmp = std.testing.tmpDir(.{ .iterate = true });
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

### ZS-CONC-19 [M] Replace a file another reader depends on atomically, with `createFileAtomic`

`dir.createFileAtomic(io, sub_path, .{ .replace = true })` returns a `File.Atomic` holding an
unnamed ephemeral file. Write, flush, then `af.replace(io)`. `af.link(io)` is the create-if-absent
variant; `.replace` in the options must match which one you will call, or `replace` asserts.

This holds for a file that is authoritative state some later reader depends on — a database or a
WAL, configuration a service reads at boot, key material, a lockfile, anything another process reads
concurrently — and for every file that is *updated*, meaning read, modified and written back,
because its pre-write contents are the only copy of the data being replaced. A file regenerated from
scratch on every run — a build artifact, a cache, a scratch file — may use plain `writeFile`.

`af.deinit(io)` is safe to `defer` unconditionally: it removes the ephemeral file if
`replace`/`link` was never reached.

**Why:** truncating a file in place has a window in which the file is empty or half-written. If the
process dies there, the on-disk state is unrecoverable — the old contents are already gone and the
new ones are not there yet.

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
    var buffer: [64]u8 = undefined;
    var fw = af.file.writer(io, &buffer);
    try fw.interface.writeAll("new");
    try fw.flush();
    try af.replace(io);

    var read_buf: [16]u8 = undefined;
    try std.testing.expectEqualStrings("new", try tmp.dir.readFile(io, "state.json", &read_buf));
}
```

### ZS-CONC-20 [S] Pick the traversal API by who decides to descend

Four levels, cheapest first. `Io.Dir.Reader` — you supply a `[Reader.min_buffer_len]u8` aligned to
`usize` and batch entries with `read(io, &entries)`; no allocation. `dir.iterate()` — the ~2 KiB
self-buffering `Iterator` of ZS-CONC-18, one entry at a time. `dir.walkSelectively(gpa)` —
recursive, but *you* call `walker.enter(io, entry)` for each directory you want to descend into.
`dir.walk(gpa)` — recursive and descends unconditionally. Choose `walkSelectively` whenever any
subtree can be excluded; choose `Dir.Reader` when the traversal is hot enough that the `Iterator`'s
one-entry-per-call round trip shows up, or when you cannot allocate at all. Both walkers hand back
`Entry.path`/`basename` that are invalidated by the next `next` — copy before you keep one, exactly
as with reader slices (ZS-CONC-12).

**Why:** `walk` is `walkSelectively` with an automatic `enter` on every directory (its `Walker.next`
calls `enter` on each entry), so it cannot skip `.git`, `node_modules`, or a looping bind mount, and
filtering what it returns has already paid for the whole subtree.

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
// fragment — the allocation-free form
var buffer: [Io.Dir.Reader.min_buffer_len]u8 align(@alignOf(usize)) = undefined;
var dr: Io.Dir.Reader = .init(dir, &buffer);
var entries: [entry_batch_max]Io.Dir.Entry = undefined;
var files: usize = 0;
while (true) {
    const n = try dr.read(io, &entries);
    if (n == 0 and dr.state == .finished) break;
    for (entries[0..n]) |e| if (e.kind == .file) {
        files += 1;
    };
}
```

### ZS-CONC-21 [M] Say which race you mean: `rename`, `renamePreserve` or `hardLink`

`dir.rename(old_sub_path, new_dir, new_sub_path, io)` **replaces** the destination silently.
`dir.renamePreserve(...)` is the same call that returns `error.PathAlreadyExists` instead,
atomically — or `error.OperationUnsupported` where the filesystem cannot do a non-replacing rename.
`dir.hardLink(old_sub_path, new_dir, new_sub_path, io, options)` publishes a second name for one
inode. Note the shape shared by all three: the two path arguments straddle the destination `Dir` and
`io` comes **last**, before the options — this is the one family in `Io.Dir` that breaks the
receiver-then-`io` rule of ZS-CONC-02, and getting it wrong is a compile error, not a bug.

`hardLink` is the primitive behind content-addressed caches and atomic publication — link the new
name, then `rename` over the old one — and unlike a copy it cannot half-succeed. For an in-place
replacement of an existing file, ZS-CONC-19's `createFileAtomic` + `replace` remains the answer;
these are for the naming operations around it.

**Why:** "create this file only if it does not exist" and "create this file" are different programs,
and doing the check yourself (`if (exists) return error.X;` then rename) is a TOCTOU window that
another process wins. `renamePreserve` pushes the check into the same syscall.

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

    var buffer: [8]u8 = undefined;
    try std.testing.expectEqualStrings("v1", try tmp.dir.readFile(io, "new.txt", &buffer));
}
```

### ZS-CONC-22 [S] Map a large file you access at random with `createMemoryMap`

`file.createMemoryMap(io, options)` returns a `MemoryMap` whose `.memory` is a plain
`[]align(page_size_min) u8`. It may be a real mapping or file operations behind a buffer, so
`mm.read(io)` and `mm.write(io)` are the synchronization points — a change no `write` follows may or
may not reach the file — and `mm.destroy(io)` is the release. `CreateOptions.len` has no alignment
requirement, `offset` must be page-aligned, and `protection` must not exceed the mode the file was
opened with: the default `.{ .read = true, .write = true }` on a read-only handle is
`error.AccessDenied`. A small file is `readFileAlloc`'s.

**Why:** a `File.Reader` streams linearly, so random access over a large file through it is a seek
and a buffer refill per access; the map makes the file a slice, and its explicit sync points say
when the slice and the file agree, mapped or not.

**Check:** a `File.Reader` or positional-read loop seeking back and forth over a file too large to
read whole; a `createMemoryMap` with no `defer mm.destroy(io)`; a change to `.memory` meant to
persist with no `mm.write(io)` after it; a read-write map of a handle opened read-only.

## Structured concurrency

### ZS-CONC-23 [M] Every started `Future` is awaited or canceled exactly once, on every path

`io.async(f, args)` returns a `Future(R)` — `await` and `cancel` are idempotent but **not**
threadsafe. An early `return` that skips remaining futures abandons them. The correct fan-out shape
awaits *all* futures and only then propagates the first error.

The call's shape is `io.async(function, args_tuple)` — arguments go in a tuple, `Io` itself is
usually the first of them. `async` and `await` are no longer language keywords, which is why
`io.async` and `f.await(io)` are ordinary declarations.

**Why:** under `Io.Threaded` each future is a heap allocation plus a claimed slot against
`async_limit`; abandoning it leaks both and leaves a worker writing into a result slot whose stack
frame is gone.

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
/// Most shards fanned out per call; bounds the futures array.
const shard_max = 8;

fn fetchShard(io: Io, index: u32) FetchError!u32 {
    try io.sleep(.fromMilliseconds(1), .awake);
    if (index == 3) return error.Broken;
    return index * index;
}

/// Spawn N tasks, await ALL of them, propagate the first error.
fn fetchAll(io: Io, out: []u32) FetchError!void {
    var futures: [shard_max]Io.Future(FetchError!u32) = undefined;
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

### ZS-CONC-24 [S] Prefer `io.async`; use `io.concurrent` only for simultaneous progress

`io.async` guarantees only "already completed, or assigned a unit of concurrency" — it may run the
function inline before returning. `io.concurrent` demands real concurrency and can fail with
`error.ConcurrencyUnavailable`. `io.async` never fails; `Io.Threaded` degrades to inline execution
on OOM or when `async_limit` is reached (`Io/Threaded.zig`).

**Why:** running inline makes `async` work on single-threaded stackful backends and
`init_single_threaded`, but lets a producer spawned with it run to completion *before* the consumer
starts, which deadlocks on a bounded `Io.Queue`. Tasks that must interleave need `concurrent`.

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

### ZS-CONC-25 [S] Pick the right aggregate: `Group`, `Select`, or `Queue`

`Io.Group` is an unordered task set whose members return something coercible to `Cancelable!void`;
it is a cancellation-propagation boundary, so a member returning `error.Canceled` is absorbed.
`Io.Select(U)` waits on the first of several heterogeneous tasks, keyed by the fields of a tagged
union. `Io.Queue(T)` is a bounded MPMC channel closed with `q.close(io)`. `Select`'s buffer must be
large enough for all outstanding tasks or `cancel` deadlocks.

**Why:** `Group` releases each task's resources when *that task* returns, not when the group
completes, so a long-lived group is not a leak — but async tasks are not guaranteed to run until
`await`/`cancel`, so an abandoned group is.

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
// verified — `cancel` is the abandonment-safe exit
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

### ZS-CONC-26 [M] Never ignore `error.Canceled`

A cancellation point is any `Io` call whose error set contains `error.Canceled`. After a cancel
request, **only the next** cancellation point signals it; later ones do not re-signal. Respond by
propagating, by `io.recancel()` and continuing, or by entering cancel protection.

The tell is not the *shape* of the `catch` — `catch |err| log.warn(…)` strands a canceller exactly
as `catch {}` does, because logging *without propagating* is not responding. (Logging and then
returning the error is fine; that is ZS-ERR-07's "add context, then propagate".) What matters is
whether control then goes on to do more work.

One exemption, and only one: a cleanup on a path that is **already leaving** — a `defer`/`errdefer`
body, or a statement on an error path with nothing after it but the `return` — cannot strand anyone,
because no further work follows either way. Log the error there rather than discarding it silently
(ZS-ERR-10), or wrap the cleanup in cancel protection when it must actually happen.

std draws the line in the same place but stops short of logging: a bare `catch {}` on a cancelable
unlink appears in `std.testing.TmpDir.cleanup` (its `deleteTree`), `std.Io.File.Atomic.deinit`, and
the `testGetCurrentFileTimestamp` helper in `std.Build.Cache` — always on a leaving path, never
mid-flow. Read those as evidence for *where* the exemption lies, not as licence for the bare form;
this standard still wants it logged.

**Why:** swallowing the one signal you get converts a cancellation request into a task that runs
forever, and `Group.await`/`Future.cancel` then block indefinitely waiting for it.

**Check:** any `catch` on an expression taking an `io` — `catch {}`, `catch return`,
`catch continue`, `catch unreachable`, **or `catch |err| log…`** — after which the function keeps
working; and a `switch` over an `Io` error set with an `else => {}` arm, which absorbs
`error.Canceled` without naming it. The legal responses all name it: propagate, `io.recancel()`, or
enter cancel protection. A cleanup on a path that is already leaving is exempt per the exemption
above.

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

### ZS-CONC-27 [M] Call `io.checkCancel()` inside long CPU-bound loops

`checkCancel` is a pure cancellation point that performs no I/O. Check on a power-of-two stride so
the check itself is not the cost.

Every loop whose trip count comes from input, a file or the network rather than from a compile-time
constant gets one; a loop bounded by a named `_max` may skip it, because its worst-case duration is
known and reviewable — unless the system has a shutdown path, a request deadline or a watchdog, as a
server, a database or a consensus node does, where every long CPU-bound loop gets one.

**Why:** cancellation only takes effect at cancellation points. A loop that does no I/O is
uninterruptible, so a shutdown, a deadline, or a watchdog cannot preempt it — the task keeps burning
a carrier thread while whoever requested the cancel blocks in `await`.

**Check:** in a function that takes an `io`, a loop — a `while (true)`, or a `for (0..n)` over a
runtime length — with no `io.*` call anywhere in its body, a bound that is not a small compile-time
constant, and no `io.checkCancel()` on a stride inside it.

```zig
// verified — GOOD
const std = @import("std");
const Io = std.Io;
fn grind(io: Io, iterations: usize) Io.Cancelable!u64 {
    var acc: u64 = 0;
    for (0..iterations) |i| {
        if (i % 1024 == 0) try io.checkCancel();
        acc += i;
    }
    return acc;
}
```

### ZS-CONC-28 [M] Use the `*Uncancelable` variants in `defer` and cleanup paths

`Mutex.lockUncancelable`, `RwLock.lockUncancelable`, `RwLock.lockSharedUncancelable`,
`Condition.waitUncancelable`, `Event.waitUncancelable`, `Semaphore.waitUncancelable`,
`Queue.putUncancelable` / `putOneUncancelable` / `getUncancelable` / `getOneUncancelable`, and
`io.futexWaitUncancelable`. Those 11 names are the whole callable surface for 0.17. A grep counts 14
`pub fn *Uncancelable` — the other three are `TypeErasedQueue.putUncancelable`/`getUncancelable`,
which are the untyped layer `Queue` forwards into rather than separate APIs, and
`noFutexWaitUncancelable`, an internal vtable stub taking `userdata: ?*anyopaque` — from `Io.zig`,
`Io/RwLock.zig`, and `Io/Semaphore.zig`. 0.17 adds `Semaphore.waitTimeout(io, timeout)`, which is
cancelable and has no uncancelable timed form, so it never belongs in a `defer`. The `Uncancelable`
variants return `void` (or drop `Cancelable` from the set, as the `Queue` pair do).

**Why:** a `defer` body cannot propagate an error, so a cancelable blocking call inside one — a lock
acquisition, a queue hand-off, an event wait — has no correct failure handling; you would have to
`catch unreachable` on a reachable condition.

**Check:** a `defer` or `errdefer` body calling the *cancelable* spelling of any primitive on the
list above — `m.lock(io)`, `rw.lock(io)`, `rw.lockShared(io)`, `c.wait(io, …)`, `e.wait(io)`,
`sem.wait(io)`, `q.put(io, …)` / `putOne` / `get` / `getOne`, `io.futexWait(…)` — and any
`catch unreachable` or `catch {}` wrapped around one of those calls. Both are the same finding
wearing different clothes: the `catch` is there only to paper over the wrong spelling.

Scope: this rule is about primitives that *have* a correct uncancelable form. A `defer` cleanup with
no such twin — `dir.deleteFile(io, path)`, which has no `deleteFileUncancelable` — is governed by
ZS-CONC-26's already-leaving exemption instead, not by this rule. Do not report it here.

### ZS-CONC-29 [M] Synchronize with the `Io` primitives, never OS primitives

`std.Thread` has **no** synchronization primitives in 0.17 — no `Mutex`, `Condition`, `Semaphore`,
`RwLock`, `ResetEvent`, `WaitGroup`, `Pool`, or `Futex`. All of them moved to `std.Io` and take an
`io`. There is no `Io.Futex` type — `futexWait`/`futexWake` are free functions on `Io`.
`std.atomic.Mutex` is a lock-free `tryLock`/`unlock` pair with no blocking `lock`; it is not a
substitute.

**Why:** this is correctness, not taste. An OS mutex blocks the whole carrier thread, which under an
evented or fiber backend is running other tasks, possibly the one holding the lock: a deadlock that
only manifests on the non-default backend.

**Check:** `std.Thread.Mutex`, `.Condition`, `.Semaphore`, `.RwLock`, `.ResetEvent`, `.WaitGroup`,
`.Pool`, or `.Futex` in a diff — all are compile errors in 0.17 (`has no member named 'Mutex'`), and
none of the messages names the `std.Io` replacement, so name it in the review. `std.atomic.Mutex` is
the one that *does* compile and is still the finding: it has no blocking `lock`, so a
`while (!m.tryLock()) {}` around it is a spin that no scheduler can preempt.

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

### ZS-CONC-30 [M] Write colorless code: never branch on which backend you were handed

The same function body must be correct under `Io.Threaded`, `Io.Evented`, `init_single_threaded`,
and `Io.failing`. Do not inspect `io.userdata`, do not compare `io.vtable`, do not gate behavior on
`builtin.single_threaded`. The only backend-dependent behavior you may rely on is the documented
one: `io.concurrent` may return `error.ConcurrencyUnavailable`, and you must handle it.

**Why:** the colorless property — no `async fn` infection, no duplicated sync/async APIs — exists
because the function is written once against `Io` and the *caller* chooses the execution model,
which every backend test (`std.testing.io` today, an io_uring ring tomorrow) depends on.

**Check:** `io.userdata`, `io.vtable`, `@TypeOf(io)`, or `builtin.single_threaded` read anywhere
inside a function that also performs I/O; and any `if`/`switch` selecting between two
implementations of the same operation on that basis. The one legal backend-dependent branch is the
`error.ConcurrencyUnavailable` arm of an `io.concurrent`.

### ZS-CONC-31 [S] Use raw `std.Thread` only for dedicated, long-lived OS threads

`std.Thread.spawn`/`join`/`detach`/`getCpuCount`/`yield` are correct, and so is `setName`, which
takes an `Io`: `thread.setName(io, name)`. Use them for a thread that must own a resource for the
process lifetime — a signal-handling thread, a real-time audio callback thread, a thread pinned to a
core. When you do use `std.Thread`, synchronize with `std.atomic.Value` or an `Io` primitive; there
is nothing else left.

**Why:** `Io` tasks are units of work with a scheduler behind them. A thread that owns a resource
for the process lifetime is not a unit of work and gains nothing from `Io`; everything else should
be `io.async`/`Group`, so it stays substitutable.

**Check:** a `std.Thread.spawn` whose `join` is in the same function — that is a unit of work, so it
is `io.async`. A legitimate use spawns once during startup and either `detach`es or joins during
shutdown, and the entry function's body is a `while (true)` owning one resource.

### ZS-CONC-32 [M] Time is `Io`: `Io.Timestamp`, `Io.Duration`, `Io.Clock`, `io.sleep`

`std.time` is unit constants plus `std.time.epoch` and nothing else — no `Timer`, no `Instant`, no
`timestamp()`, no `sleep()`. `Io.Clock` variants are exactly `real`, `awake`, `boot`, `cpu_process`,
`cpu_thread`; the monotonic clock is `.awake` and `.monotonic` is a compile error. Duration
constructors are spelled in full: `fromNanoseconds`, `fromMicroseconds`, `fromMilliseconds`,
`fromSeconds`. Pick the clock by what you measure: `.awake` excludes suspend and never goes
backwards, so it is the one for latency and benchmarks; `.real` is settable and can jump, so a
measurement taken with it says why; `.cpu_thread` and `.cpu_process` count CPU time, not wall time.

**Why:** a clock is nondeterminism, so it belongs behind the same interface as the rest of it. That
is what makes deterministic simulation testing possible: a test `Io` can advance time by fiat.
Reading the wall clock through a global would defeat it.

**Check:** `std.time.Timer`, `std.time.Instant`, `std.time.timestamp`, `milliTimestamp`,
`nanoTimestamp`, or `std.time.sleep` anywhere in a diff; `.monotonic` used as an `Io.Clock`; and any
abbreviated `Duration` constructor (`fromMs`, `fromNs`) — the names are spelled in full. Also a
benchmark timed with `.real` and no comment saying why.

```zig
// fragment — GOOD
try io.sleep(.fromMilliseconds(1), .awake);
const now: Io.Timestamp = .now(io, .awake);
// Durations print with {f}: `Io.Duration.fromMilliseconds(1500)` renders as "1.5s".
```

### ZS-CONC-33 [S] Express a multi-step timeout as one shared deadline, not a duration per call

`Io.Timeout` is `union(enum) { none, duration: Clock.Duration, deadline: Clock.Timestamp }`.

**Why:** N steps each given a 50 ms duration is a 50N ms worst case, which is not the budget anyone
intended. A single `.deadline` computed once bounds the whole operation regardless of how it is
decomposed. Use the `.duration` form only for a genuinely single wait.

**Check:** two or more `.duration` timeouts on the steps of one logical operation — connect, then
write, then read, each given its own budget. The fix is one deadline made at entry and threaded
through: `timeout.toDeadline(io)` turns whatever the caller passed into one, and `.none` stays
`.none`. A function that performs more than one waiting call holds one `Io.Timeout` value, or it is
the finding.

```zig
// verified — GOOD
const std = @import("std");
const Io = std.Io;

/// Both waits share the caller's budget: it becomes one deadline at entry.
fn waitBoth(io: Io, first: *Io.Event, second: *Io.Event, timeout: Io.Timeout) !void {
    const deadline = timeout.toDeadline(io);
    try first.waitTimeout(io, deadline);
    try second.waitTimeout(io, deadline);
}

test "timeout as a deadline, not a per-call duration" {
    const io = std.testing.io;
    var first: Io.Event = .unset;
    var second: Io.Event = .unset;
    first.set(io);

    const budget: Io.Timeout = .{ .duration = .{ .raw = .fromMilliseconds(50), .clock = .awake } };
    try std.testing.expectError(error.Timeout, waitBoth(io, &first, &second, budget));
}
```

## TigerStyle, re-derived for `std.Io`

### ZS-CONC-34 [M] Drain a batch of what a peer sends; do not wake once per event

TigerStyle: *don't do things directly in reaction to external events; your program should run at its
own pace.* In 0.17 that means `q.get(io, &batch, 1)` — which returns up to `batch.len` items in one
wake-up — rather than `q.getOne(io)` in a loop, and `writeVecAll`/`sendFileAll` rather than a write
per record.

Anything that crosses the process boundary is amortized over a batch — one `flush` and one
`writeVecAll` per batch of records, never per record. A per-event `getOne` loop is acceptable only
where the event rate is bounded by a human or by a file the program already holds, not by a peer.
The non-I/O half of this is ZS-PERF-05.

`Io.Batch` + `Io.Operation` is the lowest-level form of the same idea: N operations submitted
together, results collected with `batch.next()`. `awaitAsync` returns once *at least one* has
completed, so collect until every submitted operation has been seen — a count of the `add` calls,
not `storage.len`, which is only the capacity: awaiting an operation that was never added blocks
forever. `read_batch_max` is that capacity's named bound (ZS-CONC-37). Reach for `Io.Batch` only
when `Future`/`Group` measurably costs too much per operation.

**Why:** one wake-up per event means one context switch, one scheduler round-trip, and one set of
assertion re-checks per event. Batching amortizes all three and bounds work per time period, which
is what makes the per-batch assertions affordable.

**Check:** `q.getOne(io)` inside a `while`; a `writeAll`/`print` plus a `flush` per record inside a
loop over records; an `io.async` per event rather than per batch. The batched forms are
`q.get(io, &batch, 1)`, `writeVecAll`/`sendFileAll`, and one task per batch — and each batch array
needs the named `_max` of ZS-CONC-37 plus an assertion on the returned count.

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

```zig
// fragment — `Io.Batch`: two reads submitted as one batch, both collected
var storage: [read_batch_max]Io.Operation.Storage = undefined;
var batch: Io.Batch = .init(&storage);
defer batch.cancel(io);

var pending: usize = 0;
_ = batch.add(.{ .file_read_streaming = .{ .file = fa, .data = &.{&buf_a} } });
pending += 1;
_ = batch.add(.{ .file_read_streaming = .{ .file = fb, .data = &.{&buf_b} } });
pending += 1;
assert(pending <= storage.len);

while (pending > 0) {
    try batch.awaitAsync(io);
    while (batch.next()) |completion| : (pending -= 1) {
        _ = try completion.result.file_read_streaming;
    }
}
```

### ZS-CONC-35 [M!] A suspension point invalidates every entry-time assertion about shared state

TigerStyle says: *ensure functions run to completion without suspending, so that precondition
assertions are true throughout the lifetime of the function.* Under `io.async` that rule cannot be
followed literally — any `io.*` call is a suspension point. The 0.17 form of the rule: assert about
shared state only in a region where you hold exclusive access, and re-establish the assertion after
every `io.*` call.

The pure-function corollary still holds and is now easier to satisfy: a function that takes only its
own inputs and no `io` cannot suspend, so its preconditions hold for its whole body. Push `io` calls
to the edges and keep the computational core `io`-free — that is where TigerStyle's assertion
density belongs.

*Relaxed form:* do not write an assertion about shared state *above* a suspension point at all: move
it below the acquisition or delete it. That is weaker than re-establishing the invariant after every
`io.*` call, but it still forbids the specific line that lies.

**Why:** between `try a.lock.lock(io)` and its return, other tasks in the same `Io` run and mutate
`a`, so an assertion written before the lock documents a fact that is false by the time the code
after it executes — worse than no assertion, because it reads as a guarantee.

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

### ZS-CONC-36 [M] Replace completion callbacks with `io.async` and `await`

What `std.Io` kills is the callback-**driven I/O** pattern: the `read_sector()` /
`read_sector_callback()` pair, the continuation threaded through an `on_complete` field, the state
machine that exists only to remember where to resume. Do not write those. `io.async(f, args)`
returns a `Future` and `f.await(io)` resumes in the caller's own lexical scope, so there is no
completion to name and nothing to position. TigerStyle's *other* callback rule — a function value
passed as data goes last, after its `context` — survives, and ZS-NAME-10 owns it.

**Why:** callback-driven I/O exists where there is no I/O interface to suspend through, so
TigerBeetle hand-rolled a callback-threaded event loop. The interface is the replacement, and it
removes the naming problem rather than solving it.

**Check:** in a diff, a `*_callback` parameter or field, an `on_*` completion field, or a function
split into `doThing` / `doThingCallback` — all should be `io.async` + `await`.

The TigerStyle rules this chapter *does* keep — bounded buffers, bounded queues, batching, assertion
density — are independent of the I/O model and carry over unchanged.

### ZS-CONC-37 [M] Bound every stream buffer and queue with a named compile-time constant

Reader buffers, writer buffers, `Io.Queue` storage, `Io.Select` storage, `Io.Batch` storage, and
`Io.Group` fan-out width are all caller-provided fixed arrays. Size each from a `const` with a name
and a comment saying what it bounds, not from a literal at the call site. This is ZS-ASSERT-19
applied to `std.Io`, where the length of the array is also the maximum line, message, or fan-out
width.

**Why:** the API already refuses to allocate on your behalf, so the only question is whether the
bound is documented or accidental. A name also lets an assertion state the relationship
(`assert(out.len <= futures.len)`).

**Check:** outside a `test` block, an array length written as a bare numeric literal at the point of
declaration — `var buffer: [4096]u8`, `[8]Io.Future(…)`, `var storage: [2]u32` feeding `Queue.init`
— with no named constant. The declarations to sweep are reader and writer buffers, `Io.Queue`
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

## Networking

`std.net` is gone; networking is `std.Io.net`, and it obeys every rule above — `Io` after the
receiver, `Io.Limit` on reads, `error.Canceled` never swallowed, buffers sized deliberately. Only
`Io.Threaded` implements it in 0.17.0 (ZS-CONC-03).

### ZS-CONC-38 [M] Build the address first; `listen`, `bind`, and `connect` are methods on it

`net.IpAddress` is `union(enum) { ip4: Ip4Address, ip6: Ip6Address }` and is the entry point for
every connection. `address.listen(io, options) -> Server` for connection-oriented work,
`address.bind(io, options) -> Socket` for datagrams, `address.connect(io, options) -> Stream` for a
client. Note the parameter order: the address is the receiver, `io` comes immediately after it
(ZS-CONC-02). There is no free `net.listen(io, "127.0.0.1", 8080)`.

Two constructors, and the difference matters: `IpAddress.parse(text, port)` is **pure** and cannot
handle an IPv6 scope; `IpAddress.resolve(io, text, port)` takes an `Io` precisely because
`fe80::1%eno1` needs a syscall to turn `eno1` into an interface index. `parseLiteral(text)` handles
the combined `addr:port` / `[v6addr]:port` spellings. For a DNS name, use
`net.HostName.connect(host, io, port, options)`, which is a Happy-Eyeballs racer built on
`io.async` + `Io.Queue` — do not hand-roll one.

`ListenOptions` defaults to `.{ .mode = .stream, .protocol = .tcp, .kernel_backlog = 128 }` and
`reuse_address = false`; `BindOptions` and `ConnectOptions` require `mode` explicitly, because a
datagram socket and a stream socket are not interchangeable and std refuses to guess.

**Why:** routing everything through a parsed `IpAddress` means the parse failure and the connect
failure are separate error sets at separate call sites, instead of one function that can fail for
either reason.

**Check:** `std.net` anywhere; `IpAddress.parse` on a string that may carry a `%scope`;
`ConnectOptions` left at `.timeout = .none` on an outbound connection to an untrusted host.

```zig
// fragment — GOOD
test "address parsing" {
    const a: net.IpAddress = try .parse("127.0.0.1", 8080);
    try std.testing.expectEqual(8080, a.getPort());
    var buffer: [64]u8 = undefined;
    try std.testing.expectEqualStrings("127.0.0.1:8080", try std.mem.print(&buffer, "{f}", .{a}));
}
```

### ZS-CONC-39 [M] A socket is an ordinary stream source — and `.limited` is not optional on one

`stream.reader(io, &buffer)` and `stream.writer(io, &buffer)` return `net.Stream.Reader` /
`net.Stream.Writer`, each with an `interface` field and an `err` field, so the buffer-then-flush
rules apply unchanged (ZS-CONC-04, ZS-CONC-06, ZS-CONC-08). Every socket read and write is also a
cancellation point (ZS-CONC-26): a `catch {}` around one strands a shutdown on a silent peer.

The example's accept side runs under `io.concurrent`, not `io.async`: the server must make progress
while the client connects, which is exactly the interleaving requirement of ZS-CONC-24.
`net.Stream.Writer.sendFile` is `error.Unimplemented` in 0.17, so `sendFileAll` over a socket
silently falls back to the userspace copy loop — the ZS-CONC-14 zero-copy argument does not apply to
sockets in 0.17.

**Why:** the peer chooses how many bytes arrive and when, which makes a socket the canonical
untrusted input boundary of ZS-CONC-13: `.unlimited` there is an attacker-controlled allocation, and
an unsized reader buffer an attacker-controlled maximum message length (ZS-CONC-10).

**Check:** `.unlimited` passed to any read over a `net.Stream`. A bare-literal socket buffer is the
ZS-CONC-37 finding, and a missing `flush` before `stream.close(io)` the ZS-CONC-04 one.

```zig
// fragment — GOOD
const std = @import("std");
const Io = std.Io;
fn serve(io: Io, server: *net.Server) !void {
    const conn = try server.accept(io);
    defer conn.close(io);

    var buffer: [reply_buffer_max]u8 = undefined;
    var cw = conn.writer(io, &buffer);
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

### ZS-CONC-40 [M] Close every socket on every path; `shutdown` is how you unblock a blocked peer

`stream.close(io)`, `socket.close(io)`, and `server.deinit(io)` each take the `Io`, exactly like
`file.close(io)` — pair each with a `defer` on the acquisition line (ZS-MEM-10). To wake a task
parked in `accept` or a read, call `stream.shutdown(io, .recv/.send/.both)` from another task. That
is documented behavior, not a trick: `Server.accept`'s `error.SocketNotListening` carries the
comment "This allows `shutdown` to be used as a concurrent cancellation mechanism."

`net.Socket.closeMany(io, sockets)` closes a batch in one call. `Socket.createPair(io, .{})`
defaults to `.family = .ip4`, which `socketpair` rejects on Darwin: there it returns
`error.Unexpected`.

**Why:** a socket is a file descriptor, so a leaked one fails like a leaked `Dir` (ZS-CONC-18). On a
graceful-shutdown path, `shutdown` is how an accept loop returns so its `Group` can be awaited
rather than abandoned (ZS-CONC-23).

**Check:** an `accept`/`connect`/`createPair` result not followed by its `defer …close(io)` the way
ZS-MEM-10 requires; an accept loop with no way to be woken.

## Subprocesses

`std.process.Child.init` + `spawn()` is the 0.14 shape and does not exist. In 0.17 the two entry
points are free functions taking `io`, and the choice between them is whether you want the output or
the stream.

### ZS-CONC-41 [M] `std.process.run` for the output; `std.process.spawn` for the stream

The exact signatures are the first example's, from `std/process.zig`.

`RunResult` is `{ term: Child.Term, stdout: []u8, stderr: []u8 }` and **the caller owns both
slices**. `RunOptions` carries `exe`, `argv`, `stdout_limit`/`stderr_limit` (`Io.Limit`),
`reserve_amount`, `cwd`, `environ_map`, `progress_node`, and `timeout: Io.Timeout`. `SpawnOptions`
carries `exe`, `argv`, `cwd`, `environ_map`, `progress_node`, `inherit_dirs`/`inherit_files`, and
`stdin`/`stdout`/`stderr`, each a
`StdIo = union(enum) { inherit, file: File, ignore, pipe, close }`. `exe` says how `argv[0]` is
found — `.detect` (the default), `.search` on `PATH`, `.path` relative to a `Dir`, `.file`, or
`.explicit` — so a child relative to a directory is `.exe = .{ .path = dir }`. Note the ordering
rule holds: `run` is a free function so `gpa` precedes `io` (ZS-CONC-02).

`run` is `spawn` with `.stdin = .ignore, .stdout = .pipe, .stderr = .pipe` plus an
`Io.File.MultiReader` that drains both pipes concurrently. Use `spawn` only when you need the output
*incrementally* — a build tool relaying a compiler's diagnostics as they appear — or need a `StdIo`
shape `run` does not offer.

**Why:** draining concurrently is the whole point: a child that fills the stderr pipe blocks forever
while you read stdout, and hand-rolling `spawn` plus two sequential reads reintroduces exactly that
deadlock.

**Check:** `stdout_limit`/`stderr_limit` left at their `.unlimited` default on a child whose output
is not bounded by construction (ZS-CONC-13); `run`'s `result.stdout`/`result.stderr` without a
`defer gpa.free`; any surviving `std.process.Child.init`.

```zig
// fragment — from std/process.zig
pub fn spawn(io: Io, options: SpawnOptions) SpawnError!Child;
pub fn run(gpa: Allocator, io: Io, options: RunOptions) RunError!RunResult;
pub fn replace(io: Io, options: ReplaceOptions) ReplaceError; // never returns on success
```

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

### ZS-CONC-42 [M] `child.wait(io)` closes the pipes; never close `child.stdout`/`stderr` yourself

`Child` exposes `stdin`, `stdout`, `stderr` as `?File`, populated for each stream you set to
`.pipe`. Read them through a normal `File.Reader`, then call `wait`. `wait` reaps the process
**and** closes every pipe it opened. Pair the spawn with `errdefer child.kill(io)` so an error
between spawn and `wait` does not leave an orphan, and let `wait` be the single release point on the
success path.

`stdin = .pipe` is the mirror image: write to the child's `stdin` through a `File.Writer`, `flush`,
and then let `wait` close it — but a child that is still reading stdin will not exit, so a program
that both feeds and drains a child needs the two directions on separate tasks (`io.concurrent`,
ZS-CONC-24), not sequentially.

**Why:** `?File` looks like a handle you own, but closing it before `wait` is a double close that
panics in `wait`'s cleanup: `std.Io.Threaded.closeFd` maps `.BADF => recoverableOsBugDetected()`,
which is `reached unreachable code` in a `debug` build.

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

    var buffer: [64]u8 = undefined;
    var stdout = child.stdout orelse return error.TestUnexpectedResult;
    var cr = stdout.readerStreaming(io, &buffer);
    var lines: usize = 0;
    while (try cr.interface.takeDelimiter('\n')) |_| lines += 1;

    // `wait` closes the pipe files itself; closing them here is a double close.
    const term = try child.wait(io);
    try std.testing.expectEqual(std.process.Child.Term{ .exited = 0 }, term);
    try std.testing.expectEqual(2, lines);
}
```

## Terminals and progress

### ZS-CONC-43 [S] Decide color with `Io.Terminal`, not with your own `isatty` check

`Io.Terminal` is `{ writer: *Io.Writer, mode: Mode }`, and `t.setColor(color)` emits through it. For
stderr, `io.lockStderr(&buffer, null)` has already chosen the mode, from the handle and from
`NO_COLOR` and `CLICOLOR_FORCE` in the process environment: take `locked.terminal()`. For any other
file, build the mode with `Io.Terminal.Mode.detect(io, file, NO_COLOR, CLICOLOR_FORCE)`, where the
two `bool`s mean "the environment variable is present and non-empty" — read them from
`init.environ_map`. `detect` calls `file.enableAnsiEscapeCodes`, which on Windows mutates console
mode. `Mode` is `union(enum) { no_color, escape_codes, windows_api }`, so `.no_color` makes
`setColor` a no-op and the same code path serves a pipe.

Deviate only if you are emitting a format whose color is part of the data rather than a presentation
choice — say so in a comment.

**Why:** the mode folds four decisions into one value — is the handle a terminal, can ANSI escapes
be *enabled* on it, does `NO_COLOR` forbid color, does `CLICOLOR_FORCE` demand it anyway — and
hand-rolling them gets the Windows console path and the `NO_COLOR` convention wrong.

**Check:** any `isatty`, `std.io.tty`, or hard-coded `"\x1b[31m"` in a diff; reading `NO_COLOR`
without also honoring `CLICOLOR_FORCE`; and a `Mode.detect` on stderr, whose lock already holds the
mode.

```zig
// verified — GOOD
const std = @import("std");
test "stderr color through the lock's own terminal" {
    const io = std.testing.io;
    var buffer: [64]u8 = undefined;
    // The lock detected the mode, honoring NO_COLOR and CLICOLOR_FORCE.
    const locked = try io.lockStderr(&buffer, null);
    defer io.unlockStderr();
    const t = locked.terminal();
    try t.setColor(.red);
    try t.setColor(.reset);
}
```

### ZS-CONC-44 [S] Report long work through `std.Progress`, and pass the node to children

`std.Progress.start(io, .{ .root_name = "…" })` returns the root `Node`; `node.start(name, total)`
opens a child, `completeOne`/`setCompletedItems`/`setEstimatedTotalItems` update it, `node.end()`
closes it. `Node.none` is the do-nothing node, so progress-aware code needs no `?Node`. Progress
crosses process boundaries: both `SpawnOptions` and `RunOptions` carry a `progress_node`, and std
wires a pipe through the `ZIG_PROGRESS` environment variable so the child's tree grafts into the
parent's. A build tool that does not pass its node makes every subprocess a black box in the
display.

Deviate for a program with no interactive lifetime — a filter in a pipeline. `start` asserts it is
called once per process, so a library never calls it; a library takes a `Node` parameter and
defaults it to `.none`.

**Why:** it is why ZS-CONC-09 exists — `Progress` takes the same stderr lock as `std.log` and the
panic handler, so it is the *reason* ad-hoc stderr writes corrupt output, and the thing to use
instead of printing "processing 5/100" yourself.

**Check:** a `std.process.spawn`/`run` inside a progress-reporting tool with no `progress_node`; a
manual "N/M" counter printed to stderr; `std.Progress.start` in library code.

```zig
// verified — GOOD: a `main`, because `start` is process-global
const std = @import("std");
/// Maximum shards indexed per run; bounds the progress denominator (ZS-CONC-37).
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
