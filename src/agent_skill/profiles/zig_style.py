"""zig-style: its own `[M]` rules, applied to its examples and prose."""

import re
from dataclasses import dataclass, field
from typing import override
lazy from collections.abc import Iterable, Iterator

from agent_skill.model import Skill, inside_tests
from agent_skill.profiles import Exemption, NotDecisive, Profile, register
from agent_skill.profiles.rust_style import META
from agent_skill.report import Finding, fail
from agent_skill.text import strip_comment
lazy from agent_skill.lang.zig import ZIG_VERSION
lazy from agent_skill.proc import have, run


@dataclass
class ZigStyle(Profile):
    """What zig-style's checks need to know about it."""

    name: str = "zig-style"
    prefix: str = "ZS"
    languages: tuple[str, ...] = ("zig",)
    #: `build.zig.zon` examples carry markers too, and were invisible to
    #: every tool while the rule prefix was derived from the fence tag.
    marked_languages: tuple[str, ...] = ("zon",)
    toolchain: str | None = "zig"
    #: Still the vocabulary from before `rejected` named its tool, and
    #: still the chapter names and family codes from before the shared
    #: table. Both move with the zig bump, which waits for this
    #: machine's `zig` rather than upstream.
    markers: tuple[str, ...] = ("verified", "fragment", "does-not-compile")
    tools: tuple[str, ...] = ("zig",)
    language: str = "Zig"
    follows_local: str | None = (
        "follows this machine's `zig`, and is bumped with the skill, never ahead of it"
    )
    exempt: dict[str, Exemption] = field(
        default_factory=lambda: {
            # ZS-NAME-14: "keep `self` for anonymous generic containers"
            # — a receiver typed `Self` is the case the rule permits.
            "ZS-NAME-14": lambda lines, at, _in_test: "Self" in lines[at.start - 1],
            # ZS-TEST-11: "`rg …` inside `test` blocks — every hit must
            # be on an `errdefer` line". Container-scope logging is not
            # the target.
            "ZS-TEST-11": lambda lines, at, in_test: (
                (at.start - 1) not in in_test or "errdefer" in lines[at.start - 1]
            ),
        }
    )
    #: Each snippet is the defect its rule forbids, written the way it
    #: turns up in real code. A fixture shaped to match proves the
    #: fixture, not the pattern.
    fires: dict[str, tuple[str, ...]] = field(
        default_factory=lambda: {
            # Four patterns, because one line of alternation is
            # unreadable — so four fixtures. While there was one, three
            # of the four were counted as proven by a snippet none of
            # them matched, and any of the three could have been
            # narrowed to match nothing without this noticing. Each is
            # the *old* spelling from that pattern's own row in the
            # table, written as the call site had it.
            "ZS-MIG-13": (
                "const seen = EnumSet(Color).initEmpty();",
                (
                    "try std.tar.pipeToFileSystem("
                    "dest, reader, .{ .mode_mode = .ignore });"
                ),
                "std.debug.captureStackTrace(@returnAddress(), &trace);",
                "const cp = try std.unicode.utf8Decode(bytes[i..][0..len]);",
            ),
        }
    )
    #: Measured, not judged: each of these was promoted to accuse and
    #: hit the standard's own compliant examples. The reason names what
    #: the span finds and what, outside the match, decides whether the
    #: hit is a defect — never how many examples it hit the day someone
    #: measured, which is a number `_render` already prints live two
    #: fields away and nothing re-measures.
    not_decisive: dict[str, NotDecisive] = field(
        default_factory=lambda: {
            "ZS-INTEROP-09": NotDecisive(
                "c_int",
                "the span finds every C type; whether the hit is inside the "
                "designated boundary module decides, and a line does not say which "
                "file it is in",
            ),
            "ZS-INTEROP-10": NotDecisive(
                "[*c]",
                "the span finds every `[*c]`; whether it is a parameter of an "
                "`export fn` or a `callconv(.c)` function — the one place it is "
                "allowed — decides",
            ),
            "ZS-COMPTIME-13": NotDecisive(
                "comptime T: type",
                "the span finds every `comptime` parameter; how many distinct "
                "arguments its call sites pass decides, which is a count over the "
                "whole tree",
            ),
            "ZS-ERR-03": NotDecisive(
                "@panic(",
                "the span finds every `@panic(`; whether the file is a library rather "
                "than `main` or `build.zig` decides",
            ),
            "ZS-ERR-04": NotDecisive(
                ") ![",
                "the span finds every inferred error set; whether the function is "
                "`pub`, and neither `main` nor a test, decides",
            ),
            "ZS-OUT-10": NotDecisive(
                "{b64}",
                "the span finds every `{b64}`; whether a width or precision is "
                "applied to it over a slice decides, and both spellings build cleanly",
            ),
            "ZS-CONC-18": NotDecisive(
                "w.buffered()",
                "the span finds every `w.buffered()`; whether it runs before the "
                "first emit in a `drain` body decides, which is an ordering the line "
                "does not carry",
            ),
            "ZS-MEM-08": NotDecisive(
                ".allocator()",
                "the span finds every `.allocator()`; whether its receiver is a local "
                "`var` in the same frame that returns decides, which is a fact about "
                "the declaration above it",
            ),
            "ZS-MIG-12": NotDecisive(
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
            "ZS-PERF-18": NotDecisive(
                "@prefetch(",
                "the span finds every `@prefetch(`; whether its options literal "
                "spells every field out, rather than leaning on defaults, decides",
            ),
            "ZS-TEST-06": NotDecisive(
                "@as(",
                "the span finds every `@as(`; whether it wraps an `expectEqual` "
                "argument, where it is the wrapper the rule removes, decides",
            ),
            "ZS-TEST-18": NotDecisive(
                ".init(seed)",
                "the span finds every seeded PRNG; whether it is the simulation's "
                "*second* one decides, which is a count over the test body",
            ),
            "ZS-BUILD-19": NotDecisive(
                "returns hits only from that file",
                "the Check asks which file a `_max` lives in, which a standalone "
                "block cannot answer",
            ),
            "ZS-MIG-04": NotDecisive(
                "every hit must read",
                "the pattern finds `format` methods; the signature decides",
            ),
            "ZS-BUILD-27": NotDecisive(
                ".github/ build.zig scripts/",
                "scoped to the build and release scripts, where a hit is licensed "
                "by a benchmark the pattern cannot see",
            ),
            # Polarity: this Check asserts the shape is *present*, so
            # its hits are evidence of compliance and reading them as
            # defects inverts the rule.
            "ZS-BUILD-39": NotDecisive(
                "has this block",
                "a presence assertion, and scoped to `build.zig`: the finding is a "
                "missing guard, which no hit can show",
            ),
            "ZS-TEST-15": NotDecisive(
                "is the finding",
                "the pattern finds every PRNG; the `.init(` seed argument decides, and "
                "`std.testing.random_seed` is the compliant one",
            ),
        }
    )
    #: One probe per `zig` row in the chapters' `Decided by tools`
    #: tables, each compiled on 0.17.0 and rejected with the row's
    #: error (`research/zig-rows.md` in the refresh-zig change).
    probes: dict[str, str] = field(
        default_factory=lambda: {
            "unused local constant": (
                "export fn probe() void {\n    const x: u32 = 1;\n}\n"
            ),
            "unused local variable": (
                "export fn probe() void {\n    var x: u32 = 1;\n}\n"
            ),
            "unused function parameter": ("export fn probe(x: u32) void {}\n"),
            "unused capture": (
                "export fn probe(o: ?*u32) void {\n    if (o) |p| {}\n}\n"
            ),
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
                "fn g() u32 {\n"
                "    return 1;\n"
                "}\n"
                "export fn probe() void {\n"
                "    g();\n"
                "}\n"
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
            "redundant comptime keyword in already comptime scope": (
                'const std = @import("std");\n'
                "const n = comptime std.math.log2_int(u32, 1024);\n"
                "comptime {\n"
                "    _ = n;\n"
                "}\n"
            ),
        }
    )

    @override
    def pin(self) -> str | None:
        """The compiler release the examples are verified against."""
        return ZIG_VERSION

    @override
    def running_version(self) -> str | None:
        """What `zig version` reports here, or None if it cannot say."""
        if not have("zig"):
            return None
        answered = run(["zig", "version"], timeout=30)
        return answered.out.strip() if answered.ok else None

    @override
    def conventions(self, skill: Skill) -> Iterable[Finding]:
        """zig-style's own rules, applied to its own examples."""
        for b in skill.advice("zig"):
            lines = b.lines
            for j, raw in enumerate(lines):
                where = f"{b.file}:{b.at(j)} [{b.rule}]"
                code = strip_comment(raw)

                # ZS-ERR-08 [M] — every `catch {}` or
                # `catch unreachable` carries a comment. The comment may
                # sit on the line above.
                justified = "//" in raw or any(
                    ln.strip().startswith("//") for ln in lines[max(0, j - 3) : j]
                )
                if re.search(r"catch\s*(\{\s*\}|unreachable)", code) and not justified:
                    yield fail(
                        "`catch` swallows without the comment ZS-ERR-08 requires", where
                    )

                # ZS-ERR-30 [M] — "every hit is a defect, including
                # inside `comptime` blocks and `const` initializers"
                if ".?" in code and b.rule != "ZS-ERR-30":
                    yield fail(
                        "`.?` unwrap; ZS-ERR-30 asks for `orelse`, a capture, or "
                        "`orelse unreachable` with the proof beside it",
                        where,
                    )

                # ZS-TEST-06 [M] — "drop the `@as` wrapper": peer
                # resolution already handles a literal on the other side
                if re.search(r"expectEqual\(@as\([a-zA-Z0-9_]+, [^()]*\), ", code):
                    yield fail(
                        "`@as` wrapper inside `expectEqual`; peer resolution already "
                        "handles it (ZS-TEST-06)",
                        where,
                    )

                if raw.lstrip().startswith("///") and META.search(raw):
                    yield fail(
                        "doc comment discusses the example rather than the API", where
                    )

            # ZS-NAME-19 — "Order imports `@This()` → `builtin` → `std`
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
                    '`@import("builtin")` below `@import("std")` (ZS-NAME-19)',
                    f"{b.file}:{b.at(imports['builtin'])} [{b.rule}]",
                )

    @override
    def inside_tests(self, body: str) -> set[int]:
        """Body-line indices inside a `test` block, by brace depth."""
        return inside_tests(body)

    @override
    def prose(self, skill: Skill) -> Iterable[Finding]:
        """ZS-ERR-30 forbids `.?` outright.

        Prose naming it is therefore either hunting it (inside a
        `**Check:**`) or is the rule that bans it. Anything else is the
        standard recommending a spelling it forbids, which is how three
        passages survived the rule being tightened. Scoped per rule and
        per Check block, because both wrap.
        """
        span = re.compile(r"`[^`\n]*\.\?[^`\n]*`")
        for chapter in skill.chapters:
            for i, line, rid, in_check in _prose_lines(chapter.text, skill.prefix):
                if rid == "ZS-ERR-30" or in_check or "ZS-ERR-30" in line:
                    continue
                if span.search(line):
                    yield fail(
                        "prose names `.?` outside a **Check:** and outside ZS-ERR-30",
                        f"{chapter.name}:{i} [{rid}]",
                    )


def _prose_lines(text: str, prefix: str) -> Iterator[tuple[int, str, str, bool]]:
    """Each unfenced prose line, with the rule and Check it sits in.

    Yields (lineno, line, owning rule, inside-a-Check).
    """
    rid, in_check, fenced = "?", False, False
    head = re.compile(rf"^### ({prefix}-[A-Z]+-\d+[a-z]?) \[")
    for i, line in enumerate(text.split("\n"), 1):
        if line.startswith("```"):
            fenced = not fenced
            in_check = False
            continue
        if fenced:
            continue
        if m := head.match(line):
            rid, in_check = str(m.group(1)), False
        elif line.startswith("**Check:"):
            in_check = True
        elif line.startswith("**") or not line.strip():
            in_check = False
        yield i, line, rid, in_check


register(ZigStyle())
