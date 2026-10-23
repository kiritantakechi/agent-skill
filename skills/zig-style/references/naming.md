# Naming, Files, Module Layout, Declaration Order, Comments

Scope: how identifiers are cased and worded, how a `.zig` file is named and laid out, the order of
declarations inside a file and inside a struct, `pub` discipline, the three comment
forms and the phrasings std uses for API contracts, and the formatting mechanics (`zig fmt`, the
trailing comma, 100 columns). Semantics of the things being named live elsewhere: error-set design
in the errors chapter, `init`/`deinit`/ownership contracts in the memory chapter, `format` and
`std.Io` in the concurrency chapter, `test` mechanics and fuzzing in the testing chapter, and
`build.zig` naming in the build chapter.

Two sources are merged here: the **official Zig style guide** (langref 0.17.0 §Style Guide, quoted
verbatim where it is normative) and **TigerStyle** (TigerBeetle's house standard). Where they
disagree, the disagreement is stated outright in the rule, with a recommendation keyed to the tier.

Unless a block shows its own imports, it assumes the preamble this chapter prescribes in
ZS-NAME-16: `const std = @import("std");` and `const assert = std.debug.assert;`. Where a
snippet's file name matters to the rule, it is named in the comment above it.
## Contents

- **Casing and word choice**
  - ZS-NAME-01 [M] Apply the official casing rules exactly
  - ZS-NAME-02 [M] Capitalize acronyms as ordinary English words
  - ZS-NAME-03 [M] Never prefix with `_`; resolve keyword collisions with `@"..."`
  - ZS-NAME-04 [M] Spell names out; abbreviate only as scope tightens
  - ZS-NAME-05 [M] Delete words that apply to every type, and segments the FQN already carries
  - ZS-NAME-06 [M] Put units and qualifiers last, sorted by descending significance
  - ZS-NAME-07 [S] Name the thing so it survives being said out loud
  - ZS-NAME-08 [M] Prefix a helper with the name of the function that calls it
  - ZS-NAME-09 [M] Use an options struct whenever two adjacent parameters share a type
  - ZS-NAME-10 [S] Reach for `io.async` first; give the function values that remain std's slot order
  - ZS-NAME-11 [S] Use std's suffix vocabulary for method variants
- **Receivers**
  - ZS-NAME-12 [M] Name the receiver after its type; keep `self` for anonymous generic containers
- **Files and modules**
  - ZS-NAME-13 [M] Name a file `TitleCase.zig` if and only if it has top-level fields
  - ZS-NAME-14 [S] Name a directory after its companion file
  - ZS-NAME-15 [M] Keep the `@This()` alias and the whole import block in one place
  - ZS-NAME-16 [S] Order imports `@This()` → `builtin` → `std` → local, and alias the hot names
  - ZS-NAME-17 [M] Order a struct body: fields → types → `init`/`deinit` → methods → tests
  - ZS-NAME-18 [S] Put the entry point and the most important declarations first
  - ZS-NAME-19 [M] Default to non-`pub`; mark `pub` only what a caller outside the file needs
- **Comments**
  - ZS-NAME-20 [M] `//!` at the file top, `///` on declarations, `//` for everything else
  - ZS-NAME-21 [M] Use std's contract phrasings verbatim
  - ZS-NAME-22 [M] Say why, not what — including at the top of every test
  - ZS-NAME-23 [S] Comment typography: space after the slashes, capital letter, full stop
- **Formatting**
  - ZS-NAME-24 [M] Run `zig fmt`; the trailing comma is your only formatting lever
  - ZS-NAME-25 [M] Hard-limit every line to 100 columns
- **Names beyond the source file**
  - ZS-NAME-26 [M] One term, one meaning, project-wide
  - ZS-NAME-27 [M] Write the commit message; a pull-request description is not one
- **Symmetry across a codebase**
  - ZS-NAME-28 [M] Name the two halves of a pair symmetrically
  - ZS-NAME-29 [M] One concept, one mechanism
  - ZS-NAME-30 [S] Keep sibling modules structurally parallel
- Decided by tools

---

## Casing and word choice

### ZS-NAME-01 [M] Apply the official casing rules exactly

`TitleCase` for types, type aliases, and callables whose return type is `type`. `camelCase` for
every other callable. `snake_case` for everything else, including 0-field structs used as
namespaces. The langref is explicit: "If `x` is a struct with 0 fields and is never meant to be
instantiated then `x` is considered to be a 'namespace' and should be `snake_case`."

> TigerStyle conflicts here: N2 mandates `snake_case` for **function** names too (`read_sector`, not
> `readSector`). TigerBeetle is internally consistent about it and it works for them, but any call
> into std in the same expression is `camelCase`, so a mixed-case expression is unavoidable.
> **Recommendation: use `camelCase` functions ([M]).** Uniform `snake_case` functions are defensible
> only in a closed codebase with zero public API surface, and only if enforced mechanically.

**Why:** these are the rules the compiler's own diagnostics, `std`, and every published package
follow, so casing carries information: seeing `foo.Bar` you know `Bar` is a type without looking it
up, and seeing `foo.bar()` you know `bar` returns a value. Mixed conventions destroy that signal.

**Check:** three greps over the diff. A `fn` whose name starts with a capital and whose return type
is not `type`; a `const`/`var` bound to a non-type value in `TitleCase`; a `fn` name containing `_`
that is not an `export fn`/`extern fn` C-ABI symbol. A 0-field struct declared as `const Foo =
struct {` and never instantiated is the fourth case — it should be `snake_case`.

```zig
// verified
const std = @import("std");

// Types and type-returning functions: TitleCase.
const XmlParser = struct { depth: u32 };
fn RingBuffer(comptime T: type) type {
    return struct { items: []T };
}

// Callables returning a non-type: camelCase.
fn readU32Be(bytes: *const [4]u8) u32 {
    return std.mem.readInt(u32, bytes, .big);
}

// Everything else: snake_case.
const xml_document: []const u8 = "<a/>";
const retry_count_max: u8 = 5;

// Namespace (a 0-field struct that is never instantiated): snake_case.
const wire_format = struct {
    pub const magic: u32 = 0xdeadbeef;
};
```

### ZS-NAME-02 [M] Capitalize acronyms as ordinary English words

`VsrState`, `Utf8View`, `IoUring`, `readU32Be`, `xml_document`. Never `VSRState`, `UTF8View`,
`IOUring`.

The langref, verbatim: "Acronyms, initialisms, proper nouns, or any other word that has
capitalization rules in written English are subject to naming conventions just like any other word.
Even acronyms that are only 2 letters long are subject to these conventions." ALL-CAPS identifiers
in std exist essentially only as C-ABI or on-disk-format mirrors (`os/windows*`, `c/*`, `elf.zig`,
`dwarf/TAG.zig`) — the "established convention such as `ENOENT`" carve-out.

> TigerStyle conflicts head-on: "Use proper capitalization for acronyms (`VSRState`, not
> `VsrState`)." **Recommendation: langref form ([M]).** Use ALL-CAPS only for identifiers that
> mirror a foreign symbol byte-for-byte.

**Why:** an acronym is a word like any other, and casing it as one keeps word boundaries decodable:
`HTTPSProxy` has no readable split; `HttpsProxy` does.

**Check:** grep new identifiers for two or more consecutive capitals — `[A-Z]{2}`. Every hit must
mirror a foreign symbol byte-for-byte (a C `#define`, an ELF/DWARF tag, an on-disk constant);
anything else is a casing violation, including a two-letter one like `IOUring`.

```zig
// fragment — BAD
const VSRState = struct { view: u32 };
const HTTPSProxyURLParser = struct {};
fn parseUTF8(bytes: []const u8) void {}
```

```zig
// fragment — GOOD
const VsrState = struct { view: u32 };
const HttpsProxyUrlParser = struct {};
fn parseUtf8(bytes: []const u8) void {}
// Exception: a name that mirrors a C symbol or an on-disk tag keeps its foreign spelling.
const ENOENT = 2;
```

### ZS-NAME-03 [M] Never prefix with `_`; resolve keyword collisions with `@"..."`

A leading underscore is reserved for foreign symbols (`_DYNAMIC`, `_start`) and explicit structure
padding (`_pad`, `_reserved`). It never means "private". For a keyword, `@"..."` string identifier
syntax is the sanctioned mechanism — std uses `@"enum"` 250 times, `@"struct"` 245 times.

**Why:** langref, verbatim: "In Zig, there are no private fields, and this style guide recommends
against pretending otherwise." A `_` field is as reachable as any other, so the prefix promises what
the language does not provide, and it breaks grep and doc generation.

**Check:** any new identifier that starts with `_` or ends with a bare `_`. A leading `_` must be a
foreign symbol or a padding field named `_pad`/`_reserved`; a trailing `_` is a mutilated
keyword and must become `@"type"`, `@"error"`, `@"align"`.

```zig
// fragment — BAD
const Parser = struct {
    _cursor: usize, // "private" — it isn't.
    type_: Kind,    // keyword dodge by mutilation
};
```

```zig
// fragment — GOOD
const Parser = struct {
    /// Not covered by semantic versioning; treat as an implementation detail.
    cursor: usize,
    @"type": Kind,
};
```

### ZS-NAME-04 [M] Spell names out; abbreviate only as scope tightens

No abbreviations in declaration names, parameters, or fields. Four exceptions, and only four:

1. Primitive integer indices passed to a sort or matrix routine (`i`, `j`, `a`, `b`).
2. Short receiver abbreviations in a type file (ZS-NAME-12): `w: *Writer`, `r: *Reader`,
   `b: *Build`, `m: *Module`.
3. The established std **role names** for singleton dependencies: `gpa`, `arena`, `scratch`
   (`references/memory.md` ZS-MEM-06), and `io`. These are not contractions of longer words — they
   name a role the whole ecosystem already agrees on, so expanding them
   (`general_purpose_allocator`) loses recognition rather than gaining clarity.
4. A name std itself has already fixed. When you bind the result of a std call, mirror std's
   spelling — `var tmp = std.testing.tmpDir(.{})` reads as `tmpDir` does — and when you implement
   a signature std documents, use std's parameter names verbatim, e.g. the panic handler
   `fn (msg: []const u8, first_trace_address: ?usize) noreturn` required by
   `std.debug.FullPanic`. Renaming these to satisfy this rule makes the code harder to match
   against the documentation it implements, which is the opposite of the rule's purpose.

Everything else is spelled out. In particular `src`/`dst` stay banned: they are contractions of
`source`/`target` and carry no role. Long-form flags in scripts: `--force`, not `-f`.

Where a pair can be named at equal length — `source`/`target`, `head`/`tail`, `lhs`/`rhs` — prefer
it. `zig fmt` strips alignment padding inserted by hand, so equal length is the only column
alignment that survives it, and identifiers derived from an aligned pair line up on adjacent lines.

This is TigerStyle N3, and the langref agrees from the other direction — under "Refrain from
Underscore Prefixes" it "recommends more verbose names at outer scopes and more abbreviated names at
inner scopes."

**Why:** an abbreviation is a private dictionary the reader must reconstruct: `rcvbuf_sz` costs
every future reader a guess, `receive_buffer_size_bytes` costs the author six seconds. The
exceptions survive because they are *public* dictionaries a reader has already learned.

**Check:** grep a diff for new identifiers that drop vowels or truncate a word (`cfg`, `msg`, `buf`,
`cnt`, `sz`, `src`, `dst`, `len_`); each must be on the list above or be spelled out.

```zig
// fragment — BAD
fn proc(msg: []const u8, cfg: Cfg, cnt: *u32, buf: []u8) !void {}
fn copy(dst: []u8, src: []const u8) void {}
```

```zig
// fragment — GOOD
fn processMessage(
    message: []const u8,
    config: Config,
    message_count: *u32,
    scratch: []u8,
) !void {}

// Same-length pair, so derived identifiers occupy the same columns and a
// transposition shows up as a visual jag rather than a silent logic bug.
@memcpy(target[target_offset..][0..len], source[source_offset..][0..len]);
```

### ZS-NAME-05 [M] Delete words that apply to every type, and segments the FQN already carries

Ban `Value`, `Data`, `Context`, `Manager`, `State`, `utils`, `misc`, and initials from type names.
Choose names against the **fully qualified** name: inside `json.zig`, the type is `Value`, not
`JsonValue`. The langref: "Every declaration is assigned a fully qualified namespace by the compiler
[…] remember that files also act as part of the fully-qualified namespace."

std is actively refactoring toward this — `std.ArrayHashMapUnmanaged` → `std.array_hash_map.Custom`,
`std.ArrayListAligned` → `std.array_list.Aligned`, and `std.bit_set.IntegerBitSet` →
`std.bit_set.Integer`, `ArrayBitSet` → `Array`, `StaticBitSet` → `Static` are all deprecations
that move the noun into the module name and leave the qualifier in the decl name.
`std.heap.MemoryPoolExtra` → `std.heap.memory_pool.Extra` was the same move; 0.17 removed the old
name.

**Why:** langref, verbatim: "Everything is a value, all types are data, everything is context, all
logic manages state. Nothing is communicated by using a word that applies to all types."

**Check:** grep new type names for `Value`, `Data`, `Context`, `Manager`, `State`, `utils`, and
`misc`. Then read each new declaration name beside its own file name: a repeated segment
(`json.JsonValue`, `wire.WireHeader`, `http.HttpClient`) is the other half of this rule, and the fix
is to delete the segment, not to rename the file.

```zig
// fragment — BAD: file: json.zig
pub const JsonValue = union(enum) { number: f64, boolean: bool };
pub const JsonParserContext = struct {};
pub const utils = struct {
    pub fn jsonEscapeString(s: []const u8) void {}
};
```

```zig
// fragment — GOOD: file: json.zig  → json.Value, json.Parser, json.escapeString
pub const Value = union(enum) { number: f64, boolean: bool };
pub const Parser = struct {};
pub fn escapeString(s: []const u8) void {}
```

### ZS-NAME-06 [M] Put units and qualifiers last, sorted by descending significance

`latency_ms_max`, not `max_latency_ms`. Subject first, then unit, then extremum. Suffix vocabulary:
`_max`, `_min`, `_default`, `_count`, `_size`, `_bytes`, `_ms`, `_ns`, `_percent`, `_limit`.

**Why:** TigerStyle N6. Big-endian names sort into *semantic* groups — `latency_ms_min` beside
`latency_ms_max` in any listing — so a missing member of a family is visible, and a unit in the name
stops `sector_count` and `sector_size_bytes` being swapped the way `n` and `len` can.

**Check:** any new constant, field, or option that *begins* with `max`, `min`, `num`, `default`, or
`total`, and any name where the unit precedes the qualifier (`max_latency_ms`, `total_size_bytes`).
Both the unit and the extremum belong at the end, extremum last.

The word has to be *qualifying* a noun to be a hit. Where it **is** the noun it is already
big-endian and stays: `total_before` / `total_after` name a total taken at two points in time, and
`before` is the qualifier correctly trailing it — that is the shape ZS-PERF-12's GOOD example uses.
`total_size_bytes` is the finding because `total` qualifies `size`; `total_before` is not, because
nothing follows `total` except its own qualifier. Read the name, do not just match the prefix.

```zig
// fragment — BAD
pub const max_latency_ms = 5000;
pub const min_latency_ms = 1;
pub const default_lsm_manifest_memory = 1 << 20;
pub const num_connections = 512;
```

```zig
// verified — GOOD
pub const latency_ms_min: u32 = 1;
pub const latency_ms_max: u32 = 5_000;
pub const connection_count_max: u16 = 512;
```

### ZS-NAME-07 [S] Name the thing so it survives being said out loud

A name must be usable verbatim in a document heading, a commit message, or a sentence to a
colleague. Two consequences: prefer a **noun** to a present participle (`replica.pipeline`, not
`replica.preparing`; `config.pipeline_max`, not `config.max_preparing`), and treat **a name that
needs a clarifying comment at the call site as the wrong name** — rename it until the comment is
redundant, then delete the comment.

The comment test is what makes the rule falsifiable: `// the number of ops we are still waiting on`
attached to `pending` is the compiler of prose telling you the identifier failed, and
`ops_awaiting_count` makes the comment disappear.

**Why:** TigerStyle: "a noun can be directly used in correspondence without having to be rephrased."
A participle has to be reworded every time it leaves the source file, a standing tax on every design
discussion, and nouns compose into derived identifiers without contortion.

**Check:** in a diff, every `//` comment sitting on the same line as, or immediately above, a call
argument or a field access is a rename candidate — ask whether the name could absorb it.

```zig
// fragment — BAD: the comment is doing the naming.
replica.preparing = true; // the pipeline is accepting new requests
try queue.add(item, 3); // 3 = retries remaining
```

```zig
// fragment — GOOD: the names say it; nothing is left for a comment.
replica.pipeline_open = true;
try queue.add(item, .{ .retry_count = 3 });
```

### ZS-NAME-08 [M] Prefix a helper with the name of the function that calls it

`readSector` calls `readSectorFill` and `readSectorVerify`.

**Why:** TigerStyle. The prefix encodes the call graph in the identifier: a reader landing on
`readSectorFill` from a stack trace or a grep knows its one caller, and a `readSector*` grep
enumerates the subsystem. Reusing the helper elsewhere would require renaming it.

**Check:** for each new non-`pub` helper, grep its single caller's name as a prefix. If the helper's
name does not appear in those results, it is misnamed. A helper with two callers that share no name
prefix is the second finding — it is no longer a helper and should be named for what it does.

```zig
// verified
fn readSector(buffer: []u8, index: u32) void {
    readSectorFill(buffer, index);
}

fn readSectorFill(buffer: []u8, index: u32) void {
    @memset(buffer, @truncate(index));
}
```

### ZS-NAME-09 [M] Use an options struct whenever two adjacent parameters share a type

TigerStyle states the hard form: a function taking two `u64` **must** use an options struct. Extend
it to any pair of same-typed parameters a caller could transpose, and to any parameter whose `null`
would be unreadable at the call site. std does this at scale: 158 `pub const …Options = struct`
declarations, 449 parameters typed `…Options`.

**Why:** Zig has no named arguments; an options struct is how you get them. Transposed same-typed
arguments type-check and produce wrong behavior at run time — the compiler cannot help. Field names
at the call site turn that into a compile error.

**Check:** any `fn` signature in the diff with two adjacent parameters of the same type, or any
parameter of type `?T` whose `null` a reader could not name at the call site. Then apply the two
exemptions below: a singleton dependency with a unique type, and a value beside its `_max`/`_min`
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

Singleton dependencies with unique types (an allocator, an `Io`, a tracer) stay **positional** and
are threaded most-general to most-specific, because their types already prevent transposition.

**Exempt: a `_max` / `_min` companion sitting beside the value it bounds.** `(op: u64, op_max: u64)`
is two `u64`s and stays positional — as in ZS-ASSERT-14's
`fn sendPrepareOk(status: Status, view: u32, op: u64, op_max: u64) bool`. The pair is not
transposable in practice: `op_max` is named *after* `op` and reads as its ceiling, so a swapped call
is wrong at a glance in a way that `copyRange(x, y, 4, 0, 2)` is not. This adjacency is exactly what
ZS-NAME-06's big-endian naming exists to create, and burying the pair in an options struct destroys
it. The exemption covers a bounded value and its bound only; it does not extend to two unrelated
`u64`s.

```zig
// fragment — GOOD: a body, with `assert` as the ZS-NAME-16 alias
// `op_max` is `op`'s ceiling, not a second interchangeable argument.
fn opCommitted(op: u64, op_max: u64) bool {
    assert(op_max >= 1);
    return op <= op_max;
}
```

### ZS-NAME-10 [S] Reach for `io.async` first; give the function values that remain std's slot order

Before designing a callback at all, check whether `io.async(function, args)` and `Io.Future` express
the same thing. For the function values that genuinely remain — comparators, visitors, vtable
members — take a written-out function type rather than an `anytype` object with an implied method,
and do not invent a parameter order: copy `std.sort`'s.

The shape to copy comes from `sort.zig` at 0.17.0 — `insertion`, `heap`, `pdq`, `block`, `argMin`,
`argMax`, `min`, `max`, `isSorted`, `binarySearch`, `lowerBound`, `upperBound`, `equalRange`, and
`std.mem.sort` / `sortUnstable` all take:

```text
(comptime T: type,
 items: []T,
 context: anytype,
 comptime lessThanFn: fn (@TypeOf(context), lhs: T, rhs: T) bool)
```

What is uniform across all of them is the **slot order**, not the spelling. std names that parameter
`lessThanFn` in `insertion`/`heap`/`pdq`/`block`/`mem.sort`/`mem.sortUnstable`, `compareFn` in the
search family — exactly four at 0.17.0: `binarySearch`, `lowerBound`, `upperBound`, `equalRange`,
where it returns `std.math.Order` rather than `bool` — and a bare `lessThan` in
`argMin`/`argMax`/`min`/`max`/`isSorted`. (`insertionContext`/`heapContext`/`pdqContext` belong to
none of the three: they take no fn parameter at all, only a `context` whose `lessThan`/`swap`
*methods* carry the behavior.) This rule picks `…Fn` of the three, because the suffix is what
distinguishes a function value from the data beside it. Take the return type from what the predicate
answers: `bool` for "is it less", `Order` for the three-way comparison a search needs.

Type parameters, then **the data**, then `context`, then the `comptime …Fn` last. The `comptime` fn
and its `context` are adjacent because the fn's first parameter type is `@TypeOf(context)`: the
context's type is *derived* from the value, never a separate `comptime Context: type` parameter.
That is what lets a stateless predicate take `{}` at zero storage cost, and a stateful comparator
carry its state in the context without a closure. When the behavior is baked into a *type* instead
of a call, it moves to the type's comptime parameter list —
`PriorityQueue(comptime T: type, comptime Context: type, comptime compareFn: …)` — and the data
arrives later through the methods.

**Why:** a written-out function type puts the contract in the signature, so a mismatched callback
fails at the call site rather than inside your loop. TigerStyle's "callbacks go last" served
hand-threaded continuations, which ZS-CONC-34 retires: an `io.async` `Future` is awaited in place.

**Check:** any new function taking a `comptime …Fn` should be diff-able against a `std.sort`
signature; if the fn is not adjacent to its `context`, or the data is not before both, it is a
private convention. A `comptime Context: type` parameter beside a `context` value is the tell that
the signature was written from memory.

```zig
// verified
const std = @import("std");

const Account = struct { id: u64, balance_cents: i64 };

fn overdrawn(_: void, account: Account) bool {
    return account.balance_cents < 0;
}

fn balanceLessThan(_: void, lhs: Account, rhs: Account) bool {
    return lhs.balance_cents < rhs.balance_cents;
}

/// Same slot order as `std.mem.sortUnstable`: type parameters, then the data,
/// then `context`, then the `comptime ...Fn`. std has no counting predicate, so
/// this one is written; finding the poorest account is `std.sort.min`'s job.
fn countWhere(
    comptime T: type,
    items: []const T,
    context: anytype,
    comptime predicateFn: fn (@TypeOf(context), item: T) bool,
) usize {
    var count: usize = 0;
    for (items) |item| {
        if (predicateFn(context, item)) count += 1;
    }
    return count;
}

test countWhere {
    const accounts = [_]Account{
        .{ .id = 1, .balance_cents = -5 },
        .{ .id = 2, .balance_cents = 40 },
        .{ .id = 3, .balance_cents = -1 },
    };
    try std.testing.expectEqual(2, countWhere(Account, &accounts, {}, overdrawn));
    // Where std has the function, the call takes the same slot order.
    const poorest = std.sort.min(Account, &accounts, {}, balanceLessThan);
    try std.testing.expectEqual(accounts[0], poorest);
}
```

### ZS-NAME-11 [S] Use std's suffix vocabulary for method variants

`…AssumeCapacity` (non-allocating twin, asserts capacity), `…Alloc` (allocating twin), `…Context`
(explicit context parameter), `…Adapted` (different key type), `…Sentinel` (sentinel-terminated),
`…Leaky` (arena-oriented, nothing is freed individually), `toOwned…` / `fromOwned…` for ownership
transfer.

In particular, **do not use `take*` to mean ownership transfer**: of the 23 `take*` functions in std
the large majority are stream consumers (`Io.Reader.take`, `takeByte`, `takeDelimiter`, `takeEnum`,
`takeSentinel`, plus the `elf` header readers), so `take` reads as "consume the next thing" to
anyone who has used `Io.Reader`. Use `toOwned…` / `fromOwned…` / `move…` instead.

**Why:** these suffixes are load-bearing in std (52 `AssumeCapacity`, 40 `Adapted`, 36 `Alloc`, 26
`Sentinel`, 3 `Leaky`), so a reader already knows the contract from the suffix alone.

**Check:** any new method name that is a base name plus a suffix not on the list above — and in
particular any `take*` that transfers ownership rather than consuming from a stream. A
non-allocating twin not spelled `…AssumeCapacity`, or an allocating twin not spelled `…Alloc`,
is the same finding.

---

## Receivers

### ZS-NAME-12 [M] Name the receiver after its type; keep `self` for anonymous generic containers

In a file that *is* a type, write `const Journal = @This();` and name receivers `journal: *Journal`
(or a consistent 1–2 letter abbreviation like `w: *Writer`). Use `const Self = @This();` and
`self:` only inside a `fn Foo(comptime T: type) type` body, where the type has no name.

A naive grep hides how std does this. `rg "\(self: *"` over std returns ~2100 hits, but counting
only *true* receivers — a first parameter whose type is the file's own `TitleCase` name or a
`@This()` alias declared in that file — the 3061 receivers in 0.17 std split `self` **44.2%** vs
named after the type **55.8%**. The split is by file kind, not taste: only **6 of 143**
`TitleCase.zig` files still declare `const Self = @This();`, while every generic container does.
Per-file receiver histograms, counted as `rg -c 'fn \w+\(<recv>: <Type>' <file>`: `Io/Writer.zig` →
`w: *Writer` ×69, `Io/Reader.zig` → `r: *Reader` ×70, `Build.zig` → `b: *Build` ×70,
`Build/Module.zig` → `m: *Module` ×24, `Target.zig` → `target: *const Target` ×28. TigerBeetle bans
`Self` outright and enforces it with a lint.

**Why:** std and TigerStyle agree on this. A named receiver also survives copy-paste into a
different type — `self` silently reads correctly in the wrong file.

**Check:** `rg -n 'self:'` in any `TitleCase.zig` file, and `rg -n 'const Self = @This\(\);'`
anywhere outside the body of a `fn Name(comptime …) type`. Both are the finding; the second is the
one that produces the first.

```zig
// fragment — BAD: file: Journal.zig, a named type
const Self = @This();
pub fn append(self: *Self, sector: []const u8) WriteError!void {}
```

```zig
// fragment — GOOD: file: Journal.zig
const Journal = @This();
pub fn append(journal: *Journal, sector: []const u8) WriteError!void {}
```

```zig
// verified — GOOD: a generic container has no concrete name, so `Self` is correct here.
const std = @import("std");
pub fn Stack(comptime T: type) type {
    return struct {
        const Self = @This();

        items: std.ArrayList(T),

        pub const empty: Self = .{ .items = .empty };

        pub fn push(self: *Self, gpa: std.mem.Allocator, item: T) std.mem.Allocator.Error!void {
            try self.items.append(gpa, item);
        }

        pub fn deinit(self: *Self, gpa: std.mem.Allocator) void {
            self.items.deinit(gpa);
            self.* = undefined;
        }
    };
}
```

## Files and modules

### ZS-NAME-13 [M] Name a file `TitleCase.zig` if and only if it has top-level fields

A file with top-level fields *is* a struct type: `Journal.zig`, `Io.zig`, `Build.zig`. A file with
no top-level fields is a namespace: `array_list.zig`, `wire_format.zig`. Directory names follow
ZS-NAME-14.

The langref, verbatim: "File names fall into two categories: types and namespaces. If the file
(implicitly a struct) has top level fields, it should be named like any other struct with fields
using `TitleCase`. Otherwise, it should use `snake_case`." Measured over 563 std files, the rule
holds with **zero counterexamples in the snake_case direction**: 0 of 420 `snake_case.zig` files
have top-level fields. Nine of 143 `TitleCase.zig` files have no fields, and all nine are the
"established convention" carve-out (`dwarf/TAG.zig`, `heap/PageAllocator.zig`, …).

**Why:** `@import("x/Foo.zig")` versus `@import("x/foo.zig")` tells you at the import site whether
you got a type or a namespace, which is exactly the information the langref example encodes:

```zig
// fragment
const namespace_name = @import("dir_name/file_name.zig");
const TypeName = @import("dir_name/TypeName.zig");
```

> **This is the sharpest conflict in the whole standard.** TigerStyle N2 rejects the convention
> outright: "We don't use Zig's `CamelCase.zig` style for 'struct' files to keep the convention
> simple and consistent." TigerBeetle's reason is real — one casing rule for functions, variables,
> **and** files means there is nothing to remember and nothing to get wrong, and their tidy lint can
> enforce it with a single regex. Modern std went the other way and hard: `Io.zig`, `Build.zig`,
> `Target.zig`, `Progress.zig`, `Uri.zig`, `Thread.zig`, `Random.zig`, `SemanticVersion.zig`,
> `BitStack.zig`, `DoublyLinkedList.zig`, `SinglyLinkedList.zig` are all top-level `TitleCase.zig`
> type files, and 143 exist tree-wide.
>
> **Recommendation: follow the langref ([M]).** Anyone reading your code has read std; the casing of
> a filename is free type information, and importing `Foo.zig` to get a type is now the dominant
> idiom. TigerStyle's uniform `snake_case` is a coherent alternative only for a closed codebase that
> enforces it mechanically and never exports a file path in its public API.

**Check:** for every file added or renamed in the diff, does it declare top-level fields? A
`snake_case.zig` with fields, or a `TitleCase.zig` without them, is the violation. The grep is
"first non-comment, non-`const`, non-`fn` line at column 0 that looks like `name: Type,`".

```
// BAD                          // GOOD
src/journal.zig  (has fields)   src/Journal.zig
src/WireFormat.zig (no fields)  src/wire_format.zig
```

### ZS-NAME-14 [S] Name a directory after its companion file

`Io/` sits beside `Io.zig`; `Build/`, `Build/Step/`, `Target/`, `Io/File/` likewise. The langref
says "Directory names should be `snake_case`", but std does not do that: only 5 directories in the
entire std tree lack a companion `<dir>.zig` sibling. Use `snake_case` directories only where there
is no companion file.

**Why:** the divergence from the langref is deliberate: a directory is the sub-namespace of the file
it accompanies, so it takes that file's exact name, casing included, and `std.Io.File` maps
mechanically to `Io/File.zig`.

**Check:** for each new directory, `ls` its parent for `<dir>.zig`. If that sibling exists, the
directory name must match it character for character, casing included; if it does not exist, the
directory must be `snake_case`.

### ZS-NAME-15 [M] Keep the `@This()` alias and the whole import block in one place

Top form: `//!` doc, then `const Foo = @This();`, then imports, then fields. Bottom form: everything
else first, imports and the `@This()` alias as the final block. Pick one per file. Both are house
style: the median std file has its first `@import` on line 2, but 19 files of 40 lines or more —
`zig/Parse.zig`, `heap/ArenaAllocator.zig` and `http/HeadParser.zig` among them — put the whole
block in their last half so that line 1 is the type's documentation rather than boilerplate.

**Why:** a split import block is not house style: `zig fmt` never reorders or moves imports, so a
scattered block stays scattered forever, and a reader cannot answer "what does this file depend on?"
without reading all of it.

**Check:** `rg -n '@import\(' <file>` — the line numbers must form one contiguous run (allowing the
alias lines derived from them). A second run further down the file is a split block, and the
`const Foo = @This();` line must sit at the same end as that run.

```zig
//! An append-only journal of fixed-size sectors held in one allocation.
// verified

const Journal = @This();

const builtin = @import("builtin");
const is_debug = builtin.optimize == .debug;

const std = @import("std");
const assert = std.debug.assert;
const Allocator = std.mem.Allocator;
```

### ZS-NAME-16 [S] Order imports `@This()` → `builtin` → `std` → local, and alias the hot names

Group in that order, each group separated by a blank line, derived aliases immediately under the
import they derive from. Do not alphabetize across groups.

The standard alias block, by frequency in std: `const assert = std.debug.assert;` (172 files),
`const mem = std.mem;` (137), `const testing = std.testing;` (129), `const math = std.math;` (119),
`const Allocator = std.mem.Allocator;` (94), `const Io = std.Io;` (75). Why `assert` is always
aliased is `references/assertions.md` ZS-ASSERT-01.

Application code always writes `@import("std")`. `@import("../std.zig")` is internal to std itself.

**Why:** the ordering is the std habit and it goes from most-fixed to most-local, so the interesting
lines (your own modules) are last and closest to the code. `zig fmt` will never reorder imports, so
a convention is the only thing keeping them consistent.

**Check:** `@import("builtin")` appearing below `@import("std")`, a local `@import` above either, an
alias separated from the import it derives from, or `@import("../std.zig")` outside std.

### ZS-NAME-17 [M] Order a struct body: fields → types → `init`/`deinit` → methods → tests

Fields carry no `pub`. Nested `pub const Foo = struct {…}` types and `pub const empty: Self = …`
decl literals come after the fields and before the methods. TigerStyle places the `const Self =
@This();` line at the *end* of the types section; std places the named `@This()` alias at the very
top of the file (ZS-NAME-15). Prefer the std placement for a `TitleCase.zig` file and the TigerStyle
placement for a nested struct.

TigerStyle: "the order is fields then types then methods". std does the same (`Io/File.zig`,
`Io/Dir.zig`, `Build/Step.zig`, `Io/Writer.zig`, `heap/ArenaAllocator.zig` all match). If a nested
type grows complex, promote it to its own top-level file.

**Why:** the layout is memory-shaped: the fields are the data and everything below is derived from
them, so a reader reconstructing the invariants reads top-down and never has to scroll back.

**Check:** read the struct body top to bottom and note the first `fn`. A field declaration or a
nested `pub const … = struct` below it is out of order, as is a `test` block above the last method,
or `init`/`deinit` appearing after another method.

```zig
//! An append-only journal of fixed-size sectors held in one allocation.
// verified

const Journal = @This();

const std = @import("std");
const assert = std.debug.assert;
const Allocator = std.mem.Allocator;

/// Backing storage for every sector. Owned by this `Journal`.
sectors: []u8,
/// Number of sectors written so far. Never exceeds `sector_count_max`.
sector_count: u32,

pub const sector_size_bytes: u32 = 512;
pub const sector_count_max: u32 = 1024;

pub const Options = struct {
    sector_count: u32 = sector_count_max,
};

pub const AppendError = error{Full};

comptime {
    assert(sector_count_max > 0);
    assert(sector_size_bytes % 8 == 0);
}

/// Deinitialize with `deinit`.
pub fn init(gpa: Allocator, options: Options) Allocator.Error!Journal {
    assert(options.sector_count <= sector_count_max);
    const bytes = try gpa.alloc(u8, options.sector_count * sector_size_bytes);
    return .{ .sectors = bytes, .sector_count = 0 };
}

pub fn deinit(journal: *Journal, gpa: Allocator) void {
    gpa.free(journal.sectors);
    journal.* = undefined;
}

/// Asserts that `sector.len` is exactly `sector_size_bytes`.
/// Invalidates slices previously returned by `sectorAt`.
pub fn append(journal: *Journal, sector: []const u8) AppendError!void {
    assert(sector.len == sector_size_bytes);
    const offset = journal.sector_count * sector_size_bytes;
    if (offset == journal.sectors.len) return error.Full;
    @memcpy(journal.sectors[offset..][0..sector_size_bytes], sector);
    journal.sector_count += 1;
}

/// Asserts that `index` is in bounds.
pub fn sectorAt(journal: *const Journal, index: u32) []const u8 {
    assert(index < journal.sector_count);
    return journal.sectors[index * sector_size_bytes ..][0..sector_size_bytes];
}

test append {
    const gpa = std.testing.allocator;
    var journal: Journal = try .init(gpa, .{ .sector_count = 1 });
    defer journal.deinit(gpa);

    const sector: [sector_size_bytes]u8 = @splat('a');
    try journal.append(&sector);
    try std.testing.expectError(error.Full, journal.append(&sector));
    try std.testing.expectEqualSlices(u8, &sector, journal.sectorAt(0));
}
```

### ZS-NAME-18 [S] Put the entry point and the most important declarations first

`main` goes first in a file that has one. Public API before private helpers. Where no ordering is
obviously right, sort alphabetically and let ZS-NAME-06's big-endian naming do the grouping.

**Why:** TigerStyle: "On the first read, a file is read top-down, so put important things near the
top." Order has no semantic effect in Zig — declaration order is irrelevant to the compiler — which
means it is pure signal, and wasting it costs nothing to fix.

**Check:** in a file declaring `main`, is `main` the first declaration after the import block? In
any other file, does a non-`pub` helper appear above the `pub` declaration that calls it? Those are
the two mechanical readings; the rest of this rule is a tie-break, not a check.

### ZS-NAME-19 [M] Default to non-`pub`; mark `pub` only what a caller outside the file needs

A declaration starts private and becomes `pub` when a caller in another file needs it. Which of the
`pub` names form the package's surface is decided once, in `root.zig` (`references/build.md`
ZS-BUILD-16).

**Why:** `pub` is the module's API contract and everything `pub` is something you cannot rename
later without a breaking change; the compiler will not tell you which `pub`s are unused.

**Check:** for every `pub` added in the diff, grep the name across the tree outside its own file. No
external hit means it should not be `pub`.

---

## Comments

### ZS-NAME-20 [M] `//!` at the file top, `///` on declarations, `//` for everything else

`//!` is module documentation and must be the first thing in the file. `///` attaches to the next
declaration, field, or parameter. `//` is an implementation note that deliberately stays out of the
generated docs.

**Why:** two of the three are enforced by the compiler, and the errors are worth knowing. All three
at 0.17.0:

```zig
// rejected — zig: expected statement, found 'a document comment'
pub fn main() void {
    /// This is a doc comment on a statement.
    // error: expected statement, found 'a document comment'
    const x: u32 = 1;
    _ = x;
}
```

```zig
// rejected — zig: expected type expression, found 'a document comment'
const std = @import("std");
//! Module doc comment not at the top.
// error: expected type expression, found 'a document comment'
```

```zig
// rejected — zig: unattached documentation comment
const std = @import("std");
/// Dangling doc comment.
// error: unattached documentation comment
```

The `///` vs `//` distinction is a deliberate editorial choice, not an accident — std places both on
adjacent lines to separate "why the design" from "what the contract is":

```zig
// fragment
// Having a countdown to grow reduces the number of instructions to
// execute when determining if the hashmap has enough capacity already.
/// Number of available slots before a grow is needed to satisfy the
/// `max_load_percentage`.
available: Size = 0,
```

std also documents **individual parameters in place**, inside the signature — a distinctive std
habit, still there in 0.17, worth copying:

```zig
// fragment
pub fn allocWithOptions(
    self: Allocator,
    comptime Elem: type,
    n: usize,
    /// null means naturally aligned
    comptime optional_alignment: ?Alignment,
    comptime optional_sentinel: ?Elem,
) ...
```

**Check:** the three misplacements above are compile errors, so `zig build` owns them. What a
reviewer greps for is a `pub` declaration with no `///` at all, and a `///` that states an
implementation reason ("we do it this way because…") rather than a contract — that one belongs on
`//`, immediately above the `///`.

### ZS-NAME-21 [M] Use std's contract phrasings verbatim

Reuse the house sentences rather than inventing synonyms:

Counts are occurrences of the **bolded stem** of each phrase over `lib/zig/std/**/*.zig` at 0.17.0,
case-sensitive — reproduce any row with `rg -I -o '<stem>' -g '*.zig' . | wc -l`. They count
the phrase family, not the full sentence in the left column.

| Phrase | Meaning | std count |
|---|---|---|
| **`Asserts that`** … | violating it trips a safety-checked assertion | 135 |
| **`Assumes`** … | violating it is unchecked Illegal Behavior | 55 |
| **`Invalidates`** element pointers if additional memory is needed. | reallocation may move them | 94 |
| **`Deinitialize with`** \`deinit\`. | ownership: call this | 10 |
| **`Caller owns`** returned memory. | ownership transfers out | 19 |
| **`Thread-safe.`** / **`Not threadsafe`**. | concurrency contract | 18 / 9 |
| **`It is illegal to`** … | hard precondition | 4 |
| **`Deprecated in favor of`** \`x\`. | one line, immediately above the alias | 36, of 237 `/// Deprecated` |
| **`See also:`** + `* \`decl\`` bullets | cross-reference block | 136 |

The full invalidation sentence, `Invalidates element pointers if additional memory is needed.`,
appears 33 times across std, 24 of them in `array_list.zig`. Cross-reference by backticked
identifier always: only backticks become links in generated docs, and 5473 `///` lines in std carry
a backticked identifier (lines matching `^\s*///` that contain `` `name` ``, 0.17.0).

Omit doc comments that restate the name (langref rule 1). `handle: Handle` is undocumented in
`Io/File.zig` for a reason.

**Why:** these are pattern-matched, not read: a reader who has seen the invalidation sentence across
std recognizes the pointer-invalidation hazard at a glance, while a paraphrase forces them to parse
the sentence and decide whether it means the same thing.

**Check:** a doc comment that paraphrases a row of the table — "the caller must free this" instead
of `Caller owns returned memory.`, "pointers may move" instead of the invalidation sentence, "this
is thread-safe" instead of `Thread-safe.` And: any declaration named in a doc comment without
backticks, which is a cross-reference that will not become a link.

### ZS-NAME-22 [M] Say why, not what — including at the top of every test

Comments explain the reasoning that is not in the code: why this constant, why not the obvious
design, what invariant is being preserved, what upstream bug is being worked around and when the
workaround can be deleted. Open each test with a sentence stating its goal and method.

TigerBeetle's highest-frequency comment categories, in order, are: why this number; why this design
and not the obvious one; invariants; correctness proofs for derived constants; links to the paper or
issue the idea came from; upstream-bug annotations with a removal condition.

**Why:** TigerStyle: "Code alone is not documentation." Restating the code duplicates a fact that
will drift, while a rationale cannot be recovered from the source at all, so it is the only thing a
comment adds that the code cannot.

**Check:** a comment whose words are the identifiers on the line below it — `// Increment the sector
count.` above `sector_count += 1` — is the canonical violation; delete it or replace it with the
reason. Second: a magic number introduced with no comment naming its derivation. Third: a `test`
block whose first line is code rather than a sentence stating goal and method.

```zig
// fragment — BAD
// Increment the sector count.
journal.sector_count += 1;
```

```zig
// fragment — GOOD
// Bump before the fsync so a torn write is detected as a short journal on
// replay rather than as a valid sector with garbage contents.
journal.sector_count += 1;

// TODO(zig): remove once https://github.com/ziglang/zig/issues/NNNNN lands;
// the alignment downcast works around a 0.16.0 codegen bug.
```

### ZS-NAME-23 [S] Comment typography: space after the slashes, capital letter, full stop

Comments are sentences: `// Like this.` A colon replaces the full stop when the comment introduces
what follows: `// Two cases:`. End-of-line comments may be unpunctuated phrases:
`+ two index blocks`.

**Why:** TigerStyle N19. Sentence-shaped comments force the author to state a complete thought;
fragments let half-formed ones through. The cost is zero and the consistency is visible at a
distance.

**Check:** `rg -n '//[^ /!\n]'` catches the missing space. Then scan standalone comment lines for a
lower-case first word or a missing `.`/`:` terminator. End-of-line comments are exempt, so restrict
the scan to comments that start their own line.

---

## Formatting

### ZS-NAME-24 [M] Run `zig fmt`; the trailing comma is your only formatting lever

`zig fmt` owns indentation (4 spaces), brace placement, spacing, and blank-line collapsing. The one
decision you make is the **trailing comma**: adding one to a parameter list, struct literal, or enum
forces one item per line; removing it collapses the list to a single line if it fits. `zig fmt`
rewrites hard tabs to 4 spaces, collapses runs of blank lines to one, and splits `_ = a; _ = b;`
onto separate lines. The langref: "If a list of things is longer than 2, put each item on its own
line and exercise the ability to put an extra comma at the end."

**Why:** `zig fmt` *collapses* a multi-line signature that lacks a trailing comma back onto one
line, so a hand-wrapped signature without a trailing comma will be silently un-wrapped.

```zig
// fragment — (`zig fmt` input)
const x = S{ .a = 1, .b = 2, };
fn f(a: u32, b: u32,) u32 { return a + b; }
```

```zig
// fragment — (`zig fmt` output)
const x = S{
    .a = 1,
    .b = 2,
};
fn f(
    a: u32,
    b: u32,
) u32 {
    return a + b;
}
```

`zig fmt` will **not** order your imports, group your blank lines, order your declarations, or wrap
a long expression — those are ZS-NAME-16 through ZS-NAME-18 and your own judgement. `// zig fmt:
off` … `// zig fmt: on` exists but appears only 32 times in all of std, exclusively for hand-aligned
tables. Source is UTF-8 with LF endings and a trailing newline.

**Check:** the CI gate of `references/build.md` ZS-BUILD-29 —
`zig fmt --check --ast-check --exclude zig-pkg --exclude .zig-cache .` — is the whole rule for
indentation and spacing. The reviewable residue is a multi-line parameter list, struct literal, or
enum with **no** trailing comma — `zig fmt` will silently collapse it back onto one line — and any
new `// zig fmt: off` that is not guarding a hand-aligned table.

### ZS-NAME-25 [M] Hard-limit every line to 100 columns

Including comments, doc comments, and string literals. Set a column ruler. Wrap by adding a trailing
comma and re-running `zig fmt`. Enforce it in CI: it is a one-line check and the only formatting
rule `zig fmt` cannot do for you. TigerStyle F3 is absolute — "Use it up. Never go beyond." The
langref is softer ("Line length: aim for 100; use common sense.") but the number agrees, and std
measured over 416 956 non-empty lines is 92.6% ≤80 columns and 97.4% ≤100.

**Why:** TigerStyle motivates the number physically: 100 columns is just enough to fit two copies of
the code side by side, which is what code review and diffing actually do. Nothing should ever be
hidden behind a horizontal scrollbar.

**Check:** `awk 'length > 100 { print FILENAME ":" FNR }' $(git ls-files "*.zig")` — any output is a
violation, including inside a comment or a string literal. `zig fmt --check` will not report this,
so it needs its own CI line.

## Names beyond the source file

### ZS-NAME-26 [M] One term, one meaning, project-wide

A word that already has a technical meaning in your project may not be reused for a second,
context-dependent meaning. Before introducing a term, grep the codebase and the design documents for
it; if it is taken, coin a different word rather than qualifying the old one.

TigerStyle's own worked example: TigerBeetle shipped a feature where a transfer could be held and
later resolved, and first called it a *two-phase commit transfer* — but *two-phase commit* was
already the name of a mechanism in their consensus protocol, so every conversation had to establish
which layer was under discussion before it could proceed. They renamed the feature to
**pending transfers**, which are subsequently **posted** or **voided**.

**Why:** the cost of an overloaded term is not paid once at naming time; it is paid on every future
reading, and it compounds because the derived identifiers inherit the ambiguity (`two_phase_timeout`
— whose?). Distinct words also make grep exact.

**Check:** for each new domain noun in a diff, `rg -i '<term>'` over `src/` and `docs/`. Hits in
an unrelated subsystem mean the term is taken. Qualifying it (`transfer_two_phase_commit`) does not
fix it — the reader still has to disambiguate.

```zig
// fragment — BAD: `two_phase` already names the consensus mechanism.
pub const TwoPhaseCommitTransfer = struct { timeout_ms: u32 };
pub fn commitTwoPhase(transfer: *TwoPhaseCommitTransfer) void {}
```

```zig
// fragment — GOOD: a distinct vocabulary: pending → posted | voided.
pub const PendingTransfer = struct { timeout_ms: u32 };
pub fn postPending(transfer: *PendingTransfer) void {}
pub fn voidPending(transfer: *PendingTransfer) void {}
```

### ZS-NAME-27 [M] Write the commit message; a pull-request description is not one

Every commit gets a descriptive message: a subject line naming what changed, and a body giving the
reasoning ZS-NAME-22 keeps out of the code. Do not put the explanation only in a pull-request
description.

`git blame` on a suspicious line is the single highest-yield debugging move in an unfamiliar
codebase, and it reaches the commit message and nothing else — not the PR, not the review thread,
not the chat log, all of which live on a third-party server that may not outlive the repository. The
message is also the only rationale that survives `git filter-repo`, a mirror, or a vendored copy of
your package in someone else's `zig-pkg/`.

**Why:** TigerStyle's reason is mechanical, not etiquette: a pull-request description lives outside
the git repository and is, in its words, "invisible in `git blame`" — so it cannot replace a commit
message.

**Check:** if reviewing the diff required a fact that is not in the commit message, the message is
incomplete — the next reader will be doing it from `git blame` with strictly less context.

```text
BAD                                   GOOD
fix                                   journal: bump sector_count before fsync

(explanation lives in the PR)         A torn write must be detected as a short journal on
                                      replay, not as a valid sector holding garbage. Bumping
                                      after the fsync leaves a window where the count and the
                                      durable bytes disagree.

                                      Found by the crash-injection simulation at seed
                                      0x8f3a21c4; regression test in Journal.zig.
```

## Symmetry across a codebase

### ZS-NAME-28 [M] Name the two halves of a pair symmetrically

A pair uses matched words: `encode`/`decode`, not `encode`/`parse`; `open`/`close`, not
`open`/`release`; `acquire`/`release`, not `acquire`/`free`. Where std has already fixed the pair,
copy it.

**Why:** matched names are what make a pair recognizable as a pair, which is how a reader knows the
inverse exists without searching for it (ZS-DATA-36). Mismatched halves read as unrelated
operations, so the reader hunts for a `decode` that was spelled `parse`.

**Check:** list every operation with an inverse and read the two names aloud together. If they do
not sound like a pair, rename the odd half.

### ZS-NAME-29 [M] One concept, one mechanism

A project configures itself one way, reports progress one way, allocates one way, and spawns
work one way. Two mechanisms for one concept means every future change must choose between them and
every reader must learn both.

**Why:** mechanisms multiply combinations. Two configuration paths and two logging paths is four
states a maintainer has to hold at once, and the second mechanism is nearly always introduced
because the first was inconvenient in one place — a local fix with a global cost.

**Check:** name the single mechanism for each cross-cutting concern: configuration, errors, logging,
allocation, I/O, concurrency. More than one per concern needs a migration plan, not an exception.

### ZS-NAME-30 [S] Keep sibling modules structurally parallel

Modules at the same level of the tree have the same internal shape: if `parser.zig` has an `Error`
set, a `Config`, and a test block at the bottom, then `renderer.zig` does too, or the difference is
explained in a comment. ZS-NAME-17 fixes the order inside one file; this rule fixes it across files.

**Why:** parallel structure lets a reader who has learned one module navigate the next without
reading it, which compounds across a codebase. The convention costs almost nothing to keep and is
paid for on every visit by every contributor.

**Check:** list the declaration kinds in each sibling module side by side. A row present in three of
four siblings is either missing from the fourth or unnecessary in the others.

## Decided by tools

The compiler rejects each of these on its own; no setting turns one off.

| Tool | Lint | Level | Forbids |
|---|---|---|---|
| zig | `unused local constant` | error | a local constant nothing reads |
| zig | `unused local variable` | error | a local variable nothing reads |
| zig | `unused function parameter` | error | a parameter the body never reads; name it `_` |
| zig | `unused capture` | error | a payload capture the body never reads; capture `\|_\|` |
| zig | `pointless discard of …` | error | `_ = x;` for a name the code goes on to use |
| zig | `local variable is never mutated` | error | a `var` nothing writes after its initializer; make it `const` |
| zig | `… shadows declaration of …` | error | a local or parameter named like a declaration in scope |
| zig | `… shadows … from outer scope` | error | a local named like a local of an enclosing scope |
| zig | `name shadows primitive …` | error | a name such as `u8`, `type` or `true` |
| zig | `unused … label` | error | a block or loop label nothing breaks to or continues |
| zig | `unattached documentation comment` | error | a `///` comment with no declaration after it |
