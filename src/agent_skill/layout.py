"""Where the repository keeps what it ships.

The skills are a Claude Code plugin, so they live inside it: a plugin
installed from a marketplace is copied whole, and keeping it in its own
directory keeps the harness, its tests and its specs out of that copy.
Every path below is relative to the repository root.
"""

from pathlib import Path

#: The plugin this repository publishes: its manifest, and its skills.
PLUGIN = Path("plugins") / "style-standards"

#: Every skill, one directory each.
SKILLS = PLUGIN / "skills"

#: The abstract standard: one file per abstract chapter, and the design
#: questions. Outside the plugin, since no skill reads it: it is the
#: harness's and the authors', and installs with nothing.
ABSTRACT = Path("abstract")

#: The repository's own CI: the workflows GitHub runs on it. Outside the
#: plugin, since they check the repository rather than ship with it.
WORKFLOWS = Path(".github") / "workflows"


def root_of(skills: Path) -> Path:
    """The repository root a skills directory sits in.

    A copy of the tree is laid out the same way, so a check that reads
    the README beside the root reads the copy's, not the original's.
    """
    return skills.parents[len(SKILLS.parts) - 1]


def in_repository(skills: Path) -> bool:
    """Is `skills` a repository's skills directory, laid out as ours?

    A test's tree written straight under its temporary directory is
    not, and has no root to read anything beside it from.
    """
    return len(skills.parts) > len(SKILLS.parts) and root_of(skills) / SKILLS == skills
