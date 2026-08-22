"""The files a skill ships in `assets/`, checked as files.

Six assets shipped and nothing validated any of them. They are the one part of a
skill a reader copies verbatim rather than adapts, so a `build.zig` that does not
parse is worse than a wrong example: it is handed over as ready to use.
"""

from __future__ import annotations

import re
import tomllib

from ..proc import have, run
from ..report import fail
from . import check

#: A workflow is not YAML we can parse without a dependency, so check the shape a
#: broken one loses first: the top-level keys and the absence of tabs.
WORKFLOW_KEYS = ("name:", "on:", "jobs:")


@check("assets", "the files a reader copies verbatim")
def assets(skill):
    directory = skill.root / "assets"
    if not directory.is_dir():
        yield fail("no assets/ directory", skill.name)
        return
    if not skill.assets:
        yield fail("assets/ is empty", skill.name)
        return

    referenced = "\n".join(p.read_text() for p in skill.markdown)
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
                    tomllib.loads(text)
                except tomllib.TOMLDecodeError as e:
                    yield fail(str(e), tag)
            case ".yml" | ".yaml":
                yield from _workflow(text, tag)

        # An asset nobody points at is not part of the skill.
        if f"assets/{path.name}" not in referenced:
            yield fail("shipped but never referenced from the skill", tag)


def _zig(path, tag):
    if not have("zig"):
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
        if not re.search(rf"^{re.escape(key)}", text, re.M):
            yield fail(f"no top-level `{key}`", tag)
    for i, line in enumerate(text.split("\n"), 1):
        if line.strip() and (len(line) - len(line.lstrip(" "))) % 2:
            yield fail("odd indent, which YAML reads as a different level", f"{tag}:{i}")
