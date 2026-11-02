"""A rule's check must be one the shipped config actually turns on.

`lints` already does this for Rust, comparing the crate's declared table
against the shipped `Cargo.toml`. Python needs a second comparison the
Rust side never had: this standard cites its checks by tool code, so a
rule can name a code the asset disables — or one the tool withdrew — and
read as enforced while nothing enforces it.

The reverse direction is deliberately absent. The asset selects `ALL`,
so the enabled set is most of ruff's catalogue and the standard cites a
fraction of it; "enabled but uncited" is the normal case rather than a
defect.
"""

import json
import re
import tempfile
import tomllib
from functools import cache
from pathlib import Path
lazy from collections.abc import Callable, Iterable, Iterator, Mapping

from agent_skill.checks import check, per_skill
from agent_skill.ids import Branch
from agent_skill.lang.python import PYTHON_STYLE
from agent_skill.lang.zig import force_analysis
from agent_skill.proc import have, run
from agent_skill.report import fail, unrun
from agent_skill.text import group
lazy from agent_skill.checks.lints import CARGO, table
lazy from agent_skill.ids import Location
lazy from agent_skill.model import LintRow, Skill
lazy from agent_skill.report import Finding

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

# The branches a finding of this check comes from.
ROW_TOOL = Branch("citations", "row_tool")
ROW_LEVEL = Branch("citations", "row_level")
RUFF_ABSENT = Branch("citations", "ruff_absent")
TY_ABSENT = Branch("citations", "ty_absent")
TY_UNKNOWN_SETTING = Branch("citations", "ty_unknown_setting")
ENABLED_UNREAD = Branch("citations", "enabled_unread")
TY_RULES_UNREAD = Branch("citations", "ty_rules_unread")
RUFF_ROW_DISABLED = Branch("citations", "ruff_row_disabled")
TY_ROW_UNKNOWN = Branch("citations", "ty_row_unknown")
TY_ROW_LEVEL = Branch("citations", "ty_row_level")
CATALOGUE_UNREAD = Branch("citations", "catalogue_unread")
UNKNOWN_CODE = Branch("citations", "unknown_code")
WITHDRAWN_CODE = Branch("citations", "withdrawn_code")
DISABLED_CODE = Branch("citations", "disabled_code")
TY_UNVERIFIED = Branch("citations", "ty_unverified")
TY_UNSHIPPED = Branch("citations", "ty_unshipped")
TY_LEVEL = Branch("citations", "ty_level")
RUST_TOOL_ABSENT = Branch("citations", "rust_tool_absent")
NO_CARGO_TOML = Branch("citations", "no_cargo_toml")
RUST_CATALOGUE_UNREAD = Branch("citations", "rust_catalogue_unread")
RUST_UNKNOWN_LINT = Branch("citations", "rust_unknown_lint")
RUST_LEVEL = Branch("citations", "rust_level")
ZIG_ABSENT = Branch("citations", "zig_absent")
ZIG_NO_PROBE = Branch("citations", "zig_no_probe")
ZIG_PROBE_COMPILES = Branch("citations", "zig_probe_compiles")
ZIG_PROBE_OTHER = Branch("citations", "zig_probe_other")
ZIG_PROBE_NO_ROW = Branch("citations", "zig_probe_no_row")


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


#: The levels a `Decided by tools` row may state, per tool: the ones at
#: which the tool fails a run. A row at a level that lets the run pass
#: is a lint nothing enforces, which is a rule with its Why and Check
#: deleted.
LEVELS: dict[str, frozenset[str]] = {
    "ruff": frozenset({"error"}),
    "ty": frozenset({"error", "warn"}),
    "rustc": frozenset({"warn", "deny", "forbid"}),
    "clippy": frozenset({"warn", "deny", "forbid"}),
    "rustdoc": frozenset({"warn", "deny", "forbid"}),
    # A compile error has one level: the build stops.
    "zig": frozenset({"error"}),
}


def row_shape(rows: Iterable[LintRow], tools: tuple[str, ...]) -> Iterator[Finding]:
    """Each row whose tool or level enforces nothing.

    Such a row names a tool the standard does not require, or a level at
    which the tool would let the run pass.
    """
    for row in rows:
        if row.tool not in tools or row.tool not in LEVELS:
            yield fail(
                f"`{row.tool}` is not a tool this standard requires",
                row.where,
                ROW_TOOL,
            )
        elif row.level not in LEVELS[row.tool]:
            levels = " / ".join(sorted(LEVELS[row.tool]))
            yield fail(
                f"`{row.lint}` at `{row.level}` fails no run; a row is one of {levels}",
                row.where,
                ROW_LEVEL,
            )


def python_rows(
    rows: Iterable[LintRow], enabled: set[str], ty_levels: dict[str, str]
) -> Iterator[Finding]:
    """Each python row not enforced as the row states.

    The shipped configuration is what enforces them. `ty_levels` is
    every rule ty knows, at the level the asset leaves it — its own
    entry, or the default.
    """
    for row in rows:
        if row.tool == "ruff" and row.lint not in enabled:
            yield fail(
                f"`{row.lint}` is a row, and `{RUFF_TOML}` does not enable it",
                row.where,
                RUFF_ROW_DISABLED,
            )
        elif row.tool == "ty":
            level = ty_levels.get(row.lint)
            if level is None:
                yield fail(
                    f"`{row.lint}` is not a rule the pinned ty recognises",
                    row.where,
                    TY_ROW_UNKNOWN,
                )
            elif level != row.level:
                yield fail(
                    f"`{row.lint}` is `{row.level}` in the row "
                    f"and `{level}` as shipped",
                    row.where,
                    TY_ROW_LEVEL,
                )


#: The `[lints]` table each Rust row's tool is configured under.
SECTION = {"rustc": "rust", "clippy": "clippy", "rustdoc": "rustdoc"}


def rust_rows(
    rows: Iterable[LintRow],
    shipped: dict[str, str],
    catalogue: dict[str, tuple[str, set[str]]],
) -> Iterator[Finding]:
    """Each Rust row not enforced as the row states.

    The shipped `[workspace.lints]` is what enforces them. `shipped` is
    the asset's table as `lints.table` reads it (`clippy.unwrap_used` ->
    `"deny"`). `catalogue` maps every lint the pinned toolchain knows,
    spelled as a `[lints]` key under its tool's section, to its default
    level and its groups. A lint's level is its own entry, else the
    entry of a group it belongs to, else its default — the order Cargo
    applies them in, given the groups' `priority = -1`.
    """
    for row in rows:
        section = SECTION.get(row.tool)
        if section is None:
            continue
        key = f"{section}.{row.lint}"
        if key not in catalogue:
            yield fail(
                f"`{row.lint}` is not a {row.tool} lint the pinned toolchain knows",
                row.where,
                RUST_UNKNOWN_LINT,
            )
            continue
        default, groups = catalogue[key]
        level = _level(shipped.get(key, "")) or next(
            (
                _level(shipped[f"{section}.{g}"])
                for g in sorted(groups)
                if f"{section}.{g}" in shipped
            ),
            default,
        )
        if level != row.level:
            yield fail(
                f"`{row.lint}` is `{row.level}` in the row and `{level}` as shipped",
                row.where,
                RUST_LEVEL,
            )


def _level(value: str) -> str:
    return group(re.search(r'"(allow|warn|deny|forbid)"', value))


def rust_catalogue() -> dict[str, tuple[str, set[str]]] | None:
    """Every lint the Rust toolchain knows, keyed as a `[lints]` entry.

    As `clippy-driver` and `rustdoc` list them; None when either cannot.
    """
    out: dict[str, tuple[str, set[str]]] = {}
    members: dict[str, set[str]] = {}
    for tool in ("clippy-driver", "rustdoc"):
        if not have(tool):
            return None
        answered = run([tool, "-W", "help"], timeout=60)
        if not answered.ok:
            return None
        _read_help(answered.out, out, members)
    for key, groups in members.items():
        if key in out:
            out[key] = (out[key][0], out[key][1] | groups)
    return out


def _read_help(
    text: str,
    out: dict[str, tuple[str, set[str]]],
    members: dict[str, set[str]],
) -> None:
    """Fold one tool's `-W help` listing into `out` and `members`."""
    section = "lints"
    for line in text.split("\n"):
        if line.startswith("Lint groups"):
            section = "groups"
        elif line.startswith("Lint checks"):
            section = "lints"
        if section == "lints":
            if m := re.match(r"^\s+(\S+)\s+(allow|warn|deny|forbid)\s", line):
                out[_key(m.group(1))] = (m.group(2), set())
        elif m := re.match(r"^\s+(\S+)\s+(\S.*)$", line):
            group, names = _key(m.group(1)), m.group(2)
            for name in names.split(", "):
                members.setdefault(_key(name.strip()), set()).add(
                    group.split(".", 1)[1]
                )


def _key(name: str) -> str:
    """A lint's name, spelled as a `[lints]` key.

    `clippy::unwrap-used` -> `clippy.unwrap_used`; `unsafe-code` ->
    `rust.unsafe_code`.
    """
    tool, _, lint = name.rpartition("::")
    return f"{tool or 'rust'}.{lint.replace('-', '_')}"


@check(
    "citations",
    "a cited check must be one the shipped config enables",
    needs=("ruff", "ty", "clippy-driver", "rustdoc", "zig"),
)
@per_skill
def citations(skill: Skill) -> Iterator[Finding]:
    """Every lint row and cited code, against the shipped config."""
    yield from row_shape(skill.lint_rows, skill.profile.tools)
    if skill.profile.toolchain == "rust":
        yield from _rust(skill)
    if skill.profile.toolchain == "zig":
        yield from _zig(skill)
    if skill.profile.toolchain != "python":
        return
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

    yield from _python(skill, ruff_toml, ty_toml)

    # The harness declares the ty levels it verifies under; the asset
    # ships one for the reader. Two tables, compared — an asset that
    # were also the configuration in force could not be checked against
    # anything.
    shipped = tomllib.loads(ty_toml.read_text()).get("rules", {})
    yield from _ty_tables(skill, shipped)

    if not have("ty"):
        yield unrun(
            "`ty` is not on PATH, so no rule name was validated", skill.at(), TY_ABSENT
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


def _python(skill: Skill, ruff_toml: Path, ty_toml: Path) -> Iterator[Finding]:
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
    yield from python_rows(skill.lint_rows, enabled, ty_levels)

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
    cited = {rule.id: _codes_in(rule.body, catalogue) for rule in skill.rules}
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


def _ty_tables(skill: Skill, shipped: Mapping[str, object]) -> Iterator[Finding]:
    """The asset's ty levels, against those the harness verifies."""
    declared = PYTHON_STYLE.ty_rules
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


def _rust(skill: Skill) -> Iterator[Finding]:
    """The Rust rows, against the shipped `[workspace.lints]`."""
    # Asked before looking for rows: a check that declares a tool and
    # returns early without it reports clean while it could not have
    # looked.
    for tool in ("clippy-driver", "rustdoc"):
        if not have(tool):
            yield unrun(
                f"`{tool}` is not available, so no Rust lint row was compared",
                skill.at(),
                RUST_TOOL_ABSENT,
            )
            return
    rows = [row for row in skill.lint_rows if row.tool in SECTION]
    manifest = skill.root / CARGO
    if not rows:
        return
    if not manifest.exists():
        yield fail(
            f"Rust lint rows, and no `{CARGO}` to enforce them",
            skill.at(),
            NO_CARGO_TOML,
        )
        return
    catalogue = rust_catalogue()
    if catalogue is None:
        yield unrun(
            "`clippy-driver` or `rustdoc` did not list its lints",
            skill.at(),
            RUST_CATALOGUE_UNREAD,
        )
        return

    shipped = table(manifest.read_text(), "workspace.")
    yield from rust_rows(rows, shipped, catalogue)


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
    rows: Iterable[LintRow],
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
    cited = {row.lint for row in rows}
    for row in rows:
        source = probes.get(row.lint)
        if source is None:
            yield fail(
                f"`{row.lint}` has no probe, so nothing shows the compiler reports it",
                row.where,
                ZIG_NO_PROBE,
            )
            continue
        errors = compile_errors(source)
        if errors is None:
            yield fail(
                f"`{row.lint}`: its probe compiles, so the compiler does not report it",
                row.where,
                ZIG_PROBE_COMPILES,
            )
        elif not any(phrase(row.lint).search(line) for line in errors):
            printed = errors[0] if errors else "no error line"
            yield fail(
                f"`{row.lint}`: its probe fails with `{printed}` instead",
                row.where,
                ZIG_PROBE_OTHER,
            )
    for lint in sorted(set(probes) - cited):
        yield fail(
            f"the probe for `{lint}` has no row in any chapter",
            profile,
            ZIG_PROBE_NO_ROW,
        )


def _compile_zig(source: str) -> list[str] | None:
    """The `error:` lines zig prints for `source`; None if it builds."""
    with tempfile.TemporaryDirectory() as work:
        probe = Path(work) / "probe.zig"
        probe.write_text(source.rstrip("\n") + "\n" + force_analysis(source))
        r = run(["zig", "build-obj", probe.name, "-fno-emit-bin"], cwd=Path(work))
    if r.ok:
        return None
    return [line for line in r.err.splitlines() if "error:" in line]


def _zig(skill: Skill) -> Iterator[Finding]:
    """The compiler rows, each against the probe that proves it."""
    # Asked before looking for rows, as `_rust` does.
    if not have("zig"):
        yield unrun(
            "`zig` is not on PATH, so no compiler row was proved",
            skill.at(),
            ZIG_ABSENT,
        )
        return
    rows = [row for row in skill.lint_rows if row.tool == "zig"]
    yield from zig_rows(rows, skill.profile.probes, _compile_zig, skill.at())
