"""zig-style: its own `[M]` rules, applied to its own examples and prose."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field

from ..model import inside_tests
from ..report import Finding, fail
from ..text import strip_comment
from . import NotDecisive, Profile, register
from .rust_style import META


@dataclass
class ZigStyle(Profile):
    name: str = "zig-style"
    prefix: str = "ZS"
    languages: tuple[str, ...] = ("zig",)
    #: `build.zig.zon` examples carry markers too, and were invisible to every
    #: tool while the rule prefix was derived from the fence tag.
    marked_languages: tuple[str, ...] = ("zon",)
    toolchain: str | None = "zig"
    exempt: dict = field(
        default_factory=lambda: {
            # ZS-NAME-14: "keep `self` for anonymous generic containers" — a
            # receiver typed `Self` is the case the rule permits.
            "ZS-NAME-14": lambda lines, at, in_test: "Self" in lines[at.start - 1],
            # ZS-TEST-11: "`rg …` inside `test` blocks — every hit must be on
            # an `errdefer` line". Container-scope logging is not the target.
            "ZS-TEST-11": lambda lines, at, in_test: (
                (at.start - 1) not in in_test or "errdefer" in lines[at.start - 1]
            ),
        }
    )
    #: Each snippet is the defect its rule forbids, written the way it turns up
    #: in real code. A fixture shaped to match proves the fixture, not the pattern.
    fires: dict = field(
        default_factory=lambda: {
            # Four patterns, because one line of alternation is unreadable — so
            # four fixtures. While there was one, three of the four were counted
            # as proven by a snippet none of them matched, and any of the three
            # could have been narrowed to match nothing without this noticing.
            # Each is the *old* spelling from that pattern's own row in the
            # table, written as the call site had it.
            "ZS-MIG-13": (
                "const seen = EnumSet(Color).initEmpty();",
                "try std.tar.pipeToFileSystem(dest, reader, .{ .mode_mode = .ignore });",
                "std.debug.captureStackTrace(@returnAddress(), &trace);",
                "const cp = try std.unicode.utf8Decode(bytes[i..][0..len]);",
            ),
        }
    )
    #: Measured, not judged: each of these was promoted to accuse and hit the
    #: standard's own compliant examples. The reason names what the span finds
    #: and what, outside the match, decides whether the hit is a defect — never
    #: how many examples it hit the day someone measured, which is a number
    #: `_render` already prints live two fields away and nothing re-measures.
    not_decisive: dict = field(
        default_factory=lambda: {
            "ZS-CAPI-09": NotDecisive(
                "c_int",
                "the span finds every C type; whether the hit is inside the designated boundary "
                "module decides, and a line does not say which file it is in",
            ),
            "ZS-CAPI-10": NotDecisive(
                "[*c]",
                "the span finds every `[*c]`; whether it is a parameter of an `export fn` or a "
                "`callconv(.c)` function — the one place it is allowed — decides",
            ),
            "ZS-CT-13": NotDecisive(
                "comptime T: type",
                "the span finds every `comptime` parameter; how many distinct arguments its call "
                "sites pass decides, which is a count over the whole tree",
            ),
            "ZS-ERR-03": NotDecisive(
                "@panic(",
                "the span finds every `@panic(`; whether the file is a library rather than `main` "
                "or `build.zig` decides",
            ),
            "ZS-ERR-04": NotDecisive(
                ") ![",
                "the span finds every inferred error set; whether the function is `pub`, and "
                "neither `main` nor a test, decides",
            ),
            "ZS-FMT-10": NotDecisive(
                "{b64}",
                "the span finds every `{b64}`; whether a width or precision is applied to it over "
                "a slice decides, and both spellings build cleanly",
            ),
            "ZS-IO-18": NotDecisive(
                "w.buffered()",
                "the span finds every `w.buffered()`; whether it runs before the first emit in a "
                "`drain` body decides, which is an ordering the line does not carry",
            ),
            "ZS-MEM-08": NotDecisive(
                ".allocator()",
                "the span finds every `.allocator()`; whether its receiver is a local `var` in the "
                "same frame that returns decides, which is a fact about the declaration above it",
            ),
            "ZS-MIG-12": NotDecisive(
                "root_source_file",
                "the span finds every `root_source_file`; whether it sits inside a `createModule` "
                "literal rather than an `addExecutable` one decides",
            ),
            "ZS-NAME-04": NotDecisive(
                "len_",
                "the span finds every truncated identifier; whether it is on the sanctioned "
                "abbreviation list decides",
            ),
            "ZS-PERF-12": NotDecisive(
                "*Self",
                "the span finds every `*Self` receiver; whether the helper assigns to a field the "
                "parent could apply instead decides",
            ),
            "ZS-PERF-18": NotDecisive(
                "@prefetch(",
                "the span finds every `@prefetch(`; whether its options literal spells every field "
                "out, rather than leaning on defaults, decides",
            ),
            "ZS-TEST-06": NotDecisive(
                "@as(",
                "the span finds every `@as(`; whether it wraps an `expectEqual` argument, where it "
                "is the wrapper the rule removes, decides",
            ),
            "ZS-TEST-18": NotDecisive(
                ".init(seed)",
                "the span finds every seeded PRNG; whether it is the simulation's *second* one "
                "decides, which is a count over the test body",
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
            # Polarity: this Check asserts the shape is *present*, so its hits are
            # evidence of compliance and reading them as defects inverts the rule.
            "ZS-BUILD-40": NotDecisive(
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

    def conventions(self, skill) -> Iterable[Finding]:
        for b in skill.advice("zig"):
            lines = b.lines
            for j, raw in enumerate(lines):
                where = f"{b.file}:{b.at(j)} [{b.rule}]"
                code = strip_comment(raw)

                # ZS-ERR-08 [M] — every `catch {}` or `catch unreachable` carries
                # a comment. The comment may sit on the line above.
                justified = "//" in raw or any(
                    ln.strip().startswith("//") for ln in lines[max(0, j - 3) : j]
                )
                if re.search(r"catch\s*(\{\s*\}|unreachable)", code) and not justified:
                    yield fail("`catch` swallows without the comment ZS-ERR-08 requires", where)

                # ZS-ERR-30 [M] — "every hit is a defect, including inside
                # `comptime` blocks and `const` initializers"
                if ".?" in code and b.rule != "ZS-ERR-30":
                    yield fail(
                        "`.?` unwrap; ZS-ERR-30 asks for `orelse`, a capture, or "
                        "`orelse unreachable` with the proof beside it",
                        where,
                    )

                # ZS-TEST-06 [M] — "drop the `@as` wrapper": peer resolution
                # already handles a literal on the other side
                if re.search(r"expectEqual\(@as\([a-zA-Z0-9_]+, [^()]*\), ", code):
                    yield fail(
                        "`@as` wrapper inside `expectEqual`; peer resolution already "
                        "handles it (ZS-TEST-06)",
                        where,
                    )

                if raw.lstrip().startswith("///") and META.search(raw):
                    yield fail("doc comment discusses the example rather than the API", where)

            # ZS-NAME-19 — "Order imports `@This()` → `builtin` → `std` → local".
            # The rule is [S], but a suggestion the library declines to follow in
            # its own examples is not a suggestion.
            imports = {
                kind: i
                for i in range(len(lines) - 1, -1, -1)
                for kind in ("builtin", "std")
                if f'@import("{kind}")' in lines[i]
            }
            if "builtin" in imports and "std" in imports and imports["builtin"] > imports["std"]:
                yield fail(
                    '`@import("builtin")` below `@import("std")` (ZS-NAME-19)',
                    f"{b.file}:{b.at(imports['builtin'])} [{b.rule}]",
                )

    def inside_tests(self, body: str) -> set[int]:
        return inside_tests(body)

    def prose(self, skill) -> Iterable[Finding]:
        """ZS-ERR-30 forbids `.?` outright.

        Prose naming it is therefore either hunting it (inside a `**Check:**`) or
        is the rule that bans it. Anything else is the standard recommending a
        spelling it forbids, which is how three passages survived the rule being
        tightened. Scoped per rule and per Check block, because both wrap.
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


def _prose_lines(text: str, prefix: str):
    """(lineno, line, owning rule, inside-a-Check) for unfenced prose."""
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
            rid, in_check = m.group(1), False
        elif line.startswith("**Check:"):
            in_check = True
        elif line.startswith("**") or not line.strip():
            in_check = False
        yield i, line, rid, in_check


register(ZigStyle())
