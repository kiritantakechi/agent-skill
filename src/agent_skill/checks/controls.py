"""Negative controls, run.

"Every check carries a negative control" was a claim in a README, verified by
hand when each check was written and never again — which is the same shape as the
defects the checks exist to catch. A check that cannot fail looks exactly like a
check that passes.

Each control copies the skills tree, injects one defect, and asserts that the
check owning it reports a failure. A control that stops firing is itself a
failure, and so is a fixture whose anchor text has drifted out of the skill.
"""

from __future__ import annotations

import shutil
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from ..report import Level, fail
from . import check


class FixtureGone(LookupError):
    """The text a control edits is no longer in the skill."""


#: Which skill each control's injection landed in, recorded as it happens.
#:
#: A control edits one skill and then the check ran over all four, which is
#: three quarters of the work thrown away — `self-application` alone was 24s of
#: a 39s `controls` run. Recorded rather than declared per control, so it cannot
#: drift away from what the control actually edits.
TOUCHED: list[str] = []


def edit(tree: Path, rel: str, old: str, new: str, count: int = 1) -> None:
    path = tree / rel
    text = path.read_text()
    if text.count(old) < count:
        raise FixtureGone(f"{rel}: {old[:60]!r}")
    path.write_text(text.replace(old, new, count))
    TOUCHED.append(rel)


def append(tree: Path, rel: str, text: str) -> None:
    path = tree / rel
    path.write_text(path.read_text() + text)
    TOUCHED.append(rel)


#: Why a check has no control, for the checks that have none.
#:
#: A mapping rather than a set, for the same reason `not_decisive` is one: a bare
#: list of names records that an exemption exists and nothing about whether it
#: still should. Two of these say the reason is not knowable from the code, which
#: is what is true — inventing a plausible one would read better and be worse.
WITHOUT_A_CONTROL = {
    "controls": "it is the mechanism the controls run through; a control on it would assert "
    "that the asserting works by asserting",
    "toolchain": "not knowable from the code. It compiles and runs every example, so a control "
    "would cost a full toolchain run — but nothing records whether that is the reason or "
    "whether nobody got to it",
    "mutation": "not knowable from the code. Same shape as `toolchain`, and the same gap",
}


def move(tree: Path, rel: str, name: str) -> None:
    """Rename a file in the throwaway tree, for a defect that is a file's name."""
    path = tree / rel
    if not path.exists():
        raise FixtureGone(rel)
    path.rename(path.with_name(name))
    TOUCHED.append(rel)


def throwaway_tree(source: Path, into: Path) -> Path:
    """A copy of the skills tree, plus what a check reads from beside it.

    One definition, because there were two: this loop and the `scratch` fixture
    in the tests, each deciding what a throwaway tree contains. They agreed until
    `documented` started reading the README, at which point the same control
    fired here and not there — and a control that fires in one runner and not the
    other is a control nobody can trust in either.
    """
    tree = into / "skills"
    shutil.copytree(source, tree, symlinks=True)
    beside = source.parent / "README.md"
    if beside.is_file():
        shutil.copy2(beside, into / "README.md")
    return tree


@dataclass(frozen=True, slots=True)
class Control:
    name: str
    check: str
    break_it: Callable[[Path], None]


HEADER = "const _: () = assert!(align_of::<Header>() == 4);\n"
PUB_FIELD = HEADER + (
    "\n/// Not layout-sensitive; this field must not be public.\n"
    "#[derive(Debug)]\npub struct Cursor {\n    pub offset: usize,\n}\n"
)

#: The one line of a `bevy-style` example this control appends to.
_TEST_BODY = "        let mut app = App::new();\n        app.add_plugins(HealthPlugin);"

#: PS-OUT-07's command as the standard now prints it, and as it used to be
#: written — wrapped at the column limit, which put a literal newline into the
#: pattern. Derived from the first rather than spelled twice: the two differ by
#: exactly the defect, and nothing else.
SQL_COMMAND = r"""`rg -n 'f"[^"\n]*(SELECT|INSERT|UPDATE|DELETE) ' src/`"""
SQL_WRAPPED = SQL_COMMAND.replace("UPDATE|DELETE", "UPDATE|\nDELETE")


def _unaccounted_anchor_rule(tree: Path) -> None:
    """An anchor standard's own defect, in the delta's examples, unmentioned by it.

    `crossref` reaches its verdict by four branches over the same input, and this
    control used to edit `SKILL.md` — which trips the citation branch too. It
    reported two failures and passed on the citation one alone for as long as the
    anchor sweep was unreachable, which is how the sweep stayed dead.

    So the injection lands in an example and leaves `SKILL.md` untouched: the
    anchor sweep is then the only branch that can report, and the control fails
    when it stops running.

    The rule is chosen for a property that could stop holding, so the property is
    asserted rather than assumed. `RS-OWN-43` works because `bevy-style` never
    names it; the day it does, the injection would be accounted for and this
    control would pass while proving nothing.
    """
    if "RS-OWN-43" in (tree / "bevy-style/SKILL.md").read_text():
        raise FixtureGone(
            "bevy-style/SKILL.md now names RS-OWN-43, so its defect is accounted "
            "for and no longer reaches the anchor sweep"
        )
    edit(
        tree,
        "bevy-style/references/testing.md",
        _TEST_BODY,
        f"{_TEST_BODY}\n        let _ = app.world().resource::<AppTypeRegistry>().read();",
    )


#: A `Decided by tools` table with one row, for the controls on Rust rows.
def _rust_row(lint: str, level: str) -> str:
    return (
        "\n## Decided by tools\n\n| Tool | Lint | Level | Forbids |\n|---|---|---|---|\n"
        f"| clippy | `{lint}` | {level} | an unwrap |\n"
    )


#: `python-style` is the standard the structure controls inject into: it was the
#: first to conform, and a defect injected into an exempt one reaches nothing.
PY = "python-style"

#: A rule of the async family, filed in the testing chapter. New, so no rename
#: row names it and only the family branch of `skeleton` can report it.
MISFILED = "\n### PS-ASYNC-99 [M] Misfiled\n\nX.\n\n**Why:** y.\n\n**Check:** z.\n"

STRUCTURE: list[Control] = [
    Control(
        "a section title with a subtitle the other standards do not have",
        "skeleton",
        lambda t: edit(
            t, f"{PY}/SKILL.md", "## 3. Design principles\n", "## 3. Design principles — less\n"
        ),
    ),
    Control(
        "a chapter named outside the shared vocabulary",
        "skeleton",
        lambda t: move(t, f"{PY}/references/async.md", "asyncio.md"),
    ),
    Control(
        "a rule filed in a chapter whose family is another",
        "skeleton",
        lambda t: append(t, f"{PY}/references/testing.md", MISFILED),
    ),
    Control(
        "a severity label the shared model does not have",
        "skeleton",
        lambda t: edit(t, f"{PY}/references/review-checklist.md", "| **Style** |", "| **Nit** |"),
    ),
    Control(
        "section 5 drifting from the protocol's review order",
        "skeleton",
        lambda t: edit(t, f"{PY}/SKILL.md", "10. **The build.**", "10. **The release.**"),
    ),
    Control(
        "a rename row leading to a rule that does not exist",
        "skeleton",
        lambda t: edit(
            t,
            f"{PY}/references/migration.md",
            "| `PS-ERR-09` | lint `ruff:E722` |",
            "| `PS-ERR-09` | `PS-ERR-99` |",
        ),
    ),
    Control(
        "a shared sentence edited in one standard's copy",
        "shared-text",
        lambda t: edit(t, f"{PY}/SKILL.md", "Apply it literally.", "Apply it with judgement."),
    ),
    Control(
        # The chapter's last rule, cited nowhere but its heading and its contents
        # line, so moving its number leaves no dangling citation behind.
        "a gap in a chapter's numbering",
        "anatomy",
        lambda t: edit(t, f"{PY}/references/migration.md", "PS-MIG-15 [M]", "PS-MIG-17 [M]", 2),
    ),
    Control(
        "a Why that runs to a fourth line",
        "anatomy",
        lambda t: edit(
            t,
            f"{PY}/references/api.md",
            "**Why:** without it the public surface is",
            "**Why:** one line more.\nwithout it the public surface is",
        ),
    ),
    Control(
        "a ty lint row at a level the shipped configuration does not set",
        "citations",
        lambda t: edit(
            t,
            f"{PY}/references/async.md",
            "| ty | `deprecated` | warn |",
            "| ty | `deprecated` | error |",
        ),
    ),
]


CONTROLS: list[Control] = [
    *STRUCTURE,
    Control(
        # The asset denies it; a row saying `warn` describes a build that is not shipped.
        "a Rust lint row at a level the shipped table does not set",
        "citations",
        lambda t: append(t, "rust-style/references/errors.md", _rust_row("unwrap_used", "warn")),
    ),
    Control(
        "a Rust lint row naming a lint clippy does not have",
        "citations",
        lambda t: append(t, "rust-style/references/errors.md", _rust_row("unwarp_used", "deny")),
    ),
    Control(
        "a workflow installing an interpreter the harness did not verify against",
        "pins",
        lambda t: edit(
            t,
            "python-style/assets/ci.yml",
            "uv python install cpython-3.15.0+freethreaded",
            "uv python install 3.15t",
        ),
    ),
    Control(
        "a python rule citing a lint code the shipped config disables",
        "citations",
        lambda t: edit(
            t,
            "python-style/references/concurrency.md",
            "**Check:** `rg -n 'f_locals' src/`",
            "**Check:** COM812 decides this. `rg -n 'f_locals' src/`",
        ),
    ),
    Control(
        "a ty rule the asset ships and the harness does not verify",
        "citations",
        lambda t: edit(
            t,
            "python-style/assets/ty.toml",
            "[analysis]",
            'redundant-cast = "error"\n\n[analysis]',
        ),
    ),
    Control(
        "a python example using the future import the standard forbids",
        "conventions",
        lambda t: edit(
            t,
            "python-style/references/concurrency.md",
            "import sys\nimport sysconfig",
            "from __future__ import annotations\n\nimport sys\nimport sysconfig",
        ),
    ),
    Control(
        "prose naming the forbidden future import without condemning it",
        "prose",
        lambda t: edit(
            t,
            "python-style/references/concurrency.md",
            "Unless a block shows its own imports,",
            "Reach for `from __future__ import annotations` here. Unless a block shows its own"
            " imports,",
        ),
    ),
    Control(
        "a python block whose marker is outside this skill's vocabulary",
        "markers",
        lambda t: edit(
            t,
            "python-style/references/concurrency.md",
            "# verified — GOOD\nimport sys\nimport sysconfig",
            "# does-not-compile — GOOD\nimport sys\nimport sysconfig",
        ),
    ),
    Control(
        # `rejected` alone says the block is wrong and not who says so — the
        # word that replaced `does-not-compile` exists to name the tool.
        "a rejected block that does not name the tool rejecting it",
        "markers",
        lambda t: edit(
            t,
            "python-style/references/concurrency.md",
            "# verified — GOOD\nimport sys\nimport sysconfig",
            "# rejected — the GIL is off\nimport sys\nimport sysconfig",
        ),
    ),
    Control(
        "an asset citing a rule the skill does not define",
        "assets",
        lambda t: edit(t, "bevy-style/assets/ci.yml", "BV-ARC-01", "BV-ARC-99"),
    ),
    Control(
        "a bevy example using an API the skill forbids",
        "self-application",
        lambda t: edit(
            t,
            "bevy-style/references/events.md",
            "mut damage: MessageReader<DamageDealt>",
            "mut damage: EventReader<DamageDealt>",
        ),
    ),
    Control(
        "a component with a private field",
        "conventions",
        lambda t: edit(
            t,
            "bevy-style/references/scheduling.md",
            "struct Velocity(pub Vec3);",
            "struct Velocity(Vec3);",
        ),
    ),
    Control(
        "a component that is not reflected",
        "conventions",
        lambda t: edit(
            t,
            "bevy-style/references/scheduling.md",
            "#[derive(Component, Debug, Reflect)]\n#[reflect(Component)]\nstruct Velocity",
            "#[derive(Component, Debug)]\nstruct Velocity",
        ),
    ),
    Control(
        "a component that does not derive Debug",
        "conventions",
        lambda t: edit(
            t,
            "bevy-style/references/ecs.md",
            "#[derive(Component, Debug, Clone, Copy, PartialEq, Reflect)]",
            "#[derive(Component, Clone, Copy, PartialEq, Reflect)]",
        ),
    ),
    Control(
        "a plugin added as a function rather than a type",
        "self-application",
        lambda t: edit(
            t,
            "bevy-style/references/testing.md",
            "app.add_plugins(HealthPlugin);",
            "app.add_plugins(health_plugin);",
        ),
    ),
    Control(
        "a plugin type missing a derive every plugin type carries",
        "conventions",
        lambda t: edit(
            t,
            "bevy-style/references/architecture.md",
            "#[derive(Debug, Default)]\npub struct DecayPlugin;",
            "#[derive(Debug)]\npub struct DecayPlugin;",
        ),
    ),
    Control(
        "a plugin type without the suffix its trait requires",
        "conventions",
        lambda t: edit(
            t,
            "bevy-style/references/architecture.md",
            "impl Plugin for CombatPlugin {",
            "impl Plugin for Combat {",
        ),
    ),
    Control(
        "an anchor rule that fires on the delta's examples and is not accounted for",
        "crossref",
        lambda t: _unaccounted_anchor_rule(t),
    ),
    Control(
        "a citation into a standard that has no such rule",
        "crossref",
        lambda t: edit(
            t,
            "bevy-style/SKILL.md",
            "`RS-API-24` Keep every struct field private",
            "`RS-API-99` Keep every struct field private",
        ),
    ),
    Control(
        "an override row quoting a title the other standard no longer has",
        "crossref",
        lambda t: edit(
            t,
            "bevy-style/SKILL.md",
            "`RS-NAME-33` Never suffix a name with the language construct",
            "`RS-NAME-33` Always suffix a name with the language construct",
        ),
    ),
    Control(
        "frontmatter with no name",
        "frontmatter",
        lambda t: edit(t, "rust-style/SKILL.md", "name: rust-style", "nome: rust-style"),
    ),
    Control(
        "pointer rule that grew a Why",
        "anatomy",
        # zig-style is where pointer rules still live: the standards brought
        # over to standard-structure removed theirs.
        lambda t: edit(
            t,
            "zig-style/references/comptime-and-generics.md",
            "constant, and nothing in the build output says so. See also ZS-CT-07 on bounding",
            "constant.\n\n**Why:** it is. See also ZS-CT-07 on bounding",
        ),
    ),
    Control(
        "core rule citing the wrong chapter",
        "anatomy",
        lambda t: edit(
            t,
            "rust-style/SKILL.md",
            "`references/api.md` RS-API-51",
            "`references/errors.md` RS-API-51",
        ),
    ),
    Control(
        "a rule appended in the middle of a chapter",
        "anatomy",
        lambda t: edit(
            t,
            "bevy-style/references/scheduling.md",
            "BV-SCH-09 [M] Never read per-frame input",
            "BV-SCH-77 [M] Never read per-frame input",
            2,
        ),
    ),
    Control(
        "two rules sharing a title",
        "anatomy",
        lambda t: edit(
            t,
            "zig-style/references/types-and-data.md",
            "ZS-TYPE-30 [M] Return the lowest-dimensionality type that can carry the answer",
            "ZS-TYPE-30 [M] Reference long-lived elements by handle, not by pointer",
            2,
        ),
    ),
    Control(
        "shipped lint weaker than the verified one",
        "lints",
        lambda t: edit(
            t,
            "rust-style/assets/Cargo.toml",
            'indexing_slicing = "deny"',
            'indexing_slicing = "warn"',
        ),
    ),
    Control(
        "a prose line over the column limit",
        "layout",
        lambda t: append(t, "zig-style/references/types-and-data.md", "\n" + "x " * 60 + "\n"),
    ),
    Control(
        "a second marker line in one block",
        "markers",
        lambda t: edit(
            t,
            "zig-style/references/naming-and-files.md",
            "// fragment — BAD\n",
            "// fragment — BAD\n// GOOD\n",
        ),
    ),
    Control(
        "pub field on a non-repr(C) type",
        "conventions",
        lambda t: edit(t, "rust-style/references/unsafe.md", HEADER, PUB_FIELD),
    ),
    Control(
        "`.?` in a GOOD example",
        "conventions",
        lambda t: edit(
            t,
            "zig-style/references/types-and-data.md",
            '// verified — GOOD\nconst std = @import("std");',
            '// verified — GOOD\nconst std = @import("std");\n'
            "const injected: u8 = (@as(?u8, 3)).?;",
        ),
    ),
    Control(
        "`builtin` imported below `std`",
        "conventions",
        lambda t: edit(
            t,
            "zig-style/references/c-interop-and-targets.md",
            'const builtin = @import("builtin");\nconst std = @import("std");\n'
            "const assert = std.debug.assert;",
            'const std = @import("std");\nconst builtin = @import("builtin");\n'
            "const assert = std.debug.assert;",
        ),
    ),
    Control(
        "build provenance in prose",
        "prose",
        lambda t: append(
            t,
            "zig-style/references/types-and-data.md",
            "\nMeasured on this machine: the layout is stable.\n",
        ),
    ),
    Control(
        "prose recommending a forbidden spelling",
        "prose",
        lambda t: edit(
            t,
            "zig-style/references/types-and-data.md",
            "**Why:**",
            "Reach for `slot.?` when the optional is provably present.\n\n**Why:**",
        ),
    ),
    Control(
        "a manifest that does not parse",
        "assets",
        lambda t: append(t, "rust-style/assets/rustfmt.toml", "\nbroken = = 1\n"),
    ),
    Control(
        # The defect this check exists for: a check ships, and the README's
        # promise of a reason for every one quietly stops being true.
        "a check registered with no row in the README that promises one for every check",
        "documented",
        lambda t: edit(t.parent, "README.md", "| `documented` |", "| `renamed-away` |"),
    ),
    Control(
        # A pattern narrowed until it no longer catches the defect it was written
        # for still reports clean, because clean is what an empty result looks like.
        "a pattern narrowed until it no longer catches its own defect",
        "sensitivity",
        lambda t: edit(
            t,
            "python-style/references/async.md",
            "rg -n 'create_task|ensure_future' src/",
            "rg -n 'ensure_future' src/",
        ),
    ),
    Control(
        # The one above narrows a rule's only pattern, which `any` and every both
        # report. This narrows one of four, leaving three still matching — which
        # `any` read as covered. That is how three of `ZS-MIG-13`'s four patterns
        # were counted as proven by a fixture none of them touched.
        "one pattern of several narrowed until its own fixture no longer matches",
        "sensitivity",
        lambda t: edit(
            t,
            "zig-style/references/migration-and-dead-apis.md",
            "rg -n 'captureStackTrace|dumpStackTraceFromBase|walkStackWindows' src/",
            "rg -n 'dumpStackTraceFromBase|walkStackWindows' src/",
        ),
    ),
    Control(
        # The other direction of the cover, isolated. Pointing one pattern at a
        # fixture another already covers leaves *every pattern* matching
        # something, so only the orphaned fixture is left to report — which is
        # the branch that stops an uncovered pattern from being "covered" by
        # adding a snippet nobody related to the rule.
        "a fixture no pattern in its rule matches",
        "sensitivity",
        lambda t: edit(
            t,
            "zig-style/references/migration-and-dead-apis.md",
            "rg -n 'captureStackTrace|dumpStackTraceFromBase|walkStackWindows' src/",
            "rg -n 'utf8Decode\\b' src/",
        ),
    ),
    Control(
        # The reader installs what the asset says; the harness verified against
        # what pyproject says. A silent disagreement hands them a different build.
        "a shipped asset pinning a tool version the harness never verified against",
        "pins",
        lambda t: edit(
            t,
            "python-style/assets/pyproject.toml",
            'typecheck = ["ty==0.0.90"]',
            'typecheck = ["ty==0.0.60"]',
        ),
    ),
    Control(
        "an asset nothing references",
        "assets",
        lambda t: (t / "rust-style/assets/orphan.toml").write_text("x = 1\n"),
    ),
    Control(
        # The defect verbatim: the shipped template named itself `acme-widget`
        # and its package `acmewidget`, so no backend could find the package.
        "a project template whose distribution name does not match its module",
        "assets",
        lambda t: edit(
            t,
            "python-style/assets/pyproject.toml",
            'name = "acmewidget"',
            'name = "acme-widget"',
        ),
    ),
    Control(
        # The silent class: the command moved to `rg`, the dialect did not.
        # `\\|` compiles, runs, exits 1, and matches nothing.
        "an `rg` pattern still carrying BRE's escaped alternation",
        "dialect",
        lambda t: edit(
            t,
            "zig-style/references/testing-and-fuzzing.md",
            "rg -n 'Io.Threaded|Io.Uring|Io.Kqueue'",
            "rg -n 'Io.Threaded\\|Io.Uring\\|Io.Kqueue'",
        ),
    ),
    Control(
        # The same class from the other side. The harness passes `--multiline`
        # and the printed command does not, so a command wrapped across a line
        # of the markdown runs here and exits 2 for the reader. Two shipped that
        # way, and in one the alternative after the newline was dead even here.
        "an `rg` command wrapped across a line of the source",
        "dialect",
        lambda t: edit(t, "python-style/references/output.md", SQL_COMMAND, SQL_WRAPPED),
    ),
    Control(
        "a rule its own pattern would catch",
        "self-application",
        lambda t: edit(t, "rust-style/references/unsafe.md", HEADER, PUB_FIELD),
    ),
    Control(
        "an exemption quoting words the rule no longer says",
        "self-application",
        lambda t: edit(
            t, "zig-style/references/build-and-project.md", "has this block", "carries the guard"
        ),
    ),
    Control(
        "a mirrored rule whose tier drifted",
        "mirror",
        lambda t: edit(
            t,
            "zig-style/references/naming-and-files.md",
            "### ZS-NAME-02 [M] Capitalize acronyms as ordinary English words",
            "### ZS-NAME-02 [S] Capitalize acronyms as ordinary English words",
        ),
    ),
]


@check("controls", "each check still fails on the defect it owns", scope="all")
def controls(skills, *, fast: bool = False):
    """Yields a finding per control that no longer fires, and nothing when they all do."""
    from ..model import discover
    from . import by_name

    if not skills:
        return
    source = skills[0].root.parent
    for control in CONTROLS:
        target = by_name(control.check)
        if target is None:
            yield fail(f"{control.name}: no check named {control.check!r}", "controls")
            continue
        if target.slow and fast:
            # `controls` is not marked slow itself, so without this `--fast`
            # would compile and run every example once per control — the exact
            # cost `--fast` exists to avoid.
            continue
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            tree = throwaway_tree(source, Path(tmp))
            TOUCHED.clear()
            try:
                control.break_it(tree)
            except FixtureGone as e:
                yield fail(f"{control.name}: cannot be injected any more — {e}", "controls")
                continue
            found = discover(tree)
            # A control that writes a file directly records nothing, and a
            # cross-skill check needs its siblings; both fall back to the set.
            # An "all"-scope check reads one skill against another, so it needs
            # the whole set even when the injection landed in one of them. Read
            # from the check rather than from a list of names beside it: a list
            # would have to be remembered when a cross-skill check is added, and
            # forgetting scopes its control to one skill while it still passes.
            injected = {rel.split("/")[0] for rel in TOUCHED}
            if injected and target.scope != "all":
                found = [s for s in found if s.name in injected] or found
            result = target.run(found)
            if not any(f.level is Level.FAIL for f in result.findings):
                yield fail(
                    f"{control.name}: `{control.check}` still passes — the control no longer fires",
                    "controls",
                )

    yield from _empty_corpus()


def _empty_corpus():
    """Extraction is the only place that can tell "no defects" from "no input".

    Every profile that names a toolchain is exercised, not a hardcoded pair: an
    extractor that silently yields nothing makes the whole toolchain check report
    clean, which is the one failure mode this guard exists for.
    """
    from ..lang import toolchain_for
    from ..model import Skill
    from ..profiles import registered

    for profile in registered():
        if profile.toolchain is None:
            continue
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            root = Path(tmp) / profile.name
            (root / "references").mkdir(parents=True)
            (root / "SKILL.md").write_text("---\nname: x\n---\n")
            tc = toolchain_for(profile.toolchain)
            if tc and tc.extract(Skill(root), Path(tmp) / "out"):
                yield fail(f"an empty {profile.toolchain} corpus still extracts blocks", "controls")
