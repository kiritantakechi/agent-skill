"""The standard's own Checks, run against its own examples.

Many rules end in a Check that is a literal `grep`. A standard whose examples
fail its own greps is not a standard, and nothing was running them.

The greps are run by `grep`, not reimplemented. Compiling a rule's pattern with
Python's `re` looked equivalent and was not: `[[:space:]]` parses as a character
class of `[:space` plus a literal `]` and matches nothing, so one Check was
reported as ran-and-clean while being incapable of firing; five whose pattern
ends in a bare `(` were dropped as unparseable; and `grep` without `-E` is BRE,
where `(` and `)` are literal, so reading `grep -rn 'pub fn main()' src/` as an
ERE accused eight correct examples of being the old entry point.
"""

from __future__ import annotations

import re
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from ..proc import run
from ..report import fail, note
from . import check

#: A backticked span is worth running only if it looks like code, not prose.
CODEISH = re.compile(r"[\[\](){}<>:\\|*+?^$]|_")
#: Patterns this broad match everything and teach nothing.
TOO_BROAD = {"pub ", "fn ", r"\.clone\(\)", "unsafe", "mut ", "&mut ", "impl "}
#: The quoted token in `grep -n 'pat' *.zig` that is the file, not the pattern.
#:
#: A miss here is not a false negative, it is a build break: an unrecognised file
#: argument becomes a `kind="command"` pattern, and a command-kind hit is tier 1
#: — so every example mentioning the filename would fail the standard. Python
#: configuration lives in bare top-level files rather than behind a glob, so the
#: names have to be listed the way `build.zig` already is.
FILE_ARG = re.compile(
    r"\*\.(zig|rs|py|md|toml|zon)$"
    r"|^src/|^references/"
    r"|^(build\.zig|pyproject\.toml|pytest\.toml|ruff\.toml|ty\.toml)$"
)

COMMAND = re.compile(r"`((?:grep|rg)\s[^`]*)`")
QUOTED = re.compile(r"'([^']*)'|\"([^\"]*)\"")


@dataclass(frozen=True, slots=True)
class Pattern:
    text: str
    mode: str  #: -F fixed, -E extended, -G basic
    kind: str  #: "command" — the Check ships it; "prose" — a span it names

    @property
    def over_comments(self) -> bool:
        """Does this Check mean the comment, rather than the code?

        A fact about the pattern, so it is asked once. `hits` and `lines_for`
        each spelled it, ten lines apart, and they have to agree: the exemption
        hook reads line `n` of whichever list `lines_for` returns, numbered by
        whichever file `hits` grepped.
        """
        return "//" in self.text


@dataclass
class Corpus:
    """Every line a rule's grep may be run over, and where each came from."""

    raw: list[str] = field(default_factory=list)
    code: list[str] = field(default_factory=list)
    index: list[tuple[str, str, int, str]] = field(default_factory=list)
    in_test: set[int] = field(default_factory=set)
    blocks: int = 0
    excluded: int = 0

    def build(self, skill, lang: str, work: Path) -> Corpus:
        from ..text import strip_comment, syntax_for

        comment, quotes = syntax_for(lang)

        advice = skill.advice(lang, verified=True)
        self.excluded = len(skill.blocks(lang, verified=True)) - len(advice)
        for b in advice:
            self.blocks += 1
            base = len(self.raw)
            self.in_test |= {base + i for i in skill.profile.inside_tests(b.body)}
            for j, line in enumerate(b.lines):
                # The marker classifies the block; it is not part of the example.
                kept = "" if line == b.marker.raw else line
                self.raw.append(kept)
                self.code.append(strip_comment(kept, comment, quotes))
                self.index.append((b.file, b.rule, b.at(j), line.strip()[:64]))
        self.raw_file = work / "raw.txt"
        self.code_file = work / "code.txt"
        self.raw_file.write_text("\n".join(self.raw) + "\n")
        self.code_file.write_text("\n".join(self.code) + "\n")
        return self

    def hits(self, pattern: Pattern):
        """Line numbers, or None when grep did not answer.

        grep exits 0 for a match, 1 for none, and 2 when it rejects the
        pattern — which is what the `-F` retry is for. Anything else is not an
        answer at all: a timeout gives `rc is None` and a missing grep gives
        127, and both carry an empty stdout. Reading that as zero hits would
        report a Check as clean on the strength of a run that never happened.
        """
        target = self.raw_file if pattern.over_comments else self.code_file
        for attempt in (pattern.mode, "-F"):
            r = run(["grep", "-n", attempt, "-e", pattern.text, str(target)], timeout=30)
            if r.timed_out or r.rc not in (0, 1, 2):
                return None, attempt
            if r.rc != 2:
                return [int(ln.split(":", 1)[0]) for ln in r.out.splitlines() if ln], attempt
        return None, pattern.mode

    def lines_for(self, pattern: Pattern) -> list[str]:
        return self.raw if pattern.over_comments else self.code


def grep_mode(command: str) -> str:
    """The dialect this command actually asks for."""
    flags = "".join(re.findall(r"(?<!\S)-([a-zA-Z]+)", command))
    if "F" in flags:
        return "-F"
    if "E" in flags or command.split()[0] == "rg":
        return "-E"
    return "-G"


def patterns_of(check_text: str) -> list[Pattern]:
    """Every runnable pattern a Check names.

    A pattern quoted inside a `grep`/`rg` command is what the Check tells the
    reader to run, in the dialect that command selects. A backticked span in
    prose is literal text the reader is told to look for, so it is a fixed
    string — compiling it as a regex turned `|x| f(x)` into an alternation that
    matched every line, which is how the first version produced five thousand
    hits.
    """
    out: list[Pattern] = []
    for command in COMMAND.findall(check_text):
        mode = grep_mode(command)
        for quoted in QUOTED.findall(command):
            text = quoted[0] or quoted[1]
            if not text or text.startswith("-") or FILE_ARG.search(text):
                continue
            out.append(Pattern(text, mode, "command"))
    if not out and re.search(
        r"\bgrep\b|\brg\b|\bscan\b|\bsearch for\b|\blook for\b", check_text, re.I
    ):
        for span in re.findall(r"`([^`\n]+)`", check_text):
            if len(span) < 4 or not CODEISH.search(span):
                continue
            if not re.match(r"^(references/|[A-Z]{2}-)", span):
                out.append(Pattern(span, "-F", "prose"))
    return [p for p in out if p.text not in TOO_BROAD]


@check("self-application", "the standard's own greps over its own examples")
def selfapply(skill):
    lang = skill.profile.languages[0] if skill.profile.languages else None
    if lang is None:
        return
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as work:
        yield from _run(skill, lang, Path(work))


def _run(skill, lang, work):
    profile = skill.profile
    corpus = Corpus().build(skill, lang, work)
    if not corpus.blocks or not skill.rules:
        yield fail(
            f"nothing to check: {corpus.blocks} blocks, {len(skill.rules)} rules — "
            f"an empty corpus passes every grep in the library",
            skill.name,
        )
        return

    claimed: set[str] = set()
    tier1: list[tuple] = []
    tier2: list[tuple] = []
    tier3: list[tuple] = []

    for rule in skill.rules:
        if not rule.check:
            continue
        # An entry suppresses this rule's grep, so it has to keep quoting words
        # the rule still says. Claimed before the path-scoped skip below, or a
        # `grep -v` rule with an entry would look like a rule that vanished.
        if entry := profile.not_decisive.get(rule.id):
            claimed.add(rule.id)
            if entry.anchor not in " ".join(rule.check.split()):
                yield fail(
                    f"{rule.id}: the exemption quotes {entry.anchor!r}, which its "
                    f"**Check:** no longer says",
                    skill.name,
                )
        # `grep … | grep -v '^src/lib.rs'` asks *which file* the hit is in. An
        # example block is a single crate root, so it cannot be evaluated here.
        if re.search(r"grep -v", rule.check):
            continue

        for pattern in patterns_of(rule.check):
            lines, used = corpus.hits(pattern)
            if lines is None:
                yield fail(
                    f"{rule.id}: grep gave no answer for its own Check pattern "
                    f"/{pattern.text}/ — rejected, timed out, or not installed",
                    skill.name,
                )
                continue
            exempt = profile.exempt.get(rule.id)
            source = corpus.lines_for(pattern)
            hits = [n for n in lines if not (exempt and exempt(source, n - 1, corpus.in_test))]
            if not hits:
                continue
            row = (rule, pattern, used, hits)
            if len(hits) > profile.judgement:
                tier3.append(row)
            elif pattern.kind == "command" and rule.id not in profile.not_decisive:
                tier1.append(row)
            else:
                tier2.append(row)

    # Only this skill's own entries: an entry naming a rule the skill no longer
    # defines is a suppression standing over nothing.
    for rid in sorted(set(profile.not_decisive) - claimed):
        yield fail(f"{rid}: the exemption names a rule this skill does not define", skill.name)

    for rule, pattern, used, hits in sorted(tier1, key=lambda r: -len(r[3])):
        yield fail(_render(corpus, rule, pattern, used, hits), skill.name)
    for rule, pattern, used, hits in sorted(tier2, key=lambda r: -len(r[3])):
        entry = profile.not_decisive.get(rule.id)
        why = entry.reason if entry else "prose span: the grep narrows, a person decides"
        yield note(_render(corpus, rule, pattern, used, hits, limit=3) + f"  ({why})", skill.name)
    for rule, pattern, used, hits in sorted(tier3, key=lambda r: -len(r[3])):
        yield note(
            _render(corpus, rule, pattern, used, hits, limit=0)
            + "  (enumerates rather than accuses)",
            skill.name,
        )


def _render(corpus, rule, pattern, used, hits, limit: int = 8) -> str:
    head = f"{rule.id} {used} /{pattern.text}/ — {len(hits)} hit(s) — {rule.title}"
    for h in hits[:limit]:
        chapter, owner, line, snippet = corpus.index[h - 1]
        head += f"\n      {chapter}:{line} [{owner}] {snippet}"
    if len(hits) > limit:
        head += f"\n      … {len(hits) - limit} more"
    return head
