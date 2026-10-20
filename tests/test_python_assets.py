"""The shipped Python configuration must mean what the standard says it means.

Every case here is a claim the standard makes in prose. A claim nobody runs is a
claim that stops being true without anyone noticing.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
RUFF_TOML = REPO / "skills" / "python-style" / "assets" / "ruff.toml"
RUFF = REPO / ".venv" / "bin" / "ruff"

pytestmark = pytest.mark.skipif(not RUFF.exists(), reason="the pinned ruff is not installed")


def enabled(config: Path, cwd: Path) -> set[str]:
    """Every code ruff resolves as enabled, as ruff itself reports them."""
    out = subprocess.run(
        [str(RUFF), "check", "--no-cache", "--config", str(config), "--show-settings", "."],
        cwd=cwd,
        capture_output=True,
        text=True,
    ).stdout
    codes, inside = set(), False
    for line in out.split("\n"):
        if line.startswith("linter.rules.enabled = ["):
            inside = True
        elif inside:
            if line.startswith("]"):
                break
            if m := re.search(r"\(([A-Z]+[0-9]+)\)", line):
                codes.add(m.group(1))
    return codes


def test_no_preview_rule_is_enabled(tmp_path):
    """The asset runs stable rules only, which is what lets a rule cite a code as enforced.

    A preview rule can change or vanish in any release; one enabled here would make
    the standard's enforcement depend on which ruff happened to run.
    """
    import json

    (tmp_path / "m.py").write_text("x = 1\n")
    rules = json.loads(
        subprocess.run(
            [str(RUFF), "rule", "--all", "--output-format", "json"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    )
    preview = {rule["code"] for rule in rules if "Preview" in str(rule.get("status", ""))}
    assert preview, "no preview rule found, so this test proves nothing"
    assert not (enabled(RUFF_TOML, tmp_path) & preview)


def test_py315_target_does_not_warn(tmp_path):
    """A warning on every run is a warning nobody reads."""
    (tmp_path / "m.py").write_text("x = 1\n")
    r = subprocess.run(
        [str(RUFF), "check", "--no-cache", "--config", str(RUFF_TOML), "m.py"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert "under development" not in (r.stdout + r.stderr)


#: Ruff's own documented list of rules that conflict with its formatter.
#: https://docs.astral.sh/ruff/formatter/#conflicting-lint-rules
FORMATTER_CONFLICTS = frozenset(
    """W191 E111 E114 E117 D203 D206 D300 Q000 Q001 Q002 Q003 Q004
       COM812 COM819 ISC002""".split()
)


def test_no_formatter_conflicting_rule_is_enabled(tmp_path):
    """Checked against ruff's documented list, not against `ruff format --check`.

    Of the fifteen, only COM812 and D203 actually make `ruff format` warn under
    default formatter settings — so a config that disabled just those two would
    pass the "zero stderr" test while leaving thirteen conflicts enabled.
    """
    (tmp_path / "m.py").write_text("x = 1\n")
    assert not (enabled(RUFF_TOML, tmp_path) & FORMATTER_CONFLICTS)


def test_isc001_is_enabled_because_it_is_not_a_conflict(tmp_path):
    """A belief worth pinning: older documentation listed ISC001 as conflicting.

    Current ruff does not, and its ISC002 documentation actively recommends
    enabling ISC001. The asset's `allow-multiline = false` is only safe with it.
    """
    (tmp_path / "m.py").write_text("x = 1\n")
    assert "ISC001" in enabled(RUFF_TOML, tmp_path)


def test_e501_is_enabled_as_the_line_length_backstop(tmp_path):
    """The formatter makes only a best-effort attempt at the limit."""
    (tmp_path / "m.py").write_text("x = 1\n")
    assert "E501" in enabled(RUFF_TOML, tmp_path)
