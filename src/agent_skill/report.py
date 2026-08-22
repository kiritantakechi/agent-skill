"""What a check produces, and how it is shown.

A check returns findings. It does not print and it does not exit, so the same
function backs a command-line report, a pytest assertion, and a negative control
that asserts the check *can* fail.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Level(Enum):
    """A finding either blocks or informs. There is no third thing."""

    FAIL = "FAIL"
    NOTE = "note"


@dataclass(frozen=True, slots=True)
class Finding:
    level: Level
    message: str
    where: str = ""

    def __str__(self) -> str:
        return f"{self.where}: {self.message}" if self.where else self.message


def fail(message: str, where: str = "") -> Finding:
    return Finding(Level.FAIL, message, where)


def note(message: str, where: str = "") -> Finding:
    return Finding(Level.NOTE, message, where)


@dataclass(slots=True)
class Result:
    """One check's output: its findings, plus what it wants to say about scale."""

    name: str
    findings: list[Finding] = field(default_factory=list)
    details: list[str] = field(default_factory=list)

    @property
    def fails(self) -> list[Finding]:
        return [f for f in self.findings if f.level is Level.FAIL]

    @property
    def notes(self) -> list[Finding]:
        return [f for f in self.findings if f.level is Level.NOTE]

    @property
    def ok(self) -> bool:
        return not self.fails

    def extend(self, findings) -> Result:
        self.findings.extend(findings)
        return self
