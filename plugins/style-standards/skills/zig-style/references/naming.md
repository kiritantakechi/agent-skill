# Naming, Files, Formatting

Scope: how identifiers are cased and worded, how a `.zig` file is cased, and the formatting
mechanics (`zig fmt`, the trailing comma, 100 columns). How a project is divided into files, how
they are laid out and ordered, and how long a file name runs are the modules chapter. Semantics of
the things being named live elsewhere: error-set design in the errors chapter,
`init`/`deinit`/ownership contracts in the memory chapter, `format` and `std.Io` in the concurrency
chapter, `test` mechanics and fuzzing in the testing chapter, `build.zig` naming in the build
chapter, and what a comment says (the three comment forms, std's contract phrasings) in the
documentation chapter.

Two sources are merged here: the **official Zig style guide** (langref 0.17.0 §Style Guide, quoted
verbatim where it is normative) and **TigerStyle** (TigerBeetle's house standard). Where they
disagree, the disagreement is stated outright in the rule, with the side this standard takes.

Unless a block shows its own imports, it assumes the preamble the modules chapter prescribes in
ZS-MOD-09: `const std = @import("std");` and `const assert = std.debug.assert;`. Where a snippet's
file name matters to the rule, it is named in the comment above it.

## Contents

- **Casing and word choice**
  - ZS-NAME-01 [M] Apply the official casing rules exactly
  - ZS-NAME-02 [M] Capitalize acronyms as ordinary English words
  - ZS-NAME-03 [M] Never prefix with `_`; resolve keyword collisions with `@"..."`
  - ZS-NAME-04 [M] Spell names out; abbreviate only as scope tightens
  - ZS-NAME-05 [M] Delete the segments the fully qualified name already carries
  - ZS-NAME-06 [M] Never let a word that applies to every type be the whole name
  - ZS-NAME-07 [M] Put units and qualifiers last, sorted by descending significance
  - ZS-NAME-08 [S] Name the thing so it survives being said out loud
  - ZS-NAME-09 [M] Name a predicate so it reads as a question
  - ZS-NAME-10 [M] Prefix a helper with the name of the function that calls it
  - ZS-NAME-11 [S] Reach for `io.async` first; give the function values that remain std's slot order
  - ZS-NAME-12 [S] Use std's suffix vocabulary for method variants
- **Receivers**
  - ZS-NAME-13 [M] Name the receiver after its type; keep `self` for anonymous generic containers
- **Files and `pub`**
  - ZS-NAME-14 [M] Name a file `TitleCase.zig` if and only if it has top-level fields
- **Formatting**
  - ZS-NAME-15 [M] Let the trailing comma decide when a list explodes; `zig fmt` does the rest
  - ZS-NAME-16 [M] Hard-limit every line to 100 columns
- **Names beyond the source file**
  - ZS-NAME-17 [M] One term, one meaning, project-wide
  - ZS-NAME-18 [M] Write the commit message; a pull-request description is not one
- **Symmetry across a codebase**
  - ZS-NAME-19 [M] Name the two halves of a pair symmetrically
- Decided by tools

---

## Casing and word choice

### ZS-NAME-01 [M] Apply the official casing rules exactly

`TitleCase` for types, type aliases, and callables whose return type is `type`. `camelCase` for
every other callable. `snake_case` for everything else, including 0-field structs used as
namespaces. The langref is explicit: "If `x` is a struct with 0 fields and is never meant to be
instantiated then `x` is considered to be a 'namespace' and should be `snake_case`."

TigerStyle conflicts here: N2 mandates `snake_case` for **function** names too (`read_sector`, not
`readSector`). TigerBeetle is internally consistent about it, but any call into std in the same
expression is `camelCase`, so a mixed-case expression is unavoidable: functions are `camelCase`.
Uniform `snake_case` functions are defensible only in a closed codebase with zero public API
surface, and only if enforced mechanically.

**Why:** these are the rules the compiler's own diagnostics, `std`, and every published package
follow, so casing carries information: seeing `foo.Bar` you know `Bar` is a type without looking it
up, and seeing `foo.bar()` you know `bar` returns a value. Mixed conventions destroy that signal.

**Check:** three shapes in a diff. A `fn` whose name starts with a capital and whose return type is
not `type`; a `const`/`var` bound to a non-type value in `TitleCase`; a `fn` name containing `_`
that is not an `export fn`/`extern fn` C-ABI symbol. A 0-field struct declared as
`const Foo = struct {` and never instantiated is the fourth case — it should be `snake_case`.

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

TigerStyle conflicts head-on: "Use proper capitalization for acronyms (`VSRState`, not `VsrState`)."
This standard takes the langref's form, and ALL-CAPS only for an identifier that mirrors a foreign
symbol byte-for-byte.

**Why:** an acronym is a word like any other, and casing it as one keeps word boundaries decodable:
`HTTPSProxy` has no readable split; `HttpsProxy` does.

**Check:** a new identifier with two or more consecutive capitals. Every one must mirror a foreign
symbol byte-for-byte (a C `#define`, an ELF/DWARF tag, an on-disk constant); anything else is a
casing violation, including a two-letter one like `IOUring`.

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
foreign symbol or a padding field named `_pad`/`_reserved`; a trailing `_` is a mutilated keyword
and must become `@"type"`, `@"error"`, `@"align"`.

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
2. Short receiver abbreviations in a type file (ZS-NAME-13): `w: *Writer`, `r: *Reader`,
   `b: *Build`, `m: *Module`.
3. The established std **role names** for singleton dependencies: `gpa`, `arena`, `scratch`
   (ZS-MEM-06), and `io`. These are not contractions of longer words — they name a role the whole
   ecosystem already agrees on, so expanding them (`general_purpose_allocator`) loses recognition
   rather than gaining clarity.
4. A name std itself has already fixed. When you bind the result of a std call, mirror std's
   spelling — `var tmp = std.testing.tmpDir(.{})` reads as `tmpDir` does — and when you implement a
   signature std documents, use std's parameter names verbatim, e.g. the panic handler
   `fn (msg: []const u8, first_trace_address: ?usize) noreturn` required by `std.debug.FullPanic`.
   Renaming these to satisfy this rule makes the code harder to match against the documentation it
   implements, which is the opposite of the rule's purpose.

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

**Check:** a new identifier in a diff that drops vowels or truncates a word (`cfg`, `msg`, `buf`,
`cnt`, `sz`, `src`, `dst`, `len_`) is on the list above, or is spelled out.

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

### ZS-NAME-05 [M] Delete the segments the fully qualified name already carries

Choose names against the **fully qualified** name: inside `json.zig`, the type is `Value`, not
`JsonValue`. The langref: "Every declaration is assigned a fully qualified namespace by the compiler
[…] remember that files also act as part of the fully-qualified namespace."

std is actively refactoring toward this — `std.ArrayHashMapUnmanaged` → `std.array_hash_map.Custom`,
`std.ArrayListAligned` → `std.array_list.Aligned`, and `std.bit_set.IntegerBitSet` →
`std.bit_set.Integer`, `ArrayBitSet` → `Array`, `StaticBitSet` → `Static` are all deprecations that
move the noun into the module name and leave the qualifier in the decl name.
`std.heap.MemoryPoolExtra` → `std.heap.memory_pool.Extra` was the same move; 0.17 removed the old
name.

**Why:** a declaration is always written behind its path, so a segment the name repeats is said
twice at every use: `json.JsonValue`, `http.HttpClient`.

**Check:** read each new declaration name beside its own file name: a repeated segment
(`json.JsonValue`, `wire.WireHeader`, `http.HttpClient`) is the finding, and the fix is to delete
the segment, not to rename the file.

```zig
// fragment — BAD: file: json.zig
pub const JsonValue = union(enum) { number: f64, boolean: bool };
pub fn jsonEscapeString(s: []const u8) void {}
```

```zig
// fragment — GOOD: file: json.zig  → json.Value, json.escapeString
pub const Value = union(enum) { number: f64, boolean: bool };
pub fn escapeString(s: []const u8) void {}
```

### ZS-NAME-06 [M] Never let a word that applies to every type be the whole name

Ban `Value`, `Data`, `Context`, `Manager`, `State`, `utils`, `misc`, and initials as the whole name
of a type or namespace. Beside a qualifier, or in a file whose name supplies one (`json.Value`), the
word is fine; alone it names a container, and a container can hold anything.

**Why:** langref, verbatim: "Everything is a value, all types are data, everything is context, all
logic manages state. Nothing is communicated by using a word that applies to all types."

**Check:** a new type or namespace name that is only `Value`, `Data`, `Context`, `Manager`, `State`,
`utils` or `misc` and sits in a file whose name does not say what it is a value, context or manager
of. Each is the finding.

```zig
// fragment — BAD
pub const utils = struct {
    pub fn escapeString(s: []const u8) void {}
};
pub const Context = struct {};
```

```zig
// verified — GOOD
pub const Journal = struct {
    entries: u32,
};

pub const escaping = struct {
    pub fn escapeString(s: []const u8) usize {
        return s.len;
    }
};
```

### ZS-NAME-07 [M] Put units and qualifiers last, sorted by descending significance

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

### ZS-NAME-08 [S] Name the thing so it survives being said out loud

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

### ZS-NAME-09 [M] Name a predicate so it reads as a question

`isEmpty`, `hasChildren`, `startsWith`, `eql`. A function returning `bool` whose name is a noun is a
function whose call site reads as an assignment.

**Why:** `if (flush(buffer))` gives the reader no way to know whether it flushed and reported
success or merely asked a question, and the two are opposite. std names its predicates this way
(`std.mem.startsWith`, `std.ascii.isAlphabetic`), so a reader already expects it.

**Check:** every function declared `bool`. A name that is not a question is the finding.

```zig
// verified — GOOD
const Buffer = struct {
    len: usize,

    fn isEmpty(buffer: Buffer) bool {
        return buffer.len == 0;
    }

    fn hasRoom(buffer: Buffer, capacity: usize) bool {
        return buffer.len < capacity;
    }
};
```

### ZS-NAME-10 [M] Prefix a helper with the name of the function that calls it

`readSector` calls `readSectorFill` and `readSectorVerify`.

**Why:** TigerStyle. The prefix encodes the call graph in the identifier: a reader landing on
`readSectorFill` from a stack trace or a search knows its one caller, and a search for `readSector`
enumerates the subsystem. Reusing the helper elsewhere would require renaming it.

**Check:** each new non-`pub` helper's name begins with its single caller's name, or it is misnamed.
A helper with two callers that share no name prefix is the second finding — it is no longer a helper
and should be named for what it does.

```zig
// verified
fn readSector(buffer: []u8, index: u32) void {
    readSectorFill(buffer, index);
}

fn readSectorFill(buffer: []u8, index: u32) void {
    @memset(buffer, @truncate(index));
}
```

### ZS-NAME-11 [S] Reach for `io.async` first; give the function values that remain std's slot order

Before designing a callback at all, check whether `io.async(function, args)` and `Io.Future` express
the same thing. For the function values that genuinely remain — comparators, visitors, vtable
members — take a written-out function type rather than an `anytype` object with an implied method,
and do not invent a parameter order: copy `std.sort`'s.

The shape to copy comes from `sort.zig` at 0.17.0 — `insertion`, `heap`, `pdq`, `block`, `argMin`,
`argMax`, `min`, `max`, `isSorted`, `binarySearch`, `lowerBound`, `upperBound`, `equalRange`, and
`std.mem.sort` / `sortUnstable` all take the first example's parameter list.

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
hand-threaded continuations, which ZS-CONC-36 retires: an `io.async` `Future` is awaited in place.

**Check:** any new function taking a `comptime …Fn` should be diff-able against a `std.sort`
signature; if the fn is not adjacent to its `context`, or the data is not before both, it is a
private convention. A `comptime Context: type` parameter beside a `context` value is the tell that
the signature was written from memory.

```text
(comptime T: type,
 items: []T,
 context: anytype,
 comptime lessThanFn: fn (@TypeOf(context), lhs: T, rhs: T) bool)
```

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

### ZS-NAME-12 [S] Use std's suffix vocabulary for method variants

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
non-allocating twin not spelled `…AssumeCapacity`, or an allocating twin not spelled `…Alloc`, is
the same finding.

## Receivers

### ZS-NAME-13 [M] Name the receiver after its type; keep `self` for anonymous generic containers

In a file that *is* a type, write `const Journal = @This();` and name receivers `journal: *Journal`
(or a consistent 1–2 letter abbreviation like `w: *Writer`). Use `const Self = @This();` and `self:`
only inside a `fn Foo(comptime T: type) type` body, where the type has no name.

In std the split is by file kind, not taste: a `TitleCase.zig` file names its receiver after its
type — `w: *Writer` in `Io/Writer.zig`, `r: *Reader` in `Io/Reader.zig`, `b: *Build` in `Build.zig`,
`m: *Module` in `Build/Module.zig`, `target: *const Target` in `Target.zig` — and a generic
container, which has no name, declares `const Self = @This();`. TigerBeetle bans `Self` outright and
enforces it with a lint.

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
// verified — a generic container has no concrete name, so `Self` is correct here.
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

## Files and `pub`

### ZS-NAME-14 [M] Name a file `TitleCase.zig` if and only if it has top-level fields

A file with top-level fields *is* a struct type: `Journal.zig`, `Io.zig`, `Build.zig`. A file with
no top-level fields is a namespace: `array_list.zig`, `wire_format.zig`. Directory names follow
ZS-MOD-06.

The langref, verbatim: "File names fall into two categories: types and namespaces. If the file
(implicitly a struct) has top level fields, it should be named like any other struct with fields
using `TitleCase`. Otherwise, it should use `snake_case`." std holds to it with no counterexample in
the `snake_case` direction: no `snake_case.zig` file has top-level fields, and the `TitleCase.zig`
files with none are the "established convention" carve-out (`dwarf/TAG.zig`,
`heap/PageAllocator.zig`, …).

This is the sharpest conflict in the whole standard. TigerStyle N2 rejects the convention outright:
"We don't use Zig's `CamelCase.zig` style for 'struct' files to keep the convention simple and
consistent." TigerBeetle's reason is real — one casing rule for functions, variables, **and** files
means there is nothing to remember and nothing to get wrong, and their tidy lint can enforce it with
a single regex. Modern std went the other way and hard: `Io.zig`, `Build.zig`, `Target.zig`,
`Progress.zig`, `Uri.zig`, `Thread.zig`, `Random.zig`, `SemanticVersion.zig`, `BitStack.zig`,
`DoublyLinkedList.zig` and `SinglyLinkedList.zig` are all top-level `TitleCase.zig` type files. This
standard follows the langref: anyone reading your code has read std, the casing of a filename is
free type information, and importing `Foo.zig` to get a type is the dominant idiom. TigerStyle's
uniform `snake_case` is a coherent alternative only for a closed codebase that enforces it
mechanically and never exports a file path in its public API.

**Why:** `@import("x/Foo.zig")` versus `@import("x/foo.zig")` tells you at the import site whether
you got a type or a namespace, which is exactly the information the langref example encodes.

**Check:** for every file added or renamed in the diff, does it declare top-level fields? A
`snake_case.zig` with fields, or a `TitleCase.zig` without them, is the violation. A top-level field
is a line at column 0 that reads `name: Type,`, and is not a comment, a `const` or a `fn`.

```zig
// fragment
const namespace_name = @import("dir_name/file_name.zig");
const TypeName = @import("dir_name/TypeName.zig");
```

```
// BAD                          // GOOD
src/journal.zig  (has fields)   src/Journal.zig
src/WireFormat.zig (no fields)  src/wire_format.zig
```

## Formatting

### ZS-NAME-15 [M] Let the trailing comma decide when a list explodes; `zig fmt` does the rest

`zig fmt` owns indentation (4 spaces), brace placement, spacing, and blank-line collapsing. The one
decision you make is the **trailing comma**: adding one to a parameter list, struct literal, or enum
forces one item per line; removing it collapses the list to a single line if it fits. `zig fmt`
rewrites hard tabs to 4 spaces, collapses runs of blank lines to one, and splits `_ = a; _ = b;`
onto separate lines. The langref: "If a list of things is longer than 2, put each item on its own
line and exercise the ability to put an extra comma at the end."

`zig fmt` will **not** order your imports, group your blank lines, order your declarations, or wrap
a long expression — those are ZS-MOD-09 through ZS-MOD-10 and your own judgement. `// zig fmt: off`
… `// zig fmt: on` exists, and std uses it only for hand-aligned tables. Source is UTF-8 with LF
endings and a trailing newline.

**Why:** `zig fmt` *collapses* a multi-line signature that lacks a trailing comma back onto one
line, so a hand-wrapped signature without a trailing comma will be silently un-wrapped.

**Check:** the CI gate of ZS-BUILD-22 —
`zig fmt --check --ast-check --exclude zig-pkg --exclude .zig-cache .` — is the whole rule for
indentation and spacing. The reviewable residue is a multi-line parameter list, struct literal, or
enum with **no** trailing comma — `zig fmt` will silently collapse it back onto one line — and any
new `// zig fmt: off` that is not guarding a hand-aligned table.

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

### ZS-NAME-16 [M] Hard-limit every line to 100 columns

Including comments, doc comments, and string literals. Set a column ruler. Wrap by adding a trailing
comma and re-running `zig fmt`. Enforce it in CI: it is a one-line check and the only formatting
rule `zig fmt` cannot do for you. TigerStyle F3 is absolute — "Use it up. Never go beyond." The
langref is softer ("Line length: aim for 100; use common sense.") but the number agrees, and nearly
every line of std fits in 100 columns.

**Why:** TigerStyle motivates the number physically: 100 columns is just enough to fit two copies of
the code side by side, which is what code review and diffing actually do. Nothing should ever be
hidden behind a horizontal scrollbar.

**Check:** `awk 'length > 100 { print FILENAME ":" FNR }' $(git ls-files "*.zig")` — any output is a
violation, including inside a comment or a string literal. `zig fmt --check` will not report this,
so it needs its own CI line.

## Names beyond the source file

### ZS-NAME-17 [M] One term, one meaning, project-wide

A word that already has a technical meaning in your project may not be reused for a second,
context-dependent meaning. Before introducing a term, grep the codebase and the design documents for
it; if it is taken, coin a different word rather than qualifying the old one.

TigerStyle's own worked example: TigerBeetle shipped a feature where a transfer could be held and
later resolved, and first called it a *two-phase commit transfer* — but *two-phase commit* was
already the name of a mechanism in their consensus protocol, so every conversation had to establish
which layer was under discussion before it could proceed. They renamed the feature to **pending
transfers**, which are subsequently **posted** or **voided**.

**Why:** the cost of an overloaded term is not paid once at naming time; it is paid on every future
reading, and it compounds because the derived identifiers inherit the ambiguity (`two_phase_timeout`
— whose?). Distinct words also make grep exact.

**Check:** for each new domain noun in a diff, `rg -i '<term>'` over `src/` and `docs/`. Hits in an
unrelated subsystem mean the term is taken. Qualifying it (`transfer_two_phase_commit`) does not fix
it — the reader still has to disambiguate.

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

### ZS-NAME-18 [M] Write the commit message; a pull-request description is not one

Every commit gets a descriptive message: a subject line naming what changed, and a body giving the
reasoning ZS-DOC-07 keeps out of the code. Do not put the explanation only in a pull-request
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

### ZS-NAME-19 [M] Name the two halves of a pair symmetrically

A pair uses matched words: `encode`/`decode`, not `encode`/`parse`; `open`/`close`, not
`open`/`release`; `acquire`/`release`, not `acquire`/`free`. Where std has already fixed the pair,
copy it.

**Why:** matched names are what make a pair recognizable as a pair, which is how a reader knows the
inverse exists without searching for it (ZS-API-07). Mismatched halves read as unrelated operations,
so the reader hunts for a `decode` that was spelled `parse`.

**Check:** list every operation with an inverse and read the two names aloud together. If they do
not sound like a pair, rename the odd half.

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
