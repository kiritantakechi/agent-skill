# Type selection, integers, structs, data layout

Scope: choosing integer types and casting between them; index/count/size discipline and rounding
intent; struct construction (decl literals, `init`/`deinit`, out-pointer initialization and Result
Location Semantics); memory layout (`extern` / `packed` / default, alignment); container selection
(`ArrayList`, `MultiArrayList`, fixed arrays, handles vs pointers); and modeling with enums, tagged
unions, optionals and sentinels. Naming rules live in the naming chapter; error-set design and
`try`/`catch` shape live in the errors chapter; allocator lifetime and ownership live in the memory
chapter; `comptime` metaprogramming and generic-type authoring live in the comptime chapter.

Every snippet below assumes this file-scope preamble, per ZS-ASSERT-01:

```zig
// fragment
const std = @import("std");
const assert = std.debug.assert;
```

## Contents

- **Integers and arithmetic**
  - ZS-DATA-01 [M] Use `usize` only for in-memory lengths, indices, and byte sizes
  - ZS-DATA-02 [M] Never let `usize` reach a serialized or `extern` layout
  - ZS-DATA-03 [M!] Give bounded domain quantities a width that encodes the bound
  - ZS-DATA-04 [S] Name integers so that index, count, and size are distinguishable
  - ZS-DATA-05 [M] Convert between index, count, and size in one explicit step
  - ZS-DATA-06 [M] Show rounding intent with an explicit division operation
  - ZS-DATA-07 [M] Let integer overflow trap; never reach for `+%` to silence a panic
  - ZS-DATA-08 [M] Use wrapping and saturating operators only where the semantics demand them
  - ZS-DATA-09 [M] Choose the cast builtin by intent, not by whichever one compiles
  - ZS-DATA-10 [M] Use the checked `std.math` helpers where a bad value is an operating error
  - ZS-DATA-11 [M] Convert float to int with `@trunc`/`@round`, after a range check
- **Struct construction and initialization**
  - ZS-DATA-12 [M] Write `const x: T = .{ ... }`, not `const x = T{ ... }`
  - ZS-DATA-13 [M] Construct std containers with their decl literals
  - ZS-DATA-14 [M] Give every allocating type a paired `init`/`deinit` with a matching signature
  - ZS-DATA-15 [M] Never build a value out of its own fields through an anonymous initializer
  - ZS-DATA-16 [M] Initialize a self-referential struct in place through an out pointer
  - ZS-DATA-17 [M!] In-place initialization is viral — propagate it to every containing struct
  - ZS-DATA-18 [S] Pass aggregates larger than 16 bytes as `*const T`
- **Memory layout**
  - ZS-DATA-19 [M] Default to plain `struct`; use `extern` for ABI and `packed(uN)` for bits
  - ZS-DATA-20 [M] Always spell the backing integer and enum tag type in `extern`/`packed`/`export`
- **Containers and data-oriented layout**
  - ZS-DATA-21 [S] Reference long-lived elements by handle, not by pointer
  - ZS-DATA-22 [S] Use `std.MultiArrayList` when hot loops read a subset of the fields
  - ZS-DATA-23 [M] Build a fixed-capacity list with `ArrayList.initBuffer`; get stable addresses from a pool or a list
  - ZS-DATA-24 [S] Prefer a fixed array when the bound is comptime-known
- **Modeling with enums, unions, and optionals**
  - ZS-DATA-25 [M] Model variants as a tagged union, not a struct with a kind field
  - ZS-DATA-26 [M] Make an enum non-exhaustive only for values that come from outside
  - ZS-DATA-27 [M] Return the lowest-dimensionality type that can carry the answer
  - ZS-DATA-28 [M] Express absence with the weakest construct that fits
  - ZS-DATA-29 [M] `[]const u8` is the default string; `[:0]const u8` only where a NUL is required
- **Text: UTF-8, WTF-8, and ASCII**
  - ZS-DATA-30 [M] A byte index is not a codepoint index; iterate with `Utf8View`
  - ZS-DATA-31 [M] Windows filenames are WTF-8, not UTF-8 — use the `wtf8` family for paths
  - ZS-DATA-32 [M] `std.ascii` operates on bytes; never let it stand in for Unicode
- **Arithmetic and type-system rules with silent-wrong-code potential**
  - ZS-DATA-33 [M] `std.math.sign` returns the narrowest integer, not the argument's type
  - ZS-DATA-34 [M] Check type-level code against the five rules older Zig code trips on
- **Serialization**
  - ZS-DATA-35 [M] ZON for formats you own, `std.json` for interop; bound both on untrusted input
- **Symmetry of an API surface**
  - ZS-DATA-36 [M] Give every operation its inverse, or document why there is none
  - ZS-DATA-37 [M] Keep parameter order identical across sibling functions
  - ZS-DATA-38 [M] Split a function rather than adding a mode parameter

---

## Integers and arithmetic

### ZS-DATA-01 [M] Use `usize` only for in-memory lengths, indices, and byte sizes

Use `usize` wherever std's own API already uses it — `slice.len`, the argument to `[]`, `@sizeOf`,
and every length in `std.mem.Allocator` and the std containers — so no cast is inserted at those
points. A *domain* index with its own named bound may be narrower (ZS-DATA-03); convert it with a
single explicit `@intCast` at the slice boundary rather than at every arithmetic step. What this
rule forbids is `usize` as a general-purpose integer, and `u32` as a general-purpose replacement for
`slice.len`.

TigerStyle's "use explicitly-sized types like `u32` for everything" was written for a codebase that
owns its own containers; in a codebase that uses std, it is load-bearing where ZS-DATA-02 and
ZS-DATA-03 apply.

**Why:** forcing `u32` on in-memory lengths inserts a cast at every `slice.len`, every
`ArrayList.append`, and every `gpa.alloc`, and each of those casts is a place a real bug can hide.
Casts you write because the language made you write them stop being read.

**Check:** an `@intCast` sitting directly on `slice.len`, `@sizeOf`, or a container/allocator length
argument — that cast exists only because something narrower than `usize` was chosen where std uses
`usize`. In the other direction, a `usize` on a quantity that is not a length, an index, or a byte
size.

```zig
// verified — GOOD
fn checksum(bytes: []const u8) u64 {
    var sum: u64 = 0;
    var index: usize = 0;
    // A byte checksum is defined modulo 2^64 (ZS-DATA-08).
    while (index < bytes.len) : (index += 1) sum +%= bytes[index];
    return sum;
}
```

### ZS-DATA-02 [M] Never let `usize` reach a serialized or `extern` layout

Any integer that is written to disk, put on the wire, hashed, fed to a checksum, or placed in a
struct shared with C must have an explicit width and, where endianness matters, an explicit
endianness.

The C-named integers are target-dependent too. On 0.17, `extern struct { a: c_int, b: c_long }` is
16 bytes with `b` at offset 8 on `x86_64-linux-gnu`, and 8 bytes with `b` at offset 4 on
`x86_64-windows-gnu`, `arm-linux-gnueabihf` and `wasm32-wasi`. So a struct you define and share with
C takes fixed-width fields, and one set of layout assertions holds on every target. Where the struct
is C's and its field types are not yours to choose, keep the assertion and put it in a `comptime`
branch on `builtin.target` (ZS-INTEROP-18) rather than dropping it.

**Why:** `@sizeOf(usize)` is target-dependent. A record with a `usize` field is 8 bytes on x86_64
and 4 on wasm32/arm32, so the same program, cross-compiled, cannot read its own files, and a
checksum over the struct's bytes differs by target.

**Check:** `usize`, `isize`, `c_int`, `c_long`, or an unparameterized `enum` as a field type inside
any `extern struct` or `packed struct`, or inside a type handed to a write, hash, or checksum call.
Every field of such a type names its width.

```zig
// verified — BAD: this compiles; that is the problem
const Record = extern struct {
    offset: usize, // 8 bytes on x86_64, 4 on wasm32. Same source, two file formats.
    length: usize,
};
```

```zig
// verified — GOOD
const std = @import("std");
const assert = std.debug.assert;
const Record = extern struct {
    offset_bytes: u64,
    length_bytes: u64,
};

comptime {
    assert(@sizeOf(Record) == 16);
}
```

### ZS-DATA-03 [M!] Give bounded domain quantities a width that encodes the bound

A replica id, an opcode, a slot number, a nesting depth — anything with a real domain limit — gets
the narrowest type that expresses the limit, not `usize` and not a reflex `u32`.

*Relaxed form:* keep the reflex `u32`, but the limit gets a named `const` and every value entering
the field is asserted against it, so the bound still exists in one named place.

**Why:** the type becomes the invariant. `replica: u3` with `replica_count_max = 6` makes an
out-of-range replica id unrepresentable rather than merely unlikely, and `std.math.IntFittingRange`
keeps the type and the limit from drifting apart.

**Check:** a field or parameter named `*_id`, `*_index`, `*_slot`, `*_depth`, or `*_opcode` typed
`u32`/`usize` while a matching `*_max` constant exists nearby, with no `IntFittingRange` deriving
the type and no assert against the max.

```zig
// verified — GOOD
const std = @import("std");
const assert = std.debug.assert;
const replica_count_max = 6;
const Replica = std.math.IntFittingRange(0, replica_count_max - 1);

comptime {
    assert(Replica == u3);
}
```

### ZS-DATA-04 [S] Name integers so that index, count, and size are distinguishable

An `index` is 0-based and identifies one element. A `count` is 1-based and answers "how many". A
`size` is a count multiplied by a unit — always suffix it with the unit (`_bytes`, `_blocks`,
`_sectors`).

**Why:** these are three different conceptual types wearing the same primitive. TigerStyle: "the
usual suspects for off-by-one errors are casual interactions between an `index`, a `count` or a
`size`." Zig will not type-check the difference, so the name is the only guard rail.

**Check:** a name that is bare `len`, `n`, `num`, `size`, `total`, or `length` with no role or unit;
a `*_size` with no unit suffix; or a `*_count` used directly as a subscript, which is the off-by-one
itself.

```zig
// fragment — BAD
const len = list.items.len;       // Count? Index of last? Bytes?
const total = len * 4;            // Bytes of what?
```

```zig
// fragment — GOOD
const entry_count = list.items.len;
const entry_index_last = entry_count - 1;
const entries_size_bytes = entry_count * @sizeOf(Entry);
```

### ZS-DATA-05 [M] Convert between index, count, and size in one explicit step

Write the `+ 1` and the `* unit` out. Do not let a value drift from index-space to count-space
across several statements.

**Why:** every conversion is an off-by-one opportunity, and a conversion that happens implicitly
across three lines cannot be reviewed. `index_last + 1` next to `count` makes the relation checkable
at a glance; `count * @sizeOf(T)` makes the unit visible.

**Check:** a `+ 1` or `- 1` on a line that does not also change the name's role from index to count
or back, and a `* @sizeOf(T)` applied to a variable whose name says `index`. Both mean the
conversion was spread across statements instead of written in one.

```zig
// verified — GOOD
const std = @import("std");
test "index count size" {
    const items = [_]u32{ 10, 20, 30 };
    const index_last: usize = items.len - 1; // 2
    const count_total: usize = index_last + 1; // index -> count: +1
    const size_bytes: usize = count_total * @sizeOf(u32); // count -> size: * unit
    try std.testing.expectEqual(3, count_total);
    try std.testing.expectEqual(12, size_bytes);
}
```

### ZS-DATA-06 [M] Show rounding intent with an explicit division operation

This rule owns division and rounding for the whole standard; ZS-ASSERT-21 (derive dependent limits)
points here for the rounding half.

For integers, use `@divExact`, `@divFloor`, `@divTrunc`, or `@divCeil`. Reserve bare `/` for
unsigned operands where truncation is obviously intended and obviously irrelevant. The same applies
to the remainder: `@rem` takes the sign of the dividend, `@mod` takes the sign of the divisor, and
`%` is rejected on runtime-known signed operands for exactly that reason. Pair each division with
its matching remainder — `@divTrunc`/`@rem`, `@divFloor`/`@mod` — so that `q * b + r == a` holds
with the sign convention you meant.

Zig already rejects bare `/` on runtime-known signed integers
(`signed integers must use @divTrunc, @divFloor, @divCeil, or @divExact`); unsigned `/` compiles
silently. `@divExact` is safety-checked: a nonzero remainder panics with
`exact division produced remainder`. `@divCeil`, new in 0.17, is checked the same way (a zero
denominator panics with `division by zero`); where a zero denominator is an operating condition
rather than a bug, use `std.math.divCeil`, which returns `error{DivisionByZero, Overflow}!T`.
TigerStyle's `div_ceil` helper (their own `stdx`) is `@divCeil` here; do not reimplement it.

**Why:** floor and truncation disagree on negatives, and an unexpected remainder is a silent
rounding bug. A named builtin states which rounding was meant, and `@divExact` turns a wrong
assumption about the remainder into a crash at the line that made it.

**Check:** `rg -n '\+ (\w+ - 1|\d+)\) / ' -g '*.zig'` finds the hand-rolled ceil idiom,
`(x + k - 1) / k` or `(x + 4095) / 4096`; each hit is the finding, and `@divCeil` its replacement.
Every other `/` and `%` on integer operands in a diff is read: an unsigned truncation whose
remainder is provably irrelevant, or a named builtin.

```zig
// fragment — BAD
const pages = (size_bytes + 4095) / 4096; // Hand-rolled ceil; overflows near maxInt.
const sectors = total_bytes / 512;        // Is a remainder possible? Unstated.
```

```zig
// verified — GOOD
const std = @import("std");
const page_size_bytes: usize = 4096;

fn pagesFor(size_bytes: usize) usize {
    // Cannot overflow and cannot divide by zero: the denominator is a nonzero constant.
    return @divCeil(size_bytes, page_size_bytes);
}

test "divExact states the invariant" {
    const total_bytes: u64 = 8192;
    const sector_count = @divExact(total_bytes, 512); // Panics if not a whole number of sectors.
    try std.testing.expectEqual(16, sector_count);
}

test "signed division and remainder are two independent choices" {
    const a: i32 = -7;
    const b: i32 = 2;
    try std.testing.expectEqual(-3, @divTrunc(a, b)); // Toward zero...
    try std.testing.expectEqual(-1, @rem(a, b)); // ...with the remainder signed like `a`.
    try std.testing.expectEqual(-4, @divFloor(a, b)); // Toward negative infinity...
    try std.testing.expectEqual(1, @mod(a, b)); // ...with the remainder signed like `b`.
}
```

### ZS-DATA-07 [M] Let integer overflow trap; never reach for `+%` to silence a panic

`+`, `-`, `*` on integers are safety-checked: overflow panics with `integer overflow` in `debug` and
`safe` builds. That panic is the feature. If the value can legitimately exceed the type, widen the
type or check the input; do not change the operator.

**Why:** an overflow in ordinary arithmetic means a bound you believed was true is false. Replacing
`+` with `+%` converts a detected programmer error into silent corruption that surfaces far from its
cause.

**Check:** a `+%`, `-%`, or `*%` whose operands are a running total, a length, an offset, a
capacity, or a counter. Those are accumulators, not modular arithmetic, and a wrapping operator on
one is a silenced panic — especially when the diff that introduced it also touched the width.

```zig
// fragment — BAD
total +%= record.length_bytes; // Hides that `total: u32` is too narrow for the workload.
```

```zig
// fragment — GOOD
var total_bytes: u64 = 0;
total_bytes += record.length_bytes; // Panics if the u64 bound is ever violated.
```

### ZS-DATA-08 [M] Use wrapping and saturating operators only where the semantics demand them

`+%`, `-%`, `*%`, `<<%` are legitimate only when arithmetic modulo 2^N is the specification: hash
mixing, PRNG state advance, checksums, wrap-around sequence numbers, deliberate two's-complement
tricks. `+|`, `-|`, `*|` are legitimate only when clamping at the type bound is the domain answer:
UI levels, retry backoff caps, signal mixing. Comment the reason at the operator.

**Why:** these operators disable the overflow check permanently and invisibly. A reader who sees
`+%` must be able to tell, without leaving the line, whether it encodes a spec or hides a bug.

**Check:** every `+%`, `-%`, `*%`, `<<%`, `+|`, `-|`, `*|` in a diff needs a comment on the same
line or the line above naming the specification that demands it — FNV, xorshift, sequence wrap,
clamp. No comment is the violation.

```zig
// verified — GOOD
fn fnv1a(bytes: []const u8) u64 {
    var hash: u64 = 0xcbf29ce484222325;
    for (bytes) |byte| {
        hash ^= byte;
        hash *%= 0x100000001b3; // FNV-1a is defined modulo 2^64.
    }
    return hash;
}

fn boostLevel(level: u8, amount: u8) u8 {
    return level +| amount; // Level is clamped at 255 by design, not by accident.
}
```

### ZS-DATA-09 [M] Choose the cast builtin by intent, not by whichever one compiles

- `@intCast` — the value *should* fit; a value that does not is a bug. Safety-checked
  (`integer does not fit in destination type`).
- `@truncate` — discarding the high bits is the intent. Well defined, never checked. Only use it to
  narrow.
- `@bitCast` — reinterpret the same bits as a same-sized type (`u32` <-> `f32`, `[4]u8` <-> `u32`).
  Never for numeric conversion. It rejects an `extern struct` or `extern union` operand
  (`error: cannot @bitCast from 'T'`; use `@ptrCast` or an `extern union`), reads arrays and vectors
  as logical bits whatever the target's endianness, and safety-checks a cast to an enum.
- `@fromBackingInt` / `@backingInt` — conversion between an enum, or a packed struct or union with
  an explicit backing integer, and that integer. `@fromBackingInt` is checked for exhaustive enums
  and takes exactly the backing type, so `@intCast` a wider operand first. `@enumFromInt` and
  `@intFromEnum` are their deprecated spellings, and `zig fmt` rewrites them to these.
- `@ptrCast` / `@alignCast` — pointers only, and each needs its own justification.

0.17 accepts `@truncate` to a *wider* type, though the langref describes its result as "a smaller or
same-sized integer type": do not rely on the compiler to catch a mis-widened `@truncate`, and widen
with `@intCast`.

**Why:** all four are one token long and all four compile in the same slot, so the choice carries
the entire signal about what the programmer believes. `@truncate` where `@intCast` was meant is the
classic silent-corruption bug: it turns `300` into `44` with no diagnostic in any build mode.

**Check:** every `@truncate` in a diff. If the discarded high bits are not stated in a comment or
implied by the destination's name (`low_byte`, `*_lsb`), it should be `@intCast`. Also flag any
`@truncate` whose destination is at least as wide as its source, and any `@bitCast` between two
integer types — that is a numeric conversion wearing the wrong builtin.

```zig
// fragment — BAD
const small: u8 = @truncate(record_count); // Silently turns 300 into 44, in every build mode.
```

```zig
// verified — GOOD
const std = @import("std");
test "cast intent" {
    var word: u32 = 0xdead_beef;
    _ = &word;
    const low_byte: u8 = @truncate(word); // Deliberately keeping the low 8 bits.
    try std.testing.expectEqual(0xef, low_byte);

    const bits: u32 = 0x3f80_0000;
    const value: f32 = @bitCast(bits); // Reinterpretation, same width.
    try std.testing.expectEqual(1.0, value);

    var count: u32 = 7;
    _ = &count;
    const index: usize = @intCast(count); // Must fit; crash if it ever does not.
    try std.testing.expectEqual(7, index);
}
```

### ZS-DATA-10 [M] Use the checked `std.math` helpers where a bad value is an operating error

At a trust boundary — parsed input, network frames, on-disk headers, FFI returns — an out-of-range
value is *expected*, not a bug. Use `std.math.cast(T, x) ?T`, `std.math.add/sub/mul(T, a, b)`
(`error{Overflow}!T`), and `std.math.div*` so the failure becomes an error you handle, not a panic.
This is TigerStyle's line between assertions, which detect programmer errors (ZS-DATA-07,
ZS-DATA-09), and operating errors, which must be handled.

Text is parsed with `std.fmt.parseInt` into the narrowest type the field admits, which is the range
check (ZS-OUT-14).

**Why:** `@intCast` and `+` panic, which is right for a programmer error and wrong for adversarial
input: a peer sending a 5-byte length field must not be able to abort your process.

**Check:** trace each `@intCast`, `+`, and `*` back to where its operand entered the process. If it
came from `parseInt`, a socket read, an on-disk header, or a C return value, it must be
`std.math.cast`/`add`/`sub`/`mul` returning an error instead of a builtin that panics.

```zig
// verified — GOOD
const std = @import("std");

/// `record_count` came off the wire, so a size that overflows is the peer's error, not ours.
fn payloadSizeBytes(record_count: u32, record_size_bytes: u32) error{Overflow}!u16 {
    const size_bytes = try std.math.mul(u32, record_count, record_size_bytes);
    return std.math.cast(u16, size_bytes) orelse error.Overflow;
}

test "checked arithmetic and conversion at the boundary" {
    try std.testing.expectEqual(4000, try payloadSizeBytes(100, 40));
    try std.testing.expectError(error.Overflow, payloadSizeBytes(2000, 40)); // fits u32, not u16
    try std.testing.expectError(error.Overflow, payloadSizeBytes(0x8000_0000, 4)); // overflows u32
}
```

### ZS-DATA-11 [M] Convert float to int with `@trunc`/`@round`, after a range check

The unary float builtins convert directly to an integer result type:
`export fn a(x: f64) i32 { return @trunc(x); }` compiles. The langref marks `@intFromFloat`
"Deprecated. Equivalent to @trunc." and nothing else does: it emits no warning, `zig fmt` leaves it
alone, and std still uses it (`std.math.lossyCast` does). It is the less informative spelling, which
is why this rule prefers `@trunc`/`@round`. Whichever you use, an out-of-range value is
safety-checked illegal behavior: `panic: integer part of floating point value out of bounds`. NaN
fails every comparison, so the range guard must be a positive in-range test, not a negated
out-of-range test.

**Why:** float-to-int is two decisions — which direction to round, and what to do about values
outside the destination range. `@intFromFloat` names neither; `@round(x)` names the first, and an
explicit range test names the second.

**Check:** every `@intFromFloat` — legal but deprecated, and its rounding is unstated — and every
`@trunc`/`@round` with an integer result type. Each needs a range guard on a preceding line, spelled
`if (!(x >= lo and x <= hi))` — a guard written `if (x < lo or x > hi)` passes NaN straight through
to the panic.

```zig
// fragment — BAD
const ticks: i32 = @intFromFloat(seconds * 1000.0); // Rounding unstated; NaN/overflow panics.
```

```zig
// verified — GOOD
fn ticksFromSeconds(seconds: f64) ?i32 {
    const ms = seconds * 1000.0;
    // Positive in-range test: NaN fails it, so NaN returns null rather than panicking.
    if (!(ms >= -2147483648.0 and ms <= 2147483647.0)) return null;
    return @round(ms);
}
```

## Struct construction and initialization

### ZS-DATA-12 [M] Write `const x: T = .{ ... }`, not `const x = T{ ... }`

Annotate the declaration and let the initializer be anonymous.

This is Result Location Semantics, not cosmetics. Per the langref's propagation table,
`const value: T = x` gives `x` the result location `&value`, and `.{ .a = x }` forwards that to
`&value.a`; a *typed* initializer `T{ .a = x }` has "**no** result location" for its
sub-expressions. The annotated form is also what enables decl literals (`.empty`, `.init(...)`),
because the result *type* is what makes the leading dot resolve.

**Why:** `const x: T = .{ ... }` desugars to writing each field directly into `x`'s storage, while
`const x = T{ ... }` may build a temporary and copy it.

**Check:** `rg -n '= [A-Z][A-Za-z0-9_.]*\{' -g '*.zig'` finds a `TitleCase` name immediately
followed by a brace on the right of an assignment; each hit is the finding, and becomes an annotated
declaration plus `.{ ... }` or a decl literal.

```zig
// verified — GOOD
const std = @import("std");
const Budget = struct {
    limit_bytes: u64,
    used_bytes: u64,

    pub const empty: Budget = .{ .limit_bytes = 0, .used_bytes = 0 };

    pub fn init(limit_bytes: u64) Budget {
        return .{ .limit_bytes = limit_bytes, .used_bytes = 0 };
    }
};

test "decl literals" {
    const a: Budget = .empty;
    const b: Budget = .init(1024);
    try std.testing.expectEqual(0, a.limit_bytes);
    try std.testing.expectEqual(1024, b.limit_bytes);
}
```

### ZS-DATA-13 [M] Construct std containers with their decl literals

`var list: std.ArrayList(T) = .empty;` is the form. `std.ArrayList` *is* the unmanaged list;
`std.ArrayListUnmanaged` is a deprecated alias for it, and the managed variant is
`std.array_list.Managed(T)`, marked `/// Deprecated.` The allocator is passed per call (ZS-MEM-05),
and `std.ArrayList(T).init(gpa)` does not compile.

Other decl literals in std: `std.MultiArrayList(T) = .empty`,
`std.StringHashMapUnmanaged(V) = .empty`, `std.Deque(T) = .empty`, `std.EnumSet(E) = .empty` /
`.full` (there is no `.initEmpty()` or `.initFull()`), and `std.mem.Alignment = .fromByteUnits(n)`.

**Why:** `.empty` is a `pub const empty: Self` in `array_list.zig`, so it costs nothing at runtime
and works in a struct field default. Keeping the allocator out also lets the container sit in a
`packed`/`extern`-adjacent struct, be memcpy'd, and be stored in a `MultiArrayList`.

**Check:** `ArrayList(`, `HashMap(`, or `MultiArrayList(` followed by `.init(`, and a container
whose fields are spelled out (`.{ .items = …, .capacity = … }`) where `.empty` would do. A call that
passes no allocator is ZS-MEM-05's finding.

```zig
// verified — GOOD
const std = @import("std");
test "arraylist decl literal" {
    const gpa = std.testing.allocator;
    var list: std.ArrayList(u32) = .empty;
    defer list.deinit(gpa);
    try list.append(gpa, 1);
    try list.appendSlice(gpa, &.{ 2, 3 });
    try std.testing.expectEqualSlices(u32, &.{ 1, 2, 3 }, list.items);
}
```

### ZS-DATA-14 [M] Give every allocating type a paired `init`/`deinit` with a matching signature

If `init` (or `.empty` plus an allocating method) took a `gpa`, `deinit` takes the same `gpa`. What
else `deinit` owes — no failure, no allocation, and the poisoning store at the end — is ZS-ERR-16.

**Why:** the allocator is not stored, so `deinit` cannot recover it; passing it back is the contract
std uses throughout.

**Check:** every `pub fn deinit` in a diff takes the same allocator parameter its `init` took. A
`deinit` with no allocator parameter on a type that allocates means the allocator was stored in the
struct instead (ZS-MEM-05).

```zig
// verified — GOOD
const std = @import("std");
const Tree = struct {
    nodes: std.ArrayList(Node),

    const Node = struct { key: u64 };

    pub const empty: Tree = .{ .nodes = .empty };

    pub fn deinit(tree: *Tree, gpa: std.mem.Allocator) void {
        tree.nodes.deinit(gpa);
        tree.* = undefined;
    }
};
```

### ZS-DATA-15 [M] Never build a value out of its own fields through an anonymous initializer

`x = .{ f(x.a), g(x.b) }` is not an atomic assignment. Use `std.mem.swap` or an explicit temporary.

**Why:** `value = .{ a, b }` forwards the result locations `&value[0]` and `&value[1]`, so the
statement desugars to `value[0] = a; value[1] = b;` *in order*. Reading `pair[0]` in the second
element therefore reads the value just written.

**Check:** an assignment whose left-hand name also appears inside the `.{ ... }` on its right —
`x = .{ x.b, x.a }`, `pair = .{ pair[1], pair[0] }`. Every such line is order-dependent and wrong;
`std.mem.swap` or a named temporary is the fix.

```zig
// verified — BAD: this "swap" leaves .{ 2, 2 }
const std = @import("std");
test "anonymous initializer is not atomic" {
    var pair: [2]u32 = .{ 1, 2 };
    pair = .{ pair[1], pair[0] };
    try std.testing.expectEqualSlices(u32, &.{ 2, 2 }, &pair);
}
```

```zig
// verified — GOOD
const std = @import("std");
test "swap" {
    var pair: [2]u32 = .{ 1, 2 };
    std.mem.swap(u32, &pair[0], &pair[1]);
    try std.testing.expectEqualSlices(u32, &.{ 2, 1 }, &pair);
}
```

### ZS-DATA-16 [M] Initialize a self-referential struct in place through an out pointer

Write `pub fn init(x: *T, ...) void { x.* = .{ ... }; }` and call it as
`var x: T = undefined; x.init(...);` rather than returning `T` by value, for a type whose address is
part of its correctness: one that stores a pointer to one of its own fields or hands one out, an
allocator or arena embedded in a larger object, an intrusive list head, a pinned I/O buffer, or
anything registered by address. A struct large enough that the copy matters — on an embedded or
kernel stack, or on a hot path a profile names — is initialized the same way. Any other type may
return by value.

**Why:** a `return T{ ... }` does not propagate the caller's result location, so a value-returning
`init` may build the object in the callee's frame and copy it out, leaving any pointer it stored to
itself dangling. An out pointer fixes the address before the first field is written.

**Check:** a `pub fn init(...) T` returning by value on a type any of whose fields is a pointer into
itself, an `interface` field (ZS-COMPTIME-17), an intrusive node, or a fixed buffer whose address is
handed out. The expected shape at the call site is `var x: T = undefined; x.init(...);`, not
`const x: T = .init(...);`.

```zig
// verified — BAD: `self_ref` ends up pointing into a dead frame
const std = @import("std");
const Engine = struct {
    cursor: usize,
    self_ref: *Engine,
};

fn makeByValue() Engine {
    var engine: Engine = .{ .cursor = 0, .self_ref = undefined };
    engine.self_ref = &engine; // Address of makeByValue's frame.
    return engine; // Copied out; self_ref now dangles.
}

test "value-returning init breaks self-reference" {
    const engine = makeByValue();
    try std.testing.expect(engine.self_ref != &engine);
}
```

```zig
// verified — GOOD
const std = @import("std");
const Arena = struct {
    buffer: [256]u8,
    cursor: usize,
    owner: *Arena,

    pub fn init(arena: *Arena) void {
        arena.* = .{ .buffer = undefined, .cursor = 0, .owner = arena };
    }
};

test "in-place init" {
    var arena: Arena = undefined;
    arena.init();
    try std.testing.expect(arena.owner == &arena);
}
```

### ZS-DATA-17 [M!] In-place initialization is viral — propagate it to every containing struct

If any field of `T` must be initialized in place, `T` itself gets an out-pointer `init`, and so does
anything that embeds a `T` by value. The trigger is ZS-DATA-16's.

*Relaxed form:* ZS-DATA-16's.

**Why:** an out-pointer `init` on the inner type buys nothing if the outer type is still constructed
by value and copied: the inner object's self-pointer would point at the outer temporary.

**Check:** for every type that has an out-pointer `init`, each struct that embeds it by value as a
field must also have an out-pointer `init`; one that still has a value-returning `init` is the break
in the chain, and it is the containing struct that is wrong.

```zig
// fragment — GOOD: `Engine` here is the out-pointer version from ZS-DATA-16
const Server = struct {
    engine: Engine, // Engine.init takes an out pointer, so Server.init must too.
    port: u16,

    pub fn init(server: *Server, port: u16) void {
        server.port = port;
        server.engine.init();
    }
};

test "viral in-place init" {
    var server: Server = undefined;
    server.init(8080);
    try std.testing.expect(server.engine.self_ref == &server.engine);
}
```

### ZS-DATA-18 [S] Pass aggregates larger than 16 bytes as `*const T`

TigerStyle's threshold: if you do not mean the argument to be copied and the type exceeds 16 bytes,
take `*const T`.

This is not about copy cost. The langref is explicit that for structs, unions and arrays "Zig may
choose to copy and pass by value, or pass by reference, whichever way Zig decides will be faster" —
parameters are immutable, so the compiler already elides the copy when it wants to. Passing by value
is fine for small or trivially-copyable aggregates; say so in a comment when the type is large.

**Why:** `*const T` buys identity — the callee provably observes *the caller's* object, so `&arg` is
meaningful and comparable — and a visible `f(&config)` at the call site saying no snapshot was
taken, which is the accidental-copy bug TigerStyle is hunting.

**Check:** every by-value parameter whose type is a struct or an array — run `@sizeOf` on it. Over
16 bytes it needs either `*const T` or a comment on the parameter saying the snapshot is intended.

```zig
// verified — GOOD
const std = @import("std");
const assert = std.debug.assert;
const Config = struct {
    replica_count: u8,
    cluster_id: u128,
    grid_size_bytes: u64,
};

comptime {
    assert(@sizeOf(Config) > 16);
}

fn quorum(config: *const Config) u8 {
    return @divFloor(config.replica_count, 2) + 1;
}
```

## Memory layout

### ZS-DATA-19 [M] Default to plain `struct`; use `extern` for ABI and `packed(uN)` for bits

Three layouts, three jobs:

- `struct` — **no layout guarantee at all**; the compiler reorders fields and pads freely. Use for
  everything that only ever lives in memory.
- `extern struct` — "has in-memory layout matching the C ABI for the target": declaration field
  order, C padding, C alignment. Use for C interop, mmap'd records, on-disk and wire formats.
- `packed struct(uN)` — "exactly the same ABI as their backing integer"; fields are a logical
  sequence of bits, least- to most-significant. Use for bitfields, flag words, MMIO registers.

`@sizeOf` and `@offsetOf` on a default-layout `struct` are not a contract.

Constraints that follow from the table: `packed struct` fields must be integers (exactly their bit
width), `bool` (1 bit), enums (their tag width), `packed union`, or `packed struct`; **pointers are
forbidden** in packed types; and all fields of a `packed union` must have the same `@bitSizeOf`
(`error: field bit width does not match earlier field`).

**Why:** the default layout is unspecified *on purpose* so the compiler can pack fields optimally,
which is what you want everywhere except at a boundary where another party has an opinion about byte
offsets. `extern` or `packed` on an in-memory-only type forfeits that for nothing.

**Check:** every `extern struct` and `packed struct` in a diff must name its boundary — C, disk,
wire, or MMIO — in a doc comment or an adjacent comment. One with no boundary should be a plain
`struct`. In the other direction, `@offsetOf` or `@sizeOf` relied on as a contract over a
default-layout `struct`.

```zig
// verified — GOOD
const std = @import("std");
const assert = std.debug.assert;
const Flags = packed struct(u8) {
    compressed: bool,
    encrypted: bool,
    _reserved: u6 = 0, // Explicit padding: reserved bits are zero, not garbage.
};

comptime {
    assert(@bitSizeOf(Flags) == 8);
    assert(@sizeOf(Flags) == 1);
}

test "packed struct is its backing integer" {
    const f: Flags = .{ .compressed = true, .encrypted = false };
    try std.testing.expectEqual(1, @backingInt(f));
}
```

### ZS-DATA-20 [M] Always spell the backing integer and enum tag type in `extern`/`packed`/`export`

Write `enum(u8)`, `packed struct(u32)`, `packed union(u16)` — never rely on inference in a type that
crosses a boundary. Zig rejects an inferred tag in an extern context outright
(`error: extern structs cannot contain fields of type 'Kind'`,
`note: integer tag type of enum is inferred`), and 0.17's `@backingInt` and `@fromBackingInt` refuse
a packed type whose backing integer is inferred
(`error: @backingInt is ambiguous for type 'Flags'`).

**Why:** even where an inferred tag compiles, its width is a layout decision the compiler is free to
revisit, and an inferred packed backing integer has unspecified signedness.

**Check:** `enum {` with no parenthesized tag type, and `packed struct {` / `packed union {` with no
parenthesized backing integer, anywhere in a file that also contains `extern`, `export`, or a
serialization call.

```zig
// rejected — zig: extern structs cannot contain fields of type 'Kind'
// error: extern structs cannot contain fields of type 'Kind'
// note: integer tag type of enum is inferred
const Kind = enum { a, b };
const Rec = extern struct { kind: Kind, n: u32 };
export fn use(r: Rec) u32 { return r.n; }
```

```zig
// verified — GOOD
const Command = enum(u8) { ping = 1, pong = 2 };

const Message = extern struct {
    command: Command,
    _padding: [3]u8 = @splat(0),
    payload_size_bytes: u32,
};
```

## Containers and data-oriented layout

### ZS-DATA-21 [S] Reference long-lived elements by handle, not by pointer

Store an index newtype (`enum(u32) { none = maxInt(u32), _ }`) and resolve it through the container
at each use. Where you need pointer *stability* rather than handles, ZS-DATA-23 gives the containers
that provide it.

**Why:** handles survive reallocation, are half the size of a pointer, serialize cleanly, and make
"no element" representable without a `?*T`: the reserved `.none` tag replaces a null pointer with a
value the type system can switch on.

**Check:** a `*T`, `?*T`, or `[]T` field stored in a struct that also owns the container those
pointers came from — that pair outlives exactly one append.

```zig
// verified — GOOD
const std = @import("std");
const assert = std.debug.assert;
const NodeIndex = enum(u32) { none = std.math.maxInt(u32), _ };

const Tree = struct {
    nodes: std.ArrayList(Node),

    const Node = struct { key: u64, left: NodeIndex = .none, right: NodeIndex = .none };

    pub const empty: Tree = .{ .nodes = .empty };

    pub fn at(tree: *Tree, index: NodeIndex) *Node {
        assert(index != .none);
        return &tree.nodes.items[@backingInt(index)];
    }

    pub fn add(tree: *Tree, gpa: std.mem.Allocator, key: u64) std.mem.Allocator.Error!NodeIndex {
        const index: u32 = @intCast(tree.nodes.items.len);
        try tree.nodes.append(gpa, .{ .key = key });
        return @fromBackingInt(index);
    }
};
```

### ZS-DATA-22 [S] Use `std.MultiArrayList` when hot loops read a subset of the fields

`MultiArrayList(T)` stores one array per field (struct-of-arrays) behind one allocation. Access
whole columns with `.items(.field)`, or take `.slice()` once and pull several columns from it.

It has two costs: `get(i)`/`set(i)` reassemble the struct field by field, and you cannot take a `*T`
to an element at all, so it is the wrong choice when elements are handled one at a time or passed
around by pointer. A plain `ArrayList` stays the default; reach for `MultiArrayList` when a profile
names a column-scan workload.

**Why:** an array-of-structs loop that reads one `f32` out of a 12-byte element brings the other 8
bytes into cache on every iteration and defeats vectorization. SoA makes the hot column contiguous,
and since padding is per column rather than per element, mixed field alignments shrink the total.

**Check:** in both directions. A `for (list.items) |item|` that touches only one or two fields of a
multi-field element, on a path with a measurement behind it, is the `MultiArrayList` case. A
`MultiArrayList` whose call sites use `get(i)`/`set(i)` more often than `items(.field)` is paying
the reassembly cost for nothing and should be a plain `ArrayList`.

```zig
// verified — GOOD
const std = @import("std");
const Row = struct { id: u32, score: f32, live: bool };

test "column scan" {
    const gpa = std.testing.allocator;
    var rows: std.MultiArrayList(Row) = .empty;
    defer rows.deinit(gpa);
    try rows.setCapacity(gpa, 2); // exactly 2: `ensureTotalCapacity` would round the bound up
    rows.appendAssumeCapacity(.{ .id = 1, .score = 0.5, .live = true });
    rows.appendAssumeCapacity(.{ .id = 2, .score = 1.5, .live = false });

    const s = rows.slice();
    var sum: f32 = 0;
    for (s.items(.score), s.items(.live)) |score, live| {
        if (live) sum += score;
    }
    try std.testing.expectEqual(0.5, sum);
}
```

### ZS-DATA-23 [M] Build a fixed-capacity list with `ArrayList.initBuffer`; get stable addresses from a pool or a list

`std.BoundedArray` and `std.SegmentedList` do not exist. For a fixed-capacity list, use
`std.ArrayList(T).initBuffer(&backing)` plus the `AssumeCapacity` / `Bounded` methods. For pointer
stability across growth, use an intrusive `std.DoublyLinkedList` or `std.SinglyLinkedList` with
nodes owned by an arena, or `std.heap.MemoryPool(T)` (ZS-MEM-14).

`appendAssumeCapacity` asserts, so a bug crashes; `appendBounded` returns `error{OutOfMemory}`, so
an operating error is handled. std's linked lists are intrusive: the list holds `?*Node`, the node
holds only `prev`/`next`, and you recover the payload with `@fieldParentPtr`.

**Why:** `initBuffer` sets capacity from the buffer and documents that "all functions that accept an
Allocator argument cause illegal behavior", so the list cannot allocate by construction —
TigerStyle's static-allocation rule, expressed in modern std.

**Check:** each fixed-capacity list picked the right failure mode: `*AssumeCapacity` where overflow
is a programmer error, `append*Bounded` where the size came from outside.

```zig
// rejected — zig: root source file struct 'std' has no member named 'BoundedArray'
const std = @import("std");
pub fn fill() !void {
    var list: std.BoundedArray(u32, 4) = .{};
    try list.append(1);
}
```

```zig
// verified — GOOD
const std = @import("std");
test "fixed-capacity list" {
    var backing: [4]u32 = undefined;
    var list: std.ArrayList(u32) = .initBuffer(&backing);
    list.appendAssumeCapacity(1); // Overflow here is a bug: asserts.
    try list.appendBounded(2); // Overflow here is expected: returns error.OutOfMemory.
    try std.testing.expectEqualSlices(u32, &.{ 1, 2 }, list.items);
}
```

```zig
// verified — an intrusive list: stable addresses
const std = @import("std");
const Job = struct {
    node: std.DoublyLinkedList.Node = .{},
    id: u32,
};

test "intrusive list" {
    var queue: std.DoublyLinkedList = .{};
    var a: Job = .{ .id = 1 };
    var b: Job = .{ .id = 2 };
    queue.append(&a.node);
    queue.append(&b.node);

    var total: u32 = 0;
    var it = queue.first;
    while (it) |node| : (it = node.next) {
        const job: *Job = @fieldParentPtr("node", node);
        total += job.id;
    }
    try std.testing.expectEqual(3, total);
}
```

### ZS-DATA-24 [S] Prefer a fixed array when the bound is comptime-known

A `[N]T` field, or `[N]?T` when slots can be empty, beats any list when `N` is a constant.

**Why:** no allocator, no failure path, no `deinit`, no pointer invalidation, and the size shows up
in `@sizeOf` where a comptime assertion can pin it. `@splat` initializes the whole array in one
expression. TigerStyle's "put a limit on everything" is easiest to obey when the limit is the type.

**Check:** an `ArrayList` field whose every append is guarded by a comptime constant, and a `deinit`
whose only job is to free a container with a constant maximum. Both are `[N]T` written the long way.

```zig
// verified — GOOD
const Cache = struct {
    entries: [16]?u64 = @splat(null),

    fn put(cache: *Cache, slot: u4, value: u64) void {
        cache.entries[slot] = value; // `u4` makes an out-of-range slot unrepresentable.
    }

    fn get(cache: *const Cache, slot: u4) ?u64 {
        return cache.entries[slot];
    }
};
```

## Modeling with enums, unions, and optionals

### ZS-DATA-25 [M] Model variants as a tagged union, not a struct with a kind field

A value that is "one of N shapes" is a `union(enum)`, not a struct with a kind field and several
maybe-valid members. Switch over it exhaustively (ZS-ERR-27). Reading a payload field while another
is active is safety-checked illegal behavior
(`access of union field 'b' while field 'a' is active`).

**Why:** a payload is reachable only through its active tag, never as stale bytes, and adding a
variant is a compile error at every exhaustive switch that must change.

**Check:** any struct pairing a `kind`/`tag`/`type` enum field with members that are only meaningful
for some values of it — that is a tagged union written without the compiler's help.

```zig
// fragment — BAD
const Op = struct {
    kind: enum { nop, push, jump },
    value: u32, // Meaningful for `.push` and `.jump` only.
    conditional: bool, // Meaningful for `.jump` only.
};
```

```zig
// verified — GOOD
const Op = union(enum) {
    nop,
    push: u32,
    jump: struct { target: u32, conditional: bool },
};

fn opcodeWidth(op: Op) usize {
    return switch (op) {
        .nop => 1,
        .push => 5,
        .jump => 6,
    };
}
```

### ZS-DATA-26 [M] Make an enum non-exhaustive only for values that come from outside

Add a trailing `_` field (which requires an explicit integer tag type) when the integer comes from a
peer, a file, or a kernel, and switch on it with a `_ =>` prong (ZS-ERR-27). With `_`,
"`@fromBackingInt` on a non-exhaustive enum always results in a valid enum value"; its operand must
already have the tag type, so the only check left is the `@intCast` that narrows a wider wire
integer to it. A non-exhaustive enum without a tag type is
`error: non-exhaustive enum missing integer tag type`.

**Why:** without `_`, `@fromBackingInt` of an unrecognized value is safety-checked illegal behavior,
so a remote peer could crash you by sending opcode 99.

**Check:** every `@fromBackingInt` (or `@enumFromInt`, its deprecated spelling) whose argument came
from a file, a socket, a C call, or a command line — the target enum must carry a trailing `_`.
Conversely, a trailing `_` on an enum whose values you alone produce.

```zig
// verified — GOOD
const std = @import("std");
const Syscall = enum(u16) {
    read = 0,
    write = 1,
    open = 2,
    _,
};

fn isIo(s: Syscall) bool {
    return switch (s) {
        .read, .write => true,
        .open => false,
        _ => false, // Unknown wire value. Adding a named tag still breaks the build here.
    };
}

test "unknown tag is well defined" {
    try std.testing.expect(!isIo(@fromBackingInt(9999)));
}
```

### ZS-DATA-27 [M] Return the lowest-dimensionality type that can carry the answer

This rule owns the dimensionality ladder for the whole standard, and ZS-DATA-28 (optional for
absence, error union for failure) resolves the top two rungs.

TigerStyle's ordering, weakest first — each rung is a strict superset of the one below:

| Return type | What it adds | Cost imposed on every caller |
|---|---|---|
| `void` | nothing | none |
| `bool` | one bit of outcome | one `if` |
| `u64` | a magnitude | arithmetic, and a range the caller must trust |
| `?u64` | "no answer" as a distinct state | `orelse` / `if (x) \|v\|` unwrap at every use |
| `!u64` | *why* there was no answer | `try`/`catch`, plus an error set in every signature above |

Take the lowest rung that can carry the answer, and climb only when the extra dimension carries
information the caller must act on.

Three specific reductions, in descending order of payoff:

- A function whose error set is empty in practice returns `T`, not `!T`. If it can only fail through
  the allocator, say `error{OutOfMemory}!T` rather than an inferred `!T`, so the set does not grow
  silently (ZS-ERR-03).
- A `?T` whose `null` the caller can only turn back into a default belongs behind a function that
  applies the default and returns `T`.
- A `bool` that every caller immediately switches on, alongside other state, is usually an enum or a
  tagged union (ZS-DATA-25) — that is climbing *sideways*, not up, and it costs nothing.

This is not a licence to hide failures. If the caller must distinguish outcomes, the dimension is
real and removing it is worse than paying for it: swallowing an error into a `bool` or a sentinel is
the bug ZS-DATA-28 exists to prevent. The rule is about removing dimensions that carry *no*
information.

**Why:** each rung up multiplies the branches every caller must write, and dimensionality is viral:
a `!void` that cannot fail forces `try` at every call site and an error set into every caller's
signature, for nothing. `E!T` costs most, because it reaches every transitive caller.

**Check:** in a diff, flag every new `!` and every new `?` in a return type. For `!T`, the body must
contain a `return error.…` or a `try` that can actually fail. For `?T`, at least one caller must do
something other than `orelse <constant>`. Flag `!void` and `!bool` returns hardest — those are the
two that are almost always one rung too high.

```zig
// fragment — BAD
fn clear(registry: *Registry) !bool { // Cannot fail; the bool is always true.
    registry.names = @splat("");
    return true;                      // Every caller now writes `_ = try clear(&r);`.
}
```

```zig
// verified — GOOD
const std = @import("std");
const Registry = struct {
    names: [4][]const u8 = @splat(""),

    fn clear(registry: *Registry) void {
        registry.names = @splat("");
    }

    /// `?[]const u8`, not `![]const u8`: a miss is an ordinary outcome with no reason to report.
    fn find(registry: *const Registry, slot: usize) ?[]const u8 {
        if (slot >= registry.names.len) return null;
        const name = registry.names[slot];
        return if (name.len == 0) null else name;
    }

    /// `[]const u8`, not `?[]const u8`: the default is applied here, once, not at every call site.
    fn nameOr(registry: *const Registry, slot: usize, fallback: []const u8) []const u8 {
        return registry.find(slot) orelse fallback;
    }
};

test "dimensionality" {
    var registry: Registry = .{};
    registry.names[1] = "primary";
    registry.clear();
    try std.testing.expectEqualStrings("none", registry.nameOr(1, "none"));
    // A slot past the end is what makes the return type `?[]const u8` rather
    // than `[]const u8`: a miss, not a panic. Without this case the bounds
    // guard can be deleted and the test still passes.
    try std.testing.expectEqualStrings("none", registry.nameOr(4, "none"));
}
```

### ZS-DATA-28 [M] Express absence with the weakest construct that fits

- **Optional `?T`** — absence is an ordinary, expected outcome the caller inspects (lookup miss,
  empty queue, unset field). One extra branch, no error set.
- **Error union `E!T`** — absence is a failure with a *reason* the caller may need to distinguish or
  propagate. Costs an error set in every signature above it.
- **Sentinel value** — only when an external format mandates it (`-1` from a C API, `0xFFFF_FFFF` as
  a reserved id, NUL-terminated bytes). Wrap it into a `?T` or a handle enum at the boundary and
  never let the raw sentinel travel inward.
- **`?*T`** — a nullable pointer. Zig lays this out as a plain pointer with null represented by
  address zero, so it costs nothing; never hand-roll `@ptrFromInt(0)`.

**Why:** an optional is one bit the compiler forces you to unwrap; an error union drags a set
through every caller and blocks `orelse`-style defaulting; a raw sentinel is invisible to the type
system. Pick by whether the caller needs a *reason*.

**Check:** a magic return value (`-1`, `0`, `maxInt`) whose meaning lives in a comment rather than
in a `?T` or a handle enum; an `E!T` whose set has one member that every caller turns straight into
`null` or a default — on a lookup, an error named `NotFound`, `Missing`, `Empty`, `NoSuchKey`, or
`Absent` is almost always a `?T` written as an `E!T`; and a `@ptrFromInt(0)` or a `0` compared
against a pointer.

```zig
// fragment — BAD: a cache miss is not a failure
fn get(cache: *const Cache, key: u32) error{NotFound}!u32 { ... }
// Every caller now writes `catch |e| switch (e) { error.NotFound => ... }`.
```

```zig
// verified — GOOD
const std = @import("std");
fn findScalarIndex(haystack: []const u8, needle: u8) ?usize {
    return std.mem.findScalar(u8, haystack, needle); // Miss is normal: optional.
}
```

### ZS-DATA-29 [M] `[]const u8` is the default string; `[:0]const u8` only where a NUL is required

Use a sentinel-terminated slice or pointer at a C boundary and nowhere else. `[:0]const u8` coerces
to `[]const u8` for free; the reverse requires an allocation. Keep the NUL at the edge;
ZS-INTEROP-10 gives the conversion for each direction. Slicing with `data[a..b :0]` asserts the
sentinel at runtime (`panic: sentinel mismatch: expected 0, found 1`).

**Why:** the sentinel is a guarantee you must maintain, so a `[:0]` in an internal API forces every
intermediate function to preserve a terminator it does not use.

**Check:** `[:0]const u8` or `[*:0]` in a signature that is not `extern`, `export`, or a direct
`std.c.*` call. Also `[a..b :0]` in internal code — that slice asserts the sentinel at runtime and
will panic on a string that was never terminated.

```zig
// fragment — BAD
fn parseHeader(name: [:0]const u8) !Header { // Nothing here needs the NUL, but every
    ...                                      // caller must now produce one.
}
```

```zig
// verified — GOOD
const std = @import("std");
fn openPath(gpa: std.mem.Allocator, path: []const u8) !c_int {
    const path_z = try gpa.dupeSentinel(u8, path, 0); // Add the NUL only at the C boundary.
    defer gpa.free(path_z);
    return std.c.open(path_z.ptr, .{});
}
```

## Text: UTF-8, WTF-8, and ASCII

ZS-DATA-29 settles the *slice* question for strings. These four rules settle the *encoding*
question. `[]const u8` in Zig is a byte slice and nothing more — no type in the language records
that a byte slice is valid UTF-8, so the discipline is entirely yours.

### ZS-DATA-30 [M] A byte index is not a codepoint index; iterate with `Utf8View`

`text.len` is a size in bytes. To count codepoints, call `std.unicode.utf8CountCodepoints`, which
validates as it counts. To visit them, validate once with `std.unicode.Utf8View.init` (returns
`error.InvalidUtf8`) and walk the `Utf8Iterator` it hands out. Never divide, slice, or truncate a
UTF-8 string at an arbitrary byte offset.

There are *three* units, not two:

- **byte** — what `[]const u8` indexes, what `@sizeOf` and `readFileAlloc` count, what a length
  prefix on the wire almost always means. 1 to 4 bytes per codepoint in UTF-8.
- **codepoint** (`u21`) — what `Utf8Iterator.nextCodepoint` yields. Not a character: `é` may be one
  codepoint (U+00E9) or two (U+0065 U+0301), and both render identically.
- **grapheme cluster** — what a user calls a character. std has **no** grapheme segmentation; if you
  need cursor movement, column counts, or truncation-for-display, that is a third-party library.

Name the variable for its unit — `size_bytes`, `codepoint_count`, `byte_index` — per ZS-DATA-04.

`std.unicode.utf8Decode` and `std.unicode.wtf8Decode` are both marked "Deprecated. This function has
an awkward API that is too easy to use incorrectly" — they take a `[]const u8` whose length they
*assert* rather than check, so a caller who guesses the length wrong gets `unreachable`. Replace
them with the iterator, or, when you already hold a fixed-size array, with the checked `utf8Decode2`
/ `utf8Decode3` / `utf8Decode4` (and `utf8Decode3AllowSurrogateHalf` for WTF-8), whose parameter
types are `[2]u8` / `[3]u8` / `[4]u8` and therefore cannot be given a wrong length.

**Why:** this is ZS-DATA-04's index/count/size confusion applied to text, and the name is the only
guard rail, because `usize` is `usize`. Slicing at a byte offset the iterator did not give you
splits a codepoint in half and yields bytes that are not UTF-8.

**Check:** in a diff, flag `utf8Decode(` and `wtf8Decode(` (deprecated), any `[i]` or `[a..b]` on a
string where the bound did not come from an iterator, and any variable named `len`/`count` holding a
text length without a unit in its name.

```zig
// verified — GOOD
const std = @import("std");
test "bytes are not codepoints" {
    const text = "café";
    try std.testing.expectEqual(5, text.len); // size_bytes
    try std.testing.expectEqual(4, try std.unicode.utf8CountCodepoints(text)); // codepoint_count
}

test "visit codepoints through a validated view" {
    const view = try std.unicode.Utf8View.init("café"); // Validates the whole slice, once.
    var it = view.iterator();
    var last: u21 = 0;
    while (it.nextCodepoint()) |codepoint| last = codepoint;
    try std.testing.expectEqual(0xE9, last);
}

test "decode one codepoint without the deprecated API" {
    const bytes = "é";
    try std.testing.expectEqual(2, try std.unicode.utf8ByteSequenceLength(bytes[0]));
    try std.testing.expectEqual(0xE9, try std.unicode.utf8Decode2(bytes[0..2].*));
}
```

### ZS-DATA-31 [M] Windows filenames are WTF-8, not UTF-8 — use the `wtf8` family for paths

A Windows path is a sequence of arbitrary `u16` values, which may contain unpaired surrogates and is
therefore not always valid UTF-16 and has no UTF-8 encoding. Convert with
`std.unicode.wtf8ToWtf16Le*` / `wtf16LeToWtf8*` and validate with `wtf8ValidateSlice`. Use
`Wtf8View` / `Wtf8Iterator` when you must iterate one. Convert down to UTF-8 explicitly and lossily
— `wtf8ToUtf8Lossy` — only at the point where you hand the text to something that demands UTF-8. On
a surrogate, `utf8ToUtf16Le` returns `error.InvalidUtf8`, and the UTF-8 path would silently
substitute U+FFFD, producing a name that does not open the file. The same applies to WASI and to any
OS string you did not create yourself.

**Why:** WTF-8 is UTF-8 extended to encode the surrogate range U+D800..U+DFFF, so it round-trips
every legal NTFS name and UTF-8 cannot. Using the `utf8` family on a path is a bug that only fires
on the user's machine, with the user's files.

**Check:** any `utf8ToUtf16Le*` / `utf16LeToUtf8*` call whose argument is a path, a filename, an
environment variable, or a command-line argument should be the `wtf8`/`wtf16Le` spelling instead.

```zig
// verified — GOOD
const std = @import("std");
test "wtf8 round-trips an unpaired surrogate; utf8 cannot" {
    const gpa = std.testing.allocator;
    const name_w = [_]u16{ 'a', 0xD800, 'b' }; // Lone high surrogate: a legal NTFS name.
    const wtf8 = try std.unicode.wtf16LeToWtf8Alloc(gpa, &name_w);
    defer gpa.free(wtf8);
    try std.testing.expect(!std.unicode.utf8ValidateSlice(wtf8));
    try std.testing.expect(std.unicode.wtf8ValidateSlice(wtf8));

    const back = try std.unicode.wtf8ToWtf16LeAlloc(gpa, wtf8);
    defer gpa.free(back);
    try std.testing.expectEqualSlices(u16, &name_w, back);
}
```

### ZS-DATA-32 [M] `std.ascii` operates on bytes; never let it stand in for Unicode

`std.ascii.toUpper`, `toLower`, `upperString`, `lowerString`, `eqlIgnoreCase`, `isAlphabetic`,
`isWhitespace` and friends all take `u8` and only understand code units below 128. Use them for
protocol tokens, identifiers, hex digits, and HTTP header names. Do not use them on human text. std
has no Unicode case mapping or collation at all; correct casing is locale-dependent (Turkish dotless
ı, German ß) and needs a library.

This is a live caveat on ZS-CONC-15, whose `drain` example uppercases every byte passing through a
`Writer` with `std.ascii.toUpper`. As a demonstration of the `drain` contract it is correct; as a
text transform it is ASCII-only, and a stream carrying UTF-8 will pass through half-uppercased.

**Why:** they are safe but silent. No UTF-8 lead byte (0xC2..0xF4) or continuation byte (0x80..0xBF)
falls in `'a'..'z'`, so the encoding survives, but every non-ASCII letter is left alone: `"café"`
uppercases to `"CAFé"` and the bug ships.

**Check:** every `std.ascii.` call in a diff needs an answer to "where did these bytes come from?"
Protocol/format bytes: fine. Anything a human typed: flag it.

```zig
// verified — BAD: this is what "silently incomplete" looks like
const std = @import("std");
test "ascii case mapping silently ignores non-ascii" {
    var buffer: [8]u8 = undefined;
    const out = std.ascii.upperString(buffer[0.."café".len], "café");
    try std.testing.expectEqualStrings("CAFé", out); // Not "CAFÉ".
}
```

## Arithmetic and type-system rules with silent-wrong-code potential

The migration table holds every spelling that changed. The two rules below cover only the entries
that produce **wrong behavior rather than a compile error**, because this is the chapter a reader
consults when choosing a type — not the one they consult when a build breaks.

### ZS-DATA-33 [M] `std.math.sign` returns the narrowest integer, not the argument's type

`sign` returns `SignOf(@TypeOf(n))`: `i2` for a signed integer *or a float*, `u1` for an unsigned
integer, and the elementwise equivalent for a vector. It does not return `T`. Convert explicitly at
the point of use, or skip `sign` entirely and write the branch: for floats
`std.math.copysign(magnitude, x)` says what you actually meant, and `std.math.order(a, b)` gives a
three-way comparison as an enum rather than as an integer.

**Why:** `magnitude * std.math.sign(x)` on floats reads as an `f64 * f64` multiply, but the right
operand is an `i2`, so the expression is either a compile error or, where a `comptime_int` or a
coercion is in play, a silently different computation.

**Check:** every `std.math.sign` in a diff. If its result is multiplied by, added to, or compared
against a value of the argument's type, the conversion must be written out.

```zig
// verified — GOOD
const std = @import("std");
test "sign returns the narrowest int, never the input type" {
    try std.testing.expectEqual(i2, @TypeOf(std.math.sign(@as(i32, -5))));
    try std.testing.expectEqual(u1, @TypeOf(std.math.sign(@as(u32, 5))));
    try std.testing.expectEqual(i2, @TypeOf(std.math.sign(@as(f64, -0.5))));

    // The float case needs an explicit conversion back; it is not an f64 any more.
    const magnitude: f64 = 3.0;
    const signed = magnitude * @as(f64, @floatFromInt(std.math.sign(@as(f64, -0.5))));
    try std.testing.expectEqual(-3.0, signed);
}
```

### ZS-DATA-34 [M] Check type-level code against the five rules older Zig code trips on

The migration table holds every removed spelling. Of these five, two change what code that *still
compiles* means, one is a cast that can lose a bound, and two turn latent bugs into compile errors.

1. **`*u8` and `*align(1) u8` are distinct types**, though `*u8` still coerces to `*align(1) u8`.
   `@TypeOf` comparisons, `switch` on a type, `std.meta.eql` over type values, and any hand-rolled
   type dispatch that assumed they were equal now take a different branch.
2. **`@ptrCast` can produce a slice from a single-item pointer.** `const s: []u8 = @ptrCast(&arr);`
   compiles and derives `len` from the array length. Convenient, and a way to lose a bound — prefer
   `&arr` coercion or `arr[0..]`, which cannot pick the wrong length.
3. **A zero-bit tuple field is not implicitly `comptime`.** `struct { void, u32 }` reports
   `field_attrs[0].@"comptime" == false`, so reflection that filters fields on that flag to skip
   zero-bit members sees them.
4. **Non-scalar sentinels are forbidden** — `[3:S{ .a = 0 }]S` is
   `error: non-scalar sentinel type 'S'`. Sentinels are limited to scalars; a struct terminator has
   to become a length prefix or an `?T`.
5. **`@memcpy` requires in-memory-coercible operands and checks aliasing at comptime.**
   `@memcpy(target_u8, source_i8)` is
   `error: pointer element type 'i8' cannot coerce into element type 'u8'`, and overlapping operands
   in a comptime call are `error: '@memcpy' arguments alias`. At runtime overlap is illegal behavior
   and undetected — use `@memmove` when ranges overlap. (`std.mem.copyForwards` / `copyBackwards`
   are deprecated and are a review finding under ZS-MEM-23; they also push the direction choice onto
   you, and picking the wrong one smears the first element across the range with no diagnostic in
   any build mode.)

**Why:** items 1 and 3 change the result of type-level metaprogramming that still compiles; item 2
is a cast that compiles and can lose a bound; items 4 and 5 turn latent bugs into diagnostics, which
is worth knowing so the diagnostic is not "fixed" by casting around it.

**Check:** five questions, one per item — a `@ptrCast` whose destination is a slice type;
`@"comptime"` used to filter fields; `std.meta.eql`, `switch`, or `==` over `type` values where
alignment could differ; a non-scalar sentinel in an array type; and `@memcpy` on two ranges derived
from the same backing buffer.

```zig
// verified — GOOD
const std = @import("std");
const assert = std.debug.assert;
test "pointer and builtin rules" {
    try std.testing.expect(*u8 != *align(1) u8); // Distinct types...
    var x: u8 = 7;
    const p: *u8 = &x;
    const q: *align(1) u8 = p; // ...but *u8 still coerces to *align(1) u8.
    try std.testing.expectEqual(7, q.*);

    var array: [4]u8 = .{ 1, 2, 3, 4 };
    const slice: []u8 = @ptrCast(&array); // Single-item pointer -> slice.
    try std.testing.expectEqual(4, slice.len);

    const tuple: struct { void, u32 } = .{ {}, 5 };
    comptime assert(!@typeInfo(@TypeOf(tuple)).@"struct".field_attrs[0].@"comptime");
}
```

## Serialization

### ZS-DATA-35 [M] ZON for formats you own, `std.json` for interop; bound both on untrusted input

For configuration, fixtures, and any data format whose only consumer is your own program, use ZON:
`std.zon.parse.fromSlice(T, .{ .gpa, .arena, .source, .diagnostics })` to read,
`std.zon.stringify.serialize(val, options, w)` to write, and `@import("config.zon")` to embed one at
compile time as a typed value with no parser in the binary at all. Reach for `std.json` only when
something outside your tree demands JSON.

Since 0.17 the call names the result's owner: `fromSlice` allocates the result's pointers, and the
diagnostics, into the `.arena` you pass, so the arena owns the value and nothing is freed piecemeal;
`fromSliceNoAlloc` asserts at *comptime* that the destination type contains no pointers, so its
result outlives that arena.

Two constraints apply to both formats:

- **Both write through a `*std.Io.Writer`** after Writergate —
  `std.zon.stringify.serialize(val, opts, w)` and `std.json.Stringify`. There is no `toString`-style
  allocating shortcut in the blessed path, so the buffering and flushing rules (ZS-CONC-04) apply
  unchanged.
- **Both need an explicit `Io.Limit` on untrusted input.** Neither parser bounds the *source* it is
  handed; the bound belongs on the read that produced the slice. See ZS-CONC-13 — spell
  `.limited(n)` with a justified `n`, and reserve `.unlimited` for bytes you produced yourself.

Note the spellings, which are not symmetric with `std.json`: the ZON serializer namespace is
lowercase `std.zon.stringify` (with `serialize`, `serializeMaxDepth`, `serializeArbitraryDepth`),
and the incremental type is `std.zon.Serializer`. There is no `std.zon.Stringify`; that spelling is
`std.json.Stringify`.

**Why:** ZON is a subset of Zig's own grammar, so a ZON file is checked against your struct type: an
unknown field is `error.ParseZon` with a source location in the required `Diagnostics`, not a
silently ignored key. An `@import`ed `.zon` file has no runtime failure path at all.

**Check:** a new `std.json` dependency in a diff needs a named external consumer; otherwise it
should be ZON. Every `parse.fromSlice` needs an `.arena` that outlives the value it returns; a
result type with no pointers reads better as `parse.fromSliceNoAlloc`, which lets the arena go
first. Every parse of bytes from a file, socket, or subprocess needs the `Io.Limit` on the read that
produced them.

```zig
// verified — GOOD
const std = @import("std");
const Config = struct {
    replica_count: u8,
    grid_size_bytes: u64,
};

test "zon round trip" {
    const gpa = std.testing.allocator;
    var arena_state: std.heap.ArenaAllocator = .init(gpa);
    defer arena_state.deinit();

    // `fromSliceNoAlloc` asserts at comptime that `Config` holds no pointers, so the
    // result outlives the arena. A type with pointers uses `fromSlice`, and the arena
    // owns its result.
    const source: [:0]const u8 = ".{ .replica_count = 6, .grid_size_bytes = 4096 }";
    var diagnostics: std.zon.parse.Diagnostics = undefined;
    const config = try std.zon.parse.fromSliceNoAlloc(Config, .{
        .gpa = gpa,
        .arena = arena_state.allocator(),
        .source = source,
        .diagnostics = &diagnostics,
    });
    try std.testing.expectEqual(6, config.replica_count);

    var buffer: [64]u8 = undefined;
    var w: std.Io.Writer = .fixed(&buffer);
    try std.zon.stringify.serialize(config, .{ .whitespace = false }, &w);
    try std.testing.expectEqualStrings(
        ".{.replica_count=6,.grid_size_bytes=4096}",
        w.buffered(),
    );
}
```

## Symmetry of an API surface

### ZS-DATA-36 [M] Give every operation its inverse, or document why there is none

`init` implies `deinit` (ZS-DATA-14 is this rule's most important instance), but so does
`append`/`pop`, `open`/`close`, `encode`/`decode`, `acquire`/`release`, `register`/`unregister`.

**Why:** a caller who learns half a pair assumes the other half exists. When it is genuinely absent,
the absence is meaningful — the operation is lossy, the handle is consumed, the resource is owned
elsewhere — and silence reads as an oversight that gets worked around.

**Check:** list the public operations on each type in pairs. Every unpaired one either gains its
inverse or gains a doc comment saying why it cannot have one.

### ZS-DATA-37 [M] Keep parameter order identical across sibling functions

Fix the order once and do not vary it: if one function takes `(io, gpa, target, source)`, its
siblings do too. ZS-NAME-10 fixes the order for function-value slots by copying `std.sort`; this
rule is the same discipline applied to your own functions.

**Why:** siblings are called from the same code, often adjacent, and the reader generalizes from the
first one they learn. When the types match, an inconsistent order compiles, so the failure is a
silently swapped argument at a call site that looks correct.

**Check:** list every function in the file taking two or more parameters of related type and compare
their orders. Any disagreement is the finding, and the outlier is what changes.

### ZS-DATA-38 [M] Split a function rather than adding a mode parameter

When a parameter selects behavior rather than supplying data, the function has become two functions
sharing a body. Split it and let the shared part be a private helper.

**Why:** a mode parameter makes the return type and the error set the union of both modes, so every
caller handles cases that cannot arise in its mode — the opposite of ZS-DATA-27. Splitting gives
each caller a precise signature and makes the shared logic explicit.

**Check:** for each parameter, does the body branch on it at the top level? If the two branches
share little, it is two functions with two names.
