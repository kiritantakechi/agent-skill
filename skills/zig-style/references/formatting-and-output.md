# Formatting values and program output

Scope: turning values into bytes (`{f}` and the custom `format` method, the complete 0.17 specifier
set, width/fill/alignment/precision, the `std.fmt` API, `parseInt`/`parseFloat`), and where those
bytes are allowed to go (buffered `*Io.Writer` for program output, `std.log` for diagnostics,
`std.process.fatal` for a fatal CLI condition, a custom `logFn` for structured logs).

This chapter does not own stream mechanics: obtaining `Io`, `Io.Writer` internals, buffering,
flushing, and authoring a custom writer are `references/io-and-concurrency.md` (ZS-IO-05, ZS-IO-06,
ZS-IO-08, ZS-IO-11). Error classification and the log-versus-return decision are
`references/errors-and-control-flow.md` (ZS-ERR-03, ZS-ERR-17, ZS-ERR-32, ZS-ERR-33).
**Source-code** formatting — `zig fmt`, the trailing comma as your only wrapping lever, 100
columns — is a different subject and lives in `references/naming-and-files.md` ZS-NAME-29 and
ZS-NAME-30. This chapter cites them rather than repeating them.

Every example assumes a file opening with `const std = @import("std");`, `const Io = std.Io;`,
`const Writer = std.Io.Writer;` and `const assert = std.debug.assert;` — assertions are called bare,
per ZS-ASRT-01. In the `{t}` examples, `Level` is `std.log.Level` and `Node` is a small tagged union
declared beside the test.
## Contents

- **1. `{}` versus `{f}`**
  - ZS-FMT-01 [M] Use `{f}` for any type that defines `format`; `{}` silently ignores it
  - ZS-FMT-02 [M] Write the `format` signature exactly: value, writer, `Writer.Error!void`
  - ZS-FMT-03 [S] Express a second rendering with `std.fmt.alt`, not a second `format` method
- **2. The specifier set**
  - ZS-FMT-04 [M] Choose the specifier deliberately; this is the complete 0.17 set
  - ZS-FMT-05 [M] Print an enum, union tag, or error name with `{t}`
  - ZS-FMT-06 [M] Give `{?}` and `{!}` an inner specifier for the payload
  - ZS-FMT-07 [S] Treat `{any}` as a debugging dump — never as an output format
  - ZS-FMT-08 [S] `{*}` prints an address; keep addresses out of anything compared or persisted
- **3. Width, fill, alignment, precision**
  - ZS-FMT-09 [M] Width is counted in bytes, so it does not align non-ASCII text
  - ZS-FMT-10 [M] Width and precision are for numbers and strings; on an enum they panic
- **4. The `std.fmt` API**
  - ZS-FMT-11 [M] Use the 0.17 names: `Options`, `Alt`/`alt`, `std.mem.printSentinel`
  - ZS-FMT-12 [M!] Use `std.mem.print`, not `gpa.print`, when a constant bounds the size
  - ZS-FMT-13 [S] Use `comptimePrint` for compile-time strings and `count` for exact sizing
  - ZS-FMT-14 [M] Parse with `parseInt`/`parseFloat` and handle both failure modes by name
  - ZS-FMT-15 [M!] Round-trip every format you persist or transmit, in a test
- **5. Where the bytes go**
  - ZS-FMT-16 [M] Program output goes to a buffered, flushed `*Io.Writer` — never `std.debug.print`
  - ZS-FMT-17 [M] A library renders into the caller's writer or returns bytes; it never prints
  - ZS-FMT-18 [M] Pick the failure channel by who needs to read it
- **6. Logging**
  - ZS-FMT-19 [S] A custom `std.options.logFn` is the only route to timestamps or a sink
- **7. Dead formatting API**
  - ZS-FMT-20 [M] Reject the old formatting API on sight

---

## 1. `{}` versus `{f}`

### ZS-FMT-01 [M] Use `{f}` for any type that defines `format`; `{}` silently ignores it
Since 0.16 the `{f}` specifier — with `{qf}`, its quoting twin added in 0.17 — is the *only* thing
that calls a type's `format` method. A bare `{}` falls through to the compiler's default value
dump. Both compile.

**Why:** this is the single most dangerous change in 0.16 because the failure mode is **wrong
output, not a compile error**. A log line, a serialized record, or a golden-file test that used to
read `(1, 2)` now reads `.{ .x = 1, .y = 2 }`, and nothing in the build tells you.

**Check:** every bare `{}` placeholder in the diff, against the type of the argument it consumes: if
that type declares `pub fn format`, the `{}` is a defect. Grepping the diff for `pub fn format` and
then for the type's name at call sites finds them from the other direction.

```zig
// verified — GOOD
const std = @import("std");
const Writer = std.Io.Writer;
const Point = struct {
    x: u32,
    y: u32,

    pub fn format(p: Point, w: *Writer) Writer.Error!void {
        try w.print("({d}, {d})", .{ p.x, p.y });
    }
};

test "{} ignores format, {f} calls it" {
    // `{}` silently prints the compiler's default struct dump.
    try std.testing.expectFmt(".{ .x = 1, .y = 2 }", "{}", .{Point{ .x = 1, .y = 2 }});
    // `{f}` is the only spelling that reaches `Point.format`.
    try std.testing.expectFmt("(1, 2)", "{f}", .{Point{ .x = 1, .y = 2 }});
}
```

The reverse direction *is* checked: `{f}` on a type with no `format` method is
`error: no field or member function named 'format' in 'Plain'`. So the asymmetry is entirely
one-sided — over-specifying is safe, under-specifying is silent.

### ZS-FMT-02 [M] Write the `format` signature exactly: value, writer, `Writer.Error!void`
`pub fn format(value: T, w: *std.Io.Writer) std.Io.Writer.Error!void`. There is no format-string
parameter and no options parameter any more, and the writer is the concrete `*Io.Writer`, not
`anytype`.

**Why:** `std.Io.Writer.printValue` dispatches `{f}` as literally `value.format(w)`. A
0.14-era four-parameter `format` therefore fails with
`error: member function expected 3 argument(s), found 1` — a clear error, but only if you reach it.
Dropping the format string is what makes the method non-generic: it can no longer branch on the
caller's specifier, which is why a second rendering needs `std.fmt.alt` (ZS-FMT-03) instead.

**Check:** any `pub fn format(` with more than two parameters, with a `comptime fmt` or `options`
parameter, with `w: anytype` rather than `w: *Writer`, or with an inferred `!void` return in place
of `Writer.Error!void`.

```zig
// verified — GOOD
/// A version number rendered as `major.minor.patch`.
const std = @import("std");
const Writer = std.Io.Writer;
const Version = struct {
    major: u16,
    minor: u16,
    patch: u16,

    /// 0.16 signature: value first, `*Io.Writer` second, no format string and
    /// no options. Fail only with what the writer failed with.
    pub fn format(v: Version, w: *Writer) Writer.Error!void {
        try w.print("{d}.{d}.{d}", .{ v.major, v.minor, v.patch });
    }
};

test "custom format method" {
    const v: Version = .{ .major = 0, .minor = 16, .patch = 0 };
    try std.testing.expectFmt("zig 0.16.0", "zig {f}", .{v});
}
```

```zig
// does-not-compile — the 0.14 shape; {f} passes exactly one argument
pub fn format(o: Old, comptime f: []const u8, opts: anytype, w: anytype) !void {
    _ = .{ f, opts };
    try w.print("{d}", .{o.x});
}
```

Keep the error set at `Writer.Error` (`error{WriteFailed}`) and nothing wider. A `format` method
that can fail for its own reasons has no way to report them — the specifier has no error channel —
so validate at construction instead.

Two sibling hooks exist for numeric types: `{d}`/`{x}`/`{X}`/`{b}`/`{o}`/`{e}` on a struct dispatch
to `formatNumber(value, w, std.fmt.Number)`, and `{B}`/`{Bi}` dispatch to
`formatByteSize(value, w, mode)`. Implement `formatNumber` only when your type genuinely *is* a
number and should honour base, width, and precision.

### ZS-FMT-03 [S] Express a second rendering with `std.fmt.alt`, not a second `format` method
`std.fmt.alt(value, .method_name)` wraps a value so that `{f}` dispatches to `method_name` instead
of `format`. It replaced `std.fmt.Formatter`.

**Why:** `format` takes no specifier, so one type gets one default rendering and there is nowhere to
hang a "short" or "verbose" variant. `alt` puts the choice at the call site where it is visible,
rather than encoding it in a wrapper struct the reader has to go look up. Deviate when a rendering
is elaborate enough to deserve a named function the caller invokes directly.

**Check:** a wrapper struct whose only member is a `format` method over one borrowed field — that is
a hand-rolled `Alt`. Also a `format` method that reads a mode/verbosity field of its own value to
pick between renderings.

```zig
// verified — GOOD
const std = @import("std");
const Writer = std.Io.Writer;
const Sha = struct {
    bytes: [4]u8,

    pub fn format(s: Sha, w: *Writer) Writer.Error!void {
        try w.print("{x}", .{&s.bytes});
    }

    /// Alternate rendering, reached with `std.fmt.alt(sha, .short)`.
    pub fn short(s: Sha, w: *Writer) Writer.Error!void {
        try w.print("{x}", .{s.bytes[0..2]});
    }
};

test "alt selects a second rendering" {
    const s: Sha = .{ .bytes = .{ 0xde, 0xad, 0xbe, 0xef } };
    try std.testing.expectFmt("deadbeef", "{f}", .{s});
    try std.testing.expectFmt("dead", "{f}", .{std.fmt.alt(s, .short)});
}
```

---

## 2. The specifier set

### ZS-FMT-04 [M] Choose the specifier deliberately; this is the complete 0.17 set
The placeholder grammar is `{[argument][specifier]:[fill][alignment][width].[precision]}`.

**Why:** the set changed in 0.15/0.16 — `{f}` and `{t}` are new, `{D}` is gone, and several
specifiers that used to be optional are now mandatory (a slice, an optional, or an error union with
a bare `{}` is a compile error) — and 0.17 adds `{q}` and `{qf}`. Guessing produces either a
compile error you will fix by guessing again, or the wrong output.

| Spec | Correct for | Renders |
|---|---|---|
| `{s}` | `[]const u8`, `[N]u8`, `[*:0]const u8` | the bytes as text — the only way to print a string |
| `{d}` | ints, floats, enums, `formatNumber` structs | base 10; on an enum this is the **tag's integer**, not its name |
| `{x}` / `{X}` | ints, floats, byte slices/arrays | lower/upper hex; on a slice, a hex dump of the bytes |
| `{b}` / `{o}` | ints, enums, `formatNumber` structs | base 2 / base 8 |
| `{c}` | an integer of **at most 8 bits** | one ASCII byte. `{c}` on a `u32` is a compile error |
| `{u}` | an integer of at most 21 bits | the codepoint encoded as UTF-8 |
| `{e}` / `{E}` | **floats only** | scientific notation. `{e}` on an integer is a compile error |
| `{t}` | enums, tagged unions, error sets | the bare name — see ZS-FMT-05 |
| `{?}` / `{!}` | optionals / error unions | payload or `null` / payload or the error — see ZS-FMT-06 |
| `{*}` | pointers | `Child@hexaddress` — see ZS-FMT-08 |
| `{f}` | any type declaring `format` | that method's output — see ZS-FMT-01 |
| `{q}` | `[]const u8`, `[N]u8`, `[*:0]const u8` | the bytes in double quotes; `\n`, `\r`, `\t`, `\\` and `"` escaped, control bytes and invalid UTF-8 hex-encoded |
| `{qf}` | any type declaring `format` | that method's output, double-quote escaped the same way |
| `{any}` | anything | the compiler's default dump, depth-limited — see ZS-FMT-07 |
| `{b64}` | byte slices/arrays | standard base64 |
| `{B}` / `{Bi}` | integers, `formatByteSize` structs | SI (`1.5kB`) / IEC (`1.5KiB`) byte sizes |
| `{}` | ints, floats, bools, enums, error sets, structs, unions | the default rendering for that type |

**`{D}` no longer exists.** 0.16 removed it from `printValue`, and 0.17 also dropped it from the doc
comment on `Io.Writer.print`: `{D}` on a `u64` is `error: invalid format string 'D' for type
'u64'`. Durations now carry their own `format` method, so a `std.Io.Duration` prints with `{f}`:
`Io.Duration.fromMilliseconds(1500)` renders `1.5s`.

**Check:** `{D}` anywhere in the diff, `{e}`/`{E}` over an integer argument, `{c}` over an argument
wider than 8 bits, `{u}` over one wider than 21 bits, and a bare `{}` over a slice, optional, error
union, or many/C pointer. All but the format-string typos are compile errors — finding them in
review is cheaper than finding them from the compiler twice.

```zig
// verified — GOOD
const std = @import("std");
test "specifier table" {
    try std.testing.expectFmt("abc", "{s}", .{"abc"});
    try std.testing.expectFmt("42 -7", "{d} {d}", .{ 42, -7 });
    try std.testing.expectFmt("3.14", "{d:.2}", .{3.14159});
    try std.testing.expectFmt("ff FF", "{x} {X}", .{ 255, 255 });
    try std.testing.expectFmt("dead DEAD", "{x} {X}", .{ "\xde\xad", "\xde\xad" });
    try std.testing.expectFmt("1011 777", "{b} {o}", .{ 11, 511 });
    try std.testing.expectFmt("Z", "{c}", .{@as(u8, 'Z')});
    try std.testing.expectFmt("1.2345e3", "{e}", .{1234.5});
    try std.testing.expectFmt("{ 1, 2, 3 }", "{any}", .{[_]u8{ 1, 2, 3 }});
    try std.testing.expectFmt("aGk=", "{b64}", .{"hi"});
    try std.testing.expectFmt("1.5kB 1.5KiB", "{B} {Bi}", .{ 1500, 1536 });
    try std.testing.expectFmt("\"a\\\"b\\n\"", "{q}", .{"a\"b\n"});
}
```

Four cases where a bare `{}` is a **compile error**, which is the API telling you to be explicit:
slices (`{s}`, `{x}`, `{b64}`, or `{any}`), optionals (`{?}` or `{any}`), error unions (`{!}` or
`{any}`), and many/C pointers (`{s}` or `{*}`).

### ZS-FMT-05 [M] Print an enum, union tag, or error name with `{t}`
`{t}` yields `@tagName` for enums, enum literals, and tagged unions, and `@errorName` for error
sets. `{}` on the same values yields Zig *syntax* — `.warn`, `error.FileNotFound`.

**Why:** the two are for different audiences. `{t}` is the name you put in a log line, a wire
protocol, a JSON field, or a user-facing message; `{}` is a debug dump that happens to be
paste-able Zig. Silently shipping `.warn` where you meant `warn` breaks every consumer that parses
the field. Note also that `{d}` on an enum prints the tag's integer value, not its name — three
different renderings of the same value, only one of which is usually what you want.

**Check:** a `{}` or `{d}` whose argument is an enum, tagged union, or error value inside a log
line, a serialized field, or a user-facing message. Also `@tagName(` or `@errorName(` used solely to
feed a `{s}` — that is `{t}` written the long way.

```zig
// fragment — GOOD
const std = @import("std");
test "{t} prints names, {} prints syntax" {
    try std.testing.expectFmt("warn", "{t}", .{Level.warn});
    try std.testing.expectFmt("leaf", "{t}", .{Node{ .leaf = 1 }});
    try std.testing.expectFmt("FileNotFound", "{t}", .{error.FileNotFound});

    // `{}` renders Zig syntax instead, which is a debug dump, not a name.
    try std.testing.expectFmt(".warn", "{}", .{Level.warn});
    try std.testing.expectFmt("error.FileNotFound", "{}", .{error.FileNotFound});
}
```

`{t}` is also the right specifier for logging a captured error — `log.err("failed: {t}", .{err})` —
which is the form used throughout `references/errors-and-control-flow.md` ZS-ERR-17.

### ZS-FMT-06 [M] Give `{?}` and `{!}` an inner specifier for the payload
`{?x}` means "hex if present, otherwise `null`"; `{!d}` means "decimal if successful, otherwise the
error". The character after `?` or `!` is the payload's specifier.

**Why:** a bare `{?}` or `{!}` applies the *default* rendering to the payload, which for a slice
payload is a compile error and for an enum payload is `.name` rather than the name. Spelling the
inner specifier keeps one placeholder honest about both branches.

**Check:** the literal strings `{?}` and `{!}` — a bare sigil with nothing between it and the
closing brace — and their aligned forms `{?:` and `{!:`.

```zig
// verified — GOOD
const std = @import("std");
test "optionals and error unions carry an inner specifier" {
    const present: ?u32 = 255;
    const absent: ?u32 = null;
    try std.testing.expectFmt("ff null", "{?x} {?x}", .{ present, absent });

    const ok: anyerror!u32 = 7;
    const bad: anyerror!u32 = error.Broken;
    try std.testing.expectFmt("7 error.Broken", "{!d} {!d}", .{ ok, bad });
}
```

Formatting an error union is a *debugging* convenience, not error handling: it consumes the error
without propagating it, which destroys the error return trace
(`references/errors-and-control-flow.md` ZS-ERR-17). Handle the error, then format the outcome.

### ZS-FMT-07 [S] Treat `{any}` as a debugging dump — never as an output format
`{any}` prints the compiler's structural rendering and stops at `std.options.fmt_max_depth`
(default 3), replacing anything deeper with `.{ ... }`.

**Why:** the output is silently *truncated* rather than wrong-but-complete, and its exact shape is a
compiler implementation detail that has already changed twice. Anything a machine will read, a user
will see, or a test will compare needs a `format` method and `{f}`. Deviate freely inside
`log.debug` and while bisecting a bug.

**Check:** `{any}` in a format string that is not the argument of `log.debug` — specifically inside
`expectFmt`, a writer that reaches a file or socket, or any string later parsed.

```zig
// verified — GOOD: demonstrating the truncation, not endorsing the format
const std = @import("std");
test "{any} is depth limited" {
    const L3 = struct { v: u32 };
    const L2 = struct { c: L3 };
    const L1 = struct { b: L2 };
    const Outer = struct { a: L1 };
    const o: Outer = .{ .a = .{ .b = .{ .c = .{ .v = 1 } } } };
    // std.options.fmt_max_depth defaults to 3: deeper fields become `.{ ... }`.
    try std.testing.expectFmt(".{ .a = .{ .b = .{ .c = .{ ... } } } }", "{any}", .{o});
}
```

### ZS-FMT-08 [S] `{*}` prints an address; keep addresses out of anything compared or persisted
`{*}` renders `Child@hexaddress`. A single-item pointer to a non-container type renders the same way
under a bare `{}`.

**Why:** addresses vary per run under ASLR, so a golden test containing one is flaky by
construction, and a log line containing one is meaningless to anyone without the same process image.
Deviate when identity is exactly what you are debugging — a use-after-free, an aliasing question, a
vtable mix-up — and say so in the message.

**Check:** `{*}` in an `expectFmt` or golden-file comparison, in a `format` method, or in anything
written to disk or a wire. Also a bare `{}` whose argument is a `*T` where `T` is not a container,
which renders the same address.

```zig
// fragment
std.log.debug("node {*} reparented under {*}", .{ child, parent }); // identity is the point
```

---

## 3. Width, fill, alignment, precision

### ZS-FMT-09 [M] Width is counted in bytes, so it does not align non-ASCII text
`{s:>6}` pads to six *bytes*. The `Io.Writer.print` doc comment says it outright: "Alignment is not
Unicode-aware; appropriate only when used with raw bytes or ASCII."

**Why:** any column layout built with `{s:<N}` over user-supplied text misaligns the moment a
non-ASCII byte appears, and it misaligns *more* for scripts with wide glyphs, where even a codepoint
count would be wrong: `"héllo"` is five codepoints but six bytes, so `{s:>6}` pads it by
zero.

**Check:** a `{s:` carrying a width or fill whose argument can originate outside the program — a
filename, a username, a record field, a translated message. A width over a hex digest, an
identifier, or a `{t}` name is fine.

```zig
// verified — GOOD: showing the trap
const std = @import("std");
test "width counts bytes, not codepoints" {
    // "ok" is 2 bytes, so it is padded to 6.
    try std.testing.expectFmt("[    ok]", "[{s:>6}]", .{"ok"});
    // "héllo" is 5 codepoints but 6 bytes, so it is not padded at all.
    try std.testing.expectFmt("[héllo]", "[{s:>6}]", .{"héllo"});
}
```

For a table whose cells may contain non-ASCII, compute the display width yourself (count codepoints
with `std.unicode`, and account for wide and combining characters) and emit the padding explicitly.
Reserve `{s:<N}` for text you know is ASCII — hex digests, identifiers, enum names via `{t}`.

### ZS-FMT-10 [M] Width and precision are for numbers and strings; on an enum they panic
`fill`, `alignment`, and `width` apply to numbers and to string-like renderings (`{s}`, `{t}`,
bools). `precision` applies to floats. Applying width to a value that renders through the "options
forbidden" path — a bare `{}` on an enum or an error set, `{x}` on a slice, `{b64}` — trips
`assert(options.width == null)` at **runtime**.

**Why:** the check is an assertion inside `optionsForbidden`, a private helper in
`std/Io/Writer.zig`, not a `@compileError`, so `"{:>8}"` on an enum builds cleanly and then panics
with `reached unreachable code` in `debug` and `safe` — or, in `fast`, silently proceeds with a
violated invariant (see ZS-CORE-10). The
fix is always to name the rendering you want: `{t:>8}`, not `{:>8}`.

**Check:** a placeholder whose specifier is empty but which carries a `:` — the literal patterns
`{:` and `{[`…`]:` with no specifier letter — and a width on `{x}`/`{X}`/`{b64}` over a slice. These
build cleanly, so grep is the only line of defence.

```zig
// fragment — GOOD
const std = @import("std");
test "fill, alignment, width, precision" {
    try std.testing.expectFmt("[      42]", "[{d:>8}]", .{42});
    try std.testing.expectFmt("[42      ]", "[{d:<8}]", .{42});
    try std.testing.expectFmt("[   42   ]", "[{d:^8}]", .{42});
    try std.testing.expectFmt("[00000042]", "[{d:0>8}]", .{42});
    try std.testing.expectFmt("[***ab****]", "[{s:*^9}]", .{"ab"});
    try std.testing.expectFmt("[3.142]", "[{d:.3}]", .{@as(f64, 3.14159)});
    // Width is legal on {t} because it renders a string...
    try std.testing.expectFmt("[    warn]", "[{t:>8}]", .{Level.warn});
}
```

```zig
// fragment — BAD: compiles, then panics in Io/Writer.zig optionsForbidden
try w.print("[{:>8}]", .{Level.warn});
```

Two grammar details worth memorizing: a fill byte other than `0` **must** be followed by an
alignment character, or the parser reads it as the width; and `{d:0>8}` is the zero-padding idiom,
since `0` is the one fill byte allowed to appear without an explicit alignment. Precision has no
effect on `{s}` — `{s:.2}` of `"abcdef"` is `abcdef`, not `ab`, so truncate with a slice expression
instead.

---

## 4. The `std.fmt` API

### ZS-FMT-11 [M] Use the 0.17 names: `Options`, `Alt`/`alt`, `std.mem.printSentinel`
At 0.17.0, `std.fmt.Formatter`, `std.fmt.FormatOptions` and `std.fmt.bufPrintZ` **do not
exist**; `std.fmt.Options`, `std.fmt.Alt`/`std.fmt.alt` and
`std.mem.printSentinel(buf, fmt, args, 0)` are their replacements. The printing functions moved
out of `std.fmt` as well: `std.fmt.bufPrint`, `bufPrintSentinel`, `BufPrintError`, `allocPrint`
and `allocPrintSentinel` still compile, but each carries `/// Deprecated in favor of` its
replacement — respectively `mem.print`, `mem.printSentinel`, `mem.PrintError`, `Allocator.print`
and `Allocator.printSentinel`.

**Why:** the removals are compile errors and will be caught. The five deprecated print functions
are the dangerous ones — silent deprecation aliases, the same category of staleness as
`std.mem.indexOf` (SKILL.md 2.3): the build stays green while the code reads a generation old.

**Check:** `std.fmt.Formatter`, `std.fmt.FormatOptions`, or `std.fmt.bufPrintZ` anywhere in the
diff, and any `std.fmt.bufPrint`, `bufPrintSentinel`, `BufPrintError`, `allocPrint` or
`allocPrintSentinel`. Only those last five still compile, so they are the ones worth a standing
grep in CI.

```zig
// verified — GOOD
const std = @import("std");
const Writer = std.Io.Writer;
test "std.fmt surface in 0.17" {
    const gpa = std.testing.allocator;

    const heap = try gpa.print("{s}-{d}", .{ "id", 7 });
    defer gpa.free(heap);
    try std.testing.expectEqualStrings("id-7", heap);

    var buf: [16]u8 = undefined;
    const stack = try std.mem.print(&buf, "{s}-{d}", .{ "id", 7 });
    try std.testing.expectEqualStrings("id-7", stack);

    const z = try std.mem.printSentinel(&buf, "{d}", .{7}, 0);
    try std.testing.expectEqual(0, z[z.len]);

    // std.fmt.Options is the options struct; there is no FormatOptions.
    const opts: std.fmt.Options = .{ .width = 5, .fill = '0', .alignment = .right };
    var w: Writer = .fixed(&buf);
    try w.printInt(@as(u32, 42), 10, .lower, opts);
    try std.testing.expectEqualStrings("00042", w.buffered());
}
```

The full current surface: `comptimePrint`, `count`, `printInt`, `parseInt`, `parseUnsigned`,
`parseIntSizeSuffix`, `parseFloat`, `hexToBytes`, `bytesToHex`, `Options`, `Number`, `Alignment`,
`Case`, `Alt`, `alt`, `Placeholder`, `Parser`, `Specifier` — and, outside `std.fmt`,
`std.mem.print`, `std.mem.printSentinel`, `std.mem.PrintError`, `Allocator.print` and
`Allocator.printSentinel`.

### ZS-FMT-12 [M!] Use `std.mem.print`, not `gpa.print`, when a constant bounds the size
If the longest possible rendering can be derived from the argument types or from a named `_max`
constant, format into a fixed array with `std.mem.print`. Reach for `Allocator.print` (`gpa.print`)
only when the length genuinely depends on unbounded runtime data. (0.17 renamed both: `bufPrint`
and `allocPrint` are deprecated aliases of these two.)

**Why:** this is the bounded-limits principle (`references/assertions-and-limits.md` ZS-ASRT-24 and
ZS-ASRT-26) applied to formatting. A derived bound removes an allocation, an error path, a `defer
gpa.free`, and one way to leak — and it forces you to *state* the maximum length of the thing you
are printing, which is exactly the fact a reviewer needs. `[M!]` applies where an unbounded or
failing allocation is unacceptable: embedded and firmware, databases and other must-not-OOM
services, crypto, and any formatter reachable from untrusted input. *Relaxed form* elsewhere:
`gpa.print` is fine for one-shot, human-facing strings; keep `std.mem.print` for anything on a hot
path or inside a loop.

**Check:** an `Allocator.print`/`printSentinel` call (`gpa.print(`), or the deprecated
`allocPrint`/`allocPrintSentinel`, whose format string contains only fixed-width integer, float,
`{t}`, or literal-length placeholders — no `{s}` over unbounded input. Its maximum is derivable, so
a `std.mem.print` and a named `_max` constant belong there instead. An allocating print inside a
loop body is the same finding with the cost multiplied.

```zig
// verified — GOOD
/// Longest rendering of a shard label: "shard-" plus a u16 in decimal.
const std = @import("std");
const shard_label_max = "shard-".len + 5;

fn shardLabel(buffer: *[shard_label_max]u8, shard: u16) []const u8 {
    // The bound is derived from the type, so NoSpaceLeft is unreachable here
    // and the proof is the constant above.
    return std.mem.print(buffer, "shard-{d}", .{shard}) catch unreachable;
}

test "std.mem.print with a derived bound needs no allocator" {
    var buffer: [shard_label_max]u8 = undefined;
    try std.testing.expectEqualStrings("shard-65535", shardLabel(&buffer, 65535));
    try std.testing.expectEqualStrings("shard-0", shardLabel(&buffer, 0));
}
```

The `catch unreachable` above is only legitimate because the constant one line up *is* the proof, in
the sense ZS-ERR-10 requires. Without a derived bound, handle `error.NoSpaceLeft`: `std.mem.print`
writes as much as fits and then fails, so the partial output must not be used. Note also that
`Io.Writer.Allocating` reports allocation failure as `error.WriteFailed`, whereas `Allocator.print`
maps it back to `error.OutOfMemory` for you (`references/io-and-concurrency.md` ZS-IO-09).

### ZS-FMT-13 [S] Use `comptimePrint` for compile-time strings and `count` for exact sizing
`comptimePrint(fmt, args)` returns a `*const [N:0]u8` whose length is comptime-known;
`count(fmt, args)` returns the byte length a `print` would produce, without writing it.

**Why:** `comptimePrint` moves the formatting to compile time and gives you a string literal whose
length participates in later comptime arithmetic — array sizes, `@compileError` messages, generated
identifiers. `count` is how you size a buffer for a rendering whose bound is not obvious from the
types. Deviate when the string is only used once at runtime; a comptime string costs binary size.

**Check:** a `std.mem.print` (or deprecated `bufPrint`) into an array whose length is a bare
numeric literal rather than a named constant derived by `comptimePrint`, `count`, or arithmetic
over the argument types. In the other direction: a `comptimePrint` whose result feeds exactly one
runtime `print`.

```zig
// verified — GOOD
const std = @import("std");
const assert = std.debug.assert;
test "comptimePrint and count" {
    const banner = std.fmt.comptimePrint("v{d}.{d}", .{ 0, 16 });
    comptime assert(banner.len == 5); // length is known at compile time
    try std.testing.expectEqualStrings("v0.16", banner);
    try std.testing.expectEqual(5, std.fmt.count("{d}", .{65535}));
}
```

To count bytes produced by a *runtime* stream rather than a format call, use
`Io.Writer.Discarding`, whose total is `dw.count + dw.writer.end`.

### ZS-FMT-14 [M] Parse with `parseInt`/`parseFloat` and handle both failure modes by name
`std.fmt.parseInt(T, text, base)` fails with `error.InvalidCharacter` or `error.Overflow`;
`parseFloat(T, text)` fails with `error.InvalidCharacter`. Base `0` infers from a `0x`/`0o`/`0b`
prefix.

**Why:** the two integer errors need different messages — one means "that is not a number", the
other means "that number is too big for this field" — and collapsing them into a single "bad input"
loses the only actionable half of the diagnostic. This is also the canonical boundary check from
ZS-CORE-08: text arriving from outside the process is validated with an error, never an assertion.

**Check:** a `parseInt` whose failure is handled by one `catch` arm, a `catch unreachable`, or a
message that names neither `InvalidCharacter` nor `Overflow`. Also a `parseInt(u64, …)` or
`parseInt(usize, …)` followed by a hand-written range comparison, where a narrower destination type
would have done the check.

```zig
// verified — GOOD
const std = @import("std");
fn parsePort(text: []const u8) error{ InvalidCharacter, Overflow }!u16 {
    return std.fmt.parseInt(u16, text, 10);
}

test "parseInt reports both failure modes" {
    try std.testing.expectEqual(8080, try parsePort("8080"));
    try std.testing.expectError(error.InvalidCharacter, parsePort("80x"));
    try std.testing.expectError(error.Overflow, parsePort("99999"));
    try std.testing.expectEqual(1.5, try std.fmt.parseFloat(f64, "1.5"));
}
```

Note that the destination type *is* the range check: `parseInt(u16, ...)` rejects `99999` for you,
so choose the narrowest type the field admits rather than parsing into `u64` and comparing
afterwards.

### ZS-FMT-15 [M!] Round-trip every format you persist or transmit, in a test
For any rendering that will be written to disk, sent over a wire, or read back by another program,
write a test that formats a value and parses it back, and assert equality over a set of values that
includes the extremes.

**Why:** this is `references/assertions-and-limits.md` ZS-ASRT-18 — check a property on both code
paths — applied to serialization, and it is the cheapest possible defence against the ZS-FMT-01
failure mode: a `{}` that should have been `{f}` changes the output, and the round-trip test is what
notices. `[M!]` applies to formats you cannot change later: on-disk records, wire protocols, log
formats consumed by tooling, anything with a version number. *Relaxed form* for human-facing output:
assert the exact expected string with `std.testing.expectFmt` for at least the boundary values,
which catches the same class of regression without requiring a parser.

**Check:** a type declaring both `format` and a `parse`/`decode`/`fromBytes` function, with no test
whose body calls one on the output of the other. Also any diff that edits a `format` method of a
persisted type and adds no test.

```zig
// verified — GOOD
const std = @import("std");
const Writer = std.Io.Writer;
const RecordId = struct {
    epoch: u32,
    index: u32,

    pub fn format(id: RecordId, w: *Writer) Writer.Error!void {
        try w.print("{d}:{d}", .{ id.epoch, id.index });
    }

    pub const ParseError = error{InvalidFormat} || std.fmt.ParseIntError;

    pub fn parse(text: []const u8) ParseError!RecordId {
        const colon = std.mem.findScalar(u8, text, ':') orelse return error.InvalidFormat;
        return .{
            .epoch = try std.fmt.parseInt(u32, text[0..colon], 10),
            .index = try std.fmt.parseInt(u32, text[colon + 1 ..], 10),
        };
    }
};

test "format and parse are checked against each other" {
    var buffer: [24]u8 = undefined;
    for ([_]RecordId{
        .{ .epoch = 0, .index = 0 },
        .{ .epoch = 1, .index = 4_294_967_295 },
    }) |id| {
        const text = try std.mem.print(&buffer, "{f}", .{id});
        try std.testing.expectEqual(id, try RecordId.parse(text));
    }
}
```

`buffer` is `[24]u8` because two `u32`s and a colon cannot exceed 21 bytes — the ZS-FMT-12
discipline again. A `std.testing.Smith` fuzz target over the same pair is the natural next step
(`references/testing-and-fuzzing.md`).

---

## 5. Where the bytes go

### ZS-FMT-16 [M] Program output goes to a buffered, flushed `*Io.Writer` — never `std.debug.print`
Build the writer in `main` from `init.io`, pass `*Io.Writer` down, `flush()` on every success path.
`std.debug.print` writes to **stderr**, unbuffered, one syscall per call, swallowing every error.

**Why:** stated in full at `references/io-and-concurrency.md` ZS-IO-05 (flush or lose the bytes) and
ZS-IO-06 (`std.debug.print` bypasses the `Io` interface, cannot be redirected, and cannot be
substituted in a test). The formatting consequence is the one to remember here: a `std.debug.print`
that "works" is writing your program's output to the wrong stream, so `prog > out.txt` produces an
empty file and a terminal full of results.

**Check:** `std.debug.print` anywhere outside a `// BAD` example, a scratch debugging commit, or an
`errdefer` failure diagnostic inside a `test` block (which `references/testing-and-fuzzing.md`
ZS-TEST-11 requires — see ZS-IO-06 for why tests are the one exception). Then, for each
`Io.File.Writer` constructed in the diff, a `flush()` on every `return` path out of the function
that owns it — an early `return` before the flush loses everything buffered.

```zig
// verified — GOOD: the whole shape, from `main` down
const std = @import("std");
const Io = std.Io;
const Writer = std.Io.Writer;
pub fn main(init: std.process.Init) !void {
    const io = init.io;

    var stdout_buffer: [4096]u8 = undefined;
    var stdout_writer: Io.File.Writer = .init(.stdout(), io, &stdout_buffer);
    const stdout = &stdout_writer.interface;

    try emitRows(stdout, &.{ 10, 20 });
    try stdout.flush(); // buffered bytes are lost without this
}

fn emitRows(w: *Writer, rows: []const u32) Writer.Error!void {
    for (rows, 0..) |row, i| try w.print("{d}\t{d}\n", .{ i, row });
}
```

```zig
// verified — GOOD: the same function under test, with no process and no files
fn emitRows(w: *Writer, rows: []const u32) Writer.Error!void {
    for (rows, 0..) |row, i| try w.print("{d}\t{d}\n", .{ i, row });
}

const std = @import("std");
const Writer = std.Io.Writer;
test "program output goes through a writer" {
    var aw: Writer.Allocating = .init(std.testing.allocator);
    defer aw.deinit();
    try emitRows(&aw.writer, &.{ 10, 20 });
    try std.testing.expectEqualStrings("0\t10\n1\t20\n", aw.written());
}
```

That second block is the payoff: because `emitRows` takes `*Io.Writer` rather than reaching for
stdout, the exact bytes are testable. A function that calls `std.debug.print` is not.

### ZS-FMT-17 [M] A library renders into the caller's writer or returns bytes; it never prints
`ZS-ERR-03` states the general rule — a library never panics, exits, or prints. Its formatting form:
a reusable function takes `w: *Io.Writer` and returns `Io.Writer.Error!void`, or returns an owned
`[]u8` the caller frees. It never opens stdout, and it never decides where the output goes.

**Why:** the caller may be writing to a socket, a hash, a compressor, an in-memory buffer, or a test
double, and only the caller knows. Taking `*Io.Writer` costs nothing — it is already type-erased
(ZS-IO-08) — and it is what makes the round-trip test in ZS-FMT-15 possible at all.

**Check:** in a module that is not the executable's root: `.stdout()`, `.stderr()`,
`std.debug.print`, `std.process.fatal`, or `std.process.exit`. The milder form is a `pub fn` that
renders a value and returns `void` without taking a `w: *Writer` parameter.

```zig
// fragment — GOOD
/// A library renders into the caller's writer. It never opens stdout and never
/// decides that the process should stop.
const std = @import("std");
const Writer = std.Io.Writer;
pub fn writeManifest(w: *Writer, version: Version, entries: u32) Writer.Error!void {
    try w.print("version={f}\nentries={d}\n", .{ version, entries });
}
```

Diagnostics are the exception, and they go through a scoped `std.log` namespace so the *application*
decides whether the library is audible: `references/errors-and-control-flow.md` ZS-ERR-32.

### ZS-FMT-18 [M] Pick the failure channel by who needs to read it
Three mechanisms, one decision:

| Situation | Mechanism | What the user sees |
|---|---|---|
| Bad arguments, missing input, unusable environment — the user must fix something | `std.process.fatal(fmt, args)` | one line on stderr, exit code 1 |
| Something went wrong and the program continues | `std.log.err(fmt, args)` | one line on stderr, exit code unchanged |
| A bug, or a failure whose *origin* is the diagnostic | `return err` from `main` | `error: Name` plus the error return trace |

`std.process.fatal` takes exactly two parameters and is `noreturn`:
`pub fn fatal(comptime format: []const u8, format_arguments: anytype) noreturn`.
Its body is `std.log.err(format, format_arguments); exit(1);` — so it honours the application's
`logFn` and the same stderr lock, unlike a hand-rolled `stderr.print` + `exit`.

**Why:** a stack trace is a message to *you*; a sentence is a message to the *user*. A CLI that
dumps an error return trace because someone typed a non-numeric port is unusable, and a service that
swallows a corrupt-state error into a one-line message has thrown away the only record of where it
came from. On 0.17.0, `fatal` printed `error: 'abc' is not a number` and exited 1
with stdout empty; returning `error.UnluckyCount` from `main` printed the error name *and* the
`return` site with source lines.

**Check:** a `main` that propagates a raw error out of argument parsing or environment lookup — the
user gets a stack trace for a typo. Conversely, a `std.process.fatal` whose message describes an
internal invariant rather than something the user can fix. And any hand-rolled
`stderr.print(...)` followed by `std.process.exit(1)`, which bypasses the application's `logFn`.

```zig
// verified — GOOD: a complete CLI failure surface
const std = @import("std");
pub fn main(init: std.process.Init) !void {
    const arena = init.arena.allocator();
    const args = try init.minimal.args.toSlice(arena);
    if (args.len < 2) std.process.fatal("usage: {s} <count>", .{args[0]});

    const count = std.fmt.parseInt(u32, args[1], 10) catch |err| switch (err) {
        error.InvalidCharacter => std.process.fatal("'{s}' is not a number", .{args[1]}),
        error.Overflow => std.process.fatal("'{s}' does not fit in u32", .{args[1]}),
    };
    if (count == 13) return error.UnluckyCount; // a bug: let the trace speak
}
```

Note the error return trace exists only in `debug` and `safe`
(`references/errors-and-control-flow.md` ZS-ERR-17), so `return err` from `main` degrades to a bare
`error: Name` in `fast` — another reason to ship `safe` (ZS-CORE-10).

---

## 6. Logging

### ZS-FMT-19 [S] A custom `std.options.logFn` is the only route to timestamps or a sink
`std.log.defaultLog` writes `level(scope): message` to stderr with color and nothing else — no
timestamp, no key/value structure, no destination choice. Overriding `logFn` in the root source file
is the whole extension mechanism. The signature, from the `logFn` field of `std.Options`:

```zig
// fragment
logFn: fn (
    comptime message_level: log.Level,
    comptime scope: @EnumLiteral(),
    comptime format: []const u8,
    args: anytype,
) void = log.defaultLog,
```

**Why:** three properties of that signature drive the rules. It receives **no `Io`**, so it cannot
await, cannot do async I/O, and must not call anything that suspends — which is why the body below
uses `std.debug.lockStderr` (the `Io`-bypassing variant) rather than `io.lockStderr`. Its first
three parameters are `comptime`, so level, scope, and the format string cost nothing at runtime and
can be concatenated into a prefix at compile time. And it is a single global function, so filtering
by scope belongs in `std_options.log_scope_levels` (ZS-ERR-33), not in an `if` chain here. Deviate —
i.e. keep `defaultLog` — whenever stderr text is genuinely enough; a custom `logFn` is a piece of
infrastructure to maintain.

**Check:** inside a `logFn` body: a write to stderr not obtained from `std.debug.lockStderr`, a
missing `defer std.debug.unlockStderr()`, any `io.` call or other operation that can suspend, a file
open, a `try`, or a `catch unreachable`. Also an `if` chain on `scope` inside the body, which
belongs in `std_options.log_scope_levels`.

```zig
// verified — GOOD: prints "info default: starting 1"
const std = @import("std");
pub const std_options: std.Options = .{
    .log_level = .debug,
    .logFn = logWithPrefix,
};

fn logWithPrefix(
    comptime level: std.log.Level,
    comptime scope: @EnumLiteral(),
    comptime format: []const u8,
    args: anytype,
) void {
    // No `Io` is available here, so use the debug-level stderr lock. It is the
    // same mutex `std.Progress` and the panic handler take.
    var buffer: [512]u8 = undefined;
    const stderr = std.debug.lockStderr(&buffer);
    defer std.debug.unlockStderr();

    const w = &stderr.file_writer.interface;
    w.print("{t} {t}: ", .{ level, scope }) catch return;
    w.print(format ++ "\n", args) catch return;
}
```

Taking the lock is not optional. `std.log`, the panic handler, and `std.Progress` all serialize on
it, and `lockStderr` additionally clears any progress bar before you write (`LockedStderr.clear`).
Writing to stderr outside it interleaves your log lines with progress escape sequences and panic
traces. `unlockStderr` flushes, so the writer needs no separate `flush`. For a file sink, open the
file once at startup and hold it in a global the `logFn` reads — it cannot open one itself without
an `Io`, and it must not fail. Application-level stderr writes *outside* a `logFn`, where you do
have an `Io`, use `io.lockStderr` instead (ZS-IO-11).

---

## 7. Dead formatting API

### ZS-FMT-20 [M] Reject the old formatting API on sight
Each entry is checked against 0.17.0. GONE means a compile error; the deprecated aliases
still build and are therefore silent staleness.

**Why:** the rows that do not say GONE are the ones that do not fail the build. A `{}` on a
formattable type, a deprecated `std.fmt` print function, and a `std.debug.print` carrying program
output all compile, run, and exit 0 — so the only thing standing between them and production is
this table and the review checklist in SKILL.md.

**Check:** grep the diff for every left-column entry below. The rows that compile — a `{}` on a
formattable type, the deprecated `std.fmt` print functions (`bufPrint`, `bufPrintSentinel`,
`BufPrintError`, `allocPrint`, `allocPrintSentinel`), and `std.debug.print` carrying program
output — are the ones worth a permanent CI grep; the rest the compiler will find for you.

| Dead | Status | Replacement |
|---|---|---|
| `{}` on a type with a `format` method | **compiles, wrong output** | `{f}` |
| `pub fn format(v, comptime fmt, options, writer)` | GONE | `pub fn format(v, w: *Io.Writer) Io.Writer.Error!void` |
| `{D}` (duration) | GONE | the type's own `format`, via `{f}` |
| `std.fmt.Formatter` | GONE | `std.fmt.Alt` / `std.fmt.alt` |
| `std.fmt.FormatOptions` | GONE | `std.fmt.Options` |
| `std.fmt.format(writer, fmt, args)` | GONE | `w.print(fmt, args)` |
| `std.fmt.formatType` / `formatIntValue` | GONE | `w.printValue(...)` / `w.printInt(...)` |
| `std.fmt.fmtSliceHexLower` / `fmtSliceHexUpper` | GONE | `{x}` / `{X}` on the slice |
| `std.fmt.fmtDuration` | GONE | `{f}` on an `Io.Duration` |
| `std.fmt.fmtIntSizeDec` / `fmtIntSizeBin` | GONE | `{B}` / `{Bi}` |
| `std.fmt.allocPrintZ` | GONE | `gpa.printSentinel(fmt, args, 0)` |
| `std.fmt.bufPrintZ` | GONE (a deprecated alias in 0.16) | `std.mem.printSentinel(buf, fmt, args, 0)` |
| `std.fmt.allocPrint` / `allocPrintSentinel` | deprecated alias | `gpa.print(fmt, args)` / `gpa.printSentinel(fmt, args, 0)` |
| `std.fmt.bufPrint` / `bufPrintSentinel` / `BufPrintError` | deprecated alias | `std.mem.print` / `std.mem.printSentinel` / `std.mem.PrintError` |
| `std.debug.print` for program output | works, wrong stream | a buffered `*Io.Writer` + `flush()` |

The whole-namespace removals that also bite formatting code — `std.io`, `std.io.Writer`,
`GenericWriter`, `AnyWriter`, `fixedBufferStream` — are tabulated in
`references/io-and-concurrency.md` ZS-IO-39.
