# What changed: dead APIs and the 0.13 -> 0.16 migration table

Lookup tables for every spelling that changed between Zig 0.13/0.14 and **0.16.0**. Use this chapter
to answer "does this symbol still exist, and what is it called now?" — it is a dictionary, not a
tutorial. Rationale for the *new* designs (how to structure `std.Io` code, how to pick an allocator,
how to lay out `build.zig`) lives in the std.Io, memory, and build chapters; the language-design
reasoning lives in the types and control-flow chapters. Every row below was checked against the
0.16.0 standard-library source tree — locate yours with `zig env | grep std_dir` — or by compiling a
probe with `zig 0.16.0`; rows that are only claimed by release notes are marked.

This chapter is the **single home for dead-API tables**. Other chapters teach the new designs and
cite these tables rather than reprinting them — in particular `references/io-and-concurrency.md`
ZS-IO-39 points at ZS-MIG-03 (streams), ZS-MIG-05 (filesystem), and ZS-MIG-10 (concurrency, time,
randomness).

Every example assumes a file opening with `const std = @import("std");` and
`const assert = std.debug.assert;` — assertions are called bare, per ZS-ASRT-01. Snippets that use
`io` or `gpa` assume they came from `std.process.Init` (ZS-MIG-09) or `std.testing`.

The tables use three status values:

| Status | Meaning |
|---|---|
| **gone** | The old spelling is a compile error. Loud failure. |
| **alias** | The old spelling still compiles as a deprecated alias. **Silent** staleness. |
| **wrong output** | Compiles, runs, produces different results than you intended. Worst case. |

## Contents

- **Part 1 — Verify against the local std, never from memory**
  - ZS-MIG-01 [M] Write 0.16.0 spellings; verify unfamiliar std symbols against local std
- **Part 2 — Language: removed syntax and builtins**
  - ZS-MIG-02 [M] Language: removed syntax and builtins
- **Part 3 — Writergate: streams, formatting, and the filesystem**
  - ZS-MIG-03 [M] Writergate: `std.io` is `std.Io`, and every stream carries its own buffer
  - ZS-MIG-04 [M] The `format` method takes only a writer, and only `{f}` calls it
  - ZS-MIG-05 [M] Filesystem: `std.fs` is a six-declaration shim; use `std.Io.Dir` / `std.Io.File`
- **Part 4 — Silent renames: search, containers, allocators**
  - ZS-MIG-06 [M] `std.mem.indexOf*` is now `find*` — these are silent aliases
  - ZS-MIG-07 [M] Containers: `ArrayList` is the unmanaged one; `gpa` is a per-call parameter
  - ZS-MIG-08 [M] Allocators: `DebugAllocator` replaced `GeneralPurposeAllocator`
- **Part 5 — Entry point, concurrency, and testing**
  - ZS-MIG-09 [M] Entry point: `pub fn main(init: std.process.Init) !void`
  - ZS-MIG-10 [M] Concurrency, sync, time, and randomness all moved onto `std.Io`
  - ZS-MIG-11 [M] Testing: `std.testing.io`, `Smith` fuzz inputs, `tmpDir(Io.Dir.OpenOptions)`
- **Part 6 — Build system and miscellaneous renames**
  - ZS-MIG-12 [M] Build: artifacts take `.root_module`; `.name` is an enum literal in `.zon`
  - ZS-MIG-13 [M] Miscellaneous std renames
- **Part 7 — Enforcing it**
  - ZS-MIG-14 [M!] Fail the build on deprecated-but-compiling spellings
  - SMELL TEST

---

## Part 1 — Verify against the local std, never from memory

### ZS-MIG-01 [M] Write 0.16.0 spellings; verify unfamiliar std symbols against local std

Never emit a `std.*` symbol from memory of an older Zig. Grep the installed std source before you
type a signature. The 0.13/0.14 era is the single largest source of wrong Zig.

**Why:** roughly a third of the migrations below are **alias** or **wrong output** rows, not
**gone** rows. `zig build` passing proves nothing about whether the code is current —
`std.mem.indexOf`, `std.ArrayListUnmanaged`, `std.array_list.Managed`, `std.fs.path`,
`std.fmt.bufPrintZ` and `EnumSet.initEmpty()` all compile clean in 0.16.0 and all are marked `///
Deprecated` in the source.

**Check:** run the denylist grep of ZS-MIG-14 over the diff — it collects the alias rows from every
table below. Separately, every `std.*` signature new to the diff must be findable by `grep -rn` in
the local std tree; one that is not is misremembered, not merely misspelled.

```sh
# GOOD — the only reliable check. Run it, don't recall it.
grep -rn "pub fn takeDelimiter" "$(zig env | grep std_dir)"/Io/Reader.zig
```

---

## Part 2 — Language: removed syntax and builtins

### ZS-MIG-02 [M] Language: removed syntax and builtins

All rows below were confirmed by compiling a probe with `zig build-obj` on 0.16.0.

**Why:** not applicable — this section is a lookup table, not a single rule. The rationale for each
replacement is owned by the chapter that teaches it: the `@Type` split is
`references/comptime-and-generics.md` ZS-CT-18, `usingnamespace` is ZS-CT-27, colorless concurrency
is `references/io-and-concurrency.md`, and `@branchHint` is `references/errors-and-control-flow.md`
ZS-ERR-31.

**Check:** grep the diff for `usingnamespace`, `@Type(`, `@setCold`, `@fence(`, `@setAlignStack`,
`callconv(.C)`/`.Stdcall`/`.Naked`, `@typeInfo(` followed by a `TitleCase` field, `anyframe`,
`@frameSize`, `suspend`/`resume`, and `@export(` whose first argument has no leading `&`. Every hit
is a hard compile error on 0.16.0, so a hit also means the file was never built against it.

| Old (0.13/0.14) | 0.16.0 | Status | Exact diagnostic / note |
|---|---|---|---|
| `usingnamespace` | removed; re-export explicitly, one `pub const` per name | gone | `expected function or variable declaration after pub` |
| `async f()`, `await`, `suspend`, `resume`, `anyframe`, `@frameSize` | removed as keywords; concurrency is `io.async` / `Future.await` | gone | `async` now parses as an ordinary identifier |
| `@Type(.{ .int = ... })` | `@Int`, `@Tuple`, `@Pointer`, `@Fn`, `@Struct`, `@Union`, `@Enum`, `@EnumLiteral` | gone | `invalid builtin function: '@Type'` |
| `@setCold(true)` | `@branchHint(.cold)` (also `.likely`, `.unlikely`, `.unpredictable`, `.none`) | gone | `invalid builtin function: '@setCold'` |
| `@fence(order)` | removed; strengthen the atomic orderings instead | gone | `invalid builtin function: '@fence'` |
| `@setAlignStack(n)` | `callconv(.withStackAlign(.c, n))` | gone | `std.builtin.CallingConvention.withStackAlign` |
| `callconv(.C)`, `.Stdcall`, `.Naked` | `callconv(.c)`, `.winapi`, `.naked` | gone | `union 'builtin.CallingConvention' has no member named 'C'` |
| `@export(foo, .{...})` | `@export(&foo, .{...})` | gone | `expected pointer type, found 'fn () void'` |
| `@typeInfo(T).Int`, `.Struct`, `.ComptimeInt`, `.Pointer.Size.One` | `.int`, `.@"struct"`, `.comptime_int`, `.one` | gone | `no field named 'Int' in union 'builtin.Type'` |
| `asm volatile (... ::: "rcx", "r11")` | `asm volatile (... ::: .{ .rcx = true, .r11 = true })` | gone | `expected ')', found ','` |
| pointer field in a `packed struct`/`packed union` | store `usize`; `@ptrFromInt`/`@intFromPtr` at the boundary | gone | `packed structs cannot contain fields of type '*u8'` |
| `v[runtime_index]` on a `@Vector` | copy to an array first, then index | gone | `vector index not comptime known` |
| `fn f() *const u8 { var x: u8 = 1; return &x; }` | return by value, or take an out-pointer | gone | `returning address of expired local variable 'x'` |
| `pub fn panic(msg, trace, ra) noreturn` | `pub const panic = std.debug.FullPanic(myPanicFn);` | alias | `std.debug.FullPanic(fn ([]const u8, ?usize) noreturn)` |
| `@intFromFloat(x)` for truncation | `@trunc`/`@floor`/`@ceil`/`@round` convert float -> int directly | alias | both compile; the rounding builtins say what you meant |
| `@floatFromInt(small)` | plain coercion when the int fits the significand exactly | alias | `const f: f64 = @as(u8, 200);` compiles |
| `@cImport({...})` | `b.addTranslateC(...)` in `build.zig`, imported as a module | alias | now backed by Aro, not libclang |

Constructs added in 0.14/0.16 that current code is expected to use:

| Feature | Rel | Shape |
|---|---|---|
| decl literals | 0.14 | `const config: Cfg = .default;` — drives `.empty`, `.init`, `.full`, `.limited(n)` |
| labeled switch + `continue :label` | 0.14 | threaded dispatch for tokenizers, VMs, state machines |
| `@FieldType(S, "name")` | 0.14 | replaces `@TypeOf(@field(undefined_s, "name"))` gymnastics |
| `@Int(.unsigned, bits)` / `@Tuple(&.{...})` | 0.16 | replaces `std.meta.Int` / `std.meta.Tuple` |
| `packed union(u16)` with explicit backing int; `==` on packed unions | 0.16 | |
| packed struct/union values as `switch` prong items | 0.16 | |

The `@Type` row is a lookup entry only. Which of the eight replacement builtins to reach for, their
signatures and arities, and why there is deliberately no `@Float`/`@Array`/`@Optional` are owned by
`references/comptime-and-generics.md` ZS-CT-18.

`usingnamespace` has no replacement construct — this row is the whole answer, and
`references/comptime-and-generics.md` ZS-CT-27 points here. Re-export one `pub const` per name.
There is no mixin, no wildcard, and no conditional-declaration trick; a declaration that used to be
conditionally mixed in becomes a `pub const x = if (cond) a else b;` or a separate file selected by
`@import`.

```zig
// does-not-compile — BAD: 0.14 — `expected function or variable declaration after pub`
pub usingnamespace @import("helpers.zig");
```

```zig
// fragment — GOOD: (compiles and runs under 0.16.0)
const helpers = @import("helpers.zig");
pub const encode = helpers.encode; // one pub const per re-exported name
pub const decode = helpers.decode;

const Cfg = struct {
    retries: u8,
    pub const default: Cfg = .{ .retries = 3 };
};
const config: Cfg = .default; // decl literal

fn unlikelyPath() void {
    @branchHint(.cold); // not @setCold(true)
}
```

---

## Part 3 — Writergate: streams, formatting, and the filesystem

### ZS-MIG-03 [M] Writergate: `std.io` is `std.Io`, and every stream carries its own buffer

There is no `std.io` in 0.16.0 (`root source file struct 'std' has no member named 'io'`).
`std.Io.Writer` and `std.Io.Reader` are single non-generic structs that own a `buffer:
[]u8`; there is no separate buffered wrapper and no generic/`Any` split.

**Why:** the buffer moved *into* the interface, so `GenericWriter`/`AnyWriter`/`BufferedWriter`/
`FixedBufferStream` all collapsed into one type. Code that still wraps a writer in a buffered writer
is not just stale, it double-buffers.

**Check:** grep the diff for `std.io.`, `GenericWriter`, `AnyWriter`, `GenericReader`, `AnyReader`,
`bufferedWriter`, `bufferedReader`, `fixedBufferStream`, `LinearFifo`, `std.RingBuffer`,
`std.fmt.format(`, `FormatOptions`, and `std.fmt.Formatter` — each is a row in the table below.
Then: an `ArrayList` passed where a writer is expected, and any `flush()` on a wrapper rather than
on the `*std.Io.Writer` itself.

| Old (0.13/0.14) | 0.16.0 | Status |
|---|---|---|
| `std.io` namespace | `std.Io` | gone |
| `std.io.Writer(...)`, `GenericWriter`, `AnyWriter` | `std.Io.Writer` (one struct) | gone |
| `std.io.Reader`, `GenericReader`, `AnyReader` | `std.Io.Reader` (one struct) | gone |
| `std.io.bufferedWriter(w)` / `BufferedWriter` | pass a buffer to the writer constructor | gone |
| `std.io.bufferedReader(r)` / `BufferedReader` | pass a buffer to the reader constructor | gone |
| `std.io.fixedBufferStream(&buf)` (write) | `std.Io.Writer.fixed(&buf)` | gone |
| `std.io.fixedBufferStream(bytes)` (read) | `std.Io.Reader.fixed(bytes)` | gone |
| `std.io.getStdOut().writer()` | `std.Io.File.Writer = .init(.stdout(), io, &buf)`, then `&fw.interface` | gone |
| `std.io.getStdErr()`, `getStdIn()` | `std.Io.File.stderr()`, `.stdin()` | gone |
| `std.io.null_writer` | `var d: std.Io.Writer.Discarding = .init(&scratch);` then `&d.writer` | gone |
| `std.io.CountingWriter` | `Io.Writer.Discarding` — field `count`, plus `fullCount()` which includes buffered bytes | gone |
| `std.io.CountingReader` | `Reader.discard(limit) !usize` returns the count; `Reader.seek` is a public field | gone |
| `std.fifo.LinearFifo`, `std.RingBuffer` | removed; use `std.Io.Reader`/`Writer` or `std.Deque(T)` | gone |
| `std.fmt.format(w, fmt, args)` | `w.print(fmt, args)` | gone |
| `std.fmt.FormatOptions` | `std.fmt.Options` | gone |
| `std.fmt.Formatter` | `std.fmt.Alt(Data, formatFn)` + `std.fmt.alt(ctx, .funcName)` | gone |
| ArrayList used as a writer | `std.Io.Writer.Allocating` (field `.writer`, `.written()`) | gone |
| `try bw.flush()` on the wrapper | `try w.flush()` on the `*std.Io.Writer` | — |
| `w.adaptToNewApi()` (0.15.1 shim) | never in new code | — |

```zig
// does-not-compile — BAD: 0.14-era; none of these symbols exist in 0.16.0
const stdout_file = std.io.getStdOut().writer();
var bw = std.io.bufferedWriter(stdout_file);
const stdout = bw.writer();
try stdout.print("{}\n", .{value});
try bw.flush();
```

```zig
// fragment — GOOD: this is the shape `zig init` emits
var stdout_buffer: [1024]u8 = undefined;
var stdout_file_writer: std.Io.File.Writer = .init(.stdout(), io, &stdout_buffer);
const stdout = &stdout_file_writer.interface;
try stdout.print("{f}\n", .{value});
try stdout.flush(); // a Writer with a buffer loses output if you skip this
```

```zig
// fragment — GOOD: in-memory writers
var buf: [64]u8 = undefined;
var w: std.Io.Writer = .fixed(&buf); // was std.io.fixedBufferStream
try w.print("{d}-{s}\n", .{ 42, "ok" });
assert(std.mem.eql(u8, w.buffered(), "42-ok\n"));

var aw: std.Io.Writer.Allocating = .init(gpa); // was "ArrayList as a writer"
defer aw.deinit();
try aw.writer.print("{x}", .{@as(u32, 255)});
assert(std.mem.eql(u8, aw.written(), "ff"));
```

---

### ZS-MIG-04 [M] The `format` method takes only a writer, and only `{f}` calls it

A custom `format` is `fn (value, w: *std.Io.Writer) std.Io.Writer.Error!void` — no format string, no
options. `{}` does **not** dispatch to it.

**Why:** this is the only migration row in the whole chapter that produces neither a compile error
nor an alias warning — `{}` silently falls back to the compiler's default aggregate dump. The
output for `w.print("[{}] [{f}]", .{ P{ .x = 1 }, P{ .x = 3 } })` is `[.{ .x = 1 }] [CUSTOM3]`.

**Check:** `grep -rn 'pub fn format(' src/` — every hit must read
`(value, w: *std.Io.Writer) std.Io.Writer.Error!void`; a four-parameter signature is the loud half
of this rule. The silent half: for each type that declares `format`, grep its name at call sites and
confirm the specifier is `{f}` and not `{}`. Also `{D}` anywhere, and `{}`/`{any}` on an enum where
`{t}` was meant.

| Old | 0.16.0 | Status |
|---|---|---|
| `pub fn format(self, comptime fmt, options, writer: anytype) !void` | `pub fn format(self: @This(), w: *std.Io.Writer) std.Io.Writer.Error!void` | wrong output |
| `{}` to invoke a custom `format` | `{f}` | wrong output |
| `{}`/`{any}` on an enum to get its name | `{t}` | wrong output |
| `{D}` duration specifier | `Io.Duration` has a `format` method; use `{f}` | gone |
| Unicode-width-aware alignment | alignment is ASCII/byte based only | wrong output |

```zig
// verified — GOOD
const std = @import("std");
const Point = struct {
    x: u32,
    pub fn format(p: Point, w: *std.Io.Writer) std.Io.Writer.Error!void {
        try w.print("Point({d})", .{p.x});
    }
};
// call site: w.print("{f}", .{point});  // "{}" would print `.{ .x = 1 }`
```

---

### ZS-MIG-05 [M] Filesystem: `std.fs` is a six-declaration shim; use `std.Io.Dir` / `std.Io.File`

There is no `std.fs.cwd()`, no `std.fs.Dir`, no `std.fs.File`: `root source file struct
'fs' has no member named 'cwd'`. Every remaining member of `std/fs.zig` carries `/// Deprecated`.

**Why:** filesystem access is now dispatched through the `Io` vtable, so a `Dir` handle alone cannot
perform an operation — it needs the `Io` that owns the syscall/green-thread strategy. That is why
`io` is the parameter immediately after the receiver on essentially every call.

**Check:** `grep -rn 'std\.fs\.' src/` — every hit is either a `gone` row (a hard error) or one of
the six deprecated aliases below, and both are findings. Then the structural check: every `Io.Dir`
or `Io.File` method call whose first argument after the receiver is not `io`, and any `makeDir`,
`makePath`, `makeOpenPath`, `realpath`, `getEndPos`, `setEndPos`, or `writeAll` on a directory or
file handle.

Exact deprecation rows in `std/fs.zig`:

| Deprecated | Replacement |
|---|---|
| `std.fs.path` | `std.Io.Dir.path` |
| `std.fs.max_path_bytes` | `std.Io.Dir.max_path_bytes` |
| `std.fs.max_name_bytes` | `std.Io.Dir.max_name_bytes` |
| `std.fs.base64_alphabet` | `std.base64.url_safe_alphabet_chars` |
| `std.fs.base64_encoder` | `std.base64.url_safe.Encoder` |
| `std.fs.base64_decoder` | `std.base64.url_safe.Decoder` |

Everything else moved outright:

| Old | 0.16.0 | Status |
|---|---|---|
| `std.fs.cwd()` | `std.Io.Dir.cwd()` | gone |
| `std.fs.Dir` / `std.fs.File` | `std.Io.Dir` / `std.Io.File` | gone |
| `std.fs.MAX_PATH_BYTES` | `std.Io.Dir.max_path_bytes` | gone |
| `dir.openFile(p, .{})` | `dir.openFile(io, p, .{})` | gone |
| `dir.createFile(p, .{})` | `dir.createFile(io, p, .{})` | gone |
| `dir.makeDir(p)` | `dir.createDir(io, p, permissions)` | gone |
| `dir.makePath(p)` | `dir.createDirPath(io, p)` | gone |
| `dir.makeOpenPath(p, o)` | `dir.createDirPathOpen(io, p, options)` | gone |
| `dir.readFileAlloc(gpa, p, max)` | `dir.readFileAlloc(io, p, gpa, limit)`, `limit: std.Io.Limit` | gone |
| `dir.writeFile(.{...})` | `dir.writeFile(io, .{ .sub_path = …, .data = … })` | gone |
| `file.close()` | `file.close(io)` | gone |
| `file.read` / `readv` | `file.readStreaming(io, bufs)` | gone |
| `file.pread` / `preadv` | `file.readPositional(io, bufs, offset)` | gone |
| `file.write` / `writev` | `file.writeStreaming(io, header, data, splat)` | gone |
| `file.writeAll(bytes)` | `file.writeStreamingAll(io, bytes)` | gone |
| `file.getEndPos()` / `setEndPos()` | `file.length(io)` / `file.setLength(io, n)` | gone |
| `dir.realpath(p, &buf)` | `dir.realPathFile(io, p, &out) !usize` — returns a **length**, not a slice | gone |
| `dir.realpathAlloc(gpa, p)` | `dir.realPathFileAlloc(io, p, gpa) ![:0]u8` | gone |
| `std.fs.realpath(abs, &buf)` | `std.Io.Dir.realPathFileAbsolute(io, abs, &out)` (+ `…AbsoluteAlloc`) | gone |
| `file.reader(&buf)` (0.15) | `file.reader(io, &buf)` | gone |
| `file.writer(&buf)` (0.15) | `file.writer(io, &buf)` | gone |
| `std.fs.File.Mode` | `std.Io.File.Permissions` | gone |
| `std.fs.File.OpenFlags` / `CreateFlags` | `Io.Dir.OpenFileOptions` / `CreateFileOptions` | alias on `Io.File` |
| `dir.chmod` / `dir.chown` | `dir.setPermissions(io, …)` / `dir.setOwner(io, …)` | gone |
| `dir.setAsCwd()` | `std.process.setCurrentDir(io, dir)` | gone |
| `*Z` / `*W` / `*W2` path variants | removed entirely | gone |
| `std.fs.openSelfExe` | `std.process.openExecutable(io, flags)` | gone |
| `std.fs.selfExePath[Alloc]` | `std.process.executablePath(io, buf)` | gone |
| `std.fs.selfExeDirPath[Alloc]` | `std.process.executableDirPath(io, buf)` | gone |
| `std.fs.getAppDataDir` | removed with no replacement | gone |
| `std.net` | `std.Io.net` | gone |
| `error.RenameAcrossMountPoints`, `error.NotSameFileSystem` | `error.CrossDevice` | gone |
| `error.SharingViolation` | `error.FileBusy` | gone |
| `error.EnvironmentVariableNotFound` | `error.EnvironmentVariableMissing` | gone |
| rename onto a non-empty dir -> `error.PathAlreadyExists` | now `error.DirNotEmpty` | wrong output |

```zig
// fragment — GOOD: end to end
var dir: std.Io.Dir = .cwd();
try dir.writeFile(io, .{ .sub_path = "demo.txt", .data = "line1\nline2\n" });
// Best-effort cleanup, so not `try`. Logged rather than discarded, because a silent
// `catch {}` is a dropped error (ZS-ERR-11). Absorbing the `error.Canceled` in
// `deleteFile`'s set is legal here only because this scope is unwinding (ZS-IO-27).
defer dir.deleteFile(io, "demo.txt") catch |err|
    std.log.warn("removing demo.txt: {t}", .{err});

const contents = try dir.readFileAlloc(io, "demo.txt", gpa, .limited(1 << 20));
defer gpa.free(contents);

var file = try dir.openFile(io, "demo.txt", .{});
defer file.close(io);
var read_buffer: [64]u8 = undefined;
var file_reader = file.reader(io, &read_buffer);
var lines: usize = 0;
while (try file_reader.interface.takeDelimiter('\n')) |_| lines += 1;
```

---

## Part 4 — Silent renames: search, containers, allocators

### ZS-MIG-06 [M] `std.mem.indexOf*` is now `find*` — these are silent aliases

Every `indexOf*`/`lastIndexOf*` name in `std.mem` still compiles as a deprecated alias. Nothing
warns. Emit the `find*` names.

**Why:** because the old names compile, this staleness never appears as a build failure — only as
code that reads a generation old. From the `/// Deprecated in favor of` markers in
`std/mem.zig`.

**Check:** `rg -n 'std\.mem\.(indexOf|lastIndexOf)'` — every hit compiles and every hit is stale.
Then the three that are not simple renames: `containsAtLeastScalar` (the `2` suffix **swaps two
arguments** — read each call site), `mem.tokenize(`/`mem.split(`/`mem.splitBackwards(` with no
`Scalar`/`Any`/`Sequence` suffix, and `mem.page_size`.

| Deprecated (still compiles) | Use instead |
|---|---|
| `mem.indexOf` | `mem.find` |
| `mem.indexOfPos` | `mem.findPos` |
| `mem.indexOfPosLinear` | `mem.findPosLinear` |
| `mem.lastIndexOf` | `mem.findLast` |
| `mem.lastIndexOfLinear` | `mem.findLastLinear` |
| `mem.indexOfScalar` | `mem.findScalar` |
| `mem.indexOfScalarPos` | `mem.findScalarPos` |
| `mem.lastIndexOfScalar` | `mem.findScalarLast` |
| `mem.indexOfAny` | `mem.findAny` |
| `mem.indexOfAnyPos` | `mem.findAnyPos` |
| `mem.lastIndexOfAny` | `mem.findLastAny` |
| `mem.indexOfNone` | `mem.findNone` |
| `mem.indexOfNonePos` | `mem.findNonePos` |
| `mem.lastIndexOfNone` | `mem.findLastNone` |
| `mem.indexOfDiff` | `mem.findDiff` |
| `mem.indexOfSentinel` | `mem.findSentinel` |
| `mem.indexOfMin` | `mem.findMin` |
| `mem.indexOfMax` | `mem.findMax` |
| `mem.indexOfMinMax` | `mem.findMinMax` |
| `mem.containsAtLeastScalar(T, list, minimum, element)` | `mem.containsAtLeastScalar2(T, list, element, minimum)` |
| `mem.readPackedIntNative/Foreign` | `mem.readPackedInt(T, bytes, bit_offset, .native/.foreign)` |
| `mem.writePackedIntNative/Foreign` | `mem.writePackedInt(T, bytes, bit_offset, value, .native/.foreign)` |

> [!WARNING]
> `containsAtLeastScalar` -> `containsAtLeastScalar2` **swaps the last two arguments**. Both take
> `(comptime T, list, X, Y)` and both compile, so a mechanical rename inverts the meaning. Check
> every call site by hand.

Related `std.mem` removals that are hard errors, plus the new `cut` family:

| Old | 0.16.0 | Status |
|---|---|---|
| `mem.tokenize` | `tokenizeScalar` / `tokenizeAny` / `tokenizeSequence` | gone |
| `mem.split`, `mem.splitBackwards` | `splitScalar`/`splitAny`/`splitSequence`, `splitBackwards*` | gone |
| `mem.page_size` | `std.heap.page_size_min` / `page_size_max` / `pageSize()` | gone |
| manual prefix/suffix slicing | `mem.cut`, `cutLast`, `cutScalar`, `cutScalarLast`, `cutPrefix`, `cutSuffix` | new |

```zig
// fragment — GOOD: inside a test body
try std.testing.expectEqual(2, std.mem.find(u8, "abcd", "cd"));
try std.testing.expectEqual(1, std.mem.findScalar(u8, "abc", 'b'));
const parts = std.mem.cut(u8, "key=value", "=") orelse
    return error.TestUnexpectedResult;
try std.testing.expectEqualStrings("key", parts[0]);
try std.testing.expectEqualStrings("value", parts[1]);
```

---

### ZS-MIG-07 [M] Containers: `ArrayList` is the unmanaged one; `gpa` is a per-call parameter

`std.ArrayList(T)` is `array_list.Aligned(T, null)` — no allocator field. Diagnostic:
`std.ArrayList(T).init(gpa)` is now
`error: struct 'array_list.Aligned(u8,null)' has no member named 'init'`.

Decl-literal construction is `references/types-and-data.md` ZS-TYPE-13; the
`std.BoundedArray`/`SegmentedList` replacements are ZS-TYPE-26; *why* the allocator is a per-call
parameter rather than a field is `references/memory-and-allocators.md` ZS-MEM-06. The table below is
the lookup surface for all three.

**Why:** not applicable — this section is a rename table, not a single rule. The rationale for the
unmanaged shape belongs to `references/memory-and-allocators.md` ZS-MEM-06, cited above.

**Check:** grep the diff for `ArrayListUnmanaged`, `array_list.Managed`, `BoundedArray`,
`SegmentedList`, `TailQueue`, `ComptimeStringMap`, and `std.ArrayHashMap`/`AutoArrayHashMap`/
`StringArrayHashMap`. Then the per-call-allocator shape: any `ArrayList(...)` followed by `.init(`,
and any `append`, `appendSlice`, `deinit`, `ensureTotalCapacity`, or `toOwnedSlice` whose first
argument is not an allocator.

| Old | 0.16.0 | Status |
|---|---|---|
| `std.ArrayList(T).init(gpa)` | `var list: std.ArrayList(T) = .empty;` | gone |
| `var l: ArrayListUnmanaged(T) = .{}` | `= .empty` | — |
| `list.append(x)` | `list.append(gpa, x)` | gone |
| `list.appendSlice(xs)` | `list.appendSlice(gpa, xs)` | gone |
| `list.deinit()` | `list.deinit(gpa)` | gone |
| `list.toOwnedSlice()` | `list.toOwnedSlice(gpa)` | gone |
| `list.pop()` | `list.pop() ?T` — still no `gpa`, non-allocating | — |
| `std.ArrayListUnmanaged(T)` | `std.ArrayList(T)` | alias |
| `std.ArrayListAligned`, `ArrayListAlignedUnmanaged` | `std.array_list.Aligned(T, alignment)` | alias |
| `std.array_list.Managed(T)` / `AlignedManaged` | the deprecated one — do not write new code with it | alias |
| `std.BoundedArray(T, n)` | `std.ArrayList(T) = .initBuffer(&stack_buf)` + `*AssumeCapacity` | gone |
| `std.ArrayHashMap` | `std.array_hash_map.Custom` | gone |
| `std.AutoArrayHashMap` | `std.array_hash_map.Auto` | gone |
| `std.StringArrayHashMap` | `std.array_hash_map.String` | gone |
| `std.ArrayHashMapUnmanaged` | `std.array_hash_map.Custom` | alias |
| `std.AutoArrayHashMapUnmanaged` | `std.array_hash_map.Auto` | alias |
| `std.StringArrayHashMapUnmanaged` | `std.array_hash_map.String` | alias |
| `std.SegmentedList` | removed | gone |
| `std.TailQueue` | `std.DoublyLinkedList` (intrusive `Node` + `@fieldParentPtr`) | gone |
| `std.ComptimeStringMap` | `std.StaticStringMap` | gone |
| `std.heap.MemoryPoolAligned` / `Extra` / `Options` | `std.heap.memory_pool.Aligned` / `.Extra` / `.Options` | alias |
| `PriorityQueue`/`PriorityDequeue` with an allocator field | field removed; pass `gpa` per call | gone |
| — | `std.Deque(T)` with `.empty`, `initCapacity`, `initBuffer` | new |

> [!WARNING]
> The **non-array** hash maps did not follow. `std.StringHashMap`, `std.AutoHashMap` and
> `std.HashMap` still exist in 0.16.0, are still managed (they hold an allocator field), and are
> **not** marked deprecated — `_ = std.StringHashMap;` compiles. Only the
> `ArrayHashMap` family was purged. Prefer the `Unmanaged` variants for consistency with
> `ArrayList`, but do not "fix" `std.StringHashMap` into a nonexistent
> `std.hash_map.String`.

```zig
// does-not-compile — BAD: 0.13/0.14 spelling; `init` does not exist on ArrayList
var list = std.ArrayList(u32).init(gpa);
defer list.deinit();
try list.append(1);
```

```zig
// fragment — GOOD
var list: std.ArrayList(u32) = .empty;
defer list.deinit(gpa);
try list.append(gpa, 1);

var map: std.array_hash_map.String(u32) = .empty;
defer map.deinit(gpa);
try map.put(gpa, "k", 7);
```

---

### ZS-MIG-08 [M] Allocators: `DebugAllocator` replaced `GeneralPurposeAllocator`

`std.heap.GeneralPurposeAllocator` no longer exists (`root source file struct 'heap' has no member
named 'GeneralPurposeAllocator'`). Initialize with the decl literal `.init`.

**Why:** the rename reflects what it is (a debugging allocator with leak and double-free detection),
and `remap` was added so allocators can move an allocation cheaply instead of forcing every caller
to alloc/copy/free — implementations that only provide `resize` leave that on the table.

**Check:** grep for `GeneralPurposeAllocator`, `ThreadSafeAllocator`, and `std.mem.page_size`. For a
project that implements its own allocator, the structural check is the vtable literal: three members
instead of four, or an `alloc`/`resize`/`free` taking a `u8` log2 alignment instead of
`std.mem.Alignment`, means it predates 0.16 and will not compile.

| Old | 0.16.0 | Status |
|---|---|---|
| `std.heap.GeneralPurposeAllocator(.{})` | `std.heap.DebugAllocator(.{})` | gone |
| `var gpa = GPA(.{}){};` | `var da: std.heap.DebugAllocator(.{}) = .init;` | gone |
| `gpa.deinit()` returning `bool` | returns `std.heap.Check` (`.ok` / `.leak`) | wrong output |
| `std.heap.ThreadSafeAllocator` | removed — for a general thread-safe allocator use `DebugAllocator(.{ .thread_safe = true })` or `std.heap.smp_allocator` | gone |
| `heap.ArenaAllocator` default-init `.{}` | `.init(child_allocator)` | alias |
| — | `std.heap.smp_allocator` (`SmpAllocator`) for multithreaded ReleaseFast/ReleaseSmall | new |
| vtable `alloc/resize/free` with `u8` log2 align | all take `alignment: std.mem.Alignment` | gone |
| vtable had no `remap` | `remap` is now a **required** vtable member | gone |
| `std.mem.page_size` | `std.heap.page_size_min` / `page_size_max` / `pageSize()` | gone |

The migration consequence, in one line: **an allocator written before 0.16 will not compile**,
because `remap` is a required vtable member and every slot takes `alignment: std.mem.Alignment`
instead of a `u8` log2 alignment. The vtable's exact declaration and the four members' contracts —
including why returning `null` from `remap` is a correct answer rather than a failure — are owned by
`references/memory-and-allocators.md` ZS-MEM-24. Unimplementable slots take `Allocator.noAlloc` /
`noResize` / `noRemap` / `noFree`.

```zig
// fragment — GOOD: only when you cannot take `init.gpa`; see ZS-MIG-09
var da: std.heap.DebugAllocator(.{}) = .init;
defer assert(da.deinit() == .ok);
const gpa = da.allocator();
```

---

## Part 5 — Entry point, concurrency, and testing

### ZS-MIG-09 [M] Entry point: `pub fn main(init: std.process.Init) !void`

Take `std.process.Init` (or `Init.Minimal`) as the first parameter of `main`. Do not hand-roll an
allocator, argv, environ, or an `Io` in `main`.

**Why:** argv and environ are no longer process globals — `std.process.argsAlloc` and
`std.process.getEnvMap` do not exist: `root source file struct 'process' has no member
named 'argsAlloc'`. The only supported way to reach them is through the parameter the runtime hands
you. `Init` also hands you a leak-checked `gpa` and a target-appropriate `Io`, which is the whole
GPA-setup boilerplate deleted.

**Check:** `grep -rn 'pub fn main()' src/` returns nothing, and neither does a grep for
`argsAlloc`, `argsFree`, `getEnvMap`, `std.ChildProcess`, `process.Child.init(`, or
`process.Child.run(`. A `DebugAllocator` constructed in `main` when `init.gpa` is in scope is the
milder form of the same finding.

Exact shape (`std/process.zig`):

```zig
// fragment — from std/process.zig
pub const Init = struct {
    minimal: Minimal,                 // Init is a superset of Minimal
    arena: *std.heap.ArenaAllocator,  // whole-process storage, freed on exit, threadsafe
    gpa: Allocator,                   // temporary allocations; leak-checked in Debug
    io: Io,                           // default Io for the target; leak-checked in Debug
    environ_map: *Environ.Map,        // NOT threadsafe
    preopens: Preopens,               // mainly WASI

    pub const Minimal = struct { environ: Environ, args: Args };
};
```

| Old | 0.16.0 | Status |
|---|---|---|
| `pub fn main() !void` + manual GPA | `pub fn main(init: std.process.Init) !void` | compiles, but obsolete |
| `std.process.argsAlloc(gpa)` / `argsFree` | `try init.minimal.args.toSlice(arena)` -> `[]const [:0]const u8` | gone |
| any std argument *parser* | there has never been one; hand-roll it (`references/build-and-project.md` ZS-BUILD-42) | — |
| `std.process.getEnvMap(gpa)` | `init.environ_map` | gone |
| `var gpa_state = GPA(.{}){}; const gpa = …` | `const gpa = init.gpa;` | — |
| `std.io.getStdOut()` | `std.Io.File.stdout()` + `init.io` | gone |
| `std.process.Child.init(argv, gpa)` + `spawn()` | `std.process.spawn(io, .{ .argv = …, .stdout = .pipe })` | gone |
| `std.process.Child.run(...)` | `std.process.run(gpa, io, options)` | gone |
| `std.process.execv` | `std.process.replace` / `replacePath` | gone |
| `std.ChildProcess` | `std.process.Child` | gone |

```zig
// verified — GOOD
const std = @import("std");
pub fn main(init: std.process.Init) !void {
    const io = init.io;
    const gpa = init.gpa;
    const arena = init.arena.allocator();
    const args = try init.minimal.args.toSlice(arena);

    var stdout_buffer: [1024]u8 = undefined;
    var stdout_file_writer: std.Io.File.Writer = .init(.stdout(), io, &stdout_buffer);
    const out = &stdout_file_writer.interface;
    try out.print("argc={d}\n", .{args.len});
    try out.flush();
    _ = gpa;
}
```

---

### ZS-MIG-10 [M] Concurrency, sync, time, and randomness all moved onto `std.Io`

`std/Thread.zig` contains **zero** occurrences of `Mutex`, `Condition`, `Semaphore`, `RwLock`,
`ResetEvent`, `WaitGroup`, `Pool`, or `Futex`. `std/time.zig` is unit constants plus
`std.time.epoch`.

**Why:** this is a correctness requirement, not a style preference. An OS-level mutex blocks the
whole carrier thread and deadlocks green-thread backends (`Io.Evented`, fiber). The release notes
state outright that converting every `Thread.Mutex`/`Condition`/`ResetEvent` is *required* when
moving to `std.Io`.

**Check:** grep for `std.Thread.` followed by `Mutex`, `Condition`, `Semaphore`, `RwLock`,
`ResetEvent`, `WaitGroup`, `Pool`, or `Futex`; for `std.time.` followed by `Timer`, `Instant`,
`timestamp`, `milliTimestamp`, `nanoTimestamp`, or `sleep`; and for `std.event.Loop`, `std.once`,
and `std.crypto.random`. Then the two plausible names that do not exist: `Duration.fromMs` and
`Clock.monotonic`. Also `setName(` with two arguments — it gained an `Io`.

| Old | 0.16.0 | Status |
|---|---|---|
| `std.Thread.Mutex` | `std.Io.Mutex` | gone |
| `std.Thread.Condition` | `std.Io.Condition` | gone |
| `std.Thread.ResetEvent` | `std.Io.Event` | gone |
| `std.Thread.Semaphore` | `std.Io.Semaphore` | gone |
| `std.Thread.RwLock` | `std.Io.RwLock` | gone |
| `std.Thread.Futex` | `io.futexWait` / `io.futexWake` (free functions; **no** `Io.Futex` type) | gone |
| `std.Thread.WaitGroup` | `std.Io.Group` | gone |
| `std.Thread.Pool` | removed — `io.async` / `Io.Group`; `Io.Threaded`'s `async_limit: Io.Limit` **is** the pool size | gone |
| `std.Thread.Mutex.Recursive` | removed | gone |
| `std.event.Loop` | `Io.Threaded` (OS threads) or `Io.Evented` (green threads) | gone |
| `std.once` | removed | gone |
| `std.time.Timer` / `Instant` | `std.Io.Timestamp` | gone |
| `std.time.timestamp()` / `milliTimestamp()` | `std.Io.Timestamp.now(...)` | gone |
| `std.time.sleep(ns)` | `io.sleep(duration, clock)` | gone |
| ad-hoc `u64` nanoseconds | `Io.Duration` — `.fromNanoseconds/.fromMicroseconds/.fromMilliseconds/.fromSeconds` | — |
| `.monotonic` clock | `Io.Clock` is `{ real, awake, boot, cpu_process, cpu_thread }`; monotonic is `.awake` | gone |
| `std.crypto.random.bytes(&buf)`, `posix.getrandom` | `io.random(&buf)`; `io.randomSecure(&buf)` for entropy-guaranteed | gone |
| `std.Options.crypto_always_getrandom` / `crypto_fork_safety` | removed — use `io.randomSecure` | gone |

Spelling traps, each a compile error: there is no `Duration.fromMs` (it is `fromMilliseconds`)
and no `Clock.monotonic` (it is `.awake`).

What survived on `std.Thread` (`std/Thread.zig`): `spawn`, `join`, `detach`,
`getHandle`, `getCurrentId`, `getCpuCount`, `yield`, `getName`, and `std.atomic.Value(T)` with the
atomic builtins. One trap in that list — **`setName` gained an `Io`**: it is
`setName(self: Thread, io: Io, name: []const u8)`, not the 0.14 two-argument form.

```zig
// fragment — GOOD
var group: std.Io.Group = .init;
errdefer group.cancel(io);
for (0..4) |_| group.async(io, bump, .{io}); // `async` is an ordinary method name now
try group.await(io);

fn bump(io: std.Io) void {
    // Cancellation is signalled exactly once, at the next cancellation point.
    // Swallowing it with `catch {}` would leave `group.await` blocked forever
    // (ZS-IO-27) — handle it explicitly, even when the handling is "stop".
    io.sleep(.fromMilliseconds(1), .awake) catch |err| switch (err) {
        error.Canceled => return,
    };
}
```

---

### ZS-MIG-11 [M] Testing: `std.testing.io`, `Smith` fuzz inputs, `tmpDir(Io.Dir.OpenOptions)`

The three test-surface changes that break 0.14 test code. How to *use* them is owned by the testing
chapter: `std.testing.io` and test-time I/O are `references/testing-and-fuzzing.md` ZS-TEST-09;
writing `Smith`-shaped fuzz targets is ZS-TEST-20; the `Smith` types you may and may not ask for is
ZS-TEST-22. This table is the rename lookup.

**Why:** not applicable — this section is a rename table, not a single rule. The reasoning behind
`Smith` and test-time `Io` is owned by `references/testing-and-fuzzing.md` ZS-TEST-09 and
ZS-TEST-20, cited above.

**Check:** in test code, grep for a fuzz target whose parameter is `[]const u8` rather than
`*std.testing.Smith`; for a `tmpDir` handle's `.dir` methods called with no `std.testing.io`
argument; and for `std.fs.cwd()` inside a `test` block. `expectEqual(@as(` is the cosmetic third:
redundant wherever peer resolution already fixes the type, but **not** stale — 0.16 std still writes
it 732 times, and it stays necessary where the two arguments do not peer-resolve (ZS-TEST-06). Note
it only; never make it a blocking finding.

| Old | 0.16.0 | Status |
|---|---|---|
| `fn testOne(input: []const u8) anyerror!void` | `fn testOne(context: anytype, smith: *std.testing.Smith) anyerror!void` | gone |
| `std.testing.fuzz(ctx, testOne, .{})` with a byte-slice target | same call, `Smith`-shaped target | gone |
| `std.testing.tmpDir(.{})` on `std.fs.Dir` options | `std.testing.tmpDir(opts: std.Io.Dir.OpenOptions)`; `tmp.dir` is an `Io.Dir` | gone |
| tests calling `std.fs.cwd()` | `std.Io.Dir.cwd()` with `std.testing.io` | gone |
| `expectEqual(@as(u32, 3), x)` | `expectEqual(3, x)` — both params are `anytype`, peer-resolved | — |
| `std.testing.FailingAllocator` / `checkAllAllocationFailures` | unchanged, still the right tool | — |

`Smith`'s public surface (`std/testing/Smith.zig`): `value(T)`, `valueWeighted`,
`valueRangeAtMost(T, lo, hi)`, `valueRangeLessThan`, `index(len)`, `boolWeighted`, `eos()`,
`bytes(out)`, `slice(buf)`, plus `*WithHash` variants.

```zig
// fragment — GOOD: the two mechanical edits
// was: fn testOne(input: []const u8) anyerror!void
fn testOne(context: void, smith: *std.testing.Smith) !void {
    _ = context;
    _ = smith;
}

// was: var tmp = std.testing.tmpDir(.{}); try tmp.dir.writeFile(.{ .sub_path = ... });
var tmp = std.testing.tmpDir(.{}); // options are now Io.Dir.OpenOptions
defer tmp.cleanup();
try tmp.dir.writeFile(std.testing.io, .{ .sub_path = "a.txt", .data = "hello" });
```

Note that `zig build test --fuzz` and `zig test -ffuzz` do not build on 0.16.0 —
`references/build-and-project.md` ZS-BUILD-35. The corpus still runs under plain `zig test`.

---

## Part 6 — Build system and miscellaneous renames

### ZS-MIG-12 [M] Build: artifacts take `.root_module`; `.name` is an enum literal in `.zon`

From `std/Build.zig`: `ExecutableOptions` is exactly
`{ name, root_module, version, linkage, max_rss, use_llvm, use_lld, zig_lib_dir, win32_manifest }` —
`root_source_file`, `target`, and `optimize` are not among them. (`use_new_linker` is a field on the
returned `Step.Compile`, assigned after creation, not an option.)

The build chapter owns the reasoning and the shapes to write instead: module-vs-artifact settings
are `references/build-and-project.md` ZS-BUILD-02, `addLibrary(.{ .linkage })` is ZS-BUILD-07, the
`build.zig.zon` manifest fields are ZS-BUILD-10, and `.paths` is ZS-BUILD-12. Below is the rename
lookup only.

**Why:** not applicable — this section is a rename table, not a single rule. The reasoning for the
module-versus-artifact split is owned by `references/build-and-project.md` ZS-BUILD-02, cited above.

**Check:** in `build.zig`, every `root_source_file` must sit inside a `createModule`/`addModule`
literal, never inside an `addExecutable`/`addLibrary`/`addTest` one; then grep for
`addStaticLibrary`, `addSharedLibrary`, `addWriteFiles`, `addRemoveDirTree("`, `.addModule(` called
on an artifact, and `getPath(`/`getPath2(`/`getPath3(` on a `LazyPath`. In `build.zig.zon`: a quoted
`.name`, a missing `.fingerprint`, or a `.hash` beginning `1220`.

| Old | 0.16.0 | Status |
|---|---|---|
| `b.addExecutable(.{ .name, .root_source_file, .target, .optimize })` | `.{ .name = …, .root_module = b.createModule(.{ .root_source_file, .target, .optimize, .imports }) }` | gone |
| `b.addSharedLibrary` / `b.addStaticLibrary` | `b.addLibrary(.{ .linkage = …, .name = …, .root_module = mod })` | gone |
| `b.addTest(.{ .root_source_file = … })` | `b.addTest(.{ .root_module = mod })` — one module per test binary | gone |
| `exe.addModule("x", m)` | `mod.addImport("x", m)` or `.imports = &.{ .{ .name = "x", .module = m } }` | gone |
| `b.addWriteFiles()` to update sources | `b.addUpdateSourceFiles()` | gone |
| `b.addRemoveDirTree("path")` | `b.addRemoveDirTree(.{ .cwd_relative = path })` (LazyPath) | gone |
| `@cImport` in source | `b.addTranslateC(.{ .root_source_file, .target, .optimize })` -> `.createModule()` | alias |
| `LazyPath.getPath` / `getPath2` / `getPath3` | `getPath4` (returns `Io.Cancelable!Cache.Path`) | alias |
| `GeneratedFile.getPath` / `getPath2` | `getPath3` (returns `Io.Cancelable![]const u8`) | alias |
| `-Dno-bin` skip-the-binary idiom | a `check` step whose artifacts are never installed or run (`references/build-and-project.md` ZS-BUILD-32) | — |

`build.zig.zon` changed independently. **`.name` is an enum literal there, and a plain string in
`build.zig`** — mixing these up is a common error:

| Old | 0.16.0 |
|---|---|
| `.name = "myproject"` (string) | `.name = .myproject` (enum literal) |
| — | `.fingerprint = 0x…` — generated once, **never** hand-edited (identity + trust implications) |
| — | `.minimum_zig_version = "0.16.0"` — documentation only; the compiler never reads it |
| `.hash = "1220115ff0…"` (old multihash) | `name-version-fingerprint-size` form, e.g. `mime-3.0.0-zwmL-6wgAAD…` |
| hand-written dependency entries | `zig fetch --save <url>`; `zig build --fetch` fetches recursively |

```zig
// fragment — GOOD: the one edit that fixes most 0.13-era build scripts
const exe = b.addExecutable(.{
    .name = "initproj", // still a []const u8 here; enum literal only in the .zon
    .root_module = b.createModule(.{ // was: .root_source_file/.target/.optimize here
        .root_source_file = b.path("src/main.zig"),
        .target = target,
        .optimize = optimize,
        .imports = &.{.{ .name = "initproj", .module = mod }},
    }),
});
```

The full canonical `build.zig` — every step a project should expose, and how the test binaries are
wired — is `references/build-and-project.md` ZS-BUILD-01. Do not reconstruct it from this table.

---

### ZS-MIG-13 [M] Miscellaneous std renames

Low-frequency but each one dates a diff. Deviating is only defensible while mid-migration.

**Why:** the tier is `[M]` for the same reason ZS-MIG-06 is, not because these renames matter more
than their frequency suggests: the `alias` rows **compile silently**, so nothing but this rule
catches them, and six of them — `bufPrintZ`, `initEmpty()`, `initFull()`, `std.meta.Int`,
`std.meta.Tuple`, `pipeToFileSystem` — already fail the build under ZS-MIG-14's `[M!]` denylist. A
rule cannot own a spelling at `[S]` while another rule fails CI on it. `std.math.sign` is the
sharpest row and is not an alias at all: its return type changed, so old call sites keep compiling
and produce a different value. Beyond the shared mechanism each row is its own small story, and the
row's right-hand column is the whole answer.

**Check:** grep the diff for `bufPrintZ`, `std.meta.Int`, `std.meta.Tuple`, `std.meta.declList`,
`initEmpty()`, `initFull()`, `pipeToFileSystem`, `PipeOptions`, `std.rand.`, `CrossTarget`,
`captureStackTrace`, `dumpStackTraceFromBase`, `walkStackWindows`, `StackIterator`, `utf8Decode`,
`wtf8Decode`, and `std.debug.runtime_safety` — each is a row above. `std.math.sign` deserves a
second look rather than a grep: its return type changed, so every call site that stores or compares
its result needs re-reading.

| Old | 0.16.0 | Status |
|---|---|---|
| `std.fmt.bufPrintZ(buf, fmt, args)` | `std.fmt.bufPrintSentinel(buf, fmt, args, 0)` | alias |
| `std.meta.Int(sign, bits)` | `@Int(sign, bits)` | alias |
| `std.meta.Tuple(&.{...})` | `@Tuple(&.{...})` | alias ("to be removed after 0.16.0") |
| `std.meta.declList` | removed | gone |
| `std.tar.PipeOptions` | `std.tar.ExtractOptions` | alias |
| `std.tar.pipeToFileSystem` | `std.tar.extract(io, dir, reader, options)` — now sanitizes path traversal | alias |
| `EnumSet.initEmpty()` / `initFull()` | decl literals `.empty` / `.full` | alias |
| `BitSet.initEmpty()` / `initFull()` | `.empty` / `.full` | alias |
| `std.debug.runtime_safety` | read your own module's mode; std's is not yours | alias |
| `std.debug.captureStackTrace` | `std.debug.captureCurrentStackTrace(options, addr_buf)` | gone |
| `std.debug.dumpStackTraceFromBase` | `std.debug.dumpCurrentStackTrace(options)` | gone |
| `std.debug.walkStackWindows` / `writeStackTraceWindows` | `captureCurrentStackTrace` / `writeCurrentStackTrace` | gone |
| `std.debug.StackIterator` | now internal | gone |
| `std.unicode.utf8Decode` / `wtf8Decode` | deprecated: "awkward API that is too easy to use incorrectly" | alias |
| `std.rand` | `std.Random` | gone |
| `std.zig.CrossTarget` | `std.Target.Query` | gone |
| `std.Target.SubSystem` | `std.zig.Subsystem`; `builtin.subsystem` removed | gone |
| `std.DynLib` on Windows | removed — call `LoadLibraryExW`/`GetProcAddress` directly | gone |
| medium-level `std.posix` / `std.os.windows` wrappers | removed — go up to `std.Io` or down to `std.posix.system` | gone |
| `std.math.sign` | now returns the smallest int type that fits the possible values | wrong output |
| `std.compress.flate` | removed in 0.15.1, re-added in 0.16.0 as a from-scratch deflate | — |

```zig
// fragment — GOOD: inside a test body; `Color` is an enum
var zbuf: [16]u8 = undefined;
const z = try std.fmt.bufPrintSentinel(&zbuf, "{d}", .{7}, 0); // was bufPrintZ

var set: std.EnumSet(Color) = .empty; // was .initEmpty()
const all: std.EnumSet(Color) = .full; // was .initFull()

var bytes: [4]u8 = @splat(0);
std.mem.writePackedInt(u12, &bytes, 3, 0xabc, .native); // was writePackedIntNative
const v = std.mem.readPackedInt(u12, &bytes, 3, .native);
```

---

## Part 7 — Enforcing it

### ZS-MIG-14 [M!] Fail the build on deprecated-but-compiling spellings

Add a CI step that greps the source for the **alias** rows above and fails on a hit, pin the
toolchain for real — `.minimum_zig_version` is documentation only, so use a pinned CI version plus
the `comptime builtin.zig_version` guard (`references/build-and-project.md` ZS-BUILD-34,
ZS-BUILD-40) — and treat a toolchain bump as a migration task with its own review.

**`[M!]` trigger:** high-reliability code — databases, consensus, crypto, allocators, parsers on
untrusted input, embedded firmware — anything where corruption is unacceptable and upgrade windows
are long. ***Relaxed form:*** elsewhere, no CI gate is required, but the same grep runs by hand
before each release and any alias in a file you are already editing gets fixed in that diff. The
weaker rule is still a rule: "I did not notice" stops being an acceptable answer once the denylist
exists in the repository.

**Why:** alias rows never surface as build failures, so on a long-lived codebase they accumulate
until an upgrade deletes them all at once and the diff is too large to review carefully. A grep gate
converts a future big-bang migration into a per-PR cost. High-reliability codebases care more
because their upgrade windows are longest and their review budgets are spent on correctness, not
renames.

**Check:** the CI workflow contains a step that runs the denylist below and fails on a hit — a `rg`
whose exit status is checked, not a `|| true`. Run it once by hand when adding it: a non-empty
result means the gate is being added to a tree that already fails it, and those hits are the first
commit, not the second.

```sh
# GOOD — every `alias` row in this chapter that is safely greppable. Each hit
# compiles today and is stale; at 0.16.0 every spelling below
# still resolves, so none of these patterns is dead weight.
# EVERY pattern must use `-e`. With one bare positional and one `-e`, rg reads the
# bare pattern as a PATH: it exits 2 on every run and silently drops that half of
# the denylist. Exit status is the gate — 0 means a hit, 1 means clean.
rg -n --type zig \
  -e 'std\.mem\.(indexOf|lastIndexOf)|ArrayListUnmanaged|ArrayListAligned|array_list\.Managed' \
  -e '(ArrayHashMap|AutoArrayHashMap|StringArrayHashMap)Unmanaged|std\.fs\.(path|max_)' \
  -e 'bufPrintZ|initEmpty\(\)|initFull\(\)|std\.meta\.(Int|Tuple)' \
  -e 'MemoryPool(Aligned|Extra|Options)|pipeToFileSystem|tar\.PipeOptions' \
  -e 'debug\.runtime_safety|(utf8|wtf8)Decode\(|\.getPath[23]?\(|File\.(Open|Create)Flags' \
  src/
```

Four `alias` rows are **deliberately** not on the list, and the exclusion is part of the rule — a
denylist nobody trusts gets deleted. `@intFromFloat` and `@floatFromInt` are legal, unremarkable
builtins that this standard merely prefers to spell more informatively (ZS-TYPE-11), so gating them
would fail builds over a preference. `@cImport` is ZS-BUILD-36's `[S]` recommendation, not a
mandate. `heap.ArenaAllocator` default-init `.{}` has no spelling a regex can distinguish from any
other `.{}`. Everything else in the chapter's alias column is above: adding a row to that table
without adding it here leaves a gate that claims more coverage than it has.

---

### SMELL TEST

Any one of these in a diff means the author was working from a pre-0.16 mental model. Re-check the
whole file, not just the flagged line.

1. `std.io.` anywhere — lowercase `io` does not exist under `std`.
2. `std.fs.cwd()`, `std.fs.File`, `std.fs.Dir` — the filesystem is `std.Io.Dir` / `std.Io.File`.
3. A filesystem or socket call whose first argument after the receiver is **not** `io`.
4. `bufferedWriter` / `bufferedReader` / `fixedBufferStream` / `GenericWriter` / `AnyWriter`.
5. `pub fn format(self, comptime fmt, options, writer: anytype)` — the 4-argument signature is dead;
   and any `{}` where a custom `format` was intended (should be `{f}`).
6. `std.ArrayList(T).init(gpa)`, `list.append(x)` without `gpa`, or `list.deinit()` with no
   argument.
7. `std.heap.GeneralPurposeAllocator`, `std.BoundedArray`, `std.ArrayHashMap`, `std.SegmentedList`.
8. `pub fn main() !void` paired with manual GPA setup, `std.process.argsAlloc`, or `getEnvMap`.
9. `std.Thread.Mutex` / `Condition` / `Pool` / `WaitGroup`, or `std.time.Timer` / `std.time.sleep`.
10. `std.mem.indexOf*` / `lastIndexOf*` — compiles, but a generation old (see ZS-MIG-06).
11. `usingnamespace`, `@Type(...)`, `@setCold`, `@fence`, `callconv(.C)`, `@typeInfo(T).Int`.
12. `b.addExecutable(.{ .root_source_file = ... })` without `.root_module`, or a `build.zig.zon`
    with `.name = "string"` or no `.fingerprint`.
13. A fuzz target taking `[]const u8` instead of `*std.testing.Smith`.
14. `Duration.fromMs`, `Clock.monotonic`, or `Io.Futex` — plausible-looking names that do not exist.
