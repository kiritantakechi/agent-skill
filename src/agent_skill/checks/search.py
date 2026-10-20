"""Running one pattern over one corpus, and what a match is.

`Span` lives here rather than with the corpus because it describes a
match; the corpus is what was matched against.
"""

import json
import tempfile
from dataclasses import dataclass
from pathlib import Path

from agent_skill.checks.corpus import Corpus
from agent_skill.checks.patterns import Pattern
from agent_skill.proc import have, run, tool_path, version_mismatch
lazy from agent_skill.text import strip_comment, syntax_for


@dataclass(frozen=True, slots=True, order=True)
class Span:
    """The region a pattern matched: one line, or many.

    A hit used to be an `int`. Under multi-line matching one match
    covers a range and the start line alone does not describe it, so
    everything that consumes a hit — exemptions, rendering, the tiering
    — reads a span. A single-line match is a span of one line, handled
    by the same path.
    """

    start: int  #: 1-based, global across the corpus
    end: int  #: 1-based and inclusive; equal to `start` for a single line

    def __len__(self) -> int:
        return self.end - self.start + 1


def searcher_problem() -> str | None:
    """Why the pinned searcher cannot be trusted right now, or None.

    Absent, or present at a version nobody verified against — both mean
    the patterns did not run the way this repository claims they run,
    and a check that did not run must not report success.
    """
    if not have("rg"):
        return "`rg` is not available, so no pattern was run"
    answered = run([tool_path("rg"), "--version"], timeout=30)
    if not answered.ok:
        return "`rg` did not answer `--version`, so nothing confirmed which build ran"
    return version_mismatch("rg", answered.out)


def find(corpus: Corpus, pattern: Pattern):
    """The spans this pattern matched, or None when the search did not answer.

    `rg` exits 0 for a match, 1 for none, and 2 when it rejects the
    pattern. A rejected pattern is a defect in the pattern and is
    reported as one — there is no retry as a fixed string. That retry
    existed only because two grammars were in play and the engine could
    not tell which one a pattern was written for; turning a broken regex
    into a literal is how a check stops being able to fire while still
    reporting.

    Anything outside 0/1/2 is not an answer at all: a timeout gives
    `rc is None` and a missing binary gives 127, and both carry an empty
    stdout. Reading that as zero hits would report a Check as clean on
    the strength of a run that never happened.
    """
    target = corpus.raw_dir if pattern.over_comments else corpus.code_dir
    command = [
        tool_path("rg") or "rg",
        "--json",
        # The result must depend on the pattern, the corpus, and the
        # pinned binary — nothing else. Measured: a personal `-i` in a
        # user's RIPGREP_CONFIG_PATH turned a non-matching pattern into
        # a match.
        "--no-config",
        # The corpus is a synthesized directory with no ignore files in
        # it, so looking for one in every directory is pure overhead —
        # and, like `--no-config`, it stops a stray file on the host
        # from deciding what gets searched. Measured, with `-j1`, at
        # 3.5x faster: the corpus is a few hundred tiny files, which is
        # far below the size where a thread pool pays for its own setup.
        "--no-ignore",
        "--threads",
        "1",
        # Multi-line, but not dotall: `^`/`$` keep line anchoring and
        # `.` still stops at a newline, so a pattern spans lines only
        # when it says `(?s)` or uses a class that matches one.
        "--multiline",
        *(["--fixed-strings"] if pattern.mode == "-F" else []),
        "--regexp",
        pattern.text,
        str(target),
    ]
    r = run(command, timeout=30)
    # 0 is a match and 1 is none. Everything else is not an answer, by
    # one route or another: 2 is a rejected pattern, a timeout gives
    # `rc is None`, and a missing binary gives 127. They were two
    # branches returning the same value, which read as though the caller
    # could tell them apart.
    if r.timed_out or r.rc not in (0, 1):
        return None, pattern.mode

    found = []
    for line in r.out.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if event.get("type") != "match":
            continue
        data = event["data"]
        base = corpus.starts[int(Path(data["path"]["text"]).stem)]
        start = base + data["line_number"]
        text = data["lines"].get("text", "")
        # Under --multiline one match covers a region, and `line_number`
        # is only where it began.
        spanned = max(
            1, text.count("\n") if text.endswith("\n") else text.count("\n") + 1
        )
        found.append(Span(start, start + spanned - 1))
    return sorted(found, key=lambda s: s.start), pattern.mode


def matches(snippet: str, pattern: Pattern, lang: str) -> bool | None:
    """Does this pattern fire on this text? None when the search did not answer.

    The other half of `find`. `find` asks what a pattern hits in the
    corpus of compliant examples, where the answer must be nothing; this
    asks whether it hits a snippet that does contain the defect, where
    the answer must be something. A pattern that cannot answer either
    question is not a check.

    Prepared the way the corpus is, which is why `lang` is here. `find`
    searches the comment-stripped copy unless the pattern names a
    comment, and a fixture written verbatim is a different input: the
    two halves would then answer about two different texts, and a
    fixture whose match depends on comment content could certify a
    pattern the corpus path can never fire on.
    """
    if not pattern.over_comments:
        comment, quotes = syntax_for(lang)
        snippet = "\n".join(
            strip_comment(x, comment, quotes) for x in snippet.split("\n")
        )

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as work:
        target = Path(work) / "fixture.txt"
        target.write_text(snippet if snippet.endswith("\n") else snippet + "\n")
        answered = run(
            [
                tool_path("rg") or "rg",
                "--no-config",
                "--no-ignore",
                "--threads",
                "1",
                "--multiline",
                "--quiet",
                *(["--fixed-strings"] if pattern.mode == "-F" else []),
                "--regexp",
                pattern.text,
                str(target),
            ],
            timeout=30,
        )
    if answered.timed_out or answered.rc not in (0, 1):
        return None
    return answered.rc == 0
