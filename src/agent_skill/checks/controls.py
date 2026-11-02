"""Negative controls, run.

"Every check carries a negative control" was a claim in a README,
verified by hand when each check was written and never again — which is
the same shape as the defects the checks exist to catch. A check that
cannot fail looks exactly like a check that passes.

A control is named for one branch of one check: it copies the skills
tree, injects one defect, and asserts that this branch reports a
failure. Another branch of the same check reporting it does not count,
since the branch the control exists for could then be deleted with the
control still passing. A control that stops firing is itself a failure,
and so is a fixture whose anchor text has drifted out of the skill.
"""

import shutil
import tempfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from functools import partial
from pathlib import Path
lazy from collections.abc import Callable, Iterator, Mapping, Sequence

from agent_skill import shared
from agent_skill.checks import (
    anatomy,
    assets,
    check,
    citations,
    crossref,
    dialect,
    documented,
    frontmatter,
    layout,
    lints,
    markers,
    mirror,
    pins,
    plugin,
    prose,
    selfapply,
    sensitivity,
    skeleton,
)
from agent_skill.ids import Location
from agent_skill.layout import PLUGIN, SKILLS, root_of
from agent_skill.profiles import bevy_style, python_style, rust_style, zig_style
from agent_skill.report import Level, declare, fail, unrun
lazy from agent_skill.checks import Check, by_name
lazy from agent_skill.ids import Branch
lazy from agent_skill.lang import toolchain_for
lazy from agent_skill.lang.python import INTERPRETER
lazy from agent_skill.model import Skill, Tree, discover
lazy from agent_skill.proc import pinned_version
lazy from agent_skill.profiles import registered
lazy from agent_skill.report import Finding, Result


class FixtureGoneError(LookupError):
    """The text a control edits is no longer in the skill."""


# The branches a finding of this check comes from. A finding of it is
# about the controls in the harness, so it lies in no skill.
GONE = declare("controls", "gone", Level.FAIL)
UNEXERCISED = declare("controls", "unexercised", Level.UNRUN)
SILENT = declare("controls", "silent", Level.FAIL)
BESIDE = declare("controls", "beside", Level.FAIL)
ELSEWHERE = declare("controls", "elsewhere", Level.FAIL)
EMPTY_CORPUS = declare("controls", "empty_corpus", Level.FAIL)

#: What an injection returns: the paths it edited, each relative to the
#: directory it edited under — the skills tree, or the copy's root for a
#: file beside it. A path's first part names the skill it lies in.
type Edited = tuple[str, ...]


def edit(tree: Path, rel: str, old: str, new: str, count: int = 1) -> Edited:
    """Replace the first `count` copies of `old` in one file of `tree`.

    Raises `FixtureGoneError` when the file holds fewer copies than
    that.
    """
    path = tree / rel
    text = path.read_text()
    if text.count(old) < count:
        msg = f"{rel}: {old[:60]!r}"
        raise FixtureGoneError(msg)
    path.write_text(text.replace(old, new, count))
    return (rel,)


def append(tree: Path, rel: str, text: str) -> Edited:
    """Add `text` to the end of one file of `tree`."""
    path = tree / rel
    path.write_text(path.read_text() + text)
    return (rel,)


def write(tree: Path, rel: str, text: str) -> Edited:
    """Write `text` as one file of `tree`, new or replacing one."""
    (tree / rel).write_text(text)
    return (rel,)


def remove(tree: Path, rel: str) -> Edited:
    """Delete one file or directory of `tree`."""
    path = tree / rel
    if path.is_dir():
        shutil.rmtree(path)
    elif path.exists():
        path.unlink()
    else:
        raise FixtureGoneError(rel)
    return (rel,)


def move(tree: Path, rel: str, name: str) -> Edited:
    """Rename a file in the throwaway tree.

    For a defect that is a file's name.
    """
    path = tree / rel
    if not path.exists():
        raise FixtureGoneError(rel)
    path.rename(path.with_name(name))
    return (rel,)


def drop_line(tree: Path, rel: str, start: str) -> Edited:
    """Delete the first line of `rel` that opens with `start`."""
    lines = (tree / rel).read_text().splitlines(keepends=True)
    line = next((ln for ln in lines if ln.startswith(start)), None)
    if line is None:
        msg = f"{rel}: {start[:60]!r}"
        raise FixtureGoneError(msg)
    return edit(tree, rel, line, "")


def throwaway_tree(source: Path, into: Path) -> Path:
    """A copy of the skills tree, plus what a check reads beside it.

    One definition, because there were two: this loop and the `scratch`
    fixture in the tests, each deciding what a throwaway tree contains.
    They agreed until `documented` started reading the README, at which
    point the same control fired here and not there — and a control that
    fires in one runner and not the other is a control nobody can trust
    in either.
    """
    tree = into / SKILLS
    shutil.copytree(source, tree, symlinks=True)
    root = root_of(source)
    for beside in ("README.md", "LICENSE"):
        if (root / beside).is_file():
            shutil.copy2(root / beside, into / beside)
    for manifests in (Path(".claude-plugin"), PLUGIN / ".claude-plugin"):
        if (root / manifests).is_dir():
            shutil.copytree(root / manifests, into / manifests)
    return tree


#: Why a check has no control, for the checks that have none.
WITHOUT_A_CONTROL = {
    "controls": (
        "it is the mechanism the controls run through; a control on it would "
        "assert that the asserting works by asserting"
    ),
    "toolchain": (
        "not knowable from the code. It compiles and runs every example, so a "
        "control would cost a full toolchain run — but nothing records whether "
        "that is the reason or whether nobody got to it"
    ),
    "mutation": (
        "not knowable from the code. Same shape as `toolchain`, and the same gap"
    ),
}


@dataclass(frozen=True, slots=True)
class Control:
    """A defect to inject, and the branch that must report it.

    `inject` edits a throwaway copy of the skills tree and returns the
    paths it edited; a per-skill check then reads only the skills they
    lie in. `also` names each other branch of the check the defect
    cannot help reaching, with why — any other branch reporting it
    fails the control.
    """

    branch: Branch
    inject: Callable[[Path], Sequence[str]]
    also: Mapping[Branch, str] = field(default_factory=dict)


def exercise(control: Control, source: Path) -> list[Finding]:
    """What `controls` says of one control: nothing, when it fires.

    The one runner, which the `controls` check and the test suite both
    call. `source` is the skills tree to copy.
    """
    target = _target(control)
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        copy = throwaway_tree(source, Path(tmp))
        try:
            edited = control.inject(copy)
        except FixtureGoneError as e:
            return [
                fail(
                    f"{control.branch}: cannot be injected any more — {e}",
                    Location(),
                    GONE,
                )
            ]
        # A per-skill check reads only the skills the injection landed
        # in: what it finds in the others it found before the injection
        # too. `run` decides which checks those are, from how the check
        # was written. An edit beside the skills names none, and the
        # check reads every skill.
        tree = Tree.of(discover(copy))
        about = {Path(rel).parts[0] for rel in edited}
        result = target.run(tree, about=about)
        read = {s.name for s in tree} & about or {s.name for s in tree}
    return list(_verdict(control, target, result, read))


def _verdict(
    control: Control, target: Check, result: Result, read: set[str]
) -> Iterator[Finding]:
    """What is wrong with how `target` answered `control`'s defect."""
    nowhere = Location()
    fired = {f.branch for f in result.fails}
    if control.branch not in fired:
        if result.unrun:
            # The check could not look — a toolchain is absent — so
            # whether the control fires is unknown rather than false.
            # `UNRUN` withholds the pass exactly as `FAIL` does.
            yield unrun(
                f"{control.branch}: `{target.name}` could not run here, "
                "so the control was not exercised",
                nowhere,
                UNEXERCISED,
            )
        else:
            instead = ", ".join(sorted(str(b) for b in fired)) or "nothing"
            yield fail(
                f"{control.branch}: the control no longer fires — "
                f"`{target.name}` reports {instead}",
                nowhere,
                SILENT,
            )
        return
    if beside := sorted(str(b) for b in fired - {control.branch, *control.also}):
        yield fail(
            f"{control.branch}: also fires {', '.join(beside)}, and the control "
            "does not say why the defect reaches it",
            nowhere,
            BESIDE,
        )
    if target.reads_one_skill:
        # A per-skill check reads fewer skills under `--skill` and here,
        # which drops only findings no one asked for if each finding it
        # makes lies in a skill it was reading.
        for f in result.findings:
            if f.where.skill not in read:
                yield fail(
                    f"{control.branch}: `{target.name}` read {sorted(read)} "
                    f"and found `{f}`",
                    nowhere,
                    ELSEWHERE,
                )


def _target(control: Control) -> Check:
    """The check `control`'s branch belongs to.

    Always registered: the bijection test holds every control's branch
    to a declared branch of a registered check.
    """
    target = by_name(control.branch.check)
    if target is None:
        msg = f"{control.branch} names no registered check"
        raise LookupError(msg)
    return target


HEADER = "const _: () = assert!(align_of::<Header>() == 4);\n"
PUB_FIELD = HEADER + (
    "\n/// Not layout-sensitive; this field must not be public.\n"
    "#[derive(Debug)]\npub struct Cursor {\n    pub offset: usize,\n}\n"
)

#: The opening of PS-CONC-01's example, which several controls edit.
_BUILD_CONSTANT = "import sys\nfrom typing import Final\n\nFREE_THREADED_BUILD"

#: The one line of a `bevy-style` example this control appends to.
_TEST_BODY = "        let mut app = App::new();\n        app.add_plugins(HealthPlugin);"

#: PS-OUT-07's command as the standard now prints it, and as it used to
#: be written — wrapped at the column limit, which put a literal newline
#: into the pattern. Derived from the first rather than spelled twice:
#: the two differ by exactly the defect, and nothing else.
SQL_COMMAND = r"""`rg -n 'f"[^"\n]*(SELECT|INSERT|UPDATE|DELETE) ' src/`"""
SQL_WRAPPED = SQL_COMMAND.replace("UPDATE|DELETE", "UPDATE|\nDELETE")


def _unaccounted_anchor_rule(tree: Path) -> Edited:
    """An anchor's defect in the delta's examples, unmentioned by it.

    `crossref` reaches its verdict by four branches over the same input,
    and this control used to edit `SKILL.md` — which trips the citation
    branch too. It reported two failures and passed on the citation one
    alone for as long as the anchor sweep was unreachable, which is how
    the sweep stayed dead.

    The rule is chosen for a property that could stop holding, so the
    property is asserted rather than assumed. `RS-OWN-36` works because
    `bevy-style` never names it; the day it does, the injection would be
    accounted for and this control would pass while proving nothing.
    """
    if "RS-OWN-36" in (tree / "bevy-style/SKILL.md").read_text():
        msg = (
            "bevy-style/SKILL.md now names RS-OWN-36, so its defect is accounted "
            "for and no longer reaches the anchor sweep"
        )
        raise FixtureGoneError(msg)
    return edit(
        tree,
        "bevy-style/references/testing.md",
        _TEST_BODY,
        f"{_TEST_BODY}\n"
        "        let _ = app.world().resource::<AppTypeRegistry>().read();",
    )


#: The head of `bevy-style`'s override table, which `_no_override_table`
#: turns into prose along with every row under it.
_OVERRIDES = "| `rust-style` rule | What applies instead | Why Bevy forces it |\n"


def _no_override_table(tree: Path) -> Edited:
    """The delta's override table, its rows kept as a paragraph.

    The anchor used to be read off the table's rows, so deleting the
    table took the anchor with it: the sweep of the anchor's patterns
    had nothing to run, and what was left was a note. The rows stay as
    prose so the rules they name stay named: deleted outright, the
    anchor's patterns for those rules run and hit as well.
    """
    rel = "bevy-style/SKILL.md"
    text = (tree / rel).read_text()
    if _OVERRIDES not in text:
        msg = f"{rel}: {_OVERRIDES[:60]!r}"
        raise FixtureGoneError(msg)
    lines = text.partition(_OVERRIDES)[2].split("\n")
    end = next(i for i, line in enumerate(lines) if not line.startswith("|"))
    said = " ".join(c.strip() for row in lines[1:end] for c in row.split("|"))
    return edit(tree, rel, _OVERRIDES + "\n".join(lines[:end]) + "\n", said + "\n")


def _no_uv_interpreter(tree: Path) -> Edited:
    """Every `uv python install` in the workflow, gone.

    The interpreter half compared only the lines that were there, so a
    workflow with none — running whatever the runner had — passed.
    """
    rel = "python-style/assets/ci.yml"
    line = f"uv python install {INTERPRETER}"
    count = (tree / rel).read_text().count(line)
    return edit(tree, rel, line, "python --version", max(count, 1))


#: The head of a chapter's `Decided by tools` table. A chapter has one,
#: so a row is injected under it: a second table is not read.
_TABLE = "| Tool | Lint | Level | Forbids |\n|---|---|---|---|\n"


def _row(tree: Path, rel: str, row: str) -> Edited:
    """Add `row` first under the `Decided by tools` table of `rel`."""
    return edit(tree, rel, _TABLE, f"{_TABLE}{row}\n")


#: `python-style` is the standard the structure controls inject into.
PY = "python-style"


def _disabled_c4_citation(tree: Path) -> Edited:
    """A rule citing `C408`, and the asset turning `C408` off.

    The family is the point. A token was classified by stripping its
    digits and looking the letters up in a hand-written list, which
    named the family `C4` — so `C408` became `C`, matched nothing, and
    was dropped as prose. No row names `C408`, so only the cited-code
    branch can report it.
    """
    return (
        *edit(tree, f"{PY}/assets/ruff.toml", '"CPY001",\n', '"CPY001",\n  "C408",\n'),
        *edit(
            tree,
            f"{PY}/references/concurrency.md",
            "**Check:** `rg -n 'f_locals' src/`",
            "**Check:** C408 decides this. `rg -n 'f_locals' src/`",
        ),
    )


#: A rule of the async family, filed in the testing chapter. New, so no
#: rename row names it and only the family branch of `skeleton` can
#: report it.
MISFILED = "\n### PS-ASYNC-99 [M] Misfiled\n\nX.\n\n**Why:** y.\n\n**Check:** z.\n"

CONTROLS: list[Control] = [
    # A section title with a subtitle the other standards do not have.
    Control(
        skeleton.SECTION,
        lambda t: edit(
            t,
            f"{PY}/SKILL.md",
            "## 3. Design principles\n",
            "## 3. Design principles — less\n",
        ),
    ),
    Control(
        skeleton.CHAPTER_NAME,
        lambda t: move(t, f"{PY}/references/async.md", "asyncio.md"),
    ),
    Control(
        skeleton.FAMILY,
        lambda t: append(t, f"{PY}/references/testing.md", MISFILED),
    ),
    Control(
        # A block between the contents and the first section belongs to
        # no section, so the chapter layer refuses the file, and every
        # check reads it as a chapter with no rules. The migration
        # chapter, because refusing one whose rules a rename row names
        # leaves that row pointing at nothing.
        skeleton.UNREAD,
        lambda t: edit(
            t, f"{PY}/references/migration.md", "\n---\n\n## ", "\n---\n\nStray.\n\n## "
        ),
    ),
    Control(
        skeleton.SEVERITY,
        lambda t: edit(
            t, f"{PY}/references/review-checklist.md", "| **Style** |", "| **Nit** |"
        ),
    ),
    # Section 5 drifting from the protocol's review order.
    Control(
        skeleton.REVIEW_ORDER,
        lambda t: edit(
            t, f"{PY}/SKILL.md", "10. **The build.**", "10. **The release.**"
        ),
    ),
    Control(
        skeleton.RENAME_TARGET,
        lambda t: edit(
            t,
            f"{PY}/references/migration.md",
            "| `PS-ERR-09` | lint `ruff:E722` |",
            "| `PS-ERR-09` | `PS-ERR-99` |",
        ),
    ),
    Control(
        skeleton.RENAME_SELF,
        lambda t: edit(
            t,
            f"{PY}/references/migration.md",
            "| `PS-ERR-09` | lint `ruff:E722` |",
            "| `PS-ERR-09` | `PS-ERR-09` |",
        ),
    ),
    # An old ID dropped from the rename table while no rule carries it.
    Control(
        skeleton.UNCHANGED_GONE,
        lambda t: edit(
            t, f"{PY}/references/migration.md", "| `PS-API-22` | `PS-DOC-10` |\n", ""
        ),
    ),
    Control(
        shared.DIFFERS,
        lambda t: edit(
            t, f"{PY}/SKILL.md", "Apply it literally.", "Apply it with judgement."
        ),
    ),
    Control(
        # The chapter's last rule, cited nowhere but its heading and its
        # contents line, so moving its number leaves no dangling
        # citation behind.
        anatomy.NUMBERING,
        lambda t: edit(
            t, f"{PY}/references/migration.md", "PS-MIG-09 [M]", "PS-MIG-17 [M]", 2
        ),
    ),
    Control(
        # Words, not a line break: a Why is measured as filled, so a
        # break inside it adds no line.
        anatomy.WHY_LENGTH,
        lambda t: edit(
            t,
            f"{PY}/references/api.md",
            "**Why:** without it the public surface is",
            "**Why:** one sentence more, long enough that no filling of this "
            "paragraph keeps it to three lines. Without it the public surface is",
        ),
    ),
    Control(
        anatomy.ABBREVIATED,
        lambda t: edit(
            t,
            f"{PY}/references/naming.md",
            "`self` and `cls` always, never renamed.",
            "`self` and `cls` always, never renamed (PS-NAME-02, -03).",
        ),
    ),
    Control(
        anatomy.RELAXED_LABEL,
        lambda t: edit(
            t,
            f"{PY}/references/output.md",
            "*Relaxed form:* application code at a display boundary",
            "**Relaxed form:** application code at a display boundary",
        ),
    ),
    Control(
        anatomy.RELAXED_ORDER,
        lambda t: edit(
            t,
            f"{PY}/references/naming.md",
            "A name that is not a question is the finding.\n",
            "A name that is not a question is the finding.\n\n*Relaxed form:* none.\n",
        ),
    ),
    # A rule with no Why.
    Control(
        anatomy.UNSTATED,
        lambda t: edit(
            t,
            f"{PY}/references/naming.md",
            "**Why:** casing carries information",
            "Casing carries information",
        ),
    ),
    Control(
        anatomy.BELOW_TARGET,
        lambda t: edit(
            t,
            f"{PY}/references/naming.md",
            "`self` and `cls` always, never renamed.",
            "`self` and `cls` always, never renamed (stable since 3.9).",
        ),
    ),
    Control(
        citations.TY_ROW_LEVEL,
        lambda t: edit(
            t,
            f"{PY}/references/async.md",
            "| ty | `deprecated` | warn |",
            "| ty | `deprecated` | error |",
        ),
    ),
    Control(citations.DISABLED_CODE, _disabled_c4_citation),
    Control(
        # The code the standard once cited and ruff never had.
        citations.UNKNOWN_CODE,
        lambda t: edit(
            t,
            f"{PY}/references/concurrency.md",
            "**Check:** `rg -n 'f_locals' src/`",
            "**Check:** ASYNC101 decides this. `rg -n 'f_locals' src/`",
        ),
    ),
    Control(
        # A row removed while the profile keeps its probe. Renaming the
        # row's error instead also leaves a row with no probe, so it
        # fires `zig_no_probe` and never a probe printing another error.
        citations.ZIG_PROBE_NO_ROW,
        lambda t: drop_line(
            t,
            "zig-style/references/errors.md",
            "| zig | `cannot return from defer expression` |",
        ),
    ),
    Control(
        # The asset denies it; a row saying `warn` describes a build
        # that is not shipped.
        citations.RUST_LEVEL,
        lambda t: _row(
            t,
            "rust-style/references/errors.md",
            "| clippy | `unwrap_used` | warn | an unwrap |",
        ),
    ),
    Control(
        citations.RUST_UNKNOWN_LINT,
        lambda t: _row(
            t,
            "rust-style/references/errors.md",
            "| clippy | `unwarp_used` | deny | an unwrap |",
        ),
    ),
    Control(
        citations.TY_UNVERIFIED,
        lambda t: edit(
            t,
            f"{PY}/assets/ty.toml",
            "[analysis]",
            'redundant-cast = "error"\n\n[analysis]',
        ),
    ),
    Control(
        pins.WORKFLOW_OTHER,
        lambda t: edit(
            t,
            f"{PY}/assets/ci.yml",
            "uv python install cpython-3.15.2+freethreaded",
            "uv python install 3.15t",
        ),
    ),
    Control(
        # The reader installs what the asset says; the harness verified
        # against what pyproject says. A silent disagreement hands them
        # a different build.
        pins.PROJECT_PIN,
        lambda t: edit(
            t,
            f"{PY}/assets/pyproject.toml",
            'typecheck = ["ty==0.0.95"]',
            'typecheck = ["ty==0.0.60"]',
        ),
    ),
    Control(
        # Only a requirement already spelled `==` was compared, so a
        # floor handed the reader any build at all and passed.
        pins.PROJECT_INEXACT,
        lambda t: edit(
            t,
            f"{PY}/assets/pyproject.toml",
            f'"ty=={pinned_version("ty")}"',
            '"ty>=0.0.60"',
        ),
    ),
    Control(pins.WORKFLOW_NONE, _no_uv_interpreter),
    Control(
        python_style.FUTURE,
        lambda t: edit(
            t,
            f"{PY}/references/concurrency.md",
            _BUILD_CONSTANT,
            "from __future__ import annotations\n\n" + _BUILD_CONSTANT,
        ),
    ),
    Control(
        python_style.FUTURE_PROSE,
        lambda t: edit(
            t,
            f"{PY}/references/concurrency.md",
            "Unless a block shows its own imports,",
            "Reach for `from __future__ import annotations` here. "
            "Unless a block shows its own imports,",
        ),
    ),
    Control(
        markers.NO_MARKER,
        lambda t: edit(
            t,
            f"{PY}/references/concurrency.md",
            "# verified — GOOD\n" + _BUILD_CONSTANT,
            "# does-not-compile — GOOD\n" + _BUILD_CONSTANT,
        ),
    ),
    Control(
        # `rejected` alone says the block is wrong and not who says so —
        # the word that replaced `does-not-compile` exists to name the
        # tool.
        markers.REJECTED_TOOL,
        lambda t: edit(
            t,
            f"{PY}/references/concurrency.md",
            "# verified — GOOD\n" + _BUILD_CONSTANT,
            "# rejected — the GIL is off\n" + _BUILD_CONSTANT,
        ),
    ),
    Control(
        markers.SECOND_MARKER,
        lambda t: edit(
            t,
            "zig-style/references/naming.md",
            "// fragment — BAD\n",
            "// fragment — BAD\n// GOOD\n",
        ),
    ),
    Control(
        assets.CITES,
        lambda t: edit(t, "bevy-style/assets/ci.yml", "BV-ARCH-01", "BV-ARCH-99"),
    ),
    Control(
        assets.TOML,
        lambda t: append(t, "rust-style/assets/rustfmt.toml", "\nbroken = = 1\n"),
    ),
    Control(
        assets.UNREFERENCED,
        lambda t: write(t, "rust-style/assets/orphan.toml", "x = 1\n"),
    ),
    Control(
        # The defect verbatim: the shipped template named itself
        # `acme-widget` and its package `acmewidget`, so no backend
        # could find the package.
        assets.BUILD,
        lambda t: edit(
            t,
            f"{PY}/assets/pyproject.toml",
            'name = "acmewidget"',
            'name = "acme-widget"',
        ),
    ),
    Control(
        bevy_style.PRIVATE_FIELD,
        lambda t: edit(
            t,
            "bevy-style/references/scheduling.md",
            "struct Velocity(pub Vec3);",
            "struct Velocity(Vec3);",
        ),
    ),
    Control(
        # The derive kept: without it the component also lacks a
        # derive, which is the branch below.
        bevy_style.COMPONENT_REFLECT,
        lambda t: edit(
            t,
            "bevy-style/references/scheduling.md",
            "#[derive(Component, Debug, Reflect)]\n#[reflect(Component)]\n"
            "struct Velocity",
            "#[derive(Component, Debug, Reflect)]\nstruct Velocity",
        ),
    ),
    Control(
        bevy_style.COMPONENT_DERIVE,
        lambda t: edit(
            t,
            "bevy-style/references/ecs.md",
            "#[derive(Component, Debug, Clone, Copy, PartialEq, Reflect)]",
            "#[derive(Component, Clone, Copy, PartialEq, Reflect)]",
        ),
    ),
    Control(
        bevy_style.PLUGIN_DERIVE,
        lambda t: edit(
            t,
            "bevy-style/references/architecture.md",
            "#[derive(Debug, Default)]\npub struct DecayPlugin;",
            "#[derive(Debug)]\npub struct DecayPlugin;",
        ),
    ),
    Control(
        bevy_style.PLUGIN_SUFFIX,
        lambda t: edit(
            t,
            "bevy-style/references/architecture.md",
            "impl Plugin for CombatPlugin {",
            "impl Plugin for Combat {",
        ),
    ),
    Control(crossref.ANCHOR_HIT, _unaccounted_anchor_rule),
    Control(crossref.DELTA_NO_TABLE, _no_override_table),
    Control(
        # Added beside the rules the delta names rather than in place of
        # one. Renaming the override row's `RS-API-15` also stopped the
        # delta naming that rule, so the anchor sweep ran its pattern,
        # hit, and fired with the citation branch gone.
        crossref.FOREIGN_CITATION,
        lambda t: edit(
            t,
            "bevy-style/SKILL.md",
            "`RS-NAME-02` is **not** on this list,",
            "`RS-NAME-02` is **not** on this list, nor `RS-API-99`,",
        ),
    ),
    Control(
        crossref.OVERRIDE_TITLE,
        lambda t: edit(
            t,
            "bevy-style/SKILL.md",
            "`RS-NAME-29` Never suffix a name with the language construct",
            "`RS-NAME-29` Always suffix a name with the language construct",
        ),
    ),
    # Frontmatter with no name. Misspelling the key instead also adds a
    # key the spec does not have.
    Control(
        frontmatter.REQUIRED,
        lambda t: edit(t, "rust-style/SKILL.md", "name: rust-style\n", ""),
    ),
    Control(
        # The second ID of the list. `_paths` reads the first ID after
        # a path, and caught a wrong first one, so the control fired
        # with `_core_citations` gone; a core rule's whole list is read,
        # which is the reason that branch exists.
        anatomy.CORE_WRONG_CHAPTER,
        lambda t: edit(
            t,
            "rust-style/SKILL.md",
            "`references/api.md` RS-API-15, RS-API-16",
            "`references/api.md` RS-API-15, RS-ERR-03",
        ),
    ),
    Control(
        anatomy.SHARED_TITLE,
        lambda t: edit(
            t,
            "zig-style/references/data.md",
            "ZS-DATA-27 [M] Return the lowest-dimensionality type "
            "that can carry the answer",
            "ZS-DATA-27 [M] Reference long-lived elements by handle, not by pointer",
            2,
        ),
    ),
    # Shipped lint weaker than the verified one.
    Control(
        lints.LEVEL,
        lambda t: edit(
            t,
            "rust-style/assets/Cargo.toml",
            'indexing_slicing = "deny"',
            'indexing_slicing = "warn"',
        ),
    ),
    Control(
        plugin.MANIFEST_NAME,
        lambda t: edit(
            root_of(t),
            f"{PLUGIN}/.claude-plugin/plugin.json",
            '"name": "style-standards"',
            '"name": "style-standard"',
        ),
    ),
    Control(
        # Only a missing manifest used to be reported. One that was
        # there and did not parse returned before anything read it, with
        # no finding, and the check passed.
        plugin.UNREAD,
        lambda t: edit(
            root_of(t),
            f"{PLUGIN}/.claude-plugin/plugin.json",
            '"name": "style-standards",',
            '"name": "style-standards",,',
        ),
    ),
    Control(
        layout.TABLE_CELLS,
        lambda t: edit(
            t, f"{PY}/SKILL.md", "`X \\| None`, `A \\| B`", "`X | None`, `A | B`"
        ),
    ),
    Control(
        # A paragraph the printer would fill onto two lines, so the
        # file is not canonical. Joined, not repeated: `"x " * 60` ends
        # in a space, a second way of not being canonical.
        layout.CANONICAL,
        lambda t: append(t, "zig-style/references/data.md", "\n" + "x " * 59 + "x\n"),
    ),
    Control(
        # The printer keeps an example's lines as written, so only the
        # width branch measures them.
        layout.CODE_WIDTH,
        lambda t: append(
            t, "zig-style/references/data.md", "\n```text\n" + "x" * 101 + "\n```\n"
        ),
    ),
    # A pub field on a non-repr(C) type.
    Control(
        rust_style.PUBLIC_FIELD,
        lambda t: edit(t, "rust-style/references/unsafe.md", HEADER, PUB_FIELD),
    ),
    # `.?` in a GOOD example.
    Control(
        zig_style.UNWRAP,
        lambda t: edit(
            t,
            "zig-style/references/data.md",
            '// verified — GOOD\nconst std = @import("std");',
            '// verified — GOOD\nconst std = @import("std");\n'
            "const injected: u8 = (@as(?u8, 3)).?;",
        ),
    ),
    # `builtin` imported below `std`.
    Control(
        zig_style.IMPORT_ORDER,
        lambda t: edit(
            t,
            "zig-style/references/interop.md",
            'const builtin = @import("builtin");\nconst std = @import("std");\n'
            "const assert = std.debug.assert;",
            'const std = @import("std");\nconst builtin = @import("builtin");\n'
            "const assert = std.debug.assert;",
        ),
    ),
    # Build provenance in prose.
    Control(
        prose.PROVENANCE_LINE,
        lambda t: append(
            t,
            "zig-style/references/data.md",
            "\nMeasured on this machine: the layout is stable.\n",
        ),
    ),
    # Prose recommending a forbidden spelling.
    Control(
        zig_style.UNWRAP_PROSE,
        lambda t: edit(
            t,
            "zig-style/references/data.md",
            "**Why:**",
            "Reach for `slot.?` when the optional is provably present.\n\n**Why:**",
        ),
    ),
    Control(
        # The defect this check exists for: a check ships, and the
        # README's promise of a reason for every one quietly stops being
        # true. Renaming the row instead also leaves a row for a check
        # that does not exist.
        documented.UNDOCUMENTED,
        lambda t: drop_line(root_of(t), "README.md", "| `documented` |"),
    ),
    Control(
        # A pattern beside proven ones that no fixture of its rule
        # matches. Proving a rule by `any` of its patterns read this as
        # covered: that is how three of `ZS-MIG-12`'s four patterns were
        # counted as proven by a fixture none of them touched. Narrowing
        # one of them instead leaves its fixture unmatched too, which is
        # the branch below.
        sensitivity.PATTERN_UNCOVERED,
        lambda t: edit(
            t,
            "zig-style/references/migration.md",
            "`rg -n 'captureStackTrace|dumpStackTraceFromBase|walkStackWindows' src/`",
            "`rg -n 'captureStackTrace|dumpStackTraceFromBase|walkStackWindows' src/` "
            "and `rg -n 'dumpCurrentStackTraceInjected' src/`",
        ),
    ),
    Control(
        # The other direction of the cover, isolated. Pointing one
        # pattern at a fixture another already covers leaves *every
        # pattern* matching something, so only the orphaned fixture is
        # left to report — which is the branch that stops an uncovered
        # pattern from being "covered" by adding a snippet nobody
        # related to the rule.
        sensitivity.FIXTURE_UNCOVERED,
        lambda t: edit(
            t,
            "zig-style/references/migration.md",
            "rg -n 'captureStackTrace|dumpStackTraceFromBase|walkStackWindows' src/",
            "rg -n 'utf8Decode\\b' src/",
        ),
    ),
    Control(
        # The gap that was skipped without a word: a pattern shipped,
        # nothing proved it fires, and nothing said so.
        sensitivity.UNACCOUNTED,
        lambda t: append(
            t,
            f"{PY}/references/testing.md",
            "\n### PS-TEST-99 [M] Injected\n\nX.\n\n**Why:** y.\n\n"
            "**Check:** `rg -n 'injected_call\\(' src/`.\n",
        ),
    ),
    # An unproven entry for a rule that no longer ships a pattern.
    Control(
        sensitivity.STALE_UNPROVEN,
        lambda t: edit(
            t,
            f"{PY}/references/naming.md",
            "**Check:** `rg -n 'self\\.__[a-z]' src/` — every hit",
            "**Check:** every `self.__` name — every hit",
        ),
    ),
    Control(
        # The silent class: the command moved to `rg`, the dialect did
        # not. `\\|` compiles, runs, exits 1, and matches nothing.
        dialect.BRE_ALTERNATION,
        lambda t: edit(
            t,
            "zig-style/references/testing.md",
            "rg -n 'Io.Threaded|Io.Uring|Io.Kqueue'",
            "rg -n 'Io.Threaded\\|Io.Uring\\|Io.Kqueue'",
        ),
    ),
    Control(
        # The same class from the other side. The harness passes
        # `--multiline` and the printed command does not, so a command
        # wrapped across a line of the markdown runs here and exits 2
        # for the reader. Two shipped that way, and in one the
        # alternative after the newline was dead even here.
        dialect.WRAPPED,
        lambda t: edit(t, f"{PY}/references/output.md", SQL_COMMAND, SQL_WRAPPED),
    ),
    # A rule its own pattern would catch.
    Control(
        selfapply.DECIDES,
        lambda t: edit(t, "rust-style/references/unsafe.md", HEADER, PUB_FIELD),
    ),
    Control(
        # A Check ending in `| rg -v` was skipped whole, so a pattern in
        # it that `rg` rejects was never run to be rejected.
        selfapply.FILTERED_NO_ANSWER,
        lambda t: edit(
            t,
            "rust-style/references/modules.md",
            "`rg -n 'pub use' -g '*.rs' src/ | rg -v",
            "`rg -n 'pub use(' -g '*.rs' src/ | rg -v",
        ),
    ),
    # An exemption quoting words the rule no longer says.
    Control(
        selfapply.STALE_EXEMPTION,
        lambda t: edit(
            t, "zig-style/references/build.md", "has this block", "carries the guard"
        ),
    ),
    Control(
        mirror.TIER,
        lambda t: edit(
            t,
            "zig-style/references/naming.md",
            "### ZS-NAME-02 [M] Capitalize acronyms as ordinary English words",
            "### ZS-NAME-02 [S] Capitalize acronyms as ordinary English words",
        ),
    ),
]


@check("controls", "each branch that can fail a run still fails on its own defect")
def controls(tree: Tree, *, fast: bool = False) -> Iterator[Finding]:
    """A finding for each control that no longer fires as its branch.

    Nothing when they all do. The controls run at once, each over its
    own copy of the tree: nothing they share is written.
    """
    if not tree.skills:
        return
    source = tree.skills[0].root.parent
    # A control on a slow check would compile and run every example
    # once per control — the exact cost `--fast` exists to avoid.
    chosen = [c for c in CONTROLS if not (fast and _target(c).slow)]
    with ThreadPoolExecutor() as pool:
        for found in pool.map(partial(exercise, source=source), chosen):
            yield from found
    yield from _empty_corpus()


def _empty_corpus() -> Iterator[Finding]:
    """An empty skill extracts no blocks, for every profile's toolchain.

    Extraction is the only place that can tell "no defects" from "no
    input". Every profile that names a toolchain is exercised, not a
    hardcoded pair: an extractor that silently yields nothing makes the
    whole toolchain check report clean, which is the one failure mode
    this guard exists for.
    """
    for profile in registered():
        if not profile.toolchain:
            continue
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            root = Path(tmp) / profile.name
            (root / "references").mkdir(parents=True)
            (root / "SKILL.md").write_text("---\nname: x\n---\n")
            tc = toolchain_for(profile.toolchain)
            if tc and tc.extract(Skill(root), Path(tmp) / "out"):
                yield fail(
                    f"an empty {profile.toolchain} corpus still extracts blocks",
                    Location(),
                    EMPTY_CORPUS,
                )
