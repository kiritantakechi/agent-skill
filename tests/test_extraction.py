"""A toolchain is an extraction and its inverse; a mutant, one grammar.

`restore ∘ extract` is the identity on every block body of every shipped
skill, every `verified` block is extracted wherever it stands, and each
is a file of its own whose line `i` is the body's. None of it runs a
compiler, so it runs in the fast suite.
"""

import fcntl
import threading
from dataclasses import replace
from pathlib import Path

import pytest

from agent_skill.lang import (
    Extraction,
    deletable,
    extracted,
    language,
    rust,
    toolchain_for,
)
from agent_skill.lang.python import PYTHON_STYLE
from agent_skill.lang.rust import RUST_STYLE, rebase
from agent_skill.lang.zig import SENTINEL, ZIG_STYLE, throwaway
from agent_skill.layout import SKILLS
from agent_skill.model import discover
from structure_fixture import DEMO, build, reparse
lazy from agent_skill.lang import Toolchain
lazy from agent_skill.model import Skill

SHIPPED = discover(Path(__file__).resolve().parents[1] / SKILLS)


def _extracted(skill: Skill, out: Path) -> tuple[Toolchain, Extraction]:
    tc = toolchain_for(skill.profile.toolchain)
    assert tc is not None, skill.name
    return tc, tc.extract(skill, out)


@pytest.mark.parametrize("skill", SHIPPED, ids=lambda s: s.name)
def test_restore_after_extract_is_the_identity(skill: Skill, tmp_path: Path) -> None:
    """Byte for byte, and for every verified block: none is left out."""
    tc, ex = _extracted(skill, tmp_path / "out")
    assert ex
    want = {b: b.body for b in extracted(skill, tc.language)}
    assert dict(tc.restore(ex)) == want


@pytest.mark.parametrize("skill", SHIPPED, ids=lambda s: s.name)
def test_a_unit_is_a_file_of_one_block_line_for_line(
    skill: Skill, tmp_path: Path
) -> None:
    """So a line a tool names in the file is a line of the markdown."""
    _, ex = _extracted(skill, tmp_path / "out")
    assert len({u.path for u in ex.units}) == len(ex.units)
    for unit in ex.units:
        assert unit.path.is_file()
        written = unit.path.read_text().split("\n")
        body = unit.block.body.split("\n")[:-1]
        if (crate := skill.profile.crate) is not None:
            stem, mod = unit.path.parent.name, unit.path.stem
            body = rebase(unit.block.body, crate, stem, mod).split("\n")[:-1]
        assert written[: len(body)] == body, unit.where


@pytest.mark.parametrize(
    ("config", "fence", "body"),
    [
        (PYTHON_STYLE, "python", "# verified\nx = 1\n"),
        (RUST_STYLE, "rust", "// verified\nfn a() {}\n"),
    ],
    ids=["python", "rust"],
)
def test_a_verified_block_in_skill_md_is_extracted(
    tmp_path: Path, config: object, fence: str, body: str
) -> None:
    """In every language: Rust skipped one, naming modules by rule."""
    demo = build(tmp_path, replace(DEMO, languages=(fence,), toolchain=config))
    demo.skill_md.write_text(f"{demo.skill_md.read_text()}\n```{fence}\n{body}```\n")
    demo = reparse(demo)
    tc, ex = _extracted(demo, tmp_path / "out")
    (unit,) = ex.units
    assert unit.block.file == "SKILL.md"
    assert unit.block.rule is None
    assert tc.restore(ex)[unit.block] == body


def test_zig_restores_what_its_formatter_wrote(tmp_path: Path) -> None:
    """The trailer the extractor adds is cut, blank line or none."""
    zig = toolchain_for(ZIG_STYLE)
    assert zig is not None
    skill = build(tmp_path, replace(DEMO, languages=("zig",), toolchain=ZIG_STYLE))
    chapter = skill.root / "references" / "errors.md"
    block = "```zig\n// verified\nfn f() void {}\n```\n"
    chapter.write_text(f"{chapter.read_text()}\n{block}")
    ex = zig.extract(reparse(skill), tmp_path / "out")
    unit = ex.units[0]
    text = unit.path.read_text()
    unit.path.write_text(text.replace(f"\n\n{SENTINEL}\n", f"\n{SENTINEL}\n"))
    assert zig.restore(ex)[unit.block] == unit.block.body


def deleted(fence: str, body: str) -> list[str]:
    """The statements `deletable` picks from `body`."""
    return [statement for _, statement in deletable(language(fence), body)]


def test_one_grammar_python() -> None:
    """Any statement, not only assignments; never a test's own line."""
    body = '''def f(items: list[int]) -> int:
    """Sum them."""
    total: int
    total = 0
    for x in items:
        total += x
    if not items: raise ValueError("empty")
    items.append(
        1,
    )
    assert total >= 0
    return total


def test_f() -> None:
    assert f([1]) == 1
'''
    assert deleted("python", body) == [
        "total = 0",
        "total += x",
        'if not items: raise ValueError("empty")',
        "return total",
    ]


def test_one_grammar_rust() -> None:
    """Statements outside the tests; no binding, item or assertion."""
    body = """pub fn f(v: &mut Vec<u32>) -> u32 {
    let n = v.len();
    v.push(1); // grow
    assert!(n < 10);
    v.iter().for_each(|x| {
        drop(x);
    });
    0
}

#[cfg(test)]
mod tests {
    #[test]
    fn it() {
        super::f(&mut vec![]);
    }
}
"""
    assert deleted("rust", body) == ["v.push(1);", "drop(x);"]


def test_one_grammar_zig() -> None:
    """A trailing comment does not hide a statement."""
    body = """fn f(v: *u32) void {
    v.* += 1; // bump
    std.debug.assert(v.* > 0);
    _ = v;
}

test "f" {
    var v: u32 = 0;
    f(&v);
}
"""
    assert deleted("zig", body) == ["v.* += 1;"]


def test_rust_leaves_its_build_directory_at_the_dependencies(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Each run's own build of the crate goes before the next builds.

    Extraction is to a new directory every run, so Cargo hashes the
    crate afresh and kept every earlier build beside the new one; the
    dependencies' files are the build worth keeping.
    """
    monkeypatch.setattr(rust, "CACHE", tmp_path)
    debug = tmp_path / RUST_STYLE.name / "debug"
    own = [
        "deps/rust_style_verify-0123456789abcdef",
        "deps/librust_style_verify-0123456789abcdef.rlib",
        "librust_style_verify.rlib",
        ".fingerprint/rust-style-verify-0123456789abcdef/lib",
        "incremental/rust_style_verify-0123456789abcdef/s-1/x.o",
    ]
    kept = [
        "deps/libthiserror-0123456789abcdef.rlib",
        ".fingerprint/thiserror-0123456789abcdef/lib",
        "build/thiserror-0123456789abcdef/out",
    ]
    for rel in (*own, *kept, rust.CARGO_LOCK):
        (debug / rel).parent.mkdir(parents=True, exist_ok=True)
        (debug / rel).write_text("")
    rust._tidy(RUST_STYLE)
    assert [rel for rel in own if (debug / rel).exists()] == []
    assert [rel for rel in kept if not (debug / rel).exists()] == []
    assert RUST_STYLE.env["CARGO_INCREMENTAL"] == "0"


@pytest.mark.parametrize(
    "hold", [fcntl.LOCK_SH, fcntl.LOCK_EX], ids=["cargo-1.99", "older-cargo"]
)
def test_rust_tidies_only_once_cargo_lets_go_of_the_build(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, hold: int
) -> None:
    """A build over the same skill keeps its files until it ends.

    The thread holds the build directory's lock as a Cargo building
    there does: shared since fine-grained locking, exclusive before.
    """
    monkeypatch.setattr(rust, "CACHE", tmp_path)
    debug = tmp_path / RUST_STYLE.name / "debug"
    own = debug / "deps" / "librust_style_verify-0123456789abcdef.rlib"
    own.parent.mkdir(parents=True)
    own.write_text("")
    lock = debug / rust.CARGO_LOCK
    lock.write_text("")
    holding, done = threading.Event(), threading.Event()

    def cargo() -> None:
        with lock.open("rb") as f:
            fcntl.flock(f, hold)
            holding.set()
            done.wait(timeout=30)

    building = threading.Thread(target=cargo)
    building.start()
    assert holding.wait(timeout=30)
    tidying = threading.Thread(target=rust._tidy, args=(RUST_STYLE,))
    tidying.start()
    tidying.join(timeout=0.5)
    assert tidying.is_alive(), "the cleanup did not wait for the build"
    assert own.exists()
    done.set()
    building.join(timeout=30)
    tidying.join(timeout=30)
    assert not tidying.is_alive()
    assert not own.exists()


def test_zig_keeps_its_caches_in_the_run_s_directory(tmp_path: Path) -> None:
    """Both caches under the directory removed after the run, hidden.

    Hidden, so `zig fmt` over the extraction does not walk into them.
    """
    env = throwaway(tmp_path)
    assert sorted(env) == ["ZIG_GLOBAL_CACHE_DIR", "ZIG_LOCAL_CACHE_DIR"]
    for value in env.values():
        path = Path(value)
        assert path.parent == tmp_path
        assert path.name.startswith(".")
