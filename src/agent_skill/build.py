"""Packaging a skill, and putting it where an agent will find it."""

import zipfile
from dataclasses import dataclass
from pathlib import Path

EXCLUDE = {".DS_Store", "__pycache__", ".git"}

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


def package(skill, out_dir: Path) -> Path:
    """Zip the skill directory into `<name>.skill`, rooted at the skill name."""
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / f"{skill.name}.skill"
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as z:
        for path in sorted(skill.root.rglob("*")):
            if any(part in EXCLUDE for part in path.parts):
                continue
            if path.is_file():
                z.write(path, Path(skill.name) / path.relative_to(skill.root))
    return target


def install(skill, target: Target) -> tuple[Path, str]:
    """Point `<target>/<name>` at the working copy.

    A symlink rather than a copy, so there is no installed second copy
    to drift from the source. Antigravity held a copy taken a week
    earlier that differed in every file — which is the failure this
    whole apparatus exists to prevent.

    An existing real directory is moved aside rather than deleted, and
    never overwritten twice.
    """
    target.skills.mkdir(parents=True, exist_ok=True)
    link = target.skills / skill.name

    if link.is_symlink():
        if link.readlink() == skill.root:
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
        link.symlink_to(skill.root)
        return link, f"linked; the copy that was here moved to {aside}"

    link.symlink_to(skill.root)
    return link, "linked"
