"""Subprocesses, and what a timeout actually reaches."""

from __future__ import annotations

import time

from agent_skill.proc import run


def test_a_timeout_kills_the_whole_process_group(tmp_path):
    """`Popen.kill` signals only the leader, and cargo's children outlive it.

    Measured on a timed-out `cargo test`: nine `rustc` processes still alive
    the moment `run` returned, twelve two seconds later, every one of them
    writing into the build directory the next invocation was about to use —
    with cargo's lock gone, because cargo was the process that died. That is
    how a mutation run reports a survivor the example does not have.
    """
    witness = tmp_path / "child-outlived-the-kill"
    r = run(["sh", "-c", f"(sleep 1; touch {witness}) & sleep 30"], timeout=0.5)

    assert r.timed_out
    assert r.rc is None
    time.sleep(2.0)
    assert not witness.exists(), "a child outlived the timeout that killed its parent"


def test_a_missing_tool_is_a_result_not_an_exception():
    r = run(["definitely-not-a-real-binary-xyz"])
    assert r.rc == 127
    assert not r.ok


def test_output_and_status_survive_the_rewrite():
    r = run(["sh", "-c", "printf out; printf err >&2; exit 3"])
    assert (r.rc, r.out, r.err, r.timed_out) == (3, "out", "err", False)
    assert not r.ok
