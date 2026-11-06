"""A migration row marked `gone` is looked up in the pinned release.

normalize-the-standards, decision 9: a `gone` row sends a reader to
rewrite every place its old spelling stands, so a row naming an API the
release still provides is a defect the table cannot see in itself. Each
toolchain looks the spelling up its own way — an import on the pinned
interpreter, a search of the pinned crates' source, a compile — and the
driver runs the step it gives.
"""

lazy from pathlib import Path

import pytest

from agent_skill.checks import demo
from agent_skill.checks.toolchain import GONE_LIVE, GONE_UNPROBED, gone
from agent_skill.lang import Step, execute
from agent_skill.lang.python import PYTHON, PYTHON_TOOLCHAIN
from agent_skill.lang.rust import RUST
from agent_skill.lang.zig import ZIG
from agent_skill.model import Skill
from agent_skill.proc import have

pytestmark = pytest.mark.toolchain


def provides(step: Step | None) -> bool | None:
    """Whether a probe found its name: None for no probe at all."""
    if step is None:
        return None
    assert isinstance(step, Step)
    ran = execute(step)
    assert ran.rc in {0, 1}, ran.err
    return ran.ok


@pytest.mark.skipif(not PYTHON.exists(), reason="the pinned interpreter is not built")
@pytest.mark.parametrize(
    ("spelling", "live"),
    [
        ("os.getcwd", True),
        ("os.getcwdu", False),
        ("glob.glob0", False),
        ("str.removeprefix", True),
        ("sre_compile", False),
        ("from __future__ import annotations", None),
        # A C API name is read from the headers: the library still
        # exports the removed one for the stable ABI.
        ("PyImport_ImportModule", True),
        ("PyImport_ImportModuleNoBlock", False),
    ],
)
def test_python_imports_the_name_on_the_pinned_interpreter(
    skills: list[Skill],
    tmp_path: Path,
    spelling: str,
    live: bool | None,  # noqa: FBT001 — a parametrised expectation
) -> None:
    python = next(s for s in skills if s.name == "python-style")
    assert provides(PYTHON_TOOLCHAIN.probe(python, spelling, tmp_path)) is live


@pytest.mark.skipif(not have("rg"), reason="`rg` is not on PATH")
@pytest.mark.parametrize(
    ("spelling", "live"),
    [
        ("Commands::spawn", True),
        ("despawn_recursive", False),
        ("EventWriter", False),
        ("MessageWriter", True),
        ("app.add_plugins(…)", None),
    ],
)
def test_rust_searches_the_pinned_crates_source(
    skills: list[Skill],
    tmp_path: Path,
    spelling: str,
    live: bool | None,  # noqa: FBT001 — a parametrised expectation
) -> None:
    bevy = next(s for s in skills if s.name == "bevy-style")
    step = RUST.probe(bevy, spelling, tmp_path)
    if live is not None and step is None:
        pytest.skip("the pinned Bevy crates are not in Cargo's registry here")
    assert provides(step) is live


@pytest.mark.skipif(not have("rg"), reason="`rg` is not on PATH")
@pytest.mark.parametrize(
    ("spelling", "live"),
    [
        # The standard library's source, when the toolchain ships it.
        ("std::env::home_dir", True),
        ("Atomic*::fetch_update", None),
        ("std::sync::ONCE_INIT", True),
        ("std::mem::forget_unchecked", False),
        # An attribute is compiled, edition 2021 against edition 2024.
        ("#[no_mangle]", False),
        ("#[inline]", True),
    ],
)
def test_rust_looks_up_the_language_in_the_pinned_toolchain(
    skills: list[Skill],
    tmp_path: Path,
    spelling: str,
    live: bool | None,  # noqa: FBT001 — a parametrised expectation
) -> None:
    rust = next(s for s in skills if s.name == "rust-style")
    step = RUST.probe(rust, spelling, tmp_path)
    if live is not None and step is None:
        pytest.skip("the pinned toolchain ships no standard-library source here")
    assert provides(step) is live


def test_rust_reads_an_attribute_no_edition_accepts_as_a_broken_probe(
    skills: list[Skill], tmp_path: Path
) -> None:
    """Rejected by the older edition too, the probe proves nothing."""
    rust = next(s for s in skills if s.name == "rust-style")
    step = RUST.probe(rust, "#[export_name]", tmp_path)
    assert step is not None
    assert execute(step).rc == 2


@pytest.mark.skipif(not have("zig"), reason="`zig` is not on PATH")
@pytest.mark.parametrize(
    ("spelling", "live"),
    [
        ("std.mem.copyForwards", True),
        ("std.mem.copy", False),
        ("std.io.getStdOut", False),
        ("@intToFloat", None),
    ],
)
def test_zig_compiles_a_reference_to_the_name(
    skills: list[Skill],
    tmp_path: Path,
    spelling: str,
    live: bool | None,  # noqa: FBT001 — a parametrised expectation
) -> None:
    zig = next(s for s in skills if s.name == "zig-style")
    assert provides(ZIG.probe(zig, spelling, tmp_path / "probes")) is live


@pytest.mark.skipif(not PYTHON.exists(), reason="the pinned interpreter is not built")
def test_the_driver_fails_a_gone_row_the_release_provides(tmp_path: Path) -> None:
    """The demo's rows, looked up as Python's: one names a live API."""
    demo.build(tmp_path)
    root = tmp_path / demo.PROFILE.name
    migration = root / "references" / "migration.md"
    migration.write_text(
        migration.read_text().replace(
            "| `old_flag` | `new_flag` | alias | DS-MIG-01 |\n",
            "| `old_flag` | `new_flag` | alias | DS-MIG-01 |\n"
            "| `os.getcwd` | `pathlib.Path.cwd` | gone | DS-MIG-01 |\n"
            "| `glob.glob0` | `glob.glob` | gone | DS-MIG-01 |\n"
            "| `print >>f` | `print(file=f)` | gone | DS-MIG-01 |\n",
        )
    )
    found = list(gone(PYTHON_TOOLCHAIN, Skill(root, demo.PROFILE), tmp_path / "out"))
    assert [(str(f.branch), f.where.line) for f in found] == [
        (str(GONE_LIVE), 17),
        (str(GONE_UNPROBED), 19),
    ]
