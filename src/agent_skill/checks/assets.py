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
from agent_skill.ids import Branch, cited
from agent_skill.proc import have, run
from agent_skill.report import fail, unrun
lazy from agent_skill.ids import Location
lazy from agent_skill.model import Skill
lazy from agent_skill.report import Finding

#: A workflow is not YAML we can parse without a dependency, so check
#: the shape a broken one loses first: the top-level keys and the
#: absence of tabs.
WORKFLOW_KEYS = ("name:", "on:", "jobs:")

# The branches a finding of this check comes from.
NO_DIRECTORY = Branch("assets", "no_directory")
EMPTY = Branch("assets", "empty")
TAB = Branch("assets", "tab")
NEWLINE = Branch("assets", "newline")
TOML = Branch("assets", "toml")
UNREFERENCED = Branch("assets", "unreferenced")
CITES = Branch("assets", "cites")
UV_ABSENT = Branch("assets", "uv_absent")
BUILD = Branch("assets", "build")
NO_WHEEL = Branch("assets", "no_wheel")
NO_PY_TYPED = Branch("assets", "no_py_typed")
ZIG_ABSENT = Branch("assets", "zig_absent")
ZIG_FMT = Branch("assets", "zig_fmt")
ZIG_AST = Branch("assets", "zig_ast")
WORKFLOW_KEY = Branch("assets", "workflow_key")
ODD_INDENT = Branch("assets", "odd_indent")


@check("assets", "the files a reader copies verbatim", needs=("uv", "zig"))
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


def _asset(skill: Skill, path: Path, referenced: str) -> Iterator[Finding]:
    """One asset: its whitespace, its kind's checks, its citations."""
    tag = skill.at(path)
    text = path.read_text()
    if "\t" in text:
        yield fail("hard tab", tag, TAB)
    if not text.endswith("\n"):
        yield fail("no trailing newline", tag, NEWLINE)

    match path.suffix:
        case ".zig" | ".zon":
            yield from _zig(path, tag)
        case ".toml":
            try:
                data = tomllib.loads(text)
            except tomllib.TOMLDecodeError as e:
                yield fail(str(e), tag, TOML)
            else:
                yield from _build(data, text, tag)
        case ".yml" | ".yaml":
            yield from _workflow(text, partial(skill.at, path))

    # An asset nobody points at is not part of the skill.
    if f"assets/{path.name}" not in referenced:
        yield fail("shipped but never referenced from the skill", tag, UNREFERENCED)

    # An asset cites rules to say why it is shaped the way it is,
    # and nothing was checking those: `_references` reads the
    # chapters and `SKILL.md`, not `assets/`. Twenty-two citations
    # sat unverified.
    for rid in sorted(set(cited(text, skill.prefix)) - skill.ids):
        yield fail(f"cites {rid}, which is not a rule", tag, CITES)


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
        # `unrun` here; this path and `_zig` were the two that did not,
        # and both were copied from the same wrong precedent.
        yield unrun(
            "`uv` is not on PATH, so nothing built this project", tag, UV_ABSENT
        )
        return

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        # The directory is the *distribution* name, not the name a
        # backend normalises it to. That is the point: PS-BUILD-14
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


def _zig(path: Path, tag: Location) -> Iterator[Finding]:
    """A zig asset is `zig fmt` clean and passes `zig ast-check`."""
    if not have("zig"):
        # Silence is not success, and a `NOTE` is silence: it does not
        # withhold the pass. A shipped `build.zig` that nothing parsed
        # is exactly the case this check exists for.
        yield unrun(
            "`zig` is not on PATH, so nothing parsed this file", tag, ZIG_ABSENT
        )
        return
    if not run(["zig", "fmt", "--check", str(path)], timeout=60).ok:
        yield fail("not `zig fmt` clean", tag, ZIG_FMT)
    r = run(["zig", "ast-check", str(path)], timeout=60)
    if not r.ok:
        first = next((ln for ln in r.err.split("\n") if ": error:" in ln), r.err[:80])
        # the absolute path is noise; the line and the message are not
        yield fail(first.split(f"{path}:")[-1].strip()[:84], tag, ZIG_AST)


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
