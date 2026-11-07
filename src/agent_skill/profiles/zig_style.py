"""zig-style: its own `[M]` rules, applied to its examples and prose."""

lazy from collections.abc import Iterator

from agent_skill.ids import RuleId
from agent_skill.lang.zig import ZIG_STYLE
from agent_skill.profiles.record import (
    LineRule,
    Near,
    NotDecisive,
    Profile,
    Unless,
    keyed,
    rules,
)
from agent_skill.profiles.rust_style import META
from agent_skill.report import Level, declare, fail
lazy from agent_skill.model import Block
lazy from agent_skill.report import Finding

# The branches of `conventions` and of `prose` this standard's own rules
# fire through.
CATCH = declare("conventions", "zs_catch", Level.FAIL)
UNWRAP = declare("conventions", "zs_unwrap", Level.FAIL)
AS_WRAPPER = declare("conventions", "zs_as_wrapper", Level.FAIL)
META_DOC = declare("conventions", "zs_meta_doc", Level.FAIL)
IMPORT_ORDER = declare("conventions", "zs_import_order", Level.FAIL)
UNWRAP_PROSE = declare("prose", "zs_unwrap", Level.FAIL)

#: A comment on the line, or opening one of the three above it.
COMMENTED = Unless(near=(Near("//"), Near(r"^\s*//", above=3, own=False)))

CONVENTIONS = (
    # ZS-ERR-08 and ZS-ERR-09 [M] — a `catch unreachable` carries its
    # proof, and a `catch {}` its justification, in a comment, which
    # may sit on the line above.
    LineRule(
        CATCH,
        r"catch\s*unreachable",
        "`{0}` without the comment ZS-ERR-08 requires",
        unless=COMMENTED,
    ),
    LineRule(
        CATCH,
        r"catch\s*\{\s*\}",
        "`{0}` without the comment ZS-ERR-09 requires",
        unless=COMMENTED,
    ),
    # ZS-ERR-26 [M] — "every hit is a defect, including inside
    # `comptime` blocks and `const` initializers".
    LineRule(
        UNWRAP,
        r"\.\?",
        "`.?` unwrap; ZS-ERR-26 asks for `orelse`, a capture, or "
        "`orelse unreachable` with the proof beside it",
        unless_own=RuleId.parse("ZS-ERR-26"),
    ),
    # ZS-TEST-05 [M] — "drop the `@as` wrapper": peer resolution already
    # handles a literal on the other side.
    LineRule(
        AS_WRAPPER,
        r"expectEqual\(@as\([a-zA-Z0-9_]+, [^()]*\), ",
        "`@as` wrapper inside `expectEqual`; peer resolution already handles it "
        "(ZS-TEST-05)",
    ),
    LineRule(
        META_DOC,
        rf"(?i)^\s*///.*{META}",
        "doc comment discusses the example rather than the API",
        comments=True,
    ),
)

PROSE = (
    # ZS-ERR-26 forbids `.?` outright. Prose naming it is therefore
    # either hunting it (inside a `**Check:**`) or is the rule that bans
    # it. Anything else is the standard recommending a spelling it
    # forbids, which is how three passages survived the rule being
    # tightened.
    LineRule(
        UNWRAP_PROSE,
        r"`[^`\n]*\.\?[^`\n]*`",
        "prose names `.?` outside a **Check:** and outside ZS-ERR-26",
        unless_own=RuleId.parse("ZS-ERR-26"),
        unless=Unless(near=(Near("ZS-ERR-26"),)),
    ),
)


def import_order(b: Block) -> Iterator[Finding]:
    """ZS-MOD-09 — imports run `@This()`, `builtin`, `std`, then local.

    The rule is [S], but a suggestion the library declines to follow in
    its own examples is not a suggestion. Which of two lines comes first
    is a fact about the example, not about either line.
    """
    lines = b.lines
    first = {
        kind: i
        for i in range(len(lines) - 1, -1, -1)
        for kind in ("builtin", "std")
        if f'@import("{kind}")' in lines[i]
    }
    if "builtin" in first and "std" in first and first["builtin"] > first["std"]:
        yield fail(
            '`@import("builtin")` below `@import("std")` (ZS-MOD-09)',
            b.where_at(first["builtin"]),
            IMPORT_ORDER,
        )


PROFILE = Profile(
    name="zig-style",
    prefix="ZS",
    languages=("zig",),
    # `build.zig.zon` examples carry markers too, and were invisible to
    # every tool while the rule prefix was derived from the fence tag.
    marked_languages=("zon",),
    tools=("zig",),
    language="Zig",
    verified_as="compiles as written against Zig {pin}",
    strict_scope="high-reliability",
    toolchain=ZIG_STYLE,
    exempt=keyed(
        {
            # ZS-NAME-13: "keep `self` for anonymous generic
            # containers" — a receiver typed `Self` is the case the
            # rule permits.
            "ZS-NAME-13": Unless(near=(Near("Self"),)),
            # ZS-TEST-10: "`rg …` inside `test` blocks — every hit must
            # be on an `errdefer` line". Container-scope logging is not
            # the target.
            "ZS-TEST-10": Unless(near=(Near("errdefer"),), outside_tests=True),
        }
    ),
    # Each snippet is the defect its rule forbids, written the way it
    # turns up in real code. A fixture shaped to match proves the
    # fixture, not the pattern.
    fires=keyed(
        {
            "ZS-BUILD-28": (
                "- uses: actions/checkout@v7",
                "- uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1",
            ),
            # Two patterns, so two fixtures: each the call a `changed`
            # row of ZS-MIG-01's says to re-read, written as a 0.16 call
            # site had it.
            "ZS-MIG-01": (
                "if (std.mem.containsAtLeastScalar(u8, list, 3, 'a')) return;",
                "if (std.mem.eql(f64, readings, baseline)) return;",
            ),
            "ZS-CONC-12": ("        _ = splat;",),
            "ZS-DATA-06": ("const pages = (size_bytes + page_size - 1) / page_size;",),
            "ZS-DATA-12": ("const config = Config{ .port = 8080, .verbose = false };",),
            "ZS-OUT-19": (
                '    return parseInner(gpa, text) catch @panic("bad input");',
            ),
            "ZS-ERR-02": ("pub fn load(gpa: Allocator, path: []const u8) ![]u8 {",),
            "ZS-ERR-04": (
                "pub fn run(io: Io, args: []const []const u8) anyerror!void {",
            ),
            "ZS-ERR-26": ("const first = list.first.?;",),
            "ZS-INTEROP-08": ("fn area(width: c_int, height: c_int) c_int {",),
            "ZS-INTEROP-09": ("const Buffer = struct { data: [*c]u8, len: usize };",),
            "ZS-COMPTIME-08": ("pub fn Store(comptime Allocator: type) type {",),
            "ZS-COMPTIME-11": (
                "const default = field.default_value_ptr orelse return null;",
            ),
            "ZS-OUT-10": ('try w.print("{:>8}", .{level});',),
            "ZS-PERF-25": ("@prefetch(&values[i + stride], .{});",),
        }
    ),
    # Each of these ships an `rg` pattern that no fixture in `fires`
    # proves yet. Giving one a fixture means deleting it here, which
    # `sensitivity` insists on, so the list only shrinks.
    unproven=rules(
        "ZS-ASSERT-08",
        "ZS-ASSERT-20",
        "ZS-ASSERT-04",
        "ZS-BUILD-19",
        "ZS-BUILD-30",
        "ZS-BUILD-31",
        "ZS-COMPTIME-15",
        "ZS-MEM-04",
        "ZS-MEM-06",
        "ZS-NAME-13",
        "ZS-MOD-08",
        "ZS-DOC-08",
        "ZS-NAME-17",
        "ZS-TEST-02",
        "ZS-TEST-06",
        "ZS-TEST-07",
        "ZS-TEST-08",
        "ZS-TEST-10",
        "ZS-TEST-20",
        "ZS-TEST-30",
    ),
    # Measured, not judged: each of these was promoted to accuse and
    # hit the standard's own compliant examples. The reason names what
    # the span finds and what, outside the match, decides whether the
    # hit is a defect — never how many examples it hit the day someone
    # measured, which is a number `_render` already prints live two
    # fields away and nothing re-measures.
    not_decisive=keyed(
        {
            "ZS-INTEROP-08": NotDecisive(
                "c_int",
                "the span finds every C type; whether the hit is inside the "
                "designated boundary module decides, and a line does not say which "
                "file it is in",
            ),
            "ZS-INTEROP-09": NotDecisive(
                "[*c]",
                "the span finds every `[*c]`; whether it is a parameter of an "
                "`export fn` or a `callconv(.c)` function — the one place it is "
                "allowed — decides",
            ),
            "ZS-OUT-19": NotDecisive(
                "@panic\\(",
                "the pattern finds every `@panic(` and `std.process.exit`; whether the "
                "file is a library rather than `main` or `build.zig` decides",
            ),
            "ZS-ERR-02": NotDecisive(
                "pub fn \\w+",
                "the pattern finds every public inferred error set; whether the "
                "function is `main` decides",
            ),
            "ZS-PERF-20": NotDecisive(
                "*Self",
                "the span finds every `*Self` receiver; whether the helper assigns to "
                "a field the parent could apply instead decides",
            ),
            "ZS-ASSERT-20": NotDecisive(
                "returns hits only from",
                "the Check asks which file a `_max` lives in, which a standalone "
                "block cannot answer",
            ),
            "ZS-ASSERT-04": NotDecisive(
                ".github/ build.zig scripts/",
                "scoped to the build and release scripts, where a hit is licensed "
                "by a benchmark the pattern cannot see",
            ),
            # Polarity: this Check asserts the shape is *present*, so
            # its hits are evidence of compliance and reading them as
            # defects inverts the rule.
            "ZS-BUILD-30": NotDecisive(
                "has this block",
                "a presence assertion, and scoped to `build.zig`: the finding is a "
                "missing guard, which no hit can show",
            ),
            "ZS-TEST-20": NotDecisive(
                "is the finding",
                "the pattern finds every PRNG; the `.init(` seed argument decides, and "
                "`std.testing.random_seed` is the compliant one",
            ),
        }
    ),
    # One probe per `zig` row in the chapters' `Decided by tools`
    # tables, each compiled on 0.17.0 and rejected with the row's
    # error (`research/zig-rows.md` in the refresh-zig change).
    probes={
        "unused local constant": (
            "export fn probe() void {\n    const x: u32 = 1;\n}\n"
        ),
        "unused local variable": ("export fn probe() void {\n    var x: u32 = 1;\n}\n"),
        "unused function parameter": ("export fn probe(x: u32) void {}\n"),
        "unused capture": ("export fn probe(o: ?*u32) void {\n    if (o) |p| {}\n}\n"),
        "pointless discard of …": (
            "export fn probe() u32 {\n"
            "    const x: u32 = 1;\n"
            "    _ = x;\n"
            "    return x;\n"
            "}\n"
        ),
        "local variable is never mutated": (
            "export fn probe() u32 {\n    var x: u32 = 1;\n    return x;\n}\n"
        ),
        "… shadows declaration of …": (
            "const count: u32 = 1;\n"
            "export fn probe() u32 {\n"
            "    const count: u32 = 2;\n"
            "    return count;\n"
            "}\n"
        ),
        "… shadows … from outer scope": (
            "export fn probe() u32 {\n"
            "    const a: u32 = 1;\n"
            "    {\n"
            "        const a: u32 = 2;\n"
            "        return a;\n"
            "    }\n"
            "    return a;\n"
            "}\n"
        ),
        "name shadows primitive …": (
            "export fn probe() u32 {\n    const u8: u32 = 1;\n    return u8;\n}\n"
        ),
        "unused … label": (
            "var n: u32 = 0;\n"
            "export fn probe() void {\n"
            "    blk: {\n"
            "        n += 1;\n"
            "    }\n"
            "}\n"
        ),
        "unattached documentation comment": (
            "const S = struct {\n    x: u32,\n    /// Nothing follows this.\n};\n"
        ),
        "expected statement, found 'a document comment'": (
            "export fn probe() u32 {\n"
            "    /// A doc comment on a statement.\n"
            "    const x: u32 = 1;\n"
            "    return x;\n"
            "}\n"
        ),
        "expected type expression, found 'a document comment'": (
            "const n: u32 = 1;\n//! A module doc comment after a declaration.\n"
        ),
        "union 'lang.CallingConvention' has no member named '…'": (
            "export fn probe() callconv(.C) void {}\n"
        ),
        "type does not have a fixed bitsize: …": (
            'const std = @import("std");\n'
            "fn draw(smith: *std.testing.Smith, n: usize) usize {\n"
            "    return smith.valueRangeLessThan(usize, 0, n);\n"
            "}\n"
            "comptime {\n"
            "    _ = &draw;\n"
            "}\n"
        ),
        "no field named '…' in struct 'Build.…Options'": (
            'const std = @import("std");\n'
            "fn build(b: *std.Build) void {\n"
            "    _ = b.addExecutable(.{\n"
            '        .name = "probe",\n'
            '        .root_source_file = b.path("src/main.zig"),\n'
            "    });\n"
            "}\n"
            "comptime {\n"
            "    _ = &build;\n"
            "}\n"
        ),
        "no field or member function named '…' in 'Build'": (
            'const std = @import("std");\n'
            "fn build(b: *std.Build) void {\n"
            '    _ = b.addStaticLibrary(.{ .name = "probe" });\n'
            "}\n"
            "comptime {\n"
            "    _ = &build;\n"
            "}\n"
        ),
        "error … of type … is ignored": (
            "fn f() error{Oops}!void {\n"
            "    return error.Oops;\n"
            "}\n"
            "export fn probe() void {\n"
            "    f();\n"
            "}\n"
        ),
        "error union is discarded": (
            "fn f() error{Oops}!u32 {\n"
            "    return error.Oops;\n"
            "}\n"
            "export fn probe() void {\n"
            "    _ = f();\n"
            "}\n"
        ),
        "value of type … ignored": (
            "fn g() u32 {\n    return 1;\n}\nexport fn probe() void {\n    g();\n}\n"
        ),
        "expected error union type, found …": (
            "fn g() void {}\nexport fn probe() void {\n    try g();\n}\n"
        ),
        "expected optional type, found …": (
            "fn g() u32 {\n"
            "    return 1;\n"
            "}\n"
            "export fn probe() u32 {\n"
            "    return g() orelse 0;\n"
            "}\n"
        ),
        "operator == not allowed for type …": (
            "const E = error{ A, B };\n"
            "fn f(x: u8) E!u8 {\n"
            "    if (x == 0) return error.A;\n"
            "    return x;\n"
            "}\n"
            "export fn probe(x: u8) bool {\n"
            "    return f(x) == 3;\n"
            "}\n"
        ),
        "duplicate switch value …": (
            "export fn probe(x: u8) u8 {\n"
            "    return switch (x) {\n"
            "        1 => 0,\n"
            "        1 => 1,\n"
            "        else => 2,\n"
            "    };\n"
            "}\n"
        ),
        "'try' not allowed inside defer expression": (
            "fn mayFail() error{Oops}!void {}\n"
            "export fn probe() void {\n"
            "    defer mayFail() catch {};\n"
            "}\n"
            "fn g() error{Oops}!void {\n"
            "    defer try mayFail();\n"
            "}\n"
            "comptime {\n"
            "    _ = &g;\n"
            "}\n"
        ),
        "cannot return from defer expression": (
            "fn h() u32 {\n"
            "    defer return 1;\n"
            "    return 2;\n"
            "}\n"
            "comptime {\n"
            "    _ = &h;\n"
            "}\n"
        ),
        "unreachable code": (
            "export fn probe() u32 {\n    return 1;\n    return 2;\n}\n"
        ),
        "returning address of expired local variable …": (
            "fn f() *const u8 {\n"
            "    var x: u8 = 1;\n"
            "    _ = &x;\n"
            "    return &x;\n"
            "}\n"
            "comptime {\n"
            "    _ = &f;\n"
            "}\n"
        ),
        "invalid builtin function: …": (
            "export fn probe() void {\n    @setCold(true);\n}\n"
        ),
        "… not allowed in function with calling convention …": (
            "export fn zs_f(s: []const u8) usize {\n    return s.len;\n}\n"
        ),
        "'@branchHint' must appear as the first statement in a function or "
        "conditional branch": (
            "export fn probe(x: u32) u32 {\n"
            "    const y = x + 1;\n"
            "    @branchHint(.cold);\n"
            "    return y;\n"
            "}\n"
        ),
        "redundant comptime keyword in already comptime scope": (
            'const std = @import("std");\n'
            "const n = comptime std.math.log2_int(u32, 1024);\n"
            "comptime {\n"
            "    _ = n;\n"
            "}\n"
        ),
    },
    domain={
        "comptime": "compile-time execution",
        "memory": "explicit allocators",
        "assertions": "assertions and the optimize modes",
        "interop": "the C ABI and cross-target builds",
    },
    conventions=CONVENTIONS,
    prose=PROSE,
    structural=(import_order,),
)
