"""Packaging a skill, and putting it where Claude Code will find it."""

from __future__ import annotations

import zipfile
from pathlib import Path

CLAUDE_SKILLS = Path.home() / ".claude" / "skills"
EXCLUDE = {".DS_Store", "__pycache__", ".git"}


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


def install(skill, into: Path = CLAUDE_SKILLS) -> tuple[Path, str]:
    """Point `~/.claude/skills/<name>` at the working copy.

    A symlink rather than a copy, so there is no installed second copy to drift
    from the source — the failure this whole apparatus exists to prevent.
    """
    into.mkdir(parents=True, exist_ok=True)
    link = into / skill.name
    if link.is_symlink():
        if link.readlink() == skill.root:
            return link, "already linked"
        link.unlink()
    elif link.exists():
        return link, "not a symlink; left alone"
    link.symlink_to(skill.root)
    return link, "linked"
