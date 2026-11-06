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

And everything else the harness knows about Python: how a rule's
citation of a ruff code and a `Decided by tools` row are checked against
the shipped `ruff.toml` and `ty.toml`, how the interpreter pin is held
against the assets that install it and against `uv`'s releases, and how
`fmt` rewrites a block the way `ruff format` would.
"""

import json
import re
import tempfile
import tomllib
from collections import Counter
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path
from types import MappingProxyType
from typing import Any
lazy from collections.abc import Iterable, Iterator, Mapping

from agent_skill.harness import HARNESS, pinned
from agent_skill.ids import Pin
from agent_skill.lang import Extraction, Language, Unit, inconclusive, timed_out
from agent_skill.proc import Ran, have, run
from agent_skill.report import Finding, Level, declare, fail, note, unrun
lazy from agent_skill.checks.citations import Row, rows_of
lazy from agent_skill.checks.pins import SortKey, _sort_key
lazy from agent_skill.doc import text_of
lazy from agent_skill.fmt import RUFF_FORMAT, put_back
lazy from agent_skill.ids import Location
lazy from agent_skill.model import Block, Skill

# The branches of `toolchain` and of `mutation` Python's steps report
# through.
OUTSIDE = declare("toolchain", "py_outside", Level.FAIL)
RUN_TIMEOUT = declare("toolchain", "py_run_timeout", Level.FAIL)
RUN = declare("toolchain", "py_run", Level.FAIL)
TY_TIMEOUT = declare("toolchain", "py_ty_timeout", Level.FAIL)
RUFF_TIMEOUT = declare("toolchain", "py_ruff_timeout", Level.FAIL)
REPORTED = declare("toolchain", "py_diagnostic", Level.FAIL)
UNREAD = declare("toolchain", "py_unread", Level.FAIL)
HUNG = declare("mutation", "py_inconclusive", Level.NOTE)
SURVIVOR = declare("mutation", "py_survivor", Level.NOTE)

# The branches of `citations` Python's citations and rows report
# through.
RUFF_ABSENT = declare("citations", "ruff_absent", Level.UNRUN)
TY_ABSENT = declare("citations", "ty_absent", Level.UNRUN)
TY_UNKNOWN_SETTING = declare("citations", "ty_unknown_setting", Level.FAIL)
ENABLED_UNREAD = declare("citations", "enabled_unread", Level.UNRUN)
TY_RULES_UNREAD = declare("citations", "ty_rules_unread", Level.UNRUN)
RUFF_ROW_DISABLED = declare("citations", "ruff_row_disabled", Level.FAIL)
TY_ROW_UNKNOWN = declare("citations", "ty_row_unknown", Level.FAIL)
TY_ROW_LEVEL = declare("citations", "ty_row_level", Level.FAIL)
CATALOGUE_UNREAD = declare("citations", "catalogue_unread", Level.UNRUN)
UNKNOWN_CODE = declare("citations", "unknown_code", Level.FAIL)
WITHDRAWN_CODE = declare("citations", "withdrawn_code", Level.FAIL)
DISABLED_CODE = declare("citations", "disabled_code", Level.FAIL)
TY_UNVERIFIED = declare("citations", "ty_unverified", Level.FAIL)
TY_UNSHIPPED = declare("citations", "ty_unshipped", Level.FAIL)
TY_LEVEL = declare("citations", "ty_level", Level.FAIL)

# The branches of `pins` the interpreter pin reports through.
WORKFLOW_NONE = declare("pins", "workflow_none", Level.FAIL)
WORKFLOW_OTHER = declare("pins", "workflow_other", Level.FAIL)
PROJECT_UNPARSED = declare("pins", "project_unparsed", Level.UNRUN)
PROJECT_PIN = declare("pins", "project_pin", Level.FAIL)
PROJECT_INEXACT = declare("pins", "project_inexact", Level.FAIL)
UV_ABSENT = declare("pins", "uv_absent", Level.UNRUN)
UV_SILENT = declare("pins", "uv_silent", Level.UNRUN)
RELEASE_UNORDERED = declare("pins", "release_unordered", Level.UNRUN)
INTERPRETER_STALE = declare("pins", "interpreter_stale", Level.FAIL)


def inside_tests(body: str) -> set[int]:
    """Body-line indices inside a `def test_*` function, by indentation.

    Python has no block delimiter to count, so the end of a test is the
    next line at or below the `def`'s own indentation that is not blank.
    """
    inside: set[int] = set()
    lines = body.split("\n")
    depth: int | None = None
    for i, line in enumerate(lines):
        stripped = line.strip()
        indent = len(line) - len(line.lstrip())
        if depth is not None:
            if stripped and indent <= depth:
                depth = None
            else:
                inside.add(i)
                continue
        if re.match(r"^\s*(?:async\s+)?def\s+test_", line):
            depth, _ = indent, inside.add(i)
    return inside


#: Python's comment is `#`, and `//` is floor division: reading it as a
#: comment truncated every line after one. Both quotes open a string.
LANGUAGE = Language("python", "#", "\"'", ".py", inside_tests)

#: The interpreter the examples are written for, resolved through `uv`
#: rather than through PATH. PATH here is a GIL build, and verifying
#: free-threading rules against one is the shape of failure the README
#: records for `zig --version`: a probe that cannot fail reports
#: success.
INTERPRETER = Pin.parse("cpython-3.15.2+freethreaded")

#: A venv on that interpreter, holding the pinned `pytest`. Persistent
#: for the same reason `.cache/target` is: resolving it per run costs
#: more than it saves.
VENV = Path(__file__).resolve().parents[3] / ".cache" / "python315t"
PYTHON = VENV / "bin" / "python"


@dataclass(frozen=True, slots=True)
class PythonSnippet:
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

    #: the build every example runs on
    interpreter: Pin = INTERPRETER
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

    @property
    def pin(self) -> Pin:
        """The interpreter the examples run on."""
        return self.interpreter

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


PYTHON_STYLE = PythonSnippet()

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
    return str(INTERPRETER.version.public)


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
    language: Language = LANGUAGE
    needs: tuple[str, ...] = ("ty", "ruff")
    #: Each row's tool, and the levels at which it fails a run.
    rows: Mapping[str, frozenset[str]] = MappingProxyType(
        {"ruff": frozenset({"error"}), "ty": frozenset({"error", "warn"})}
    )
    compilers: frozenset[str] = frozenset[str]()
    cites_with: tuple[str, ...] = ("ruff", "ty")
    pins_with: tuple[str, ...] = ("uv",)
    asset_suffixes: tuple[str, ...] = ()
    assets_with: tuple[str, ...] = ()

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
            f"`{tool}` is not on PATH" for tool in self.needs if not have(tool)
        )
        return absent

    def extract(self, skill: Skill, out: Path) -> Extraction:
        """Write each verified block as a file of its own."""
        out = out.resolve()
        out.mkdir(parents=True, exist_ok=True)
        for stale in out.glob("*.py"):
            stale.unlink()

        ex = Extraction(out, skill=skill.name)
        seen: Counter[str] = Counter()
        for b in skill.blocks("python", verified=True):
            stem = Path(b.file).stem.replace("-", "_")
            name = f"{stem}_{seen[stem]:03d}.py"
            seen[stem] += 1
            path = out / name
            path.write_text(b.body.rstrip("\n") + "\n")
            ex.units.append(Unit(path, b.file, b.line, b.rule, skill.name))
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
                    OUTSIDE,
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
                yield timed_out("the block", 120, unit.where, RUN_TIMEOUT)
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
                yield fail(last.strip()[:120], unit.where, RUN)

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
            yield timed_out(label, 300, ex.where, TY_TIMEOUT)
            return
        yield from self._report(ex, r, label)

    def _lint(self, ex: Extraction) -> Iterable[Finding]:
        r = run(["ruff", "check", *PYTHON_STYLE.ruff_args(), str(ex.root)], timeout=300)
        if r.timed_out:
            yield timed_out("ruff", 300, ex.where, RUFF_TIMEOUT)
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
            yield fail(
                f"{label}: {m['rest'].strip()[:110]}",
                unit.where_at(int(m["line"]) - 1),
                REPORTED,
            )
        if not r.ok and not found:
            yield fail(
                f"{label} exited {r.rc} without a diagnostic this harness could read: "
                f"{(r.err or r.out).strip()[:100]}",
                ex.where,
                UNREAD,
            )

    def cite(self, skill: Skill) -> Iterator[Finding]:
        """Each python row and cited code, against what is shipped."""
        ruff_toml, ty_toml = skill.root / RUFF_TOML, skill.root / TY_TOML
        if not ruff_toml.exists() or not ty_toml.exists():
            return
        if not have("ruff"):
            yield unrun(
                "`ruff` is not on PATH, so nothing compared the citations",
                skill.at(),
                RUFF_ABSENT,
            )
            return

        yield from _rows_and_codes(skill, ruff_toml, ty_toml)

        # The harness declares the ty levels it verifies under; the
        # asset ships one for the reader. Two tables, compared — an
        # asset that were also the configuration in force could not be
        # checked against anything.
        shipped = tomllib.loads(ty_toml.read_text()).get("rules", {})
        yield from _ty_tables(skill, shipped, _snippet(skill).ty_rules)

        if not have("ty"):
            yield unrun(
                "`ty` is not on PATH, so no rule name was validated",
                skill.at(),
                TY_ABSENT,
            )
            return
        if (known := _ty_rules()) is not None:
            for name in sorted(set(shipped) - set(known)):
                yield fail(
                    f"names `{name}`, which the pinned ty does not "
                    "recognise — the setting silently does nothing",
                    skill.at(TY_TOML),
                    TY_UNKNOWN_SETTING,
                )

    def pins(self, skill: Skill) -> Iterator[Finding]:
        """The interpreter, against the assets and `uv`'s releases."""
        interpreter = _snippet(skill).interpreter
        yield from _asset_pins(skill, interpreter)
        yield from _interpreter_pin(
            skill,
            str(interpreter.version.public),
            want_ft=interpreter.version.local == FREE_THREADED,
        )

    def asset(self, path: Path, where: Location) -> Iterator[Finding]:  # noqa: ARG002 — no asset is Python's to read
        """Nothing: `assets` builds a `pyproject.toml` as any other."""
        return iter(())

    def format(self, skill: Skill) -> list[Finding]:
        """Rewrite each `# verified` block as `ruff format` would.

        Simpler than the Rust path because each block is already its own
        file: there is no crate to reassemble, so a block that fails to
        format is reported alone rather than taking its chapter's
        siblings with it.
        """
        config = skill.root / RUFF_TOML
        if not config.exists():
            return []
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as work:
            extraction = self.extract(skill, Path(work) / "out")
            if not extraction:
                return []
            r = run(
                [
                    "ruff",
                    "format",
                    "--no-cache",
                    "--config",
                    str(config),
                    str(extraction.root),
                ],
                timeout=300,
            )
            if not r.ok:
                said = (r.err or r.out).strip()[:160]
                return [fail(f"ruff format failed: {said}", skill.at(), RUFF_FORMAT)]

            changed: list[Finding] = []
            by_chapter: dict[str, list[Unit]] = {}
            for unit in extraction.units:
                by_chapter.setdefault(unit.chapter, []).append(unit)
            for chapter, units in by_chapter.items():
                # Last first, so an earlier replacement cannot move a
                # later block.
                ordered = sorted(units, key=lambda u: u.line, reverse=True)
                edits = _formatted(skill, chapter, ordered)
                changed += put_back(skill, chapter, LANGUAGE.fence, edits)
            return changed

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
                        yield inconclusive(stripped, unit.where_at(i), HUNG)
                    elif r.ok:
                        yield note(
                            f"`{stripped[:52]}` can be deleted "
                            "and every test still passes",
                            unit.where_at(i),
                            SURVIVOR,
                        )
                finally:
                    unit.path.write_text(original)


def _snippet(skill: Skill) -> PythonSnippet:
    """How `skill`'s examples are checked: its profile's snippet."""
    config = skill.profile.toolchain
    if not isinstance(config, PythonSnippet):
        msg = f"{skill.name} is checked as Python and its profile names no snippet"
        raise TypeError(msg)
    return config


#: The local label of an interpreter built without the GIL.
FREE_THREADED = "freethreaded"


def _formatted(
    skill: Skill, chapter: str, units: Iterable[Unit]
) -> Iterator[tuple[Block, str]]:
    """Each unit's formatted body, with the block it was cut from."""
    for unit in units:
        body = unit.path.read_text()
        same = (b for b in skill.blocks(LANGUAGE.fence) if b.file == chapter)
        block = next((b for b in same if b.line == unit.line), None)
        if block is not None:
            yield block, body


#: `PS-CONC-02` and `3.15` are not ruff codes; `ANN401` and `B008` are.
#: `ASYNC251` is five letters, and a cap of four hid every citation of
#: that family — including one to a code that does not exist.
CODE = re.compile(r"(?<![A-Za-z0-9-])([A-Z]{1,5}[0-9]{3,4})(?![0-9])")

#: What a code's family is left as once these are stripped from its end.
DIGITS = "0123456789"

#: The asset that enables ruff's rules.
RUFF_TOML = "assets/ruff.toml"

#: The asset that sets ty's rule levels.
TY_TOML = "assets/ty.toml"


def _codes_in(text: str, catalogue: Mapping[str, str]) -> set[str]:
    """Every token in `text` spelled as a code of a ruff family.

    A family is the letters a catalogued code starts with, read from
    ruff's own catalogue rather than written down here. The list that
    used to be written here named linters by their prefix — `C4`, `T20`
    — while a token is classified by stripping its digits, which turns
    `C408` into `C` and `T201` into `T`: four families could never be
    produced, and every citation of one was dropped as prose. Asked by
    family rather than by code, a code ruff never had is still read as
    a citation, and reported as one.
    """
    families = {code.rstrip(DIGITS) for code in catalogue}
    return {code for code in CODE.findall(text) if code.rstrip(DIGITS) in families}


def _enabled(config: Path) -> tuple[set[str], str]:
    """Every code the asset turns on, as ruff itself resolves them."""
    r = run(
        [
            "ruff",
            "check",
            "--no-cache",
            "--config",
            str(config),
            "--show-settings",
            ".",
        ],
        cwd=config.parent,
        timeout=120,
    )
    if not r.out:
        return set(), (r.err or "ruff produced no settings").strip()[:120]
    codes: set[str] = set()
    inside = False
    for line in r.out.split("\n"):
        if line.startswith("linter.rules.enabled = ["):
            inside = True
            continue
        if inside:
            if line.startswith("]"):
                break
            if m := re.search(r"\(([A-Z]+[0-9]+)\)", line):
                codes.add(m.group(1))
    return codes, ""


@cache
def _ty_rules() -> dict[str, str] | None:
    """Every rule the pinned ty knows, with its default level.

    None if ty would not say.
    """
    r = run(["ty", "explain", "rule", "--output-format", "json"], timeout=120)
    if not r.ok or not r.out:
        return None
    return {rule["name"]: rule["default_level"] for rule in json.loads(r.out)}


def _ty_levels(ty_toml: Path) -> dict[str, str] | None:
    """Every rule the pinned ty knows, at its level as shipped.

    The asset's own entry where it has one, ty's default otherwise.
    """
    if (rules := _ty_rules()) is None:
        return None
    shipped = tomllib.loads(ty_toml.read_text()).get("rules", {})
    return {name: shipped.get(name, level) for name, level in rules.items()}


@cache
def _catalogue() -> dict[str, str] | None:
    """Every code the pinned ruff has ever had, with its status.

    None if ruff would not say. A status is `Stable`, `Preview` or
    `Removed`; selecting a removed code is a hard failure, not a
    warning.
    """
    r = run(["ruff", "rule", "--all", "--output-format", "json"], timeout=120)
    if not r.ok or not r.out:
        return None
    return {
        rule["code"]: str(rule.get("status", ""))
        for rule in json.loads(r.out)
        if rule.get("code")
    }


def python_rows(
    rows: Iterable[Row], enabled: set[str], ty_levels: dict[str, str]
) -> Iterator[Finding]:
    """Each python row not enforced as the row states.

    The shipped configuration is what enforces them. `ty_levels` is
    every rule ty knows, at the level the asset leaves it — its own
    entry, or the default.
    """
    for where, row in rows:
        if row.tool == "ruff" and row.lint not in enabled:
            yield fail(
                f"`{row.lint}` is a row, and `{RUFF_TOML}` does not enable it",
                where,
                RUFF_ROW_DISABLED,
            )
        elif row.tool == "ty":
            level = ty_levels.get(row.lint)
            if level is None:
                yield fail(
                    f"`{row.lint}` is not a rule the pinned ty recognises",
                    where,
                    TY_ROW_UNKNOWN,
                )
            elif level != row.level:
                yield fail(
                    f"`{row.lint}` is `{row.level}` in the row "
                    f"and `{level}` as shipped",
                    where,
                    TY_ROW_LEVEL,
                )


def _rows_and_codes(skill: Skill, ruff_toml: Path, ty_toml: Path) -> Iterator[Finding]:
    """The python rows and every cited code, against the enabled set."""
    enabled, problem = _enabled(ruff_toml)
    if problem:
        yield unrun(
            f"could not read the enabled set: {problem}", skill.at(), ENABLED_UNREAD
        )
        return
    ty_levels = _ty_levels(ty_toml)
    if ty_levels is None:
        yield unrun(
            "`ty` did not list its rules, so no ty row was compared",
            skill.at(),
            TY_RULES_UNREAD,
        )
        ty_levels = {}
    yield from python_rows(rows_of(skill), enabled, ty_levels)

    catalogue = _catalogue()
    if catalogue is None:
        yield unrun(
            "`ruff` did not list its rules, so no cited code was told from prose",
            skill.at(),
            CATALOGUE_UNREAD,
        )
        return
    # A rule's own body is where it cites its checks; the `**Check:**`
    # section is part of it. Core rules in SKILL.md point at the chapter
    # that owns them, so they carry no citation of their own.
    cited = {
        rule.id: _codes_in(text_of(rule.body), catalogue)
        for rule in skill.chapter_rules
    }
    for rule_id, codes in sorted(cited.items()):
        for code in sorted(codes):
            if code not in catalogue:
                yield fail(
                    f"{rule_id} cites `{code}`, which is not a rule the pinned ruff "
                    "has; the rule reads as enforced by a check that does not exist",
                    skill.at(),
                    UNKNOWN_CODE,
                )
            elif "Removed" in catalogue[code]:
                yield fail(
                    f"{rule_id} cites `{code}`, which ruff has withdrawn — "
                    "selecting it is a hard failure, so the rule can never be "
                    "enforced",
                    skill.at(),
                    WITHDRAWN_CODE,
                )
            elif code not in enabled:
                yield fail(
                    f"{rule_id} cites `{code}`, which `{RUFF_TOML}` does not "
                    "enable; the rule reads as enforced and is not",
                    skill.at(),
                    DISABLED_CODE,
                )


def _ty_tables(
    skill: Skill, shipped: Mapping[str, object], declared: Mapping[str, str]
) -> Iterator[Finding]:
    """The asset's ty levels, against those the harness verifies."""
    where = skill.at(TY_TOML)
    for name in sorted(set(shipped) - set(declared)):
        yield fail(
            f"enables `{name}` that the harness does not verify", where, TY_UNVERIFIED
        )
    for name in sorted(set(declared) - set(shipped)):
        yield fail(
            f"the harness verifies `{name}` that the asset does not ship",
            where,
            TY_UNSHIPPED,
        )
    for name in sorted(set(shipped) & set(declared)):
        if shipped[name] != declared[name]:
            yield fail(
                f"`{name}` is {shipped[name]!r} in the asset "
                f"and {declared[name]!r} in the harness",
                where,
                TY_LEVEL,
            )


#: The asset whose interpreter is compared.
WORKFLOW = "assets/ci.yml"

#: The asset whose tool requirements are compared.
PROJECT = "assets/pyproject.toml"

#: `cpython-3.15.0rc1+freethreaded-macos-aarch64-none` -> ("3.15.0rc1",
#: True)
RELEASE = re.compile(
    r"^cpython-(?P<version>\d+\.\d+\.\d+[a-z0-9]*)(?P<ft>\+freethreaded)?-"
)


def _asset_pins(skill: Skill, interpreter: Pin) -> Iterator[Finding]:
    """What the assets install, against what the harness verifies."""
    # Two declarations, compared — the harness verifies against one and
    # the reader copies the other, so an asset that installs a different
    # build than the one these examples were verified on is the defect
    # this half exists to catch.
    workflow = skill.root / WORKFLOW
    if workflow.exists():
        yield from workflow_pins(
            workflow.read_text(), str(interpreter), skill.at(WORKFLOW)
        )

    # Two declarations, compared — the same reason the interpreter half
    # exists. The harness verifies against one pin and the reader
    # installs the other, so an asset naming a different version hands
    # them a build these examples were never checked on.
    shipped = skill.root / PROJECT
    if shipped.exists():
        try:
            project = tomllib.loads(shipped.read_text())
        except tomllib.TOMLDecodeError:
            yield unrun(
                "does not parse (`assets` says where), so no pin in it was compared",
                skill.at(PROJECT),
                PROJECT_UNPARSED,
            )
            return
        harness = {
            tool.package: str(pin.version) if (pin := pinned(tool.binary)) else ""
            for tool in HARNESS.tools
        }
        yield from project_pins(project, harness, skill.at(PROJECT))


def workflow_pins(text: str, interpreter: str, where: Location) -> Iterator[Finding]:
    """What is wrong with the interpreter a workflow installs, if any.

    It must install `interpreter` with `uv python install`, and nothing
    else. Comparing only the lines that were there passed a workflow
    with none: the runner's own interpreter then runs every job, which
    is the one build nobody verified anything on.
    """
    stated = set(re.findall(r"uv python install (\S+)", text))
    if not stated:
        yield fail(
            f"installs no interpreter with `uv python install`, so a reader runs "
            f"whatever the runner has rather than `{interpreter}`",
            where,
            WORKFLOW_NONE,
        )
    for named in sorted(stated - {interpreter}):
        yield fail(
            f"installs `{named}` where the harness verifies against "
            f"`{interpreter}` — a reader would not be running what this was "
            "checked on",
            where,
            WORKFLOW_OTHER,
        )


#: `ty>=0.0.60`, `ruff [extra] == 0.17.3 ; python_version >= "3.15"`:
#: the name, then the version clauses up to any marker.
REQUIREMENT = re.compile(
    r"^\s*(?P<name>[A-Za-z0-9][A-Za-z0-9._-]*)\s*(?:\[[^\]]*\])?\s*(?P<spec>[^;]*)"
)


def project_pins(
    project: dict[str, Any], harness: dict[str, str], where: Location
) -> Iterator[Finding]:
    """Each requirement on a harness tool that is not exactly its pin.

    `harness` maps a distribution to the version the harness verifies
    against. Only `==` that version will do: a floor such as
    `ty>=0.0.60` lets the resolver hand the reader any build at all,
    and it passed, because only a requirement already spelled `==` was
    compared.
    """
    for requirement in _requirements(project):
        m = REQUIREMENT.match(requirement)
        if m is None:
            continue
        name = m["name"].lower().replace("_", "-")
        want = harness.get(name)
        if want is None:
            continue
        spec = "".join(m["spec"].split())
        if spec == f"=={want}":
            continue
        # Two defects: a pin on another build, and a requirement that
        # pins nothing. A floor passed for as long as only the first was
        # looked for.
        if spec.startswith("==") and "," not in spec:
            yield fail(
                f"requires `{requirement}` where the harness verifies against "
                f"`{name}=={want}` — a reader installs a build this was never "
                "checked on",
                where,
                PROJECT_PIN,
            )
        else:
            yield fail(
                f"requires `{requirement}` where the harness verifies against "
                f"`{name}=={want}` — anything but that exact pin lets a reader "
                "resolve a build this was never checked on",
                where,
                PROJECT_INEXACT,
            )


def _requirements(project: dict[str, Any]) -> Iterator[str]:
    """Every requirement string a `pyproject.toml` declares.

    The build system's, the project's, its extras' and its dependency
    groups'. An `include-group` table is not a requirement.
    """
    lists: list[object] = [
        project.get("build-system", {}).get("requires", []),
        project.get("project", {}).get("dependencies", []),
        *project.get("project", {}).get("optional-dependencies", {}).values(),
        *project.get("dependency-groups", {}).values(),
    ]
    for entries in lists:
        if isinstance(entries, list):
            yield from (e for e in entries if isinstance(e, str))


def _interpreter_pin(skill: Skill, pinned: str, *, want_ft: bool) -> Iterator[Finding]:
    """The interpreter pin against what `uv` offers in its series."""
    if not have("uv"):
        yield unrun(
            "`uv` is not on PATH, so no release list was consulted",
            skill.at(),
            UV_ABSENT,
        )
        return
    r = run(["uv", "python", "list", "--all-versions"], timeout=120)
    if not r.out:
        yield unrun(
            "`uv python list` returned nothing to compare against",
            skill.at(),
            UV_SILENT,
        )
        return

    # Scoped to the pinned minor series on purpose: a newer patch or
    # candidate is a pin refresh, and a newer *minor* is a deliberate
    # change of target that this check has no business demanding.
    series = ".".join(pinned.split(".")[:2])  # 3.15.0rc1 -> 3.15
    here = _sort_key(pinned)
    if here is None:
        # `tests/test_profiles.py` holds every interpreter pin to a
        # release this orders, so this is the harness misdeclared.
        msg = f"the interpreter pin {pinned} is not a release this can order"
        raise ValueError(msg)

    newer, unreadable = _releases(r.out, series, here, want_ft=want_ft)
    if unreadable:
        yield unrun(
            f"`uv python list` offers {', '.join(sorted(unreadable))} in the {series} "
            f"series, which this cannot order against `{pinned}` — a release it cannot "
            f"compare is not a release it has ruled out",
            skill.at(),
            RELEASE_UNORDERED,
        )

    if newer:
        best = max(newer, key=newer.__getitem__)
        yield fail(
            f"the interpreter pin is `{pinned}` and `{best}` is available — move it in "
            "`lang/python.py` and `assets/ci.yml`, re-verify the PS-MIG table "
            "against the released What's New, and re-run the suite",
            skill.at(),
            INTERPRETER_STALE,
        )


def _releases(
    listing: str, series: str, here: SortKey, *, want_ft: bool
) -> tuple[dict[str, SortKey], set[str]]:
    """Releases in `series` newer than `here`, and any it cannot order.

    Newer ones map to their order, so the best is picked without
    ordering by a key function that is allowed to answer `None`.
    """
    newer: dict[str, SortKey] = {}
    unreadable: set[str] = set()
    for line in listing.split("\n"):
        found = RELEASE.match(line.strip())
        if not found or bool(found["ft"]) != want_ft:
            continue
        version = found["version"]
        if not version.startswith(f"{series}."):
            continue
        # Scoped to the pinned series, so this reports what it could not
        # rule out rather than every oddity in a list of every CPython
        # ever built.
        order = _sort_key(version)
        if order is None:
            unreadable.add(version)
        elif order > here:
            newer[version] = order
    return newer, unreadable


PYTHON_TOOLCHAIN = Python()
