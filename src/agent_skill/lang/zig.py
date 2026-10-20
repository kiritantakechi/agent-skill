"""zig-style's examples, one standalone file each.

The rust side compiles its blocks as modules of one crate; Zig has no
such container, so each block becomes a standalone file — which is also
the stronger claim, and the one `// verified` should mean: this text
compiles as written.
"""

import re
from collections import Counter
lazy from collections.abc import Iterable
from pathlib import Path

from agent_skill.lang import Extraction, Unit
from agent_skill.model import inside_tests, needs_c_object
from agent_skill.proc import have, run
from agent_skill.report import Finding, fail, note

#: The compiler `zig-style` is verified against. It follows this
#: machine's `zig` rather than upstream's newest release, so `pins`
#: compares it with `zig version` only: the skill moves when the
#: compiler here does.
ZIG_VERSION = "0.16.0"

#: A `comptime` block at file scope is analysed by `zig build-obj`, so
#: forcing analysis costs a tenth of a second per block instead of a
#: link and a launch. Without it Zig never analyses the body of a
#: function nobody calls, and a block with a type error in it reports
#: success.
FORCE_ANALYSIS = """
comptime {
    // The capture is named for this harness: Zig makes a capture that shadows a
    // container declaration a hard error, and the error would point here rather
    // than at whatever the block was actually doing wrong.
    for (@typeInfo(@This()).@"struct".decls) |__zs_decl| {
        _ = &@field(@This(), __zs_decl.name);
    }
}
"""

#: A statement worth deleting: not a declaration, a brace, or a discard.
_SKIP = ("//", "const ", "var ", "pub const", "pub var", "}", "_ = ")

#: A defensive assertion earns its place on the path the tests do *not*
#: reach — deleting one and staying green is what it is for, not a gap.
_ASSERT = re.compile(r"^(std\.debug\.)?assert\s*\(")


class Zig:
    name = "zig"
    tool = "zig"

    def missing(self) -> list[str]:
        return [] if have(self.tool) else [f"`{self.tool}` is not on PATH"]

    def extract(self, skill, out: Path) -> Extraction:
        out = out.resolve()
        out.mkdir(parents=True, exist_ok=True)
        for stale in out.glob("*.zig"):
            stale.unlink()

        ex = Extraction(out)
        seen: Counter[str] = Counter()
        for b in skill.blocks("zig", verified=True):
            stem = Path(b.file).stem.replace("-", "_")
            name = f"{stem}_{seen[stem]:03d}.zig"
            seen[stem] += 1
            path = out / name
            path.write_text(b.body.rstrip("\n") + "\n" + FORCE_ANALYSIS)
            ex.units.append(Unit(path, b.file, b.line, b.rule))
        return ex

    def verify(self, ex: Extraction) -> Iterable[Finding]:
        for unit in ex.units:
            source = unit.path.read_text()
            # semantic analysis of every declaration, without linking or
            # running
            r = run(
                ["zig", "build-obj", str(unit.path), "-fno-emit-bin"],
                cwd=ex.root,
                timeout=180,
            )
            if r.timed_out:
                yield fail("build-obj timed out", unit.where)
                continue
            if not r.ok:
                first = next(
                    (ln for ln in r.err.split("\n") if ": error:" in ln), r.err[:100]
                )
                yield fail(
                    first.split(f"{unit.path.name}:")[-1].strip()[:96], unit.where
                )
                continue

            # A block that ships a `test` gets its assertions executed —
            # unless it declares an `extern fn`, which needs a C object
            # to link against. `extern struct` is a layout qualifier and
            # links fine; testing for the substring `extern ` excluded
            # two blocks whose four tests pass.
            if _has_test(source) and not needs_c_object(source):
                t = run(["zig", "test", str(unit.path)], cwd=ex.root, timeout=180)
                if t.timed_out:
                    yield fail("test run timed out", unit.where)
                elif not t.ok:
                    first = next(
                        (
                            ln
                            for ln in t.err.split("\n")
                            if ": error:" in ln or "FAIL" in ln
                        ),
                        t.err[:100],
                    )
                    yield fail(f"test run: {first.strip()[:84]}", unit.where)

        # One invocation for the whole directory. Spawning `zig fmt` per
        # block cost 215 process launches for a check that names each
        # file anyway.
        r = run(["zig", "fmt", "--check", str(ex.root)], cwd=ex.root, timeout=180)
        by_file = {u.path.name: u for u in ex.units}
        for line in r.out.splitlines():
            unit = by_file.get(Path(line.strip()).name)
            yield fail("not `zig fmt` clean", unit.where if unit else line.strip())

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
            base = run(["zig", "test", str(unit.path)], cwd=ex.root, timeout=60)
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
                    r = run(["zig", "test", str(unit.path)], cwd=ex.root, timeout=15)
                    if not r.timed_out and r.ok:
                        yield note(
                            f"`{s[:52]}` can be deleted and every test still passes",
                            f"{unit.chapter}:{unit.line + i} [{unit.rule}]",
                        )
                finally:
                    unit.path.write_text(text)


def _has_test(source: str) -> bool:
    return "\ntest " in source or source.startswith("test ")


ZIG = Zig()
