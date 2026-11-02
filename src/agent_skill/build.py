"""Packaging a skill, and putting it where an agent will find it."""

import zipfile
from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path

lazy from agent_skill.model import Skill

#: What a package leaves out, as globs matched against each part of a
#: path below the skill: what `.gitignore` keeps out of the repository,
#: and `.git` and `.DS_Store` besides. It stopped at five names while
#: `.gitignore` kept caches and bytecode out, so a skill that a tool had
#: run in shipped its `.ruff_cache`.
EXCLUDE = (
    ".DS_Store",
    ".git",
    "__pycache__",
    "*.py[cod]",
    ".venv",
    ".pytest_cache",
    ".ruff_cache",
    "dist",
    ".cache",
    ".zig-cache",
    "zig-out",
)

HOME = Path.home()


@dataclass(frozen=True, slots=True)
class Target:
    """An agent that reads `<dir>/<name>/SKILL.md`.

    Claude Code, Codex and Antigravity all read the same shape: a
    directory per skill, a `SKILL.md` with `name` and `description`
    frontmatter, and optional `references/` beside it. So one source can
    serve all three.
    """

    name: str
    skills: Path
    #: what must already exist for the agent to count as installed here
    marker: Path

    @property
    def present(self) -> bool:
        """Is this agent installed on this machine?"""
        return self.marker.is_dir()

    @property
    def displaced(self) -> Path:
        """Where a copy that was standing in the way is moved to.

        Beside the skills directory rather than inside it, so nothing
        there is still discovered.
        """
        return self.skills.parent / "skills-replaced"


TARGETS: tuple[Target, ...] = (
    Target("claude", HOME / ".claude" / "skills", HOME / ".claude"),
    Target("codex", HOME / ".codex" / "skills", HOME / ".codex"),
    Target(
        "antigravity",
        HOME / ".gemini" / "config" / "skills",
        HOME / ".gemini" / "config",
    ),
)


def package(skill: Skill, out_dir: Path) -> Path:
    """Zip the skill directory into `<name>.skill`.

    The archive is rooted at the skill name. Only the path below the
    skill is matched against `EXCLUDE`: matched whole, a checkout under
    a directory named `dist` would have packaged nothing.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / f"{skill.name}.skill"
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as z:
        for path in sorted(skill.root.rglob("*")):
            inside = path.relative_to(skill.root)
            if any(fnmatch(part, glob) for part in inside.parts for glob in EXCLUDE):
                continue
            if path.is_file():
                z.write(path, Path(skill.name) / inside)
    return target


def install(skill: Skill, target: Target) -> tuple[Path, str]:
    """Point `<target>/<name>` at the working copy.

    A symlink rather than a copy, so there is no installed second copy
    to drift from the source. Antigravity held a copy taken a week
    earlier that differed in every file — which is the failure this
    whole apparatus exists to prevent.

    An existing real directory is moved aside rather than deleted, and
    never overwritten twice. The link holds the skill's absolute path: a
    relative `--skills` made a link that resolved against the agent's
    skills directory, and pointed at nothing.
    """
    target.skills.mkdir(parents=True, exist_ok=True)
    link = target.skills / skill.name
    source = skill.root.resolve()

    if link.is_symlink():
        if link.readlink() == source:
            return link, "already linked"
        link.unlink()
    elif link.exists():
        # Out of the skills directory, not merely renamed inside it:
        # discovery walks `skills/*/SKILL.md` and reads the name from
        # the frontmatter, so a `rust-style.replaced` beside
        # `rust-style` is a second skill claiming the same name.
        aside = target.displaced / skill.name
        if aside.exists():
            return (
                link,
                f"a real directory is here and {aside} already exists; left alone",
            )
        aside.parent.mkdir(parents=True, exist_ok=True)
        link.rename(aside)
        link.symlink_to(source)
        return link, f"linked; the copy that was here moved to {aside}"

    link.symlink_to(source)
    return link, "linked"
