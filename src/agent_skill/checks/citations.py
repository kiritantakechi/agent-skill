"""A rule's check must be one the shipped configuration actually turns on.

`lints` already does this for Rust, comparing the crate's declared table against
the shipped `Cargo.toml`. Python needs a second comparison the Rust side never
had: this standard cites its checks by tool code, so a rule can name a code the
asset disables — or one the tool withdrew — and read as enforced while nothing
enforces it.

The reverse direction is deliberately absent. The asset selects `ALL`, so the
enabled set is most of ruff's catalogue and the standard cites a fraction of it;
"enabled but uncited" is the normal case rather than a defect.
"""

import json
import re
import tomllib
from functools import cache
from pathlib import Path

from agent_skill.checks import check
from agent_skill.lang.python import PYTHON_STYLE
from agent_skill.proc import have, run
from agent_skill.report import fail, unrun
lazy from agent_skill.checks.lints import table

#: `PS-CONC-02` and `3.15` are not ruff codes; `ANN401` and `B008` are.
#: `ASYNC251` is five letters, and a cap of four hid every citation of that
#: family — including one to a code that does not exist.
CODE = re.compile(r"(?<![A-Za-z0-9-])([A-Z]{1,5}[0-9]{3,4})(?![0-9])")

#: Prefixes that are ruff linters. Anything else matching the shape is prose.
LINTERS = frozenset(
    [
        "A",
        "AIR",
        "ANN",
        "ARG",
        "ASYNC",
        "B",
        "BLE",
        "C4",
        "C90",
        "COM",
        "CPY",
        "D",
        "DJ",
        "DOC",
        "DTZ",
        "E",
        "EM",
        "ERA",
        "EXE",
        "F",
        "FA",
        "FAST",
        "FBT",
        "FIX",
        "FLY",
        "FURB",
        "G",
        "I",
        "ICN",
        "INP",
        "INT",
        "ISC",
        "LOG",
        "N",
        "NPY",
        "PD",
        "PERF",
        "PGH",
        "PIE",
        "PLC",
        "PLE",
        "PLR",
        "PLW",
        "PT",
        "PTH",
        "PYI",
        "Q",
        "RET",
        "RSE",
        "RUF",
        "S",
        "SIM",
        "SLF",
        "SLOT",
        "T10",
        "T20",
        "TC",
        "TD",
        "TID",
        "TRY",
        "UP",
        "W",
        "YTT",
    ]
)


def _codes_in(text: str) -> set[str]:
    return {
        code
        for code in CODE.findall(text)
        if re.match(r"^[A-Z]+", code).group(0) in LINTERS  # type: ignore[union-attr]
    }


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
    codes, inside = set(), False
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
    """Every rule the pinned ty knows, with its default level; None if ty would not say."""
    r = run(["ty", "explain", "rule", "--output-format", "json"], timeout=120)
    if not r.ok or not r.out:
        return None
    return {rule["name"]: rule["default_level"] for rule in json.loads(r.out)}


def _ty_levels(ty_toml: Path) -> dict[str, str] | None:
    """Every rule the pinned ty knows, at the level the shipped asset leaves it."""
    if (rules := _ty_rules()) is None:
        return None
    shipped = tomllib.loads(ty_toml.read_text()).get("rules", {})
    return {name: shipped.get(name, level) for name, level in rules.items()}


def _withdrawn() -> set[str]:
    """Codes ruff has removed. Selecting one is a hard failure, not a warning."""
    r = run(["ruff", "rule", "--all", "--output-format", "json"], timeout=120)
    if not r.ok:
        return set()
    return {
        rule["code"]
        for rule in json.loads(r.out)
        if "Removed" in str(rule.get("status", ""))
    }


#: The levels a `Decided by tools` row may state, per tool: the ones at which the
#: tool fails a run. A row at a level that lets the run pass is a lint nothing
#: enforces, which is a rule with its Why and Check deleted.
LEVELS: dict[str, frozenset[str]] = {
    "ruff": frozenset({"error"}),
    "ty": frozenset({"error", "warn"}),
    "rustc": frozenset({"warn", "deny", "forbid"}),
    "clippy": frozenset({"warn", "deny", "forbid"}),
    "rustdoc": frozenset({"warn", "deny", "forbid"}),
}


def row_shape(rows, tools: tuple[str, ...]):
    """(row, message) for rows naming a tool the standard does not require, or a level
    at which the tool would let the run pass.
    """
    for row in rows:
        if row.tool not in tools or row.tool not in LEVELS:
            yield row, f"`{row.tool}` is not a tool this standard requires"
        elif row.level not in LEVELS[row.tool]:
            levels = " / ".join(sorted(LEVELS[row.tool]))
            yield (
                row,
                f"`{row.lint}` at `{row.level}` fails no run; a row is one of {levels}",
            )


def python_rows(rows, enabled: set[str], ty_levels: dict[str, str]):
    """(row, message) for python rows the shipped configuration does not enforce as stated.

    `ty_levels` is every rule ty knows, at the level the asset leaves it — its own
    entry, or the default.
    """
    for row in rows:
        if row.tool == "ruff" and row.lint not in enabled:
            yield (
                row,
                f"`{row.lint}` is a row, and `assets/ruff.toml` does not enable it",
            )
        elif row.tool == "ty":
            level = ty_levels.get(row.lint)
            if level is None:
                yield row, f"`{row.lint}` is not a rule the pinned ty recognises"
            elif level != row.level:
                yield (
                    row,
                    f"`{row.lint}` is `{row.level}` in the row and `{level}` as shipped",
                )


#: The `[lints]` table each Rust row's tool is configured under.
SECTION = {"rustc": "rust", "clippy": "clippy", "rustdoc": "rustdoc"}


def rust_rows(
    rows, shipped: dict[str, str], catalogue: dict[str, tuple[str, set[str]]]
):
    """(row, message) for Rust rows the shipped `[workspace.lints]` does not enforce as stated.

    `shipped` is the asset's table as `lints.table` reads it (`clippy.unwrap_used` ->
    `"deny"`). `catalogue` maps every lint the pinned toolchain knows, spelled as a
    `[lints]` key under its tool's section, to its default level and its groups. A
    lint's level is its own entry, else the entry of a group it belongs to, else its
    default — the order Cargo applies them in, given the groups' `priority = -1`.
    """
    for row in rows:
        section = SECTION.get(row.tool)
        if section is None:
            continue
        key = f"{section}.{row.lint}"
        if key not in catalogue:
            yield (
                row,
                f"`{row.lint}` is not a {row.tool} lint the pinned toolchain knows",
            )
            continue
        default, groups = catalogue[key]
        level = _level(shipped.get(key)) or next(
            (
                _level(shipped[f"{section}.{g}"])
                for g in sorted(groups)
                if f"{section}.{g}" in shipped
            ),
            default,
        )
        if level != row.level:
            yield (
                row,
                f"`{row.lint}` is `{row.level}` in the row and `{level}` as shipped",
            )


def _level(value: str | None) -> str | None:
    if value is None:
        return None
    m = re.search(r'"(allow|warn|deny|forbid)"', value)
    return m.group(1) if m else None


def rust_catalogue() -> dict[str, tuple[str, set[str]]] | None:
    """Every lint `clippy-driver` and `rustdoc` know, keyed as a `[lints]` entry."""
    out: dict[str, tuple[str, set[str]]] = {}
    members: dict[str, set[str]] = {}
    for tool in ("clippy-driver", "rustdoc"):
        if not have(tool):
            return None
        answered = run([tool, "-W", "help"], timeout=60)
        if not answered.ok:
            return None
        section = "lints"
        for line in answered.out.split("\n"):
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
    for key, groups in members.items():
        if key in out:
            out[key] = (out[key][0], out[key][1] | groups)
    return out


def _key(name: str) -> str:
    """`clippy::unwrap-used` -> `clippy.unwrap_used`; `unsafe-code` -> `rust.unsafe_code`."""
    tool, _, lint = name.rpartition("::")
    return f"{tool or 'rust'}.{lint.replace('-', '_')}"


@check(
    "citations",
    "a cited check must be one the shipped config enables",
    needs=("ruff", "ty", "clippy-driver", "rustdoc"),
)
def citations(skill):
    for row, message in row_shape(skill.lint_rows, skill.profile.tools):
        yield fail(message, f"{skill.name}/{row.where}")
    if skill.profile.toolchain == "rust":
        yield from _rust(skill)
    if skill.profile.toolchain != "python":
        return
    assets = skill.root / "assets"
    ruff_toml, ty_toml = assets / "ruff.toml", assets / "ty.toml"
    if not ruff_toml.exists() or not ty_toml.exists():
        return
    if not have("ruff"):
        yield unrun(
            "`ruff` is not on PATH, so nothing compared the citations", skill.name
        )
        return

    # A rule's own body is where it cites its checks; the `**Check:**` section is
    # part of it. Core rules in SKILL.md point at the chapter that owns them, so
    # they carry no citation of their own.
    cited = {rule.id: _codes_in(rule.body) for rule in skill.rules}

    enabled, problem = _enabled(ruff_toml)
    if problem:
        yield unrun(f"could not read the enabled set: {problem}", skill.name)
    else:
        ty_levels = _ty_levels(ty_toml)
        if ty_levels is None:
            yield unrun(
                "`ty` did not list its rules, so no ty row was compared", skill.name
            )
            ty_levels = {}
        for row, message in python_rows(skill.lint_rows, enabled, ty_levels):
            yield fail(message, f"{skill.name}/{row.where}")
        withdrawn = _withdrawn()
        for rule_id, codes in sorted(cited.items()):
            for code in sorted(codes):
                if code in withdrawn:
                    yield fail(
                        f"{rule_id} cites `{code}`, which ruff has withdrawn — selecting it is a "
                        f"hard failure, so the rule can never be enforced",
                        skill.name,
                    )
                elif code not in enabled:
                    yield fail(
                        f"{rule_id} cites `{code}`, which `assets/ruff.toml` does not enable; "
                        f"the rule reads as enforced and is not",
                        skill.name,
                    )

    # The harness declares the ty levels it verifies under; the asset ships one
    # for the reader. Two tables, compared — an asset that were also the
    # configuration in force could not be checked against anything.
    shipped = tomllib.loads(ty_toml.read_text()).get("rules", {})
    declared = PYTHON_STYLE.ty_rules
    for name in sorted(set(shipped) - set(declared)):
        yield fail(
            f"assets/ty.toml enables `{name}` that the harness does not verify",
            skill.name,
        )
    for name in sorted(set(declared) - set(shipped)):
        yield fail(
            f"the harness verifies `{name}` that assets/ty.toml does not ship",
            skill.name,
        )
    for name in sorted(set(shipped) & set(declared)):
        if shipped[name] != declared[name]:
            yield fail(
                f"`{name}` is {shipped[name]!r} in the asset and {declared[name]!r} in the harness",
                skill.name,
            )

    if not have("ty"):
        yield unrun("`ty` is not on PATH, so no rule name was validated", skill.name)
        return
    if (known := _ty_rules()) is not None:
        for name in sorted(set(shipped) - set(known)):
            yield fail(
                f"assets/ty.toml names `{name}`, which the pinned ty does not recognise — the "
                f"setting silently does nothing",
                skill.name,
            )


def _rust(skill):
    # Asked before looking for rows: a check that declares a tool and returns
    # early without it reports clean while it could not have looked.
    for tool in ("clippy-driver", "rustdoc"):
        if not have(tool):
            yield unrun(
                f"`{tool}` is not available, so no Rust lint row was compared",
                skill.name,
            )
            return
    rows = [row for row in skill.lint_rows if row.tool in SECTION]
    manifest = skill.root / "assets" / "Cargo.toml"
    if not rows:
        return
    if not manifest.exists():
        yield fail(
            "Rust lint rows, and no `assets/Cargo.toml` to enforce them", skill.name
        )
        return
    catalogue = rust_catalogue()
    if catalogue is None:
        yield unrun("`clippy-driver` or `rustdoc` did not list its lints", skill.name)
        return

    shipped = table(manifest.read_text(), "workspace.")
    for row, message in rust_rows(rows, shipped, catalogue):
        yield fail(message, f"{skill.name}/{row.where}")
