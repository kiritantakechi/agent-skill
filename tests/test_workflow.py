"""A workflow's steps, as the checks read them, and the repository's.

The harness reads the part of YAML a step is written in, and nothing
more, so these hold that reader to what a step says: its action, its
`with:` in either form, its `run:` on its line or under it. Then the
repository's workflow is held to python-style's, step by shared step,
as `self-application` holds it.
"""

import re
from pathlib import Path

import pytest

from agent_skill import workflow
from agent_skill.checks.pins import _actions
from agent_skill.checks.selfapply import _workflows
from agent_skill.layout import SKILLS, root_of
from agent_skill.model import Tree, discover
from agent_skill.profiles import PROFILES

REPO = Path(__file__).resolve().parents[1]

COMMIT = "3d3c42e5aac5ba805825da76410c181273ba90b1"

#: A job in each form a step's keys are written in.
JOB = f"""\
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@{COMMIT}  # v7.0.1
        with: {{ persist-credentials: false, token: "${{{{ secrets.T }}}}" }}
      - name: Toolchain
        uses: dtolnay/rust-toolchain@{COMMIT}  # master
        with:
          toolchain: 1.99.1   # the pin
          components: clippy, rustfmt
      # - uses: actions/cache@v4
      - run: uv python install cpython-3.15.2+freethreaded
      - run: |
          cargo test   # a shell comment stays
          cargo doc
  lint:
    steps:
    - run: uv run ruff check
"""


def test_each_step_reads_as_written() -> None:
    read = workflow.steps(JOB)
    assert [s.line for s in read] == [5, 7, 13, 14, 19]
    checkout, toolchain, interpreter, cargo, ruff = read
    assert checkout.uses is not None
    assert checkout.uses.named == f"actions/checkout@{COMMIT}"
    assert checkout.inputs == (
        ("persist-credentials", "false"),
        ("token", "${{ secrets.T }}"),
    )
    assert toolchain.inputs == (
        ("components", "clippy, rustfmt"),
        ("toolchain", "1.99.1"),
    )
    assert interpreter.run == "uv python install cpython-3.15.2+freethreaded"
    assert cargo.run == "cargo test # a shell comment stays cargo doc"
    assert ruff.run == "uv run ruff check"


@pytest.mark.parametrize(
    ("run", "identity"),
    [
        ("uv python install cpython-3.15.2+freethreaded", "uv python install"),
        ("uv python install 3.15t", "uv python install"),
        ("uv sync --group dev", "uv sync --group dev"),
        ("python3 -m pip check", "python3 -m pip check"),
    ],
)
def test_a_command_is_the_same_step_up_to_what_it_pins(run: str, identity: str) -> None:
    assert workflow.Step(1, run=run).identity == identity


def test_the_repository_runs_a_workflow_python_style_ships_one_for() -> None:
    """What `self-application` compares is there to compare."""
    [standard] = [p.name for p in PROFILES.values() if p.harness]
    ours = [workflow.steps(p.read_text()) for p in workflow.run_by(REPO)]
    assert ours, "the repository runs no workflow"
    skill = REPO / SKILLS / standard
    shipped = {
        s.identity
        for p in workflow.shipped(sorted((skill / "assets").iterdir()))
        for s in workflow.steps(p.read_text())
    }
    shared = {s.identity for steps in ours for s in steps} & shipped
    assert {"actions/checkout", "astral-sh/setup-uv", "uv python install"} <= shared


def _drift(scratch: Path, old: str, new: str) -> list[tuple[str, int | None]]:
    """What `self-application` says once the workflow says `new`."""
    path = root_of(scratch) / ".github" / "workflows" / "check.yml"
    text = path.read_text()
    assert old in text
    path.write_text(text.replace(old, new))
    found = _workflows(Tree.of(discover(scratch)))
    return [(f.branch.name, f.where.line) for f in found]


def test_the_shipped_workflow_takes_each_shared_step_as_the_asset_does(
    scratch: Path,
) -> None:
    assert list(_workflows(Tree.of(discover(scratch)))) == []


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ("cpython-3.15.2+freethreaded", "cpython-3.15.1+freethreaded"),
        ("cpython-3.15.2+freethreaded", "3.15t"),
        (f"checkout@{COMMIT}", f"checkout@{'0' * 40}"),
        ("persist-credentials: false", "persist-credentials: true"),
    ],
)
def test_a_shared_step_moved_fails_on_each_job_it_moved_in(
    scratch: Path, old: str, new: str
) -> None:
    found = _drift(scratch, old, new)
    assert len(found) == 2, "the step is in both jobs"
    assert {branch for branch, _ in found} == {"drifted_step"}


def test_a_step_of_the_repository_s_own_is_not_compared(scratch: Path) -> None:
    assert _drift(scratch, "check --fast", "check --fast --verbose") == []
    assert (
        _drift(scratch, "toolchain: 1.99.1, components: clippy", "toolchain: 1.98")
        == []
    )


def test_pins_reads_the_repository_s_workflow_as_it_reads_an_asset(
    scratch: Path,
) -> None:
    """An action the workflow names by its tag is found where it is."""
    path = root_of(scratch) / ".github" / "workflows" / "check.yml"
    text = path.read_text()
    first = re.search(r"uses: (\S+)@[0-9a-f]{40} +# (\S+)", text)
    assert first is not None
    path.write_text(text.replace(first[0], f"uses: {first[1]}@{first[2]}", 1))
    line = text[: first.start()].count("\n") + 1
    found = [
        (f.branch.name, str(f.where)) for f in _actions(Tree.of(discover(scratch)))
    ]
    assert found == [("movable_action", f"./.github/workflows/check.yml:{line}")]
