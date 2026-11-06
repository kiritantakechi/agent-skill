"""A Check's text, turned into the patterns it names.

Split out of `selfapply` because three checks want it and only one of
them is about self-application: `crossref` runs one standard's patterns
over another's examples, and `dialect` inspects pattern syntax without
running anything.
"""

import re
from dataclasses import dataclass

lazy from agent_skill.lang import language

#: A backticked span is worth running only if it looks like code, not
#: prose.
CODEISH = re.compile(r"[\[\](){}<>:\\|*+?^$]|_")
#: Patterns this broad match everything and teach nothing.
TOO_BROAD = {"pub ", "fn ", r"\.clone\(\)", "unsafe", "mut ", "&mut ", "impl "}
#: The quoted token in `rg -n 'pat' -g '*.zig'` that is the file, not
#: the pattern.
#:
#: A miss here is not a false negative, it is a build break: an
#: unrecognised file argument becomes a `kind="command"` pattern, and a
#: command-kind hit is tier 1 — so every example mentioning the filename
#: would fail the standard. Python configuration lives in bare top-level
#: files rather than behind a glob, so the names have to be listed the
#: way `build.zig` already is.
FILE_ARG = re.compile(
    r"\*\.(zig|rs|py|md|toml|zon|c|h)$"
    r"|^src/|^references/"
    r"|^(build\.zig|pyproject\.toml|pytest\.toml|ruff\.toml|ty\.toml)$"
)

COMMAND = re.compile(r"`(rg\s[^`]*)`")
#: `| rg -v '…'` to the end of its command: a second search that drops
#: lines from the first one's output.
NEGATED = re.compile(r"\|\s*(rg\s+-v\b[^`]*)")
QUOTED = re.compile(r"'([^']*)'|\"([^\"]*)\"")
#: A prose span shorter than this is not run as a pattern.
SHORTEST = 4


@dataclass(frozen=True, slots=True)
class Pattern:
    """One runnable pattern a Check names, and how to run it."""

    text: str
    mode: str  #: `-F` literal text, `-E` regex — there is no third
    kind: str  #: "command" — the Check ships it; "prose" — a span it names

    def over_comments(self, lang: str) -> bool:
        """Does this Check mean the comment, rather than the code?

        A fact about the pattern in `lang`, so it is asked here once.
        `hits` and `lines_for` each spelled it, ten lines apart, and
        they have to agree: the exemption hook reads line `n` of
        whichever list `lines_for` returns, numbered by whichever file
        `hits` searched.

        The language's own comment token. This asked for `//` whatever
        the language, so a Python pattern over a comment — `# noqa` —
        was run over the code with every comment stripped, and could
        never fire.
        """
        return language(lang).comment in self.text


def dialect_of(command: str) -> str:
    """Regex, or literal text — the only distinction left.

    Two values, not three. The library used to hold basic and extended
    expressions at once, selected by whether a command happened to carry
    `-E`, and a pattern read in the wrong one matches nothing while
    reporting clean.

    Both spellings of the fixed-string flag count. Reading only the
    short one made `rg --fixed-strings 'a|b'` a regex, which turns a
    literal pipe the author asked for into an alternation.
    """
    flags = "".join(re.findall(r"(?<!\S)-([a-zA-Z]+)(?!\S)", command))
    if "F" in flags or "--fixed-strings" in command:
        return "-F"
    return "-E"


def patterns_of(check_text: str) -> list[Pattern]:
    """Every runnable pattern a Check names.

    A pattern quoted inside an `rg` command is what the Check tells the
    reader to run, in the dialect that command selects. A backticked
    span in prose is literal text the reader is told to look for, so it
    is a fixed string — compiling it as a regex turned `|x| f(x)` into
    an alternation that matched every line, which is how the first
    version produced five thousand hits.
    """
    out: list[Pattern] = []
    for command in COMMAND.findall(check_text):
        mode = dialect_of(command)
        for quoted in QUOTED.findall(command):
            text = quoted[0] or quoted[1]
            if not text or text.startswith("-") or FILE_ARG.search(text):
                continue
            out.append(Pattern(text, mode, "command"))
    if not out and re.search(
        # `grep` stays. Most Checks that name a search phrase it rather
        # than shipping a command, and the word they reach for is still
        # `grep` — a word in prose is not a tool invocation, so the
        # migration to `rg` left them alone. No count here: it moves
        # every time a Check is promoted, and a number in a comment is a
        # claim nothing checks. What this branch rests on is that the
        # population is not empty, which is asserted in
        # `test_patterns.py` rather than asserted here and believed.
        r"\bgrep\b|\brg\b|\bscan\b|\bsearch for\b|\blook for\b",
        check_text,
        re.IGNORECASE,
    ):
        for span in re.findall(r"`([^`\n]+)`", check_text):
            if len(span) < SHORTEST or not CODEISH.search(span):
                continue
            if not re.match(r"^(references/|[A-Z]{2}-)", span):
                out.append(Pattern(span, "-F", "prose"))
    return [p for p in out if p.text not in TOO_BROAD]


def filtered_of(check_text: str) -> tuple[list[Pattern], list[Pattern]]:
    """The patterns a Check searches for, and those it filters out.

    `rg -n 'pub use' src/ | rg -v '^src/lib.rs'` searches for the
    first and drops what the second matches — here by which file a hit
    is in. Read whole, the second reads as one more pattern to find.
    """
    filters = [
        p
        for command in NEGATED.findall(check_text)
        for p in patterns_of(f"`{command}`")
    ]
    return patterns_of(NEGATED.sub("", check_text)), filters
