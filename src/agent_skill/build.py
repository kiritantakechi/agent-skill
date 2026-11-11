"""Packaging a skill, and putting it where an agent will find it."""

import shutil
import zipfile
from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path
lazy from collections.abc import Iterator

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


@dataclass(frozen=True, slots=True)
class Installed:
    """What `install` did at one agent: the link, and what it found.

    `ok` is False when a copy differing from the skill stands where the
    link belongs and was left alone: the agent reads that copy, not the
    skill, so the install did not happen.
    """

    link: Path
    how: str
    ok: bool = True


def shipped(root: Path) -> Iterator[Path]:
    """Each file below `root` a package holds, as its path below `root`.

    Only the path below the skill is matched against `EXCLUDE`: matched
    whole, a checkout under a directory named `dist` would have packaged
    nothing.
    """
    for path in sorted(root.rglob("*")):
        inside = path.relative_to(root)
        if any(fnmatch(part, glob) for part in inside.parts for glob in EXCLUDE):
            continue
        if path.is_file():
            yield inside


#: The names one package is written under, as suffixes. The bytes are
#: one zip archive: `.skill` is what a skill file is called, and `.zip`
#: what an upload that wants a zip, a marketplace's, accepts.
SUFFIXES = (".skill", ".zip")


def package(skill: Skill, out_dir: Path) -> tuple[Path, ...]:
    """Zip the skill directory once, as `<name>` under each suffix.

    The archive is rooted at the skill name, and holds what `shipped`
    yields: one folder named after the skill, `SKILL.md` directly in it,
    which is the shape a skill upload takes, a marketplace's included.
    It is written under the first suffix and copied under the others, so
    every name holds the same bytes. Returned in `SUFFIXES` order.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    first, *others = (out_dir / f"{skill.name}{s}" for s in SUFFIXES)
    with zipfile.ZipFile(first, "w", zipfile.ZIP_DEFLATED) as z:
        for inside in shipped(skill.root):
            z.write(skill.root / inside, Path(skill.name) / inside)
    for other in others:
        shutil.copyfile(first, other)
    return (first, *others)


def identical(copy: Path, skill: Path) -> bool:
    """Whether `copy` holds what a package of `skill` holds, exactly."""
    files = list(shipped(skill))
    return list(shipped(copy)) == files and all(
        (copy / f).read_bytes() == (skill / f).read_bytes() for f in files
    )


def install(skill: Skill, target: Target) -> Installed:
    """Point `<target>/<name>` at the working copy.

    A symlink rather than a copy, so there is no installed second copy
    to drift from the source. Antigravity held a copy taken a week
    earlier that differed in every file — which is the failure this
    whole apparatus exists to prevent.

    An existing real directory is moved aside rather than deleted, and
    never overwritten twice: when the place it would move to is taken,
    it is left alone, which is a failed install unless it holds what
    the skill holds. The link holds the skill's absolute path: a
    relative `--skills` made a link that resolved against the agent's
    skills directory, and pointed at nothing.
    """
    target.skills.mkdir(parents=True, exist_ok=True)
    link = target.skills / skill.name
    source = skill.root.resolve()

    if link.is_symlink():
        if link.readlink() == source:
            return Installed(link, "already linked")
        link.unlink()
    elif link.exists():
        # Out of the skills directory, not merely renamed inside it:
        # discovery walks `skills/*/SKILL.md` and reads the name from
        # the frontmatter, so a `rust-style.replaced` beside
        # `rust-style` is a second skill claiming the same name.
        aside = target.displaced / skill.name
        if aside.exists():
            if identical(link, source):
                return Installed(
                    link,
                    f"a copy identical to the skill is here and {aside} already "
                    "exists; left alone",
                )
            return Installed(
                link,
                f"a copy differing from the skill is here and {aside} already "
                "exists; left alone",
                ok=False,
            )
        aside.parent.mkdir(parents=True, exist_ok=True)
        link.rename(aside)
        link.symlink_to(source)
        return Installed(link, f"linked; the copy that was here moved to {aside}")

    link.symlink_to(source)
    return Installed(link, "linked")
