"""The files a skill ships in `assets/`, checked as files.

Six assets shipped and nothing validated any of them. They are the one
part of a skill a reader copies verbatim rather than adapts, so a
`build.zig` that does not parse is worse than a wrong example: it is
handed over as ready to use.
"""

import re
import tempfile
import tomllib
import zipfile
from functools import partial
from pathlib import Path
lazy from collections.abc import Callable, Iterator
lazy from typing import Any

from agent_skill.checks import check, per_skill
from agent_skill.ids import cited
from agent_skill.lang import needs, toolchains
from agent_skill.proc import have, run
from agent_skill.report import Level, declare, fail, unrun
lazy from agent_skill.ids import Location
lazy from agent_skill.model import Skill
lazy from agent_skill.report import Finding

#: A workflow is not YAML we can parse without a dependency, so check
#: the shape a broken one loses first: the top-level keys and the
#: absence of tabs.
WORKFLOW_KEYS = ("name:", "on:", "jobs:")

# The branches a finding of this check comes from. A toolchain that
# reads an asset of its own declares the branches it reports through.
NO_DIRECTORY = declare("assets", "no_directory", Level.FAIL)
EMPTY = declare("assets", "empty", Level.FAIL)
TAB = declare("assets", "tab", Level.FAIL)
NEWLINE = declare("assets", "newline", Level.FAIL)
TOML = declare("assets", "toml", Level.FAIL)
UNREFERENCED = declare("assets", "unreferenced", Level.FAIL)
CITES = declare("assets", "cites", Level.FAIL)
UV_ABSENT = declare("assets", "uv_absent", Level.UNRUN)
BUILD = declare("assets", "build", Level.FAIL)
NO_WHEEL = declare("assets", "no_wheel", Level.FAIL)
NO_PY_TYPED = declare("assets", "no_py_typed", Level.FAIL)
WORKFLOW_KEY = declare("assets", "workflow_key", Level.FAIL)
ODD_INDENT = declare("assets", "odd_indent", Level.FAIL)
DELTA_UNCHANGED = declare("assets", "delta_unchanged", Level.FAIL)
DELTA_UNNAMED = declare("assets", "delta_unnamed", Level.FAIL)


@check(
    "assets",
    "the files a reader copies verbatim",
    needs=("uv", *needs(lambda tc: tc.assets_with)),
)
@per_skill
def assets(skill: Skill) -> Iterator[Finding]:
    """Each asset: well formed, referenced, and citing real rules."""
    directory = skill.root / "assets"
    if not directory.is_dir():
        yield fail("no assets/ directory", skill.at(), NO_DIRECTORY)
        return
    if not skill.assets:
        yield fail("assets/ is empty", skill.at(), EMPTY)
        return

    referenced = "\n".join(str(doc) for doc in skill.docs.values())
    for path in skill.assets:
        yield from _asset(skill, path, referenced)
    yield from _delta(skill, referenced)


def _delta(skill: Skill, referenced: str) -> Iterator[Finding]:
    """A delta's assets are its anchor's, replaced where it departs.

    So it ships an asset only where its own differs from its anchor's,
    and every one of its anchor's it does not ship is named in its
    text, which is how a reader learns the anchor's file applies. One
    asset, one copy: a delta shipping its anchor's file unchanged holds
    a second copy of a file that will drift from the first.
    """
    anchor = skill.profile.anchor
    theirs = skill.root.parent / anchor / "assets"
    if not anchor or not theirs.is_dir():
        return
    for path in sorted(theirs.iterdir()):
        own = skill.root / "assets" / path.name
        rel = f"assets/{path.name}"
        if own.exists() and _same(own, path):
            yield fail(
                f"ships {anchor}'s `{rel}` unchanged; the anchor's applies",
                skill.at(own),
                DELTA_UNCHANGED,
            )
        elif not own.exists() and rel not in referenced:
            yield fail(
                f"applies {anchor}'s `{rel}` and never says so",
                skill.at(),
                DELTA_UNNAMED,
            )


def _same(a: Path, b: Path) -> bool:
    """One asset: equal as data where both are TOML, else as text."""
    if a.suffix == ".toml":
        try:
            return tomllib.loads(a.read_text()) == tomllib.loads(b.read_text())
        except tomllib.TOMLDecodeError:
            return False
    return a.read_text() == b.read_text()


def _asset(skill: Skill, path: Path, referenced: str) -> Iterator[Finding]:
    """One asset: its whitespace, its kind's checks, its citations."""
    tag = skill.at(path)
    text = path.read_text()
    if "\t" in text:
        yield fail("hard tab", tag, TAB)
    if not text.endswith("\n"):
        yield fail("no trailing newline", tag, NEWLINE)

    yield from _kind(skill, path, text)

    # An asset nobody points at is not part of the skill.
    if f"assets/{path.name}" not in referenced:
        yield fail("shipped but never referenced from the skill", tag, UNREFERENCED)

    # An asset cites rules to say why it is shaped the way it is,
    # and nothing was checking those: `_references` reads the
    # chapters and `SKILL.md`, not `assets/`. Twenty-two citations
    # sat unverified.
    for rid in sorted(set(cited(text, skill.prefix)) - skill.ids):
        yield fail(f"cites {rid}, which is not a rule", tag, CITES)


def _kind(skill: Skill, path: Path, text: str) -> Iterator[Finding]:
    """What one asset's kind asks of it.

    A toolchain reads the assets in its own language; a manifest is
    parsed, and built if it describes a project; a workflow is read for
    its shape.
    """
    tag = skill.at(path)
    for toolchain in toolchains():
        if path.suffix in toolchain.asset_suffixes:
            yield from toolchain.asset(path, tag)
    match path.suffix:
        case ".toml":
            try:
                data = tomllib.loads(text)
            except tomllib.TOMLDecodeError as e:
                yield fail(str(e), tag, TOML)
            else:
                yield from _build(data, text, tag)
        case ".yml" | ".yaml":
            yield from _workflow(text, partial(skill.at, path))


def _build(data: dict[str, Any], text: str, tag: Location) -> Iterator[Finding]:
    """Build the project the metadata describes, if it describes one.

    Parsing is not verification. `assets/pyproject.toml` was valid TOML,
    agreed with every rule that owned it, was cited by name from three
    chapters, and could not be built at all: the distribution was
    `acme-widget`, so the backend looked for `src/acme_widget/` and the
    package was `acmewidget`. Sixteen checks and 109 tests passed over
    it, because none of them ever handed it to a backend.
    """
    name = data.get("project", {}).get("name")
    if not name or "build-system" not in data:
        return  # a config file, not a project
    if not have("uv"):
        # `UNRUN`, not `NOTE`: `Result.ok` is `not fails and not unrun`,
        # so a note lets a run where nothing built this template report
        # ALL CHECKS PASSED. `citations`, `pins` and `toolchain` all use
        # `unrun` here; this path and the zig asset's were the two that
        # did not, and both were copied from the same wrong precedent.
        yield unrun(
            "`uv` is not on PATH, so nothing built this project", tag, UV_ABSENT
        )
        return

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        # The directory is the *distribution* name, not the name a
        # backend normalises it to. That is the point: PS-MOD-06
        # requires the two to match, so a name needing an override fails
        # here rather than silently working because the fixture was
        # built to suit it.
        package = root / "src" / name
        package.mkdir(parents=True)
        (package / "__init__.py").write_text("")
        (package / "py.typed").write_text("")
        (root / "pyproject.toml").write_text(text)
        readme = data["project"].get("readme")
        if isinstance(readme, str):
            (root / readme).write_text(f"# {name}\n")
        for licence in data["project"].get("license-files", []):
            if not set(licence) & set("*?["):
                (root / licence).write_text("Copyright\n")

        result = run(
            ["uv", "build", "--wheel", "--out-dir", str(root / "dist")],
            cwd=root,
            timeout=300,
        )
        if not result.ok:
            first = next(
                (
                    ln
                    for ln in result.err.split("\n")
                    if ln.strip().startswith(("Error", "error:"))
                ),
                result.err.strip()[:90],
            )
            yield fail(f"does not build: {first.strip()[:88]}", tag, BUILD)
            return

        # A rule claims the marker ships. Read it off the artefact
        # rather than off the backend's documentation, which is where
        # the claim came from.
        wheels = list((root / "dist").glob("*.whl"))
        if not wheels:
            yield fail("build reported success but produced no wheel", tag, NO_WHEEL)
            return
        shipped = zipfile.ZipFile(wheels[0]).namelist()
        if not any(n.endswith("/py.typed") for n in shipped):
            yield fail("built wheel ships no `py.typed`", tag, NO_PY_TYPED)


def _workflow(text: str, at: Callable[..., Location]) -> Iterator[Finding]:
    """A workflow has its top-level keys and indents in steps of two.

    `at` locates a line of it, or the whole file given no line.
    """
    for key in WORKFLOW_KEYS:
        if not re.search(rf"^{re.escape(key)}", text, re.MULTILINE):
            yield fail(f"no top-level `{key}`", at(), WORKFLOW_KEY)
    for i, line in enumerate(text.split("\n"), 1):
        if line.strip() and (len(line) - len(line.lstrip(" "))) % 2:
            yield fail(
                "odd indent, which YAML reads as a different level", at(i), ODD_INDENT
            )
