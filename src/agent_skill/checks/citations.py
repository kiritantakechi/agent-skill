"""A rule's check must be one the shipped configuration actually turns on.

`lints` already does this for Rust, comparing the crate's declared table against
the shipped `Cargo.toml`. Python needs a second comparison the Rust side never
had: this standard cites its checks by tool code, so a rule can name a code the
asset disables — or one the tool withdrew — and read as enforced while nothing
enforces it.

The reverse direction is deliberately absent. The asset selects `ALL`, so the
enabled set is 786 codes and the standard cites a handful; "enabled but uncited"
is the normal case rather than a defect.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

from ..lang.python import PYTHON_STYLE
from ..proc import have, run
from ..report import fail, unrun
from . import check

#: `PS-FT-02` and `3.15` are not ruff codes; `ANN401` and `B008` are.
#: `ASYNC251` is five letters, and a cap of four hid every citation of that
#: family — including one to a code that does not exist.
CODE = re.compile(r"(?<![A-Za-z0-9-])([A-Z]{1,5}[0-9]{3,4})(?![0-9])")

#: Prefixes that are ruff linters. Anything else matching the shape is prose.
LINTERS = frozenset(
    "A AIR ANN ARG ASYNC B BLE C4 C90 COM CPY D DJ DOC DTZ E EM ERA EXE F FA FAST FBT FIX FLY "
    "FURB G I ICN INP INT ISC LOG N NPY PD PERF PGH PIE PLC PLE PLR PLW PT PTH PYI Q RET RSE RUF "
    "S SIM SLF SLOT T10 T20 TC TD TID TRY UP W YTT".split()
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
        ["ruff", "check", "--no-cache", "--config", str(config), "--show-settings", "."],
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


def _withdrawn() -> set[str]:
    """Codes ruff has removed. Selecting one is a hard failure, not a warning."""
    r = run(["ruff", "rule", "--all", "--output-format", "json"], timeout=120)
    if not r.ok:
        return set()
    import json

    return {rule["code"] for rule in json.loads(r.out) if "Removed" in str(rule.get("status", ""))}


@check("citations", "a cited check must be one the shipped config enables", needs=("ruff", "ty"))
def citations(skill):
    if skill.profile.toolchain != "python":
        return
    assets = skill.root / "assets"
    ruff_toml, ty_toml = assets / "ruff.toml", assets / "ty.toml"
    if not ruff_toml.exists() or not ty_toml.exists():
        return
    if not have("ruff"):
        yield unrun("`ruff` is not on PATH, so nothing compared the citations", skill.name)
        return

    # A rule's own body is where it cites its checks; the `**Check:**` section is
    # part of it. Core rules in SKILL.md point at the chapter that owns them, so
    # they carry no citation of their own.
    cited = {rule.id: _codes_in(rule.body) for rule in skill.rules}

    enabled, problem = _enabled(ruff_toml)
    if problem:
        yield unrun(f"could not read the enabled set: {problem}", skill.name)
    else:
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
        yield fail(f"assets/ty.toml enables `{name}` that the harness does not verify", skill.name)
    for name in sorted(set(declared) - set(shipped)):
        yield fail(f"the harness verifies `{name}` that assets/ty.toml does not ship", skill.name)
    for name in sorted(set(shipped) & set(declared)):
        if shipped[name] != declared[name]:
            yield fail(
                f"`{name}` is {shipped[name]!r} in the asset and {declared[name]!r} in the harness",
                skill.name,
            )

    if not have("ty"):
        yield unrun("`ty` is not on PATH, so no rule name was validated", skill.name)
        return
    r = run(["ty", "explain", "rule", "--output-format", "json"], timeout=120)
    if r.ok and r.out:
        import json

        known = {rule["name"] for rule in json.loads(r.out)}
        for name in sorted(set(shipped) - known):
            yield fail(
                f"assets/ty.toml names `{name}`, which the pinned ty does not recognise — the "
                f"setting silently does nothing",
                skill.name,
            )
