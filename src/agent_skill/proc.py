"""Subprocesses whose timeout is a result, not an exception.

Deleting a loop increment turns a test into a hang. Handled on one side
and left to raise on the other, that asymmetry aborted a whole mutation
pass on the first hanging mutant and skipped every one after it.
"""

import os
import shutil
import signal
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Ran:
    """How one subprocess ended.

    `rc` is None when the run timed out and was killed.
    """

    rc: int | None
    out: str
    err: str
    timed_out: bool

    @property
    def ok(self) -> bool:
        """Did the command exit 0 inside its time?"""
        return self.rc == 0 and not self.timed_out


def run(
    cmd: list[str],
    cwd: Path | None = None,
    timeout: float = 180,
    env: dict[str, str] | None = None,
    stdin: str | None = None,
) -> Ran:
    """Run `cmd` and wait for it, for at most `timeout` seconds.

    A timeout is a result, not an exception: the whole process tree is
    killed, and `timed_out` says so. A binary that is not there is
    status 127, as a shell reports it. A non-empty `env` is laid over
    this process's environment rather than replacing it.

    Output is read as UTF-8, and a byte that is not UTF-8 becomes U+FFFD
    rather than an exception: a tool that printed one byte of a binary,
    or a path in another encoding, raised `UnicodeDecodeError` out of
    the check that ran it, which reported nothing about the tool.
    """
    try:
        proc = subprocess.Popen(  # noqa: S603 — argv lists the harness builds; no shell
            cmd,
            cwd=cwd,
            stdin=subprocess.PIPE if stdin is not None else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8",
            errors="replace",
            env={**os.environ, **env} if env is not None and len(env) > 0 else None,
            # So a timeout can reach the whole tree, not just the
            # leader.
            start_new_session=True,
        )
    except FileNotFoundError:
        return Ran(127, "", f"{cmd[0]}: not found", timed_out=False)
    with proc:
        try:
            out, err = proc.communicate(input=stdin, timeout=timeout)
        except subprocess.TimeoutExpired:
            _kill_tree(proc)
            proc.communicate()
            return Ran(None, "", "", timed_out=True)
        return Ran(proc.returncode, out, err, timed_out=False)


def _kill_tree(proc: subprocess.Popen[str]) -> None:
    """Kill the process group: `Popen.kill` kills only the leader.

    Timing out a `cargo` left nine to twelve `rustc` children alive —
    measured, and still climbing two seconds later — every one of them
    writing into the build directory the next invocation was about to
    use, with cargo's lock already gone. A build directory in an
    undefined state is how a mutation run reports something impossible.
    """
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    except ProcessLookupError, PermissionError:
        proc.kill()


def tool_path(tool: str) -> str | None:
    """Where this tool actually is: the pinned copy before the host's.

    `shutil.which` answers "what would a shell run", which is the host's
    binary whenever `PATH` puts it first. Measured: with `ripgrep-bin`
    pinned into the environment, `which("rg")` still resolved to
    `/run/current-system/sw/bin/rg` outside an activated venv. A tool is
    pinned so that *it* runs; a pin that does not decide which binary
    executes describes an install nobody uses.
    """
    local = Path(sys.prefix) / "bin" / tool
    if local.is_file() and os.access(local, os.X_OK):
        return str(local)
    return shutil.which(tool)


def have(tool: str) -> bool:
    """Is this tool available at all?

    By lookup, not by running it: `zig --version` is not how zig spells
    it, so probing with `--version` reported zig as absent and silently
    skipped every check that needed it.
    """
    return tool_path(tool) is not None
