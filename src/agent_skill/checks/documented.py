"""The README's claims about the checks, compared against the checks.

`README.md` is where this repository keeps the answer to why each check exists,
and it says so: *"Every one was added because a real defect shipped past the
checks that existed at the time."* Nothing verified it. The table listed sixteen
rows against eighteen registered checks, so `dialect` and `sensitivity` shipped
with no recorded reason in the file that promises one for every check.

The row describing `controls` is the sharper case. It claimed `controls` proves
"every other check still fails on the defect it owns" while three checks are
exempt — and the note beside it records that `controls` exists *because* a README
carried an unverified universal claim about negative controls. The same file then
made an unverified universal claim about `controls`.

Scope is deliberately narrow. This reads the table's first column (which checks
are named) and whether the third column is non-empty (whether each carries a
reason). Wording, column order and prose style are outside it: a check that fires
on rewording is a check people learn to ignore.

What it cannot decide is whether a reason is *true*. That is a reviewer's
judgement, and a check pretending to make it would be a check that cannot.
"""

import re
from pathlib import Path

from agent_skill.checks import check
from agent_skill.checks.controls import WITHOUT_A_CONTROL
from agent_skill.report import fail
lazy from agent_skill.checks import all_checks

#: `| `name` | catches | added because |` — a table row naming a check.
ROW = re.compile(r"^\|\s*`([a-z-]+)`\s*\|(.*)\|\s*$", re.MULTILINE)

#: A `|` that separates cells, rather than one written into a cell.
#:
#: A GFM table needs `\|` for a literal pipe, code span or not. Scanning a cell
#: as `[^|]*` stops at the escape and reads the remainder as the next column:
#: measured, the `dialect` row's reason — which opens with `` `\|` is alternation
#: to `grep` `` — came back as the two characters `` ` \ `` and satisfied "every
#: row carries a reason" on them. The question this check asks is whether a
#: reason is there, so it has to be asked of the whole reason.
CELL = re.compile(r"(?<!\\)\|")

#: How the `controls` row must describe what it covers. Stating the rule rather
#: than a count is what keeps it true when a check is added: "every other check"
#: was false the moment one was exempted, and "15 of 18" would be false the next
#: time one is registered.
CONTROLS_SCOPE = "every check except those exempted"


def readme(skills) -> Path:
    """Beside the tree being checked, not beside this file.

    `controls` copies the tree, injects a defect and re-runs the check over the
    copy. A check that reads a path fixed at import time reads the original
    every time, so no control could ever reach it — which is how a check ends up
    exempt from the guarantee that it can fail.
    """
    if skills:
        return skills[0].root.parent.parent / "README.md"
    return Path(__file__).resolve().parents[3] / "README.md"


def documented_rows(text: str) -> dict[str, tuple[str, str]]:
    """Each documented check: what the table says it catches, and why it was added.

    A row with fewer than two cells after the name is not a row this can read, and is left out —
    which surfaces as the check it names being undocumented, rather than as silence.
    """
    found: dict[str, tuple[str, str]] = {}
    for name, rest in ROW.findall(text):
        cells = [c.strip() for c in CELL.split(rest)]
        if len(cells) >= 2:
            found[name] = (cells[0], cells[-1])
    return found


@check(
    "documented",
    "the README's claims about the checks, against the checks",
    scope="all",
)
def documented(skills):
    source = readme(skills)
    if not source.is_file():
        yield fail(f"no README at {source}", "documented")
        return

    rows = documented_rows(source.read_text())
    registered = {c.name for c in all_checks()}

    for name in sorted(registered - set(rows)):
        yield fail(
            f"`{name}` is registered and the README documents no row for it — the file that "
            f"promises a reason for every check is missing one",
            "documented",
        )
    for name in sorted(set(rows) - registered):
        yield fail(
            f"the README documents `{name}`, which is not a registered check — "
            f"documentation outliving its subject is documentation nobody re-read",
            "documented",
        )

    for name in sorted(set(rows) & registered):
        if not rows[name][1].strip():
            yield fail(
                f"`{name}` is documented with no reason it was added — the table's claim is that "
                f"every check has one. Whether the reason is true is a reviewer's call; whether "
                f"there is one is this check's",
                "documented",
            )

    # The one row that describes another check's coverage, and so can go stale
    # when an exemption is added rather than when the README is edited.
    if "controls" in rows and CONTROLS_SCOPE not in rows["controls"][0]:
        yield fail(
            f"the `controls` row describes its scope as {rows['controls'][0].strip()!r}, which "
            f"does not say {CONTROLS_SCOPE!r} — it covers every check except the "
            f"{len(WITHOUT_A_CONTROL)} in `WITHOUT_A_CONTROL`, and a row stating a count or an "
            f"'every' goes stale the next time that mapping changes",
            "documented",
        )
