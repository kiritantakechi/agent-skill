"""The values the harness reasons about, each with one spelling.

A rule ID, a tier, a location, a version, a pin, the answer a tool did
or did not give, and the branch a finding came from. Each is a frozen
value with one parser and one printer, and every other module reads and
writes them through these. A concept spelled in two places is read two
ways, and a defect in one reading is invisible to every check written
against the other.

A parser raises `ValueError` on text that is not the value: reading
input is not asking a question of the world, so its failure is not a
`NoAnswer`.
"""

import re
from dataclasses import dataclass
from enum import Enum
from string import ascii_lowercase
from typing import Self, override
lazy from collections.abc import Callable, Iterator, Mapping

#: A standard's prefix, such as `RS`.
STANDARD = r"[A-Z]{2}"

#: A rule family's code, such as `ERR` or `CORE`.
FAMILY = r"[A-Z]+"

#: The number a rule ID ends in. A letter after it marks a rule
#: inserted between two others, as in `XS-ERR-12a`, until a
#: renumbering closes the gap. The letter is part of every spelling:
#: a pattern that leaves it out reads an inserted rule as no rule.
NUMBER = r"\d+[a-z]?"


def rule_id(prefix: str = STANDARD, family: str = FAMILY) -> str:
    """A regex, with no groups, for a whole rule ID under `prefix`.

    The one pattern a rule ID is matched with. `RuleId.parse` reads
    through it too, so a scanner and the parser cannot disagree about
    what an ID is.
    """
    return rf"{prefix}-{family}-{NUMBER}"


@dataclass(frozen=True, slots=True, order=True)
class RuleId:
    """A rule's identity: standard, family, number and inserted letter.

    Ordered by those four in turn, so within a family the order is
    numeric (`-09` before `-10`) and an inserted `-12a` sits between
    `-12` and `-13`. Printed with the number zero-padded to two digits.
    """

    standard: str
    family: str
    number: int
    suffix: str = ""

    def __post_init__(self) -> None:
        """Refuse a part that could not be printed and read back."""
        if not (
            re.fullmatch(STANDARD, self.standard)
            and re.fullmatch(FAMILY, self.family)
            and self.number >= 0
            and re.fullmatch(r"[a-z]?", self.suffix)
        ):
            msg = f"not the parts of a rule ID: {self!r}"
            raise ValueError(msg)

    @classmethod
    def parse(cls, text: str) -> Self:
        """The rule ID `text` spells: `RS-ERR-03`, `XS-ERR-12a`."""
        if not re.fullmatch(rule_id(), text):
            msg = f"not a rule ID: {text!r}"
            raise ValueError(msg)
        standard, family, tail = text.split("-", 2)
        digits = tail.rstrip(ascii_lowercase)
        return cls(standard, family, int(digits), tail[len(digits) :])

    @classmethod
    def try_parse(cls, text: str) -> Self | None:
        """The rule ID `text` spells whole, or None when it is not one.

        For a token that may or may not be an ID, such as a table cell
        or a paragraph's first word: not being one is an answer there,
        not an error.
        """
        try:
            return cls.parse(text)
        except ValueError:
            return None

    @override
    def __str__(self) -> str:
        """`RS-ERR-03`: the number in two digits, then any letter."""
        return f"{self.standard}-{self.family}-{self.number:02d}{self.suffix}"


def _whole(standard: str) -> re.Pattern[str]:
    """An ID under `standard` with no word character on either side.

    A word character beside it would make it part of something else.
    """
    return re.compile(rf"\b{rule_id(standard)}\b")


def cited(text: str, standard: str = STANDARD) -> Iterator[RuleId]:
    """Each rule ID `text` names under `standard`, in order.

    For text the document model keeps whole rather than splitting into
    tokens: a paragraph's citations, a table cell, an example, a source
    file.
    """
    for rid, _ in cited_at(text, standard):
        yield rid


def cited_at(text: str, standard: str = STANDARD) -> Iterator[tuple[RuleId, int]]:
    """Each rule ID `text` names under `standard`, and where it ends.

    For a reader of what follows a citation: `RS-ERR-03 below` points by
    position, which breaks when the rule moves, and only the text after
    the ID says so.
    """
    for m in _whole(standard).finditer(text):
        yield RuleId.parse(m.group()), m.end()


def cited_lines(text: str, standard: str = STANDARD) -> Iterator[tuple[RuleId, int]]:
    """Each rule ID `text` names under `standard`, and its line, from 1.

    For a file read whole, outside the document model, whose findings
    still need a line: an ID never spans one, so each line is searched
    alone. A line ends at a newline and nowhere else, as an editor
    counts them; `str.splitlines` also ends one at a form feed.
    """
    for number, line in enumerate(text.split("\n"), 1):
        for rid in cited(line, standard):
            yield rid, number


def uncited(text: str, standard: str = STANDARD) -> str:
    """`text` with each rule ID it names under `standard` taken out."""
    return _whole(standard).sub("", text)


def leading(text: str) -> RuleId | None:
    """The rule ID `text` opens with, or None when it opens otherwise.

    As a word citing a rule does, whatever follows the ID: `RS-ERR-03),`
    or `ZS-ERR-01's`. A word character after the ID and its inserted
    letter would make it part of something else, so `RS-ERR-03ab`
    opens with none.
    """
    m = re.match(rf"{rule_id()}\b", text)
    return RuleId.parse(m.group()) if m else None


#: The en dash a range of IDs is written with, as prose writes a range
#: of numbers.
DASH = "\u2013"

#: A range as prose states one: two IDs, each in a code span, joined by
#: the dash; or one ID alone, a range of one.
_RANGE = re.compile(rf"`({rule_id()})`(?:{DASH}`({rule_id()})`)?")


def ranges(text: str) -> Iterator[tuple[RuleId, RuleId]]:
    """Each range of IDs `text` states, as its first and its last.

    A rename table opens with the ranges its families ran before the
    revision, and an ID in range that no row lists still names its rule,
    so the ranges are read as exactly as the rows are.
    """
    for m in _RANGE.finditer(text):
        yield RuleId.parse(m[1]), RuleId.parse(m[2] or m[1])


def print_range(first: RuleId, last: RuleId) -> str:
    """The range from `first` to `last`, as `ranges` reads one.

    The two IDs in code spans joined by `DASH`, or the one ID alone for
    a range of one; so a table a revision writes reads back as the
    ranges it was written from.
    """
    return f"`{first}`" + (f"{DASH}`{last}`" if last != first else "")


#: A rule ID, or a family alone: `RS-ERR-03`, or `RS-ERR` with no number
#: after it. The same parts as `rule_id`, the number made optional.
_TOKEN = re.compile(rf"\b(?P<family>{STANDARD}-{FAMILY})(?:-(?P<number>{NUMBER}))?\b")


def respell(
    text: str, ids: Mapping[RuleId, RuleId], families: Mapping[str, str]
) -> str:
    """`text` with each ID `ids` maps and each family `families` maps.

    One pass over the text, from one dictionary. Dense numbering reuses
    IDs — the old `-03` is the new `-02` while another rule becomes the
    new `-03` — so a chain of replacements would rewrite the overlap
    twice, and the result would read exactly like a correct one. A
    family is spelled with its prefix, `RS-ERR`, and is matched only
    where no number follows it. Anything neither maps is left as
    written.
    """

    def swap(m: re.Match[str]) -> str:
        if m["number"] is None:
            return families.get(m.group(), m.group())
        rid = RuleId.parse(m.group())
        return str(ids[rid]) if rid in ids else m.group()

    return _TOKEN.sub(swap, text)


class Tier(Enum):
    """How binding a rule is: `[M]`, `[M!]` or `[S]`.

    A chapter rule and a core rule carry the same type, so a comparison
    between them cannot fail on spelling.
    """

    M = "M"
    M_BANG = "M!"
    S = "S"

    @classmethod
    def parse(cls, text: str) -> Tier:
        """The tier `text` spells, brackets included."""
        inner = text.removeprefix("[").removesuffix("]")
        if f"[{inner}]" != text or inner not in {t.value for t in cls}:
            msg = f"not a tier: {text!r}"
            raise ValueError(msg)
        return cls(inner)

    @override
    def __str__(self) -> str:
        """`[M]`, `[M!]` or `[S]`."""
        return f"[{self.value}]"


#: A skill's directory name.
_SKILL = re.compile(r"[a-z0-9][a-z0-9-]*")

#: A file path as a location prints it: no whitespace, no colon, which
#: separates the line, and no bracket, which encloses the rule.
_FILE = re.compile(r"[^\s:\[\]]+")


@dataclass(frozen=True, slots=True)
class Location:
    """Where a finding is: skill, file, line and rule, as far as known.

    `file` is relative to the skill when there is one and to the
    repository when there is not. Printed `skill/file:line [rule]`; a
    file outside any skill is printed `./file`, because a bare path
    would read as a skill and its file.
    """

    skill: str | None = None
    file: str | None = None
    line: int | None = None
    rule: RuleId | None = None

    def __post_init__(self) -> None:
        """Refuse a location its own printer could not spell."""
        if self.skill is not None and not _SKILL.fullmatch(self.skill):
            msg = f"not a skill name: {self.skill!r}"
            raise ValueError(msg)
        if self.file is not None and not _FILE.fullmatch(self.file):
            msg = f"not a file a location can name: {self.file!r}"
            raise ValueError(msg)
        if self.line is not None and (self.file is None or self.line < 1):
            msg = f"a line is a positive line of a file: {self!r}"
            raise ValueError(msg)

    @classmethod
    def parse(cls, text: str) -> Self:
        """The location `text` spells, as `__str__` prints one."""
        head, rule = text, None
        if text.endswith("]") and "[" in text:
            head, _, bracketed = text.rpartition("[")
            rule = RuleId.parse(bracketed.removesuffix("]"))
            if head and not head.endswith(" "):
                msg = f"not a location: {text!r}"
                raise ValueError(msg)
            head = head.removesuffix(" ")
        path, colon, digits = head.rpartition(":")
        line = None
        if colon and digits.isdigit():
            head, line = path, int(digits)
        skill: str | None = None
        file: str | None = None
        if head.startswith("./"):
            file = head.removeprefix("./")
        elif "/" in head:
            skill, file = head.split("/", 1)
        elif head:
            skill = head
        return cls(skill, file, line, rule)

    @override
    def __str__(self) -> str:
        """`rust-style/references/errors.md:42 [RS-ERR-03]`, or less."""
        if self.skill is not None:
            path = self.skill if self.file is None else f"{self.skill}/{self.file}"
        else:
            path = "" if self.file is None else f"./{self.file}"
        if self.line is not None:
            path += f":{self.line}"
        if self.rule is None:
            return path
        return f"{path} [{self.rule}]" if path else f"[{self.rule}]"


class Stage(Enum):
    """How far a release has come, in the order releases reach them."""

    ALPHA = "a"
    BETA = "b"
    CANDIDATE = "rc"
    FINAL = ""

    def __lt__(self, other: Stage) -> bool:
        """Is this stage reached before `other`?"""
        order = list(Stage)
        return order.index(self) < order.index(other)


#: A version has at least a major and a minor number.
_MAJOR_MINOR = 2

#: A version's release numbers, a pre-release stage and its count, then
#: a local label. No leading zeros, so every text it accepts is the one
#: it prints.
_VERSION = re.compile(
    r"(?P<release>(?:0|[1-9]\d*)(?:\.(?:0|[1-9]\d*))+)"
    r"(?:(?P<stage>a|b|rc)(?P<candidate>0|[1-9]\d*))?"
    r"(?:\+(?P<local>[a-z0-9]+(?:\.[a-z0-9]+)*))?"
)

#: A local label: what follows a `+`.
_LOCAL = re.compile(r"[a-z0-9]+(?:\.[a-z0-9]+)*")

#: An edition: a year, four digits, as Rust names one. One number where
#: a release has at least two, so neither reads as the other.
_EDITION = re.compile(r"[1-9]\d{3}")

#: A version among other words: no word character or dot on either
#: side, so a version is never read out of a longer token.
_NAMED = re.compile(rf"(?<![\w.]){_VERSION.pattern}(?![\w.])")

#: How many numbers a published release has: major, minor and patch.
_RELEASED = 3


@dataclass(frozen=True, slots=True, order=True)
class Version:
    """A release: its numbers, its stage if it is not final, its build.

    Ordered so a final release follows its candidates (`3.15.0rc2` <
    `3.15.0`), which a string comparison gets backwards, and so a
    version that stops at the minor sorts before every patch of it
    (`1.99` < `1.99.0`).

    `local` is PEP 440's local label, which `uv` uses for a build of an
    interpreter: `3.15.2+freethreaded` is release 3.15.2, built free of
    the GIL. It is part of what a pin holds the tool to, and not of the
    release a title names, which is `public`.

    An edition is a version too: a year, one number, `2024`. A language
    whose changes land in editions as well as releases keys a migration
    row by either, and one parser reads both (normalize-the-standards,
    decision 9). It orders among editions; it is never found among
    other words, and it is never a published release.
    """

    release: tuple[int, ...]
    stage: Stage = Stage.FINAL
    candidate: int = 0
    local: str = ""

    def __post_init__(self) -> None:
        """Refuse a version its own printer could not spell."""
        if (
            (len(self.release) < _MAJOR_MINOR and not self._spells_edition)
            or min(self.release) < 0
            or self.candidate < 0
            or (self.stage is Stage.FINAL and self.candidate != 0)
            or (self.local and not _LOCAL.fullmatch(self.local))
        ):
            msg = f"not the parts of a version: {self!r}"
            raise ValueError(msg)

    @classmethod
    def parse(cls, text: str) -> Self:
        """The version `text` spells: `0.17.3`, `3.15.0rc1`, `2024`."""
        if _EDITION.fullmatch(text):
            return cls((int(text),))
        m = _VERSION.fullmatch(text)
        if m is None:
            msg = f"not a version this can order: {text!r}"
            raise ValueError(msg)
        release = tuple(int(n) for n in m["release"].split("."))
        local = m["local"] or ""
        if m["stage"] is None:
            return cls(release, local=local)
        return cls(release, Stage(m["stage"]), int(m["candidate"]), local)

    @classmethod
    def try_parse(cls, text: str) -> Self | None:
        """The version `text` spells whole, or None when it is not one.

        For an answer from outside — an index, a channel, a release list
        — where not being a version is an answer to report, not an
        error.
        """
        try:
            return cls.parse(text)
        except ValueError:
            return None

    @classmethod
    def search(cls, text: str) -> Self | None:
        """The first version `text` names, or None when it names none.

        As a tool's `--version` line names its own, among other words:
        `ripgrep 15.2.0 (rev e89fff89ac)`, `rustc 1.99.0-nightly (…)`.
        A version run into a word or another number on either side is
        not one: `1.2.3.post1` names none.
        """
        m = _NAMED.search(text)
        return cls.parse(m.group()) if m else None

    @classmethod
    def released(cls, text: str) -> Self | None:
        """`text` as a release a pin is compared with, or None.

        Three numbers and at most a pre-release stage: the precision a
        pin and the place that publishes releases share. Anything else
        is no answer, never a release that happens to compare. `15.2`
        orders before `15.2.0`, so an index answering in a coarser form
        would read as older than the pin and the pin as current, on a
        comparison nobody made; and a local label is a build, not a
        release.
        """
        found = cls.try_parse(text)
        if found is None or len(found.release) != _RELEASED or found.local:
            return None
        return found

    @property
    def _spells_edition(self) -> bool:
        """Is this one number `_EDITION` reads, and nothing else?"""
        return (
            len(self.release) == 1
            and _EDITION.fullmatch(str(self.release[0])) is not None
            and self.stage is Stage.FINAL
            and not self.local
        )

    @property
    def edition(self) -> bool:
        """Is this an edition, `2024`, rather than a release?"""
        return len(self.release) == 1

    @property
    def public(self) -> Version:
        """This release without its local label: `3.15.2`."""
        return Version(self.release, self.stage, self.candidate)

    @property
    def series(self) -> Version:
        """The major.minor this release is of: `3.15` of `3.15.0rc1`.

        What a standard's title names, and the series a pin is refreshed
        within: a newer patch moves the pin, a newer minor is a new
        target.
        """
        return Version(self.release[:_MAJOR_MINOR])

    @override
    def __str__(self) -> str:
        """`0.17.3`, `1.99`, `3.15.0rc1`, `3.15.2+freethreaded`."""
        printed = ".".join(str(n) for n in self.release)
        if self.stage is not Stage.FINAL:
            printed += f"{self.stage.value}{self.candidate}"
        return f"{printed}+{self.local}" if self.local else printed


def releases(text: str, major: int) -> Iterator[Version]:
    """Each release of `major` that prose names, as its major.minor.

    `3.13` in a Python standard, `since 3.9`, `0.19` in a Bevy one. The
    minor is any number that does not start with `0`, which keeps a
    decimal such as `0.05` out, and is not followed by a letter, which
    keeps `3.5x faster` out. A leading `~` marks a quantity, never a
    release: `~0.3 ns`. A patch after the minor is the same series:
    `3.13.1` names `3.13`.
    """
    for m in re.finditer(rf"(?<![\d.~]){major}\.([1-9]\d*)(?!\w)", text):
        yield Version((major, int(m[1])))


class Op(Enum):
    """How a pin holds its tool to its version, as its file spells it.

    Every pin but a floor is exact. They differ in spelling only, and
    each is the spelling of the file the pin is copied into: a Python
    requirement, a Cargo dependency, a `uv` interpreter request.
    """

    #: A Python requirement: `ruff==0.17.3`.
    EXACT = "=="
    #: A Python requirement's floor: `ty>=0.0.60`.
    FLOOR = ">="
    #: Cargo's exact requirement, `version = "=0.20.1"`: `bevy=0.20.1`.
    CARGO = "="
    #: `uv`'s interpreter request: `cpython-3.15.2+freethreaded`.
    REQUEST = "-"


#: A tool's name, as a pin spells it.
_TOOL = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")

#: An interpreter's name in a request: letters only, so the first `-`
#: is the one that divides it from the version.
_IMPLEMENTATION = re.compile(r"[a-z]+")

#: A tool's name, then the operator, then the version. The name holds
#: no `=` or `>`, so the first of them divides it from the operator.
_PIN = re.compile(
    rf"(?P<tool>{_TOOL.pattern})(?P<op>==|>=|=)(?P<version>\S+)"
    rf"|(?P<implementation>{_IMPLEMENTATION.pattern})-(?P<requested>\S+)"
)


@dataclass(frozen=True, slots=True)
class Pin:
    """A tool held to a version: exactly, or as a floor.

    An exact pin holds the tool at the precision it states: `rust==1.99`
    is met by every 1.99 patch release, and moved by 1.100.
    """

    tool: str
    version: Version
    op: Op = Op.EXACT

    def __post_init__(self) -> None:
        """Refuse a tool name its own printer could not spell."""
        name = _IMPLEMENTATION if self.op is Op.REQUEST else _TOOL
        if not name.fullmatch(self.tool):
            msg = f"not a tool name for {self.op.value!r}: {self.tool!r}"
            raise ValueError(msg)

    @classmethod
    def parse(cls, text: str) -> Self:
        """The pin `text` spells: `ruff==0.17.3`, `bevy=0.20.1`, …."""
        m = _PIN.fullmatch(text)
        if m is None:
            msg = f"not a pin: {text!r}"
            raise ValueError(msg)
        if m["implementation"] is not None:
            return cls(m["implementation"], Version.parse(m["requested"]), Op.REQUEST)
        return cls(m["tool"], Version.parse(m["version"]), Op(m["op"]))

    @property
    def exact(self) -> bool:
        """Does this pin name one release, rather than a floor?"""
        return self.op is not Op.FLOOR

    @override
    def __str__(self) -> str:
        """`ruff==0.17.3`, `ty>=0.0.60`, `bevy=0.20.1`, `pypy-3.11`."""
        return f"{self.tool}{self.op.value}{self.version}"


@dataclass(frozen=True, slots=True)
class Answered[T]:
    """What a tool, a query or a request answered."""

    value: T

    @override
    def __str__(self) -> str:
        """The answer, printed as its own type prints it."""
        return str(self.value)


#: How a printed `NoAnswer` begins.
_NO_ANSWER = "no answer: "


@dataclass(frozen=True, slots=True)
class NoAnswer:
    """The question went unanswered, and why.

    Distinct from every answer, so no comparison can read it as a
    version, a success or an empty result.
    """

    reason: str

    @override
    def __str__(self) -> str:
        """`no answer: ` and the reason."""
        return f"{_NO_ANSWER}{self.reason}"


type Answer[T] = Answered[T] | NoAnswer


def parse_answer[T](text: str, parse: Callable[[str], T]) -> Answer[T]:
    """The answer `text` spells, its value read with `parse`.

    A sum over another type, so its parser takes that type's.
    """
    if text.startswith(_NO_ANSWER):
        return NoAnswer(text.removeprefix(_NO_ANSWER))
    return Answered(parse(text))


#: A check's name, as the command line spells it: `shared-text`.
_CHECK = re.compile(r"[a-z][a-z0-9-]*")

#: A branch's name within its check, as Python spells a name:
#: `disabled_code`.
_NAME = re.compile(r"[a-z][a-z0-9_]*")


@dataclass(frozen=True, slots=True)
class Branch:
    """The place in a check a finding came from: `layout.canonical`.

    A negative control is named for the branch it exists to make fire,
    so a finding has to say which branch produced it.
    """

    check: str
    name: str

    def __post_init__(self) -> None:
        """Refuse a name its own printer could not spell."""
        if not (_CHECK.fullmatch(self.check) and _NAME.fullmatch(self.name)):
            msg = f"not a branch: {self!r}"
            raise ValueError(msg)

    @classmethod
    def parse(cls, text: str) -> Self:
        """The branch `text` spells, `check.name`."""
        check, dot, name = text.partition(".")
        if not dot:
            msg = f"not a branch: {text!r}"
            raise ValueError(msg)
        return cls(check, name)

    @override
    def __str__(self) -> str:
        """`check.name`."""
        return f"{self.check}.{self.name}"
