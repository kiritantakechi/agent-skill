# comptime, generics, and interfaces

Rules for compile-time evaluation (`comptime` params, blocks, `inline`, `@setEvalBranchQuota`),
generic type functions, `anytype` and its contracts, type introspection with the 0.17 builtins, and
the three interface shapes Zig offers (comptime duck typing, runtime vtable, tagged union). Naming
of type functions and receivers lives in the naming chapter; `std.Io.Writer`/`Reader` usage and
buffering live in the concurrency chapter; `comptime {}` assertions about wire/disk layout live in
the assertions chapter — this chapter only covers how the interfaces themselves are *shaped*.

The discipline here is **interface-first**: pick which of Zig's three interface shapes fits —
comptime duck typing, runtime vtable, or tagged union — name it, and write the concrete type against
it.

TigerStyle advises the opposite: "only a minimum of excellent abstractions", introduced once a
second implementation exists. Interface-first buys a boundary that is total and symmetric because no
concrete type shaped it. TigerStyle's other claim stands and is the reason the choice matters —
abstractions are never zero-cost, and in Zig the cost is concrete: a comptime abstraction costs
binary size and compile time, a vtable costs an indirect call and an optimization barrier. Deciding
the shape early does not remove those costs; it means choosing which one you pay. ZS-COMPTIME-10,
ZS-COMPTIME-11, and ZS-COMPTIME-16 keep the cost from becoming damage: if any is being bent to make
an interface fit, the interface is wrong and the fallback is a concrete type.

Unlike the other chapters, the blocks here carry their own `const std = @import("std");` rather than
assuming a file-scope preamble — several of them are whole files, and the point of a type function
is often what it does at the top of a file.

## Contents

- **Anti-pattern index**
- **Deciding to use comptime at all**
  - ZS-COMPTIME-01 [M] Force comptime with a labeled block, and keep its product small
  - ZS-COMPTIME-02 [M] Use `comptime var` only as an accumulator driven by an `inline` loop
- **`inline` and its real costs**
  - ZS-COMPTIME-03 [S] Treat `inline fn` as a semantic guarantee, not an optimizer hint
  - ZS-COMPTIME-04 [M] `inline for`/`inline while` only over comptime-known heterogeneous sequences
  - ZS-COMPTIME-05 [M] Scale `@setEvalBranchQuota` to the input; never hardcode a large constant
- **Generic type functions**
  - ZS-COMPTIME-06 [M] Write `comptime` on the type parameters of a type function
  - ZS-COMPTIME-07 [M!] Validate a caller's comptime parameters with `@compileError`, before any use
  - ZS-COMPTIME-08 [S] Non-generic core, generic wrapper of `inline fn` shims
  - ZS-COMPTIME-09 [M] Consume the std interface; never parameterize over it
  - ZS-COMPTIME-10 [M] A `comptime` parameter the body does not depend on is a bug
- **`anytype`**
  - ZS-COMPTIME-11 [M] `anytype` in a public API needs a documented contract and a guard
  - ZS-COMPTIME-12 [S] Prefer a concrete parameter type, then `comptime T: type`, then `anytype`
  - ZS-COMPTIME-13 [S] Use `anytype` where std uses it, and constrain it with `std.meta` predicates
- **Type introspection**
  - ZS-COMPTIME-14 [M] Build types with `@Int`, `@Struct` and the other type builtins
  - ZS-COMPTIME-15 [M] Use `@typeInfo` only to walk lists, and use the 0.17 spellings and accessors
- **Interfaces**
  - ZS-COMPTIME-16 [M] Pick the interface shape from this table before writing any dispatch code
  - ZS-COMPTIME-17 [M] The runtime vtable is two fields; recover the impl by `@ptrCast(@alignCast(…))`
  - ZS-COMPTIME-18 [M] Embed a stateful interface as field `interface`; recover owner by `@fieldParentPtr`
  - ZS-COMPTIME-19 [S] Give vtable members defaults so implementations only override what they must
  - ZS-COMPTIME-20 [M] A closed set of implementations is a tagged union, not an interface
- **Debugging comptime**
  - ZS-COMPTIME-21 [M] Debug comptime errors with `-freference-trace`, and delete every `@compileLog`
- **Where TigerStyle and std disagree**
- Decided by tools

---

## Anti-pattern index

| Symptom | Rule |
|---|---|
| `fn F(comptime T: type)` with one caller ever | ZS-COMPTIME-10 |
| `comptime` keyword at container scope | the compiler (Decided by tools) |
| `inline fn` on a non-trivial function | ZS-COMPTIME-03 |
| `inline for` over a homogeneous array | ZS-COMPTIME-04 |
| `@setEvalBranchQuota(1000000)` | ZS-COMPTIME-05 |
| Generic over the allocator or writer type | ZS-COMPTIME-09 |
| Bare `anytype` in a `pub fn` | ZS-COMPTIME-11, ZS-COMPTIME-12 |
| `@Type(...)`, `std.meta.Int`, `std.meta.Tuple` | ZS-COMPTIME-14 |
| `@typeInfo(T).Struct`, `.@"struct".fields`, a raw `default_value_ptr` | ZS-COMPTIME-15 |
| Hand-rolled vtable for a closed set of impls | ZS-COMPTIME-20 |
| `usingnamespace` | ZS-BUILD-16 |
| `error: unable to resolve comptime value` with no visible cause | ZS-COMPTIME-21 |

---

## Deciding to use comptime at all

### ZS-COMPTIME-01 [M] Force comptime with a labeled block, and keep its product small

Within a runtime function, `comptime` *is* required to force evaluation. Use
`const x = comptime blk: { ... break :blk v; };` so the scratch variables die with the block and
only the finished value survives.

**Why:** the block's result is materialized into `.rodata`. A loose `comptime var` at function scope
leaks mutable comptime state into the rest of the body and makes it much harder to see what actually
ends up in the binary.

**Check:** a `comptime` expression in a function body whose scratch variables are still in scope on
the line after it. The conforming shape is `const x = comptime blk: { ... break :blk v; };` — a
`comptime` with no `blk:` label, or a loop building a constant directly in the function's own scope,
is this rule.

```zig
// verified — GOOD
const std = @import("std");

fn squares() [4]u8 {
    const t = comptime blk: {
        var a: [4]u8 = undefined;
        for (&a, 0..) |*e, i| e.* = @intCast(i * i);
        break :blk a;
    };
    return t;
}
```

### ZS-COMPTIME-02 [M] Use `comptime var` only as an accumulator driven by an `inline` loop

A `comptime var` is legal in a runtime function, but only because everything that touches it must
itself be comptime-known. Restrict it to accumulating over an `inline for`/`inline while`, and make
the result a `const` as soon as the loop ends. Mutating it from a partially runtime-dependent path
is `error: store to comptime variable depends on runtime condition`.

**Why:** that error's `note: runtime condition here` can point at a branch far from the mutation
site. Confining the variable to an inline loop keeps the failure local.

**Check:** every `comptime var` in a diff. The statement after its declaration must be an
`inline for` or `inline while` that mutates it, and the variable must not be read past that loop
except to initialize a `const`. A `comptime var` mutated inside an `if` or a plain `for` is the
finding.

```zig
// verified — GOOD
export fn tripleSum() u32 {
    comptime var acc: u32 = 0;
    inline for (.{ 1, 2, 3 }) |v| acc += v;
    return acc;
}
```

---

## `inline` and its real costs

### ZS-COMPTIME-03 [S] Treat `inline fn` as a semantic guarantee, not an optimizer hint

The langref is explicit: inlining "is not a hint to be possibly observed by optimization passes, but
has implications on the types and values involved in the function call." It also names the only
three uses it addresses: (a) ensuring certain stack frames are in the call stack, for debugging or
for integrating with assembly, (b) forcing comptime-known arguments to propagate to the return
value, and (c) working around limitations of a compiler backend. Otherwise let the optimizer decide.
Deviating needs a comment naming which of the three applies. Speed is not one of them: a performance
`inline` rests on a measurement the comment cites (`references/performance.md` ZS-PERF-21). The
one-line forwarding shims of ZS-COMPTIME-08 are a sanction of their own, without a fresh
measurement, because there the `inline` is what makes the type-erased core cost what the
monomorphized version would.

At an `inline fn` call site, comptime-known arguments are treated as comptime parameters, which no
`@inlineCall`-style hint can achieve.

**Why:** `inline` removes the compiler's ability to *not* inline. On a large function called from
many sites that is a direct, unrecoverable increase in code size and I-cache pressure, and the
optimizer cannot undo it; on a small one it buys nothing, since LLVM already inlines those.

**Check:** every `inline fn` in a diff — count the statements in its body. More than a forwarding
one-liner, with no comment naming which of the three reasons applies, is the finding: `inline` on a
hot loop body is nearly always wrong, and on a one-line shim over a generic core nearly always
right. Reason (b) has a visible tell: the result is used where a comptime value is required, such as
an array length in a runtime function, with no `comptime` written at the call.

```zig
// verified — GOOD: reason (b), comptime-known arguments propagate to the result
const std = @import("std");

const page_size_bytes = 4096;

/// `inline`: called with comptime-known arguments it returns a comptime-known result, so a
/// runtime function can size an array with it. As a plain `fn`, the array length below is
/// `error: unable to resolve comptime value`.
inline fn pagesFor(size_bytes: usize) usize {
    return @divCeil(size_bytes, page_size_bytes);
}

test "a comptime-known result from an inline call" {
    const page_count = pagesFor(10_000);
    const dirty: [page_count]bool = @splat(false);
    try std.testing.expectEqual(3, dirty.len);
}
```

### ZS-COMPTIME-04 [M] `inline for`/`inline while` only over comptime-known heterogeneous sequences

Legitimate operands: `@typeInfo(T).@"struct".field_names` / `.field_types`, tuples, `[]const type`,
enum field lists. Illegitimate: a homogeneous `[N]u8`, a range whose bound is a plain `usize`
constant chosen for performance, anything derived from runtime data. `inline else => |payload|` in a
runtime `switch` is the same tool: it gives each prong a comptime-known tag, which earns its
unrolling when the payloads have different types.

`inline for` over a runtime bound is not slow, it is a compile error:
`error: unable to resolve comptime value` / `note: inline loop condition must be comptime-known`.

**Why:** `inline for` unrolls into N copies of the body. When the element type varies (fields,
types) that is the *only* way to write the code at all; when it does not, you buy N copies of
identical machine code and a slower compile for what a normal loop would do.

**Check:** every `inline for` — its operand must be `@typeInfo(...).field_names`, `.field_types`,
`.decl_names`, an error-set list, a tuple literal, or a `[]const type`; an operand that is an array,
a slice, or a `0..n` range is this rule. An `inline while` takes a boolean condition, not an
iterable, so the operand test does not apply to it: the check there is that its condition and its
continue-expression are both comptime-known and that the loop provably terminates — an
`inline while` driven by a `comptime var` counter (the ZS-COMPTIME-02 shape) is conforming, not a
finding. An `inline else` whose prongs all bind one payload type is the finding too.

```zig
// fragment — BAD
var sum: u32 = 0;
inline for (buffer) |b| sum += b; // buffer: [4096]u8 — 4096 copies of one add
```

```zig
// verified — GOOD
const std = @import("std");

fn countU32Fields(comptime T: type) usize {
    var n: usize = 0;
    inline for (@typeInfo(T).@"struct".field_types) |FieldType| {
        if (FieldType == u32) n += 1;
    }
    return n;
}

const Value = union(enum) { byte: u8, word: u32, quad: u64 };

/// Each prong binds a payload of a different type: what `inline else` is for.
fn encodedSizeBytes(value: Value) usize {
    return switch (value) {
        inline else => |payload| @sizeOf(@TypeOf(payload)),
    };
}

test "countU32Fields" {
    try std.testing.expectEqual(2, countU32Fields(struct { a: u32, b: u8, c: u32 }));
}

test encodedSizeBytes {
    try std.testing.expectEqual(4, encodedSizeBytes(.{ .word = 7 }));
    try std.testing.expectEqual(8, encodedSizeBytes(.{ .quad = 7 }));
}
```

### ZS-COMPTIME-05 [M] Scale `@setEvalBranchQuota` to the input; never hardcode a large constant

The default budget is 1000 backwards branches. When you exceed it, raise the quota by an expression
derived from the actual input size, the way std does
(`@setEvalBranchQuota(@typeInfo(E).@"enum".field_names.len + eval_branch_quota_cushion)` in
`std/enums.zig`), not by picking a big round number.

Hitting the quota means *one* comptime evaluation took too many backwards branches: it is a signal
to bound the computation, and only sometimes a signal to raise the number. Comptime recursion whose
depth depends on user-supplied data is prohibited, as all such recursion is (ZS-ERR-21).

**Why:** the quota is the only guardrail against a comptime evaluation that does not terminate, and
a big round number turns a fast error into a long hang. A quota derived from the input documents the
intended complexity, so an input past the design point fails loudly.

**Check:** every `@setEvalBranchQuota` whose argument is a bare literal rather than an expression
over the input — and any argument of more than five digits regardless of how it is spelled.

```zig
// fragment — BAD
@setEvalBranchQuota(100_000_000);
```

```zig
// verified — GOOD
const std = @import("std");

const crc_table: [256]u32 = blk: {
    @setEvalBranchQuota(256 * 8 * 4); // 256 entries x 8 bits, with slack
    var t: [256]u32 = undefined;
    for (&t, 0..) |*e, i| {
        var c: u32 = @intCast(i);
        for (0..8) |_| c = if (c & 1 != 0) 0xEDB88320 ^ (c >> 1) else c >> 1;
        e.* = c;
    }
    break :blk t;
};
```

## Generic type functions

### ZS-COMPTIME-06 [M] Write `comptime` on the type parameters of a type function

Write the `comptime` keyword on type parameters even though `T: type` also compiles. std writes it
on ~94% of type parameters; the 52 bare `X: type` occurrences are the outliers. Inside the returned
anonymous struct the type has no name, so `const Self = @This();` and a `self` receiver are where
`references/naming.md` ZS-NAME-12 allows them.

**Why:** it is std's spelling, and it states at the declaration that the parameter is resolved at
compile time, which `T: type` leaves the reader to infer from the type.

**Check:** a bare `T: type` parameter with no `comptime` keyword in front of it.

```zig
// verified — GOOD
const std = @import("std");

pub fn RingBuffer(comptime T: type, comptime capacity: usize) type {
    // The contract is `@compileError`, not `comptime assert` — ZS-COMPTIME-07.
    if (capacity == 0) @compileError("RingBuffer capacity must be > 0");
    return struct {
        const Self = @This();

        items: [capacity]T = undefined,
        head: usize = 0,
        len: usize = 0,

        pub const empty: Self = .{};

        pub fn push(self: *Self, item: T) error{Full}!void {
            if (self.len == capacity) return error.Full;
            self.items[(self.head + self.len) % capacity] = item;
            self.len += 1;
        }

        pub fn pop(self: *Self) ?T {
            if (self.len == 0) return null;
            const item = self.items[self.head];
            self.head = (self.head + 1) % capacity;
            self.len -= 1;
            return item;
        }
    };
}
```

### ZS-COMPTIME-07 [M!] Validate a caller's comptime parameters with `@compileError`, before any use

A type function, or any function with a `comptime` parameter a caller supplies, checks the
requirements it depends on — required fields, required decls, size bounds — before anything uses the
parameter, and rejects with a message that names the requirement. Reserve `comptime assert` for
relationships internal to your own module. The same construct documents a deliberately absent API:
`pub const intExclusive = @compileError("intentionally not implemented: ranges are closed");`.
`[M!]` applies to published library code and to any codebase where a misuse must not reach runtime —
databases, consensus, crypto, allocators, parsers on untrusted input. *Relaxed form:* state the
requirement in the doc comment in the words the guard would have used, and make the body's *first*
use of `T` the one that fails — so the diagnostic still lands on the required field or decl rather
than forty lines into the returned struct.

The body of a type function is ordinary function scope, not comptime scope, so
`comptime assert(capacity > 0);` there compiles: the compiler's `redundant comptime keyword` row
does not apply. It is still the wrong way to state a contract. A failed `comptime assert` reports
`error: reached unreachable code` sourced to the `unreachable` inside `std.debug.assert`, so nothing
the caller reads names the requirement.

`@FieldType(T, "link")` on a type with no such field is itself a compile error, so short-circuit it
with `@hasField` first (`or` short-circuits at comptime).

**Why:** without the guard, the diagnostic surfaces at whatever line inside your body first fails to
compile, so the reader sees your internals rather than their mistake. `@compileError` puts your
sentence on the error line, with a note at the offending call site.

**Check:** every `pub fn Name(comptime T: type) type` whose body relies on a field, a declaration or
the size of `T` — its first statement must be a requirement test ending in `@compileError`, before
any `@typeInfo` walk, field access, or `return struct`. A `comptime assert(` whose condition
constrains a caller-supplied `comptime` parameter rather than the module's own constants is
unguarded, and so is a `@FieldType(T, "x")` not short-circuited by `@hasField(T, "x")`: both put the
compiler's message where yours belongs.

```zig
// verified — GOOD
const std = @import("std");

pub const Link = struct { next: ?*Link = null };

/// Intrusive FIFO. `T` must have a field `link: Link`.
pub fn Queue(comptime T: type) type {
    if (!@hasField(T, "link") or @FieldType(T, "link") != Link)
        @compileError(@typeName(T) ++ " must have a field `link: Queue.Link`");
    return struct {
        // ...
        head: ?*Link = null,
    };
}
```

### ZS-COMPTIME-08 [S] Non-generic core, generic wrapper of `inline fn` shims

For a generic container, write the data structure once over type-erased links or bytes, then wrap it
in a thin `fn Foo(comptime T: type) type` whose methods are `inline fn` one-liners. This is
TigerBeetle's R39, and the one place where `inline fn` and generics are both justified.

**Why:** the algorithm is compiled once however many element types exist, and the shims inline away
to nothing, so the call cost matches the fully monomorphized version while compile time and binary
size scale with *methods*, not methods × types.

**Check:** a `fn Foo(comptime T: type) type` whose returned struct holds more than one or two
non-`inline` method bodies — that is the whole algorithm being monomorphized per element type. The
conforming shape is a type-erased struct at file scope plus `pub inline fn` one-liners that forward
into it.

```zig
// verified — GOOD
const std = @import("std");
const assert = std.debug.assert;

pub const Link = struct { next: ?*Link = null };

const QueueAny = struct {
    in: ?*Link = null,
    out: ?*Link = null,
    count: u64 = 0,

    fn push(q: *QueueAny, link: *Link) void {
        assert(link.next == null);
        if (q.in) |in| {
            in.next = link;
            q.in = link;
        } else {
            assert(q.out == null);
            q.in = link;
            q.out = link;
        }
        q.count += 1;
    }

    fn pop(q: *QueueAny) ?*Link {
        const link = q.out orelse return null;
        q.out = link.next;
        if (q.in == link) q.in = null;
        link.next = null;
        q.count -= 1;
        return link;
    }
};

/// Intrusive FIFO. `T` must have a field `link: Link`.
pub fn Queue(comptime T: type) type {
    if (!@hasField(T, "link") or @FieldType(T, "link") != Link)
        @compileError(@typeName(T) ++ " must have a field `link: Link`");
    return struct {
        const Self = @This();

        any: QueueAny = .{},

        pub inline fn push(self: *Self, item: *T) void {
            self.any.push(&item.link);
        }

        pub inline fn pop(self: *Self) ?*T {
            const link = self.any.pop() orelse return null;
            return @alignCast(@fieldParentPtr("link", link));
        }
    };
}
```

### ZS-COMPTIME-09 [M] Consume the std interface; never parameterize over it

Take `gpa: std.mem.Allocator`, `w: *std.Io.Writer`, `r: *std.Io.Reader`, `io: std.Io` as ordinary
runtime parameters. This is one rule with two failure modes, and both are common:

- **Parameterizing over it.** `fn Store(comptime Alloc: type) type`, `fn write(w: anytype)` — you
  monomorphize a subsystem over an interface that is already type-erased, paying N copies for a
  vtable you were given for free.
- **Inventing a parallel one.** A bespoke `MyOutput` with its own `write` method — you get the
  vtable cost anyway, and none of the ecosystem.

Reusable code that produces bytes takes `w: *std.Io.Writer` and returns `std.Io.Writer.Error!void`;
code that consumes bytes takes `r: *std.Io.Reader`; code that allocates takes
`gpa: std.mem.Allocator`; code that does I/O or concurrency takes `io: std.Io`. Take the interface,
not a concrete type that happens to provide it: a function that only reads takes `*std.Io.Reader`,
not an `*Io.File`.

`std.testing.allocator`, `Allocator.failing`, `Io.failing`, `Writer.fixed`, `Writer.Allocating`,
`Writer.Discarding`, `Writer.hashed`, an `Io.File`, and a socket all speak the std interface and
none of them speak yours; every one of them would have to be re-implemented against your type.

**Why:** one vtable indirection per allocation is cheaper than N copies of your entire subsystem,
and it is the difference between a type your callers can store in a struct field and one they
cannot. Either deviation costs the same thing: composition.

**Check:** grep a diff for `comptime .*: type` whose name ends in `Allocator`, `Alloc`, `Writer`,
`Reader`, or `Io`, and for any new struct with a `vtable` field whose operations are "write bytes",
"read bytes", or "allocate". Both are this rule, and so is a parameter typed `*Io.File` where a
`*Io.Reader` or `*Io.Writer` would do.

```zig
// fragment — BAD: parameterizing over what is already type-erased
pub fn Store(comptime Alloc: type, comptime Out: type) type {
    return struct { alloc: Alloc, out: Out };
}
```

```zig
// verified — GOOD
const std = @import("std");

pub fn printReport(w: *std.Io.Writer, rows: []const u32) std.Io.Writer.Error!void {
    for (rows) |row| try w.print("{d}\n", .{row});
}

test "printReport composes with any std writer" {
    var buffer: [16]u8 = undefined;
    var w: std.Io.Writer = .fixed(&buffer);
    try printReport(&w, &.{ 1, 2 });
    try std.testing.expectEqualStrings("1\n2\n", w.buffered());
}
```

### ZS-COMPTIME-10 [M] A `comptime` parameter the body does not depend on is a bug

If deleting the `comptime T: type` parameter and substituting the one type actually used leaves the
body unchanged, delete it. Same for a `comptime` value parameter that is only ever passed one value.
The same goes for a type function whose whole job is to compute a value: make it a function
returning that value.

**Why:** the parameter still forces one instantiation per distinct argument, and the instantiations
are bit-identical machine code. You pay for monomorphization and receive nothing.

**Check:** for each `comptime` parameter, grep its call sites and count the distinct arguments. One
distinct argument across the whole tree means one instantiation and no reason for the parameter. In
the body, a `comptime T: type` that appears only in the signature — never in a field type, a
`@sizeOf`, a cast, or a `@typeInfo` — is the same finding.

---

## `anytype`

### ZS-COMPTIME-11 [M] `anytype` in a public API needs a documented contract and a guard

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

### ZS-COMPTIME-12 [S] Prefer a concrete parameter type, then `comptime T: type`, then `anytype`

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

### ZS-COMPTIME-13 [S] Use `anytype` where std uses it, and constrain it with `std.meta` predicates

The idiomatic uses are format-argument tuples (`args: anytype`), opaque user contexts
(`context: anytype`), hashers, and pointer-shaped duck typing (`allocation: anytype` in
`Allocator.resize`/`remap`/`free`). When the contract is "has this method," express it with
`std.meta.hasFn` / `std.meta.hasMethod` rather than hand-rolled `@typeInfo` walking.

**Why:** `std.meta.hasMethod(*T, "reset")` handles the pointer-vs-value and namespace cases
correctly, which hand-written checks routinely get wrong. Following std's placement also means
readers already know what the parameter means without reading the body.

**Check:** a hand-rolled `@typeInfo(@TypeOf(x))` walk whose question is "does it have a decl named
…" — that is `std.meta.hasFn`/`hasMethod`. And an `anytype` parameter that is not a format-args
tuple, a `context`, a hasher, or a pointer-shaped allocation: it is outside the idiom and needs the
ZS-COMPTIME-11 guard.

```zig
// verified — GOOD
const std = @import("std");

/// Contract: `T` must expose `pub fn reset(*T) void`.
fn resetAll(comptime T: type, items: []T) void {
    if (!std.meta.hasMethod(*T, "reset"))
        @compileError(@typeName(T) ++ " must declare `pub fn reset(*" ++
            @typeName(T) ++ ") void`");
    for (items) |*item| item.reset();
}
```

## Type introspection

### ZS-COMPTIME-14 [M] Build types with `@Int`, `@Struct` and the other type builtins

`@Type` does not exist — `error: invalid builtin function: '@Type'` — and neither do `std.meta.Int`
and `std.meta.Tuple` (`error: root source file struct 'meta' has no member named 'Int'`). The type
builtins are `@Int`, `@Tuple`, `@Struct`, `@Union`, `@Enum`, `@Pointer`, `@Fn`, `@EnumLiteral`.
There is deliberately no `@Float`, `@Array`, `@Opaque`, `@Optional`, `@ErrorSet` or `@ErrorUnion` —
those types have ordinary syntax, so reflection was never needed to build them.

**Why:** each builtin takes the arguments its kind of type needs, typed in its signature, so a
malformed type is an error at the call; every other spelling fails to build.

**Check:** grep a diff for `@Type(`, `std.meta.Int`, and `std.meta.Tuple`. All three fail to build,
so the grep is a pre-flight for carried-over code rather than something a reviewer has to catch by
eye.

Signatures, from the langref:

```text
@Int(comptime signedness: std.lang.Signedness, comptime bits: u16) type
@Tuple(comptime field_types: []const type) type
@Enum(comptime TagInt: type, comptime mode: std.lang.Type.Enum.Mode,
      comptime field_names: []const []const u8,
      comptime field_values: *const [field_names.len]TagInt) type
@Struct(comptime layout: std.lang.Type.ContainerLayout, comptime BackingInt: ?type,
        comptime field_names: []const []const u8,
        comptime field_types: *const [field_names.len]type,
        comptime field_attrs: *const [field_names.len]std.lang.Type.Struct.FieldAttributes) type
@EnumLiteral() type
```

```zig
// rejected — zig: invalid builtin function: '@Type'
const T = @Type(.{ .int = .{ .signedness = .unsigned, .bits = 8 } });
```

```zig
// verified — GOOD
const std = @import("std");

test "type builtins" {
    try std.testing.expectEqual(u7, @Int(.unsigned, 7));
    const Pair = @Tuple(&.{ u8, bool });
    const p: Pair = .{ 3, true };
    try std.testing.expectEqual(3, p[0]);
}
```

### ZS-COMPTIME-15 [M] Use `@typeInfo` only to walk lists, and use the 0.17 spellings and accessors

Two halves, in order of application.

**Do not reach for `@typeInfo` at all** when a narrower builtin answers the question. `@TypeOf`,
`@FieldType(T, "a")`, `@hasField`, `@hasDecl`, `@field` are stable, read as what they mean, and
cannot break when std's reflection layout changes. Prefer `@FieldType(T, "a")` over
`std.meta.fieldInfo(T, .a).type`; `fieldInfo`, `fieldNames` and `fieldTypes` are deprecated in favor
of `@typeInfo`. `@typeInfo` earns its keep only when you genuinely need to iterate fields, decls, or
error-set members. One trap: `@hasDecl` is `true` only for `pub` declarations, even when the caller
is in the same file, so a feature test over a private declaration silently answers `false`. The
langref recommends feature detection via `@hasDecl`/`@hasField` over version comparisons.

**When you do walk a list, use the 0.17 spellings and accessor methods.** Tags are `.@"struct"`,
`.@"union"`, `.@"enum"`, `.@"fn"`, `.@"opaque"`, and plain `.pointer`, `.int`, `.float`,
`.optional`, `.error_union`, `.error_set`. A container's members are parallel slices, not a slice of
field structs: `.field_names[i]`, `.field_types[i]` and `.field_attrs[i]` for fields, `.decl_names`
for declarations. Read defaults with `info.field_attrs[i].defaultValue(info.field_types[i])`
(returns `?FieldType`) and sentinels with `ptr_info.sentinel()`, never by `@ptrCast`-ing the raw
`*anyopaque` pointer fields.

Three more traps: pointer and field alignment, `.pointer.attrs.@"align"` and
`.field_attrs[i].@"align"`, are `?usize` (`null` means natural alignment), not `comptime_int`;
`@typeInfo(E).error_set.error_names` is `?[]const [:0]const u8` where `null` means `anyerror`, so a
`null` check is not an "empty set" check; and a zero-bit tuple field is not implicitly `comptime`
(`references/data.md` ZS-DATA-34).

The `.Int` -> `.int` / `.Struct` -> `.@"struct"` renames and 0.17's move from `.fields` to
`.field_names`/`.field_types`/`.field_attrs` are hard compile errors, so they are rows of the
migration table rather than enumerated here. This rule is about the parts that still compile.

**Why:** the accessor methods encapsulate the `default_value_ptr`/`sentinel_ptr` representation, so
code that calls them survives a representation change, and code that reads the raw fields does not.

**Check:** every `@typeInfo` in a diff must be followed by an `inline for` or an equivalent list
walk; if it is followed by a single field or decl access, a narrow builtin does it better. Grep for
`default_value_ptr` and `sentinel_ptr` — both should be `defaultValue(FieldType)` / `sentinel()`.

```zig
// verified — GOOD
const std = @import("std");

fn writeFields(w: *std.Io.Writer, value: anytype) std.Io.Writer.Error!void {
    const T = @TypeOf(value);
    // `@typeInfo` is justified: this genuinely needs the field list.
    inline for (@typeInfo(T).@"struct".field_names) |name| {
        try w.print("{s}={d};", .{ name, @field(value, name) });
    }
}

fn defaultRetries(comptime T: type) ?u8 {
    // Not `field_attrs[0].default_value_ptr` + `@ptrCast`.
    const info = @typeInfo(T).@"struct";
    return info.field_attrs[0].defaultValue(info.field_types[0]);
}

test "accessors" {
    const Config = struct { retries: u8 = 3 };
    try std.testing.expectEqual(3, defaultRetries(Config));
    // The narrow builtin, where it answers the question.
    try std.testing.expectEqual(u8, @FieldType(Config, "retries"));

    var buffer: [16]u8 = undefined;
    var w: std.Io.Writer = .fixed(&buffer);
    const config: Config = .{};
    try writeFields(&w, config);
    try std.testing.expectEqualStrings("retries=3;", w.buffered());
}
```

---

## Interfaces

### ZS-COMPTIME-16 [M] Pick the interface shape from this table before writing any dispatch code

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
of implementations that all live in your own tree — that is ZS-COMPTIME-20's tagged union.

### ZS-COMPTIME-17 [M] The runtime vtable is two fields; recover the impl by `@ptrCast(@alignCast(…))`

Fields are a type-erased context pointer plus `vtable: *const VTable`. `std.mem.Allocator` spells it
`ptr: *anyopaque, vtable: *const VTable`; `std.Io` spells it
`userdata: ?*anyopaque, vtable: *const VTable`. Provide public wrapper methods on the interface so
callers never touch `vtable` directly, and hand out the interface from a method taking `*Self`.

Treat the context pointer as opaque, never as an identity: `std.mem.Allocator` documents that `ptr`
may be `undefined` for stateless allocators and that comparing it is illegal behavior.

**Why:** the context pointer aliases the implementation's storage, so building the interface in a
method on `*Self` is what pins it to a stable address; the wrapper methods are the only place the
`userdata` and the vtable slot are guaranteed to stay paired.

**Check:** an interface value built anywhere but a method taking `*Self` — a
`fn sink(cs: CountingSink) Sink` takes the receiver by value and pins the vtable to a copy. Also any
`==` or `!=` on the `ptr`/`userdata` field, and any call site spelling `x.vtable.f(x.ptr, …)`
instead of going through a wrapper method.

```zig
// verified — GOOD
const std = @import("std");

pub const Sink = struct {
    ptr: *anyopaque,
    vtable: *const VTable,

    pub const Error = error{SinkFailed};

    pub const VTable = struct {
        write: *const fn (ptr: *anyopaque, bytes: []const u8) Error!usize,
        flush: *const fn (ptr: *anyopaque) Error!void = defaultFlush,
    };

    fn defaultFlush(ptr: *anyopaque) Error!void {
        _ = ptr;
    }

    pub fn write(s: Sink, bytes: []const u8) Error!usize {
        return s.vtable.write(s.ptr, bytes);
    }

    pub fn flush(s: Sink) Error!void {
        return s.vtable.flush(s.ptr);
    }
};

pub const CountingSink = struct {
    count: usize = 0,

    pub fn sink(cs: *CountingSink) Sink {
        return .{ .ptr = cs, .vtable = &.{ .write = write } };
    }

    fn write(ptr: *anyopaque, bytes: []const u8) Sink.Error!usize {
        const cs: *CountingSink = @ptrCast(@alignCast(ptr));
        cs.count += bytes.len;
        return bytes.len;
    }
};
```

### ZS-COMPTIME-18 [M] Embed a stateful interface as field `interface`; recover owner by `@fieldParentPtr`

This is the modern std house pattern. The implementation struct declares `interface: std.Io.Writer`
(or `Reader`) as a field **by value**, hands out `&self.interface`, and every vtable function starts
with `const self: *Impl = @alignCast(@fieldParentPtr("interface", io_w));`. `Io.Writer` and
`Io.Reader` carry no userdata pointer — a vtable function receives only the interface pointer — so
`@fieldParentPtr` is the whole mechanism, and it works only on a by-value field.

Name the field `interface`. std is split: `Io.File.Writer`, `Io.File.Reader`, `Io.Reader.Limited`,
`Io.net`, `http` and `testing` say `interface`, while the adapters `Io.Writer.Discarding` and
`Allocating`, `compress.flate.Decompress` and `crypto.tls.Client` say `writer` or `reader`. Either
recovers the parent; one name per codebase is what lets a reviewer find every embedded interface.

`std.Io.Writer` holds `vtable`, `buffer: []u8`, and `end: usize` inline: the caller writes straight
into `buffer`, and the vtable is reached only when the buffer overflows or on flush.

Write the `@alignCast` unconditionally — but not "to match std", which does not: 97 of 0.17 std's
172 `@fieldParentPtr` calls wrap it and **75 do not**, including `Io/Reader/Limited.zig`, otherwise
this exact pattern. Write it because it is *required* whenever the field's alignment is weaker than
the parent's, and free when it is not, so unconditional is the only spelling that cannot go wrong as
the struct changes shape underneath it.

Never copy a struct that contains a live `interface` field: a `*Io.Writer` handed out earlier then
points into the dead original.

**Why:** the interface is part of the implementation, not a wrapper around it: no second allocation,
no context pointer to keep in sync, and `@fieldParentPtr` subtracts a comptime-known offset, so
recovery is free and the indirect call stays off the hot path.

**Check:** an `Io.Writer`/`Io.Reader` field declared as a pointer (`*Io.Writer`) rather than by
value, or named anything but `interface`; a `@fieldParentPtr` whose first argument is some other
name for those types; in **code the diff adds**, a `@fieldParentPtr` not wrapped in `@alignCast` —
existing call sites are left alone (75 of std's 172 omit it, and the compiler rejects the ones that
needed it), new ones are written unconditionally so the next field reorder cannot turn a compiling
line into a failing one; and any `return`, assignment, or `append` that copies a struct with an
`interface` field by value after `&x.interface` has been handed out.

```zig
// verified — GOOD
const std = @import("std");
const Io = std.Io;

/// Counts bytes written through it.
pub const CountingWriter = struct {
    count: u64 = 0,
    interface: Io.Writer,

    pub fn init(buffer: []u8) CountingWriter {
        return .{ .interface = .{ .vtable = &.{ .drain = drain }, .buffer = buffer } };
    }

    fn drain(io_w: *Io.Writer, data: []const []const u8, splat: usize) Io.Writer.Error!usize {
        const cw: *CountingWriter = @alignCast(@fieldParentPtr("interface", io_w));
        cw.count += io_w.end;
        io_w.end = 0;
        const n = Io.Writer.countSplat(data, splat);
        cw.count += n;
        return n;
    }
};
```

### ZS-COMPTIME-19 [S] Give vtable members defaults so implementations only override what they must

Declare optional operations with a default implementation in the `VTable` struct itself, so an
implementation's vtable literal lists only the required functions. std does this:
`std.Io.Writer.VTable` requires only `drain` (`sendFile` defaults to `unimplementedSendFile`,
`flush` to `defaultFlush`, `rebase` to `defaultRebase`), and `std.Io.Reader.VTable` requires only
`stream` (`discard`, `readVec`, and `rebase` all default).

**Why:** defaults keep every implementation to a handful of lines, and adding a new optional
operation with a default is then a backwards-compatible change instead of breaking every
implementation in the ecosystem.

**Check:** a `VTable` struct whose fields carry no `= default…` initializers, sitting next to two or
more implementations whose vtable literals name the same function with the same body. That repeated
function is the default that was not declared.

### ZS-COMPTIME-20 [M] A closed set of implementations is a tagged union, not an interface

If every implementation is known at compile time and lives in your own tree, model it as
`union(enum)` with methods that `switch` exhaustively (`references/errors.md` ZS-ERR-25).
`std.Build.LazyPath` is the canonical std example.

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

## Debugging comptime

### ZS-COMPTIME-21 [M] Debug comptime errors with `-freference-trace`, and delete every `@compileLog`

Every failure mode in this chapter reports at the innermost frame, which is almost never the frame
that caused it. Two tools address that, and both need discipline.

**`-freference-trace[=num]`.** Every comptime diagnostic ends with a `referenced by:` chain, but the
default shows only the first few frames and then prints
`N reference(s) hidden; use '-freference-trace=<N+2>' to see all references`. Raise it and re-run —
the frame you want is usually the deepest non-std one. It works on `zig build-obj`, `zig test`, and
`zig build`; for a build, pass `zig build -freference-trace=20` (0.17 removed `b.reference_trace`,
so `build.zig` can no longer set it).

It is the single highest-value flag for this chapter's failure surface: ZS-COMPTIME-02's leaked
`comptime var`, ZS-COMPTIME-04's runtime `inline for` bound, ZS-COMPTIME-07 and ZS-COMPTIME-11's
unguarded type parameters, and every `@compileError` you emit are all reported at a line the caller
did not write.

**Why:** `error: unable to resolve comptime value` names the line where a runtime value met a
`comptime` parameter, but the bug is at the call site that made the value runtime-known, which may
be forty frames up. The reference trace is the only artifact connecting the two.

```text
$ zig build-obj bad.zig
bad.zig:3:35: error: unable to resolve comptime value
fn mid(n: usize) void { _ = inner(n); }
                                  ^
bad.zig:3:35: note: argument to comptime parameter must be comptime-known
bad.zig:2:10: note: parameter declared comptime here
referenced by:
    outer: bad.zig:4:29
    4 reference(s) hidden; use '-freference-trace=6' to see all references
```

**`@compileLog` discipline.** `@compileLog` is not a print statement: reaching one is itself
`error: found compile log statement`, and the values are dumped in a `Compile Log Output:` block
after the error. So the build fails by design, a `@compileLog` left in a shared branch breaks
everyone's build, and it can never be committed. Three consequences:

- Treat it exactly like a debugger breakpoint — add, read, delete, in one sitting. Never commit one.
- It renders comptime *values*, not types: log `@typeName(T)` rather than `T`, and `@sizeOf(T)`
  rather than a type expression, or you get `@as(type, ...)` noise.
- Because it aborts, you get one shot per compile. Log several values in one call —
  `@compileLog(@typeName(T), @sizeOf(T), i)` — rather than bisecting across builds.

For a check that should *stay* in the source, use `comptime { assert(...) }` or `@compileError` with
a message naming the requirement (ZS-COMPTIME-07), not `@compileLog`.

**Check:** `rg -n "@compileLog"` over the diff must return nothing. If a comptime bug report in a
review says only "unable to resolve comptime value", ask for the output with `-freference-trace`
raised — the bare diagnostic does not identify the caller.

```zig
// rejected — zig: found compile log statement; never commit one
// error: found compile log statement
// Compile Log Output:
// @as(*const [3:0]u8, "u32"), @as(comptime_int, 4)
fn sizeOfLogged(comptime T: type) usize {
    @compileLog(@typeName(T), @sizeOf(T));
    return @sizeOf(T);
}

comptime {
    _ = sizeOfLogged(u32);
}
```

---

## Where TigerStyle and std disagree

TigerBeetle pins Zig 0.14.1 and predates `std.Io`, so TigerStyle's position on dispatch was formed
without a std interface to lean on.

**TigerStyle's position:** minimize abstractions; where an abstraction is unavoidable, prefer static
dispatch — TigerBeetle parameterizes its whole storage/replica stack on comptime types
(`fn ReplicaType(comptime ...)`), so every call is direct and every layer is visible to the
optimizer and to a reader following one instantiation.

**std's position:** the opposite for the three central abstractions. `std.mem.Allocator`, `std.Io`,
and `std.Io.Writer`/`Reader` are all runtime vtables. std explicitly traded static dispatch away for
storability, ABI stability, and one compiled copy of every consumer.

**Recommendation, keyed to the tiers:**

- [M] Take `Allocator`, `*Io.Writer`, `*Io.Reader`, and `Io` as runtime interfaces (ZS-COMPTIME-09).
  This is not a style preference: hand-rolling around them costs you the entire std ecosystem, and
  comptime-parameterizing on an allocator type is a pattern std deliberately deleted.
- [S] For your *own* abstractions, follow TigerStyle: prefer no abstraction, then a tagged union
  (ZS-COMPTIME-20), then an interface. Reach for a vtable only when the implementation set is
  genuinely open.
- [M!] In high-reliability code — databases, consensus, embedded, crypto, allocators, anything where
  a crash or corruption is unacceptable — apply TigerStyle's static-dispatch preference to the hot
  path, and use ZS-COMPTIME-08 (type-erased core + `inline fn` shims) to get direct calls without
  N-fold monomorphization. Elsewhere, one indirect call is not worth designing around.

A smaller disagreement: TigerStyle uses `inline fn` freely for shims, while the langref says "it is
generally better to let the compiler decide when to inline a function." ZS-COMPTIME-03 resolves it:
the shim case, a one-line forwarder over a type-erased core (ZS-COMPTIME-08), is a sanction of its
own beside the langref's three reasons, so both are satisfied.

## Decided by tools

The compiler rejects each of these on its own; no setting turns one off.

| Tool | Lint | Level | Forbids |
|---|---|---|---|
| zig | `redundant comptime keyword in already comptime scope` | error | `comptime` on what is comptime already: a container initializer, an array length, a type |
