"""python-style's examples, one file each, run on the pinned build.

Rust compiles its blocks as modules of one crate; Python, like Zig, has
no such container, so each block becomes a file — the stronger claim,
and the one `# verified` should mean: this text runs as written.

Two tools are needed rather than one, and for a reason worth stating.
Running a block exercises only the lines it reaches, and Python reaches
none of an unexercised branch: a block whose error is inside
`if never():` runs clean. A type checker analyses every declaration
whether or not it executes. Execution covers what runs; `ty` covers what
does not. Neither alone is enough.
"""

import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
lazy from collections.abc import Iterable

from agent_skill.lang import Extraction, Unit
from agent_skill.proc import Ran, have, run
from agent_skill.report import Finding, fail, note
lazy from agent_skill.model import Skill

#: The interpreter the examples are written for, resolved through `uv`
#: rather than through PATH. PATH here is a GIL build, and verifying
#: free-threading rules against one is the shape of failure the README
#: records for `zig --version`: a probe that cannot fail reports
#: success.
INTERPRETER = "cpython-3.15.0+freethreaded"

#: A venv on that interpreter, holding the pinned `pytest`. Persistent
#: for the same reason `.cache/target` is: resolving it per run costs
#: more than it saves.
VENV = Path(__file__).resolve().parents[3] / ".cache" / "python315t"
PYTHON = VENV / "bin" / "python"


@dataclass(frozen=True, slots=True)
class Snippet:
    """How the examples are checked: declared here, compared to assets.

    This is deliberately *not* read from `assets/ruff.toml`. An asset
    that is also the configuration in force cannot be checked against
    anything — the comparison would have the asset on both sides.
    `checks/lints.py` already works this way for Rust: the crate
    declares its table, the asset ships one, and the check compares
    them.

    The selection is narrower than the asset because these are snippets,
    not a project: a fenced example has no module docstring and no
    `__init__.py`, and holding it to rules about project shape would
    teach nothing.
    """

    select: tuple[str, ...] = (
        "E9",  # syntax and IO errors
        "F",  # pyflakes: undefined names, unused imports
        "B",  # bugbear: mutable defaults, loop-variable capture
        "UP",  # pyupgrade: the stale spellings this standard forbids
        "SIM",  # simplifiable constructs
        "RUF",  # ruff's own
        "I",  # import order
        "ASYNC",  # blocking calls in async code
        "PERF",  # avoidable overhead
    )
    ignore: tuple[str, ...] = (
        "B008",  # a call in a default is the point of some examples
        "RUF001",  # the prose uses en-dashes deliberately
    )
    #: `ty` rule levels: every rule that is off by default and that the
    #: asset enables, named one at a time for the reason
    #: `assets/ty.toml` gives.
    ty_rules: dict[str, str] = field(
        default_factory=lambda: {
            "blanket-ignore-comment": "error",
            "dynamic-function-decorator-return": "error",
            "missing-override-decorator": "error",
            "missing-type-argument": "error",
            "unsound-assignment": "error",
            "unsound-return-statement": "error",
            "unsound-yield": "error",
            "unsupported-dynamic-base": "error",
            "disjoint-cast": "error",
            "mismatched-sentinel-name": "error",
            "invalid-legacy-positional-parameter": "warn",
            "division-by-zero": "warn",
            "possibly-missing-attribute": "warn",
            "possibly-missing-import": "warn",
            "possibly-unresolved-reference": "warn",
            "redundant-condition-strict": "warn",
            "truthiness-test-of-none-union": "warn",
        }
    )

    def ruff_args(self) -> list[str]:
        """The `ruff check` arguments that apply this selection."""
        return [
            "--no-cache",
            "--isolated",
            "--target-version=py315",
            f"--select={','.join(self.select)}",
            f"--ignore={','.join(self.ignore)}",
            "--output-format=concise",
        ]

    def ty_config(self) -> str:
        """The `ty.toml` the examples are type-checked under."""
        rules = "\n".join(f'{k} = "{v}"' for k, v in sorted(self.ty_rules.items()))
        return (
            '[environment]\npython-version = "3.15"\n\n'
            f"[rules]\n{rules}\n\n"
            "[analysis]\nstrict-equality-semantics = true\n"
            "strict-generic-narrowing = true\n\n"
            '[terminal]\nerror-on-warning = true\noutput-format = "concise"\n'
        )


PYTHON_STYLE = Snippet()

#: `path:line:col: CODE message` — the one output shape both tools
#: share, and the only `ty` format that keeps warn distinct from error.
DIAGNOSTIC = re.compile(r"^(?P<file>[^:]+):(?P<line>\d+):\d+:\s*(?P<rest>.+)$")

#: A statement worth deleting when hunting for a test that cannot fail:
#: not a declaration, an import, or a bare expression.
_SKIP = ("def ", "class ", "import ", "from ", "@", "#", "assert ", "return", "yield")


def _has_tests(source: str) -> bool:
    return "\ndef test_" in source or source.startswith("def test_")


def _reaches_outside(source: str) -> bool:
    """Does the block need what a sealed temp directory cannot give?

    Such a block is not eligible to be `# verified`; the rule that shows
    it marks it `# fragment`. Checked rather than trusted, because "it
    worked on my machine" is exactly the claim `# verified` is supposed
    to replace.
    """
    return bool(
        re.search(r"\b(urlopen|requests\.|socket\.|time\.sleep|input\()", source)
    )


def _pinned() -> str:
    m = re.match(r"cpython-([0-9][^+]*)", INTERPRETER)
    return str(m.group(1)) if m else INTERPRETER


def _running() -> str:
    """The version the venv's interpreter reports.

    Spelled `3.15.0` or `3.15.0rc1`.
    """
    answered = run([str(PYTHON), "--version"], timeout=30)
    return answered.out.strip().removeprefix("Python ") if answered.ok else "unknown"


class Python:
    """The pinned free-threaded build, and `ty` and `ruff` with it."""

    name = "python"
    tool = "python"

    def missing(self) -> list[str]:
        """The interpreter, venv and tools it needs and cannot find."""
        absent: list[str] = []
        rebuild = (
            f"`uv venv --python {INTERPRETER} {VENV}` "
            f"then `uv pip install --python {VENV} pytest`"
        )
        if not PYTHON.exists():
            absent.append(f"the pinned interpreter is not built — {rebuild}")
        elif (running := _running()) != (pinned := _pinned()):
            # The venv outlives a pin move. Without this, moving the pin
            # left the examples verified on the old build while the
            # harness reported the new.
            absent.append(
                f"the venv runs Python {running} and the pin is {pinned} — {rebuild}"
            )
        absent.extend(
            f"`{tool}` is not on PATH" for tool in ("ty", "ruff") if not have(tool)
        )
        return absent

    def extract(self, skill: Skill, out: Path) -> Extraction:
        """Write each verified block as a file of its own."""
        out = out.resolve()
        out.mkdir(parents=True, exist_ok=True)
        for stale in out.glob("*.py"):
            stale.unlink()

        ex = Extraction(out)
        seen: Counter[str] = Counter()
        for b in skill.blocks("python", verified=True):
            stem = Path(b.file).stem.replace("-", "_")
            name = f"{stem}_{seen[stem]:03d}.py"
            seen[stem] += 1
            path = out / name
            path.write_text(b.body.rstrip("\n") + "\n")
            ex.units.append(Unit(path, b.file, b.line, b.rule))
        return ex

    def verify(self, ex: Extraction) -> Iterable[Finding]:
        """Run each block, type-check them all, and lint them all."""
        yield from self._run_each(ex)
        yield from self._analyse(ex, ["ty", "check", "--config-file"], "ty")
        yield from self._lint(ex)

    def _run_each(self, ex: Extraction) -> Iterable[Finding]:
        """Execute every block, and run the tests any of them ship."""
        for unit in ex.units:
            source = unit.path.read_text()
            if _reaches_outside(source):
                yield fail(
                    "a `# verified` block may not need the network, the clock, "
                    "or stdin; mark it `# fragment`",
                    unit.where,
                )
                continue
            cmd = (
                [
                    str(PYTHON),
                    "-m",
                    "pytest",
                    "-q",
                    "-p",
                    "no:cacheprovider",
                    unit.path.name,
                ]
                if _has_tests(source)
                else [str(PYTHON), unit.path.name]
            )
            # cwd is the extraction directory, so a block that writes a
            # file writes it somewhere the run owns and the caller
            # deletes.
            r = run(cmd, cwd=ex.root, timeout=120)
            if r.timed_out:
                yield fail("the block did not finish in 120s", unit.where)
            elif not r.ok:
                detail = (r.err or r.out).strip().split("\n")
                last = next(
                    (
                        ln
                        for ln in reversed(detail)
                        if ln.strip() and not ln.startswith(" ")
                    ),
                    detail[-1] if detail else "",
                )
                yield fail(last.strip()[:120], unit.where)

    def _analyse(
        self, ex: Extraction, prefix: list[str], label: str
    ) -> Iterable[Finding]:
        """Type-check every declaration, even those nothing executes."""
        config = ex.root / "ty.toml"
        config.write_text(PYTHON_STYLE.ty_config())
        r = run(
            [*prefix, str(config), "--python", str(VENV), str(ex.root)], timeout=300
        )
        if r.timed_out:
            yield fail(
                f"{label} did not finish in 300s",
                ex.units[0].where if ex.units else label,
            )
            return
        yield from self._report(ex, r, label)

    def _lint(self, ex: Extraction) -> Iterable[Finding]:
        r = run(["ruff", "check", *PYTHON_STYLE.ruff_args(), str(ex.root)], timeout=300)
        if r.timed_out:
            yield fail(
                "ruff did not finish in 300s", ex.units[0].where if ex.units else "ruff"
            )
            return
        yield from self._report(ex, r, "ruff")

    def _report(self, ex: Extraction, r: Ran, label: str) -> Iterable[Finding]:
        """Diagnostics decide; the exit code only corroborates.

        The README records what reading the exit status costs: clippy
        was reported clean because half the table is `warn` and it exits
        0 on a warning. So the output is parsed, and a non-zero exit
        that produced no parsed diagnostic is its own finding — that
        combination means the harness did not understand the output,
        which is worse than either answer.
        """
        by_name = {u.path.name: u for u in ex.units}
        found = 0
        for line in (r.out + "\n" + r.err).split("\n"):
            m = DIAGNOSTIC.match(line.strip())
            if not m:
                continue
            unit = by_name.get(Path(m["file"]).name)
            if unit is None:
                continue
            found += 1
            offset = int(m["line"]) - 1
            yield fail(
                f"{label}: {m['rest'].strip()[:110]}",
                f"{unit.chapter}:{unit.line + offset} [{unit.rule}]",
            )
        if not r.ok and not found:
            yield fail(
                f"{label} exited {r.rc} without a diagnostic this harness could read: "
                f"{(r.err or r.out).strip()[:100]}",
                ex.units[0].where if ex.units else label,
            )

    def mutate(self, ex: Extraction) -> Iterable[Finding]:
        """A shipped test must be able to fail.

        Survivors are notes, not verdicts: an illustrative example's
        test pins the case its name describes, and a guard outside that
        case is expected to survive. The defect this catches is a test
        that cannot fail on its own stated case.
        """
        for unit in ex.units:
            original = unit.path.read_text()
            if not _has_tests(original):
                continue
            base = run(
                [
                    str(PYTHON),
                    "-m",
                    "pytest",
                    "-q",
                    "-p",
                    "no:cacheprovider",
                    unit.path.name,
                ],
                cwd=ex.root,
                timeout=120,
            )
            if not base.ok:
                continue  # not runnable here; verify() reports why

            lines = original.split("\n")
            for i, line in enumerate(lines):
                stripped = line.strip()
                if not stripped or stripped.startswith(_SKIP) or "=" not in stripped:
                    continue
                unit.path.write_text("\n".join(lines[:i] + lines[i + 1 :]))
                try:
                    r = run(
                        [
                            str(PYTHON),
                            "-m",
                            "pytest",
                            "-q",
                            "-p",
                            "no:cacheprovider",
                            unit.path.name,
                        ],
                        cwd=ex.root,
                        timeout=60,
                    )
                    if r.timed_out:
                        yield note(
                            f"`{stripped[:44]}` timed out — hung, or merely slow",
                            f"{unit.chapter}:{unit.line + i} [{unit.rule}]",
                        )
                    elif r.ok:
                        yield note(
                            f"`{stripped[:52]}` can be deleted "
                            "and every test still passes",
                            f"{unit.chapter}:{unit.line + i} [{unit.rule}]",
                        )
                finally:
                    unit.path.write_text(original)


PYTHON_TOOLCHAIN = Python()
