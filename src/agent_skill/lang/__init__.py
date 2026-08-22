"""Turning a skill's examples back into code a compiler will accept.

The markdown is the source of truth, not a crate kept alongside it. The previous
apparatus inverted that: examples lived in a crate, were injected into the
markdown, and a block deleted from the markdown left an orphan module the orphan
check could not see. Extracting in this direction makes that state unreachable.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from ..report import Finding


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
    #: how the extracted crate is built; None for a toolchain that needs no manifest
    crate: object | None = None

    def __bool__(self) -> bool:
        return bool(self.units)


class Toolchain(Protocol):
    name: str
    tool: str

    def extract(self, skill, out: Path) -> Extraction: ...

    def verify(self, ex: Extraction) -> Iterable[Finding]: ...

    def mutate(self, ex: Extraction) -> Iterable[Finding]: ...


def toolchain_for(name: str | None) -> Toolchain | None:
    if name is None:
        return None
    from . import rust, zig

    return {"rust": rust.RUST, "zig": zig.ZIG}.get(name)
