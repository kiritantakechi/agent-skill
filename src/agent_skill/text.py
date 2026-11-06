"""Reading source text as a compiler would, not as a regex would.

Comments and strings are told apart from code, and a regex match is
narrowed to the text it found.
"""

lazy import re


def group(m: re.Match[str] | None, key: int | str = 1) -> str:
    """What group `key` of `m` matched, or "" when it matched nothing.

    "" both without a match and for a group that took no part in it.
    The stubs type every group as possibly absent, even one the pattern
    cannot leave out; narrowing here says what each caller meant.
    """
    found = m.group(key) if m is not None else None
    return found if isinstance(found, str) else ""


def strip_comment(line: str, comment: str, quotes: str) -> str:
    """Everything before the first `comment` token outside a string.

    `const url = "https://example.com";` keeps its value. Splitting on
    the token does not, and a Check searching for a path would miss it.

    The token and the quotes are parameters, with no default, because
    they are not a property of source text in general: a language
    declares them (`lang.Language`). `q = total // count` loses its
    divisor under Rust's and keeps it under Python's.
    """
    i, opener = 0, ""
    width = len(comment)
    while i < len(line):
        c = line[i]
        if opener:
            if c == "\\":
                i += 2
                continue
            if c == opener:
                opener = ""
        elif c in quotes:
            opener = c
        elif line[i : i + width] == comment:
            break
        i += 1
    return line[:i]


def code_only(body: str, comment: str, quotes: str) -> str:
    """`body` with every comment removed and the line count kept."""
    return "\n".join(strip_comment(line, comment, quotes) for line in body.split("\n"))
