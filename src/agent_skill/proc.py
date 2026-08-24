"""Subprocesses whose timeout is a result, not an exception.

Deleting a loop increment turns a test into a hang. Handled on one side and left
to raise on the other, that asymmetry aborted a whole mutation pass on the first
hanging mutant and skipped every one after it.
"""

from __future__ import annotations

import os
import shutil
import signal
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
        proc = subprocess.Popen(
            cmd,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env={**os.environ, **env} if env else None,
            # So a timeout can reach the whole tree, not just the leader.
            start_new_session=True,
        )
    except FileNotFoundError:
        return Ran(127, "", f"{cmd[0]}: not found", False)
    with proc:
        try:
            out, err = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            _kill_tree(proc)
            proc.communicate()
            return Ran(None, "", "", True)
        return Ran(proc.returncode, out, err, False)


def _kill_tree(proc: subprocess.Popen) -> None:
    """Kill the process group, because `Popen.kill` kills only the leader.

    Timing out a `cargo` left nine to twelve `rustc` children alive — measured,
    and still climbing two seconds later — every one of them writing into the
    build directory the next invocation was about to use, with cargo's lock
    already gone. A build directory in an undefined state is how a mutation run
    reports something impossible.
    """
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    except ProcessLookupError, PermissionError:
        proc.kill()


def have(tool: str) -> bool:
    """Is this tool on PATH at all?

    By lookup, not by running it: `zig --version` is not how zig spells it, so
    probing with `--version` reported zig as absent and silently skipped every
    check that needed it.
    """
    return shutil.which(tool) is not None
