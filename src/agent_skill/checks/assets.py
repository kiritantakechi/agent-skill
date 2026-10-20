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
from pathlib import Path

from agent_skill.checks import check
from agent_skill.proc import have, run
from agent_skill.report import fail, unrun

#: A workflow is not YAML we can parse without a dependency, so check
#: the shape a broken one loses first: the top-level keys and the
#: absence of tabs.
WORKFLOW_KEYS = ("name:", "on:", "jobs:")


@check("assets", "the files a reader copies verbatim", needs=("uv", "zig"))
def assets(skill):
    directory = skill.root / "assets"
    if not directory.is_dir():
        yield fail("no assets/ directory", skill.name)
        return
    if not skill.assets:
        yield fail("assets/ is empty", skill.name)
        return

    referenced = "\n".join(p.read_text() for p in skill.markdown)
    rules = {r.id for r in skill.rules} | {rid for rid, _, _ in skill.core_rules}
    for path in skill.assets:
        tag = f"{skill.name}/assets/{path.name}"
        text = path.read_text()
        if "\t" in text:
            yield fail("hard tab", tag)
        if not text.endswith("\n"):
            yield fail("no trailing newline", tag)

        match path.suffix:
            case ".zig" | ".zon":
                yield from _zig(path, tag)
            case ".toml":
                try:
                    data = tomllib.loads(text)
                except tomllib.TOMLDecodeError as e:
                    yield fail(str(e), tag)
                else:
                    yield from _build(data, text, tag)
            case ".yml" | ".yaml":
                yield from _workflow(text, tag)

        # An asset nobody points at is not part of the skill.
        if f"assets/{path.name}" not in referenced:
            yield fail("shipped but never referenced from the skill", tag)

        # An asset cites rules to say why it is shaped the way it is,
        # and nothing was checking those: `_references` reads the
        # chapters and `SKILL.md`, not `assets/`. Twenty-two citations
        # sat unverified.
        for rid in sorted(
            set(re.findall(rf"\b{skill.prefix}-[A-Z]+-\d+[a-z]?\b", text)) - rules
        ):
            yield fail(f"cites {rid}, which is not a rule", tag)


def _build(data, text, tag):
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
        yield unrun("`uv` is not on PATH, so nothing built this project", tag)
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
            yield fail(f"does not build: {first.strip()[:88]}", tag)
            return

        # A rule claims the marker ships. Read it off the artefact
        # rather than off the backend's documentation, which is where
        # the claim came from.
        wheels = list((root / "dist").glob("*.whl"))
        if not wheels:
            yield fail("build reported success but produced no wheel", tag)
            return
        shipped = zipfile.ZipFile(wheels[0]).namelist()
        if not any(n.endswith("/py.typed") for n in shipped):
            yield fail("built wheel ships no `py.typed`", tag)


def _zig(path, tag):
    if not have("zig"):
        # Silence is not success, and a `NOTE` is silence: it does not
        # withhold the pass. A shipped `build.zig` that nothing parsed
        # is exactly the case this check exists for.
        yield unrun("`zig` is not on PATH, so nothing parsed this file", tag)
        return
    if not run(["zig", "fmt", "--check", str(path)], timeout=60).ok:
        yield fail("not `zig fmt` clean", tag)
    r = run(["zig", "ast-check", str(path)], timeout=60)
    if not r.ok:
        first = next((ln for ln in r.err.split("\n") if ": error:" in ln), r.err[:80])
        # the absolute path is noise; the line and the message are not
        yield fail(first.split(f"{path}:")[-1].strip()[:84], tag)


def _workflow(text, tag):
    for key in WORKFLOW_KEYS:
        if not re.search(rf"^{re.escape(key)}", text, re.MULTILINE):
            yield fail(f"no top-level `{key}`", tag)
    for i, line in enumerate(text.split("\n"), 1):
        if line.strip() and (len(line) - len(line.lstrip(" "))) % 2:
            yield fail(
                "odd indent, which YAML reads as a different level", f"{tag}:{i}"
            )
