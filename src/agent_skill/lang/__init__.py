"""Turning a skill's examples back into code a compiler will accept.

The markdown is the source of truth, not a crate kept alongside it. The
previous apparatus inverted that: examples lived in a crate, were
injected into the markdown, and a block deleted from the markdown left
an orphan module the orphan check could not see. Extracting in this
direction makes that state unreachable.
"""

lazy from collections.abc import Iterable
from dataclasses import dataclass, field
lazy from pathlib import Path
from typing import Protocol

lazy from agent_skill.report import Finding
lazy from agent_skill.lang import python, rust, zig


@dataclass(frozen=True, slots=True)
class Unit:
    """One extracted block, and where it came from."""

    path: Path
    chapter: str
    line: int
    rule: str

    @property
    def where(self) -> str:
        return f"{self.chapter}:{self.line} [{self.rule}]"


@dataclass
class Extraction:
    root: Path
    units: list[Unit] = field(default_factory=list)
    #: how the extracted crate is built; None for a toolchain that needs
    #: no manifest
    crate: object | None = None

    def __bool__(self) -> bool:
        return bool(self.units)


class Toolchain(Protocol):
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

    def extract(self, skill, out: Path) -> Extraction: ...

    def verify(self, ex: Extraction) -> Iterable[Finding]: ...

    def mutate(self, ex: Extraction) -> Iterable[Finding]: ...


def toolchain_for(name: str | None) -> Toolchain | None:
    if name is None:
        return None

    return {"rust": rust.RUST, "zig": zig.ZIG, "python": python.PYTHON_TOOLCHAIN}.get(
        name
    )
