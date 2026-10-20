"""The harness meets the standard it ships for its own language.

python-style's assets are the configuration in force here: ruff extends
the shipped `ruff.toml` and ty runs under the shipped `ty.toml`. These
tests run both tools over the harness, show that each would fail on a
finding, and hold the repository's configuration to the shipped one.
"""

import tomllib
from pathlib import Path
from typing import Any

from agent_skill.lang.python import INTERPRETER
from agent_skill.proc import run

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "skills" / "python-style" / "assets"
TY = ("ty", "check", "--config-file", str(ASSETS / "ty.toml"))
TREES = ("src", "tests")

#: The harness's relaxations of the shipped configuration, each with its
#: reason. Adding one is an edit here, beside its reason, not one made
#: in passing.
RELAXED = {
    # The report a run prints is the program's output; T201 is about
    # diagnostics written with `print`.
    "src/agent_skill/cli.py": ["T201"],
}

#: A module with one finding for each tool.
PROBE = """def double(x):
    return x * 2


count: int = "three"
"""


def pyproject() -> dict[str, Any]:
    return tomllib.loads((ROOT / "pyproject.toml").read_text())


def test_ruff_finds_nothing_in_the_harness() -> None:
    lint = run(["ruff", "check", *TREES], cwd=ROOT)
    assert lint.ok, lint.out
    layout = run(["ruff", "format", "--check", *TREES], cwd=ROOT)
    assert layout.ok, layout.out


def test_ty_finds_nothing_in_the_harness() -> None:
    result = run([*TY, *TREES], cwd=ROOT)
    assert result.ok, result.out


def test_both_tools_fail_on_a_finding(tmp_path: Path) -> None:
    probe = tmp_path / "probe.py"
    probe.write_text(PROBE)
    config = str(ROOT / "pyproject.toml")

    lint = run(["ruff", "check", "--config", config, str(probe)], cwd=ROOT)
    types = run([*TY, str(probe)], cwd=ROOT)

    assert not lint.ok
    assert "ANN001" in lint.out
    assert not types.ok
    assert "invalid-assignment" in types.out


def test_the_ruff_configuration_is_the_shipped_one() -> None:
    ruff = pyproject()["tool"]["ruff"]
    shipped = tomllib.loads((ASSETS / "ruff.toml").read_text())
    ignores = ruff["lint"]["per-file-ignores"]

    assert ruff["extend"] == "skills/python-style/assets/ruff.toml"
    assert set(ruff) <= {"extend", "src", "lint"}
    assert set(ruff["lint"]) == {"per-file-ignores"}
    for glob, codes in shipped["lint"]["per-file-ignores"].items():
        assert ignores.pop(glob) == codes, f"`{glob}` is restated differently"
    assert ignores == RELAXED


def test_the_harness_runs_on_the_target_the_standard_names() -> None:
    project = pyproject()
    shipped = tomllib.loads((ASSETS / "pyproject.toml").read_text())
    target = tomllib.loads((ASSETS / "ty.toml").read_text())["environment"]

    assert project["project"]["requires-python"] == f">={target['python-version']}"
    assert project["build-system"] == shipped["build-system"]
    assert (ROOT / ".python-version").read_text().strip() == INTERPRETER
