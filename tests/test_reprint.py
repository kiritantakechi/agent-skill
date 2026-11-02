"""The canonical re-print changed the standards' layout, not their text.

One commit replaced every shipped markdown file with its canonical form
and held nothing else. These tests hold that commit to it, against its
parent: each file is the canonical form of what it was, it parses to
the same tree, and every fenced example is byte-identical, which is
why no example had to be compiled again. The harness's own reader of
examples, which the toolchains extract from, is held to the same.

The commit is found by its subject line, so rewriting the branch's
history does not lose it; a clone too shallow to hold it and its parent
skips.
"""

import io
import subprocess
import tarfile
from pathlib import Path
lazy from collections.abc import Iterator

import pytest

from agent_skill.doc import Block, Doc, Fence, ListBlock, Quote, canonical
from agent_skill.layout import SKILLS
from agent_skill.model import discover

ROOT = Path(__file__).resolve().parents[1]

SUBJECT = "Re-print the four standards in their canonical form"


def git(*args: str) -> str:
    return subprocess.run(  # noqa: S603 — fixed arguments
        ["git", *args],  # noqa: S607 — the git on PATH, as a person runs it
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout


@pytest.fixture(scope="module")
def reprint() -> str:
    """The re-print commit; skips when the clone does not hold it."""
    found = git("log", "--format=%H", f"--grep=^{SUBJECT}$")
    commits = found.split()
    if not commits:
        pytest.skip("the re-print commit is not in this clone's history")
    (commit,) = commits
    parent = subprocess.run(  # noqa: S603 — fixed arguments
        ["git", "cat-file", "-e", f"{commit}^"],  # noqa: S607 — the git on PATH
        cwd=ROOT,
        capture_output=True,
        check=False,
    )
    if parent.returncode != 0:
        pytest.skip("the clone is too shallow to hold the re-print's parent")
    return commit


@pytest.fixture(scope="module")
def changed(reprint: str) -> list[str]:
    return git("diff", "--name-only", f"{reprint}^", reprint).split()


def fences(blocks: tuple[Block, ...]) -> Iterator[Fence]:
    """Every fence in `blocks`, nested ones included, in order."""
    for block in blocks:
        match block:
            case Fence():
                yield block
            case ListBlock(items):
                for item in items:
                    yield from fences(item.blocks)
            case Quote(inner):
                yield from fences(inner)
            case _:
                pass


def test_the_reprint_touched_only_the_standards_markdown(
    reprint: str, changed: list[str]
) -> None:
    shipped = git("ls-tree", "-r", "--name-only", f"{reprint}^", str(SKILLS)).split()
    assert sorted(changed) == sorted(p for p in shipped if p.endswith(".md"))


def test_every_file_is_the_canonical_form_of_what_it_was(
    reprint: str, changed: list[str]
) -> None:
    for path in changed:
        old, new = git("show", f"{reprint}^:{path}"), git("show", f"{reprint}:{path}")
        assert new == canonical(old), path
        assert Doc.parse(new) == Doc.parse(old), path


def test_every_example_is_byte_identical(reprint: str, changed: list[str]) -> None:
    total = 0
    for path in changed:
        old, new = git("show", f"{reprint}^:{path}"), git("show", f"{reprint}:{path}")
        before = [(f.info, f.body) for f in fences(Doc.parse(old).blocks)]
        after = [(f.info, f.body) for f in fences(Doc.parse(new).blocks)]
        assert after == before, path
        total += len(before)
    assert total > 0


def _checkout(rev: str, into: Path) -> Path:
    archive = subprocess.run(  # noqa: S603 — fixed arguments
        ["git", "archive", rev, str(SKILLS)],  # noqa: S607 — the git on PATH
        cwd=ROOT,
        capture_output=True,
        check=True,
    ).stdout
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        tar.extractall(into, filter="data")
    return into / SKILLS


def test_the_harness_reads_the_same_examples_and_rules(
    reprint: str, tmp_path: Path
) -> None:
    """What the toolchains extract and the checks count, unchanged."""

    def read(rev: str, name: str) -> dict[str, object]:
        return {
            skill.name: (
                [(b.file, b.lang, b.rule, b.body) for b in skill.blocks()],
                [(r.id, r.tier, r.title, r.file) for r in skill.rules],
                [(rid, tier) for rid, tier, _ in skill.core_rules],
            )
            for skill in discover(_checkout(rev, tmp_path / name))
        }

    before = read(f"{reprint}^", "before")
    assert before
    assert read(reprint, "after") == before
