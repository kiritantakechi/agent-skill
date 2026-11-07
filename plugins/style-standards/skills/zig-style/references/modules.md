# Modules: Boundaries, Layout, Imports, Order, and Orthogonality

Scope: how a Zig project is divided into modules and files, what each boundary costs, how the tree
is laid out on disk, how imports are written and the graph they form, the order of declarations in a
file and in a struct, and the one-mechanism-per-concept discipline across them. What a file is
called is the naming chapter; which declarations are `pub`, and what `src/root.zig` exports
(ZS-API-02), are the API chapter; what a `//!` comment may say is the documentation chapter.

Unless a block shows its own imports, it assumes the preamble ZS-MOD-09 prescribes:
`const std = @import("std");` and `const assert = std.debug.assert;`.

## Contents

- **Dividing code into modules**
  - ZS-MOD-01 [M] Open every file with a `//!` comment that says what it holds
  - ZS-MOD-02 [S] Split a file on a seam, not on a line count
  - ZS-MOD-03 [M] Count the encapsulation a module boundary costs, not only what it buys
  - ZS-MOD-04 [S] Keep a file name to few words
- **Layout**
  - ZS-MOD-05 [S] Keep `tests/`, `tools/`, `examples/`, and `scripts/` outside `src/`
  - ZS-MOD-06 [S] Name a directory after its companion file, or after the module it roots
- **Imports and the graph**
  - ZS-MOD-07 [M] Keep the module graph directed, because the compiler will not
  - ZS-MOD-08 [M] Keep the `@This()` alias and the whole import block in one place
  - ZS-MOD-09 [S] Order imports `@This()` → `builtin` → `std` → local, and alias the hot names
- **Order within a file**
  - ZS-MOD-10 [S] Put the entry point and the most important declarations first
  - ZS-MOD-11 [S] Order a struct body: fields → types → `init`/`deinit` → methods → tests
- **Orthogonality**
  - ZS-MOD-12 [M] One concept, one mechanism
  - ZS-MOD-13 [S] Keep sibling modules structurally parallel
  - ZS-MOD-14 [M] Absorb a special case into the general path, or give it its own type

---

## Dividing code into modules

### ZS-MOD-01 [M] Open every file with a `//!` comment that says what it holds

One sentence, at the top, naming the one thing the file is: what the type is for, or what the
members of a namespace file have in common. It states a role, not the list of declarations below it.

**Why:** a file is a claim about cohesion, and a claim you cannot write in one sentence is a
boundary in the wrong place. The sentence also tells the next contributor where new code goes, and
the generated docs show nothing else of the file's purpose.

**Check:** for each file, write the sentence. A file with no `//!` comment has none, and one whose
sentence needs "and" is two files.

```zig
// verified — GOOD
//! A fixed-capacity stack of `u32` values. Nothing here allocates or performs I/O.

const std = @import("std");

pub const Stack = struct {
    items: [8]u32 = undefined,
    len: usize = 0,

    pub fn push(stack: *Stack, value: u32) error{Full}!void {
        if (stack.len == stack.items.len) return error.Full;
        stack.items[stack.len] = value;
        stack.len += 1;
    }
};

test "push stops at capacity" {
    var stack: Stack = .{};
    for (0..8) |i| try stack.push(@intCast(i));
    try std.testing.expectError(error.Full, stack.push(8));
}
```

### ZS-MOD-02 [S] Split a file on a seam, not on a line count

Split when the declarations fall into two groups with different callers or different reasons to
change, and each half can be named with a noun. A nested type that has grown complex is promoted to
its own file (ZS-MOD-11).

**Why:** splitting on size alone produces `parser2.zig` and `config_more.zig`, which is worse than
the long file: the reader now holds two files and the relation between them. Zig sets no limit of
its own, so the only reason to split is the reader.

**Check:** when splitting, can both halves be named with a noun, and does each have callers the
other does not? If not, do not split yet.

### ZS-MOD-03 [M] Count the encapsulation a module boundary costs, not only what it buys

A module is worth its boundary where you want a different compilation setting (target, optimize,
`link_libc`, `single_threaded`) or a separately publishable API; organizing folders is what files
are for. Each module costs one more test binary (ZS-BUILD-04), and everything across the boundary
must become `pub`: a seam that exports a handful of declarations is a seam, and one that exports
dozens is the wrong seam, however much an `@import` boundary is wanted there.

**Why:** inside one module a file can keep its helpers unexported; promoting it to a module converts
those internals into public surface — for a separately published module, surface that outside code
may depend on and that you then owe compatibility for.

**Check:** list the declarations the split forces to `pub`. Would each be exported on its own
merits?

### ZS-MOD-04 [S] Keep a file name to few words

`wire_format.zig`, not `wire_format_helpers_and_codecs.zig`; `Journal.zig`, not
`JournalSectorStorage.zig`. Two words is the usual ceiling.

**Why:** the file name is the last half of every `@import` that reaches it, and one that needs many
words usually names a file doing several things: the name is reporting a design problem (ZS-MOD-02).

**Check:** say each new file name aloud. A third word is a candidate split: can both halves be named
with a noun?

## Layout

### ZS-MOD-05 [S] Keep `tests/`, `tools/`, `examples/`, and `scripts/` outside `src/`

`src/` is the shipped package. Everything else lives beside it and is excluded from `.paths`.

**Why:** consumers never download your benchmark corpus (ZS-BUILD-11), and integration tests that
`@import("myproj")` by module name exercise the *published* API — the only way to notice that you
forgot to re-export something.

**Check:** `ls src/` shows no `tests`, `tools`, `examples`, `scripts`, or benchmark directory, and
`.paths` names none of them; every file under `tests/` imports the package by module name rather
than with a `../src/` relative path.

```
myproj/
  build.zig
  build.zig.zon
  .gitignore          # .zig-cache/  zig-out/  zig-pkg/
  LICENSE  README.md
  src/
    root.zig          # public module root; re-exports the API
    main.zig          # CLI root module; @import("myproj")
    constants.zig     # every _max limit
    parser.zig …      # internal, reachable only through root.zig
  tests/
    integration.zig   # own test binary; imports "myproj" by name
  tools/
    codegen.zig       # host-only build tool
  scripts/
    release.zig       # automation, in Zig
  examples/
    basic.zig         # built by `zig build examples`, not installed
```

### ZS-MOD-06 [S] Name a directory after its companion file, or after the module it roots

`Io/` sits beside `Io.zig`; `Build/`, `Build/Step/`, `Target/`, `Io/File/` likewise. The langref
says "Directory names should be `snake_case`", but std does not do that: almost every std directory
has a companion `<dir>.zig` sibling. Use `snake_case` directories only where there is no companion
file. A directory that holds a module's sources takes the name `b.addModule` gives the module, so
the module, its directory and the `@import` string agree.

**Why:** a directory is the sub-namespace of the file or module it accompanies, so `std.Io.File`
maps mechanically to `Io/File.zig`, one grep finds every mention of a module, and a rename is one
operation; when the names differ, every reader carries the mapping.

**Check:** for each new directory, `ls` its parent for `<dir>.zig`. If that sibling exists, the
directory name must match it character for character, casing included; if it does not exist, the
directory must be `snake_case`. And the source tree reads as the module list in `build.zig`.

## Imports and the graph

### ZS-MOD-07 [M] Keep the module graph directed, because the compiler will not

`@import` cycles compile. Two modules that import each other are one module wearing two names, and
merging them is the fix.

**Why:** two files that import each other are accepted — Zig resolves the cycle and the test binary
passes — so nothing in the build tells you the boundary is fictional, and the layering has to be
maintained deliberately.

**Check:** draw the `@import` graph across module roots. Any pair pointing both ways is a merge, not
a boundary.

### ZS-MOD-08 [M] Keep the `@This()` alias and the whole import block in one place

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

### ZS-MOD-09 [S] Order imports `@This()` → `builtin` → `std` → local, and alias the hot names

Group in that order, each group separated by a blank line, derived aliases immediately under the
import they derive from. Do not alphabetize across groups.

The standard alias block, by frequency in std: `const assert = std.debug.assert;` (172 files),
`const mem = std.mem;` (137), `const testing = std.testing;` (129), `const math = std.math;` (119),
`const Allocator = std.mem.Allocator;` (94), `const Io = std.Io;` (75). Why `assert` is always
aliased is ZS-ASSERT-01.

Application code always writes `@import("std")`. `@import("../std.zig")` is internal to std itself.

**Why:** the ordering is the std habit and it goes from most-fixed to most-local, so the interesting
lines (your own modules) are last and closest to the code. `zig fmt` will never reorder imports, so
a convention is the only thing keeping them consistent.

**Check:** `@import("builtin")` appearing below `@import("std")`, a local `@import` above either, an
alias separated from the import it derives from, or `@import("../std.zig")` outside std.

## Order within a file

### ZS-MOD-10 [S] Put the entry point and the most important declarations first

`main` goes first in a file that has one. Public API before private helpers. Where no ordering is
obviously right, sort alphabetically and let ZS-NAME-07's big-endian naming do the grouping.

**Why:** TigerStyle: "On the first read, a file is read top-down, so put important things near the
top." Order has no semantic effect in Zig — declaration order is irrelevant to the compiler — which
means it is pure signal, and wasting it costs nothing to fix.

**Check:** in a file declaring `main`, is `main` the first declaration after the import block? In
any other file, does a non-`pub` helper appear above the `pub` declaration that calls it? Those are
the two mechanical readings; the rest of this rule is a tie-break, not a check.

### ZS-MOD-11 [S] Order a struct body: fields → types → `init`/`deinit` → methods → tests

Fields carry no `pub`. Nested `pub const Foo = struct {…}` types and `pub const empty: Self = …`
decl literals come after the fields and before the methods. TigerStyle places the
`const Self = @This();` line at the *end* of the types section; std places the named `@This()` alias
at the very top of the file (ZS-MOD-08). Prefer the std placement for a `TitleCase.zig` file and the
TigerStyle placement for a nested struct.

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

## Orthogonality

### ZS-MOD-12 [M] One concept, one mechanism

A project configures itself one way, reports progress one way, allocates one way, and spawns work
one way. Two mechanisms for one concept means every future change must choose between them and every
reader must learn both.

**Why:** mechanisms multiply combinations. Two configuration paths and two logging paths is four
states a maintainer has to hold at once, and the second mechanism is nearly always introduced
because the first was inconvenient in one place — a local fix with a global cost.

**Check:** name the single mechanism for each cross-cutting concern: configuration, errors, logging,
allocation, I/O, concurrency. More than one per concern needs a migration plan, not an exception.

### ZS-MOD-13 [S] Keep sibling modules structurally parallel

Modules at the same level of the tree have the same internal shape: if `parser.zig` has an `Error`
set, a `Config`, and a test block at the bottom, then `renderer.zig` does too, or the difference is
explained in a comment. ZS-MOD-11 fixes the order inside one file; this rule fixes it across files.

**Why:** parallel structure lets a reader who has learned one module navigate the next without
reading it, which compounds across a codebase. The convention costs almost nothing to keep and is
paid for on every visit by every contributor.

**Check:** list the declaration kinds in each sibling module side by side. A row present in three of
four siblings is either missing from the fourth or unnecessary in the others.

### ZS-MOD-14 [M] Absorb a special case into the general path, or give it its own type

A branch that exists for one input is not a feature; it is an unfinished generalization. Either the
general path handles it — usually by widening a parameter or adding a tag — or the case differs
enough to deserve its own type and its own function.

**Why:** special-case branches compound. Each is locally cheap and globally expensive: every later
change must be checked against every branch, nothing records which combinations are reachable, and
ZS-ERR-18's simple control flow erodes one plausible patch at a time.

**Check:** for each `if` whose condition names a specific input — a particular length, an empty
slice treated unlike others, a sentinel value — ask what the general case would need to be for the
branch to disappear. That is usually the correct design.
