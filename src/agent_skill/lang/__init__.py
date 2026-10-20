"""Turning a skill's examples back into code a compiler will accept.

The markdown is the source of truth, not a crate kept alongside it. The
previous apparatus inverted that: examples lived in a crate, were
injected into the markdown, and a block deleted from the markdown left
an orphan module the orphan check could not see. Extracting in this
direction makes that state unreachable.
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol
lazy from collections.abc import Iterable
lazy from pathlib import Path

lazy from agent_skill.lang import python, rust, zig
lazy from agent_skill.model import Skill
lazy from agent_skill.report import Finding

if TYPE_CHECKING:
    # Not `lazy`: `dataclass` evaluates field annotations as the class
    # is built, and reifying this one then would import `rust`, which
    # imports this package before `Extraction` exists.
    from agent_skill.lang.rust import Crate


@dataclass(frozen=True, slots=True)
class Unit:
    """One extracted block, and where it came from."""

    path: Path
    chapter: str
    line: int
    rule: str

    @property
    def where(self) -> str:
        """Chapter, line and rule: how a finding locates the block."""
        return f"{self.chapter}:{self.line} [{self.rule}]"


@dataclass
class Extraction:
    """A skill's examples, written where a toolchain can build them."""

    root: Path
    units: list[Unit] = field(default_factory=list)
    #: how the extracted crate is built; None for a toolchain that needs
    #: no manifest
    crate: Crate | None = None

    def __bool__(self) -> bool:
        """Whether any block was extracted at all."""
        return bool(self.units)


class Toolchain(Protocol):
    """What a language must provide for its examples to be verified."""

    name: str
    tool: str

    def missing(self) -> list[str]:
        """What this toolchain needs and cannot find.

        A `shutil.which` on one name answered for Rust and Zig, where
        one binary does everything. It cannot answer for a toolchain
        that needs an exact interpreter build plus two separate tools,
        and it cannot see an interpreter that is deliberately resolved
        through a version manager rather than through PATH.
        """
        ...

    def extract(self, skill: Skill, out: Path) -> Extraction:
        """Write `skill`'s verified blocks under `out`, to be built."""
        ...

    def verify(self, ex: Extraction) -> Iterable[Finding]:
        """Everything the toolchain rejects in the extracted blocks."""
        ...

    def mutate(self, ex: Extraction) -> Iterable[Finding]:
        """Statements the extracted blocks' tests do not pin."""
        ...


def toolchain_for(name: str | None) -> Toolchain | None:
    """The toolchain called `name`, or None when there is none."""
    if name is None:
        return None

    return {"rust": rust.RUST, "zig": zig.ZIG, "python": python.PYTHON_TOOLCHAIN}.get(
        name
    )
