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
the shipped `ruff.toml` and `ty.toml`, and how the interpreter pin is
held against the assets that install it and against `uv`'s releases.
"""

import ast
import json
import re
import tomllib
from collections import Counter
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path
from types import MappingProxyType
from typing import Any
lazy from collections.abc import Iterable, Iterator, Mapping

from agent_skill.harness import HARNESS, pinned
from agent_skill.ids import Pin, Version
from agent_skill.lang import Extraction, Language, Step, Unit, extracted
from agent_skill.proc import have, run
from agent_skill.report import Finding, Level, declare, fail, unrun
lazy from agent_skill.checks.citations import Row, rows_of
lazy from agent_skill.doc import text_of
lazy from agent_skill.ids import Location
lazy from agent_skill.model import Block, Skill
lazy from agent_skill.proc import Ran

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
COOLDOWN_MISSING = declare("pins", "cooldown_missing", Level.FAIL)
COOLDOWN_EXEMPT = declare("pins", "cooldown_exempt", Level.FAIL)
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


def statements(body: str) -> set[int]:
    """Body-line indices holding whole statements that do something.

    Python ends a statement at a line's end only outside brackets and
    strings, so its parser says which lines hold one: every statement
    that starts on the line ends there too. A line whose statements do
    nothing when run — `pass`, a docstring, a bare annotation — is left
    out, since no test could notice it gone. Nothing, when the body does
    not parse: running it reports why.
    """
    try:
        tree = ast.parse(body)
    except SyntaxError:
        return set()
    starting: dict[int, list[ast.stmt]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.stmt):
            starting.setdefault(node.lineno, []).append(node)
    return {
        line - 1
        for line, nodes in starting.items()
        if all(n.end_lineno == line for n in nodes) and not all(map(_inert, nodes))
    }


def _inert(node: ast.stmt) -> bool:
    """Does `node` do nothing when it runs?"""
    match node:
        case ast.Pass() | ast.Expr(value=ast.Constant()):
            return True
        case ast.AnnAssign(value=None):
            return True
        case _:
            return False


#: Python's comment is `#`, and `//` is floor division: reading it as a
#: comment truncated every line after one. Both quotes open a string.
#:
#: A mutant deletes no declaration or import, which only stops the
#: block running, and no assertion.
LANGUAGE = Language(
    "python",
    "#",
    "\"'",
    ".py",
    inside_tests,
    statements=statements,
    kept=(
        *("def ", "async def ", "class ", "import ", "from ", "@"),
        *("global ", "nonlocal ", "type ", "assert "),
    ),
)

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
    #: What a normalised standard's examples are excused from of the
    #: configuration it ships, each with its reason: rules about the
    #: shape of a project, which a fenced snippet cannot have
    #: (normalize-the-standards, decision 12). Everything else the
    #: shipped `ruff.toml` enables, the examples are linted with.
    allowlist: Mapping[str, str] = field(
        default_factory=lambda: MappingProxyType(
            {
                "D100": "a snippet is not a module, so it has no module docstring",
                "D103": (
                    "a snippet's function shows one rule, and the chapter around it "
                    "is its documentation"
                ),
                "INP001": (
                    "a snippet is a file of its own, in no package, with no "
                    "`__init__.py` beside it"
                ),
                "N999": (
                    "a snippet's file is named by the harness, so its module name "
                    "says nothing a reader chose"
                ),
                "S101": (
                    "a snippet's tests assert as pytest's do, in a file no test "
                    "path exempts"
                ),
                "PLR2004": (
                    "a snippet's literals are its example's values, and naming each "
                    "would bury the line the rule is about"
                ),
            }
        )
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

    def ruff_args(self, shipped: Path | None = None) -> list[str]:
        """The `ruff check` arguments that apply this selection.

        Given the configuration a normalised standard ships, that
        configuration less the allowlist; otherwise the narrower
        selection declared here.
        """
        if shipped is not None:
            return [
                "--no-cache",
                "--config",
                str(shipped),
                f"--ignore={','.join(self.allowlist)}",
                "--output-format=concise",
            ]
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

#: A name a probe can look up: a module, then its attributes.
DOTTED = re.compile(r"[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*")

#: What looks a name up on the pinned interpreter: exits 0 when it
#: resolves, 1 when it does not, 2 when an import raised otherwise.
PROBE = """\
import builtins, importlib, sys
parts = sys.argv[1].split(".")
found, rest = builtins, parts
try:
    for i in range(len(parts), 0, -1):
        try:
            found = importlib.import_module(".".join(parts[:i]))
        except ImportError:
            continue
        rest = parts[i:]
        break
    for name in rest:
        if not hasattr(found, name):
            sys.exit(1)
        found = getattr(found, name)
except Exception:
    sys.exit(2)
"""

#: The type checker's configuration, written into the extraction. Its
#: diagnostics are asked for as `path:line:col: CODE message`, the one
#: output shape both tools share, and the only `ty` format that keeps
#: warn distinct from error.
TY_CONFIG = "ty.toml"


def _last_line(ran: Ran) -> str:
    """The last unindented line of a failed run: the exception raised.

    A traceback, or pytest's report, ends in what went wrong.
    """
    detail = (ran.err or ran.out).strip().split("\n")
    last = next(
        (ln for ln in reversed(detail) if ln.strip() and not ln.startswith(" ")),
        detail[-1] if detail else "",
    )
    return last.strip() or f"exited {ran.rc} and said nothing"


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
    mutant_timeout: float = 60
    #: What a sealed temporary directory cannot give a block: the
    #: network, the clock, stdin. Such a block is not eligible to be
    #: `# verified`; the rule that shows it marks it `# fragment`.
    #: Checked rather than trusted, because "it worked on my machine"
    #: is exactly the claim `# verified` is supposed to replace.
    outside: re.Pattern[str] | None = re.compile(
        r"\b(urlopen|requests\.|socket\.|time\.sleep|input\()"
    )

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
        """Write each verified block to a file, and `ty.toml`.

        The type checker's configuration is the skill's own snippet's,
        written beside the blocks it judges.
        """
        out = out.resolve()
        out.mkdir(parents=True, exist_ok=True)
        for stale in out.glob("*.py"):
            stale.unlink()
        (out / TY_CONFIG).write_text(_snippet(skill).ty_config())

        ex = Extraction(out, skill)
        seen: Counter[str] = Counter()
        for b in extracted(skill, LANGUAGE):
            stem = Path(b.file).stem.replace("-", "_")
            path = out / f"{stem}_{seen[stem]:03d}{LANGUAGE.suffix}"
            seen[stem] += 1
            path.write_text(b.body)
            ex.units.append(Unit(path, b))
        return ex

    def restore(self, ex: Extraction) -> dict[Block, str]:
        """Each block's file, as it stands: nothing was added to it."""
        return {u.block: u.path.read_text() for u in ex.units}

    def steps(self, ex: Extraction) -> Iterator[Step]:
        """Run each block, then type-check and lint them all.

        Execution covers what runs; `ty` covers what does not.
        """
        for unit in ex.units:
            if LANGUAGE.tests(unit.block.body):
                yield self.tests(ex, unit)
            else:
                # cwd is the extraction directory, so a block that
                # writes a file writes it somewhere the run owns and the
                # caller deletes.
                yield Step(
                    "runs",
                    (str(PYTHON), unit.path.name),
                    ex.root,
                    120,
                    unit=unit,
                    said=_last_line,
                )
        snippet = _snippet(ex.skill)
        config = str(ex.root / TY_CONFIG)
        ty = ("ty", "check", "--config-file", config, "--python", str(VENV))
        yield Step("ty", (*ty, str(ex.root)), ex.root, 300, diagnostics=True)
        shipped = _shipped(ex.skill)
        linted = (str(ex.root),)
        if shipped is not None:
            # Evidence shows the shape a rule forbids, and the shipped
            # configuration forbids it too: only advice is held to it.
            advice = (u for u in ex.units if not u.block.marker.evidence)
            linted = tuple(str(u.path) for u in advice)
        if linted:
            ruff = ("ruff", "check", *snippet.ruff_args(shipped), *linted)
            yield Step("ruff", ruff, ex.root, 300, diagnostics=True)

    def formatter(self, ex: Extraction) -> Step:
        """`ruff format`, under the configuration the skill ships."""
        shipped = ex.skill.root / RUFF_TOML
        config = ("--config", str(shipped)) if shipped.exists() else ("--isolated",)
        return Step(
            "ruff format",
            ("ruff", "format", "--no-cache", *config, str(ex.root)),
            ex.root,
            300,
        )

    def tests(self, ex: Extraction, unit: Unit) -> Step:
        """`pytest` over the unit's file."""
        pytest = (str(PYTHON), "-m", "pytest", "-q", "-p", "no:cacheprovider")
        return Step(
            "tests", (*pytest, unit.path.name), ex.root, 120, unit=unit, said=_last_line
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
        yield from _interpreter_pin(skill, interpreter)

    def asset(self, path: Path, where: Location) -> Iterator[Finding]:  # noqa: ARG002 — no asset is Python's to read
        """Nothing: `assets` builds a `pyproject.toml` as any other."""
        return iter(())

    def probe(self, skill: Skill, spelling: str, out: Path) -> Step | None:  # noqa: ARG002 — one interpreter for every skill
        """Import the longest module the name opens with, then the rest.

        On the pinned interpreter: `glob.glob0` imports `glob` and asks
        it for `glob0`. A name no module opens with is a builtin's:
        `str.removeprefix`. Only a dotted name is looked up; a call
        shape or a command line is not a name.
        """
        name = spelling.removesuffix("()")
        if not DOTTED.fullmatch(name):
            return None
        return Step("probe", (str(PYTHON), "-I", "-c", PROBE, name), out, 60)

    def excused(self, skill: Skill) -> Mapping[str, str]:
        """What `skill`'s examples are excused from, and why."""
        return _snippet(skill).allowlist

    def configured(self, skill: Skill) -> dict[tuple[str, str], str]:
        """Each `ty` rule the shipped `ty.toml` sets, at its level.

        ruff's codes are not set one by one: the shipped `ruff.toml`
        selects all of them and turns some off, and a row states what a
        lint forbids at a level that fails a run.
        """
        ty_toml = skill.asset(TY_TOML)
        if not ty_toml.exists():
            return {}
        rules = tomllib.loads(ty_toml.read_text()).get("rules", {})
        return {("ty", str(name)): str(level) for name, level in rules.items()}


def _shipped(skill: Skill) -> Path | None:
    """The `ruff.toml` a normalised standard's examples are linted with.

    None while the standard is not normalised, or ships none: its
    examples are linted with the selection its snippet declares.
    """
    shipped = skill.asset(RUFF_TOML).resolve()
    return shipped if skill.profile.normalized and shipped.exists() else None


def _snippet(skill: Skill) -> PythonSnippet:
    """How `skill`'s examples are checked: its profile's snippet."""
    config = skill.profile.toolchain
    if not isinstance(config, PythonSnippet):
        msg = f"{skill.name} is checked as Python and its profile names no snippet"
        raise TypeError(msg)
    return config


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

#: How many parts of a `uv python list` key name the platform after the
#: release: the system, the architecture, the C library.
_PLATFORM = 3


def listed(key: str) -> tuple[str, str, str] | None:
    """The interpreter, release and build a `uv python list` key names.

    `cpython-3.15.0rc1+freethreaded-macos-aarch64-none` is (`cpython`,
    `3.15.0rc1`, `freethreaded`): the request an interpreter pin is
    spelled as, then the platform. None for a key not of that shape.
    The release is left as text, because one that is not a version is
    reported rather than passed over.
    """
    request, *platform = key.rsplit("-", _PLATFORM)
    implementation, dash, version = request.partition("-")
    if len(platform) != _PLATFORM or not dash:
        return None
    release, _, build = version.partition("+")
    return implementation, release, build


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
        yield from cooldown(project, skill.at(PROJECT))


def cooldown(project: dict[str, Any], where: Location) -> Iterator[Finding]:
    """PS-BUILD-11 over a `pyproject.toml`: the week, and who skips it.

    Nothing is locked younger than `exclude-newer`, except by name the
    dependencies pinned with `==`: an exact pin is a review written
    down. So the exempt names and the exact pins are one set, and a
    difference either way is the finding — an exact pin left waiting,
    or a floating requirement let through. The shipped template and the
    harness's own project are both held to it.
    """
    uv = project.get("tool", {}).get("uv", {})
    if "exclude-newer" not in uv:
        yield fail(
            "has no `exclude-newer` under `[tool.uv]`, so a release published "
            "an hour ago can be locked",
            where,
            COOLDOWN_MISSING,
        )
        return
    exempt = {
        name.lower().replace("_", "-")
        for name, waits in uv.get("exclude-newer-package", {}).items()
        if waits is False
    }
    exact = set()
    for requirement in _requirements(project):
        m = REQUIREMENT.match(requirement)
        spec = "".join(m["spec"].split()) if m else ""
        if m and spec.startswith("==") and "," not in spec:
            exact.add(m["name"].lower().replace("_", "-"))
    if exempt != exact:
        waiting, floating = sorted(exact - exempt), sorted(exempt - exact)
        yield fail(
            f"exempts {sorted(exempt)} from the cooldown where the `==` pins are "
            f"{sorted(exact)}: pinned but waiting {waiting}, exempt but "
            f"floating {floating}",
            where,
            COOLDOWN_EXEMPT,
        )


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


def _interpreter_pin(skill: Skill, interpreter: Pin) -> Iterator[Finding]:
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

    pinned = interpreter.version.public
    here = Version.released(str(pinned))
    if here is None:
        # `tests/test_profiles.py` holds every interpreter pin to a
        # release this orders, so this is the harness misdeclared.
        msg = f"the interpreter pin {pinned} is not a release this can order"
        raise ValueError(msg)

    # Scoped to the pinned minor series on purpose: a newer patch or
    # candidate is a pin refresh, and a newer *minor* is a deliberate
    # change of target that this check has no business demanding.
    series = here.series
    newer, unreadable = _releases(r.out, interpreter, here)
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
    listing: str, interpreter: Pin, here: Version
) -> tuple[dict[str, Version], set[str]]:
    """Newer releases in `here`'s series, and any it cannot order.

    Of the interpreter and build `interpreter` names. Newer ones map to
    their order, so the best is picked without ordering by a key
    function that is allowed to answer `None`.
    """
    newer: dict[str, Version] = {}
    unreadable: set[str] = set()
    within = f"{here.series}."
    for line in listing.split("\n"):
        key = line.split(maxsplit=1)[0] if line.strip() else ""
        found = listed(key)
        if found is None:
            continue
        implementation, version, build = found
        if (implementation, build) != (interpreter.tool, interpreter.version.local):
            continue
        if not version.startswith(within):
            continue
        # Scoped to the pinned series, so this reports what it could not
        # rule out rather than every oddity in a list of every CPython
        # ever built.
        order = Version.released(version)
        if order is None:
            unreadable.add(version)
        elif order > here:
            newer[version] = order
    return newer, unreadable


PYTHON_TOOLCHAIN = Python()
