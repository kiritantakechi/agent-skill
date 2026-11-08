"""The behavioural eval suite, generated from the standards.

`claude plugin eval` runs a suite of cases against the plugin: each a
prompt, and graders that score what the model did with it. The suite
is written here as a function of the standards and of each profile's
selection (`Profile.evals`), so no case tests a rule as it once read: a
BAD example rewritten, or a migration row moved, changes what is
generated, and the `evals` check fails until it is written again
(one-abstract-standard, decision 8).

Per standard, in the order the run reads them, which is their names':

- a review case per selected rule: its verified BAD example sent for
  review, graded on the reply citing the rule's ID;
- a migration case per selected old spelling: what the target writes
  in its place, graded on the reply giving the code span the target
  cell opens with, and citing the rule that owns the row;
- one negative case: the first review prompt of the first standard
  whose examples are in another language, graded on this standard's
  skill not firing, in both arms of the run.

Every grader is decided from the transcript, by a regex over the reply
or by which tool was called, so no case calls a judge. A literal a
grader seeks is escaped for JavaScript's `RegExp`, which compiles it.
Every review and migration case also reports whether its skill fired,
which a run comparing the plugin with no plugin leaves out of the
score, since without the plugin it cannot pass.

Nothing here runs the suite: each run is a model session on the
owner's credential, and the README gives the command.
"""

import json
import re
from dataclasses import dataclass
from enum import Enum
from typing import override
lazy from collections.abc import Iterator, Sequence
lazy from pathlib import Path

from agent_skill.doc import Doc, Fence, Paragraph, opening_span, words
from agent_skill.doc.chapter import ELIDED
from agent_skill.ids import Location, RuleId, cited_lines
from agent_skill.layout import EVALS, RESULTS
from agent_skill.model import SKILL_MD
lazy from agent_skill.checks.skeleton import gone_rows, target
lazy from agent_skill.doc import Block
lazy from agent_skill.doc.chapter import Migration
lazy from agent_skill.model import Skill, Tree
lazy from agent_skill.profiles import Evals, Profile

#: The case format `prompt.md` declares.
SCHEMA = "1.1"

#: Runs per case in each arm: the owner's run is a session per case
#: with the plugin, and one without it.
RUNS = 1

#: The turn cap, the format's own default, stated so that a change of
#: default cannot move it under a case.
TURNS = 10

#: The tools a run may use: the read-only ones a skill reads its
#: references with, and `Skill` to load it.
TOOLS = ("Read", "Glob", "Grep", "Skill")

#: The kinds of case, each a tag and its directory's first word.
REVIEW, MIGRATION, NEGATIVE = "review", "migration", "negative"

#: Each character JavaScript's `RegExp` reads as syntax outside a class,
#: and the `/` that would close a literal.
_SYNTAX = re.compile(r"[\\^$.|?*+()[\]{}/]")

#: A value YAML reads as itself when written bare: a word of letters,
#: digits and hyphens, unless it is one YAML reads as a boolean or null.
_PLAIN = re.compile(r"[A-Za-z][A-Za-z0-9-]*")
_RESERVED = frozenset({"y", "n", "yes", "no", "on", "off", "true", "false", "null"})


def literal(text: str) -> str:
    """`text` as a JavaScript regular expression finding it as written.

    Each character `RegExp` reads as syntax is escaped and nothing else
    is, since escaping a character that is not syntax is an error under
    the `u` flag.
    """
    return _SYNTAX.sub(lambda m: "\\" + m.group(), text)


def fired(skill: str) -> str:
    """A pattern over a `Skill` call's input that names `skill`.

    The form `claude plugin eval` documents, which also takes the name
    a plugin namespaces it by: `<plugin>:<skill>`.
    """
    return r'"skill"\s*:\s*"(?:[\w-]+:)?' + literal(skill) + '"'


class Invalid(Enum):
    """Why a selection names nothing a case can be built from."""

    #: the rule is not one of the standard's
    UNKNOWN_RULE = "unknown_rule"
    #: the rule has no `verified — BAD` example to review
    NO_BAD = "no_bad"
    #: the example cites a rule ID, which a reply could pass by quoting
    BAD_CITES = "bad_cites"
    #: the spelling is no `gone` row whose Since is the target's
    NOT_GONE = "not_gone"
    #: the spelling is a shape, whose replacement no literal finds
    SHAPE = "shape"
    #: the target cell opens with no code span for a grader to seek
    NO_CODE_SPAN = "no_code_span"


@dataclass(frozen=True, slots=True)
class Refused:
    """A selection no case can be built from: why, what, and where."""

    why: Invalid
    message: str
    where: Location

    @override
    def __str__(self) -> str:
        """The message, led by where the selection fails."""
        return f"{self.where}: {self.message}"


@dataclass(frozen=True, slots=True)
class Grader:
    """One grader: its file's name and its frontmatter, in order."""

    name: str
    #: each key, and its value as YAML spells it
    fields: tuple[tuple[str, str], ...]

    @property
    def text(self) -> str:
        """The grader's file: its frontmatter, and no body."""
        return str(Doc(_frontmatter(self.fields), ()))


@dataclass(frozen=True, slots=True)
class Case:
    """One case: the standard and kind it is tagged with, its prompt."""

    standard: str
    kind: str
    slug: str
    description: str
    prompt: tuple[Block, ...]
    graders: tuple[Grader, ...]

    @property
    def directory(self) -> str:
        """The case's directory, relative to the eval directory."""
        return f"{self.standard}/{self.kind}-{self.slug}"

    @property
    def name(self) -> str:
        """The name `--case` matches and the report keys on, unique."""
        return f"{self.standard}-{self.kind}-{self.slug}"

    @property
    def files(self) -> dict[str, str]:
        """Each file of the case, by its path in the eval directory."""
        fields = (
            ("schema_version", json.dumps(SCHEMA)),
            ("name", _scalar(self.name)),
            ("description", _quoted(self.description)),
            ("tags", _sequence((self.standard, self.kind))),
            ("runs", str(RUNS)),
            ("max_turns", str(TURNS)),
            ("allowed_tools", _sequence(TOOLS)),
        )
        prompt = str(Doc(_frontmatter(fields), self.prompt))
        return {f"{self.directory}/prompt.md": prompt} | {
            f"{self.directory}/graders/{g.name}.md": g.text for g in self.graders
        }


@dataclass(frozen=True, slots=True)
class Suite:
    """What the standards generate: the cases, or why there are none.

    A selection naming nothing a case can be built from leaves the
    suite undefined, so the cases are generated only when every
    selection is valid.
    """

    cases: tuple[Case, ...]
    refused: tuple[Refused, ...]

    @property
    def files(self) -> dict[str, str]:
        """Every file of every case, by its path, in sorted order."""
        merged = {rel: text for case in self.cases for rel, text in case.files.items()}
        return dict(sorted(merged.items()))


def generate(tree: Tree) -> Suite:
    """The suite the standards of `tree` and their selections make.

    No case when a selection is refused: each refusal says why. A
    standard whose profile selects nothing has no case.
    """
    read = [_read(skill, chosen) for skill in tree if (chosen := skill.profile.evals)]
    if refused := tuple(no for _, refusals in read for no in refusals):
        return Suite((), refused)
    every = tuple(chosen for chosen, _ in read)
    return Suite(tuple(case for chosen in every for case in _cases(chosen, every)), ())


def write(root: Path, suite: Suite) -> tuple[list[str], list[str]]:
    """Write `suite` under `root`'s eval directory, and remove the rest.

    What was written and what was removed, each by its path in the
    eval directory. A file already as generated is left alone, and so is
    every run's results directory; a directory the removals empty goes.
    """
    base, files = root / EVALS, suite.files
    written: list[str] = []
    for rel, text in files.items():
        path = base / rel
        if path.is_file() and path.read_text() == text:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        written.append(rel)
    removed = [rel for rel in on_disk(root) if rel not in files]
    for rel in removed:
        (base / rel).unlink()
    _prune(base, root / RESULTS)
    return written, removed


def compare(root: Path, suite: Suite) -> tuple[list[str], list[str]]:
    """What differs from `suite` under `root`'s eval directory.

    Each file the suite holds that is missing or differs, then each file
    the directory holds that the suite does not, by its path in the
    eval directory. A run's results are no file of the suite's.
    """
    base, files = root / EVALS, suite.files
    drifted = [
        rel
        for rel, text in files.items()
        if not (base / rel).is_file() or (base / rel).read_text() != text
    ]
    extra = [rel for rel in on_disk(root) if rel not in files]
    return drifted, extra


def on_disk(root: Path) -> list[str]:
    """Every file under `root`'s eval directory but a run's results.

    By its path in the eval directory, in sorted order.
    """
    base, results = root / EVALS, root / RESULTS
    if not base.is_dir():
        return []
    return sorted(
        p.relative_to(base).as_posix()
        for p in base.rglob("*")
        if not p.is_dir() and not p.is_relative_to(results)
    )


def _prune(base: Path, results: Path) -> None:
    """Remove each directory under `base` that holds no file.

    Deepest first, so a directory emptied by removing the ones under it
    goes as well; the results directory is never touched.
    """
    if not base.is_dir():
        return
    for path in sorted(base.rglob("*"), key=lambda p: len(p.parts), reverse=True):
        if (
            path.is_dir()
            and not path.is_relative_to(results)
            and not any(path.iterdir())
        ):
            path.rmdir()


# ------------------------------------------------------------------
# what a selection is read as


@dataclass(frozen=True, slots=True)
class _Example:
    """A selected rule's BAD example: the code a review case sends."""

    rule: RuleId
    lang: str
    code: str

    @property
    def slug(self) -> str:
        """The rule's ID, as a directory name spells it."""
        return str(self.rule).lower()


@dataclass(frozen=True, slots=True)
class _Row:
    """A selected spelling's row: what replaces it, and whose it is."""

    spelling: str
    #: the code span the target cell opens with
    replacement: str
    #: the rule the row names
    owner: str

    @property
    def slug(self) -> str:
        """The spelling's words, lowercased and joined by hyphens.

        A capital after a lowercase letter or a digit starts a word, as
        in `indexOfIgnoreCase`; a spelling with no word is `spelling`.
        """
        split = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "-", self.spelling)
        return "-".join(map(str, re.findall(r"[a-z0-9]+", split.lower()))) or "spelling"


@dataclass(frozen=True, slots=True)
class _Chosen:
    """A standard's selection, read: what its cases are built from."""

    skill: Skill
    examples: tuple[_Example, ...]
    rows: tuple[_Row, ...]


def _read(skill: Skill, chosen: Evals) -> tuple[_Chosen, tuple[Refused, ...]]:
    """`skill`'s selection, read, and each part of it refused."""
    read = (
        *(_example(skill, rid) for rid in chosen.review),
        *(_row(skill, spelling) for spelling in chosen.migrate),
    )
    return (
        _Chosen(
            skill,
            tuple(r for r in read if isinstance(r, _Example)),
            tuple(r for r in read if isinstance(r, _Row)),
        ),
        tuple(r for r in read if isinstance(r, Refused)),
    )


def _example(skill: Skill, rid: RuleId) -> _Example | Refused:
    """The BAD example `rid` is reviewed by, or why there is none.

    The first `verified — BAD` block under the rule, in any language
    the standard marks, with its marker line taken out: the marker
    says what the block is, which is the answer the case asks for.
    """
    if rid not in skill.ids:
        return Refused(
            Invalid.UNKNOWN_RULE,
            f"{rid} is no rule of {skill.name}, so it has no BAD example to review",
            skill.at(),
        )
    bad = sorted(
        (
            b
            for lang in skill.profile.all_marked
            for b in skill.blocks(lang)
            if b.rule == rid and b.marker.verified and b.marker.bad
        ),
        key=lambda b: (b.file, b.line),
    )
    if not bad:
        return Refused(
            Invalid.NO_BAD,
            f"{rid} has no `verified — BAD` example, so a review case has no code "
            "to send",
            _rule_at(skill, rid),
        )
    block = bad[0]
    lines = block.lines
    marker = lines.index(block.marker.raw)
    for found, number in cited_lines(block.body):
        if number - 1 != marker:
            return Refused(
                Invalid.BAD_CITES,
                f"{rid}'s BAD example cites {found}, so a reply quoting the prompt "
                "would be graded as citing a rule",
                block.where_at(number - 1),
            )
    code = "\n".join(lines[:marker] + lines[marker + 1 :]).strip("\n")
    return _Example(rid, block.lang, code)


def _row(skill: Skill, spelling: str) -> _Row | Refused:
    """The migration row `spelling` is asked about, or why it is none.

    A `gone` row whose Since is the target's, as section 2.2 lists it,
    whose old spelling is not a shape and whose target cell opens with
    the code span the grader seeks.
    """
    gone = {row.spelling: (row, where) for row, where in gone_rows(skill)}
    found = gone.get(spelling)
    where = found[1] if found is not None else skill.at()
    if ELIDED in spelling:
        return Refused(
            Invalid.SHAPE,
            f"`{spelling}` is a shape, which stands for code left out, so no literal "
            "finds what the target writes in its place",
            where,
        )
    row: Migration | None = found[0] if found is not None else None
    if row is None or row.landed not in skill.profile.since:
        since = ", ".join(sorted(map(str, skill.profile.since))) or "the target"
        return Refused(
            Invalid.NOT_GONE,
            f"`{spelling}` is no `gone` row of the migration table whose Since is "
            f"{since}: a migration case asks what the target writes in place of a "
            "spelling it rejects",
            where,
        )
    replacement = opening_span(row.new)
    if replacement is None:
        return Refused(
            Invalid.NO_CODE_SPAN,
            f"the target cell of `{spelling}` opens with no code span, which is what "
            f"a migration case's grader seeks: {row.new[:60]!r}",
            where,
        )
    return _Row(spelling, replacement, row.rule)


def _rule_at(skill: Skill, rid: RuleId) -> Location:
    """Where `rid` is stated in `skill`: its chapter, or `SKILL.md`."""
    for chapter in skill.chapters:
        for rule in chapter.typed.rules:
            if rule.id == rid:
                return chapter.where(rule.line, rid)
    for rule in skill.core:
        if rule.id == rid:
            return skill.at(SKILL_MD, rule.line, rid)
    return skill.at(rule=rid)


# ------------------------------------------------------------------
# the cases


def _cases(chosen: _Chosen, every: Sequence[_Chosen]) -> Iterator[Case]:
    """`chosen`'s cases: each review, each migration, its negative.

    `every` is each standard's selection, in the run's order, which the
    negative case takes its prompt from.
    """
    skill, taken = chosen.skill, set[str]()
    for example in chosen.examples:
        yield _review(skill, example, _free(example.slug, taken))
    for row in chosen.rows:
        yield _migration(skill, row, _free(row.slug, taken))
    if (case := _negative(chosen, every)) is not None:
        yield case


def _review(skill: Skill, example: _Example, slug: str) -> Case:
    """The case reviewing `example`, graded on its rule's ID."""
    rid = str(example.rule)
    return Case(
        skill.name,
        REVIEW,
        slug,
        f"The BAD example of {rid}, sent for review; the reply cites {rid}.",
        _reviewed(skill.profile, example),
        (
            _regex("cites-rule", rid),
            _fired(skill.name),
        ),
    )


def _reviewed(profile: Profile, example: _Example) -> tuple[Block, ...]:
    """The prompt of a review case: the request, then the code."""
    asked = (
        f"Review this {profile.language} code against the project's standards; "
        "report each problem with the rule it breaks:"
    )
    return (Paragraph(words(asked)), Fence(example.lang, f"{example.code}\n"))


def _migration(skill: Skill, row: _Row, slug: str) -> Case:
    """The case asking what replaces `row`'s spelling, by which rule."""
    release = target(skill)
    told = (
        f"This {skill.profile.language} code was written for an earlier release, "
        f"and {release} rejects it:"
    )
    asked = (
        f"What does {release} write in its place, and which rule of the project's "
        "standards says so?"
    )
    return Case(
        skill.name,
        MIGRATION,
        slug,
        f"What {release} writes for `{row.spelling}`; the reply gives "
        f"`{row.replacement}` and cites {row.owner}.",
        (
            Paragraph(words(told)),
            Fence(_language(skill.profile), f"{row.spelling}\n"),
            Paragraph(words(asked)),
        ),
        (
            _regex("target-spelling", row.replacement),
            _regex("cites-rule", row.owner),
            _fired(skill.name),
        ),
    )


def _negative(chosen: _Chosen, every: Sequence[_Chosen]) -> Case | None:
    """The case this standard's skill must not fire on, if any.

    The first review prompt of the first standard of `every` whose
    examples are in another language; None when every standard with a
    review case writes this one's.
    """
    skill = chosen.skill
    mine = _language(skill.profile)
    for other in every:
        if other.examples and _language(other.skill.profile) != mine:
            return Case(
                skill.name,
                NEGATIVE,
                other.skill.name,
                f"The first review prompt of {other.skill.name}, in another "
                f"language; {skill.name}'s skill does not fire, with the plugin or "
                "without it.",
                _reviewed(other.skill.profile, other.examples[0]),
                (
                    Grader(
                        "skill-silent",
                        (
                            ("type", "tool_used"),
                            ("tool", "Skill"),
                            ("input_match", _quoted(fired(skill.name))),
                            ("min", "0"),
                            ("max", "0"),
                            ("arm", "both"),
                        ),
                    ),
                ),
            )
    return None


def _regex(name: str, sought: str) -> Grader:
    """A grader passing when the reply holds `sought`, as written."""
    return Grader(name, (("type", "regex"), ("pattern", _quoted(literal(sought)))))


def _fired(skill: str) -> Grader:
    """The indicator that `skill`'s skill was loaded.

    Scored only in a run of one arm: in a run against no plugin it
    cannot pass, so a run of both leaves it out of the score.
    """
    return Grader(
        "skill-fired",
        (
            ("type", "tool_used"),
            ("tool", "Skill"),
            ("input_match", _quoted(fired(skill))),
        ),
    )


def _language(profile: Profile) -> str:
    """The fence tag a standard's examples are written under first."""
    return profile.all_marked[0] if profile.all_marked else ""


def _free(slug: str, taken: set[str]) -> str:
    """`slug`, or `slug` and the first number `taken` does not hold."""
    chosen, n = slug, 1
    while chosen in taken:
        n += 1
        chosen = f"{slug}-{n}"
    taken.add(chosen)
    return chosen


# ------------------------------------------------------------------
# YAML, as much of it as a case's frontmatter needs


def _frontmatter(fields: Sequence[tuple[str, str]]) -> str:
    """`key: value` lines, each value already spelled as YAML."""
    return "\n".join(f"{key}: {value}" for key, value in fields)


def _scalar(value: str) -> str:
    """`value` as a YAML scalar: bare when it reads back as itself."""
    if _PLAIN.fullmatch(value) and value.lower() not in _RESERVED:
        return value
    return _quoted(value)


def _quoted(value: str) -> str:
    """`value` single-quoted, in which YAML reads no escape but `''`."""
    return "'" + value.replace("'", "''") + "'"


def _sequence(values: Sequence[str]) -> str:
    """`values` as a YAML flow sequence: `[Read, Glob]`."""
    return "[" + ", ".join(_scalar(v) for v in values) + "]"
