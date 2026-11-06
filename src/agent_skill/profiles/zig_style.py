"""zig-style: its own `[M]` rules, applied to its examples and prose."""

import re
lazy from collections.abc import Iterator

from agent_skill.lang.zig import LANGUAGE, ZIG_STYLE
from agent_skill.model import Skill, prose_lines
from agent_skill.profiles.record import Mirror, NotDecisive, Profile
from agent_skill.profiles.rust_style import META
from agent_skill.report import Finding, Level, declare, fail

# The branches of `conventions` and of `prose` this standard's own rules
# fire through.
CATCH = declare("conventions", "zs_catch", Level.FAIL)
UNWRAP = declare("conventions", "zs_unwrap", Level.FAIL)
AS_WRAPPER = declare("conventions", "zs_as_wrapper", Level.FAIL)
META_DOC = declare("conventions", "zs_meta_doc", Level.FAIL)
IMPORT_ORDER = declare("conventions", "zs_import_order", Level.FAIL)
UNWRAP_PROSE = declare("prose", "zs_unwrap", Level.FAIL)


def conventions(skill: Skill) -> Iterator[Finding]:
    """zig-style's own rules, applied to its own examples."""
    for b in skill.advice(LANGUAGE.fence):
        lines = b.lines
        for j, raw in enumerate(lines):
            where = b.where_at(j)
            code = LANGUAGE.uncommented(raw)

            # ZS-ERR-09 and ZS-ERR-10 [M] — a `catch unreachable`
            # carries its proof, and a `catch {}` its justification,
            # in a comment, which may sit on the line above.
            justified = "//" in raw or any(
                ln.strip().startswith("//") for ln in lines[max(0, j - 3) : j]
            )
            m = re.search(r"catch\s*(\{\s*\}|unreachable)", code)
            if m and not justified:
                rid = "ZS-ERR-09" if m.group(1) == "unreachable" else "ZS-ERR-10"
                found = m.group(0)
                yield fail(
                    f"`{found}` without the comment {rid} requires", where, CATCH
                )

            # ZS-ERR-26 [M] — "every hit is a defect, including
            # inside `comptime` blocks and `const` initializers"
            if ".?" in code and b.rule != "ZS-ERR-26":
                yield fail(
                    "`.?` unwrap; ZS-ERR-26 asks for `orelse`, a capture, or "
                    "`orelse unreachable` with the proof beside it",
                    where,
                    UNWRAP,
                )

            # ZS-TEST-04 [M] — "drop the `@as` wrapper": peer
            # resolution already handles a literal on the other side
            if re.search(r"expectEqual\(@as\([a-zA-Z0-9_]+, [^()]*\), ", code):
                yield fail(
                    "`@as` wrapper inside `expectEqual`; peer resolution already "
                    "handles it (ZS-TEST-04)",
                    where,
                    AS_WRAPPER,
                )

            if raw.lstrip().startswith("///") and META.search(raw):
                yield fail(
                    "doc comment discusses the example rather than the API",
                    where,
                    META_DOC,
                )

        # ZS-NAME-16 — "Order imports `@This()` → `builtin` → `std`
        # → local". The rule is [S], but a suggestion the library
        # declines to follow in its own examples is not a
        # suggestion.
        imports = {
            kind: i
            for i in range(len(lines) - 1, -1, -1)
            for kind in ("builtin", "std")
            if f'@import("{kind}")' in lines[i]
        }
        if (
            "builtin" in imports
            and "std" in imports
            and imports["builtin"] > imports["std"]
        ):
            yield fail(
                '`@import("builtin")` below `@import("std")` (ZS-NAME-16)',
                b.where_at(imports["builtin"]),
                IMPORT_ORDER,
            )


def prose(skill: Skill) -> Iterator[Finding]:
    """ZS-ERR-26 forbids `.?` outright.

    Prose naming it is therefore either hunting it (inside a
    `**Check:**`) or is the rule that bans it. Anything else is the
    standard recommending a spelling it forbids, which is how three
    passages survived the rule being tightened. Scoped per rule and
    per Check block, because both wrap.
    """
    span = re.compile(r"`[^`\n]*\.\?[^`\n]*`")
    for chapter in skill.chapters:
        for i, line, rid, in_check in prose_lines(chapter.text, skill.prefix):
            if rid == "ZS-ERR-26" or in_check or "ZS-ERR-26" in line:
                continue
            if span.search(line):
                yield fail(
                    "prose names `.?` outside a **Check:** and outside ZS-ERR-26",
                    chapter.where(i, rid),
                    UNWRAP_PROSE,
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
    exempt={
        # ZS-NAME-12: "keep `self` for anonymous generic containers"
        # — a receiver typed `Self` is the case the rule permits.
        "ZS-NAME-12": lambda lines, at, _in_test: "Self" in lines[at.start - 1],
        # ZS-TEST-09: "`rg …` inside `test` blocks — every hit must
        # be on an `errdefer` line". Container-scope logging is not
        # the target.
        "ZS-TEST-09": lambda lines, at, in_test: (
            (at.start - 1) not in in_test or "errdefer" in lines[at.start - 1]
        ),
    },
    # Each snippet is the defect its rule forbids, written the way it
    # turns up in real code. A fixture shaped to match proves the
    # fixture, not the pattern.
    fires={
        # Four patterns, because one line of alternation is
        # unreadable — so four fixtures. While there was one, three
        # of the four were counted as proven by a snippet none of
        # them matched, and any of the three could have been
        # narrowed to match nothing without this noticing. Each is
        # the *old* spelling from that pattern's own row in the
        # table, written as the call site had it.
        "ZS-MIG-12": (
            "const seen = EnumSet(Color).initEmpty();",
            ("try std.tar.pipeToFileSystem(dest, reader, .{ .mode_mode = .ignore });"),
            "std.debug.captureStackTrace(@returnAddress(), &trace);",
            "const cp = try std.unicode.utf8Decode(bytes[i..][0..len]);",
        ),
    },
    # Each of these ships an `rg` pattern that no fixture in `fires`
    # proves yet. Giving one a fixture means deleting it here, which
    # `sensitivity` insists on, so the list only shrinks.
    unproven=frozenset(
        {
            "ZS-ASSERT-09",
            "ZS-ASSERT-21",
            "ZS-BUILD-25",
            "ZS-BUILD-26",
            "ZS-BUILD-36",
            "ZS-BUILD-37",
            "ZS-COMPTIME-21",
            "ZS-MEM-04",
            "ZS-MEM-06",
            "ZS-MIG-04",
            "ZS-MIG-05",
            "ZS-MIG-08",
            "ZS-NAME-12",
            "ZS-NAME-15",
            "ZS-NAME-23",
            "ZS-NAME-26",
            "ZS-TEST-02",
            "ZS-TEST-05",
            "ZS-TEST-06",
            "ZS-TEST-07",
            "ZS-TEST-09",
            "ZS-TEST-13",
            "ZS-TEST-23",
        }
    ),
    # Measured, not judged: each of these was promoted to accuse and
    # hit the standard's own compliant examples. The reason names what
    # the span finds and what, outside the match, decides whether the
    # hit is a defect — never how many examples it hit the day someone
    # measured, which is a number `_render` already prints live two
    # fields away and nothing re-measures.
    not_decisive={
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
        "ZS-COMPTIME-10": NotDecisive(
            "comptime T: type",
            "the span finds every `comptime` parameter; how many distinct "
            "arguments its call sites pass decides, which is a count over the "
            "whole tree",
        ),
        "ZS-ERR-02": NotDecisive(
            "@panic(",
            "the span finds every `@panic(`; whether the file is a library rather "
            "than `main` or `build.zig` decides",
        ),
        "ZS-ERR-03": NotDecisive(
            ") ![",
            "the span finds every inferred error set; whether the function is "
            "`pub`, and neither `main` nor a test, decides",
        ),
        "ZS-OUT-10": NotDecisive(
            "{b64}",
            "the span finds every `{b64}`; whether a width or precision is "
            "applied to it over a slice decides, and both spellings build cleanly",
        ),
        "ZS-CONC-16": NotDecisive(
            "w.buffered()",
            "the span finds every `w.buffered()`; whether it runs before the "
            "first emit in a `drain` body decides, which is an ordering the line "
            "does not carry",
        ),
        "ZS-MEM-07": NotDecisive(
            ".allocator()",
            "the span finds every `.allocator()`; whether its receiver is a local "
            "`var` in the same frame that returns decides, which is a fact about "
            "the declaration above it",
        ),
        "ZS-MIG-11": NotDecisive(
            "root_source_file",
            "the span finds every `root_source_file`; whether it sits inside a "
            "`createModule` literal rather than an `addExecutable` one decides",
        ),
        "ZS-NAME-04": NotDecisive(
            "len_",
            "the span finds every truncated identifier; whether it is on the "
            "sanctioned abbreviation list decides",
        ),
        "ZS-PERF-12": NotDecisive(
            "*Self",
            "the span finds every `*Self` receiver; whether the helper assigns to "
            "a field the parent could apply instead decides",
        ),
        "ZS-PERF-17": NotDecisive(
            "@prefetch(",
            "the span finds every `@prefetch(`; whether its options literal "
            "spells every field out, rather than leaning on defaults, decides",
        ),
        "ZS-TEST-04": NotDecisive(
            "@as(",
            "the span finds every `@as(`; whether it wraps an `expectEqual` "
            "argument, where it is the wrapper the rule removes, decides",
        ),
        "ZS-TEST-16": NotDecisive(
            ".init(seed)",
            "the span finds every seeded PRNG; whether it is the simulation's "
            "*second* one decides, which is a count over the test body",
        ),
        "ZS-ASSERT-21": NotDecisive(
            "returns hits only from",
            "the Check asks which file a `_max` lives in, which a standalone "
            "block cannot answer",
        ),
        "ZS-BUILD-25": NotDecisive(
            ".github/ build.zig scripts/",
            "scoped to the build and release scripts, where a hit is licensed "
            "by a benchmark the pattern cannot see",
        ),
        # Polarity: this Check asserts the shape is *present*, so
        # its hits are evidence of compliance and reading them as
        # defects inverts the rule.
        "ZS-BUILD-36": NotDecisive(
            "has this block",
            "a presence assertion, and scoped to `build.zig`: the finding is a "
            "missing guard, which no hit can show",
        ),
        "ZS-TEST-13": NotDecisive(
            "is the finding",
            "the pattern finds every PRNG; the `.init(` seed argument decides, and "
            "`std.testing.random_seed` is the compliant one",
        ),
    },
    # Each rule here, and the title of the rust-style rule it restates.
    mirror=Mirror(
        "rust-style",
        pairs=(
            (
                "ZS-DATA-36",
                "Give every operation its inverse, or document why there is none",
            ),
            ("ZS-DATA-37", "Keep argument order identical across sibling functions"),
            (
                "ZS-DATA-38",
                "Replace a `bool` parameter: split the function, or name the flag",
            ),
            ("ZS-ERR-33", "Give sibling error variants a uniform shape"),
            (
                "ZS-ERR-34",
                "Absorb a special case into the general path, or give it its own type",
            ),
            ("ZS-NAME-28", "Name the two halves of a pair symmetrically"),
            ("ZS-NAME-29", "One concept, one mechanism"),
            ("ZS-NAME-30", "Keep sibling modules structurally parallel"),
            (
                "ZS-COMPTIME-16",
                (
                    "Name the capability as a trait before writing the type that "
                    "provides it"
                ),
            ),
            (
                "ZS-BUILD-22",
                "Count the encapsulation a split costs, not only what it buys",
            ),
            ("ZS-BUILD-24", "Give the directory and the crate the same name"),
            ("ZS-NAME-02", "Capitalize acronyms as ordinary English words"),
        ),
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
    conventions=conventions,
    prose=prose,
)
