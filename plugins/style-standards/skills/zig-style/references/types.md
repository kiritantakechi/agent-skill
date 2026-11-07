# Types

Scope: how a type states what a seam needs and what a set lists: the interface shape chosen before
the type that provides it, a closed set kept a tagged union, a `switch` over it that names every
member, the contract of an `anytype`, and how far a parameter is generic. How a type function is
written, what `comptime` evaluates and how an interface is built (vtable, `@fieldParentPtr`) are the
comptime chapter's; how a value is shaped is the data chapter's; what a public function accepts is
the API chapter's.

The discipline here is **interface-first**: pick which of Zig's three interface shapes fits —
comptime duck typing, runtime vtable, or tagged union — name it, and write the concrete type against
it. TigerStyle advises the opposite: "only a minimum of excellent abstractions", introduced once a
second implementation exists. Interface-first buys a boundary that is total and symmetric because no
concrete type shaped it, and abstractions are never zero-cost: a comptime abstraction costs binary
size and compile time, a vtable costs an indirect call and an optimization barrier. Deciding the
shape early does not remove those costs; it means choosing which one you pay.

## Contents

- **Interfaces and closed sets**
  - ZS-TYPE-01 [M] Pick the interface shape from this table before writing any dispatch code
  - ZS-TYPE-02 [M] A closed set of implementations is a tagged union, not an interface
  - ZS-TYPE-03 [M] Switch exhaustively with no `else`; use `_` on non-exhaustive enums
- **Generics**
  - ZS-TYPE-04 [M] `anytype` in a public API needs a documented contract and a guard
  - ZS-TYPE-05 [S] Prefer a concrete parameter type, then `comptime T: type`, then `anytype`

---

## Interfaces and closed sets

### ZS-TYPE-01 [M] Pick the interface shape from this table before writing any dispatch code

Zig has three shapes, plus one variant of the vtable shape. Choosing wrong is expensive to undo, so
choose before the concrete type exists: a boundary extracted from an existing type inherits its
accidents — its error set, its parameter order, its assumption that a handle is always available —
where one shaped against the caller's need is total and symmetric.

| Shape | Dispatch | Storable in a container? | Errors surface at | Use when |
|---|---|---|---|---|
| comptime duck typing (`anytype` / `comptime T`) | none, monomorphized | no — each impl is a distinct type | inside the callee body | one impl, hot, local; the whole call chain is comptime-known |
| runtime vtable (`*anyopaque` + `*const VTable`) | one indirect call | yes, single concrete type | at the call site | open set of impls; crosses a module or plugin boundary |
| embedded interface + `@fieldParentPtr` | indirect call, but only on the slow path | yes (`*Interface`) | at the call site | the interface owns a buffer/state the caller touches directly |
| tagged union + exhaustive `switch` | one jump table, inlinable | yes | at the call site | closed set known at compile time |

**Why:** the axis that matters is *who knows the set of implementations*. Comptime duck typing
cannot be stored, returned as a common type, or crossed over an ABI boundary; a vtable gives up
inlining to gain those three; a tagged union has storability and inlining for a closed set.

**Check:** a diff that picks a row whose "use when" column is false for it. Two mechanical tells: an
`anytype` or `comptime T` interface whose values are later stored in a struct field, a container, or
a common return type — comptime duck typing cannot be stored; and a new `*const VTable` over a set
of implementations that all live in your own tree — that is ZS-TYPE-02's tagged union.

### ZS-TYPE-02 [M] A closed set of implementations is a tagged union, not an interface

If every implementation is known at compile time and lives in your own tree, model it as
`union(enum)` with methods that `switch` exhaustively (ZS-TYPE-03). `std.Build.LazyPath` is the
canonical std example.

**Why:** the switch is a jump table the optimizer can see through and often inline, and the union
value can live in an array, so you keep storability, direct calls and exhaustiveness at once.
Dynamic dispatch over a known set pays an indirect call for nothing.

**Check:** a new `vtable: *const VTable` — enumerate its implementations. If every one lives in your
own tree, it is a `union(enum)`.

```zig
// verified — GOOD
const std = @import("std");

pub const Shape = union(enum) {
    circle: struct { r: f64 },
    rect: struct { w: f64, h: f64 },

    pub fn area(shape: Shape) f64 {
        return switch (shape) {
            .circle => |c| std.math.pi * c.r * c.r,
            .rect => |r| r.w * r.h,
        };
    }
};
```

### ZS-TYPE-03 [M] Switch exhaustively with no `else`; use `_` on non-exhaustive enums

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

## Generics

### ZS-TYPE-04 [M] `anytype` in a public API needs a documented contract and a guard

Any `pub fn` with an `anytype` parameter must (a) document the required shape in an in-signature doc
comment on that parameter, and (b) check it before doing any work in the body, emitting a
`@compileError` that names the requirement and the offending type.

Without the guard, passing a `u32` to an unconstrained `items: anytype` that is iterated produces
`error: type 'u32' is not indexable and not a range` pointing at your `for` loop, with the caller
only visible in the `referenced by:` trace.

**Why:** `anytype` carries no signature contract: generated documentation shows the word `anytype`
and nothing else, so the contract exists only in prose. The guard moves a violation's message back
to something the caller can act on.

**Check:** every `anytype` inside a `pub fn`. It needs a doc comment on the parameter line itself,
and a `@compileError` guard before the value is first indexed, iterated, field-accessed, or fed to
an operator. An `anytype` that reaches a `for` with nothing in between is this rule.

```zig
// fragment — BAD
pub fn sum(items: anytype) i64 {
    var total: i64 = 0;
    for (items) |it| total += it; // error surfaces here, not at the call site
    return total;
}
```

```zig
// verified — GOOD
const std = @import("std");

/// Writes `items` as comma-separated decimals.
pub fn writeCsv(
    w: *std.Io.Writer,
    /// Must be a slice whose element type is an integer.
    items: anytype,
) std.Io.Writer.Error!void {
    const T = @TypeOf(items);
    const info = @typeInfo(T);
    if (info != .pointer or info.pointer.size != .slice)
        @compileError("writeCsv expects a slice, got " ++ @typeName(T));
    if (@typeInfo(info.pointer.child) != .int)
        @compileError("writeCsv expects integer elements, got " ++
            @typeName(info.pointer.child));
    for (items) |item| try w.print("{d},", .{item});
}
```

### ZS-TYPE-05 [S] Prefer a concrete parameter type, then `comptime T: type`, then `anytype`

Rank the three options in that order and take the first that works. `anytype` is the last resort,
not the default way to avoid writing a type.

**Why:** a concrete type is checked at the call site and shows up in docs. `comptime T: type` plus
`items: []const T` still gives the compiler a shape to check against, so a wrong argument fails at
the call site with a coercion error naming both types. Bare `anytype` gives up both.

**Check:** an `anytype` parameter whose body uses it in exactly one shape — always indexed, always
`.len`-ed, always printed with one specifier. Rewriting it as `[]const T` or a concrete type is then
mechanical, and the fact that it is mechanical is the violation.

```zig
// fragment — GOOD
pub fn writeCsvU32(w: *std.Io.Writer, items: []const u32) std.Io.Writer.Error!void {
    for (items) |item| try w.print("{d},", .{item});
}
```
