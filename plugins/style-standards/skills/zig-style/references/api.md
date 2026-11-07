# API: The Public Surface, Signatures, Symmetry, and Evolution

Scope: what a Zig package makes public and how a public function is shaped for its callers: which
declarations are `pub`, what `src/root.zig` exports, the parameters and return of a function, the
pairs and siblings a surface keeps alike, and how a declaration is deprecated before it goes. The
error sets a public function names are the errors chapter's; the type a value has is the data
chapter's; what a `pub` item's doc comment says is the documentation chapter's; the layout of the
files the root sits among is the modules chapter's.

## Contents

- **The boundary**
  - ZS-API-01 [M] Default to non-`pub`; mark `pub` only what a caller outside the file needs
  - ZS-API-02 [M] `src/root.zig` is the module root and the entire public surface
- **Signatures**
  - ZS-API-03 [M] Split a function rather than adding a mode parameter
  - ZS-API-04 [M] Use an options struct whenever two adjacent parameters share a type
  - ZS-API-05 [M] Signal ownership transfer in the name and the doc comment
  - ZS-API-06 [M] Take the slice or the interface, not the container; return the concrete type
- **Symmetry**
  - ZS-API-07 [M] Give every operation its inverse, or document why there is none
  - ZS-API-08 [M] Keep parameter order identical across sibling functions
  - ZS-API-09 [M] Give the members of one error set a uniform shape
- **Evolution**
  - ZS-API-10 [M] Keep a deprecated declaration for a release, and name its replacement

---

## The boundary

### ZS-API-01 [M] Default to non-`pub`; mark `pub` only what a caller outside the file needs

A declaration starts private and becomes `pub` when a caller in another file needs it. Which of the
`pub` names form the package's surface is decided once, in `root.zig` (ZS-API-02).

**Why:** `pub` is the module's API contract and everything `pub` is something you cannot rename
later without a breaking change; the compiler will not tell you which `pub`s are unused.

**Check:** a `pub` added in the diff whose name no file but its own uses should not be `pub`.

### ZS-API-02 [M] `src/root.zig` is the module root and the entire public surface

Consumers can only reach declarations reachable from the root source file. Re-export everything
public from `root.zig`; anything not re-exported is private by construction.

`src/main.zig` is the CLI root module and imports the library by name (`@import("myproj")`), not by
path. Keeping business logic out of `main.zig` is what makes the library independently testable and
embeddable.

**Why:** Zig has no `pub(crate)` and no export lists — the reachability graph from the module root
*is* the visibility system. This makes the public API a single reviewable file, and it means adding
a file under `src/` does not silently widen your API.

**Check:** `git ls-files 'src/*.zig'` against the `pub` declaration chain from `root.zig` — a type
the README tells consumers to use that is not reachable from `root.zig` is the finding. And
`src/main.zig` reaches the library as `@import("myproj")`, never as `@import("root.zig")`.

```zig
//! Public API surface of the `myproj` module. Anything a consumer may touch is
//! re-exported here; files not reachable from this file are private.
// fragment — GOOD: src/root.zig
const std = @import("std");

pub const constants = @import("constants.zig");
pub const Parser = @import("parser.zig").Parser;
pub const version = @import("build_options").version;
```

## Signatures

### ZS-API-03 [M] Split a function rather than adding a mode parameter

When a parameter selects behavior rather than supplying data, the function has become two functions
sharing a body. Split it and let the shared part be a private helper.

**Why:** a mode parameter makes the return type and the error set the union of both modes, so every
caller handles cases that cannot arise in its mode — the opposite of ZS-DATA-26. Splitting gives
each caller a precise signature and makes the shared logic explicit.

**Check:** for each parameter, does the body branch on it at the top level? If the two branches
share little, it is two functions with two names.

### ZS-API-04 [M] Use an options struct whenever two adjacent parameters share a type

TigerStyle states the hard form: a function taking two `u64` **must** use an options struct. Extend
it to any pair of same-typed parameters a caller could transpose, and to any parameter whose `null`
would be unreadable at the call site. std does this at scale, with an `…Options` struct for almost
every call that takes more than a couple of settings.

Singleton dependencies with unique types (an allocator, an `Io`, a tracer) stay **positional** and
are threaded most-general to most-specific, because their types already prevent transposition.

A `_max` / `_min` companion sitting beside the value it bounds is exempt too:
`(op: u64, op_max: u64)` is two `u64`s and stays positional — as in ZS-ASSERT-13's
`fn sendPrepareOk(status: Status, view: u32, op: u64, op_max: u64) bool`. The pair is not
transposable in practice: `op_max` is named *after* `op` and reads as its ceiling, so a swapped call
is wrong at a glance in a way that `copyRange(x, y, 4, 0, 2)` is not. This adjacency is exactly what
ZS-NAME-07's big-endian naming exists to create, and burying the pair in an options struct destroys
it. The exemption covers a bounded value and its bound only; it does not extend to two unrelated
`u64`s.

**Why:** Zig has no named arguments; an options struct is how you get them. Transposed same-typed
arguments type-check and produce wrong behavior at run time — the compiler cannot help. Field names
at the call site turn that into a compile error.

**Check:** any `fn` signature in the diff with two adjacent parameters of the same type, or any
parameter of type `?T` whose `null` a reader could not name at the call site. Then apply the two
exemptions above: a singleton dependency with a unique type, and a value beside its `_max`/`_min`
companion. Everything else is an options struct.

```zig
// fragment — BAD: this compiles, which is exactly the problem.
copyRange(source, target, 4, 0, 2); // which offset is which?
```

```zig
// verified — GOOD
pub const CopyOptions = struct {
    source_offset: usize,
    target_offset: usize,
    len: usize,
};

pub fn copyRange(source: []const u8, target: []u8, options: CopyOptions) void {
    @memcpy(
        target[options.target_offset..][0..options.len],
        source[options.source_offset..][0..options.len],
    );
}
// call site: copyRange(source, target, .{ .source_offset = 1, .target_offset = 0, .len = 2 });
```

```zig
// fragment — the exempt pair, with `assert` as the ZS-MOD-09 alias
// `op_max` is `op`'s ceiling, not a second interchangeable argument.
fn opCommitted(op: u64, op_max: u64) bool {
    assert(op_max >= 1);
    return op <= op_max;
}
```

### ZS-API-05 [M] Signal ownership transfer in the name and the doc comment

A function that returns memory the caller must free says so: `/// Caller owns the returned memory.`
Follow std's vocabulary — `dupe`, `dupeSentinel`, `alloc*`, `create`, `clone`, `toOwnedSlice`, and
an `Alloc` suffix (`currentPathAlloc`) transfer ownership; `items`, `slice()`, `buffered()`,
`written()`, `lastPtr()`, `unusedCapacitySlice()` return a **borrow** valid only until the next
mutation.

Corollary: take `[]const u8` for borrowed input. Take `[]u8` only when you will mutate or free it —
a `[]u8` parameter is a claim.

**Why:** Zig has no ownership in the type system: `[]u8` from `dupe` and `[]u8` from `list.items`
are the same type and opposite contracts. The name and the one-line doc comment are the entire
enforcement mechanism, which is why std writes it on every such function.

**Check:** a `pub fn` returning `[]T`, `[]const T`, or `*T` whose doc comment says neither "Caller
owns" nor "Invalidated by"; and a function whose name comes from the borrow vocabulary (`items`,
`slice`, `written`, `buffered`, `view`) but whose body allocates.

```zig
// fragment
/// Caller owns the returned slice; free it with `gpa`.
pub fn renderTitle(gpa: Allocator, doc: *const Doc) Allocator.Error![]u8 {
    return gpa.dupe(u8, doc.title);
}

/// Borrowed view of the internal buffer. Invalidated by the next call to
/// `append` or `deinit`.
pub fn titleView(doc: *const Doc) []const u8 {
    return doc.title;
}
```

### ZS-API-06 [M] Take the slice or the interface, not the container; return the concrete type

A function that only reads takes `[]const T`, and one that only writes takes `*std.Io.Writer`, never
the `ArrayList` or the buffer a caller happens to hold. What it returns is the type it built, not a
pointer to an interface of it.

**Why:** a slice takes an array, a list's `items` and a sub-range alike, so a parameter typed as one
container makes every other caller copy into it. A caller holding the concrete return can use all of
it, while narrowing a return later removes methods callers already call.

**Check:** every `pub fn` with a `*const std.ArrayList(T)` parameter it only reads, or a
`*std.ArrayList(u8)` it only appends to. Each takes `[]const T` or `*std.Io.Writer` instead.

```zig
// verified — GOOD
const std = @import("std");

/// Sums any run of values, whichever container holds them.
pub fn sum(values: []const u32) u32 {
    var total: u32 = 0;
    for (values) |value| total += value;
    return total;
}

test "a list's items and an array both pass as a slice" {
    const gpa = std.testing.allocator;
    var list: std.ArrayList(u32) = .empty;
    defer list.deinit(gpa);
    try list.append(gpa, 2);
    try list.append(gpa, 3);
    try std.testing.expectEqual(5, sum(list.items));
    const array = [_]u32{ 1, 2 };
    try std.testing.expectEqual(3, sum(&array));
}
```

```zig
// fragment — BAD: only a list can be passed, though the body reads a slice
pub fn sum(values: *const std.ArrayList(u32)) u32 {
    var total: u32 = 0;
    for (values.items) |value| total += value;
    return total;
}
```

## Symmetry

### ZS-API-07 [M] Give every operation its inverse, or document why there is none

`init` implies `deinit` (ZS-DATA-14 is this rule's most important instance), but so does
`append`/`pop`, `open`/`close`, `encode`/`decode`, `acquire`/`release`, `register`/`unregister`.

**Why:** a caller who learns half a pair assumes the other half exists. When it is genuinely absent,
the absence is meaningful — the operation is lossy, the handle is consumed, the resource is owned
elsewhere — and silence reads as an oversight that gets worked around.

**Check:** list the public operations on each type in pairs. Every unpaired one either gains its
inverse or gains a doc comment saying why it cannot have one.

### ZS-API-08 [M] Keep parameter order identical across sibling functions

Fix the order once and do not vary it: if one function takes `(io, gpa, target, source)`, its
siblings do too. ZS-NAME-11 fixes the order for function-value slots by copying `std.sort`; this
rule is the same discipline applied to your own functions.

**Why:** siblings are called from the same code, often adjacent, and the reader generalizes from the
first one they learn. When the types match, an inconsistent order compiles, so the failure is a
silently swapped argument at a call site that looks correct.

**Check:** list every function in the file taking two or more parameters of related type and compare
their orders. Any disagreement is the finding, and the outlier is what changes.

### ZS-API-09 [M] Give the members of one error set a uniform shape

Members of one error set describe failures at one level of detail. Do not mix
`error.InvalidByteAtOffset` with a bare `error.Bad` in the same set, and do not let one call site
carry rich diagnostics through a side channel while its siblings carry none.

**Why:** the caller writes one `switch` over the set, and asymmetric members make that switch
asymmetric — some arms can report a position, some cannot, so the reporting code grows special cases
for the deficient members. Uniform shape is what lets one function render every failure.

**Check:** tabulate the set's members against the diagnostic context each one can supply. A column
populated for most members and empty for one is either a missing detail or a member that belongs in
a different set.

## Evolution

### ZS-API-10 [M] Keep a deprecated declaration for a release, and name its replacement

A `pub` declaration that is renamed or replaced stays one release as an alias or a thin wrapper,
with a doc comment that starts `Deprecated:` and names the new one; it is removed in the next major
version, never in a patch.

**Why:** Zig has no deprecation attribute and the compiler warns of none, so the doc comment is the
whole notice. A name that vanishes without one is a build break in code its author never sees, and
std itself keeps `std.ArrayListUnmanaged` as a marked alias for exactly this.

**Check:** for each `pub` declaration removed or renamed in the diff, was the previous release
shipping it as an alias whose doc comment starts `Deprecated:` and names the replacement? A removal
with no such release, or a notice naming nothing, is the finding.

```zig
// verified — GOOD
const std = @import("std");

/// Byte order of a field.
pub const ByteOrder = enum { big, little };

/// Deprecated: use `ByteOrder`; removed in 2.0.
pub const Endian = ByteOrder;

test "the old name still names the new type" {
    try std.testing.expect(Endian == ByteOrder);
}
```
