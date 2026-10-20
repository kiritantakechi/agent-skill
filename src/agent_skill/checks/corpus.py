"""The examples a pattern is run over, one file each.

Separate from the search: this module says what is searched, `search`
says how.
"""

import bisect
import tempfile
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path

lazy from agent_skill.checks.patterns import Pattern
lazy from agent_skill.model import Skill
lazy from agent_skill.text import strip_comment, syntax_for


@dataclass(frozen=True, slots=True)
class Unit:
    """One example, written as its own file.

    Its own file, and not a region of a shared one, because a multi-line
    pattern matches across whatever it is given. Measured on the
    concatenated corpus: a `try:` in one example paired with a
    `finally:` in the next and reported a hit neither example contains.
    A file boundary is the only separator a pattern cannot cross — no
    sentinel line survives `(?s).*`.
    """

    chapter: str
    rule: str
    raw: list[str]
    code: list[str]
    at: list[int]  #: the line each local line came from, in the chapter


@dataclass
class Corpus:
    """Every line a rule's pattern may be run over, and its origin."""

    units: list[Unit] = field(default_factory=list)
    in_test: set[int] = field(default_factory=set)
    raw_dir: Path | None = None
    code_dir: Path | None = None
    #: Global line of each unit's first line, so a hit can be numbered
    #: across the corpus without a parallel array of one entry per line.
    starts: list[int] = field(default_factory=list)

    @property
    def blocks(self) -> int:
        """How many examples the corpus holds, one unit each."""
        return len(self.units)

    def build(self, skill: Skill, lang: str, work: Path) -> Corpus:
        """Fill the corpus with `skill`'s verified `lang` advice."""
        comment, quotes = syntax_for(lang)
        suffix = {"rust": ".rs", "python": ".py", "zig": ".zig"}.get(lang, ".txt")
        self.raw_dir, self.code_dir = work / "raw", work / "code"
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.code_dir.mkdir(parents=True, exist_ok=True)

        advice = skill.advice(lang, verified=True)
        # Carried, not recomputed. `sum(len(u.raw) for u in self.units)`
        # walked every unit built so far on each iteration, and it is a
        # second derivation of the number `starts` already holds — the
        # one `find` indexes and `origin` subtracts from. Two
        # derivations of one quantity agree until someone edits one, and
        # editing this one silently renumbers every hit in the report.
        base = 0
        for n, b in enumerate(advice):
            self.starts.append(base)
            self.in_test |= {base + i for i in skill.profile.inside_tests(b.body)}
            # The marker classifies the block; it is not part of the
            # example.
            raw = ["" if line == b.marker.raw else line for line in b.lines]
            self.units.append(
                Unit(
                    b.file,
                    b.rule,
                    raw,
                    [strip_comment(x, comment, quotes) for x in raw],
                    [b.at(j) for j in range(len(b.lines))],
                )
            )
            name = f"{n:04d}{suffix}"
            (self.raw_dir / name).write_text("\n".join(raw) + "\n")
            (self.code_dir / name).write_text("\n".join(self.units[-1].code) + "\n")
            base += len(raw)
        return self

    def origin(self, line: int) -> tuple[str, str, int, str]:
        """Where a global line came from, derived rather than tabulated.

        The parallel array this replaces held one row per line and had
        to be appended in lockstep with two others; a unit already knows
        its chapter, its rule, and which source line each of its lines
        came from.
        """
        i = bisect.bisect_right(self.starts, line - 1) - 1
        unit = self.units[i]
        local = line - 1 - self.starts[i]
        return unit.chapter, unit.rule, unit.at[local], unit.raw[local].strip()[:64]

    def lines_for(self, pattern: Pattern) -> list[str]:
        """Every line, in the form `pattern` is searched against."""
        which = "raw" if pattern.over_comments else "code"
        return [line for unit in self.units for line in getattr(unit, which)]


#: One corpus per tree, because two checks want the same one. Keyed by
#: the skill's *root*, never by its name: `controls` copies the whole
#: tree, injects a defect, and re-runs a check over the copy — sharing
#: by name would hand it the unmodified corpus and the control would
#: stop firing while still reporting.
#:
#: Bounded, because that keying means a `controls` run produces one
#: entry per injected tree — around thirty — and every one of those
#: trees is deleted the moment its control finishes. An unbounded cache
#: holds a directory per dead tree for the life of the process.
_KEEP = 8
_BUILT: OrderedDict[
    tuple[str, str], tuple[Corpus, tempfile.TemporaryDirectory[str]]
] = OrderedDict()


def corpus_for(skill: Skill, lang: str) -> Corpus:
    """The corpus for this tree, built once and shared.

    604 blocks become 604 files once each example is its own file.
    `selfapply` and `crossref` each building their own made that 1208
    writes per run for byte-identical content.
    """
    key = (str(skill.root), lang)
    if key in _BUILT:
        _BUILT.move_to_end(key)
        return _BUILT[key][0]

    holder = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
    built = Corpus().build(skill, lang, Path(holder.name))
    _BUILT[key] = (built, holder)
    while len(_BUILT) > _KEEP:
        _, (_, evicted) = _BUILT.popitem(last=False)
        evicted.cleanup()
    return built
