## Why

Three of the four standards are a release behind, and the harness already says so: `pins` fails
today on `ruff` 0.16.5 (0.17.1 is out), `ty` 0.0.75 (0.0.89), and the `3.15.0rc1` interpreter
(3.15.0 is final). Two more are behind where `pins` cannot see them, because they are not pinned
anywhere it reads. Bevy 0.20.0 shipped on 2026-10-08 against a standard written for 0.19.1. The Rust
examples compile as `rust-version = "1.98"` on a 1.99 toolchain. Unpinned tools break a requirement
`check-execution` already states: every tool the harness depends on is pinned and checked in both
directions.

The four standards were written at different times. They share a shape only because each copied the
last one, and nothing checks that shape, so they have drifted apart:

- reference files are named in two conventions (`errors.md` beside `errors-and-control-flow.md`);
- the same concept carries a three-letter code in one skill and a four-letter one in the next
  (`RS-TST`, `PS-TEST`);
- there are three severity models: six levels in `rust-style`, eight in `python-style`, and none at
  all in `bevy-style`, which ships no review protocol;
- `bevy-style` has no §7, and its §5 has a different title;
- `rust-style` has no migration chapter;
- the "How to use", tier and marker paragraphs are nearly identical in every `SKILL.md`. They are
  "nearly" identical because nothing keeps them identical.

The standards are also longer than what they teach. Many rules restate a lint the shipped
configuration already turns on, with a Why, a Check and an example for something `clippy` or
`ruff` decides on its own. And the **Why** runs past three lines in 78% of `bevy-style` rules and
65% of `python-style` rules.

Why now: renumbering every rule ID is the expensive part of a symmetry pass. The version bump
already means re-reading every rule against new APIs. Doing both in one pass renumbers once instead
of twice.

## What Changes

- **Versions.**
  - Bevy 0.19.1 → 0.20.0, with a new §2 reality check and new forbidden-API rows.
  - CPython `3.15.0rc1` → `3.15.0`, free-threaded.
  - `ruff` 0.16.5 → 0.17.1 and `ty` 0.0.75 → 0.0.89, in the skill's assets and in this repository.
  - Rust 1.98 → 1.99, in the verified crate and the Bevy toolchain file.
  - `zig-style` is not touched.
- **Every target is a pin, checked both ways.** `pins` covers the Rust toolchain, the Bevy crate and
  the Zig compiler as well as the Python tools. A standard may declare that its pin follows the
  local toolchain rather than upstream. `zig-style` declares this, so a new Zig release does not turn
  the build red until this machine's `zig` moves.
- **One skeleton, enforced.**
  - Every `SKILL.md` has the same H1 form and the same eight H2 sections in the same order.
  - Every reference file is named by one word from a shared vocabulary, and every rule family code
    comes from one shared table. When two standards cover the same concept, they use the same file
    name and the same code.
  - Every standard ships `review-checklist.md` under one shared severity model, and every standard
    ships `migration.md`.
  - A new `skeleton` check fails on any deviation.
- **Shared text, single-sourced.** The paragraphs common to every standard live once, as a template
  in the package. Each `SKILL.md` keeps a verbatim, self-contained copy, so every skill still
  installs and loads on its own. A new `shared-text` check fails when a copy drifts, and
  `agent-skill fmt` rewrites the copies from the template.
- **Rules a tool decides become lint-table rows.** If a rule's whole content is one lint the shipped
  configuration enables, it becomes a row in its chapter's `## Decided by tools` table. The row
  holds the lint, its level, and one line on what it forbids. The rows are tied to the shipped
  configuration in both directions, by the same mechanism `lints` and `citations` already use. Rules
  that say more than their lint stay rules, and cite the lint in their **Check**.
- **A Why is three lines at most**, and `anatomy` enforces it.
- **One marker vocabulary.** It is `verified` / `fragment` / `rejected — <tool>`, and the qualifier
  names the tool that rejects the block. `does-not-compile` remains only in `zig-style`, as a
  recorded exemption.
- **BREAKING — every `RS-`, `PS-` and `BV-` rule ID changes.**
  - Each chapter is renumbered densely from 01, under the unified family codes.
  - Each standard's `migration.md` carries the complete old → new table.
  - The rename is applied by one script across the skills, the profiles, the controls and the tests,
    so citations in this repository move with their rules.
- **BREAKING — reference file paths change** for every renamed chapter.
- **`zig-style` is exempt by declaration, not by omission.** Its profile records why it does not yet
  conform. Once it conforms, that exemption is itself reported.

## Capabilities

### New Capabilities

- `standard-structure`: what every standard in `skills/` must look like and what the harness
  enforces about it. This covers the `SKILL.md` skeleton, the shared-text template and its copies,
  reference file names and family codes, the required chapters, the shared severity model, the
  marker vocabulary, lint-table rows, the length of a Why, dense IDs with a rename table, and how a
  standard is exempted while it is being brought over.

### Modified Capabilities

- `python-style`: the rule-anatomy requirement changes. A tool-decided claim is a lint-table row
  rather than a rule. A Why is bounded. An ID is dense within its chapter, and a renumbering ships
  its rename table instead of promising that IDs never change. The scenario "a rule restates a Ruff
  rule" changes to match.
- `check-execution`: the pinned-tool requirement is extended in two ways.
  - It now covers the libraries a standard's examples are verified against, such as the Bevy crate,
    and it says outright that an unpinned language toolchain is an unfindable pin.
  - A standard may declare that its pin follows the local toolchain. Such a pin is compared against
    the running version only, and the running version moving past the pin is its signal that the
    pin is superseded.

## Impact

- **Skills:** `skills/{rust,python,bevy}-style/` are rewritten end to end. That means the
  `SKILL.md`, every chapter (renamed, renumbered and trimmed), and the assets
  (`Cargo.toml`, `ci.yml`, `rust-toolchain.toml`, `ruff.toml`, `ty.toml`, `pyproject.toml`). There
  is a new `rust-style/references/migration.md` and a new `bevy-style/references/review-checklist.md`.
  `skills/zig-style/` is unchanged.
- **Harness:**
  - New: `checks/skeleton.py`, `checks/shared.py`, and a template module under
    `src/agent_skill/`.
  - Modified: `model.py` (lint-table rows, the default marker vocabulary), `checks/anatomy.py`
    (Why length, dense numbering), `checks/pins.py` (Rust, Bevy and Zig targets, local-tracking
    pins), `checks/citations.py` and `checks/lints.py` (lint-table rows), `fmt.py` (shared-text
    rewrite), `lang/rust.py` and `lang/python.py` (pins), every `profiles/*.py` (rule IDs, the zig
    exemption), `checks/controls.py` and `checks/mirror.py` (rule IDs, file paths), and
    `README.md`.
  - A new control for each new check and branch.
- **Repository pins:** `pyproject.toml` dev group (`ruff`, `ty`).
- **Readers:** anyone who cited an old ID or a reference path outside this repository has to look
  it up in the rename table. The installed skills are symlinks, so they update in place.
- **Risks:**
  - The rename touches every citation at once. A missed one is caught by `anatomy`'s dangling-reference
    branch, and the rename script is checked against the before and after ID sets.
  - Bevy 0.20 may not yet have a `bevy_lint` release. If so, CI states that rather than pinning a
    linter that does not support the engine.
  - The full suite runs about 70 minutes and must run alone, so the plan runs it once per converted
    skill, not concurrently.
