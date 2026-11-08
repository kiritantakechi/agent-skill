## Why

`openspec validate <capability> --type spec --strict` warns on 15 requirements in the main specs:
their requirement text, the paragraphs between the heading and the first scenario, is longer than
500 characters. OpenSpec's guidance is to move examples and edge cases into scenarios, or to split a
requirement into separate requirements that each state one behaviour.

The archived change `one-abstract-standard` recorded the decision in its task 1.1: the 15 stay whole,
because OpenSpec splits an existing requirement only when its owner asks. The owner has now asked.
After this change is archived, every main spec passes `--strict` with no warning.

## What Changes

Each of the 15 is split along the seams between the behaviours it states. No obligation changes. Every
`SHALL` and `SHALL NOT` clause, every condition and every exception survives, in the same words, in
exactly one requirement; every existing scenario survives verbatim, under the requirement whose
behaviour it exercises. Nothing is added, weakened, strengthened or dropped.

- **Removed:** the 15 long requirements, by name. OpenSpec refuses a MODIFIED requirement that omits
  one of the scenarios the main spec holds, so a requirement cannot keep its heading and also hand a
  scenario to the requirement split from it. Each delta therefore removes the old heading and adds
  its parts, and each removal's migration note names them.
- **Added:** 35 requirements: for each of the 15, the part that stays (under a heading that says what
  it now states) and 20 that were split off. OpenSpec appends added requirements at the end of a
  spec, so the parts no longer sit where the original did.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `check-authoring`: 1 requirement split into 2.
- `check-execution`: 4 requirements split into 12.
- `harness-integrity`: 3 requirements split into 7.
- `python-style`: 2 requirements split into 4.
- `python-verification`: 1 requirement split into 2.
- `standard-structure`: 4 requirements split into 8.

## Impact

Spec text only. No code, no check, no standard and no behaviour changes. The 15 requirements are in
`openspec/specs/` and change when this change is archived.
