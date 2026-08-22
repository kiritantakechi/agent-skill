"""Subprocesses whose timeout is a result, not an exception.

Deleting a loop increment turns a test into a hang. Handled on one side and left
to raise on the other, that asymmetry aborted a whole mutation pass on the first
hanging mutant and skipped every one after it.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Ran:
    rc: int | None
    out: str
    err: str
    timed_out: bool

    @property
    def ok(self) -> bool:
        return self.rc == 0 and not self.timed_out


def run(
    cmd: list[str],
    cwd: Path | None = None,
    timeout: float = 180,
    env: dict[str, str] | None = None,
) -> Ran:
    try:
        p = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            env={**os.environ, **env} if env else None,
        )
    except subprocess.TimeoutExpired:
        return Ran(None, "", "", True)
    except FileNotFoundError:
        return Ran(127, "", f"{cmd[0]}: not found", False)
    return Ran(p.returncode, p.stdout, p.stderr, False)


def have(tool: str) -> bool:
    """Is this tool on PATH at all?

    By lookup, not by running it: `zig --version` is not how zig spells it, so
    probing with `--version` reported zig as absent and silently skipped every
    check that needed it.
    """
    return shutil.which(tool) is not None
