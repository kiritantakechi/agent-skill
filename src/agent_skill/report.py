"""What a check produces, and how it is shown.

A check returns findings. It does not print and it does not exit, so the same
function backs a command-line report, a pytest assertion, and a negative control
that asserts the check *can* fail.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Level(Enum):
    """A finding blocks, informs, or reports that the check could not look.

    The third one was added because a check that cannot run looks exactly like a
    check that passes, and the repository has already paid for that twice: a zig
    probe that reported 375 symbols present including a fake one, and clippy
    reported clean because it exits 0 on a warning. `UNRUN` blocks like `FAIL`
    but reads differently, because "there is a defect here" and "nobody looked"
    call for different actions.
    """

    FAIL = "FAIL"
    UNRUN = "unrun"
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


def unrun(message: str, where: str = "") -> Finding:
    """The check could not be performed. Not a pass, and not a defect either."""
    return Finding(Level.UNRUN, message, where)


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
    def unrun(self) -> list[Finding]:
        return [f for f in self.findings if f.level is Level.UNRUN]

    @property
    def notes(self) -> list[Finding]:
        return [f for f in self.findings if f.level is Level.NOTE]

    @property
    def ok(self) -> bool:
        """Green means every check ran and every one of them passed.

        Work that could not be done is not work that succeeded, so `UNRUN`
        withholds the pass exactly as `FAIL` does.
        """
        return not self.fails and not self.unrun

    def extend(self, findings) -> Result:
        self.findings.extend(findings)
        return self
