"""zig-style's examples, one standalone file each.

Zig has no container to compile blocks in, so each block becomes a
standalone file — which is also the stronger claim, and the one
`// verified` should mean: this text compiles as written.

And everything else the harness knows about Zig: that a compiler row is
proved by a probe the compiler rejects, that the pin follows this
machine's `zig`, and that a shipped `build.zig` is `zig fmt` clean and
parses.
"""

import re
import tempfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
lazy from collections.abc import Callable, Iterable, Iterator, Mapping

from agent_skill.ids import Pin
from agent_skill.lang import Extraction, Language, Step, Unit, extracted
from agent_skill.proc import have, run
from agent_skill.report import Finding, Level, declare, fail, unrun
lazy from agent_skill.checks.citations import Row, rows_of
lazy from agent_skill.ids import Location
lazy from agent_skill.model import Block, Skill
lazy from agent_skill.proc import Ran

# The branches of `citations` a compiler row reports through.
ROWS_ABSENT = declare("citations", "zig_absent", Level.UNRUN)
NO_PROBE = declare("citations", "zig_no_probe", Level.FAIL)
PROBE_COMPILES = declare("citations", "zig_probe_compiles", Level.FAIL)
PROBE_OTHER = declare("citations", "zig_probe_other", Level.FAIL)
PROBE_NO_ROW = declare("citations", "zig_probe_no_row", Level.FAIL)

# The branches of `pins` a pin that follows this machine reports
# through.
LOCAL_SILENT = declare("pins", "local_silent", Level.UNRUN)
LOCAL_MOVED = declare("pins", "local_moved", Level.FAIL)

# The branches of `assets` a shipped zig file reports through.
ASSET_ABSENT = declare("assets", "zig_absent", Level.UNRUN)
ASSET_FMT = declare("assets", "zig_fmt", Level.FAIL)
ASSET_AST = declare("assets", "zig_ast", Level.FAIL)


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


#: A mutant deletes no binding or discard, which Zig refuses to compile
#: unused or missing, and no assertion: a defensive assertion earns its
#: place on the path the tests do *not* reach, and deleting one and
#: staying green is what it is for, not a gap.
LANGUAGE = Language(
    "zig",
    suffix=".zig",
    tests=inside_tests,
    kept=(
        *("const ", "var ", "pub const", "pub var", "}", "_ = "),
        *("assert(", "std.debug.assert("),
    ),
)

_EXTERN_FN = re.compile(r'\bextern\s+(?:"[^"]*"\s+)?fn\b')


def needs_c_object(source: str) -> bool:
    """Does this block declare a symbol only a C object can supply?

    `extern struct` and `extern union` are layout qualifiers and link
    fine. Testing for the substring `extern ` excluded two blocks whose
    four tests pass.
    """
    return bool(_EXTERN_FN.search(LANGUAGE.code(source)))


@dataclass(frozen=True, slots=True)
class ZigBuild:
    """How a skill's zig examples are built: the compiler, and why that.

    The pin follows this machine's `zig` rather than upstream's newest
    release, so `pins` compares it with `zig version` only: the skill
    moves when the compiler here does.
    """

    compiler: Pin
    #: Why the pin follows the local compiler, rather than upstream's
    #: newest release.
    follows_local: str

    @property
    def pin(self) -> Pin:
        """The compiler release the examples are verified against."""
        return self.compiler


#: A name a probe can look up: a declaration reached from `std`.
STD_PATH = re.compile(r"std(?:\.[A-Za-z_]\w*)+")

ZIG_STYLE = ZigBuild(
    Pin.parse("zig==0.17.0"),
    follows_local=(
        "follows this machine's `zig`, and is bumped with the skill, never ahead of it"
    ),
)

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


#: The line between a block and what the harness adds after it. A
#: comment, so `zig fmt` leaves it as it is, and `restore` cuts there.
SENTINEL = "// The block ends above; the harness forces its analysis below."


class Zig:
    """The `zig` toolchain: one standalone file per verified block."""

    name = "zig"
    tool = "zig"
    language: Language = LANGUAGE
    needs: tuple[str, ...] = ("zig",)
    #: A compile error has one level: the build stops.
    rows: Mapping[str, frozenset[str]] = MappingProxyType({"zig": frozenset({"error"})})
    #: Its rows are the compiler's own errors, which no setting turns
    #: off.
    compilers: frozenset[str] = frozenset({"zig"})
    cites_with: tuple[str, ...] = ("zig",)
    pins_with: tuple[str, ...] = ("zig",)
    asset_suffixes: tuple[str, ...] = (".zig", ".zon")
    assets_with: tuple[str, ...] = ("zig",)
    #: A test that hangs is deleted loop progress; a passing one takes a
    #: second.
    mutant_timeout: float = 15
    outside: re.Pattern[str] | None = None

    def missing(self) -> list[str]:
        """`zig` itself, when it is not on PATH."""
        return [f"`{tool}` is not on PATH" for tool in self.needs if not have(tool)]

    def extract(self, skill: Skill, out: Path) -> Extraction:
        """Write each verified block as a file that forces analysis.

        The block as written, then `SENTINEL`, then the analysis it
        forces: after the body, so the file's line `i` is the body's.
        """
        out = out.resolve()
        out.mkdir(parents=True, exist_ok=True)
        for stale in out.glob(f"*{LANGUAGE.suffix}"):
            stale.unlink()

        ex = Extraction(out, skill)
        seen: Counter[str] = Counter()
        for b in extracted(skill, LANGUAGE):
            stem = Path(b.file).stem.replace("-", "_")
            path = out / f"{stem}_{seen[stem]:03d}{LANGUAGE.suffix}"
            seen[stem] += 1
            path.write_text(f"{b.body}\n{SENTINEL}\n{force_analysis(b.body)}")
            ex.units.append(Unit(path, b))
        return ex

    def restore(self, ex: Extraction) -> dict[Block, str]:
        """Each block's file up to `SENTINEL`.

        The blank line before it is the extractor's; one `zig fmt` drops
        is not taken from the block.
        """
        restored: dict[Block, str] = {}
        for u in ex.units:
            head, _, _ = u.path.read_text().rpartition(f"\n{SENTINEL}\n")
            restored[u.block] = head if head.endswith("\n") else f"{head}\n"
        return restored

    def steps(self, ex: Extraction) -> Iterator[Step]:
        """Analyse each block, then run the tests it ships."""
        for unit in ex.units:
            # semantic analysis of every declaration, without linking or
            # running
            yield Step(
                "build-obj",
                (
                    "zig",
                    "build-obj",
                    str(unit.path),
                    "-fno-emit-bin",
                    *libc(unit.block.body),
                ),
                ex.root,
                180,
                unit=unit,
                diagnostics=True,
            )
            if LANGUAGE.tests(unit.block.body) and (t := self.tests(ex, unit)):
                yield t

    def formatter(self, ex: Extraction) -> Step:
        """`zig fmt`, over the whole directory.

        One invocation: spawning it per block cost 215 process launches
        for a step that names each file anyway.
        """
        return Step("zig fmt", ("zig", "fmt", str(ex.root)), ex.root, 180)

    def tests(self, ex: Extraction, unit: Unit) -> Step | None:
        """`zig test` over the unit's file; None when it cannot link.

        A block that declares an `extern fn` needs a C object to link
        against. `extern struct` is a layout qualifier and links fine;
        testing for the substring `extern ` excluded two blocks whose
        four tests pass.
        """
        if needs_c_object(unit.block.body):
            return None
        return Step(
            "tests",
            ("zig", "test", str(unit.path), *libc(unit.block.body)),
            ex.root,
            180,
            unit=unit,
            said=_failed_test,
        )

    def cite(self, skill: Skill) -> Iterator[Finding]:
        """The compiler rows, each against the probe that proves it."""
        # Asked before looking for rows, as Rust's are.
        if not have("zig"):
            yield unrun(
                "`zig` is not on PATH, so no compiler row was proved",
                skill.at(),
                ROWS_ABSENT,
            )
            return
        rows = [(where, row) for where, row in rows_of(skill) if row.tool in self.rows]
        yield from zig_rows(rows, skill.profile.probes, compile_errors, skill.at())

    def pins(self, skill: Skill) -> Iterator[Finding]:
        """The compiler pin, against the `zig` this machine runs.

        Compared with the running version only. Upstream releasing
        something newer is not a finding — the standard is verified
        against what runs here, and that has not changed. The local
        toolchain moving past the pin is: the claim that the examples
        were verified on this version has just stopped being true.
        """
        build = skill.profile.toolchain
        if not isinstance(build, ZigBuild):
            return
        where, name = skill.at(), skill.profile.name
        pinned, running = str(build.compiler.version), _running()
        if not running:
            yield unrun(
                "could not ask the local toolchain which version runs, "
                f"so `{pinned}` was not compared",
                where,
                LOCAL_SILENT,
            )
        elif running != pinned:
            moved = f"follows this machine's toolchain, which is now {running}"
            yield fail(
                f"{name} is pinned to {pinned} and {moved} — the cue to bump it",
                where,
                LOCAL_MOVED,
            )

    def asset(self, path: Path, where: Location) -> Iterator[Finding]:
        """A zig asset is `zig fmt` clean and passes `zig ast-check`."""
        if not have("zig"):
            # Silence is not success, and a `NOTE` is silence: it does
            # not withhold the pass. A shipped `build.zig` that nothing
            # parsed is exactly the case this check exists for.
            yield unrun(
                "`zig` is not on PATH, so nothing parsed this file",
                where,
                ASSET_ABSENT,
            )
            return
        if not run(["zig", "fmt", "--check", str(path)], timeout=60).ok:
            yield fail("not `zig fmt` clean", where, ASSET_FMT)
        r = run(["zig", "ast-check", str(path)], timeout=60)
        if not r.ok:
            first = next(
                (ln for ln in r.err.split("\n") if ": error:" in ln), r.err[:80]
            )
            # the absolute path is noise; the line and the message are
            # not
            yield fail(first.split(f"{path}:")[-1].strip()[:84], where, ASSET_AST)

    def probe(self, skill: Skill, spelling: str, out: Path) -> Step | None:  # noqa: ARG002 — one compiler for every skill
        """Compile a reference to the name: it builds while it is there.

        `std.mem.copy` becomes `_ = std.mem.copy;` in a `comptime`
        block, analysed and not linked. Only a path from `std` is looked
        up: a builtin, a keyword or a call is not a declaration.
        """
        name = spelling.removesuffix("()")
        if not STD_PATH.fullmatch(name):
            return None
        out.mkdir(parents=True, exist_ok=True)
        path = out / f"probe_{len(list(out.glob('probe_*.zig'))):03d}.zig"
        path.write_text(
            f'const std = @import("std");\n\ncomptime {{\n    _ = {name};\n}}\n'
        )
        cmd = ("zig", "build-obj", "-fno-emit-bin", path.name)
        return Step("probe", cmd, out, 120)

    def excused(self, skill: Skill) -> Mapping[str, str]:  # noqa: ARG002 — no example is excused
        """Nothing: each example builds under what the skill ships."""
        return dict[str, str]()

    def configured(self, skill: Skill) -> dict[tuple[str, str], str]:  # noqa: ARG002 — the compiler's errors are its rows
        """Nothing: a compiler ships no configuration to set it in."""
        return {}


def _failed_test(ran: Ran) -> str:
    """What a failed `zig test` said first: an error, or a test."""
    return next(
        (ln.strip() for ln in ran.err.split("\n") if ": error:" in ln or "FAIL" in ln),
        ran.err.strip()[:100] or f"exited {ran.rc} and said nothing",
    )


def _running() -> str:
    """What `zig version` reports here, or "" if it cannot say."""
    if not have("zig"):
        return ""
    answered = run(["zig", "version"], timeout=30)
    return answered.out.strip() if answered.ok else ""


def phrase(lint: str) -> re.Pattern[str]:
    """The `error:` line a compiler row's phrase stands for.

    A phrase is the message from its start, with `…` for each
    identifier, type or literal in it. The match is anchored at
    `error: `, so `unreachable code` does not match `reached unreachable
    code`.
    """
    parts = (re.escape(part) for part in lint.split("…"))
    return re.compile("error: " + ".+?".join(parts))


def zig_rows(
    rows: Iterable[Row],
    probes: Mapping[str, str],
    compile_errors: Callable[[str], list[str] | None],
    profile: Location,
) -> Iterator[Finding]:
    """Each row its probe does not prove, and each probe with no row.

    `compile_errors` returns the `error:` lines the compiler printed for
    a source, or `None` when it accepted it. A probe is declared by the
    skill's profile, so one with no row is reported at `profile`.
    """
    rows = list(rows)
    cited = {row.lint for _, row in rows}
    for where, row in rows:
        source = probes.get(row.lint)
        if source is None:
            yield fail(
                f"`{row.lint}` has no probe, so nothing shows the compiler reports it",
                where,
                NO_PROBE,
            )
            continue
        errors = compile_errors(source)
        if errors is None:
            yield fail(
                f"`{row.lint}`: its probe compiles, so the compiler does not report it",
                where,
                PROBE_COMPILES,
            )
        elif not any(phrase(row.lint).search(line) for line in errors):
            printed = errors[0] if errors else "no error line"
            yield fail(
                f"`{row.lint}`: its probe fails with `{printed}` instead",
                where,
                PROBE_OTHER,
            )
    for lint in sorted(set(probes) - cited):
        yield fail(
            f"the probe for `{lint}` has no row in any chapter",
            profile,
            PROBE_NO_ROW,
        )


def compile_errors(source: str) -> list[str] | None:
    """The `error:` lines zig prints for `source`; None if it builds."""
    with tempfile.TemporaryDirectory() as work:
        probe = Path(work) / "probe.zig"
        probe.write_text(source.rstrip("\n") + "\n" + force_analysis(source))
        r = run(["zig", "build-obj", probe.name, "-fno-emit-bin"], cwd=Path(work))
    if r.ok:
        return None
    return [line for line in r.err.splitlines() if "error:" in line]


ZIG = Zig()
