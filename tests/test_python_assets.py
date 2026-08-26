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


def test_preview_adds_py315_without_adding_rules(tmp_path):
    """`explicit-preview-rules` is what makes the enabled set deterministic.

    Without it, `preview = true` pulls 139 preview rules in through `ALL`, so a
    ruff release could change what the standard enforces without anyone editing
    it. With it, preview buys py315 semantics and nothing else.
    """
    (tmp_path / "m.py").write_text("x = 1\n")
    off = tmp_path / "off.toml"
    off.write_text(RUFF_TOML.read_text().replace("preview = true", "preview = false", 1))
    assert enabled(RUFF_TOML, tmp_path) == enabled(off, tmp_path)


def test_dropping_explicit_preview_rules_would_change_the_enabled_set(tmp_path):
    """The negative control for the test above: prove the guard is load-bearing."""
    (tmp_path / "m.py").write_text("x = 1\n")
    loose = tmp_path / "loose.toml"
    loose.write_text(RUFF_TOML.read_text().replace("explicit-preview-rules = true", "", 1))
    assert enabled(loose, tmp_path) > enabled(RUFF_TOML, tmp_path)


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


def test_output_prefer_rule_codes_is_top_level(tmp_path):
    """It is a hard config parse error under `[lint]`, and nothing says so."""
    (tmp_path / "m.py").write_text("x = 1\n")
    moved = tmp_path / "moved.toml"
    # Anchor on the section header, not the word: the asset's own comment
    # mentions `[lint]` while explaining exactly this trap.
    moved.write_text(
        RUFF_TOML.read_text()
        .replace("\noutput-prefer-rule-codes = true", "", 1)
        .replace("\n[lint]\n", "\n[lint]\noutput-prefer-rule-codes = true\n", 1)
    )
    r = subprocess.run(
        [str(RUFF), "check", "--no-cache", "--config", str(moved), "m.py"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert r.returncode != 0
    assert "unknown field" in (r.stdout + r.stderr).lower()


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
