"""zig-style's examples, one standalone file each.

The rust side compiles its blocks as modules of one crate; Zig has no
such container, so each block becomes a standalone file — which is also
the stronger claim, and the one `// verified` should mean: this text
compiles as written.
"""

import re
from collections import Counter
from pathlib import Path
lazy from collections.abc import Iterable

from agent_skill.lang import Extraction, Language, Unit, inconclusive, timed_out
from agent_skill.proc import have, run
from agent_skill.report import Finding, Level, declare, fail, note
lazy from agent_skill.model import Skill

# The branches of `toolchain` and of `mutation` Zig's steps report
# through.
BUILD_TIMEOUT = declare("toolchain", "zig_build_timeout", Level.FAIL)
BUILD = declare("toolchain", "zig_build", Level.FAIL)
TEST_TIMEOUT = declare("toolchain", "zig_test_timeout", Level.FAIL)
TEST = declare("toolchain", "zig_test", Level.FAIL)
FMT_TIMEOUT = declare("toolchain", "zig_fmt_timeout", Level.FAIL)
FMT = declare("toolchain", "zig_fmt", Level.FAIL)
FMT_UNREAD = declare("toolchain", "zig_fmt_unread", Level.FAIL)
HUNG = declare("mutation", "zig_inconclusive", Level.NOTE)
SURVIVOR = declare("mutation", "zig_survivor", Level.NOTE)


def inside_tests(body: str) -> set[int]:
    """Indices of the lines inside a `test` block, by brace depth.

    Several rules are scoped to test bodies ("no `std.debug.print` in a
    test"), and a `const log = std.log.scoped(...)` at container scope
    is not what they hunt. Container scope is order-independent, so a
    `test` may sit anywhere.
    """
    inside: set[int] = set()
    depth, active = 0, False
    for i, line in enumerate(body.split("\n")):
        code = LANGUAGE.uncommented(line)
        if not active and re.match(r"^\s*test\b", code):
            active, depth = True, 0
        if active:
            depth += code.count("{") - code.count("}")
            inside.add(i)
            if depth <= 0 and "}" in code:
                active = False
    return inside


LANGUAGE = Language("zig", suffix=".zig", tests=inside_tests)

_EXTERN_FN = re.compile(r'\bextern\s+(?:"[^"]*"\s+)?fn\b')


def needs_c_object(source: str) -> bool:
    """Does this block declare a symbol only a C object can supply?

    `extern struct` and `extern union` are layout qualifiers and link
    fine. Testing for the substring `extern ` excluded two blocks whose
    four tests pass.
    """
    return bool(_EXTERN_FN.search(LANGUAGE.code(source)))


#: The compiler `zig-style` is verified against. It follows this
#: machine's `zig` rather than upstream's newest release, so `pins`
#: compares it with `zig version` only: the skill moves when the
#: compiler here does.
ZIG_VERSION = "0.17.0"

#: What a block names that only libc supplies. macOS links libc into
#: everything and Linux into nothing, so a block calling `std.c`
#: verified on one and failed on the other with the error interop.md
#: quotes — "dependency on libc must be explicitly specified in the
#: build command". Such a block is verified with libc linked; every
#: other block without, so `// verified` still proves it needs none.
_LIBC = re.compile(r'\bstd\.c\b|\bextern\s+"c"|c_allocator\b|@cImport\b')


def libc(source: str) -> list[str]:
    """`-lc` for a block that names something only libc supplies."""
    return ["-lc"] if _LIBC.search(LANGUAGE.code(source)) else []


#: A top-level declaration as a block writes it, at column zero: its
#: name, plain or `@"quoted"`.
_DECL = re.compile(
    r'^(?:pub\s+)?(?:export\s+|extern\s+(?:"[^"]*"\s+)?)?(?:inline\s+|noinline\s+)?'
    r'(?:threadlocal\s+)?(?:fn|const|var)\s+(@"[^"]+"|[A-Za-z_]\w*)',
    re.MULTILINE,
)


def force_analysis(body: str) -> str:
    """A file-scope `comptime` block naming each top-level declaration.

    `zig build-obj` analyses such a block, so forcing analysis costs a
    tenth of a second per block instead of a link and a launch. Without
    it Zig never analyses the body of a function nobody calls, and a
    block with a type error in it reports success.

    Each declaration is named rather than listed through `@typeInfo`:
    the type-info decl list holds only `pub` declarations, so a private
    function stayed unanalysed, and it is laid out differently in each
    release. Naming keeps every declaration's visibility as written.
    """
    names = _DECL.findall(body)
    if not names:
        return ""
    refs = "".join(f"    _ = &{name};\n" for name in names)
    return f"\ncomptime {{\n{refs}}}\n"


#: A statement worth deleting: not a declaration, a brace, or a discard.
_SKIP = ("//", "const ", "var ", "pub const", "pub var", "}", "_ = ")

#: A defensive assertion earns its place on the path the tests do *not*
#: reach — deleting one and staying green is what it is for, not a gap.
_ASSERT = re.compile(r"^(std\.debug\.)?assert\s*\(")


class Zig:
    """The `zig` toolchain: one standalone file per verified block."""

    name = "zig"
    tool = "zig"
    language = LANGUAGE

    def missing(self) -> list[str]:
        """`zig` itself, when it is not on PATH."""
        return [] if have(self.tool) else [f"`{self.tool}` is not on PATH"]

    def extract(self, skill: Skill, out: Path) -> Extraction:
        """Write each verified block as a file that forces analysis."""
        out = out.resolve()
        out.mkdir(parents=True, exist_ok=True)
        for stale in out.glob("*.zig"):
            stale.unlink()

        ex = Extraction(out, skill=skill.name)
        seen: Counter[str] = Counter()
        for b in skill.blocks("zig", verified=True):
            stem = Path(b.file).stem.replace("-", "_")
            name = f"{stem}_{seen[stem]:03d}.zig"
            seen[stem] += 1
            path = out / name
            path.write_text(b.body.rstrip("\n") + "\n" + force_analysis(b.body))
            ex.units.append(Unit(path, b.file, b.line, b.rule, skill.name))
        return ex

    def verify(self, ex: Extraction) -> Iterable[Finding]:
        """Analyse each block, run its tests, and check `zig fmt`."""
        for unit in ex.units:
            source = unit.path.read_text()
            # semantic analysis of every declaration, without linking or
            # running
            r = run(
                ["zig", "build-obj", str(unit.path), "-fno-emit-bin", *libc(source)],
                cwd=ex.root,
                timeout=180,
            )
            if r.timed_out:
                yield timed_out("build-obj", 180, unit.where, BUILD_TIMEOUT)
                continue
            if not r.ok:
                first = next(
                    (ln for ln in r.err.split("\n") if ": error:" in ln), r.err[:100]
                )
                yield fail(
                    first.split(f"{unit.path.name}:")[-1].strip()[:96],
                    unit.where,
                    BUILD,
                )
                continue

            # A block that ships a `test` gets its assertions executed —
            # unless it declares an `extern fn`, which needs a C object
            # to link against. `extern struct` is a layout qualifier and
            # links fine; testing for the substring `extern ` excluded
            # two blocks whose four tests pass.
            if _has_test(source) and not needs_c_object(source):
                t = run(
                    ["zig", "test", str(unit.path), *libc(source)],
                    cwd=ex.root,
                    timeout=180,
                )
                if t.timed_out:
                    yield timed_out("the test run", 180, unit.where, TEST_TIMEOUT)
                elif not t.ok:
                    first = next(
                        (
                            ln
                            for ln in t.err.split("\n")
                            if ": error:" in ln or "FAIL" in ln
                        ),
                        t.err[:100],
                    )
                    yield fail(f"test run: {first.strip()[:84]}", unit.where, TEST)

        # One invocation for the whole directory. Spawning `zig fmt` per
        # block cost 215 process launches for a check that names each
        # file anyway.
        r = run(["zig", "fmt", "--check", str(ex.root)], cwd=ex.root, timeout=180)
        if r.timed_out:
            yield timed_out("`zig fmt --check`", 180, ex.where, FMT_TIMEOUT)
            return
        by_file = {u.path.name: u for u in ex.units}
        named = [line.strip() for line in r.out.splitlines() if line.strip()]
        for line in named:
            unit = by_file.get(Path(line).name)
            where, which = (unit.where, "") if unit else (ex.where, f": {line}")
            yield fail(f"not `zig fmt` clean{which}", where, FMT)
        if not r.ok and not named:
            said = (r.err or r.out).strip()[:100] or "nothing"
            yield fail(
                f"`zig fmt --check` exited {r.rc}, naming no file: {said}",
                ex.where,
                FMT_UNREAD,
            )

    def mutate(self, ex: Extraction) -> Iterable[Finding]:
        """Statements a shipped test does not pin.

        A survivor is a question, not a verdict: an illustrative
        example's test pins the case its name describes, and a guard
        clause outside that case is expected to survive. The defect this
        catches — a test that cannot fail on its *own* stated case —
        shows up as a survivor inside the very function the test is
        named for. So survivors are notes.
        """
        for unit in ex.units:
            text = unit.path.read_text()
            if not _has_test(text) or needs_c_object(text):
                continue
            base = run(
                ["zig", "test", str(unit.path), *libc(text)], cwd=ex.root, timeout=60
            )
            if base.timed_out or not base.ok:
                continue  # not runnable here; verify() reports why

            lines = text.split("\n")
            in_test = inside_tests(text)
            for i, line in enumerate(lines):
                s = line.strip()
                if i in in_test or not s.endswith(";") or s.startswith(_SKIP):
                    continue
                if _ASSERT.match(s):
                    continue
                unit.path.write_text("\n".join(lines[:i] + lines[i + 1 :]))
                try:
                    r = run(
                        ["zig", "test", str(unit.path), *libc(text)],
                        cwd=ex.root,
                        timeout=15,
                    )
                    where = unit.where_at(i)
                    if r.timed_out:
                        yield inconclusive(s, where, HUNG)
                    elif r.ok:
                        yield note(
                            f"`{s[:52]}` can be deleted and every test still passes",
                            where,
                            SURVIVOR,
                        )
                finally:
                    unit.path.write_text(text)


def _has_test(source: str) -> bool:
    return "\ntest " in source or source.startswith("test ")


ZIG = Zig()
