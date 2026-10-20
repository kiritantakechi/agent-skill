r"""A pattern carrying syntax from a grammar it will not be read in.

`\\|` is alternation in a basic regular expression and a literal pipe to
every modern engine. A Check that moved from `grep` to `rg` without that
translation is still a valid pattern: it compiles, it runs, it exits 1,
and it matches nothing. In a report that is indistinguishable from a
check that ran and found the code clean.

This is decided from the pattern's text — no corpus, no execution. It
has to be, because the patterns most at risk are the decisive ones, and
a decisive pattern is *required* to match nothing in this repository's
own compliant examples. An equivalence argument over hit sets is blind
to exactly them: measured, 97 of 137 command patterns have an empty hit
set, so empty-before and empty-after proves nothing about the 70% that
most needed proving.

Only `\\|` is forbidden. `\\(` and `\\{` are legitimate ERE escapes for
a literal parenthesis or brace and are used that way here nineteen
times; forbidding them would report nineteen correct patterns. A genuine
literal pipe is written `[|]`.

A raw newline is the same defect from the other direction. The harness
runs every pattern with `--multiline`, and the printed command does not,
so a command wrapped across a line of the markdown compiles here and is
*rejected* — `rg: the literal "\\n" is not allowed in a regex`, exit 2 —
for the reader. Measured: two Checks shipped that way, and in one of
them the alternative after the newline could never have matched anything
even here. That is a pattern carrying syntax from a grammar it will not
be read in, which is this check's subject; the grammar it will not be
read in is the reader's.
"""

import re

from agent_skill.checks import check
from agent_skill.checks.patterns import QUOTED
from agent_skill.report import fail

#: The command forms a Check ships. Only `rg` is inspected: a `grep`
#: command is pre-migration and its `\|` is correct for the grammar it
#: names.
RG_COMMAND = re.compile(r"`(rg\s[^`]*)`")


def outside_brackets(pattern: str, needle: str) -> bool:
    """Does `needle` occur where it would be an operator rather than a literal?

    Inside a bracket expression every character stands for itself, and
    `[[:space:]]` closes on its *outer* `]` — a scan that stops at the
    first one reads the rest of the class as pattern text and accuses
    it.
    """
    i, n = 0, len(pattern)
    while i < n:
        if pattern.startswith(needle, i):
            return True
        if pattern[i] == "[":
            j = i + 1
            if j < n and pattern[j] == "^":
                j += 1
            if j < n and pattern[j] == "]":
                j += 1
            while j < n and pattern[j] != "]":
                if pattern[j] == "[" and j + 1 < n and pattern[j + 1] in ":.=":
                    kind = pattern[j + 1]
                    end = pattern.find(kind + "]", j + 2)
                    j = n if end == -1 else end + 2
                    continue
                j += 1
            i = j + 1
            continue
        i += 1 + (pattern[i] == "\\" and i + 1 < n)
    return False


@check("dialect", "a pattern carries no syntax from a grammar it will not be read in")
def dialect(skill):
    for rule in skill.rules:
        if not rule.check:
            continue
        for command in RG_COMMAND.findall(rule.check):
            for quoted in QUOTED.findall(command):
                pattern = quoted[0] or quoted[1]
                if "\n" in pattern:
                    yield fail(
                        f"{rule.id}: `rg` pattern {pattern!r} carries a raw newline — the command "
                        f"is wrapped across a line of the source. `rg` rejects that without "
                        f"`--multiline`, so the printed command exits 2 for the reader while the "
                        f"harness, which passes `--multiline`, runs it. Put the command on one "
                        f"line, or split it into several",
                        skill.name,
                    )
                    continue
                if pattern and outside_brackets(pattern, "\\|"):
                    yield fail(
                        f"{rule.id}: `rg` pattern /{pattern}/ keeps BRE's `\\|`, which is a "
                        f"literal pipe here — it matches nothing and reports clean. Write `|` "
                        f"for alternation, or `[|]` for a literal pipe",
                        skill.name,
                    )
