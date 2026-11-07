# comptime, generics, and interfaces

Scope: compile-time evaluation (`comptime` params, blocks, `inline`, `@setEvalBranchQuota`), generic
type functions, `anytype` and its costs, type introspection with the 0.17 builtins, and how the
runtime interfaces are built (the vtable, the embedded interface). Which interface shape to pick,
the closed set that is a tagged union instead, an `anytype`'s contract and how far a parameter is
generic are the types chapter's. Naming of type functions and receivers is the naming chapter's;
`std.Io.Writer`/`Reader` usage and buffering the concurrency chapter's; `comptime {}` assertions
about wire and disk layout the assertions chapter's.

Every abstraction costs something, and in Zig the cost is concrete: a comptime abstraction costs
binary size and compile time, a vtable costs an indirect call and an optimization barrier. Choosing
the shape is ZS-TYPE-01's; ZS-COMPTIME-09 keeps the cost from becoming damage: if a `comptime`
parameter is being bent to make an interface fit, the interface is wrong and the fallback is a
concrete type.

std chose the other way for its three central abstractions: `std.mem.Allocator`, `std.Io` and
`std.Io.Writer`/`Reader` are runtime vtables, trading static dispatch for storability, ABI stability
and one compiled copy of every consumer, which is why ZS-COMPTIME-08 takes them as runtime
interfaces. TigerBeetle, which predates `std.Io`, parameterizes its whole storage and replica stack
on comptime types instead, so every call is direct.

Unlike the other chapters, the blocks here carry their own `const std = @import("std");` rather than
assuming a file-scope preamble — several of them are whole files, and the point of a type function
is often what it does at the top of a file.

Each symptom below, and the rule it breaks:

| Symptom | Rule |
|---|---|
| `fn F(comptime T: type)` with one caller ever | ZS-COMPTIME-09 |
| `comptime` keyword at container scope | the compiler (Decided by tools) |
| `inline fn` on a non-trivial function | ZS-COMPTIME-03 |
| `inline for` over a homogeneous array | ZS-COMPTIME-04 |
| `@setEvalBranchQuota(1000000)` | ZS-COMPTIME-05 |
| Generic over the allocator or writer type | ZS-COMPTIME-08 |
| Bare `anytype` in a `pub fn` | ZS-TYPE-04, ZS-TYPE-05 |
| `@Type(...)`, `std.meta.Int`, `std.meta.Tuple` | ZS-COMPTIME-11 |
| `@typeInfo(T).Struct`, `.@"struct".fields`, a raw `default_value_ptr` | ZS-COMPTIME-11 |
| Hand-rolled vtable for a closed set of impls | ZS-TYPE-02 |
| `usingnamespace` | ZS-API-02 |
| `error: unable to resolve comptime value` with no visible cause | ZS-COMPTIME-15 |

## Contents

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
  - ZS-COMPTIME-08 [M] Consume the std interface; never parameterize over it
  - ZS-COMPTIME-09 [M] A `comptime` parameter the body does not depend on is a bug
- **`anytype`**
  - ZS-COMPTIME-10 [S] Use `anytype` where std uses it, and constrain it with `std.meta` predicates
- **Type introspection**
  - ZS-COMPTIME-11 [M] Use `@typeInfo` only to walk lists, and use the 0.17 spellings and accessors
- **Interfaces**
  - ZS-COMPTIME-12 [M] The runtime vtable is two fields; recover the impl by `@ptrCast(@alignCast(…))`
  - ZS-COMPTIME-13 [M] Embed a stateful interface as field `interface`; recover owner by `@fieldParentPtr`
  - ZS-COMPTIME-14 [S] Give vtable members defaults so implementations only override what they must
- **Debugging comptime**
  - ZS-COMPTIME-15 [M] Debug comptime errors with `-freference-trace`, and delete every `@compileLog`
- Decided by tools

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

## `inline` and its real costs

### ZS-COMPTIME-03 [S] Treat `inline fn` as a semantic guarantee, not an optimizer hint

The langref is explicit: inlining "is not a hint to be possibly observed by optimization passes, but
has implications on the types and values involved in the function call." It also names the only
three uses it addresses: (a) ensuring certain stack frames are in the call stack, for debugging or
for integrating with assembly, (b) forcing comptime-known arguments to propagate to the return
value, and (c) working around limitations of a compiler backend. Otherwise let the optimizer decide.
Deviating needs a comment naming which of the three applies. Speed is not one of them: a performance
`inline` rests on a measurement the comment cites (ZS-PERF-28). The one-line forwarding shims of
ZS-PERF-15 are a sanction of their own, without a fresh measurement, because there the `inline` is
what makes the type-erased core cost what the monomorphized version would.

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
depth depends on user-supplied data is prohibited, as all such recursion is (ZS-ERR-22).

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
ZS-NAME-13 allows them.

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
*Relaxed form:* state the requirement in the doc comment in the words the guard would have used, and
make the body's *first* use of `T` the one that fails — so the diagnostic still lands on the
required field or decl rather than forty lines into the returned struct.

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

### ZS-COMPTIME-08 [M] Consume the std interface; never parameterize over it

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

**Check:** `rg -n 'comptime \w*(Allocator|Alloc|Writer|Reader|Io): type' -g '*.zig'` finds a type
parameter standing for a std interface; each hit is the finding. So is a new struct with a `vtable`
field whose operations are "write bytes", "read bytes", or "allocate", and a parameter typed
`*Io.File` where a `*Io.Reader` or `*Io.Writer` would do.

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

### ZS-COMPTIME-09 [M] A `comptime` parameter the body does not depend on is a bug

If deleting the `comptime T: type` parameter and substituting the one type actually used leaves the
body unchanged, delete it. Same for a `comptime` value parameter that is only ever passed one value.
The same goes for a type function whose whole job is to compute a value: make it a function
returning that value.

**Why:** the parameter still forces one instantiation per distinct argument, and the instantiations
are bit-identical machine code. You pay for monomorphization and receive nothing.

**Check:** for each `comptime` parameter, count the distinct arguments its call sites pass. One
distinct argument across the whole tree means one instantiation and no reason for the parameter. In
the body, a `comptime T: type` that appears only in the signature — never in a field type, a
`@sizeOf`, a cast, or a `@typeInfo` — is the same finding.

## `anytype`

### ZS-COMPTIME-10 [S] Use `anytype` where std uses it, and constrain it with `std.meta` predicates

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
ZS-TYPE-04 guard.

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

### ZS-COMPTIME-11 [M] Use `@typeInfo` only to walk lists, and use the 0.17 spellings and accessors

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
(ZS-DATA-38).

The `.Int` -> `.int` / `.Struct` -> `.@"struct"` renames and 0.17's move from `.fields` to
`.field_names`/`.field_types`/`.field_attrs` are hard compile errors, so they are rows of the
migration table rather than enumerated here. This rule is about the parts that still compile.

**Why:** the accessor methods encapsulate the `default_value_ptr`/`sentinel_ptr` representation, so
code that calls them survives a representation change, and code that reads the raw fields does not.

**Check:** every `@typeInfo` in a diff must be followed by an `inline for` or an equivalent list
walk; if it is followed by a single field or decl access, a narrow builtin does it better.
`rg -n 'default_value_ptr|sentinel_ptr' -g '*.zig'` finds a raw pointer field read; each hit is the
finding, and `defaultValue(FieldType)` / `sentinel()` its replacement.

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

## Interfaces

### ZS-COMPTIME-12 [M] The runtime vtable is two fields; recover the impl by `@ptrCast(@alignCast(…))`

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

### ZS-COMPTIME-13 [M] Embed a stateful interface as field `interface`; recover owner by `@fieldParentPtr`

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

### ZS-COMPTIME-14 [S] Give vtable members defaults so implementations only override what they must

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

## Debugging comptime

### ZS-COMPTIME-15 [M] Debug comptime errors with `-freference-trace`, and delete every `@compileLog`

Every failure mode in this chapter reports at the innermost frame, which is almost never the frame
that caused it. Two tools address that, and both need discipline.

**`-freference-trace[=num]`.** Every comptime diagnostic ends with a `referenced by:` chain, but the
default shows only the first few frames and then prints
`N reference(s) hidden; use '-freference-trace=<N+2>' to see all references`. Raise it and re-run —
the frame you want is usually the deepest non-std one. It works on `zig build-obj`, `zig test`, and
`zig build`; for a build, pass `zig build -freference-trace=20` (0.17 removed `b.reference_trace`,
so `build.zig` can no longer set it).

It is the single highest-value flag for this chapter's failure surface: ZS-COMPTIME-02's leaked
`comptime var`, ZS-COMPTIME-04's runtime `inline for` bound, ZS-COMPTIME-07 and ZS-TYPE-04's
unguarded type parameters, and every `@compileError` you emit are all reported at a line the caller
did not write.

`@compileLog` needs its own discipline. `@compileLog` is not a print statement: reaching one is
itself `error: found compile log statement`, and the values are dumped in a `Compile Log Output:`
block after the error. So the build fails by design, a `@compileLog` left in a shared branch breaks
everyone's build, and it can never be committed. Three consequences:

- Treat it exactly like a debugger breakpoint — add, read, delete, in one sitting. Never commit one.
- It renders comptime *values*, not types: log `@typeName(T)` rather than `T`, and `@sizeOf(T)`
  rather than a type expression, or you get `@as(type, ...)` noise.
- Because it aborts, you get one shot per compile. Log several values in one call —
  `@compileLog(@typeName(T), @sizeOf(T), i)` — rather than bisecting across builds.

For a check that should *stay* in the source, use `comptime { assert(...) }` or `@compileError` with
a message naming the requirement (ZS-COMPTIME-07), not `@compileLog`.

**Why:** `error: unable to resolve comptime value` names the line where a runtime value met a
`comptime` parameter, but the bug is at the call site that made the value runtime-known, which may
be forty frames up. The reference trace is the only artifact connecting the two.

**Check:** `rg -n "@compileLog"` over the diff must return nothing. If a comptime bug report in a
review says only "unable to resolve comptime value", ask for the output with `-freference-trace`
raised — the bare diagnostic does not identify the caller.

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

## Decided by tools

The compiler rejects each of these on its own; no setting turns one off.

| Tool | Lint | Level | Forbids |
|---|---|---|---|
| zig | `redundant comptime keyword in already comptime scope` | error | `comptime` on what is comptime already: a container initializer, an array length, a type |
