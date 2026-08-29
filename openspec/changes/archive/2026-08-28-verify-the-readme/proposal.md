## Why

`README.md` is where this repository keeps the answer to *why each check exists*. Its own words:

> Every one was added because a real defect shipped past the checks that existed at the time. The
> note after each is the defect it would have caught.

Nothing verifies it. The table listed 16 rows against 18 registered checks until this was found by
hand; `dialect` and `sensitivity` had shipped with no recorded justification, in the file that
promises one for every check.

The sharper case is the row describing `controls`:

| Check | Catches | Added because |
|---|---|---|
| `controls` | that **every other check** still fails on the defect it owns | *"Every check carries a negative control" was a claim in a file, verified by hand once and never again.* |

`controls` covers 15 of 18. Three checks — `toolchain`, `mutation`, and `controls` itself — have no
control, which `guard-the-guards` made explicit and reasoned. So the row overclaims.

**The "Added because" note on that row is a description of the row.** `controls` exists because a
README made an unverified universal claim about negative controls; the README now makes an unverified
universal claim about `controls`. The fix that worked the first time was turning the claim into a
check, and that fix was never applied to the file the claim lives in.

## What Changes

- **The check table is checked.** A row for every registered check, a check for every row, and the
  run fails on either gap — the same shape as the exemption mapping that `guard-the-guards` gave
  `WITHOUT_A_CONTROL`.
- **The `controls` row stops overclaiming.** It says what `controls` covers and names the exemptions,
  rather than saying "every other check" while three are exempt. What it says is then derived from
  the registry rather than typed.
- **The universal claim earns its "every".** "Every one was added because…" holds only if every row
  carries a non-empty note, which becomes an assertion rather than an intention.
- **Rewriting a claim is not the deliverable.** Each of the three above is a sentence a person could
  simply correct; correcting it produces another sentence nobody verifies. The change is the check.

## Capabilities

### Modified Capabilities

- `harness-integrity`: gains the requirement that a claim the repository makes about its own checks
  in prose is verified against the registry, not maintained beside it. The capability already says a
  list of what must be verified is derived from what is being verified; this extends it to the place
  those claims are written for a reader rather than for a test.

## Impact

| File | What |
|---|---|
| `README.md` | the `controls` row's scope; whatever the new check demands of the table |
| `src/agent_skill/checks/` | a check comparing the documented table against the registry |
| `src/agent_skill/checks/controls.py` | its negative control |
| `tests/` | coverage via the derived set `guard-the-guards` installed |

**Risk** — a check over prose is a check over formatting, and formatting drifts for reasons that are
not defects. Scope it to what is genuinely a claim: which checks are listed, and that each listed
check carries a note. Not wording, not column order, not prose style.

**Non-goal** — verifying that each note is *true*. Whether `dialect` was really added because twenty
patterns carried `\|` through the migration is not decidable by a machine, and pretending otherwise
would put a check where a reviewer belongs.
