# comptime, generics, and interfaces

Rules for compile-time evaluation (`comptime` params, blocks, `inline`, `@setEvalBranchQuota`),
generic type functions, `anytype` and its contracts, type introspection with the 0.17 builtins, and
the three interface shapes Zig offers (comptime duck typing, runtime vtable, tagged union). Naming
of type functions and receivers lives in the naming chapter; `std.Io.Writer`/`Reader` usage and
buffering live in the I/O chapter; `comptime {}` assertions about wire/disk layout live in the
assertions chapter — this chapter only covers how the interfaces themselves are *shaped*.

The discipline here is **interface-first**: pick which of Zig's three interface shapes fits —
comptime duck typing, runtime vtable, or tagged union — name it, and write the concrete type against
it.

TigerStyle advises the opposite: "only a minimum of excellent abstractions", introduced once a
second implementation exists. Interface-first buys a boundary that is total and symmetric because no
concrete type shaped it. TigerStyle's other claim stands and is the reason the choice matters —
abstractions are never zero-cost, and in Zig the cost is concrete: a comptime abstraction costs
binary size and compile time, a vtable costs an indirect call and an optimization barrier. Deciding
the shape early does not remove those costs; it means choosing which one you pay. ZS-CT-13,
ZS-CT-14, and ZS-CT-21 keep the cost from becoming damage: if any is being bent to make an interface
fit, the interface is wrong and the fallback is a concrete type.

Unlike the other chapters, the blocks here carry their own `const std = @import("std");` rather
than assuming a file-scope preamble — several of them are whole files, and the point of a type
function is often what it does at the top of a file.
## Contents

- **Anti-pattern index**
- **Deciding to use comptime at all**
  - ZS-CT-01 [M] Name the interface shape before writing the type that provides it
  - ZS-CT-02 [M] Never write `comptime` in a scope that is already comptime
  - ZS-CT-03 [M] Force comptime with a labeled block, and keep its product small
  - ZS-CT-04 [M] Use `comptime var` only as an accumulator driven by an `inline` loop
- **`inline` and its real costs**
  - ZS-CT-05 [S] Treat `inline fn` as a semantic guarantee, not an optimizer hint
  - ZS-CT-06 [M] `inline for`/`inline while` only over comptime-known heterogeneous sequences
  - ZS-CT-07 [M] Scale `@setEvalBranchQuota` to the input; never hardcode a large constant
  - ZS-CT-08 [M] Assert the size of everything comptime generates (see ZS-ASRT-22)
- **Generic type functions**
  - ZS-CT-09 [M] Generic types are `fn TitleCase(comptime T: type) type` — the only home of `Self`
  - ZS-CT-10 [M!] Validate type parameters at the top of the type function with `@compileError`
  - ZS-CT-11 [S] Non-generic core, generic wrapper of `inline fn` shims
  - ZS-CT-12 [M] Consume the std interface; never parameterize over it
  - ZS-CT-13 [M] A `comptime` parameter the body does not depend on is a bug
- **`anytype`**
  - ZS-CT-14 [M] `anytype` in a public API needs a documented contract and a guard
  - ZS-CT-15 [S] Prefer a concrete parameter type, then `comptime T: type`, then `anytype`
  - ZS-CT-16 [S] Use `anytype` where std uses it, and constrain it with `std.meta` predicates
  - ZS-CT-17 [S] Pass behavior as a `comptime …Fn` parameter, last, after its `context`
- **Type introspection**
  - ZS-CT-18 [M] `@Type` is removed; use the dedicated type builtins
  - ZS-CT-19 [S] Reach for the narrowest introspection builtin before `@typeInfo` (see ZS-CT-20)
  - ZS-CT-20 [M] Use `@typeInfo` only to walk lists, and use the 0.17 spellings and accessors
- **Interfaces**
  - ZS-CT-21 [M] Pick the interface shape from this table before writing any dispatch code
  - ZS-CT-22 [M] The runtime vtable is two fields; recover the impl by `@ptrCast(@alignCast(…))`
  - ZS-CT-23 [M] Embed a stateful interface as field `interface`; recover owner by `@fieldParentPtr`
  - ZS-CT-24 [S] Give vtable members defaults so implementations only override what they must
  - ZS-CT-25 [M] A closed set of implementations is a tagged union, not an interface
  - ZS-CT-26 [M] Consume the std interface instead of inventing a parallel one (see ZS-CT-12)
  - ZS-CT-27 [M] `usingnamespace` is removed; re-export explicitly (see ZS-MIG-02)
- **Debugging comptime**
  - ZS-CT-28 [M] Debug comptime errors with `-freference-trace`, and delete every `@compileLog`
- **Where TigerStyle and std disagree**

---

## Anti-pattern index

| Symptom | Rule |
|---|---|
| `fn F(comptime T: type)` with one caller ever | ZS-CT-13 |
| `comptime` keyword at container scope | ZS-CT-02 |
| `inline fn` on a non-trivial function | ZS-CT-05 |
| `inline for` over a homogeneous array | ZS-CT-06 |
| `@setEvalBranchQuota(1000000)` | ZS-CT-07 |
| Generic over the allocator or writer type | ZS-CT-12 |
| Bare `anytype` in a `pub fn` | ZS-CT-14, ZS-CT-15 |
| `@Type(...)`, `std.meta.Int`, `std.meta.Tuple` | ZS-CT-18 |
| `@typeInfo(T).Struct`, `.@"struct".fields`, a raw `default_value_ptr` | ZS-CT-20 |
| Hand-rolled vtable for a closed set of impls | ZS-CT-25 |
| `usingnamespace` | ZS-CT-27 |
| `error: unable to resolve comptime value` with no visible cause | ZS-CT-28 |

---

## Deciding to use comptime at all

### ZS-CT-01 [M] Name the interface shape before writing the type that provides it

Decide which of the three shapes the boundary needs — comptime duck typing for a
compile-time-known implementor, a runtime vtable for a set chosen at run time, a tagged union for a
closed set — write that down, then implement against it. Take the interface, not the concrete type:
a function that only reads should take a `*std.Io.Reader`, not a `*Io.File`.

**Why:** the shape of a boundary is fixed by whoever writes it first, and one extracted from an
existing type inherits that type's accidents — its error set, its parameter order, its assumption
that a handle is always available. Choosing the shape against the caller's need instead produces a
surface that is total and symmetric because no concrete type was in the room to distort it. It also
forces the cost question early, while all three shapes are still available.

**Check:** for each concrete type used across a module boundary, is the consumer written against the
type or against an interface? A function taking `*Io.File` where a `*Io.Reader` would do is the
finding. Note this does **not** license an unused generic: ZS-CT-13 still deletes a `comptime`
parameter the body ignores.

### ZS-CT-02 [M] Never write `comptime` in a scope that is already comptime
Container-scope declarations, array lengths, and type expressions are already evaluated at compile
time. In 0.16 a redundant `comptime` keyword in one of those three positions is a hard compile
error, not a warning.

**Why:** `const n = comptime f(x);` at container scope
gives `error: redundant comptime keyword in already comptime scope`. Code carried over from
0.13-era Zig, where this was merely noise, no longer builds.

The body of a type function is **not** one of those positions. `comptime assert(capacity > 0);`
inside `pub fn RingBuffer(comptime T: type, comptime capacity: usize) type` compiles cleanly: a type
function's body runs at compile time when it is *called*, but the body itself is an ordinary
function scope, so the keyword is meaningful there rather than redundant.

That it compiles does not make it the way to state a parameter **contract**: a failed
`comptime assert` reports `error: reached unreachable code` sourced to the `unreachable` inside
`std.debug.assert`, so the first line the caller reads is a std internal and nothing names the
requirement. `@compileError` puts your own sentence on the error line instead. Contracts are
ZS-CT-10; this rule is only about where the `comptime` keyword is legal.

**Check:** the `comptime` keyword on a container-scope `const`/`var` initializer, inside `[...]` of
an array type, or inside any other type expression. Each is a build break, so this grep is a
pre-flight before pushing rather than a review finding.

```zig
// does-not-compile — BAD
const std = @import("std");
const n = comptime std.math.log2_int(u32, 1024);
```

```zig
// verified — GOOD
const std = @import("std");
const n = std.math.log2_int(u32, 1024);
```

### ZS-CT-03 [M] Force comptime with a labeled block, and keep its product small
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

### ZS-CT-04 [M] Use `comptime var` only as an accumulator driven by an `inline` loop
A `comptime var` is legal in a runtime function, but only because everything that touches it must
itself be comptime-known. Restrict it to accumulating over an `inline for`/`inline while`, and make
the result a `const` as soon as the loop ends.

**Why:** a `comptime var` that is mutated from a partially runtime-dependent path produces
`error: store to comptime variable depends on runtime condition`, whose `note: runtime condition
here` can point at a branch far from the mutation site. Confining it to an inline loop keeps the
failure local.

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

### ZS-CT-05 [S] Treat `inline fn` as a semantic guarantee, not an optimizer hint
The langref is explicit: inlining "is not a hint to be possibly observed by optimization passes, but
has implications on the types and values involved in the function call." It also names the only
three uses it addresses: (a) ensuring certain stack frames are in the call stack, for debugging or
for integrating with assembly, (b) forcing comptime-known arguments to propagate to the return
value, and (c) working around limitations of a compiler backend. Otherwise let the optimizer
decide. Deviating needs a comment naming which of the three applies. Speed is not one of them:
`references/performance-and-locality.md` ZS-PERF-20 lets a performance `inline` rest only on a
measurement the comment cites. The one-line forwarding shims of ZS-CT-11 are the one shape
sanctioned without a fresh measurement, because there the `inline` is what makes the type-erased
core cost what the monomorphized version would.

**Why:** `inline` removes the compiler's ability to *not* inline. On a large function called from
many sites that is a direct, unrecoverable increase in code size and I-cache pressure, and the
optimizer cannot undo it. The genuine use is that comptime-known arguments at an `inline fn` call
site are treated as comptime parameters, which no `@inlineCall`-style hint can achieve.

**Check:** every `inline fn` in a diff — count the statements in its body. More than a forwarding
one-liner, with no comment naming which of the three reasons applies, is the finding. Reason (b) has
a visible tell: the function's result is used in a type expression or as a comptime argument.

```zig
// verified — GOOD: `inline` is what makes bitsFor usable in a type expression
const std = @import("std");

inline fn bitsFor(comptime n: comptime_int) u16 {
    return std.math.log2_int_ceil(u32, n) + 1;
}

const Index = @Int(.unsigned, bitsFor(1000)); // u11
```

### ZS-CT-06 [M] `inline for`/`inline while` only over comptime-known heterogeneous sequences
Legitimate operands: `@typeInfo(T).@"struct".field_names` / `.field_types`, tuples,
`[]const type`, enum field lists.
Illegitimate: a homogeneous `[N]u8`, a range whose bound is a plain `usize` constant chosen for
performance, anything derived from runtime data.

**Why:** `inline for` unrolls into N copies of the body. When the element type varies (fields,
types) that is the *only* way to write the code at all. When the elements are homogeneous you have
bought N copies of identical machine code and a slower compile in exchange for what a normal loop
would have done. `inline for` over a runtime bound is not slow, it is a compile error:
`error: unable to resolve comptime value` / `note: inline loop condition must be comptime-known`.

**Check:** every `inline for` — its operand must be `@typeInfo(...).field_names`, `.field_types`,
`.decl_names`, an error-set list, a tuple literal, or a `[]const type`; an operand that is an array,
a slice, or a `0..n` range is this rule. An `inline while` takes a boolean condition, not an
iterable, so the operand test does not apply to it: the check there is that its condition and its
continue-expression are both comptime-known and that the loop provably terminates — an
`inline while` driven by a `comptime var` counter (the ZS-CT-04 shape) is conforming, not a finding.

```zig
// fragment — BAD
var sum: u32 = 0;
inline for (buf) |b| sum += b; // buf: [4096]u8 — 4096 copies of one add
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

test "countU32Fields" {
    try std.testing.expectEqual(2, countU32Fields(struct { a: u32, b: u8, c: u32 }));
}
```

### ZS-CT-07 [M] Scale `@setEvalBranchQuota` to the input; never hardcode a large constant
The default budget is 1000 backwards branches. When you exceed it, raise the quota by an expression
derived from the actual input size, the way std does
(`@setEvalBranchQuota(@typeInfo(E).@"enum".field_names.len + eval_branch_quota_cushion)` in
`std/enums.zig`), not by picking a big round number.

**Why:** the quota is the only guardrail against a comptime evaluation that does not terminate.
`@setEvalBranchQuota(1_000_000)` converts "the compiler tells me in 200 ms that my comptime loop is
unbounded" into "the compiler hangs for a minute and then tells me." A quota expressed in terms of
the input also documents the intended complexity, so an input that grows past the design point
fails loudly instead of silently costing 30 s of build time. Hitting the quota means *one* comptime
evaluation took too many backwards branches — it is a signal to bound the computation, and only
sometimes a signal to raise the number. Corollary, following TigerStyle's ban on recursion:
comptime recursion whose depth depends on user-supplied data is prohibited.

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

### ZS-CT-08 [M] Assert the size of everything comptime generates (see ZS-ASRT-22)
Owned by `references/assertions-and-limits.md` ZS-ASRT-22, which also covers
`std.meta.hasUniqueRepresentation`. Every comptime-generated table, and
every type whose layout comptime derives, gets a `comptime {}` block asserting its size — a table
sized from a `comptime_int` constant grows from 1 KiB to 16 MiB of `.rodata` when someone bumps that
constant, and nothing in the build output says so. See also ZS-CT-07 on bounding the generation
itself.

---

## Generic type functions

### ZS-CT-09 [M] Generic types are `fn TitleCase(comptime T: type) type` — the only home of `Self`
Write the `comptime` keyword on type parameters even though `T: type` also compiles. Inside the
returned anonymous struct, `const Self = @This();` and a `self` receiver are correct, because the
type has no other name. In a file that *is* a type, name the receiver after the type instead.

**Why:** std writes `comptime` on ~94% of type parameters; the 52 bare `X: type` occurrences are the
outliers. And `const Self = @This();` survives in std exactly in the generic containers
(`array_list.zig`, `hash_map.zig`, `multi_array_list.zig`, `bit_set.zig`) — only 6 of 143
`TitleCase.zig` files still use it. So `Self` in a non-generic file is a reliable signal that the
author did not know the type's name at write time.

**Check:** `const Self = @This();` outside the body of a `fn TitleCase(comptime ...) type` — there
the type has a name and the receiver should use it (ZS-CORE-01b). And a bare `T: type` parameter
with no `comptime` keyword in front of it.

```zig
// verified — GOOD
const std = @import("std");

pub fn RingBuffer(comptime T: type, comptime capacity: usize) type {
    // The contract is `@compileError`, not `comptime assert` — ZS-CT-10.
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

### ZS-CT-10 [M!] Validate type parameters at the top of the type function with `@compileError`
Before returning the struct, check the requirements you actually depend on — required fields,
required decls, size bounds — and reject with a message that names your requirement. `[M!]` applies
to published library code and to any codebase where a misuse must not reach runtime — databases,
consensus, crypto, allocators, parsers on untrusted input. *Relaxed form:* state the requirement in
the type function's doc comment in the words the guard would have used, and make the body's *first*
use of `T` the one that fails — so the diagnostic still lands on the required field or decl rather
than forty lines into the returned struct.

**Why:** without the guard, the diagnostic surfaces at whatever line inside your body first fails to
compile — a `for` loop, a field access — and the reader sees your internals rather than their
mistake. Note `@FieldType(T, "link")` on a type with no such field is itself a compile error, so
short-circuit with `@hasField` first (`or` short-circuits at comptime).

**Check:** every `pub fn Name(comptime T: type) type` — its first statement must be a requirement
test ending in `@compileError`, before any `@typeInfo` walk, field access, or `return struct`. A
`@FieldType(T, "x")` not short-circuited by `@hasField(T, "x")` is the compiler's message, not
yours, and counts as unguarded.

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

### ZS-CT-11 [S] Non-generic core, generic wrapper of `inline fn` shims
For a generic container, write the data structure once over type-erased links or bytes, then wrap it
in a thin `fn Foo(comptime T: type) type` whose methods are `inline fn` one-liners.

**Why:** this is TigerBeetle's R39, and it is the one place where `inline fn` and generics are both
justified. The algorithm is compiled once regardless of how many element types exist; the shims
inline away to nothing, so the call cost is identical to the fully monomorphized version. Compile
time and binary size scale with the number of *methods*, not methods × types.

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

### ZS-CT-12 [M] Consume the std interface; never parameterize over it
Take `gpa: std.mem.Allocator`, `w: *std.Io.Writer`, `r: *std.Io.Reader`, `io: std.Io` as ordinary
runtime parameters. This is one rule with two failure modes, and both are common:

- **Parameterizing over it.** `fn Store(comptime Alloc: type) type`, `fn write(w: anytype)` — you
  monomorphize a subsystem over an interface that is already type-erased, paying N copies for a
  vtable you were given for free.
- **Inventing a parallel one.** A bespoke `MyOutput` with its own `write` method — you get the
  vtable cost anyway, and none of the ecosystem.

Reusable code that produces bytes takes `w: *std.Io.Writer` and returns `std.Io.Writer.Error!void`;
code that consumes bytes takes `r: *std.Io.Reader`; code that allocates takes
`gpa: std.mem.Allocator`; code that does I/O or concurrency takes `io: std.Io`.

**Why:** std made this exact decision deliberately and reversed the older generic design. One vtable
indirection per allocation is cheaper than N copies of your entire subsystem, and it is the
difference between a type your callers can store in a struct field and a type they cannot. The `zig
init` template states the positive half directly — accepting an `Io.Writer` instance is how you
write reusable code. Either deviation costs you the same thing: composition.
`std.testing.allocator`, `Allocator.failing`, `Io.failing`, `Writer.fixed`, `Writer.Allocating`,
`Writer.Discarding`, `Writer.hashed`, an `Io.File`, and a socket all speak the std interface and
none of them speak yours; every one of them would have to be re-implemented against your type.

**Check:** grep a diff for `comptime .*: type` whose name ends in `Allocator`, `Alloc`, `Writer`,
`Reader`, or `Io`, and for any new struct with a `vtable` field whose operations are "write bytes",
"read bytes", or "allocate". Both are this rule.

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
    var buf: [16]u8 = undefined;
    var w: std.Io.Writer = .fixed(&buf);
    try printReport(&w, &.{ 1, 2 });
    try std.testing.expectEqualStrings("1\n2\n", w.buffered());
}
```

### ZS-CT-13 [M] A `comptime` parameter the body does not depend on is a bug
If deleting the `comptime T: type` parameter and substituting the one type actually used leaves the
body unchanged, delete it. Same for a `comptime` value parameter that is only ever passed one value.

**Why:** the parameter still forces one instantiation per distinct argument, and the instantiations
are bit-identical machine code. You pay for monomorphization and receive nothing. This also shows up
as type-level metaprogramming standing in for a plain function: if a type function's whole job is to
compute a value, make it a function returning that value.

**Check:** for each `comptime` parameter, grep its call sites and count the distinct arguments. One
distinct argument across the whole tree means one instantiation and no reason for the parameter. In
the body, a `comptime T: type` that appears only in the signature — never in a field type, a
`@sizeOf`, a cast, or a `@typeInfo` — is the same finding.

---

## `anytype`

### ZS-CT-14 [M] `anytype` in a public API needs a documented contract and a guard
Any `pub fn` with an `anytype` parameter must (a) document the required shape in an in-signature doc
comment on that parameter, and (b) check it before doing any work in the body, emitting a
`@compileError` that names the requirement and the offending type.

**Why:** `anytype` carries no signature contract. Generated documentation shows the word `anytype`
and nothing else, so the contract exists only in prose. Worse, the diagnostic for a violation is
emitted inside *your* body: passing a `u32` to an unconstrained `items: anytype` that is iterated
produces `error: type 'u32' is not indexable and not a range` pointing at your `for` loop, with the
caller only visible in the `referenced by:` trace. The guard moves the message back to something the
caller can act on.

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

### ZS-CT-15 [S] Prefer a concrete parameter type, then `comptime T: type`, then `anytype`
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

### ZS-CT-16 [S] Use `anytype` where std uses it, and constrain it with `std.meta` predicates
The idiomatic uses are format-argument tuples (`args: anytype`), opaque user contexts
(`context: anytype`), hashers, and pointer-shaped duck typing (`allocation: anytype` in
`Allocator.resize`/`remap`/`free`). When the contract is "has this method," express it with
`std.meta.hasFn` / `std.meta.hasMethod` rather than hand-rolled `@typeInfo` walking.

**Why:** `std.meta.hasMethod(*T, "reset")` handles the pointer-vs-value and namespace cases
correctly (it dispatches on `.pointer` with size `.one` and falls through to `hasFn`), which
hand-written checks routinely get wrong. Following std's placement also means readers already know
what the parameter means without reading the body.

**Check:** a hand-rolled `@typeInfo(@TypeOf(x))` walk whose question is "does it have a decl named
…" — that is `std.meta.hasFn`/`hasMethod`. And an `anytype` parameter that is not a format-args
tuple, a `context`, a hasher, or a pointer-shaped allocation: it is outside the idiom and needs the
ZS-CT-14 guard.

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

### ZS-CT-17 [S] Pass behavior as a `comptime …Fn` parameter, last, after its `context`
When a generic algorithm needs a caller-supplied predicate, take a written-out function-type
parameter preceded by an opaque `context`, instead of an `anytype` object with an implied method.
Copy std's parameter order exactly — **type, data, `context`, comparator last**. Verbatim from
`std/sort.zig`:

```zig
// fragment — std/sort.zig, unmodified
pub fn insertion(
    comptime T: type,
    items: []T,
    context: anytype,
    comptime lessThanFn: fn (@TypeOf(context), lhs: T, rhs: T) bool,
) void
```

`insertion`, `heap`, `block`, `binarySearch`, `lowerBound`, `upperBound`, `equalRange`, `argMin`,
`argMax`, `isSorted`, `std.mem.sort` and `std.mem.sortUnstable` all use that order. Note the context
is `context: anytype` and the callback's first parameter is spelled `@TypeOf(context)` — the context
type is *derived*, never a separate `comptime Context: type` parameter. The type-level variant is
`PriorityQueue(comptime T, comptime Context, comptime compareFn)`, where the comparator is again
last.

**Why:** the function type is written out, so the contract is in the signature and the error for a
mismatched callback lands at the call site rather than inside your loop (ZS-CT-14). Deriving the
context type from the value means callers pass `void` for stateless predicates at zero storage cost,
and a stateful comparator carries its state without a closure. Ordering matters for a second reason:
a trailing function-type parameter is the one position where a multi-line callback reads cleanly,
and it keeps the data — the thing the reader is actually looking for — adjacent to the type.

**Where TigerStyle and std agree:** TigerStyle's callback-last convention and std's comparator-last
convention are the same rule reached independently. There is no conflict to resolve here; see also
`references/naming-and-files.md` ZS-NAME-12 for the naming half (`…Fn` suffix, `context` spelled in
full).

**Check:** any new function taking a `comptime …Fn` must place it last, immediately after its
`context`. A `comptime Context: type` parameter alongside a `context` value is the tell that the
signature was written from memory rather than from `std/sort.zig`.

```zig
// verified — GOOD
const std = @import("std");

/// Same parameter order as `std.sort.insertion` / `std.mem.sort`:
/// type, data, context, comparator last.
pub fn argMaxBy(
    comptime T: type,
    items: []const T,
    context: anytype,
    comptime lessThanFn: fn (context: @TypeOf(context), lhs: T, rhs: T) bool,
) ?usize {
    if (items.len == 0) return null;
    var best: usize = 0;
    for (items[1..], 1..) |item, index| {
        if (lessThanFn(context, items[best], item)) best = index;
    }
    return best;
}

const Row = struct { id: u32, score: f32 };

fn scoreLessThan(_: void, lhs: Row, rhs: Row) bool {
    return lhs.score < rhs.score;
}

test "context second-to-last, comparator last" {
    var rows = [_]Row{
        .{ .id = 1, .score = 0.5 },
        .{ .id = 2, .score = 2.5 },
        .{ .id = 3, .score = 1.5 },
    };
    // `void` context costs nothing when the predicate is stateless.
    try std.testing.expectEqual(1, argMaxBy(Row, &rows, {}, scoreLessThan));

    // The identical shape drives std, unchanged.
    std.mem.sort(Row, &rows, {}, scoreLessThan);
    try std.testing.expectEqual(1, rows[0].id);
    try std.testing.expectEqual(2, std.sort.argMax(Row, &rows, {}, scoreLessThan));
}
```

---

## Type introspection

### ZS-CT-18 [M] `@Type` is removed; use the dedicated type builtins
This rule owns the replacement set and its signatures; `references/migration-and-dead-apis.md`
ZS-MIG-02 keeps only the one-line table row.

`@Type` no longer exists — `error: invalid builtin function: '@Type'`. The replacements are
`@Int`, `@Tuple`, `@Struct`, `@Union`, `@Enum`, `@Pointer`, `@Fn`, `@EnumLiteral`. `std.meta.Int`
and `std.meta.Tuple`, the one-line 0.16 shims forwarding to `@Int`/`@Tuple`, are removed in 0.17:
`error: root source file struct 'meta' has no member named 'Int'`. There is deliberately no
`@Float`, `@Array`, `@Opaque`, `@Optional`, `@ErrorSet` or `@ErrorUnion` — those types have
ordinary syntax, so reflection was never needed to build them.

**Why:** in 0.16 the shims still compiled, so code that named them drifted from the standard with
no build failure to say so. `std/meta.zig` marked both (`/// Deprecated: use @Int`,
`/// Deprecated; use @Tuple instead. To be removed after Zig 0.16.0 releases.`), and 0.17 removed
them, so every spelling other than the dedicated builtins is now a build break.

**Check:** grep a diff for `@Type(`, `std.meta.Int`, and `std.meta.Tuple`. All three are build
breaks on 0.17, so the grep is a pre-flight for code carried over from 0.16 rather than something a
reviewer has to catch by eye.

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
// does-not-compile — BAD
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

### ZS-CT-19 [S] Reach for the narrowest introspection builtin before `@typeInfo` (see ZS-CT-20)
Owned by ZS-CT-20, which covers both halves of using `@typeInfo` correctly: when *not* to
reach for it, and how to spell it when you must.

### ZS-CT-20 [M] Use `@typeInfo` only to walk lists, and use the 0.17 spellings and accessors
Two halves, in order of application.

**Do not reach for `@typeInfo` at all** when a narrower builtin answers the question. `@TypeOf`,
`@FieldType(T, "a")`, `@hasField`, `@hasDecl`, `@field` are stable, read as what they mean, and
cannot break when std's reflection layout changes, as it did in 0.17. Prefer `@FieldType(T, "a")`
over `std.meta.fieldInfo(T, .a).type`; 0.17 deprecates
`fieldInfo`, `fieldNames` and `fieldTypes` in favor of `@typeInfo`. `@typeInfo` earns its keep only
when you genuinely need to iterate fields, decls, or error-set members. One trap: since 0.17
`@hasDecl` is `true` only for `pub` declarations, even when the caller is in the same file, so a
feature test over a private declaration that held in 0.16 now silently answers `false`. The langref
recommends feature detection via `@hasDecl`/`@hasField` over version comparisons.

**When you do walk a list, use the 0.17 spellings and accessor methods.** Tags are `.@"struct"`,
`.@"union"`, `.@"enum"`, `.@"fn"`, `.@"opaque"`, and plain `.pointer`, `.int`, `.float`,
`.optional`, `.error_union`, `.error_set`. A container's members are parallel slices, not a slice of
field structs: `.field_names[i]`, `.field_types[i]` and `.field_attrs[i]` for fields, `.decl_names`
for declarations. Read defaults with `info.field_attrs[i].defaultValue(info.field_types[i])`
(returns `?FieldType`) and sentinels with `ptr_info.sentinel()`, never by `@ptrCast`-ing the raw
`*anyopaque` pointer fields.

**Why:** the accessor methods encapsulate the `default_value_ptr`/`sentinel_ptr` representation, so
your code survives a representation change; the raw fields are the reason 0.14-era reflection code
does not survive. Three more traps: pointer and field alignment, `.pointer.attrs.@"align"` and
`.field_attrs[i].@"align"`, are `?usize` (`null` means natural alignment), not `comptime_int`;
`@typeInfo(E).error_set.error_names` is `?[]const [:0]const u8` where `null` means `anyerror`, so a
`null` check is not an "empty set" check; and a zero-bit tuple field is no longer implicitly
`comptime`, so filtering on `.field_attrs[i].@"comptime"` to skip zero-bit members now keeps them
(see `references/types-and-data.md` ZS-TYPE-37).

The `.Int` -> `.int` / `.Struct` -> `.@"struct"` renames (ZS-MIG-02) and 0.17's move from
`.fields` to `.field_names`/`.field_types`/`.field_attrs` are hard compile errors, so they are
listed in the migration tables of `references/migration-and-dead-apis.md` rather than enumerated
here. This rule is about the parts that still compile.

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

    var buf: [16]u8 = undefined;
    var w: std.Io.Writer = .fixed(&buf);
    const config: Config = .{};
    try writeFields(&w, config);
    try std.testing.expectEqualStrings("retries=3;", w.buffered());
}
```

---

## Interfaces

### ZS-CT-21 [M] Pick the interface shape from this table before writing any dispatch code
Zig has three shapes, plus one variant of the vtable shape. Choosing wrong is expensive to undo.

| Shape | Dispatch | Storable in a container? | Errors surface at | Use when |
|---|---|---|---|---|
| comptime duck typing (`anytype` / `comptime T`) | none, monomorphized | no — each impl is a distinct type | inside the callee body | one impl, hot, local; the whole call chain is comptime-known |
| runtime vtable (`*anyopaque` + `*const VTable`) | one indirect call | yes, single concrete type | at the call site | open set of impls; crosses a module or plugin boundary |
| embedded interface + `@fieldParentPtr` | indirect call, but only on the slow path | yes (`*Interface`) | at the call site | the interface owns a buffer/state the caller touches directly |
| tagged union + exhaustive `switch` | one jump table, inlinable | yes | at the call site | closed set known at compile time |

**Why:** the axis that matters is *who knows the set of implementations*. Comptime duck typing needs
the compiler to know the concrete type at every call, which means the interface cannot be stored,
returned as a common type, or crossed over an ABI boundary. A vtable gives up inlining to gain
exactly those three. A tagged union gives you storability *and* inlining at the price of a closed
set. There is no shape that gives all three.

**Check:** a diff that picks a row whose "use when" column is false for it. Two mechanical tells:
an `anytype` or `comptime T` interface whose values are later stored in a struct field, a container,
or a common return type — comptime duck typing cannot be stored; and a new `*const VTable` over a
set of implementations that all live in your own tree — that is ZS-CT-25's tagged union.

### ZS-CT-22 [M] The runtime vtable is two fields; recover the impl by `@ptrCast(@alignCast(…))`
Fields are a type-erased context pointer plus `vtable: *const VTable`. `std.mem.Allocator` spells it
`ptr: *anyopaque, vtable: *const VTable`; `std.Io` spells it `userdata: ?*anyopaque, vtable: *const
VTable`. Provide public wrapper methods on the interface so callers never touch `vtable` directly,
and hand out the interface from a method taking `*Self`.

**Why:** the context pointer aliases the implementation's storage, so the interface value must
not be built from anything about to be copied or moved — returning it from a method on `*Self` is
what pins it to a stable address. The wrapper methods matter because they are the only place the
`userdata` and the vtable slot are guaranteed to stay paired. `std.mem.Allocator` documents that
`ptr` may be `undefined` for stateless allocators and that comparing it is illegal behavior; treat
the context pointer as opaque, never as an identity.

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

### ZS-CT-23 [M] Embed a stateful interface as field `interface`; recover owner by `@fieldParentPtr`
This is the modern std house pattern. The implementation struct declares `interface: std.Io.Writer`
(or `Reader`) as a *field*, hands out `&self.interface`, and every vtable function starts with
`const self: *Impl = @alignCast(@fieldParentPtr("interface", io_w));`. Name the field `interface`;
std does so in `Io/File/Writer.zig`, `Io/File/Reader.zig`, `Io/Reader/Limited.zig`, `Io/net.zig`,
`http.zig`, and `testing.zig`.

**Why:** the interface value is not a wrapper around the implementation, it *is* part of it, so
there is no second allocation, no context pointer to keep in sync, and no way for the two to become
separated. `std.Io.Writer` holds `vtable`, `buffer: []u8`, and `end: usize` inline — the caller
writes straight into `buffer` and the vtable is only reached when the buffer overflows or on flush,
so the indirect call is off the hot path entirely. `@fieldParentPtr` is what makes this work: it
subtracts the field offset, which is comptime-known, so recovery is free. Write the `@alignCast`
unconditionally — but not "to match std", which does not: 97 of 0.17 std's 172 `@fieldParentPtr`
calls wrap it and **75 do not**, including `Io/Reader/Limited.zig`, otherwise this exact pattern.
Write it because it is *required* whenever the field's alignment is weaker than the parent's, and
free when it is not, so unconditional is the only spelling that cannot go wrong as the struct
changes shape underneath it. Corollary: never copy a struct that contains a live `interface` field
— a `*Io.Writer` handed out earlier now points into the dead original.

**Check:** an `Io.Writer`/`Io.Reader` field named anything but `interface`; a `@fieldParentPtr`
whose first argument is some other name for those types; in **code the diff adds**, a
`@fieldParentPtr` not wrapped in `@alignCast` — this is the enforcement hook ZS-IO-17 delegates
here, and it is the whole rule: existing call sites are left alone (75 of std's 172 omit it), new
ones are written unconditionally so the next field reorder cannot turn a compiling line into a
failing one; and — the corollary — any `return`, assignment, or `append` that copies a struct with
an `interface` field by value after `&x.interface` has been handed out.

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
        var n: usize = 0;
        for (data[0 .. data.len - 1]) |bytes| n += bytes.len;
        n += data[data.len - 1].len * splat;
        cw.count += n;
        return n;
    }
};
```

### ZS-CT-24 [S] Give vtable members defaults so implementations only override what they must
Declare optional operations with a default implementation in the `VTable` struct itself, so an
implementation's vtable literal lists only the required functions.

**Why:** this is how std keeps implementations to a handful of lines. `std.Io.Writer.VTable`
requires only `drain`; `sendFile` defaults to `unimplementedSendFile`, `flush` to `defaultFlush`,
`rebase` to `defaultRebase`. `std.Io.Reader.VTable` requires only `stream`; `discard`, `readVec`,
and `rebase` all default. Adding a new optional operation with a default is then a
backwards-compatible change instead of breaking every implementation in the ecosystem.

**Check:** a `VTable` struct whose fields carry no `= default…` initializers, sitting next to two or
more implementations whose vtable literals name the same function with the same body. That repeated
function is the default that was not declared.

### ZS-CT-25 [M] A closed set of implementations is a tagged union, not an interface
If every implementation is known at compile time and lives in your own tree, model it as
`union(enum)` with methods that `switch` exhaustively. Do not write an `else` prong.

**Why:** you get storability and direct calls at once — the switch is a jump table the optimizer
can see through and often inline, with no function pointer to defeat devirtualization, and the union
value can live in an array. The exhaustiveness is the real prize: adding a variant becomes a compile
error at every site that must handle it. An `else` prong throws that away. `std.Build.LazyPath` is
the canonical std example. Reimplementing dynamic dispatch for a set you already know is paying an
indirect call and losing exhaustiveness for nothing.

**Check:** a new `vtable: *const VTable` — enumerate its implementations. If every one lives in your
own tree, it is a `union(enum)`. And `else =>` in any `switch` over a union you own, which is the
other half of ZS-TYPE-28.

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

### ZS-CT-26 [M] Consume the std interface instead of inventing a parallel one (see ZS-CT-12)
Owned by ZS-CT-12. "Consume the std interface" and "do not parameterize over it" are the same
rule seen from two sides — both say that `Allocator`, `*Io.Writer`, `*Io.Reader` and `Io` are
runtime parameters you take as-is — so they are stated once, at ZS-CT-12.

### ZS-CT-27 [M] `usingnamespace` is removed; re-export explicitly (see ZS-MIG-02)
Owned by `references/migration-and-dead-apis.md` ZS-MIG-02. `pub usingnamespace S;` is a *parse*
error in 0.17 (`expected function or variable declaration after pub`); re-export each name with
`pub const name = impl.name;`, which is also what makes a module's public surface greppable.

---

## Debugging comptime

### ZS-CT-28 [M] Debug comptime errors with `-freference-trace`, and delete every `@compileLog`
Every failure mode in this chapter reports at the innermost frame, which is almost never the frame
that caused it. Two tools address that, and both need discipline.

**`-freference-trace[=num]`.** Every comptime diagnostic ends with a `referenced by:` chain, but the
default shows only the first few frames and then prints
`N reference(s) hidden; use '-freference-trace=<N+2>' to see all references`. Raise it and re-run —
the frame you want is usually the deepest non-std one. It works on `zig build-obj`, `zig test`, and
`zig build`; for a build, pass `zig build -freference-trace=20` (0.17 removed `b.reference_trace`,
so `build.zig` can no longer set it).

**Why:** `error: unable to resolve comptime value` names the line where a runtime value met a
`comptime` parameter — but the bug is at the call site that made the value runtime-known, which may
be forty frames up through generic instantiations that all look identical. The reference trace is
the only artifact connecting the two. This is the single highest-value flag for this chapter's
entire failure surface: ZS-CT-04's leaked `comptime var`, ZS-CT-06's runtime `inline for` bound,
ZS-CT-10 and ZS-CT-14's unguarded type parameters, and every `@compileError` you emit are all
reported at a line the caller did not write.

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

For a check that should *stay* in the source, use `comptime { assert(...) }` or `@compileError`
with a message naming the requirement (ZS-CT-10), not `@compileLog`.

**Check:** `rg -n "@compileLog"` over the diff must return nothing. If a comptime bug report in a
review says only "unable to resolve comptime value", ask for the output with `-freference-trace`
raised — the bare diagnostic does not identify the caller.

```zig
// does-not-compile — BAD: `@compileLog` fails the build by design; never commit one.
// error: found compile log statement
// Compile Log Output:
// @as(*const [3:0]u8, "u32"), @as(comptime_int, 4)
fn sizeOfLogged(comptime T: type) usize {
    @compileLog(@typeName(T), @sizeOf(T));
    return @sizeOf(T);
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

**std's position:** the opposite for the three central abstractions. `std.mem.Allocator`,
`std.Io`, and `std.Io.Writer`/`Reader` are all runtime vtables. std explicitly traded static
dispatch away for storability, ABI stability, and one compiled copy of every consumer.

**Recommendation, keyed to the tiers:**
- [M] Take `Allocator`, `*Io.Writer`, `*Io.Reader`, and `Io` as runtime interfaces (ZS-CT-12).
  This is not a style preference: hand-rolling around them costs you the entire std
  ecosystem, and comptime-parameterizing on an allocator type is a pattern std deliberately deleted.
- [S] For your *own* abstractions, follow TigerStyle: prefer no abstraction, then a tagged union
  (ZS-CT-25), then an interface. Reach for a vtable only when the implementation set is genuinely
  open.
- [M!] In high-reliability code — databases, consensus, embedded, crypto, allocators, anything
  where a crash or corruption is unacceptable — apply TigerStyle's static-dispatch preference to
  the hot path, and use ZS-CT-11 (type-erased core + `inline fn` shims) to get direct calls without
  N-fold monomorphization. Elsewhere, one indirect call is not worth designing around.

A smaller disagreement: TigerStyle uses `inline fn` freely for shims, while the langref says "it is
generally better to let the compiler decide when to inline a function." ZS-CT-05 resolves it — the
shim case (a one-line forwarder over a type-erased core) is exactly reason (a), so both are
satisfied.
