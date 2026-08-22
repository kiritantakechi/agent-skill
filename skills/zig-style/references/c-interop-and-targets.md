# C interop and cross-target builds

Scope: everything that happens where Zig stops. Exporting Zig functions to C (`export fn`,
`@export`, `callconv(.c)`); declaring C functions in Zig (`extern "c" fn`, `@extern`); the types
that may legally cross (and the fact that **error sets may not**); `[*c]` pointers, NUL-terminated
strings, and C integer types; struct layout and callbacks with `void *userdata`; who owns and frees
memory that crosses. Then the target axis: `builtin.target` branching, `-fsingle-threaded`,
freestanding and WebAssembly — including the places where the rest of this standard **does not
apply** because there is no operating system to apply it to.

Layout rules for the types themselves live in the types chapter (ZS-TYPE-19 through ZS-TYPE-22,
ZS-TYPE-32); allocator selection and ownership vocabulary live in the memory chapter; wiring
`link_libc`, C sources, and `addTranslateC` into a build lives in the build chapter (ZS-BUILD-06,
ZS-BUILD-36). This chapter cites those rather than repeating them, and adds only what is specific
to the boundary.

Every example assumes a file opening with `const std = @import("std");`,
`const builtin = @import("builtin");` and `const assert = std.debug.assert;` — assertions are called
bare, per ZS-ASRT-01.

Several examples here build for `x86_64-linux-gnu`, `x86_64-windows-gnu`, `arm-linux-gnueabihf`,
`wasm32-wasi`, `wasm32-freestanding`, and `thumb-freestanding-eabi` as well as the host; where the
target set matters to the rule, the block's marker names it.
## Contents

- **The boundary contract**
  - ZS-CAPI-01 [M] A Zig error set cannot cross a C boundary — return a status code
  - ZS-CAPI-02 [M] Only C-ABI types may appear in a `callconv(.c)` signature
  - ZS-CAPI-03 [M!] Validate everything C hands you; do not assert it
- **Exporting Zig to C**
  - ZS-CAPI-04 [M] `export fn` when the Zig name is the symbol; `@export(&f, …)` when it is not
  - ZS-CAPI-05 [M] Spell the calling convention `.c` — `CallingConvention` is a union in 0.16
  - ZS-CAPI-06 [S] Prefix every exported symbol with the library name
- **Calling C from Zig**
  - ZS-CAPI-07 [M] `extern "c" fn` for libc; bare `extern fn` for objects you link yourself
  - ZS-CAPI-08 [M] Use `@extern` only for what a declaration cannot express
  - ZS-CAPI-09 [M] Confine C types to one boundary module
- **Pointers, strings, and integers**
  - ZS-CAPI-10 [M] A `[*c]` pointer dies at the first Zig function; convert it to a slice or `?*T`
  - ZS-CAPI-11 [M] `span` in, `[]const u8` inside, `dupeZ` out, `sliceTo` for fixed arrays
  - ZS-CAPI-12 [M] Convert a C integer to a fixed-width Zig integer with a checked cast
- **Structs, callbacks, and ownership**
  - ZS-CAPI-13 [M] Give a C-shared struct fixed-width fields, so its layout assertion is portable
  - ZS-CAPI-14 [M] A C callback cannot capture; all state travels through `userdata`
  - ZS-CAPI-15 [M] A callback parks its failure in `userdata` for the caller to check
  - ZS-CAPI-16 [M] Whoever calls `free` picks the allocator: `std.heap.c_allocator` if C does
- **Getting the declarations**
  - ZS-CAPI-17 [S] Hand-write `extern` declarations; use `b.addTranslateC` for large headers
- **Targets**
  - ZS-CAPI-18 [M] On freestanding there is no `std.process.Init` — export your entry points instead
  - ZS-CAPI-19 [M] Freestanding supplies its own panic handler, as a namespace
  - ZS-CAPI-20 [M] Branch on `builtin.target` at comptime; `@compileError` the unhandled target
  - ZS-CAPI-21 [M] `-fsingle-threaded` removes task concurrency and cancellation
  - ZS-CAPI-22 [M] On WASI, resolve directories through `init.preopens`, never `Io.Dir.cwd()`
  - ZS-CAPI-23 [M] Derive `link_libc`, `single_threaded`, and `entry` from the resolved target
- **Boundary review checklist**

---

## The boundary contract

### ZS-CAPI-01 [M] A Zig error set cannot cross a C boundary — return a status code
An exported function returns either a status `enum(c_int)` or a `bool`, never `!T`. When it also
produces a value, the value leaves through a pointer parameter that is written **only** on success.
This is the single most important rule in the chapter: a wrapper that tries to return `!T` to C is
not a style mistake, it is a category error.

**Why:** the compiler rejects it outright —
`error: return type '!u32' not allowed in function with calling convention 'aarch64_aapcs_darwin'`.
An error union is a Zig-only tagged representation with no C spelling, and the error *set* is a
compile-time-assigned integer whose numbering is not stable across builds, so even smuggling it out
as an `int` would export a number that means something different next compile. Converting once, in
one `fromError` switch, is also what makes the error vocabulary the C header documents finite and
reviewable; the `switch` is exhaustive, so a new Zig error fails the build until it is given a
status.

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
        acc = std.math.mul(u32, acc, 10) catch return error.Overflow;
        acc = std.math.add(u32, acc, ch - '0') catch return error.Overflow;
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
// does-not-compile — BAD
// error: return type '!u32' not allowed in function with calling convention '...'
export fn zs_parse(text: [*:0]const u8) !u32 {
    _ = text;
    return error.Invalid;
}
```

A `bool` return is the right shape when there is exactly one failure mode and the C caller cannot
act on a reason — see ZS-CORE-24 on reducing dimensionality at the call site. Anything richer gets
the enum.

### ZS-CAPI-02 [M] Only C-ABI types may appear in a `callconv(.c)` signature
The legal set is: integers and floats, `bool`, `?*T` and other pointers, `[*]T`/`[*:0]T`/`[*c]T`,
`extern struct`, `packed struct(uN)`, and `enum` with an **explicit** tag type. Everything else is
rejected. A slice becomes a pointer and a length as two separate parameters.

**Why:** each rejection is the compiler refusing to invent a layout that C has no word for, and it
says so in the note. At 0.16.0:

| Written | Compiler note |
|---|---|
| `[]const u8` | `slices have no guaranteed in-memory representation` |
| `struct { x: u32 }` | `struct with automatic layout has no guaranteed in-memory representation` |
| `union(enum) { … }` | `union with automatic layout has no guaranteed in-memory representation` |
| `?u32` | `non-pointer optionals have no guaranteed in-memory representation` |
| `enum { x, y }` | `integer tag type of enum is inferred` (this is ZS-TYPE-20) |
| `[4]u8` | `arrays are not allowed as a parameter type` |
| `!u32` | rejected — see ZS-CAPI-01 |

Note that `?*T` **is** legal and is the correct way to accept a nullable C pointer: the optional is
the null pointer, at no cost.

**Check:** in the parameter list or return type of any `export fn` / `callconv(.c)` function: a `[]`
slice, an `enum` with no explicit tag type, a `?` on anything that is not a pointer, an array type
`[N]T`, or a struct/union type not declared `extern` or `packed`. Each maps to one row of the table
above.

```zig
// verified
const R = extern struct { a: u32, b: u32 };
const P = packed struct(u32) { a: u16, b: u16 };
const E = enum(c_int) { x = 0, y = 1 };

export fn f1(r: R) u32 {
    return r.a;
}
export fn f2(p: P) u16 {
    return p.a;
}
export fn f3(e: E) c_int {
    return @intFromEnum(e);
}
export fn f4(p: ?*u32) u32 {
    return if (p) |q| q.* else 0;
}
export fn f5(s: [*:0]const u8) u8 {
    return s[0];
}
```

### ZS-CAPI-03 [M!] Validate everything C hands you; do not assert it
At an exported entry point, check pointers for null, lengths against the buffer you were also given,
and integers against the enum or range they claim to be — with `if` and an error status, not with
`assert`.

**Trigger criteria — treat as `[M]`** when any of the SKILL.md high-reliability conditions hold, and
additionally whenever **the C side is not built from this repository**: a plugin ABI, a shared
library with third-party consumers, an FFI surface for a scripting runtime, or anything reachable
from a network-facing process. In all of those the C caller is outside your trust boundary even if
it is friendly, because it is compiled separately and can go stale.

***Relaxed form:*** always null-check pointers and always bound lengths — those two are never
optional, because in `ReleaseFast` a violated assert is not a crash but a memory-safety bug (see
ZS-CORE-10). Exhaustive enum and range validation may be skipped for a C shim that lives in the
same repository and is compiled by the same `build.zig`.

**Why:** this is ZS-CORE-08's boundary clause, applied to the one boundary where it bites hardest.
An `assert` on data from another compilation unit is a remote denial of service in `ReleaseSafe`
and illegal behavior in `ReleaseFast`. `@enumFromInt` on an out-of-range value is illegal behavior
in every mode, not a panic you can catch — so the check has to happen before the cast, which is what
`std.enums.fromInt` is for. (0.16 note: `std.meta.intToEnum` no longer exists;
`std.enums.fromInt(E, integer) ?E` replaces it and accepts any integer type.)

**Check:** in the body of an `export fn`: any `assert(`, any `@enumFromInt` on a parameter with no
preceding `std.enums.fromInt` or explicit range test, and any pointer parameter reached with `.?`,
`.*`, or `[0..len]` before an `orelse` that handles null. A length parameter used to slice without
first being compared against the buffer bound is the same defect.

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

    const path_slice = std.mem.sliceTo(path_ptr, 0);
    if (path_slice.len > path_len_max) return .invalid_argument;
    if (path_slice.len == 0) return .invalid_argument;

    const mode = std.enums.fromInt(Mode, mode_raw) orelse return .invalid_argument;

    out_ptr.* = @intFromEnum(mode);
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

### ZS-CAPI-04 [M] `export fn` when the Zig name is the symbol; `@export(&f, …)` when it is not
`export fn foo` gives the symbol the target's C calling convention automatically and names it `foo`.
When the exported symbol must differ from the Zig declaration — a C prefix, a versioned alias, weak
linkage, a specific section — use `@export` in a `comptime` block instead. The operand is a
**pointer**: `@export(&f, …)`, not `@export(f, …)`.

**Why:** the signature is
`@export(comptime ptr: *const anyopaque, comptime options: std.builtin.ExportOptions) void`. It took
a value before 0.14 and takes a pointer now; the old form is at least a loud failure
(`error: expected pointer type, found 'fn () callconv(.c) u32'`) rather than a silent one.
`ExportOptions` in 0.16 is
`{ name: []const u8, linkage: GlobalLinkage = .strong, section: ?[]const u8 = null,
visibility: SymbolVisibility = .default }` — everything but `name` has a default, and per ZS-CORE-27
pass the ones that matter to you explicitly. `@export` also lets one Zig function back several
symbols, which is how you ship a compatibility alias without duplicating the body.

**Check:** `@export(` whose first argument is not `&`-prefixed (the pre-0.14 value form), and an
`@export` call outside a `comptime` block. Also a second `export fn` whose body only forwards to
another exported function — that is an alias `@export` should provide.

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

### ZS-CAPI-05 [M] Spell the calling convention `.c` — `CallingConvention` is a union in 0.16
Write `callconv(.c)`. Not `.C`, not `.Stdcall`, not a string. `std.builtin.CallingConvention` is a
`union(enum(u8))`, so most of its members carry a payload and are written as struct literals; `.c`
is a `pub const` alias that resolves to whatever the target's C convention is.

**Why:** it changed shape twice. The `.C`/`.Stdcall`/`.Naked` enum spellings are pre-0.14. In 0.16
the type is:

```zig
// fragment — (quoted from std/builtin.zig, `CallingConvention`)
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

Practical consequences: `.c` is the only spelling you should normally write, because it is
target-resolved; `.winapi` and `.kernel` are the other two portable aliases. An
architecture-specific convention is a payload literal (`.{ .x86_64_sysv = .{} }`).
`@setAlignStack(n)` is gone, and its replacement is
`callconv(CallingConvention.withStackAlign(.c, n))` — note that `withStackAlign` does
`@field(result, @tagName(tag))` internally, so it **must** be evaluated at comptime or you get
`error: unable to evaluate comptime expression`.

**Check:** `callconv(.C)`, `callconv(.Stdcall)`, `callconv(.Naked)`, `callconv(.Inline)`, or a
string literal inside `callconv(` — all pre-0.14. Also `@setAlignStack`, and any `withStackAlign`
call not preceded by `comptime`.

```zig
// verified
const std = @import("std");
const CC = std.builtin.CallingConvention;

test "the calling convention is a union value" {
    const target_c: CC = .c;
    const explicit: CC = .{ .x86_64_sysv = .{} };
    const aligned = comptime CC.withStackAlign(.c, 16); // comptime is required
    _ = .{ target_c, explicit, aligned };
}
```

### ZS-CAPI-06 [S] Prefix every exported symbol with the library name
`zs_parse_u32`, not `parse_u32`. Apply it to `export fn`, `export var`, and every `@export` name.

**Why:** C has one flat global namespace with no modules, so an unprefixed `init` or `read` in a
static library collides at link time with any other library that had the same idea, and the
diagnostic (`duplicate symbol`) points at the linker rather than at either author. This is the one
place in this standard where `snake_case` functions are correct despite ZS-CORE-01 — the C header is
the contract and C's convention wins there. Keep the Zig-internal name `camelCase` and let the
export do the translation, as in ZS-CAPI-04.

**Check:** every `export fn`, `export var`, and `@export` `.name` in the diff begins with the
project's agreed prefix. A generic-sounding exported symbol — `init`, `open`, `read`, `free`,
`version` — is the finding.

---

## Calling C from Zig

### ZS-CAPI-07 [M] `extern "c" fn` for libc; bare `extern fn` for objects you link yourself
`extern "c" fn` names libc as the providing library and requires `link_libc`. For a symbol coming
from a `.c` file you compile into the same artifact — or any object you link — write `extern fn`
with no library name.

**Why:** the library name is a link-time dependency declaration, not decoration. Writing
`extern "c"` in a module without libc is a hard error:
`error: dependency on libc must be explicitly specified in the build command` — which is exactly
what you hit the first time you cross-compile a working interop module to `wasm32-freestanding` or
`thumb-freestanding-eabi`. Since freestanding never has libc, the bare form is the portable one for
your own C sources. Set `link_libc` on the **module**, not the artifact (ZS-BUILD-06), and only for
targets that have one (ZS-CAPI-23).

**Check:** `extern "c"` in a file that a `build.zig` also compiles for a `*-freestanding` target, or
in a module with no `link_libc` set. In the other direction, a bare `extern fn` naming a libc symbol
(`malloc`, `strlen`, `abs`, `getpid`) — that one links by accident and breaks when it does not.

```zig
// verified
const std = @import("std");

extern "c" fn strlen(s: [*:0]const u8) usize;
extern "c" fn abs(n: c_int) c_int;

test "call libc through hand-written declarations" {
    const s: [*:0]const u8 = "hello";
    try std.testing.expectEqual(5, strlen(s));
    try std.testing.expectEqual(7, abs(-7));
}
```

```zig
// fragment — same declaration, for a symbol from your own vendor/shim.c
extern fn zs_c_add(a: u32, b: u32) u32;
```

### ZS-CAPI-08 [M] Use `@extern` only for what a declaration cannot express
A plain `extern` declaration covers the ordinary case. Reach for
`@extern(T, .{ .name = …, … })` when the C symbol name is not a legal Zig identifier, when you need
`library_name`, `linkage`, `visibility`, `is_thread_local`, or `is_dll_import`, or when you want the
symbol as a value (a function *pointer*) rather than a callable declaration.

**Why:** `@extern(T: type, comptime options: std.builtin.ExternOptions) T` returns a *value* of the
type you ask for rather than introducing a declaration, which is what lets it bind a symbol whose
name is not a legal Zig identifier and what makes `library_name`, `is_thread_local`, and
`is_dll_import` expressible at all. It is strictly more verbose than `extern fn` otherwise — and
note that a plain declaration is already addressable, so `&abs` gives you a
`*const fn (c_int) callconv(.c) c_int` for a table without needing `@extern`.

**Check:** an `@extern` whose options are only `.name`, where that name is already a legal Zig
identifier — a plain `extern fn` covers it. Also an `@extern` introduced only to obtain a function
pointer, where `&declaration` already works.

```zig
// verified
const std = @import("std");

const getpid = @extern(*const fn () callconv(.c) c_int, .{ .name = "getpid" });

export var zs_version: c_int = 3;

test "bind a symbol as a value" {
    try std.testing.expect(getpid() > 0);
    try std.testing.expectEqual(3, zs_version);
}
```

### ZS-CAPI-09 [M] Confine C types to one boundary module
`c_int`, `c_long`, `[*c]T`, `[*:0]const u8`, `?*anyopaque`, and every `extern`/`@export` declaration
live in one module — `src/c.zig`, or one such file per C library. Nothing outside it names a C type.
That module exports a Zig-shaped API: slices, fixed-width integers, error sets, `Allocator`
parameters.

**Why:** every rule that follows (ZS-CAPI-10, ZS-CAPI-11, ZS-CAPI-12) is of the form "convert here,
once." That is only enforceable if there is a *here*. When `[*c]` and `c_long` are allowed to
spread, each conversion site becomes a separate decision made under different assumptions, and a
grep for `[*c]` stops being a review tool. The single-module discipline also gives the target rules
something to switch on: one file gets an `#ifdef`-shaped `comptime` branch instead of twenty.

**Check:** grep the whole tree for `c_int`, `c_long`, `c_char`, `c_uint`, `[*c]`, `?*anyopaque`,
`extern "c"`, `extern fn`, `@extern`, and `@export`. Every hit outside the designated boundary
module is the finding; the grep returning hits in more than one file per C library is the summary.

---

## Pointers, strings, and integers

### ZS-CAPI-10 [M] A `[*c]` pointer dies at the first Zig function; convert it to a slice or `?*T`
`[*c]T` may appear as a parameter of an exported function and nowhere else. The first statement that
touches it turns it into `[]T` (with the length C also gave you), `?*T`, or `[:0]const u8`. It is
never stored in a struct, never returned, and never passed to a second Zig function.

**Why:** `[*c]T` is deliberately the most permissive pointer in the language — it is simultaneously
nullable, of unknown length, and implicitly convertible to and from `*T`, `[*]T`, and `?*T` without
a cast. That is what makes translated C headers usable, and it is why it must not propagate: a
`[*c]` parameter silently accepts `null` and coerces to a non-optional `*T` with no diagnostic, so
every safety property Zig's pointer types normally give you is switched off for as long as it is in
scope. Converting at the boundary makes the null case a visible branch exactly once.

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
    var acc: u32 = 2166136261;
    for (bytes) |b| {
        acc ^= b;
        acc = acc *% 16777619;
    }
    return acc;
}

test "null C pointer becomes an empty slice, not a crash" {
    try std.testing.expectEqual(checksum("abc"), zs_checksum("abc", 3));
    try std.testing.expectEqual(checksum(""), zs_checksum(null, 0));
}
```

### ZS-CAPI-11 [M] `span` in, `[]const u8` inside, `dupeZ` out, `sliceTo` for fixed arrays
ZS-TYPE-32 already sets the policy: `[]const u8` is the internal string type and the NUL lives only
at the edge. The boundary mechanics are these four cases:

| Direction | Shape | Convert with |
|---|---|---|
| C → Zig, NUL-terminated | `[*:0]const u8`, `?[*:0]const u8` | `std.mem.span(p)` → `[:0]const u8` |
| C → Zig, fixed NUL-**padded** array | `*const [N]u8` | `std.mem.sliceTo(p, 0)` → `[]const u8` |
| C → Zig, pointer + length | `[*c]const u8` + `usize` | `p[0..len]` (ZS-CAPI-10) |
| Zig → C | `[]const u8` | `gpa.dupeZ(u8, s)` → `[:0]u8`, pass `.ptr` |

**Why:** the two inbound cases look identical in a C header and are not. `char name[16]` in a struct
is NUL-*padded*: a 16-byte name has no terminator at all, and `std.mem.span` — which searches for
the sentinel — walks off the end of the field into the next one. `sliceTo` is bounded by the array's
own length and stops at the first NUL or at the end, which is the correct reading for both cases.
Note also that `span` and `sliceTo` are optional-transparent: given `?[*:0]const u8` they return
`?[:0]const u8`, so `orelse` handles null in the same expression.

**Check:** `std.mem.span(` whose argument is `&`-taken from a fixed array or an array-typed struct
field rather than a `[*:0]` pointer — that is the read-past-the-end bug. Also a `[]const u8` handed
to a C function via `.ptr` with no `dupeZ`/`allocPrintSentinel` producing it, and any `.ptr` passed
to C where the slice was not built with a `:0` sentinel.

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
    const name_z: [:0]u8 = try gpa.dupeZ(u8, name);
    defer gpa.free(name_z);

    return strlen(name_z.ptr);
}

test "span, sliceTo and dupeZ across the boundary" {
    try std.testing.expectEqual(5, zs_greet_len("world"));
    try std.testing.expectEqual(0, zs_greet_len(null));

    // A fixed-size C char buffer is NUL-padded, not NUL-terminated by type:
    // `sliceTo` stops at the first NUL, `span` would run past a full buffer.
    const field: [8]u8 = "ab\x00\x00\x00\x00\x00\x00".*;
    try std.testing.expectEqualStrings("ab", std.mem.sliceTo(&field, 0));

    try std.testing.expectEqual(5, try callWithName(std.testing.allocator, "world"));
}
```

### ZS-CAPI-12 [M] Convert a C integer to a fixed-width Zig integer with a checked cast
`c_int`, `c_long`, `c_char` and friends appear in the exported signature and nowhere inside. Convert
with `std.math.cast(T, x) orelse return .invalid_argument` — never a bare `@intCast`, which is
illegal behavior on overflow, and never `@truncate`, which is silent.

**Why:** this is exactly the argument ZS-TYPE-02 makes about `usize`, and the C types are worse
because their width is set by the *platform ABI* rather than the pointer size. Measured on 0.16.0,
compiling the same source for six targets:

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

So a `c_long` that always fit before starts truncating the day someone builds for Windows;
`c_char` arithmetic that assumed `i8` inverts its sign comparisons on ARM Linux; and `c_int` is not
even 32 bits on the 16-bit microcontroller targets. `std.math.cast` returns `?T` and makes the
out-of-range case a branch you have to write. Where you genuinely mean "the byte", write `u8` and
`@bitCast`, not `c_char`.

**Check:** an `@intCast` or `@truncate` whose operand is declared `c_int`, `c_uint`, `c_long`,
`c_ulong`, `c_short`, `c_longlong`, or `c_char`. Also arithmetic or a comparison performed directly
on a `c_*`-typed value below the boundary module — the conversion should already have happened.

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

### ZS-CAPI-13 [M] Give a C-shared struct fixed-width fields, so its layout assertion is portable
ZS-TYPE-19 chooses the layout (`extern struct` for the C ABI, `packed struct(uN)` for bit layout,
default for neither), ZS-TYPE-20 requires the explicit backing integer and enum tag, and ZS-TYPE-21
requires the `comptime` `@sizeOf`/`@alignOf`/`@offsetOf` assertions. The rule this chapter adds:
for any struct **you** define and share with C, use fixed-width fields, so that one set of
assertions holds on every target you build for.

**Why:** `extern struct` promises the target's C ABI, and the target's C ABI is not one thing.
Measured on 0.16.0, `extern struct { a: c_int, b: c_long }` is 16 bytes with `b` at offset 8 on
`x86_64-linux-gnu`, and 8 bytes with `b` at offset 4 on `x86_64-windows-gnu`,
`arm-linux-gnueabihf`, and `wasm32-wasi`. A hard-coded `assert(@sizeOf(R) == 16)` therefore turns
cross-compilation into a build failure, and *removing* the assertion to make it build throws away
the only protection you had. Fixed-width fields make the two goals compatible. Use
`std.mem.Alignment` for any alignment you name (ZS-TYPE-22, ZS-MEM-26). Where the struct is C's, not
yours, you have no choice about the field types — in that case write the assertion inside a
`comptime` branch on `builtin.target` (ZS-CAPI-20) rather than dropping it.

**Check:** an `extern struct` you declare with a `c_int`, `c_long`, `c_char`, `usize`, `isize`, or
`?*anyopaque` field. Cross-reference each against its `comptime assert(@sizeOf(...) == N)`: that
pair is exactly what breaks on the next cross-compile. An `extern struct` with no layout assertion
at all is the ZS-TYPE-21 finding underneath this one.

```zig
// verified — compiles unchanged for x86_64-linux, x86_64-windows, arm-linux, wasm32-wasi
const std = @import("std");
const assert = std.debug.assert;

/// Fixed-width fields, so the layout assertion holds on every target.
/// `c_long` here would make this 16 bytes on Linux x86_64 and 8 on Windows.
pub const Record = extern struct {
    id: u64,
    kind: Kind,
    _padding: [3]u8 = @splat(0),
    length: u32,

    pub const Kind = enum(u8) { insert = 0, remove = 1 };
};

comptime {
    assert(@sizeOf(Record) == 16);
    assert(@alignOf(Record) == 8);
    assert(@offsetOf(Record, "kind") == 8);
    assert(@offsetOf(Record, "length") == 12);
}
```

### ZS-CAPI-14 [M] A C callback cannot capture; all state travels through `userdata`
A function passed to C is a top-level or namespaced function with `callconv(.c)`, never a closure
and never a nested function that refers to an enclosing local. State reaches it through the
`void *userdata` parameter the C API provides, and comes back with
`@ptrCast(@alignCast(userdata orelse return))`.
If the C API has no `userdata` parameter, it cannot be driven by more than one Zig object at a time
— say so at the wrapper, and use a file-scope singleton deliberately rather than by accident.

**Why:** Zig has no closures at all; a function value is just a pointer to code, with no environment
word to hold captures. That is why the `void *` exists in every well-designed C callback API, and
why an API without one is genuinely limited rather than merely awkward. Both casts are required and
neither is optional: `@ptrCast` changes the pointee type, and `@alignCast` restores the alignment
that `*anyopaque` (align 1) erased — without it the recovered `*Sum` would be a compile error, and
`@ptrCast` alone cannot add alignment.

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

### ZS-CAPI-15 [M] A callback parks its failure in `userdata` for the caller to check
A `callconv(.c)` callback cannot return an error (ZS-CAPI-01) and must not `try` past the C frame.
Give the userdata struct a `failure: ?SomeError = null` field, `catch` into it, make subsequent
invocations a no-op, and check it once the C function has returned.

**Why:** the callback runs on a C stack frame that knows nothing about error unions or `errdefer`.
Propagating out of it is impossible, and the two tempting alternatives are both wrong:
`catch unreachable` violates ZS-CORE-07 because allocation failure is an operating condition, and
`@panic` unwinds through C frames that may hold locks or partially built state. Parking the error
keeps C's iteration contract intact — it gets a `void` return every time — while making the failure
observable exactly once, at a Zig call site that can `errdefer` properly.

**Check:** `try`, `catch unreachable`, or `@panic` inside a `callconv(.c)` function body. Then, for
each such callback whose body can allocate or otherwise fail: a `failure: ?…` field on its userdata
struct, an early `return` when that field is already set, and a read of it at the Zig call site
immediately after the C function returns. A missing one of those three is the finding.

```zig
// verified — same `zs_c_each` C function as ZS-CAPI-14
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

### ZS-CAPI-16 [M] Whoever calls `free` picks the allocator: `std.heap.c_allocator` if C does
Decide, per function, which side owns each buffer, and write it in the doc comment (ZS-MEM-10). If C
will call `free()` on it, allocate it with `std.heap.c_allocator`. If your library will free it,
export a `zs_release`-style function and use any allocator you like. Never hand C a pointer from a
`DebugAllocator`, arena, `FixedBufferAllocator`, or `smp_allocator` and expect `free()` to work.

**Why:** `free()` is not a generic deallocator; it is libc's, and it requires a pointer that libc's
`malloc` produced. Every other allocator in ZS-MEM-03 keeps its bookkeeping somewhere libc has never
heard of — an arena frees nothing per-object at all, and `DebugAllocator` never reuses an address.
`std.heap.c_allocator` is the one that forwards to `malloc`/`realloc`/`free`, and its docs note that
"simple `malloc` calls are used when possible, but large requested alignments may require larger
buffers", so the `free()`-compatibility guarantee holds for naturally-aligned allocations —
`u8` buffers and C strings — which is what crosses the boundary anyway. It is a `@compileError`
without `link_libc`, so this pattern and freestanding are mutually exclusive by construction.
The library-owned form is strictly safer, because it survives a caller who links a different libc.

**Check:** a pointer returned to C from `allocPrint`, `dupeZ`, or `gpa.alloc` where the allocator is
not `std.heap.c_allocator` and the module exports no matching release function. Also an exported
release function taking a bare `[*]u8` or `?*anyopaque` rather than a pointer *and* a length, and
any exported function whose doc comment does not say which side frees the buffer it returns.

```zig
// verified
const std = @import("std");

/// Buffer the C caller releases with `free()`. It must come from libc's heap,
/// so allocate through `std.heap.c_allocator` — never a `DebugAllocator`,
/// arena, or `smp_allocator`, whose blocks `free()` does not understand.
/// Caller owns the returned pointer; release it with `free()`.
export fn zs_render(value: u64) ?[*:0]u8 {
    const gpa = std.heap.c_allocator;
    return (std.fmt.allocPrintSentinel(gpa, "{d}", .{value}, 0) catch return null).ptr;
}

/// Preferred: the library owns the buffer and exports the matching release
/// function, so any Zig allocator is fine — the same one frees it.
const Handle = extern struct { ptr: [*]u8, len: usize };

var handle_gpa: std.mem.Allocator = undefined;

export fn zs_render_owned(value: u64, out: ?*Handle) bool {
    const out_ptr = out orelse return false;
    const buf = std.fmt.allocPrint(handle_gpa, "{d}", .{value}) catch return false;
    out_ptr.* = .{ .ptr = buf.ptr, .len = buf.len };
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

Note `zs_release` takes the `Handle` back rather than a bare pointer, because ZS-MEM-15 requires
freeing exactly the slice that was allocated — C must hand the length back with the pointer.

---

## Getting the declarations

### ZS-CAPI-17 [S] Hand-write `extern` declarations; use `b.addTranslateC` for large headers
**Default to hand-writing.** Declare the dozen functions and handful of structs your wrapper uses,
in the boundary module of ZS-CAPI-09. Switch to `b.addTranslateC` when the surface is large enough
that hand-transcription is the bigger risk: a generated header, a vendored library with hundreds of
entry points, or one whose ABI changes between releases you track. `@cImport` still compiles in
0.16 and emits no warning, but ZS-BUILD-36 already prefers the build step — do not add new
`@cImport` sites.

**Why:** the mechanism cuts both directions. Hand-written declarations let you apply every rule in
this chapter at the point of declaration: `?[*:0]const u8` instead of `[*c]const u8`, an explicit
`enum(c_int)` instead of a bare `c_int`, a doc comment recording who frees what. translate-c cannot
infer any of that — it emits `[*c]` for every pointer, because a C `T *` really is nullable and
unbounded, so its output is the least safe legal translation by construction. It is also
target-specific: the same header produces different integer types per target, so the output is a
build artifact, not source. Against that, hand-writing is transcription, and transcription of two
hundred functions will contain a wrong parameter order that compiles and corrupts memory.

The practical costs matter too, and they are worse than they look. On 0.16.0 the implementation
moved from libclang to Aro, which the release notes describe as a "cross your fingers when you
upgrade" change. Measured: `@cImport` on a fresh two-line header resolves in under a
second, but the standalone `zig translate-c` CLI on the *same* header burned 90% of a core for
twenty-five minutes without emitting a byte before it was killed. That matters because
`Step.TranslateC` shells out to exactly that CLI (`std/Build/Step/TranslateC.zig` builds an argv
starting `zig translate-c …`), so `b.addTranslateC` inherits the pathology — it is cached in
`.zig-cache` afterwards, but the first build and every header change pays it. Sharpen ZS-BUILD-36
with this: the build step is still the right *shape*, but on 0.16.0 the cheapest option is not to
translate at all.

If you do use it: declare include paths and macros once in `build.zig`, import the result as a
module, and pin the parts you depend on with `addCheckFile` so a toolchain upgrade that changes the
translation fails the build instead of silently changing a type.

**Check:** a new `@cImport(` site in the diff — none should be added. A `b.addTranslateC` step with
no `addCheckFile` pinning the declarations the code depends on. And, from the other side, a
hand-written `extern` block that has grown past a few dozen declarations, or one whose parameter
order was transcribed rather than derived from the header in the same diff.

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
boundary module and get converted per ZS-CAPI-10 through ZS-CAPI-12.

---

## Targets

### ZS-CAPI-18 [M] On freestanding there is no `std.process.Init` — export your entry points instead
**This rule is an explicit exemption from ZS-MEM-01 and ZS-IO-01.** Both are `[M]` and both say to
take `std.process.Init` in `main` and use the `gpa`, `arena`, and `io` it hands you. On
`*-freestanding` there is no such thing, and those two rules do not apply. The freestanding entry
point is one or more `export fn` symbols: `_start` (or whatever the reset vector names) for bare
metal, and the exported API surface for a WebAssembly module. Allocation comes from a
`FixedBufferAllocator` over a static array (ZS-MEM-23), or from `std.heap.wasm_allocator` on wasm.
There is also no usable `Io`: `Io.Threaded`, the only backend std ships that would apply, does not
compile for either freestanding target, so no `Io.Dir`, `Io.File`, `io.async`, or `io.sleep`.

**Why:** `std.process.Init` is populated by `std/start.zig`, which runs only when there *is* a
start. Two consequences on 0.16.0:

- On `thumb-freestanding-eabi`, `pub fn main(init: std.process.Init) !void` compiles but is dead
  code — the linker reports `cannot find entry symbol _start; not setting start address`, because
  no start code was emitted to call it.
- On `wasm32-freestanding` it does not even compile: `std.start` tries to build the `Io.Threaded`
  it would hand you and fails inside it
  (`error: struct 'posix.system__struct_…' has no member named 'getrandom'`). Instantiating
  `Io.Threaded` by hand fails identically on both freestanding targets.

So "freestanding just doesn't get the nice `main`" is wrong in a dangerous direction: on bare metal
it silently produces a binary that never runs your code. The `[M!]` audience for the rest of this
standard — firmware, embedded, unattended systems — is precisely the audience for which this
exemption exists, so it is stated rather than left implicit.

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

### ZS-CAPI-19 [M] Freestanding supplies its own panic handler, as a namespace
Declare `pub const panic = std.debug.FullPanic(myPanicFn);` at the root of a freestanding program,
where `myPanicFn` has the signature `fn (msg: []const u8, first_trace_address: ?usize) noreturn`.
`panic` is a **namespace**, not a function; `std/builtin.zig` still accepts the older
`pub fn panic(msg, trace, ra) noreturn` form but marks it
"Deprecated; make `panic` a namespace instead".

**Why:** `std.debug.defaultPanic` switches on `builtin.os.tag` and for `.freestanding` its entire
body is `@trap()`. A safety failure on a microcontroller therefore becomes an undiagnosed halt with
no message, no LED, no UART byte, and no watchdog reset — which is the worst possible outcome for
the exact class of system that most needs to know it faulted. Your handler is where a real product
writes a fault record to flash and resets. Note also that the convenience namespace
`std.debug.simple_panic` **does not compile** on `wasm32-freestanding` in 0.16.0 (it reaches
`Io.Threaded`), so `FullPanic` with your own function is the portable choice, not just the better
one. `std.debug.no_panic` compiles for both freestanding targets and is the deliberate "smallest
possible" option.

**Check:** a freestanding root source file with no `pub const panic =` declaration at all, one
written as `pub fn panic(` (the deprecated function form), or one set to `std.debug.simple_panic`,
which does not compile on `wasm32-freestanding`.

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

### ZS-CAPI-20 [M] Branch on `builtin.target` at comptime; `@compileError` the unhandled target
Conditional compilation reads `builtin.target`, `builtin.target.os.tag`, `builtin.target.cpu.arch`,
`builtin.target.abi`, `builtin.link_libc`, and `builtin.single_threaded` — not a hand-rolled
`-Dplatform` string option. Use a `switch` whose `else` is `@compileError`, so a new target is a
build failure rather than a wrong default.

**Why:** these are `comptime`-known, so the untaken arm is never semantically analysed — that is
what lets one file contain both a `linux` path calling `std.posix` and a `windows` path calling
Win32 without either breaking the other. A `-D` option cannot do that, because it is not known when
the target is resolved, and it drifts out of sync with `-Dtarget`. The `else => @compileError`
matters more than it looks: the alternative, a silent fallback, means the first person to
cross-compile your module to a new platform gets subtly wrong behavior instead of a message naming
the file that needs attention. For per-target `extern` declarations, this is also how you keep the
boundary module of ZS-CAPI-09 to one file.

**Check:** a `switch` on `builtin.target.os.tag`, `builtin.target.cpu.arch`, or `builtin.target.abi`
whose `else` arm produces a value rather than `@compileError`. Also a `b.option` named `platform`,
`os`, `arch`, or similar in `build.zig`, and any `if (builtin.os.tag == ...)` chain with no final
`else` that fails.

```zig
// verified — compiles for x86_64-linux, x86_64-windows, wasm32-wasi, thumb-freestanding
const builtin = @import("builtin");
const std = @import("std");
const assert = std.debug.assert;

/// Branch on `builtin.target`, not on a hand-rolled `-Dplatform` option, and
/// branch at `comptime` so the dead arm is never analysed.
const page_size_bytes: usize = switch (builtin.target.os.tag) {
    .linux, .freebsd, .netbsd, .openbsd => 4096,
    .macos, .ios, .tvos, .watchos => if (builtin.target.cpu.arch == .aarch64) 16384 else 4096,
    .windows => 65536,
    .wasi, .freestanding => 65536,
    else => @compileError("unsupported target: " ++ @tagName(builtin.target.os.tag)),
};

comptime {
    assert(std.math.isPowerOfTwo(page_size_bytes));
}
```

### ZS-CAPI-21 [M] `-fsingle-threaded` removes task concurrency and cancellation
A single-threaded build is not "the same program with one thread". Behavior on 0.16.0:

| Construct | Under `-fsingle-threaded` |
|---|---|
| `io.async(f, args)` | Compiles and returns a `Future`, but **runs `f` eagerly and inline**. Nothing overlaps. |
| `io.concurrent(f, args)` | Returns `error.ConcurrencyUnavailable`. |
| `future.cancel(io)` | A no-op returning the already-computed result: the work already happened. |
| `std.heap.smp_allocator` | Build failure: a `comptime assert(!builtin.single_threaded)`, reported as `error: reached unreachable code`. |
| `std.heap.wasm_allocator` | The **reverse**: `@compileError("unimplemented")` *unless* single-threaded. |

**Why:** this qualifies the io chapter's structured-concurrency rules rather than contradicting
them. Code written against `Io` still compiles and still produces correct results, which is the
point of the colorless design — but a design whose *correctness* depends on two tasks overlapping
(a producer feeding a consumer through a bounded queue, a timeout racing an operation) will deadlock
or hang, and a cancellation-based timeout will not fire. So: if a module requires concurrency, say
so in its doc comment and call `io.concurrent`, whose `error.ConcurrencyUnavailable` is the honest
failure, rather than `io.async`, which will quietly serialise. Conversely, wasm and freestanding
builds are single-threaded, which is why the two allocator entries above point in opposite
directions.

**Check:** an `io.async` whose two tasks must overlap for the program to make progress — a producer
feeding a bounded queue a consumer drains, or a timeout raced against an operation — in a module
that any build target may compile `-fsingle-threaded`. It should be `io.concurrent`. Also
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

### ZS-CAPI-22 [M] On WASI, resolve directories through `init.preopens`, never `Io.Dir.cwd()`
A WASI program has no ambient filesystem. Take the directory the host granted you by name from
`init.preopens`, and fail with a named error if it is absent.

**Why:** `Io.Dir.cwd()` on WASI is a guess — the source is literally
`.wasi => .{ .handle = 3 }, // Expect the first preopen to be current working directory`. If the
host granted its preopens in a different order, or granted none, that handle is some other directory
or nothing, and every path you open is silently wrong. `std.process.Init` carries
`preopens: Preopens`, whose `get(name) ?Resource` returns
`union(enum) { file: Io.File, dir: Io.Dir }` — a real capability lookup with a null case you have to
handle. On non-WASI targets the same call still resolves `"stdin"`, `"stdout"`, and `"stderr"`, so
the code is portable.

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

### ZS-CAPI-23 [M] Derive `link_libc`, `single_threaded`, and `entry` from the resolved target
Compute them from `target.result` rather than hard-coding. `link_libc` is true only for hosted
targets. Leave `single_threaded` **unset** unless you mean it. `entry` is `.disabled` for a wasm
library and `.{ .symbol_name = "_start" }` (or your reset symbol) for bare metal, and exported
symbols go in `mod.export_symbol_names`.

**Why:** each of the three has a failure mode on 0.16.0. `link_libc = true` on freestanding
makes every `extern "c"` declaration fail with `dependency on libc must be explicitly specified`
(ZS-CAPI-07). Forcing `single_threaded = false` on `wasm32-wasi` fails inside `Io.Threaded` with
`comptime assert(builtin.cpu.has(.wasm, .atomics))` — the default is right and overriding it is
what breaks; setting it to `true` is fine and is what freestanding gets anyway. And leaving `entry`
at `.default` for a freestanding ELF target makes the LLD warning `cannot find entry symbol _start`
into a **build failure**, because `zig build` treats unexpected linker stderr as an error. Note
these all live on the `Module`, not the artifact — except `entry`, which is a property of the
executable (ZS-BUILD-06).

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

1. Does any exported function return `!T`, or an error smuggled as an integer? (ZS-CAPI-01)
2. Is every pointer parameter null-checked and every length bounded before use? (ZS-CAPI-03)
3. Does `[*c]` appear anywhere but an exported parameter list? (ZS-CAPI-10)
4. Is `std.mem.span` being applied to a fixed-size NUL-padded C array where `sliceTo` belongs?
   (ZS-CAPI-11)
5. Any `@intCast`/`@truncate` on a `c_int`/`c_long`/`c_char` instead of `std.math.cast`?
   (ZS-CAPI-12)
6. Does every struct shared with C have fixed-width fields and `comptime` layout assertions?
   (ZS-CAPI-13, ZS-TYPE-21)
7. Does any callback `try`, `catch unreachable`, or `@panic` across the C frame? (ZS-CAPI-15)
8. For each buffer that crosses: which side frees it, is it written down, and does the allocator
   match? (ZS-CAPI-16)
9. Does the code assume `std.process.Init`, `Io`, or a default panic handler on a target that has
   none? (ZS-CAPI-18, ZS-CAPI-19)
10. Does any design depend on two tasks overlapping in a build that may be `-fsingle-threaded`?
    (ZS-CAPI-21)
