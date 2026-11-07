# C interop and cross-target builds

Scope: everything that happens where Zig stops. Exporting Zig functions to C (`export fn`,
`@export`, `callconv(.c)`); declaring C functions in Zig (`extern "c" fn`, `@extern`); the types
that may legally cross (and the fact that **error sets may not**); `[*c]` pointers, NUL-terminated
strings, and C integer types; struct layout and callbacks with `void *userdata`; who owns and frees
memory that crosses. Then the target axis: `builtin.target` branching, `-fsingle-threaded`,
freestanding and WebAssembly — including the places where the rest of this standard **does not
apply** because there is no operating system to apply it to.

Layout and string rules for the types themselves live in the data chapter (ZS-DATA-19, ZS-DATA-20,
ZS-DATA-29), with their layout assertions in ZS-ASSERT-19 and alignment in ZS-MEM-24; allocator
selection and ownership vocabulary live in the memory chapter; wiring `link_libc` and C sources into
a build lives in the build chapter (ZS-BUILD-05). This chapter cites those rather than repeating
them, and adds only what is specific to the boundary, including translating C headers in the build
(ZS-INTEROP-15).

Every example assumes a file opening with `const std = @import("std");`,
`const builtin = @import("builtin");` and `const assert = std.debug.assert;` — assertions are called
bare, per ZS-ASSERT-01.

Several examples here build for `x86_64-linux-gnu`, `x86_64-windows-gnu`, `arm-linux-gnueabihf`,
`wasm32-wasi`, `wasm32-freestanding`, and `thumb-freestanding-eabi` as well as the host; where the
target set matters to the rule, the block's marker names it.

## Contents

- **The boundary contract**
  - ZS-INTEROP-01 [M] A Zig error set cannot cross a C boundary — return a status code
  - ZS-INTEROP-02 [M!] Validate everything C hands you; do not assert it
- **Exporting Zig to C**
  - ZS-INTEROP-03 [M] `export fn` when the Zig name is the symbol; `@export(&f, …)` when it is not
  - ZS-INTEROP-04 [M] Spell the C calling convention `.c`, never one architecture's member
  - ZS-INTEROP-05 [S] Prefix every exported symbol with the library name
- **Calling C from Zig**
  - ZS-INTEROP-06 [M] `extern "c" fn` for libc; bare `extern fn` for objects you link yourself
  - ZS-INTEROP-07 [M] Use `@extern` only for what a declaration cannot express
  - ZS-INTEROP-08 [M] Confine C types to one boundary module
- **Pointers, strings, and integers**
  - ZS-INTEROP-09 [M] A `[*c]` pointer dies at the first Zig function; convert it to a slice or `?*T`
  - ZS-INTEROP-10 [M] `span` in, `[]const u8` inside, `dupeSentinel` out, `sliceTo` for fixed arrays
  - ZS-INTEROP-11 [M] Convert a C integer to a fixed-width Zig integer with a checked cast
- **Structs, callbacks, and ownership**
  - ZS-INTEROP-12 [M] A C callback cannot capture; all state travels through `userdata`
  - ZS-INTEROP-13 [M] A callback parks its failure in `userdata` for the caller to check
  - ZS-INTEROP-14 [M] Whoever calls `free` picks the allocator: `std.heap.c_allocator` if C does
- **Getting the declarations**
  - ZS-INTEROP-15 [S] Hand-write `extern` declarations; use `b.addTranslateC` for large headers
- **Targets**
  - ZS-INTEROP-16 [M] On freestanding there is no `std.process.Init` — export your entry points instead
  - ZS-INTEROP-17 [M] Freestanding supplies its own panic handler, as a namespace
  - ZS-INTEROP-18 [M] Branch on `builtin.target` at comptime; `@compileError` the unhandled target
  - ZS-INTEROP-19 [M] `-fsingle-threaded` removes task concurrency and cancellation
  - ZS-INTEROP-20 [M] On WASI, resolve directories through `init.preopens`, never `Io.Dir.cwd()`
  - ZS-INTEROP-21 [M] Derive `link_libc`, `single_threaded`, and `entry` from the resolved target
- **Boundary review checklist**
- Decided by tools

---

## The boundary contract

### ZS-INTEROP-01 [M] A Zig error set cannot cross a C boundary — return a status code

An exported function returns either a status `enum(c_int)` or a `bool`, never `!T`. When it also
produces a value, the value leaves through a pointer parameter that is written **only** on success.
This is the single most important rule in the chapter: a wrapper that tries to return `!T` to C is
not a style mistake, it is a category error.

Convert in one `fromError` switch; it is exhaustive, so a new Zig error fails the build until it is
given a status. Never smuggle the error out as an `int` either: the error set is a
compile-time-assigned integer whose numbering is not stable across builds, so the number would mean
something different next compile.

**Why:** an error union is a Zig-only tagged representation with no C spelling, so the compiler
rejects it in a C signature outright. Converting once is what keeps the error vocabulary the C
header documents finite and reviewable.

**Check:** an `export fn` or `callconv(.c)` signature whose return type contains `!`, or an
`anyerror`. A `try` in the body of such a function is the same finding from inside — it can only
compile if the return type is an error union. Also a status returned as a bare `c_int` rather than
an `enum(c_int)`, which smuggles an unnamed vocabulary across.

```zig
// verified
const std = @import("std");

/// The one error vocabulary the C side sees. `0` is success, so
/// `if (rc)` in C reads as "failed".
pub const Status = enum(c_int) {
    ok = 0,
    invalid_argument = 1,
    out_of_range = 2,
    out_of_memory = 3,

    fn fromError(err: ParseError) Status {
        return switch (err) {
            error.Invalid => .invalid_argument,
            error.Overflow => .out_of_range,
        };
    }
};

const ParseError = error{ Invalid, Overflow };

fn parse(text: []const u8) ParseError!u32 {
    if (text.len == 0) return error.Invalid;
    var acc: u32 = 0;
    for (text) |ch| {
        if (ch < '0' or ch > '9') return error.Invalid;
        acc = try std.math.mul(u32, acc, 10);
        acc = try std.math.add(u32, acc, ch - '0');
    }
    return acc;
}

/// The boundary wrapper: value out through a pointer, failure through the
/// return value. `out` is untouched unless the status is `.ok`.
export fn zs_parse_u32(text: ?[*:0]const u8, out: ?*u32) Status {
    const text_ptr = text orelse return .invalid_argument;
    const out_ptr = out orelse return .invalid_argument;
    const value = parse(std.mem.span(text_ptr)) catch |err| return .fromError(err);
    out_ptr.* = value;
    return .ok;
}

test "boundary wrapper maps every error to a status" {
    var value: u32 = 0;
    try std.testing.expectEqual(Status.ok, zs_parse_u32("123", &value));
    try std.testing.expectEqual(123, value);
    try std.testing.expectEqual(Status.invalid_argument, zs_parse_u32("12a", &value));
    try std.testing.expectEqual(Status.out_of_range, zs_parse_u32("99999999999", &value));
    try std.testing.expectEqual(Status.invalid_argument, zs_parse_u32(null, &value));
}
```

```zig
// rejected — zig: return type '!u32' not allowed in a C calling convention
// error: return type '!u32' not allowed in function with calling convention '...'
export fn zs_parse(text: [*:0]const u8) !u32 {
    _ = text;
    return error.Invalid;
}
```

A `bool` return is the right shape when there is exactly one failure mode and the C caller cannot
act on a reason — see ZS-DATA-27 on reducing dimensionality at the call site. Anything richer gets
the enum.

### ZS-INTEROP-02 [M!] Validate everything C hands you; do not assert it

At an exported entry point, check pointers for null, lengths against the buffer you were also given,
and integers against the enum or range they claim to be — with `if` and an error status, not with
`assert`. Check an enum value before any cast: `@fromBackingInt` on an out-of-range value is illegal
behavior in every mode, not a panic you can catch, and so is a `@bitCast` to an enum. That check is
what `std.enums.fromInt(E, integer) ?E` is for; it accepts any integer type, where `@fromBackingInt`
accepts only the enum's exact backing type.

**Trigger criteria — treat as `[M]`** when any of the SKILL.md high-reliability conditions hold, and
additionally whenever **the C side is not built from this repository**: a plugin ABI, a shared
library with third-party consumers, an FFI surface for a scripting runtime, or anything reachable
from a network-facing process. In all of those the C caller is outside your trust boundary even if
it is friendly, because it is compiled separately and can go stale.

*Relaxed form:* always null-check pointers and always bound lengths — those two are never optional,
because in a `fast` build a violated assert is not a crash but a memory-safety bug (see
ZS-ASSERT-02). Exhaustive enum and range validation may be skipped for a C shim that lives in the
same repository and is compiled by the same `build.zig`.

**Why:** this is ZS-ASSERT-09's boundary clause, applied to the one boundary where it bites hardest.
An `assert` on data from another compilation unit is a remote denial of service in a `safe` build
and illegal behavior in a `fast` one.

**Check:** in the body of an `export fn`: any `assert(`, any `@fromBackingInt` (or the deprecated
`@enumFromInt`) on a parameter with no preceding `std.enums.fromInt` or explicit range test, and any
pointer parameter reached with `.?`, `.*`, or `[0..len]` before an `orelse` that handles null. A
length parameter used to slice without first being compared against the buffer bound is the same
defect.

```zig
// verified
const std = @import("std");

const Status = enum(c_int) { ok = 0, invalid_argument = 1 };

pub const Mode = enum(u8) { read = 0, write = 1, append = 2 };

/// Every field is checked, not asserted: a wrong `mode` is a caller bug on the
/// C side, which is outside this process's trust boundary.
export fn zs_open(
    path: ?[*:0]const u8,
    path_len_max: usize,
    mode_raw: c_int,
    out: ?*u32,
) Status {
    const out_ptr = out orelse return .invalid_argument;
    const path_ptr = path orelse return .invalid_argument;

    const path_slice = std.mem.span(path_ptr);
    if (path_slice.len > path_len_max) return .invalid_argument;
    if (path_slice.len == 0) return .invalid_argument;

    const mode = std.enums.fromInt(Mode, mode_raw) orelse return .invalid_argument;

    out_ptr.* = @backingInt(mode);
    return .ok;
}

test "hostile inputs produce a status, not a panic" {
    var handle: u32 = 0;
    try std.testing.expectEqual(Status.ok, zs_open("f", 8, 1, &handle));
    try std.testing.expectEqual(Status.invalid_argument, zs_open(null, 8, 1, &handle));
    try std.testing.expectEqual(Status.invalid_argument, zs_open("f", 0, 1, &handle));
    try std.testing.expectEqual(Status.invalid_argument, zs_open("f", 8, 99, &handle));
    try std.testing.expectEqual(Status.invalid_argument, zs_open("f", 8, -1, &handle));
}
```

---

## Exporting Zig to C

### ZS-INTEROP-03 [M] `export fn` when the Zig name is the symbol; `@export(&f, …)` when it is not

`export fn foo` gives the symbol the target's C calling convention automatically and names it `foo`.
When the exported symbol must differ from the Zig declaration — a C prefix, a versioned alias, weak
linkage, a specific section — use `@export` in a `comptime` block instead. The operand is a
**pointer**: `@export(&f, …)`, not `@export(f, …)`.

The signature is
`@export(comptime ptr: *const anyopaque, comptime options: std.lang.ExportOptions) void`. A value in
place of the pointer fails loudly: `error: expected pointer type, found 'fn () callconv(.c) u32'`.
`ExportOptions` has the fields `name: []const u8`, `linkage: GlobalLinkage = .strong`,
`section: ?[]const u8 = null`, and `visibility: SymbolVisibility = .default` — everything but `name`
has a default, and per ZS-PERF-17 pass the ones that matter to you explicitly. `GlobalLinkage` is
only `.strong` or `.weak`.

**Why:** `@export` separates the symbol from the declaration, so one Zig function can back several
symbols, which is how you ship a compatibility alias without duplicating the body.

**Check:** `@export(` whose first argument is not `&`-prefixed (the value form), and an `@export`
call outside a `comptime` block. Also a second `export fn` whose body only forwards to another
exported function — that is an alias `@export` should provide.

```zig
// verified
const std = @import("std");

/// Sums a buffer. `export` gives the symbol the target's C calling convention.
export fn zs_sum(values: [*]const u32, values_len: usize) u64 {
    var total: u64 = 0;
    for (values[0..values_len]) |v| total += v;
    return total;
}

/// A Zig-internal name, exported under a different C symbol.
fn sumInternal(values: [*]const u32, values_len: usize) callconv(.c) u64 {
    return zs_sum(values, values_len);
}

comptime {
    @export(&sumInternal, .{ .name = "zs_sum_alias", .linkage = .strong });
}
```

`export var` works the same way for globals: `export var zs_version: c_int = 3;`.

### ZS-INTEROP-04 [M] Spell the C calling convention `.c`, never one architecture's member

Write `callconv(.c)`. `std.lang.CallingConvention` is a `union(enum(u8))` whose members name one
architecture's convention each and carry a payload; `.c` is a `pub const` the target resolves to its
C convention, and `.winapi` and `.kernel` are the other two portable ones. An architecture's member,
a payload literal such as `.{ .x86_64_sysv = .{} }`, is for code that runs on that architecture
alone. The spellings the union does not have are the compiler's (the row below), and a stack
alignment is `CallingConvention.withStackAlign(.c, n)`, evaluated at `comptime`.

**Why:** nearly every member names one architecture's convention, so `.c`, the alias the target
resolves, is the one spelling right on every target. The type is:

```zig
// fragment — (quoted from std/lang.zig, `CallingConvention`)
pub const CallingConvention = union(enum(u8)) {
    pub const c = builtin.target.cCallingConvention().?;
    pub const winapi: CallingConvention = switch (builtin.target.cpu.arch) { ... };

    auto,
    async,
    naked,
    @"inline",

    x86_64_sysv: CommonOptions,
    x86_64_win: CommonOptions,
    x86_stdcall: X86RegparmOptions,
    aarch64_aapcs: CommonOptions,
    // ... one member per architecture-specific convention
};
```

**Check:** a payload literal inside `callconv(` in a file that does not branch on
`builtin.target.cpu.arch` (ZS-INTEROP-18): one architecture's convention, compiled for every target.

```zig
// verified
const std = @import("std");
const CC = std.lang.CallingConvention;

test "the calling convention is a union value" {
    const target_c: CC = .c;
    const explicit: CC = .{ .x86_64_sysv = .{} };
    const aligned = comptime CC.withStackAlign(.c, 16); // comptime is required
    _ = .{ target_c, explicit, aligned };
}
```

### ZS-INTEROP-05 [S] Prefix every exported symbol with the library name

`zs_parse_u32`, not `parse_u32`. Apply it to `export fn`, `export var`, and every `@export` name.
This is the one place in this standard where `snake_case` functions are correct despite ZS-NAME-01 —
the C header is the contract and C's convention wins there. Keep the Zig-internal name `camelCase`
and let the export do the translation, as in ZS-INTEROP-03.

**Why:** C has one flat global namespace with no modules, so an unprefixed `init` or `read` in a
static library collides at link time with any other library that had the same idea, and the
`duplicate symbol` diagnostic points at the linker rather than at either author.

**Check:** every `export fn`, `export var`, and `@export` `.name` in the diff begins with the
project's agreed prefix. A generic-sounding exported symbol — `init`, `open`, `read`, `free`,
`version` — is the finding.

---

## Calling C from Zig

### ZS-INTEROP-06 [M] `extern "c" fn` for libc; bare `extern fn` for objects you link yourself

`extern "c" fn` names libc as the providing library and requires `link_libc`. For a symbol coming
from a `.c` file you compile into the same artifact — or any object you link — write `extern fn`
with no library name. In a module without libc, `extern "c"` is a hard error:
`error: dependency on libc must be explicitly specified in the build command`. Set `link_libc` on
the **module**, not the artifact (ZS-BUILD-05), and only for targets that have one (ZS-INTEROP-21).
`std.c` already declares much of libc (`std.c.abs`, `std.c.getpid`); declare by hand only what it
lacks, so no symbol has two signatures to drift apart.

**Why:** the library name is a link-time dependency declaration, not decoration. Freestanding never
has libc, so the bare form is the one that still builds your own C sources when the module is
cross-compiled to `wasm32-freestanding` or `thumb-freestanding-eabi`.

**Check:** `extern "c"` in a file that a `build.zig` also compiles for a `*-freestanding` target, or
in a module with no `link_libc` set. In the other direction, a bare `extern fn` naming a libc symbol
(`malloc`, `strlen`, `abs`, `getpid`) — that one links by accident and breaks when it does not.

```zig
// verified
const std = @import("std");

/// `std.c` has no `strlen`, so it is declared here; `abs` comes from `std.c`.
extern "c" fn strlen(s: [*:0]const u8) usize;

test "declare by hand only what std.c lacks" {
    const s: [*:0]const u8 = "hello";
    try std.testing.expectEqual(5, strlen(s));
    try std.testing.expectEqual(7, std.c.abs(-7));
}
```

```zig
// fragment — same declaration, for a symbol from your own vendor/shim.c
extern fn zs_c_add(a: u32, b: u32) u32;
```

### ZS-INTEROP-07 [M] Use `@extern` only for what a declaration cannot express

A plain `extern` declaration covers the ordinary case. Reach for `@extern(T, .{ .name = …, … })`
when the C symbol name is not a legal Zig identifier, when you need `library_name`, `linkage`,
`visibility`, `is_thread_local`, or `is_dll_import`, or when you want the symbol as a value (a
function *pointer*) rather than a callable declaration.

Otherwise it is strictly more verbose than `extern fn`, and a plain declaration is already
addressable: `&std.c.abs` gives you a `*const fn (c_int) callconv(.c) c_int` for a table without
needing `@extern`.

**Why:** `@extern(T: type, comptime options: std.lang.ExternOptions) T` returns a *value* rather
than introducing a declaration, which is what lets it bind a symbol whose name is not a legal Zig
identifier and makes `library_name`, `is_thread_local`, and `is_dll_import` expressible at all.

**Check:** an `@extern` whose options are only `.name`, where that name is already a legal Zig
identifier — a plain `extern fn` covers it. Also an `@extern` introduced only to obtain a function
pointer, where `&declaration` already works.

```zig
// verified
const std = @import("std");

/// A declaration is already addressable: no `@extern` is needed for a pointer.
const getpid_fn: *const fn () callconv(.c) std.c.pid_t = &std.c.getpid;

export var zs_version: c_int = 3;

test "bind a symbol as a value" {
    try std.testing.expect(getpid_fn() > 0);
    try std.testing.expectEqual(3, zs_version);
}
```

```zig
// fragment — GOOD: macOS, where the symbol's name is not a legal Zig identifier
const close_nocancel = @extern(
    *const fn (fd: c_int) callconv(.c) c_int,
    .{ .name = "close$NOCANCEL" },
);
```

### ZS-INTEROP-08 [M] Confine C types to one boundary module

`c_int`, `c_long`, `[*c]T`, `[*:0]const u8`, `?*anyopaque`, and every `extern`/`@export` declaration
live in one module — `src/c.zig`, or one such file per C library. Nothing outside it names a C type.
That module exports a Zig-shaped API: slices, fixed-width integers, error sets, `Allocator`
parameters.

**Why:** ZS-INTEROP-09, ZS-INTEROP-10, and ZS-INTEROP-11 each say "convert here, once", which is
enforceable only if there is a *here*. Once `[*c]` and `c_long` spread, each conversion site is a
separate decision under different assumptions, and a grep for `[*c]` stops being a review tool.

**Check:** grep the whole tree for `c_int`, `c_long`, `c_char`, `c_uint`, `[*c]`, `?*anyopaque`,
`extern "c"`, `extern fn`, `@extern`, and `@export`. Every hit outside the designated boundary
module is the finding; the grep returning hits in more than one file per C library is the summary.

---

## Pointers, strings, and integers

### ZS-INTEROP-09 [M] A `[*c]` pointer dies at the first Zig function; convert it to a slice or `?*T`

`[*c]T` may appear as a parameter of an exported function and nowhere else. The first statement that
touches it turns it into `[]T` (with the length C also gave you), `?*T`, or `[:0]const u8`. It is
never stored in a struct, never returned, and never passed to a second Zig function.

`[*c]T` is deliberately the most permissive pointer in the language: simultaneously nullable, of
unknown length, and implicitly convertible to and from `*T`, `[*]T`, and `?*T` without a cast. A
`[*c]` parameter silently accepts `null` and coerces to a non-optional `*T` with no diagnostic.

The narrower types say the same in a C signature. A slice crosses as two parameters, a pointer and
its length. `?*T` is the nullable C pointer: the optional is the null pointer, at no cost.

**Why:** that permissiveness is what makes translated C headers usable, and it switches off every
safety property Zig's pointer types give you for as long as the pointer is in scope. Converting at
the boundary makes the null case a visible branch exactly once.

**Check:** `[*c]` anywhere but a parameter of an `export fn` or `callconv(.c)` function — in a
struct field, a return type, a `const`/`var` declaration, a local binding, or the parameter list of
a plain Zig function. One grep for `[*c]` answers this rule completely.

```zig
// verified
const std = @import("std");

// The C header says: uint32_t zs_checksum(const uint8_t *data, size_t len);
// translate-c would give `data: [*c]const u8`. Narrow it immediately.
export fn zs_checksum(data: [*c]const u8, data_len: usize) u32 {
    // One conversion, at the boundary, with the null case handled.
    const bytes: []const u8 = if (data) |p| p[0..data_len] else &.{};
    return checksum(bytes);
}

/// Everything inward takes a real slice. `[*c]` never appears below here.
fn checksum(bytes: []const u8) u32 {
    return std.hash.Fnv1a_32.hash(bytes);
}

test "null C pointer becomes an empty slice, not a crash" {
    try std.testing.expectEqual(checksum("abc"), zs_checksum("abc", 3));
    try std.testing.expectEqual(checksum(""), zs_checksum(null, 0));
}
```

### ZS-INTEROP-10 [M] `span` in, `[]const u8` inside, `dupeSentinel` out, `sliceTo` for fixed arrays

ZS-DATA-29 already sets the policy: `[]const u8` is the internal string type and the NUL lives only
at the edge. The boundary mechanics are these four cases:

| Direction | Shape | Convert with |
|---|---|---|
| C → Zig, NUL-terminated | `[*:0]const u8`, `?[*:0]const u8` | `std.mem.span(p)` → `[:0]const u8` |
| C → Zig, fixed NUL-**padded** array | `*const [N]u8` | `std.mem.sliceTo(p, 0)` → `[]const u8` |
| C → Zig, pointer + length | `[*c]const u8` + `usize` | `p[0..len]` (ZS-INTEROP-09) |
| Zig → C | `[]const u8` | `gpa.dupeSentinel(u8, s, 0)` → `[:0]u8`, pass `.ptr` |

`span` and `sliceTo` are optional-transparent: given `?[*:0]const u8` they return `?[:0]const u8`,
so `orelse` handles null in the same expression.

**Why:** the two inbound cases look identical in a C header and are not. `char name[16]` in a struct
is NUL-*padded*: a 16-byte name has no terminator, so `span` walks off the field into the next one,
while `sliceTo` stops at the first NUL or at the array's end.

**Check:** `std.mem.span(` whose argument is `&`-taken from a fixed array or an array-typed struct
field rather than a `[*:0]` pointer — that is the read-past-the-end bug. Also a `[]const u8` handed
to a C function via `.ptr` with no `dupeSentinel`/`printSentinel` producing it, and any `.ptr`
passed to C where the slice was not built with a `:0` sentinel.

```zig
// verified
const std = @import("std");

extern "c" fn strlen(s: [*:0]const u8) usize;

/// Inbound: C hands you a pointer, you produce a slice once.
export fn zs_greet_len(name: ?[*:0]const u8) usize {
    const slice: []const u8 = std.mem.span(name orelse return 0);
    return slice.len;
}

/// Outbound: a Zig `[]const u8` has no NUL, so it cannot be handed to C as
/// `const char *`. Materialise a `[:0]u8` first.
fn callWithName(gpa: std.mem.Allocator, name: []const u8) !usize {
    const name_z: [:0]u8 = try gpa.dupeSentinel(u8, name, 0);
    defer gpa.free(name_z);

    return strlen(name_z.ptr);
}

test "span, sliceTo and dupeSentinel across the boundary" {
    try std.testing.expectEqual(5, zs_greet_len("world"));
    try std.testing.expectEqual(0, zs_greet_len(null));

    // A fixed-size C char buffer is NUL-padded, not NUL-terminated by type:
    // `sliceTo` stops at the first NUL, `span` would run past a full buffer.
    const field: [8]u8 = "ab\x00\x00\x00\x00\x00\x00".*;
    try std.testing.expectEqualStrings("ab", std.mem.sliceTo(&field, 0));

    try std.testing.expectEqual(5, try callWithName(std.testing.allocator, "world"));
}
```

### ZS-INTEROP-11 [M] Convert a C integer to a fixed-width Zig integer with a checked cast

`c_int`, `c_long`, `c_char` and friends appear in the exported signature and nowhere inside. Convert
with `std.math.cast(T, x) orelse return .invalid_argument` — never a bare `@intCast`, which is
illegal behavior on overflow, and never `@truncate`, which is silent. Where you genuinely mean "the
byte", write `u8` and `@bitCast`, not `c_char`. Their widths, measured on 0.17.0 by compiling the
same source for eight targets:

| Target | `c_int` | `c_long` | `c_char` |
|---|---|---|---|
| `x86_64-linux-gnu` | 32 | **64** | signed |
| `aarch64-linux-gnu` | 32 | **64** | **unsigned** |
| `aarch64-macos` | 32 | **64** | signed |
| `x86_64-windows-gnu` | 32 | **32** | signed |
| `arm-linux-gnueabihf` | 32 | **32** | **unsigned** |
| `wasm32-wasi` | 32 | **32** | signed |
| `avr-freestanding` | **16** | **32** | signed |
| `msp430-freestanding` | **16** | **32** | **unsigned** |

So `c_char` arithmetic that assumed `i8` inverts its sign comparisons on ARM Linux, and `c_int` is
not even 32 bits on the 16-bit microcontroller targets.

**Why:** ZS-DATA-02 makes this argument about `usize`, and the C types are worse: their width is set
by the *platform ABI*, so a `c_long` that always fit starts truncating the day someone builds for
Windows. `std.math.cast` makes the out-of-range case a branch you write.

**Check:** an `@intCast` or `@truncate` whose operand is declared `c_int`, `c_uint`, `c_long`,
`c_ulong`, `c_short`, `c_longlong`, or `c_char` — ZS-DATA-10's check, at the C boundary. Also
arithmetic or a comparison performed directly on a `c_*`-typed value below the boundary module — the
conversion should already have happened.

```zig
// verified
const std = @import("std");

const Status = enum(c_int) { ok = 0, invalid_argument = 1 };

/// `c_long` is 64 bits on LP64, 32 on Windows and 32-bit ARM; `c_int` is 32
/// almost everywhere but 16 on AVR. Convert once, checked, at the boundary.
export fn zs_set_capacity(capacity: c_long, out: ?*u32) Status {
    const out_ptr = out orelse return .invalid_argument;
    const capacity_u32 = std.math.cast(u32, capacity) orelse return .invalid_argument;
    out_ptr.* = capacity_u32;
    return .ok;
}

test "checked narrowing rejects what @intCast would corrupt" {
    var capacity: u32 = 0;
    try std.testing.expectEqual(Status.ok, zs_set_capacity(4096, &capacity));
    try std.testing.expectEqual(4096, capacity);
    try std.testing.expectEqual(Status.invalid_argument, zs_set_capacity(-1, &capacity));
    try std.testing.expectEqual(4096, capacity); // Unchanged on failure.
}
```

---

## Structs, callbacks, and ownership

### ZS-INTEROP-12 [M] A C callback cannot capture; all state travels through `userdata`

A function passed to C is a top-level or namespaced function with `callconv(.c)`, never a closure
and never a nested function that refers to an enclosing local. State reaches it through the
`void *userdata` parameter the C API provides, and comes back with
`@ptrCast(@alignCast(userdata orelse return))`. Both casts are required: `@ptrCast` changes the
pointee type, and `@alignCast` restores the alignment that `*anyopaque` (align 1) erased, which
`@ptrCast` alone cannot add — without it the recovered pointer is a compile error. If the C API has
no `userdata` parameter, it cannot be driven by more than one Zig object at a time — say so at the
wrapper, and use a file-scope singleton deliberately rather than by accident.

**Why:** Zig has no closures at all; a function value is just a pointer to code, with no environment
word to hold captures. That is why the `void *` exists in every well-designed C callback API, and
why an API without one is genuinely limited rather than merely awkward.

**Check:** a `callconv(.c)` function declared inside another function body, or one whose body names
a file-scope `var` holding per-instance state instead of reading its `userdata` parameter. Also a
call into C that passes `null` for `userdata` while the callback assumes it is present.

```zig
// verified — driven by a real C caller:
//   void zs_c_each(void (*cb)(uint32_t, void *), void *ud) {
//       for (uint32_t i = 1; i <= 3; i++) cb(i, ud);
//   }
const std = @import("std");

extern "c" fn zs_c_each(
    callback: *const fn (value: u32, userdata: ?*anyopaque) callconv(.c) void,
    userdata: ?*anyopaque,
) void;

const Sum = struct {
    total: u64 = 0,

    /// A `callconv(.c)` function pointer cannot capture, so all state travels
    /// through `userdata` and comes back with `@ptrCast` + `@alignCast`.
    fn onValue(value: u32, userdata: ?*anyopaque) callconv(.c) void {
        const sum: *Sum = @ptrCast(@alignCast(userdata orelse return));
        sum.total += value;
    }
};

test "C calls back into Zig and userdata survives the round trip" {
    var sum: Sum = .{};
    zs_c_each(&Sum.onValue, &sum);
    try std.testing.expectEqual(6, sum.total);
}
```

### ZS-INTEROP-13 [M] A callback parks its failure in `userdata` for the caller to check

A `callconv(.c)` callback cannot return an error (ZS-INTEROP-01) and must not `try` past the C
frame. Give the userdata struct a `failure: ?SomeError = null` field, `catch` into it, make
subsequent invocations a no-op, and check it once the C function has returned. The two tempting
alternatives are both wrong: `catch unreachable` violates ZS-ERR-01 because allocation failure is an
operating condition, and `@panic` unwinds through C frames that may hold locks or partially built
state.

**Why:** the callback runs on a C stack frame that knows nothing about error unions or `errdefer`.
Parking the error keeps C's iteration contract intact — a `void` return every time — while making
the failure observable once, at a Zig call site that can `errdefer`.

**Check:** `try`, `catch unreachable`, or `@panic` inside a `callconv(.c)` function body. Then, for
each such callback whose body can allocate or otherwise fail: a `failure: ?…` field on its userdata
struct, an early `return` when that field is already set, and a read of it at the Zig call site
immediately after the C function returns. A missing one of those three is the finding.

```zig
// verified — same `zs_c_each` C function as ZS-INTEROP-12
const std = @import("std");

extern "c" fn zs_c_each(
    callback: *const fn (value: u32, userdata: ?*anyopaque) callconv(.c) void,
    userdata: ?*anyopaque,
) void;

const Collect = struct {
    gpa: std.mem.Allocator,
    values: std.ArrayList(u32) = .empty,
    failure: ?std.mem.Allocator.Error = null,

    fn onValue(value: u32, userdata: ?*anyopaque) callconv(.c) void {
        const c: *Collect = @ptrCast(@alignCast(userdata orelse return));
        if (c.failure != null) return; // Already failed; stay quiet.
        c.values.append(c.gpa, value) catch |err| {
            c.failure = err;
        };
    }
};

fn collectAll(gpa: std.mem.Allocator) ![]u32 {
    var collect: Collect = .{ .gpa = gpa };
    defer collect.values.deinit(gpa);

    zs_c_each(&Collect.onValue, &collect);
    if (collect.failure) |err| return err;

    return collect.values.toOwnedSlice(gpa);
}

test "callback failure surfaces after the C call returns" {
    const gpa = std.testing.allocator;

    const values = try collectAll(gpa);
    defer gpa.free(values);

    try std.testing.expectEqualSlices(u32, &.{ 1, 2, 3 }, values);
}
```

### ZS-INTEROP-14 [M] Whoever calls `free` picks the allocator: `std.heap.c_allocator` if C does

Decide, per function, which side owns each buffer, and write it in the doc comment (ZS-MEM-09). If C
will call `free()` on it, allocate it with `std.heap.c_allocator`. If your library will free it,
export a `zs_release`-style function and use any allocator you like. Never hand C a pointer from a
`SafeAllocator`, arena, `FixedBufferAllocator`, or `smp_allocator` and expect `free()` to work. The
export layer is a library's root, the one place ZS-MEM-02 lets a library name a concrete allocator,
so `std.heap.c_allocator` there is the exception that rule makes, not a breach of it.

`std.heap.c_allocator` is the one that forwards to `malloc`/`realloc`/`free`. Its docs note that
large requested alignments may need larger buffers than a simple `malloc` call, so the
`free()`-compatibility guarantee holds for naturally-aligned allocations — `u8` buffers and C
strings — which is what crosses the boundary anyway. It is a `@compileError` without `link_libc`, so
this pattern and freestanding are mutually exclusive by construction. The library-owned form is
strictly safer, because it survives a caller who links a different libc.

**Why:** `free()` is not a generic deallocator; it is libc's, and it requires a pointer that libc's
`malloc` produced. Every other allocator in ZS-MEM-03 keeps bookkeeping libc cannot see: an arena
frees nothing per object, and `SafeAllocator` trails each block with a checksummed footer.

**Check:** a pointer returned to C from `gpa.print`, `dupeSentinel`, or `gpa.alloc` where the
allocator is not `std.heap.c_allocator` and the module exports no matching release function. Also an
exported release function taking a bare `[*]u8` or `?*anyopaque` rather than a pointer *and* a
length, and any exported function whose doc comment does not say which side frees the buffer it
returns.

```zig
// verified
const std = @import("std");

/// Buffer the C caller releases with `free()`. It must come from libc's heap,
/// so allocate through `std.heap.c_allocator` — never a `SafeAllocator`,
/// arena, or `smp_allocator`, whose blocks `free()` does not understand.
/// Caller owns the returned pointer; release it with `free()`.
export fn zs_render(value: u64) ?[*:0]u8 {
    const gpa = std.heap.c_allocator;
    return (gpa.printSentinel("{d}", .{value}, 0) catch return null).ptr;
}

/// Preferred: the library owns the buffer and exports the matching release
/// function, so any Zig allocator is fine — the same one frees it.
const Handle = extern struct { ptr: [*]u8, len: usize };

var handle_gpa: std.mem.Allocator = undefined;

export fn zs_render_owned(value: u64, out: ?*Handle) bool {
    const out_ptr = out orelse return false;
    const buffer = handle_gpa.print("{d}", .{value}) catch return false;
    out_ptr.* = .{ .ptr = buffer.ptr, .len = buffer.len };
    return true;
}

export fn zs_release(handle: Handle) void {
    handle_gpa.free(handle.ptr[0..handle.len]);
}

test "library-owned buffer round trip" {
    handle_gpa = std.testing.allocator;

    var handle: Handle = undefined;
    try std.testing.expect(zs_render_owned(1234, &handle));
    defer zs_release(handle);

    try std.testing.expectEqualStrings("1234", handle.ptr[0..handle.len]);
}

test "libc-owned buffer round trip" {
    const rendered = zs_render(99) orelse return error.OutOfMemory;
    defer std.c.free(rendered);

    try std.testing.expectEqualStrings("99", std.mem.span(rendered));
}
```

Note `zs_release` takes the `Handle` back rather than a bare pointer, because ZS-MEM-14 requires
freeing exactly the slice that was allocated — C must hand the length back with the pointer.

---

## Getting the declarations

### ZS-INTEROP-15 [S] Hand-write `extern` declarations; use `b.addTranslateC` for large headers

**Default to hand-writing.** Declare the dozen functions and handful of structs your wrapper uses,
in the boundary module of ZS-INTEROP-08. Switch to `b.addTranslateC` when the surface is large
enough that hand-transcription is the bigger risk: a generated header, a vendored library with
hundreds of entry points, or one whose ABI changes between releases you track. `@cImport` is gone
(`error: invalid builtin function: '@cImport'`), so translation happens only in `build.zig`.
`b.addTranslateC` works there; the 0.17 release notes deprecate it in favour of the translate-c
package (`b.dependency("translate_c", …)` and its `Translator`), the same implementation with more
options, though the source does not mark it deprecated yet. That package is a dependency like any
other (ZS-BUILD-33).

`zig translate-c` emits `[*c]` for every pointer, because a C `T *` really is nullable and
unbounded, so its output is the least safe legal translation by construction. It is also
target-specific: the same header produces different integer types per target, so the output is a
build artifact, not source. Build time no longer weighs against it: on 0.17.0 a cold run with empty
caches takes 0.09 s, and the build step caches its output in `.zig-cache`.

If you do use it: declare include paths and macros once in `build.zig`, rather than at every import
site, import the result as a module, and pin the parts you depend on with `addCheckFile` so a
toolchain upgrade that changes the translation fails the build instead of silently changing a type.

**Why:** hand-written declarations carry this chapter's rules — `?[*:0]const u8` for `[*c]const u8`,
`enum(c_int)` for `c_int`, who frees what — and translate-c cannot infer any of it. But two hundred
transcribed functions will hold a wrong parameter order that compiles and corrupts memory.

**Check:** any `@cImport(` site — a compile error, so it marks code not yet ported. A
`b.addTranslateC` step with no `addCheckFile` pinning the declarations the code depends on, and the
include paths or `-D` macros for one header declared in more than one place. And, from the other
side, a hand-written `extern` block that has grown past a few dozen declarations, or one whose
parameter order was transcribed rather than derived from the header in the same diff.

```zig
// fragment — inside build.zig's `build(b)`; this exact form configures cleanly
const translate_c = b.addTranslateC(.{
    .root_source_file = b.path("vendor/shim.h"),
    .target = target,
    .optimize = optimize,
    // .link_libc defaults to true; set it false for a freestanding target.
});
translate_c.addIncludePath(b.path("vendor/include"));
translate_c.defineCMacro("SHIM_STATIC", "1");
boundary_mod.addImport("c", translate_c.createModule());

// Pin the shape you rely on; a changed translation then fails the build.
const check = translate_c.addCheckFile(&.{"pub extern fn zs_c_add"});
b.getInstallStep().dependOn(&check.step);
```

Either way, the translated or transcribed declarations are still C types, so they stay behind the
boundary module and get converted per ZS-INTEROP-09 through ZS-INTEROP-11.

---

## Targets

### ZS-INTEROP-16 [M] On freestanding there is no `std.process.Init` — export your entry points instead

**This rule is an explicit exemption from ZS-MEM-01 and ZS-CONC-01.** Both are `[M]` and both say to
take `std.process.Init` in `main` and use the `gpa`, `arena`, and `io` it hands you. On
`*-freestanding` there is no such thing, and those two rules do not apply. The freestanding entry
point is one or more `export fn` symbols: `_start` (or whatever the reset vector names) for bare
metal, and the exported API surface for a WebAssembly module. Allocation comes from a
`FixedBufferAllocator` over a static array (ZS-MEM-21), or from `std.heap.wasm_allocator` on wasm.
There is also no usable `Io`: `Io.Threaded`, the only backend std ships that would apply, does not
compile for either freestanding target, so no `Io.Dir`, `Io.File`, `io.async`, or `io.sleep`.

A `main` written there anyway fails two ways on 0.17.0:

- On `thumb-freestanding-eabi`, `pub fn main(init: std.process.Init) !void` compiles but is dead
  code — the linker reports `cannot find entry symbol _start; not setting start address`, because no
  start code was emitted to call it.
- On `wasm32-freestanding` it does not even compile: `std.start` tries to build the `Io.Threaded` it
  would hand you and fails inside it
  (`error: struct 'posix.system__struct_…' has no member named 'getrandom'`).

**Why:** `std.process.Init` is populated by `std/start.zig`, which runs only when there *is* a
start, so on bare metal a `main` silently yields a binary that never runs your code. Firmware is the
`[M!]` audience of the rest of this standard, so the exemption is stated rather than left implicit.

**Check:** in any file reachable from a `*-freestanding` build: `pub fn main(`, `std.process.Init`,
`init.io`, `Io.Dir`, `Io.File`, `io.async`, `io.sleep`, or `Io.Threaded`. Conversely, a freestanding
executable whose root file declares no `export fn` entry symbol and no `mod.export_symbol_names` —
that binary links and runs nothing.

```zig
// fragment — zig build-obj -target thumb-freestanding-eabi -mcpu cortex_m4
const builtin = @import("builtin");
const std = @import("std");
const assert = std.debug.assert;

extern fn zs_c_add(a: u32, b: u32) u32; // From a .c file linked into this image.

export fn zs_add(a: u32, b: u32) u32 {
    return zs_c_add(a, b);
}

/// Bare metal: the reset vector calls `_start`. There is no `main`, no
/// `std.process.Init`, no `Io`.
export fn _start() callconv(.c) noreturn {
    _ = zs_add(1, 2);
    while (true) @breakpoint();
}

comptime {
    assert(builtin.target.os.tag == .freestanding);
}
```

### ZS-INTEROP-17 [M] Freestanding supplies its own panic handler, as a namespace

Declare `pub const panic = std.debug.FullPanic(myPanicFn);` at the root of a freestanding program,
where `myPanicFn` has the signature `fn (msg: []const u8, first_trace_address: ?usize) noreturn`.
`panic` is a **namespace**, not a function; `std.lang.panic` still accepts the older
`pub fn panic(msg, trace, ra) noreturn` form but marks it "Deprecated; make `panic` a namespace
instead".

Do not use `std.debug.simple_panic` there: in 0.17.0 it **does not compile** on
`wasm32-freestanding` or `thumb-freestanding-eabi` once any safety check can reach it (it reaches
`Io.Threaded`), so `FullPanic` with your own function is the portable choice, not just the better
one. `std.debug.no_panic` compiles for both freestanding targets and is the deliberate "smallest
possible" option.

**Why:** on `.freestanding` the entire body of `std.debug.defaultPanic` is `@trap()`, so a safety
failure on a microcontroller is a halt with no message, no UART byte, and no watchdog reset. Your
handler is where a real product writes a fault record to flash and resets.

**Check:** a freestanding root source file with no `pub const panic =` declaration at all, one
written as `pub fn panic(` (the deprecated function form), or one set to `std.debug.simple_panic`,
which does not compile on a freestanding target.

```zig
// verified — builds for wasm32-freestanding and thumb-freestanding-eabi
const std = @import("std");

pub const panic = std.debug.FullPanic(trap);

fn trap(msg: []const u8, first_trace_address: ?usize) noreturn {
    _ = msg;
    _ = first_trace_address;
    // A real product records the fault and resets the watchdog here.
    @trap();
}

export fn zs_x() u32 {
    return 1;
}
```

### ZS-INTEROP-18 [M] Branch on `builtin.target` at comptime; `@compileError` the unhandled target

Conditional compilation reads `builtin.target`, `builtin.target.os.tag`, `builtin.target.cpu.arch`,
`builtin.target.abi`, `builtin.link_libc`, and `builtin.single_threaded` — not a hand-rolled
`-Dplatform` string option, which is not known when the target is resolved and drifts out of sync
with `-Dtarget`. Use a `switch` whose `else` is `@compileError`, so a new target is a build failure
rather than a wrong default. Per-target `extern` declarations branch the same way, which keeps the
boundary module of ZS-INTEROP-08 to one file.

**Why:** these are `comptime`-known, so the untaken arm is never semantically analysed: one file can
hold a `linux` path calling `std.posix` and a `windows` path calling Win32. A silent fallback gives
whoever first cross-compiles to a new platform wrong behavior, not a message naming the file.

**Check:** a `switch` on `builtin.target.os.tag`, `builtin.target.cpu.arch`, or `builtin.target.abi`
whose `else` arm produces a value rather than `@compileError`. Also a `b.option` named `platform`,
`os`, `arch`, or similar in `build.zig`, and any `if (builtin.target.os.tag == ...)` chain (or one
on the deprecated `builtin.os.tag`) with no final `else` that fails.

```zig
// verified — compiles for x86_64-linux, aarch64-macos, and x86_64-windows; wasm32-wasi stops
// at `error: no control endpoint on wasi`
const builtin = @import("builtin");
const std = @import("std");
const assert = std.debug.assert;

/// Branch on `builtin.target`, not on a hand-rolled `-Dplatform` option, and
/// branch at `comptime` so the dead arm is never analysed.
const control_endpoint: []const u8 = switch (builtin.target.os.tag) {
    .linux, .macos, .freebsd, .netbsd, .openbsd => "/var/run/zs/control.sock",
    .windows => "\\\\.\\pipe\\zs-control",
    else => @compileError("no control endpoint on " ++ @tagName(builtin.target.os.tag)),
};

comptime {
    assert(control_endpoint.len > 0);
}
```

A value std already derives per target is std's to give: the page size is `std.heap.page_size_min`,
`page_size_max`, and `pageSize()`, which already `@compileError` a target whose page size is
unknown.

### ZS-INTEROP-19 [M] `-fsingle-threaded` removes task concurrency and cancellation

A single-threaded build is not "the same program with one thread". Behavior on 0.17.0:

| Construct | Under `-fsingle-threaded` |
|---|---|
| `io.async(f, args)` | Compiles and returns a `Future`, but **runs `f` eagerly and inline**. Nothing overlaps. |
| `io.concurrent(f, args)` | Returns `error.ConcurrencyUnavailable`. |
| `future.cancel(io)` | A no-op returning the already-computed result: the work already happened. |
| `std.heap.smp_allocator` | Build failure: a `comptime assert(!builtin.single_threaded)`, reported as `error: reached unreachable code`. |
| `std.heap.wasm_allocator` | The **reverse**: `@compileError("unimplemented")` *unless* single-threaded. |

If a module requires concurrency, say so in its doc comment and call `io.concurrent`, whose
`error.ConcurrencyUnavailable` is the honest failure, rather than `io.async`, which will quietly
serialise. Wasm and freestanding builds are single-threaded, which is why the two allocator rows
point in opposite directions.

**Why:** code written against `Io` still compiles and still produces correct results — the point of
the colorless design — but a design whose *correctness* needs two tasks to overlap will deadlock or
hang, and a cancellation-based timeout will not fire.

**Check:** ZS-CONC-22's finding, an `io.async` whose tasks must overlap to make progress, in a
module that any build target may compile `-fsingle-threaded`, where it stops being latent. Also
`std.heap.smp_allocator` in a module built for wasm or freestanding, and `std.heap.wasm_allocator`
in one that is not.

```zig
// verified — builds with and without -fsingle-threaded
const std = @import("std");

fn double(x: u32) u32 {
    return x * 2;
}

test "what -fsingle-threaded does to Io" {
    const io = std.testing.io;

    // `async` still compiles and still returns a `Future`, but under
    // `-fsingle-threaded` the task runs eagerly, inline, before `async`
    // returns. Nothing overlaps.
    var task = io.async(double, .{21});
    try std.testing.expectEqual(42, task.await(io));

    // `cancel` cannot help: the work already happened.
    var done = io.async(double, .{21});
    try std.testing.expectEqual(42, done.cancel(io));

    // `concurrent` demands real overlap, so it fails outright.
    if (io.concurrent(double, .{21})) |future| {
        var f = future;
        try std.testing.expectEqual(42, f.await(io));
    } else |err| {
        try std.testing.expectEqual(error.ConcurrencyUnavailable, err);
    }
}
```

### ZS-INTEROP-20 [M] On WASI, resolve directories through `init.preopens`, never `Io.Dir.cwd()`

A WASI program has no ambient filesystem. Take the directory the host granted you by name from
`init.preopens`, and fail with a named error if it is absent. `std.process.Init` carries
`preopens: Preopens`, whose `get(name) ?Resource` returns
`union(enum) { file: Io.File, dir: Io.Dir }` — a real capability lookup with a null case you have to
handle. On non-WASI targets the same call still resolves `"stdin"`, `"stdout"`, and `"stderr"`, so
the code is portable.

**Why:** `Io.Dir.cwd()` on WASI is a guess — handle 3, on the expectation that the first preopen is
the working directory. If the host granted its preopens in another order, or none, that handle is
some other directory or nothing, and every path you open is silently wrong.

**Check:** `Io.Dir.cwd()` in any file a `build.zig` compiles for `wasm32-wasi`. Also an
`init.preopens.get(` whose result is unwrapped with `.?` or `orelse undefined` rather than
`orelse return error.<Named>`, and a `switch` over the returned `Resource` that ignores the `.file`
arm.

```zig
// verified — zig build-exe -target wasm32-wasi
const std = @import("std");
const Io = std.Io;

/// WASI has no ambient filesystem: the host grants directories as *preopens*,
/// and `Io.Dir.cwd()` there is only a guess (`.{ .handle = 3 }`). Resolve the
/// root you were actually granted, by name, and fail loudly if it is absent.
pub fn main(init: std.process.Init) !void {
    const io = init.io;

    const root: Io.Dir = switch (init.preopens.get("/data") orelse return error.NoDataPreopen) {
        .dir => |d| d,
        .file => return error.NotADirectory,
    };

    var file = try root.openFile(io, "config.txt", .{});
    defer file.close(io);
}
```

### ZS-INTEROP-21 [M] Derive `link_libc`, `single_threaded`, and `entry` from the resolved target

Compute them from `target.result` rather than hard-coding. `link_libc` is true only for hosted
targets. Leave `single_threaded` **unset** unless you mean it. `entry` is `.disabled` for a wasm
library and `.{ .symbol_name = "_start" }` (or your reset symbol) for bare metal, and exported
symbols go in `mod.export_symbol_names`. `link_libc` and `single_threaded` live on the `Module`, not
the artifact; `entry` is a property of the executable (ZS-BUILD-05).

Each of the three has a failure mode on 0.17.0:

- `link_libc = true` on freestanding fails the build outright
  (`unable to provide libc for target "thumb-freestanding-eabi"`), and leaving it false under an
  `extern "c"` declaration fails with `dependency on libc must be explicitly specified`
  (ZS-INTEROP-06), which is why the bare `extern fn` is the freestanding spelling.
- Forcing `single_threaded = false` on `wasm32-wasi` fails inside `Io.Threaded` with
  `comptime assert(builtin.cpu.has(.wasm, .atomics))`. Setting it to `true` is fine and is what
  freestanding gets anyway.
- Leaving `entry` at `.default` for a freestanding ELF target makes the LLD warning
  `cannot find entry symbol _start` into a **build failure**, because `zig build` treats unexpected
  linker stderr as an error.

**Why:** each of the three is right for some targets and a build failure on others, so a hard-coded
value breaks the first cross-compile. For `single_threaded` the default is already right, and
overriding it is what breaks.

**Check:** in `build.zig`: a literal `.link_libc = true` not derived from `target.result`, any
`.single_threaded = ` assignment at all, and an artifact built for a freestanding or wasm target
whose `entry` is never set. Also `link_libc` or `single_threaded` set on the artifact rather than
the module.

```zig
// verified — `zig build` succeeds for the host, wasm32-wasi
// wasm32-freestanding, and thumb-freestanding-eabi
const std = @import("std");

pub fn build(b: *std.Build) void {
    const target = b.standardTargetOptions(.{});
    const optimize = b.standardOptimizeOption(.{});

    const hosted = target.result.os.tag != .freestanding;

    const mod = b.createModule(.{
        .root_source_file = b.path(if (hosted) "src/main.zig" else "src/firmware.zig"),
        .target = target,
        .optimize = optimize,
        // Never unconditionally: freestanding has no libc, and
        // `std.heap.c_allocator` is a `@compileError` without it.
        .link_libc = hosted,
        // Leave `single_threaded` unset. Forcing `false` on wasm32 without the
        // `atomics` CPU feature fails inside `Io.Threaded`.
    });
    mod.addIncludePath(b.path("vendor"));
    mod.addCSourceFile(.{ .file = b.path("vendor/shim.c"), .flags = &.{"-std=c11"} });

    if (hosted) {
        b.installArtifact(b.addExecutable(.{ .name = "capidemo", .root_module = mod }));
    } else {
        // No entry point and no `main`: the host calls the exported symbols.
        mod.export_symbol_names = &.{"zs_add"};
        const firmware = b.addExecutable(.{ .name = "capidemo", .root_module = mod });
        firmware.entry = if (target.result.cpu.arch.isWasm()) .disabled else .{
            .symbol_name = "_start",
        };
        b.installArtifact(firmware);
    }
}
```

---

## Boundary review checklist

1. Does any exported function return `!T`, or an error smuggled as an integer? (ZS-INTEROP-01)
2. Is every pointer parameter null-checked and every length bounded before use? (ZS-INTEROP-02)
3. Does `[*c]` appear anywhere but an exported parameter list? (ZS-INTEROP-09)
4. Is `std.mem.span` being applied to a fixed-size NUL-padded C array where `sliceTo` belongs?
   (ZS-INTEROP-10)
5. Any `@intCast`/`@truncate` on a `c_int`/`c_long`/`c_char` instead of `std.math.cast`?
   (ZS-INTEROP-11)
6. Does every struct shared with C have fixed-width fields and `comptime` layout assertions?
   (ZS-DATA-02, ZS-ASSERT-19)
7. Does any callback `try`, `catch unreachable`, or `@panic` across the C frame? (ZS-INTEROP-13)
8. For each buffer that crosses: which side frees it, is it written down, and does the allocator
   match? (ZS-INTEROP-14)
9. Does the code assume `std.process.Init`, `Io`, or a default panic handler on a target that has
   none? (ZS-INTEROP-16, ZS-INTEROP-17)
10. Does any design depend on two tasks overlapping in a build that may be `-fsingle-threaded`?
    (ZS-INTEROP-19)

## Decided by tools

The compiler rejects each of these on its own; no setting turns one off.

| Tool | Lint | Level | Forbids |
|---|---|---|---|
| zig | `… not allowed in function with calling convention …` | error | a type with no C ABI in an `export` or `callconv(.c)` signature |
| zig | `union 'lang.CallingConvention' has no member named '…'` | error | a calling convention the union does not have: `.C`, `.Naked`, `.Stdcall` |
