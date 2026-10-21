# What changed: dead APIs and the 0.13 -> 0.17 migration tables

Lookup tables for every spelling that changed between Zig 0.13/0.14 and **0.17.0**. Use this chapter
to answer "does this symbol still exist, and what is it called now?" — it is a dictionary, not a
tutorial. Rationale for the *new* designs (how to structure `std.Io` code, how to pick an allocator,
how to lay out `build.zig`) lives in the std.Io, memory, and build chapters; the language-design
reasoning lives in the types and control-flow chapters. Every row below was checked against the
0.17.0 standard-library source tree — locate yours with `zig env | grep std_dir` — or by compiling a
probe with `zig 0.17.0`; rows that are only claimed by release notes are marked. Parts 2 to 6 are
the 0.13/0.14 -> 0.16 changes, with each right-hand column brought to its 0.17 spelling and each
status to what 0.17 does with the old spelling; Part 7 is what 0.17 itself changed.

This chapter is the **single home for dead-API tables**. Other chapters teach the new designs and
cite these tables rather than reprinting them — in particular `references/concurrency.md`
ZS-CONC-39 points at ZS-MIG-03 (streams), ZS-MIG-05 (filesystem), and ZS-MIG-10 (concurrency, time,
randomness).

Every example assumes a file opening with `const std = @import("std");` and
`const assert = std.debug.assert;` — assertions are called bare, per ZS-ASSERT-01. Snippets that use
`io` or `gpa` assume they came from `std.process.Init` (ZS-MIG-09) or `std.testing`.

The tables use three status values:

| Status | Meaning |
|---|---|
| **gone** | The old spelling is a compile error. Loud failure. |
| **alias** | The old spelling still compiles as a deprecated alias. **Silent** staleness. |
| **wrong output** | Compiles, runs, produces different results than you intended. Worst case. |

## Contents

- **Part 1 — Verify against the local std, never from memory**
  - ZS-MIG-01 [M] Write 0.17.0 spellings; verify unfamiliar std symbols against local std
- **Part 2 — Language: removed syntax and builtins**
  - ZS-MIG-02 [M] Language: removed syntax and builtins
- **Part 3 — Writergate: streams, formatting, and the filesystem**
  - ZS-MIG-03 [M] Writergate: `std.io` is `std.Io`, and every stream carries its own buffer
  - ZS-MIG-04 [M] The `format` method takes only a writer, and only `{f}` calls it
  - ZS-MIG-05 [M] Filesystem: `std.fs` is a six-declaration shim; use `std.Io.Dir` / `std.Io.File`
- **Part 4 — Silent renames: search, containers, allocators**
  - ZS-MIG-06 [M] `std.mem.indexOf*` is now `find*` — these are silent aliases
  - ZS-MIG-07 [M] Containers: `ArrayList` is the unmanaged one; `gpa` is a per-call parameter
  - ZS-MIG-08 [M] Allocators: `SafeAllocator` replaced `GeneralPurposeAllocator`
- **Part 5 — Entry point, concurrency, and testing**
  - ZS-MIG-09 [M] Entry point: `pub fn main(init: std.process.Init) !void`
  - ZS-MIG-10 [M] Concurrency, sync, time, and randomness all moved onto `std.Io`
  - ZS-MIG-11 [M] Testing: `std.testing.io`, `Smith` fuzz inputs, `tmpDir(Io.Dir.OpenOptions)`
- **Part 6 — Build system and miscellaneous renames**
  - ZS-MIG-12 [M] Build: artifacts take `.root_module`; `.name` is an enum literal in `.zon`
  - ZS-MIG-13 [M] Miscellaneous std renames
- **Part 7 — Zig 0.16 → 0.17**
- **Part 8 — Enforcing it**
  - ZS-MIG-14 [M!] Fail the build on deprecated-but-compiling spellings
  - SMELL TEST
- Decided by tools

---

## Part 1 — Verify against the local std, never from memory

### ZS-MIG-01 [M] Write 0.17.0 spellings; verify unfamiliar std symbols against local std

Never emit a `std.*` symbol from memory of an older Zig. Grep the installed std source before you
type a signature. The 0.13/0.14 era is the single largest source of wrong Zig.

**Why:** roughly a third of the migrations below are **alias** or **wrong output** rows, not
**gone** rows. `zig build` passing proves nothing about whether the code is current —
`std.mem.indexOf`, `std.ArrayListUnmanaged`, `std.array_list.Managed`, `std.fs.path`,
`std.builtin`, `std.fmt.allocPrint` and `std.heap.DebugAllocator` all compile clean in 0.17.0 and
all are marked `/// Deprecated` in the source.

**Check:** run the denylist grep of ZS-MIG-14 over the diff — it collects the alias rows from every
table below. Separately, every `std.*` signature new to the diff must be findable by `rg -n` in
the local std tree; one that is not is misremembered, not merely misspelled.

```sh
# GOOD — the only reliable check. Run it, don't recall it.
grep -rn "pub fn takeDelimiter" "$(zig env | grep std_dir)"/Io/Reader.zig
```

---

## Part 2 — Language: removed syntax and builtins

### ZS-MIG-02 [M] Language: removed syntax and builtins

All rows below were confirmed by compiling a probe with `zig build-obj` on 0.16.0, and again on
0.17.0, whose diagnostics name `lang.` where 0.16 printed `builtin.`; the column quotes 0.17.

**Why:** not applicable — this section is a lookup table, not a single rule. The rationale for each
replacement is owned by the chapter that teaches it: the `@Type` split is
`references/comptime.md` ZS-COMPTIME-18, `usingnamespace` is ZS-COMPTIME-27, colorless concurrency
is `references/concurrency.md`, and `@branchHint` is `references/errors.md`
ZS-ERR-31.

**Check:** grep the diff for `usingnamespace`, `@Type(`, `@setCold`, `@fence(`, `@setAlignStack`,
`callconv(.C)`/`.Stdcall`/`.Naked`, `@typeInfo(` followed by a `TitleCase` field, `anyframe`,
`@frameSize`, `suspend`/`resume`, `@cImport(`, and `@export(` whose first argument has no leading
`&`. Every hit is a hard compile error on 0.17.0, so a hit also means the file was never built
against it.

| Old (0.13/0.14) | 0.17.0 | Status | Exact diagnostic / note |
|---|---|---|---|
| `usingnamespace` | removed; re-export explicitly, one `pub const` per name | gone | `expected function or variable declaration after pub` |
| `async f()`, `await`, `suspend`, `resume`, `anyframe`, `@frameSize` | removed as keywords; concurrency is `io.async` / `Future.await` | gone | `async` now parses as an ordinary identifier |
| `@Type(.{ .int = ... })` | `@Int`, `@Tuple`, `@Pointer`, `@Fn`, `@Struct`, `@Union`, `@Enum`, `@EnumLiteral` | gone | `invalid builtin function: '@Type'` |
| `@setCold(true)` | `@branchHint(.cold)` (also `.likely`, `.unlikely`, `.unpredictable`, `.none`) | gone | `invalid builtin function: '@setCold'` |
| `@fence(order)` | removed; strengthen the atomic orderings instead | gone | `invalid builtin function: '@fence'` |
| `@setAlignStack(n)` | `callconv(.withStackAlign(.c, n))`, from `std.lang.CallingConvention.withStackAlign` | gone | `invalid builtin function: '@setAlignStack'` |
| `callconv(.C)`, `.Stdcall`, `.Naked` | `callconv(.c)`, `.winapi`, `.naked` | gone | `union 'lang.CallingConvention' has no member named 'C'` |
| `@export(foo, .{...})` | `@export(&foo, .{...})` | gone | `expected pointer type, found 'fn () void'` |
| `@typeInfo(T).Int`, `.Struct`, `.ComptimeInt`, `.Pointer.Size.One` | `.int`, `.@"struct"`, `.comptime_int`, `.one` | gone | `no field named 'Int' in union 'lang.Type'` |
| `asm volatile (... ::: "rcx", "r11")` | `asm volatile (... ::: .{ .rcx = true, .r11 = true })` | gone | `expected ')', found ','` |
| pointer field in a `packed struct`/`packed union` | store `usize`; `@ptrFromInt`/`@intFromPtr` at the boundary | gone | `packed structs cannot contain fields of type '*u8'` |
| `v[runtime_index]` on a runtime `@Vector`, read or store | copy to an array first (`const a: [n]T = v;`), then index; store back with `v = a;` | gone | `vector index not comptime known` — for a read as well as a store; only a comptime-known vector folds the read |
| `fn f() *const u8 { var x: u8 = 1; return &x; }` | return by value, or take an out-pointer | gone | `returning address of expired local variable 'x'` |
| `pub fn panic(msg, trace, ra) noreturn` | `pub const panic = std.debug.FullPanic(myPanicFn);` | alias | `std.debug.FullPanic(fn ([]const u8, ?usize) noreturn)` |
| `@intFromFloat(x)` for truncation | `@trunc`/`@floor`/`@ceil`/`@round` convert float -> int directly | alias | both compile; the rounding builtins say what you meant |
| `@floatFromInt(small)` | plain coercion when the int fits the significand exactly | alias | `const f: f64 = @as(u8, 200);` compiles |
| `@cImport({...})` | `b.addTranslateC(...)` in `build.zig`, imported as a module — or the translate-c package the 0.17 release notes move it to (Part 7) | gone | `invalid builtin function: '@cImport'` |

Constructs added in 0.14, 0.16 and 0.17 that current code is expected to use:

| Feature | Rel | Shape |
|---|---|---|
| decl literals | 0.14 | `const config: Cfg = .default;` — drives `.empty`, `.init`, `.full`, `.limited(n)` |
| labeled switch + `continue :label` | 0.14 | threaded dispatch for tokenizers, VMs, state machines |
| `@FieldType(S, "name")` | 0.14 | replaces `@TypeOf(@field(undefined_s, "name"))` gymnastics |
| `@Int(.unsigned, bits)` / `@Tuple(&.{...})` | 0.16 | replaces `std.meta.Int` / `std.meta.Tuple`, which 0.17 removed |
| `packed union(u16)` with explicit backing int; `==` on packed unions | 0.16 | |
| packed struct/union values as `switch` prong items | 0.16 | |
| `@backingInt(x)` / `@fromBackingInt(i)` | 0.17 | replace `@intFromEnum` / `@enumFromInt`; also cover tagged unions and packed types with an explicit backing integer |
| `@divCeil(a, b)` | 0.17 | replaces `std.math.divCeil(T, a, b) catch unreachable` |

The `@Type` row is a lookup entry only. Which of the eight replacement builtins to reach for, their
signatures and arities, and why there is deliberately no `@Float`/`@Array`/`@Optional` are owned by
`references/comptime.md` ZS-COMPTIME-18.

`usingnamespace` has no replacement construct — this row is the whole answer, and
`references/comptime.md` ZS-COMPTIME-27 points here. Re-export one `pub const` per name.
There is no mixin, no wildcard, and no conditional-declaration trick; a declaration that used to be
conditionally mixed in becomes a `pub const x = if (cond) a else b;` or a separate file selected by
`@import`.

```zig
// does-not-compile — BAD: 0.14 — `expected function or variable declaration after pub`
pub usingnamespace @import("helpers.zig");
```

```zig
// fragment — GOOD
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

There is no `std.io` in 0.17.0 (`root source file struct 'std' has no member named 'io'`).
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

| Old (0.13/0.14) | 0.17.0 | Status |
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
| `std.fmt.FormatOptions` | `std.fmt.Options` | gone: `root source file struct 'fmt' has no member named 'FormatOptions'` |
| `std.fmt.Formatter` | `std.fmt.Alt(Data, formatFn)` + `std.fmt.alt(ctx, .funcName)` | gone: `root source file struct 'fmt' has no member named 'Formatter'` |
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

**Check:** `rg -n 'pub fn format\(' src/` — every hit must read
`(value, w: *std.Io.Writer) std.Io.Writer.Error!void`; a four-parameter signature is the loud half
of this rule. The silent half: for each type that declares `format`, grep its name at call sites and
confirm the specifier is `{f}` and not `{}`. Also `{D}` anywhere, and `{}`/`{any}` on an enum where
`{t}` was meant.

| Old | 0.17.0 | Status |
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

**Check:** `rg -n 'std\.fs\.' src/` — every hit is either a `gone` row (a hard error) or one of
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

| Old | 0.17.0 | Status |
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
| `std.fs.File.OpenFlags` / `CreateFlags` | `Io.Dir.OpenFileOptions` / `CreateFileOptions` | gone (0.16 kept them as aliases on `Io.File`; 0.17 removed those) |
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
// `deleteFile`'s set is legal here only because this scope is unwinding (ZS-CONC-27).
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
Then the three that are not simple renames: `containsAtLeastScalar` (0.17 **swapped its last two
parameters** and removed `containsAtLeastScalar2` — read each call site),
`mem.tokenize(`/`mem.split(`/`mem.splitBackwards(` with no `Scalar`/`Any`/`Sequence` suffix, and
`mem.page_size`.

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

> [!WARNING]
> `containsAtLeastScalar` **swapped its last two parameters** in 0.17: 0.16 took
> `(T, list, minimum, element)`, 0.17 takes `(T, list, element, minimum)`, and the 0.16 spelling of
> the new order, `containsAtLeastScalar2`, is gone. For an integer `T` both orders type-check, so a
> 0.16 call site compiles on 0.17 and asks a different question. Check every call site by hand.

Related `std.mem` changes — the removals, the reordered `containsAtLeastScalar`, and the new `cut`
family:

| Old | 0.17.0 | Status |
|---|---|---|
| `mem.containsAtLeastScalar(T, list, minimum, element)` (the 0.16 order) | `mem.containsAtLeastScalar(T, list, element, minimum)` | wrong output |
| `mem.containsAtLeastScalar2(T, list, element, minimum)` | `mem.containsAtLeastScalar(T, list, element, minimum)` | gone |
| `mem.readPackedIntNative/Foreign` | `mem.readPackedInt(T, bytes, bit_offset, .native/.foreign)` | gone (an alias in 0.16) |
| `mem.writePackedIntNative/Foreign` | `mem.writePackedInt(T, bytes, bit_offset, value, .native/.foreign)` | gone (an alias in 0.16) |
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

Decl-literal construction is `references/data.md` ZS-DATA-13; the
`std.BoundedArray`/`SegmentedList` replacements are ZS-DATA-26; *why* the allocator is a per-call
parameter rather than a field is `references/memory.md` ZS-MEM-06. The table below is
the lookup surface for all three.

**Why:** not applicable — this section is a rename table, not a single rule. The rationale for the
unmanaged shape belongs to `references/memory.md` ZS-MEM-06, cited above.

**Check:** grep the diff for `ArrayListUnmanaged`, `array_list.Managed`, `BoundedArray`,
`SegmentedList`, `TailQueue`, `ComptimeStringMap`, and `std.ArrayHashMap`/`AutoArrayHashMap`/
`StringArrayHashMap`. Then the per-call-allocator shape: any `ArrayList(...)` followed by `.init(`,
and any `append`, `appendSlice`, `deinit`, `ensureTotalCapacity`, or `toOwnedSlice` whose first
argument is not an allocator.

| Old | 0.17.0 | Status |
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
| `std.heap.MemoryPoolAligned` / `Extra` / `Options` | `std.heap.memory_pool.Aligned` / `.Extra` / `.Options` | gone (aliases in 0.16) |
| `std.heap.memory_pool.Managed` / `AlignedManaged` / `ExtraManaged` | `std.heap.memory_pool.Aligned` / `.Extra`, with the allocator per call | gone (aliases in 0.16) |
| `PriorityQueue`/`PriorityDequeue` with an allocator field | field removed; pass `gpa` per call | gone |
| — | `std.Deque(T)` with `.empty`, `initCapacity`, `initBuffer` | new |

> [!WARNING]
> The **non-array** hash maps did not follow. `std.StringHashMap`, `std.AutoHashMap` and
> `std.HashMap` still exist in 0.17.0, are still managed (they hold an allocator field), and are
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

### ZS-MIG-08 [M] Allocators: `SafeAllocator` replaced `GeneralPurposeAllocator`

`std.heap.GeneralPurposeAllocator` no longer exists (`root source file struct 'heap' has no member
named 'GeneralPurposeAllocator'`), and the name it had from 0.14 to 0.16, `std.heap.DebugAllocator`,
is a deprecated alias in 0.17 for `std.heap.SafeAllocator`. `SafeAllocator` is not generic:
construct it with `.init(backing_allocator, .{})`.

**Why:** the rename reflects what it is (a safety-checking allocator: leaks, double frees, and
allocations freed into the wrong instance, plus most writes after free when the backing allocator
does not reuse memory), and `remap` was added so allocators can move an allocation cheaply instead
of forcing every caller to alloc/copy/free — implementations that only provide `resize` leave that
on the table.

**Check:** grep for `GeneralPurposeAllocator`, `DebugAllocator`, `heap.Check`,
`ThreadSafeAllocator`, and `std.mem.page_size`. For a project that implements its own allocator, the
structural check is the vtable literal: three members instead of four, or an `alloc`/`resize`/`free`
taking a `u8` log2 alignment instead of `std.mem.Alignment`, means it predates 0.16 and will not
compile.

| Old | 0.17.0 | Status |
|---|---|---|
| `std.heap.GeneralPurposeAllocator(.{})` | `std.heap.SafeAllocator`; 0.16's `DebugAllocator(.{})` is an alias of it (Part 7) | gone |
| `var gpa = GPA(.{}){};` | `var sa: std.heap.SafeAllocator = .init(std.heap.page_allocator, .{});` | gone |
| `gpa.deinit()` returning `bool` | returns the leak count, a `usize`; 0.16's `DebugAllocator` returned `std.heap.Check` (`.ok` / `.leak`) | wrong output |
| `std.heap.ThreadSafeAllocator` | removed — `SafeAllocator` is always thread-safe, and `std.heap.smp_allocator` is the release-build choice | gone |
| `heap.ArenaAllocator` default-init `.{}` | `.init(child_allocator)` | alias |
| — | `std.heap.smp_allocator` (`SmpAllocator`) for multithreaded `fast`/`small` builds | new |
| vtable `alloc/resize/free` with `u8` log2 align | all take `alignment: std.mem.Alignment` | gone |
| vtable had no `remap` | `remap` is now a **required** vtable member | gone |
| `std.mem.page_size` | `std.heap.page_size_min` / `page_size_max` / `pageSize()` | gone |

The migration consequence, in one line: **an allocator written before 0.16 will not compile**,
because `remap` is a required vtable member and every slot takes `alignment: std.mem.Alignment`
instead of a `u8` log2 alignment. The vtable's exact declaration and the four members' contracts —
including why returning `null` from `remap` is a correct answer rather than a failure — are owned by
`references/memory.md` ZS-MEM-24. Unimplementable slots take `Allocator.noAlloc` /
`noResize` / `noRemap` / `noFree`.

```zig
// fragment — GOOD: only when you cannot take `init.gpa`; see ZS-MIG-09
var sa: std.heap.SafeAllocator = .init(std.heap.page_allocator, .{});
defer assert(sa.deinit() == 0); // the leak count
const gpa = sa.allocator();
```

---

## Part 5 — Entry point, concurrency, and testing

### ZS-MIG-09 [M] Entry point: `pub fn main(init: std.process.Init) !void`

Take `std.process.Init` (or `Init.Minimal`) as the first parameter of `main`. Do not hand-roll an
allocator, argv, environ, or an `Io` in `main`.

**Why:** argv and environ are no longer process globals — `std.process.argsAlloc` and
`std.process.getEnvMap` do not exist: `root source file struct 'process' has no member
named 'argsAlloc'`. The only supported way to reach them is through the parameter the runtime hands
you. `Init` also hands you a leak-checked `gpa` (a `SafeAllocator` in `debug` and `safe` builds)
and a target-appropriate `Io`, which is the whole GPA-setup boilerplate deleted.

**Check:** `rg -n 'pub fn main\(\)' src/` returns nothing, and neither does a grep for
`argsAlloc`, `argsFree`, `getEnvMap`, `std.ChildProcess`, `process.Child.init(`, or
`process.Child.run(`. A `SafeAllocator` (or the deprecated `DebugAllocator`) constructed in `main`
when `init.gpa` is in scope is the milder form of the same finding.

Exact shape (`std/process.zig`):

```zig
// fragment — from std/process.zig
pub const Init = struct {
    minimal: Minimal,                 // Init is a superset of Minimal
    arena: *std.heap.ArenaAllocator,  // whole-process storage, freed on exit, threadsafe
    gpa: Allocator,                   // temporary allocations; SafeAllocator in debug and safe
    io: Io,                           // default Io for the target; leak-checked in debug
    environ_map: *Environ.Map,        // NOT threadsafe
    preopens: Preopens,               // mainly WASI

    pub const Minimal = struct { environ: Environ, args: Args };
};
```

| Old | 0.17.0 | Status |
|---|---|---|
| `pub fn main() !void` + manual GPA | `pub fn main(init: std.process.Init) !void` | compiles, but obsolete |
| `std.process.argsAlloc(gpa)` / `argsFree` | `try init.minimal.args.toSlice(arena)` -> `[]const [:0]const u8` | gone |
| any std argument *parser* | there has never been one; hand-roll it (`references/build.md` ZS-BUILD-41) | — |
| `std.process.getEnvMap(gpa)` | `init.environ_map` | gone |
| `var gpa_state = GPA(.{}){}; const gpa = …` | `const gpa = init.gpa;` | — |
| `std.io.getStdOut()` | `std.Io.File.stdout()` + `init.io` | gone |
| `std.process.Child.init(argv, gpa)` + `spawn()` | `std.process.spawn(io, .{ .argv = …, .stdout = .pipe })` | gone |
| `std.process.Child.run(...)` | `std.process.run(gpa, io, options)` | gone |
| `std.process.execv` | `std.process.replace(io, .{ .argv = … })`; add `.exe = .{ .path = dir }` for what 0.16 spelled `replacePath`, which 0.17 removed | gone |
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

| Old | 0.17.0 | Status |
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
| `std.event.Loop` | `Io.Threaded`; `Io.Evented` is experimental and no backend builds in 0.17 (ZS-CONC-04) | gone |
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
    // (ZS-CONC-27) — handle it explicitly, even when the handling is "stop".
    io.sleep(.fromMilliseconds(1), .awake) catch |err| switch (err) {
        error.Canceled => return,
    };
}
```

---

### ZS-MIG-11 [M] Testing: `std.testing.io`, `Smith` fuzz inputs, `tmpDir(Io.Dir.OpenOptions)`

The three test-surface changes that break 0.14 test code. How to *use* them is owned by the testing
chapter: `std.testing.io` and test-time I/O are `references/testing.md` ZS-TEST-09;
writing `Smith`-shaped fuzz targets is ZS-TEST-20; the `Smith` types you may and may not ask for is
ZS-TEST-22. This table is the rename lookup.

**Why:** not applicable — this section is a rename table, not a single rule. The reasoning behind
`Smith` and test-time `Io` is owned by `references/testing.md` ZS-TEST-09 and
ZS-TEST-20, cited above.

**Check:** in test code, grep for a fuzz target whose parameter is `[]const u8` rather than
`*std.testing.Smith`; for a `tmpDir` handle's `.dir` methods called with no `std.testing.io`
argument; and for `std.fs.cwd()` inside a `test` block. `expectEqual(@as(` is the cosmetic third:
redundant wherever peer resolution already fixes the type, but **not** stale — 0.17 std still writes
it 755 times, and it stays necessary where the two arguments do not peer-resolve (ZS-TEST-06). Note
it only; never make it a blocking finding.

| Old | 0.17.0 | Status |
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

Note that `zig build test --fuzz` works again on 0.17.0; it did not build on 0.16.0. `zig test
-ffuzz` builds, but its runner panics with `missing --cache-dir=[path]
argument`, so fuzz through `zig build`. The corpus still runs under plain `zig test`.

---

## Part 6 — Build system and miscellaneous renames

### ZS-MIG-12 [M] Build: artifacts take `.root_module`; `.name` is an enum literal in `.zon`

From `std/Build.zig`: `ExecutableOptions` is exactly
`{ name, root_module, version, linkage, max_rss, use_llvm, use_lld, zig_lib_dir, win32_manifest }`,
with `win32_manifest` deprecated in 0.17 — `root_source_file`, `target`, and `optimize` are not
among them. (`use_new_linker` is a field on the
returned `Step.Compile`, assigned after creation, not an option.)

The build chapter owns the reasoning and the shapes to write instead: module-vs-artifact settings
are `references/build.md` ZS-BUILD-02, `addLibrary(.{ .linkage })` is ZS-BUILD-07, the
`build.zig.zon` manifest fields are ZS-BUILD-10, and `.paths` is ZS-BUILD-12. Below is the rename
lookup only.

**Why:** not applicable — this section is a rename table, not a single rule. The reasoning for the
module-versus-artifact split is owned by `references/build.md` ZS-BUILD-02, cited above.

**Check:** in `build.zig`, every `root_source_file` must sit inside a `createModule`/`addModule`
literal, never inside an `addExecutable`/`addLibrary`/`addTest` one; then grep for
`addStaticLibrary`, `addSharedLibrary`, `addWriteFiles`, `addRemoveDirTree(`, `.addModule(` or
`.linkLibC(` called on an artifact, and any `getPath` call on a `LazyPath` — 0.17 removed all four,
`getPath4` included. In `build.zig.zon`: a quoted `.name`, a missing `.fingerprint`, or a `.hash`
beginning `1220`.

| Old | 0.17.0 | Status |
|---|---|---|
| `b.addExecutable(.{ .name, .root_source_file, .target, .optimize })` | `.{ .name = …, .root_module = b.createModule(.{ .root_source_file, .target, .optimize, .imports }) }` | gone: `no field named 'root_source_file' in struct 'Build.ExecutableOptions'` |
| `b.addSharedLibrary` / `b.addStaticLibrary` | `b.addLibrary(.{ .linkage = …, .name = …, .root_module = mod })` | gone |
| `b.addTest(.{ .root_source_file = … })` | `b.addTest(.{ .root_module = mod })` — one module per test binary | gone |
| `exe.addModule("x", m)` | `mod.addImport("x", m)` or `.imports = &.{ .{ .name = "x", .module = m } }` | gone |
| `exe.linkLibC()`, `exe.linkSystemLibrary(…)`, `exe.addIncludePath(…)`, `exe.addCSourceFile(…)` on the artifact | the same methods on the `*Module`, or `.link_libc = true` in `createModule` | gone: `no field or member function named 'linkLibC' in 'Build.Step.Compile'` |
| `b.addWriteFiles()` to update sources | `b.addUpdateSourceFiles()` | gone |
| `b.addRemoveDirTree(…)` | removed: neither 0.16 nor 0.17 has a remove-directory step. A scratch directory is `b.addTempFiles()` or `b.tmpPath()`, deleted when the build succeeds | gone |
| `@cImport` in source | `b.addTranslateC(.{ .root_source_file, .target, .optimize })` -> `.createModule()`, which the 0.17 release notes deprecate for the translate-c package (Part 7) | gone |
| `LazyPath.getPath` / `getPath2` / `getPath3` / `getPath4` | none: 0.17 resolves a path only when a step runs, so hand the `LazyPath` to the step that reads it | gone (0.16 kept the first three as aliases) |
| `GeneratedFile.getPath` / `getPath2` / `getPath3` | none: `std.Build.GeneratedFile` is removed | gone |
| `-Dno-bin` skip-the-binary idiom | a `check` step whose artifacts are never installed or run (`references/build.md` ZS-BUILD-32) | — |

`build.zig.zon` changed independently. **`.name` is an enum literal there, and a plain string in
`build.zig`** — mixing these up is a common error:

| Old | 0.17.0 |
|---|---|
| `.name = "myproject"` (string) | `.name = .myproject` (enum literal) |
| — | `.fingerprint = 0x…` — generated once, **never** hand-edited (identity + trust implications) |
| — | `.minimum_zig_version = "0.17.0"` — documentation only; the compiler never reads it |
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
wired — is `references/build.md` ZS-BUILD-01. Do not reconstruct it from this table.

---

### ZS-MIG-13 [M] Miscellaneous std renames

Low-frequency but each one dates a diff. Deviating is only defensible while mid-migration.

**Why:** the tier is `[M]` for the same reason ZS-MIG-06 is, not because these renames matter more
than their frequency suggests: the `alias` rows **compile silently**, so nothing but this rule
catches them, and the ones 0.17 still accepts — `pipeToFileSystem`, `PipeOptions`, `utf8Decode`,
`wtf8Decode`, `std.debug.runtime_safety` — already fail the build under ZS-MIG-14's `[M!]` denylist,
while 0.17 itself rejects the rows that were aliases in 0.16 (`bufPrintZ`, `initEmpty()`,
`initFull()`, `std.meta.Int`, `std.meta.Tuple`). A rule cannot own a spelling at `[S]` while another
rule fails CI on it. `std.math.sign` is the
sharpest row and is not an alias at all: its return type changed, so old call sites keep compiling
and produce a different value. Beyond the shared mechanism each row is its own small story, and the
row's right-hand column is the whole answer.

**Check:** four patterns, because one line of alternation is unreadable —
`rg -n 'bufPrintZ|std\.meta\.(Int|Tuple|declList)|initEmpty\(\)|initFull\(\)' src/` and
`rg -n 'pipeToFileSystem|PipeOptions|std\.rand\.|CrossTarget|StackIterator' src/` and
`rg -n 'captureStackTrace|dumpStackTraceFromBase|walkStackWindows' src/` and
`rg -n 'wtf8Decode\b|utf8Decode\b|std\.debug\.runtime_safety' src/`
— each hit is a row above; `utf8Decode2` and its siblings are live, which is why the
boundary is there. The same names spelled out: `bufPrintZ`, `std.meta.Int`,
`std.meta.Tuple`, `std.meta.declList`,
`initEmpty()`, `initFull()`, `pipeToFileSystem`, `PipeOptions`, `std.rand.`, `CrossTarget`,
`captureStackTrace`, `dumpStackTraceFromBase`, `walkStackWindows`, `StackIterator`, `utf8Decode`,
`wtf8Decode`, and `std.debug.runtime_safety` — each is a row above. `std.math.sign` deserves a
second look rather than a grep: its return type changed, so every call site that stores or compares
its result needs re-reading.

| Old | 0.17.0 | Status |
|---|---|---|
| `std.fmt.bufPrintZ(buf, fmt, args)` | `std.mem.printSentinel(buf, fmt, args, 0)` | gone (an alias in 0.16) |
| `std.meta.Int(sign, bits)` | `@Int(sign, bits)` | gone (an alias in 0.16) |
| `std.meta.Tuple(&.{...})` | `@Tuple(&.{...})` | gone (an alias in 0.16, "to be removed after 0.16.0") |
| `std.meta.declList` | removed | gone |
| `std.tar.PipeOptions` | `std.tar.ExtractOptions` | alias |
| `std.tar.pipeToFileSystem` | `std.tar.extract(io, dir, reader, options)` — now sanitizes path traversal | alias |
| `EnumSet.initEmpty()` / `initFull()` | decl literals `.empty` / `.full` | gone (aliases in 0.16) |
| `BitSet.initEmpty()` / `initFull()` | `.empty` / `.full`; `bit_set.Dynamic.initEmpty(gpa, n)` keeps its name | gone (aliases in 0.16) |
| `std.debug.runtime_safety` | `@import("builtin").optimize.runtimeSafety()` — your own module's mode; std's is not yours | alias (removed after 0.18) |
| `std.debug.captureStackTrace` | `std.debug.captureCurrentStackTrace(options, addr_buf)` | gone |
| `std.debug.dumpStackTraceFromBase` | `std.debug.dumpCurrentStackTrace(options)` | gone |
| `std.debug.walkStackWindows` / `writeStackTraceWindows` | `captureCurrentStackTrace` / `writeCurrentStackTrace` | gone |
| `std.debug.StackIterator` | now internal | gone |
| `std.unicode.utf8Decode` / `wtf8Decode` | deprecated: "awkward API that is too easy to use incorrectly" | alias |
| `std.rand` | `std.Random` | gone |
| `std.zig.CrossTarget` | `std.Target.Query` | gone |
| `std.Target.SubSystem` | `std.zig.Subsystem`; `builtin.subsystem` removed | gone (an alias in 0.16) |
| `std.DynLib` on Windows | removed — call `LoadLibraryExW`/`GetProcAddress` directly | gone |
| medium-level `std.posix` / `std.os.windows` wrappers | removed — go up to `std.Io` or down to `std.posix.system` | gone |
| `std.math.sign` | now returns the smallest int type that fits the possible values | wrong output |
| `std.compress.flate` | removed in 0.15.1, re-added in 0.16.0 as a from-scratch deflate | — |

```zig
// fragment — GOOD: inside a test body; `Color` is an enum
var zbuf: [16]u8 = undefined;
const z = try std.mem.printSentinel(&zbuf, "{d}", .{7}, 0); // was bufPrintZ, then bufPrintSentinel

var set: std.EnumSet(Color) = .empty; // was .initEmpty()
const all: std.EnumSet(Color) = .full; // was .initFull()

var bytes: [4]u8 = @splat(0);
std.mem.writePackedInt(u12, &bytes, 3, 0xabc, .native); // was writePackedIntNative
const v = std.mem.readPackedInt(u12, &bytes, 3, .native);
```

---

## Part 7 — Zig 0.16 → 0.17

What 0.17 renamed, removed or made mean something else. Every row was checked against the 0.17.0
standard-library source tree or by compiling a probe with `zig 0.17.0`; a row that only the release
notes claim says so. The old spelling is the 0.16 one, and where 0.16 had itself deprecated it the
status says so. **new** marks a 0.17 spelling with nothing deprecated behind it; the pattern then
finds the code it replaces.

Run a row's pattern as `rg -n -e '<pattern>' src/ build.zig`, adding your scripts and CI files for
the command-line rows at the end — `-e`, because some patterns start with `-`. Where a cell lists
several patterns, run each. Where the name did not change — the **wrong output** rows, the
`@bitCast` rows, `std.meta.declarations` and `addOptionPath` — the pattern also matches the 0.17
spelling, so each hit is a call site to re-read rather than a defect.

| 0.16 | 0.17 | Status | `rg` pattern |
|---|---|---|---|
| `@intFromEnum(x)` | `@backingInt(x)`, which also takes a tagged union or a packed type with an explicit backing integer | alias; `zig fmt` rewrites it | `@intFromEnum\(` |
| `@enumFromInt(i)` | `@fromBackingInt(i)`; `i` must already have the backing type, so `@intCast` a wider one first | alias; `zig fmt` rewrites it | `@enumFromInt\(` |
| `[_]T{v} ** n`, `a ** n` | `@splat(v)` with a result type | gone | ` \*\* ` |
| `void{}` | `{}` | gone | `\bvoid\{\}` |
| `errdefer \|err\| …` | move the body into an inner function, and at the call `inner() catch \|err\| { …; return err; }` | gone | `errdefer \x7c` |
| `i0` | `u0` | gone | `\bi0\b` |
| `@cImport(...)` | `b.addTranslateC(...)` and its `.createModule()`, or the translate-c package (next row) | gone | `@cImport\(` |
| `b.addTranslateC(.{ .root_source_file = … })` | the translate-c package: `zig fetch --save git+https://codeberg.org/ziglang/translate-c#zig-0.17.x`, then `Translator.init(b.dependency("translate_c", .{}), .{ .c_source_file = … })` | alias (release notes only; the source does not mark it) | `addTranslateC\(` |
| `.linkage = .internal`, `.linkage = .link_once` | for `.internal`, do not `@export` the symbol; for `.link_once`, `.weak`. `std.lang.GlobalLinkage` is `strong` and `weak` only | gone | `\.linkage = \.internal\b`, `\.link_once\b` |
| `@bitCast(x)` of an `extern struct` or `extern union` | `@ptrCast` of a pointer to it, or an `extern union` | gone | `@bitCast\(` |
| `@bitCast` on an array or a vector | the same call, now reinterpreting logical bits independent of endianness, so a big-endian target gets a different result | wrong output | `@bitCast\(` |
| `@bitCast(i)` to an enum, a compile error in 0.16 | compiles, and is safety-checked like `@fromBackingInt` | new | `@bitCast\(` |
| `@hasDecl(T, "name")` on a private declaration in the same file | `false`: only `pub` declarations count | wrong output | `@hasDecl\(` |
| `std.math.divCeil(T, a, b) catch unreachable` | `@divCeil(a, b)` | new | `math\.divCeil\(` |
| `enum(u8) {}` (an empty exhaustive enum) | `enum(noreturn) {}` | gone | `enum\(u\d+\) \{\}` |
| `@typeInfo(T).@"struct".fields`, each `f.name`, `f.type`, `f.is_comptime`, `f.alignment`, `f.defaultValue()` | `.field_names[i]`, `.field_types[i]`, `.field_attrs[i].@"comptime"`, `.field_attrs[i].@"align"`, `.field_attrs[i].defaultValue(FieldType)` | gone | `\.fields\b`, `\.is_comptime\b` |
| `.decls` on a struct, enum, union or opaque, each `d.name` | `.decl_names[i]` | gone | `\.decls\b` |
| `.@"enum".fields` (`.name`, `.value`), `.is_exhaustive` | `.field_names`, `.field_values`, `.mode == .exhaustive` | gone | `\.fields\b`, `\.is_exhaustive\b` |
| `.@"union".fields` | `.field_names`, `.field_types`, `.field_attrs`, plus `.backing_integer` | gone | `\.fields\b` |
| `.@"fn".params[i].type`, `.calling_convention`, `.is_var_args` | `.param_types[i]`, `.attrs.@"callconv"`, `.attrs.varargs` | gone | `\.params\[`, `\.calling_convention\b`, `\.is_var_args\b` |
| `.pointer.is_const`, `is_volatile`, `alignment`, `address_space`, `is_allowzero` | `.pointer.attrs.@"const"`, `@"volatile"`, `@"align"`, `@"addrspace"`, `@"allowzero"` | gone | `\.is_const\b`, `\.is_volatile\b`, `\.address_space\b`, `\.is_allowzero\b` |
| `@typeInfo(E).error_set`, a `?[]const Type.Error` | `.error_set.error_names`, a `?[]const [:0]const u8`; `null` still means `anyerror` | gone | `\.error_set[^.]`, `error_set\.\?` |
| `std.builtin.Type.StructField.Attributes`, `UnionField.Attributes`, `Fn.Param.Attributes` | `std.lang.Type.Struct.FieldAttributes`, `Union.FieldAttributes`, `Fn.ParamAttributes` | gone | `Field\.Attributes\b`, `Param\.Attributes\b` |
| `std.meta.fields(T)`, `std.meta.declarationInfo` | `@typeInfo(T)` | gone | `meta\.fields\(`, `meta\.declarationInfo\(` |
| `std.meta.declarations(T)`, a `[]const Declaration` | the same name, now a `[]const [:0]const u8` | gone | `meta\.declarations\(` |
| `std.meta.fieldInfo`, `fieldNames`, `fieldTypes` | `@typeInfo`, `@FieldType` | alias | `meta\.field[INT][a-z]+\(` |
| `std.builtin.X` | `std.lang.X` | alias (removed after 0.17) | `std\.builtin\b` |
| `std.builtin.OptimizeMode`, `.Debug`, `.ReleaseSafe`, `.ReleaseFast`, `.ReleaseSmall` | `std.lang.Optimize`, `.debug`, `.safe`, `.fast`, `.small` | alias, but gone in `==` and `!=`; `@tagName` and `{t}` print the new names | `OptimizeMode`, `\.Debug\b`, `\.Release[A-Z]\w*` |
| `@import("builtin").mode` | `@import("builtin").optimize` | alias (removed after 0.18) | `builtin"?\)?\.mode\b` |
| `@import("builtin").cpu`, `.os`, `.abi`, `.object_format` | `.target.cpu`, `.target.os`, `.target.abi`, `.target.ofmt` | alias (removed in 0.18) | `builtin"?\)?\.cpu\b`, `builtin"?\)?\.os\b`, `builtin"?\)?\.abi\b`, `object_format` |
| `std.debug.runtime_safety` | `@import("builtin").optimize.runtimeSafety()`, your module's mode rather than std's | alias (removed after 0.18) | `debug\.runtime_safety\b` |
| `var da: std.heap.DebugAllocator(.{}) = .init;` | `var sa: std.heap.SafeAllocator = .init(std.heap.page_allocator, .{});` — always thread-safe; its `Options` are `stack_trace_frames`, `check_write_after_free`, `canary`, `bucket_size_log2` and `block_size_log2`, with no memory limit and no verbose log | alias | `DebugAllocator` |
| `assert(da.deinit() == .ok)`, a `std.heap.Check` | `assert(sa.deinit() == 0)`: the leak count | alias | `heap\.Check\b`, `deinit\(\) [=!]= \.ok\b` |
| `std.heap.stackFallback(n, fallback)` and `.get()`, `StackFallbackAllocator` | `var buf: [n]u8 = undefined;` `var bfa: std.heap.BufferFirstAllocator = .init(&buf, fallback);` then `bfa.allocator()`, as often as you like | gone | `[sS]tackFallback` |
| `std.fmt.allocPrint(gpa, f, args)`, `allocPrintSentinel(gpa, f, args, 0)` | `gpa.print(f, args)`, `gpa.printSentinel(f, args, 0)` | alias | `fmt\.allocPrint` |
| `std.fmt.bufPrint`, `bufPrintSentinel`, `BufPrintError` | `std.mem.print`, `std.mem.printSentinel`, `std.mem.PrintError` | alias | `fmt\.[bB]ufPrint` |
| `std.fmt.bufPrintZ(buf, f, args)` | `std.mem.printSentinel(buf, f, args, 0)` | gone (an alias in 0.16) | `bufPrintZ` |
| `gpa.dupeZ(u8, s)` | `gpa.dupeSentinel(u8, s, 0)` | gone (an alias in 0.16) | `\.dupeZ\(` |
| `std.meta.Int(sign, bits)`, `std.meta.Tuple(types)` | `@Int(sign, bits)`, `@Tuple(types)` | gone (aliases in 0.16) | `meta\.Int\b`, `meta\.Tuple\b` |
| `.initEmpty()`, `.initFull()` on an `EnumSet`, `bit_set.Integer` or `bit_set.Array` | `.empty`, `.full`; `Dynamic.initEmpty(gpa, n)` keeps its name | gone (aliases in 0.16) | `\.init[EF][a-z]+\(\)` |
| `bit_set.IntegerBitSet`, `ArrayBitSet`, `StaticBitSet`, `DynamicBitSetUnmanaged`, `DynamicBitSet`, `DynamicManaged`, and the `std.*BitSet*` re-exports | `bit_set.Integer`, `Array`, `Static`, `Dynamic`; `Dynamic` takes the allocator per call | alias | `BitSet`, `DynamicManaged` |
| `std.heap.MemoryPoolAligned`, `MemoryPoolExtra`, `MemoryPoolOptions`; `heap.memory_pool.Managed`, `AlignedManaged`, `ExtraManaged` | `std.heap.memory_pool.Aligned`, `Extra`, `Options` | gone (aliases in 0.16) | `MemoryPool[AEO]`, `memory_pool\.\w*Managed` |
| `list.getLast()`, `list.getLastOrNull()` | `list.last()`, a `?T` copy; the borrow is `list.lastPtr()` | alias | `\.getLast` |
| `DoublyLinkedList.pop` | `popLast` | alias | `DoublyLinkedList`, then each `.pop()` on one |
| `mem.containsAtLeastScalar2(T, list, element, minimum)` | `mem.containsAtLeastScalar(T, list, element, minimum)` | gone | `containsAtLeastScalar2` |
| `mem.containsAtLeastScalar(T, list, minimum, element)` | the same name with the parameters swapped: `(T, list, element, minimum)` | wrong output | `containsAtLeastScalar\(` |
| `mem.readPackedIntNative`, `readPackedIntForeign`, `writePackedIntNative`, `writePackedIntForeign` | `mem.readPackedInt(T, bytes, bit_offset, .native)`, `writePackedInt(T, bytes, bit_offset, value, .foreign)` | gone (aliases in 0.16) | `PackedInt[NF]` |
| `mem.byteSwapAllFields`, `byteSwapAllFieldsAligned` | `mem.byteSwap`, `byteSwapAligned` | alias | `byteSwapAllFields` |
| `mem.eql(f64, a, a)` on a slice holding NaN | `false`: the same slice no longer short-circuits; `findDiff` likewise | wrong output | `mem\.eql\(f\d`, `findDiff\(f\d` |
| `ascii.indexOfIgnoreCase`, `indexOfIgnoreCasePos`, `indexOfIgnoreCasePosLinear` | `findIgnoreCase`, `findIgnoreCasePos`, `findIgnoreCasePosLinear` | gone (aliases in 0.16) | `indexOfIgnoreCase` |
| `std.zon.parse.fromSlice(T, gpa, source, diag, options)`, the no-pointers form | `fromSliceNoAlloc(T, .{ .gpa = gpa, .arena = arena, .source = source, .diagnostics = &diag })` | gone | `fromSlice\(\w+, [a-z]` |
| `std.zon.parse.fromSliceAlloc(…)` with `std.zon.parse.free(gpa, value)` | `fromSlice(T, .{ … })`, which allocates the result into `.arena`; there is no `free` | gone | `fromSliceAlloc`, `zon\.parse\.free\(` |
| `var diag: std.zon.parse.Diagnostics = .{};` `defer diag.deinit(gpa);` then `{f}` on `diag` | `var diag: std.zon.parse.Diagnostics = undefined;` then `diag.log(path)`, `diag.fatal(path)`, or `{f}` on `diag.fmt(path)` | gone | `Diagnostics = \.\{\}` |
| `std.Io.File.OpenFlags`, `CreateFlags`, `OpenMode` | `std.Io.Dir.OpenFileOptions`, `CreateFileOptions`, `OpenFileOptions.Mode` | gone (aliases in 0.16) | `File\.[OC][a-z]+Flags`, `File\.OpenMode` |
| `std.process.spawnPath(io, dir, options)`, `replacePath(io, dir, options)` | `spawn(io, .{ .exe = .{ .path = dir }, … })`, `replace(io, .{ .exe = .{ .path = dir }, … })` | gone | `spawnPath\(`, `replacePath\(` |
| `reader.readAlloc` on an `Io.Reader` | `readAllocAll` | alias | `\.readAlloc\(` |
| `path.resolve`, `path.relative`, and their `Posix` and `Windows` forms | `resolveAlloc`, `relativeAlloc`, and theirs | alias | `path\.resolve[^A]`, `path\.relative[^A]` |
| `uri.getHost(&buf)` | `std.Io.net.HostName.fromUri(uri, &buf)`, which validates the name | gone | `\.getHost\(` |
| `std.gpu` | `std.spirv` | gone | `std\.gpu\b` |
| `std.Target.SubSystem` | `std.zig.Subsystem` | gone (an alias in 0.16) | `SubSystem` |
| `arch.isAARCH64()`, `isMIPS`, `isMIPS32`, `isMIPS64`, `isPowerPC`, `isPowerPC32`, `isPowerPC64`, `isRISCV`, `isSPARC`, `isSpirV`, `isLoongArch`; `os.tag.isBSD()` | `isAarch64()`, `isMips`, `isMips32`, `isMips64`, `isPowerpc`, `isPowerpc32`, `isPowerpc64`, `isRiscv`, `isSparc`, `isSpirv`, `isLoongarch`; for `isBSD`, the tags you mean | alias (removed in 0.18) | `\.is[A-Z]{3}`, `\.isPowerPC`, `\.isSpirV`, `\.isLoongArch` |
| `socket.sendMany(io, messages, flags)` | `socket.sendManyTimeout(io, messages, flags, .none)`, which returns the error and the count sent | alias | `\.sendMany\(` |
| — | `{q}` and `{qf}` specifiers; `Io.Semaphore.waitTimeout`; `ArrayList.lockPointers`, `unlockPointers`, `lastPtr`; `std.meta.BackingInt` | new | — |
| `if (b.args) \|args\| run.addArgs(args);` | `run.addPassthruArgs();` — the step is then never cached, and the build script cannot see the arguments | gone | `b\.args\b` |
| `b.build_root`, a `Directory` | `b.root`, a `Cache.Path` | gone | `\.build_root\b` |
| `b.addFmt(.{ .paths = &.{"src"} })` | `.paths = b.pathList(&.{"src"})`, and the same for `.exclude_paths` | gone | `paths = &` |
| `b.lazyDependency(name, args)`, a `?*Dependency` | `b.dependency(name, args)`, which now fetches a lazy package itself, or `try b.dependencyLazy(name, args)` to batch several | alias | `lazyDependency\(` |
| `b.reference_trace = n;` | `zig build -freference-trace=n` | gone | `reference_trace` |
| `lazy_path.getPath(…)` through `getPath4(…)`; `GeneratedFile.getPath*`; `std.Build.GeneratedFile` | none: the configure phase cannot resolve a path; hand the `LazyPath` to the step that reads it | gone | `\.getPath\d?\(`, `\bGeneratedFile\b` |
| `lazy_path.getDisplayName()` | `{f}` on the `LazyPath` | alias | `getDisplayName\(` |
| `lazy_path.basename(b, step)` | removed | gone | `\.basename\(b,` |
| `.{ .cwd_relative = path }` | `b.graph.cwdRelativePath(path)` | alias | `\.cwd_relative\b` |
| `b.dupe(s)`, `b.dupeStrings(s)`, `b.dupePath(s)` | `b.graph.dupeString(s)`, `dupeStrings`, `dupePath` | alias | `\bb\.dupe` |
| `run.addArtifactArg`, `addOutputFileArg`, `addFileContentArg`, `addOutputDirectoryArg`, `addDirectoryArg`, `addDecoratedDirectoryArg`, `addDepFileOutputArg`, and each `addPrefixed*` form | the `…Arg2` of each, taking `.{ .prefix, .suffix }` and, for a path, `.make_absolute` | alias | `\.add\w+Arg\(` |
| `run.addFileArg`, `addPrefixedFileArg` | `addFileArg2` | alias (release notes only; the source does not mark it) | `\.add(Prefixed)?FileArg\(` |
| `b.runAllowFail(…)` | `b.runFallible(…)` | alias | `runAllowFail\(` |
| `run.enableTestRunnerMode()` | `run.enableProtocolMode()` | alias | `enableTestRunnerMode\(` |
| `b.findProgram(names, paths)`, an `error{FileNotFound}![]const u8` | `b.findProgramLazy(.{ .names = names })`, a `LazyPath`; or `b.findProgram(.{ .names = names })`, a `?[]const u8` that poisons the configure cache | gone | `findProgram\(&` |
| `opts.addOptionPath(name, dir)` for a directory | `addOptionPathDirectory`, since `addOptionPath` now means a file; `addOptionPathUntracked` to opt out of tracking | — | `addOptionPath\(` |
| `.include_guard_override` on a `ConfigHeader` | `.include_guard` | gone | `include_guard_override` |
| `mod.addWin32ResourceFile`, `.win32_manifest`, `.rc_includes`; `Compile.out_filename` | no replacement yet (the resource APIs move to an external `rc` package) | alias | `Win32Resource`, `win32_manifest`, `rc_includes`, `out_filename` |
| `zig build --zig-lib-dir path` | `zig build --zig-lib=path` | gone | `--zig-lib-dir` |
| `zig build --global-cache-dir`, `--build-runner`, `--debug-rt`, `--verbose-llvm-bc` | removed | gone | `--global-cache-dir`, `--build-runner`, `--debug-rt`, `--verbose-llvm-bc` |
| `-Doptimize=ReleaseSafe`, `-O ReleaseFast` | `-Doptimize=safe`, `-O fast`; TitleCase still parses, through the deprecated `Optimize.fromString` | alias | `optimize=[DR][a-z]`, `-O ?[DR][a-z]` |
| `zig fetch <url>` to fill `zig-pkg/` | `zig fetch --save <url>`, or `zig build`; a bare `zig fetch` fills only the global cache | wrong output | `zig fetch [^-]` |

Changes with no spelling to search for: `zig build test --fuzz` and `zig reduce` work again (neither
built on 0.16.0); the new ELF linker, `-fnew-linker` and therefore `-fincremental`, emits DWARF and
`.eh_frame`; a diagnostic that names a std type now says `lang.`, not `builtin.`; and no ZLS
release supports Zig 0.17.0.

---

## Part 8 — Enforcing it

### ZS-MIG-14 [M!] Fail the build on deprecated-but-compiling spellings

Add a CI step that greps the source for the **alias** rows above and fails on a hit, pin the
toolchain for real — `.minimum_zig_version` is documentation only, so use a pinned CI version plus
the `comptime builtin.zig_version` guard (`references/build.md` ZS-BUILD-34,
ZS-BUILD-39) — and treat a toolchain bump as a migration task with its own review.

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
# compiles today and is stale; at 0.17.0 every spelling below still resolves,
# so none of these patterns is dead weight. The 0.16 aliases this list used to
# carry (`bufPrintZ`, `initEmpty()`, `std.meta.Int`, `MemoryPoolExtra`,
# `getPath2`, `File.OpenFlags`) are compile errors in 0.17, so the compiler
# gates them now.
# EVERY pattern must use `-e`. With one bare positional and one `-e`, rg reads the
# bare pattern as a PATH: it exits 2 on every run and silently drops that half of
# the denylist. Exit status is the gate — 0 means a hit, 1 means clean.
rg -n --type zig \
  -e 'std\.mem\.(indexOf|lastIndexOf)|ArrayListUnmanaged|ArrayListAligned' \
  -e 'array_list\.(Aligned)?Managed|(ArrayHashMap|AutoArrayHashMap|StringArrayHashMap)Unmanaged' \
  -e 'std\.fs\.(path|max_|base64_)' \
  -e 'pipeToFileSystem|tar\.PipeOptions|(utf8|wtf8)Decode\(|^pub fn panic\(' \
  -e 'std\.builtin\b|builtin"?\)?\.(mode|cpu|os|abi|object_format)\b|debug\.runtime_safety' \
  -e 'OptimizeMode|\.(Debug|ReleaseSafe|ReleaseFast|ReleaseSmall)\b' \
  -e 'DebugAllocator|heap\.Check\b|fmt\.(allocPrint|bufPrint|BufPrintError)' \
  -e 'BitSet|DynamicManaged|\.getLast(OrNull)?\(|meta\.field(Info|Names|Types)\b' \
  -e 'byteSwapAllFields|\.readAlloc\(|path\.(resolve|relative)(Posix|Windows)?\(|\.sendMany\(' \
  -e '\.is(AARCH64|MIPS(32|64)?|PowerPC(32|64)?|RISCV|SPARC|SpirV|LoongArch|BSD)\(' \
  -e 'lazyDependency\(|runAllowFail\(|enableTestRunnerMode\(|getDisplayName\(' \
  -e '\.cwd_relative\b|\bb\.dupe|addDecoratedDirectoryArg\(' \
  -e 'add(Prefixed)?(Artifact|OutputFile|FileContent)Arg\(' \
  -e 'add(Prefixed)?(OutputDirectory|Directory|DepFileOutput)Arg\(' \
  src/ build.zig
```

Some `alias` rows are **deliberately** not on the list, and the exclusion is part of the rule — a
denylist nobody trusts gets deleted. `@intFromFloat` and `@floatFromInt` are legal, unremarkable
builtins that this standard merely prefers to spell more informatively (ZS-DATA-11), so gating them
would fail builds over a preference. `@intFromEnum` and `@enumFromInt` need no grep:
`zig fmt --check` rewrites them, so the format gate already fails. `heap.ArenaAllocator`
default-init `.{}` has no spelling a regex can distinguish from any other `.{}`, and
`DoublyLinkedList.pop` none it can distinguish from `ArrayList.pop`. `b.addTranslateC`, `addFileArg`
and `addPrefixedFileArg` are deprecated only by the 0.17 release notes, not in the source. The Win32
resource APIs and `Compile.out_filename` are deprecated with nothing yet to move to.
`-Doptimize=ReleaseSafe` on a command line is not Zig source; Part 7 gives its pattern for scripts
and CI files. Everything else in the chapter's alias column is above: adding a row to that table
without adding it here leaves a gate that claims more coverage than it has. One pattern
over-matches: `\.(Debug|ReleaseSafe|…)\b` also hits a user enum with those tag names, and the fix is
to rename the tags, not to loosen the gate.

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
15. `std.builtin.`, `builtin.mode == .Debug`, `std.heap.DebugAllocator`, `std.fmt.allocPrint`,
    `if (b.args)`, or `@typeInfo(T).@"struct".fields` — a pre-0.17 model, whether or not it still
    compiles (Part 7).

## Decided by tools

The compiler rejects each of these on its own; no setting turns one off.

| Tool | Lint | Level | Forbids |
|---|---|---|---|
| zig | `invalid builtin function: …` | error | a builtin 0.17 no longer has: `@setCold`, `@Type`, `@fence`, `@setAlignStack`, `@optimizeFor` |

## Rule IDs before the Zig 0.17.0 revision

Before the revision the families ran `ZS-ASRT-01`–`ZS-ASRT-33`, `ZS-BUILD-01`–`ZS-BUILD-43`,
`ZS-CAPI-01`–`ZS-CAPI-23`, `ZS-CT-01`–`ZS-CT-28`, `ZS-ERR-01`–`ZS-ERR-38`, `ZS-FMT-01`–`ZS-FMT-20`,
`ZS-IO-01`–`ZS-IO-48`, `ZS-MEM-01`–`ZS-MEM-28`, `ZS-MIG-01`–`ZS-MIG-14`, `ZS-NAME-01`–`ZS-NAME-37`,
`ZS-PERF-01`–`ZS-PERF-24`, `ZS-TEST-01`–`ZS-TEST-29` and `ZS-TYPE-01`–`ZS-TYPE-41`. The table lists
every ID in those ranges that changed, and what it is now; an ID it does not list is unchanged.

| Before | Now |
|---|---|
| `ZS-ASRT-01` | `ZS-ASSERT-01` |
| `ZS-ASRT-02` | `ZS-ASSERT-02` |
| `ZS-ASRT-03` | `ZS-ASSERT-03` |
| `ZS-ASRT-04` | `ZS-ASSERT-04` |
| `ZS-ASRT-05` | `ZS-ASSERT-05` |
| `ZS-ASRT-06` | `ZS-ASSERT-06` |
| `ZS-ASRT-07` | `ZS-ASSERT-07` |
| `ZS-ASRT-08` | `ZS-ASSERT-08` |
| `ZS-ASRT-09` | `ZS-ASSERT-09` |
| `ZS-ASRT-10` | `ZS-ASSERT-10` |
| `ZS-ASRT-11` | `ZS-ASSERT-11` |
| `ZS-ASRT-12` | `ZS-ASSERT-12` |
| `ZS-ASRT-13` | `ZS-ASSERT-13` |
| `ZS-ASRT-14` | `ZS-ASSERT-14` |
| `ZS-ASRT-15` | `ZS-ASSERT-15` |
| `ZS-ASRT-16` | `ZS-ASSERT-16` |
| `ZS-ASRT-17` | `ZS-ASSERT-17` |
| `ZS-ASRT-18` | `ZS-ASSERT-18` |
| `ZS-ASRT-19` | `ZS-ASSERT-19` |
| `ZS-ASRT-20` | `ZS-ASSERT-20` |
| `ZS-ASRT-21` | `ZS-ASSERT-21` |
| `ZS-ASRT-22` | `ZS-ASSERT-22` |
| `ZS-ASRT-23` | `ZS-ASSERT-23` |
| `ZS-ASRT-24` | `ZS-ASSERT-24` |
| `ZS-ASRT-25` | `ZS-ASSERT-25` |
| `ZS-ASRT-26` | `ZS-ASSERT-26` |
| `ZS-ASRT-27` | `ZS-ASSERT-27` |
| `ZS-ASRT-28` | `ZS-ASSERT-28` |
| `ZS-ASRT-29` | `ZS-ASSERT-29` |
| `ZS-ASRT-30` | `ZS-ASSERT-30` |
| `ZS-ASRT-31` | `ZS-ASSERT-31` |
| `ZS-ASRT-32` | `ZS-ASSERT-32` |
| `ZS-ASRT-33` | `ZS-ASSERT-33` |
| `ZS-BUILD-35` | removed — `zig build test --fuzz` and `zig reduce` work in 0.17, the condition this rule set for its own removal |
| `ZS-BUILD-36` | `ZS-BUILD-35` |
| `ZS-BUILD-37` | `ZS-BUILD-36` |
| `ZS-BUILD-38` | `ZS-BUILD-37` |
| `ZS-BUILD-39` | `ZS-BUILD-38` |
| `ZS-BUILD-40` | `ZS-BUILD-39` |
| `ZS-BUILD-41` | `ZS-BUILD-40` |
| `ZS-BUILD-42` | `ZS-BUILD-41` |
| `ZS-BUILD-43` | `ZS-BUILD-42` |
| `ZS-CAPI-01` | `ZS-INTEROP-01` |
| `ZS-CAPI-02` | `ZS-INTEROP-02` |
| `ZS-CAPI-03` | `ZS-INTEROP-03` |
| `ZS-CAPI-04` | `ZS-INTEROP-04` |
| `ZS-CAPI-05` | `ZS-INTEROP-05` |
| `ZS-CAPI-06` | `ZS-INTEROP-06` |
| `ZS-CAPI-07` | `ZS-INTEROP-07` |
| `ZS-CAPI-08` | `ZS-INTEROP-08` |
| `ZS-CAPI-09` | `ZS-INTEROP-09` |
| `ZS-CAPI-10` | `ZS-INTEROP-10` |
| `ZS-CAPI-11` | `ZS-INTEROP-11` |
| `ZS-CAPI-12` | `ZS-INTEROP-12` |
| `ZS-CAPI-13` | `ZS-INTEROP-13` |
| `ZS-CAPI-14` | `ZS-INTEROP-14` |
| `ZS-CAPI-15` | `ZS-INTEROP-15` |
| `ZS-CAPI-16` | `ZS-INTEROP-16` |
| `ZS-CAPI-17` | `ZS-INTEROP-17` |
| `ZS-CAPI-18` | `ZS-INTEROP-18` |
| `ZS-CAPI-19` | `ZS-INTEROP-19` |
| `ZS-CAPI-20` | `ZS-INTEROP-20` |
| `ZS-CAPI-21` | `ZS-INTEROP-21` |
| `ZS-CAPI-22` | `ZS-INTEROP-22` |
| `ZS-CAPI-23` | `ZS-INTEROP-23` |
| `ZS-CT-01` | `ZS-COMPTIME-01` |
| `ZS-CT-02` | `ZS-COMPTIME-02` |
| `ZS-CT-03` | `ZS-COMPTIME-03` |
| `ZS-CT-04` | `ZS-COMPTIME-04` |
| `ZS-CT-05` | `ZS-COMPTIME-05` |
| `ZS-CT-06` | `ZS-COMPTIME-06` |
| `ZS-CT-07` | `ZS-COMPTIME-07` |
| `ZS-CT-08` | `ZS-COMPTIME-08` |
| `ZS-CT-09` | `ZS-COMPTIME-09` |
| `ZS-CT-10` | `ZS-COMPTIME-10` |
| `ZS-CT-11` | `ZS-COMPTIME-11` |
| `ZS-CT-12` | `ZS-COMPTIME-12` |
| `ZS-CT-13` | `ZS-COMPTIME-13` |
| `ZS-CT-14` | `ZS-COMPTIME-14` |
| `ZS-CT-15` | `ZS-COMPTIME-15` |
| `ZS-CT-16` | `ZS-COMPTIME-16` |
| `ZS-CT-17` | `ZS-COMPTIME-17` |
| `ZS-CT-18` | `ZS-COMPTIME-18` |
| `ZS-CT-19` | `ZS-COMPTIME-19` |
| `ZS-CT-20` | `ZS-COMPTIME-20` |
| `ZS-CT-21` | `ZS-COMPTIME-21` |
| `ZS-CT-22` | `ZS-COMPTIME-22` |
| `ZS-CT-23` | `ZS-COMPTIME-23` |
| `ZS-CT-24` | `ZS-COMPTIME-24` |
| `ZS-CT-25` | `ZS-COMPTIME-25` |
| `ZS-CT-26` | `ZS-COMPTIME-26` |
| `ZS-CT-27` | `ZS-COMPTIME-27` |
| `ZS-CT-28` | `ZS-COMPTIME-28` |
| `ZS-FMT-01` | `ZS-OUT-01` |
| `ZS-FMT-02` | `ZS-OUT-02` |
| `ZS-FMT-03` | `ZS-OUT-03` |
| `ZS-FMT-04` | `ZS-OUT-04` |
| `ZS-FMT-05` | `ZS-OUT-05` |
| `ZS-FMT-06` | `ZS-OUT-06` |
| `ZS-FMT-07` | `ZS-OUT-07` |
| `ZS-FMT-08` | `ZS-OUT-08` |
| `ZS-FMT-09` | `ZS-OUT-09` |
| `ZS-FMT-10` | `ZS-OUT-10` |
| `ZS-FMT-11` | `ZS-OUT-11` |
| `ZS-FMT-12` | `ZS-OUT-12` |
| `ZS-FMT-13` | `ZS-OUT-13` |
| `ZS-FMT-14` | `ZS-OUT-14` |
| `ZS-FMT-15` | `ZS-OUT-15` |
| `ZS-FMT-16` | `ZS-OUT-16` |
| `ZS-FMT-17` | `ZS-OUT-17` |
| `ZS-FMT-18` | `ZS-OUT-18` |
| `ZS-FMT-19` | `ZS-OUT-19` |
| `ZS-FMT-20` | `ZS-OUT-20` |
| `ZS-IO-01` | `ZS-CONC-01` |
| `ZS-IO-02` | `ZS-CONC-02` |
| `ZS-IO-03` | `ZS-CONC-03` |
| `ZS-IO-04` | `ZS-CONC-04` |
| `ZS-IO-05` | `ZS-CONC-05` |
| `ZS-IO-06` | `ZS-CONC-06` |
| `ZS-IO-07` | `ZS-CONC-07` |
| `ZS-IO-08` | `ZS-CONC-08` |
| `ZS-IO-09` | `ZS-CONC-09` |
| `ZS-IO-10` | `ZS-CONC-10` |
| `ZS-IO-11` | `ZS-CONC-11` |
| `ZS-IO-12` | `ZS-CONC-12` |
| `ZS-IO-13` | `ZS-CONC-13` |
| `ZS-IO-14` | `ZS-CONC-14` |
| `ZS-IO-15` | `ZS-CONC-15` |
| `ZS-IO-16` | `ZS-CONC-16` |
| `ZS-IO-17` | `ZS-CONC-17` |
| `ZS-IO-18` | `ZS-CONC-18` |
| `ZS-IO-19` | `ZS-CONC-19` |
| `ZS-IO-20` | `ZS-CONC-20` |
| `ZS-IO-21` | `ZS-CONC-21` |
| `ZS-IO-22` | `ZS-CONC-22` |
| `ZS-IO-23` | `ZS-CONC-23` |
| `ZS-IO-24` | `ZS-CONC-24` |
| `ZS-IO-25` | `ZS-CONC-25` |
| `ZS-IO-26` | `ZS-CONC-26` |
| `ZS-IO-27` | `ZS-CONC-27` |
| `ZS-IO-28` | `ZS-CONC-28` |
| `ZS-IO-29` | `ZS-CONC-29` |
| `ZS-IO-30` | `ZS-CONC-30` |
| `ZS-IO-31` | `ZS-CONC-31` |
| `ZS-IO-32` | `ZS-CONC-32` |
| `ZS-IO-33` | `ZS-CONC-33` |
| `ZS-IO-34` | `ZS-CONC-34` |
| `ZS-IO-35` | `ZS-CONC-35` |
| `ZS-IO-36` | `ZS-CONC-36` |
| `ZS-IO-37` | `ZS-CONC-37` |
| `ZS-IO-38` | `ZS-CONC-38` |
| `ZS-IO-39` | `ZS-CONC-39` |
| `ZS-IO-40` | `ZS-CONC-40` |
| `ZS-IO-41` | `ZS-CONC-41` |
| `ZS-IO-42` | `ZS-CONC-42` |
| `ZS-IO-43` | `ZS-CONC-43` |
| `ZS-IO-44` | `ZS-CONC-44` |
| `ZS-IO-45` | `ZS-CONC-45` |
| `ZS-IO-46` | `ZS-CONC-46` |
| `ZS-IO-47` | `ZS-CONC-47` |
| `ZS-IO-48` | `ZS-CONC-48` |
| `ZS-TYPE-01` | `ZS-DATA-01` |
| `ZS-TYPE-02` | `ZS-DATA-02` |
| `ZS-TYPE-03` | `ZS-DATA-03` |
| `ZS-TYPE-04` | `ZS-DATA-04` |
| `ZS-TYPE-05` | `ZS-DATA-05` |
| `ZS-TYPE-06` | `ZS-DATA-06` |
| `ZS-TYPE-07` | `ZS-DATA-07` |
| `ZS-TYPE-08` | `ZS-DATA-08` |
| `ZS-TYPE-09` | `ZS-DATA-09` |
| `ZS-TYPE-10` | `ZS-DATA-10` |
| `ZS-TYPE-11` | `ZS-DATA-11` |
| `ZS-TYPE-12` | `ZS-DATA-12` |
| `ZS-TYPE-13` | `ZS-DATA-13` |
| `ZS-TYPE-14` | `ZS-DATA-14` |
| `ZS-TYPE-15` | `ZS-DATA-15` |
| `ZS-TYPE-16` | `ZS-DATA-16` |
| `ZS-TYPE-17` | `ZS-DATA-17` |
| `ZS-TYPE-18` | `ZS-DATA-18` |
| `ZS-TYPE-19` | `ZS-DATA-19` |
| `ZS-TYPE-20` | `ZS-DATA-20` |
| `ZS-TYPE-21` | `ZS-DATA-21` |
| `ZS-TYPE-22` | `ZS-DATA-22` |
| `ZS-TYPE-23` | `ZS-DATA-23` |
| `ZS-TYPE-24` | `ZS-DATA-24` |
| `ZS-TYPE-25` | `ZS-DATA-25` |
| `ZS-TYPE-26` | `ZS-DATA-26` |
| `ZS-TYPE-27` | `ZS-DATA-27` |
| `ZS-TYPE-28` | `ZS-DATA-28` |
| `ZS-TYPE-29` | `ZS-DATA-29` |
| `ZS-TYPE-30` | `ZS-DATA-30` |
| `ZS-TYPE-31` | `ZS-DATA-31` |
| `ZS-TYPE-32` | `ZS-DATA-32` |
| `ZS-TYPE-33` | `ZS-DATA-33` |
| `ZS-TYPE-34` | `ZS-DATA-34` |
| `ZS-TYPE-35` | `ZS-DATA-35` |
| `ZS-TYPE-36` | `ZS-DATA-36` |
| `ZS-TYPE-37` | `ZS-DATA-37` |
| `ZS-TYPE-38` | `ZS-DATA-38` |
| `ZS-TYPE-39` | `ZS-DATA-39` |
| `ZS-TYPE-40` | `ZS-DATA-40` |
| `ZS-TYPE-41` | `ZS-DATA-41` |
