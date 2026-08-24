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


def edit(tree: Path, rel: str, old: str, new: str, count: int = 1) -> None:
    path = tree / rel
    text = path.read_text()
    if text.count(old) < count:
        raise FixtureGone(f"{rel}: {old[:60]!r}")
    path.write_text(text.replace(old, new, count))


def append(tree: Path, rel: str, text: str) -> None:
    path = tree / rel
    path.write_text(path.read_text() + text)


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

CONTROLS: list[Control] = [
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
        "a plugin written as a function rather than a type",
        "self-application",
        lambda t: edit(
            t,
            "bevy-style/references/assets.md",
            "#[derive(Debug, Default)]\npub struct SpritesPlugin;\n\n"
            "impl Plugin for SpritesPlugin {\n"
            "    fn build(&self, app: &mut App) {\n"
            "        app.init_resource::<SpriteHandles>();\n"
            "    }\n}",
            "pub fn plugin(app: &mut App) {\n    app.init_resource::<SpriteHandles>();\n}",
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
        lambda t: edit(
            t,
            "bevy-style/SKILL.md",
            "| `RS-API-26` Keep tuple-struct fields private too",
            "| `RS-API-99` Keep tuple-struct fields private too",
        ),
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
            "`RS-NAM-33` Never suffix a name with the language construct",
            "`RS-NAM-33` Always suffix a name with the language construct",
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
        lambda t: edit(
            t,
            "rust-style/references/cli-apps.md",
            "ten-thousand-file traversal because one file is unreadable is the wrong default.",
            "ten-thousand-file traversal is the wrong default.\n\n**Why:** it is.",
        ),
    ),
    Control(
        "core rule citing the wrong chapter",
        "anatomy",
        lambda t: edit(
            t,
            "rust-style/SKILL.md",
            "`references/api-design.md` RS-API-51",
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
        lambda t: edit(t, "rust-style/references/unsafe-ffi.md", HEADER, PUB_FIELD),
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
        "an asset nothing references",
        "assets",
        lambda t: (t / "rust-style/assets/orphan.toml").write_text("x = 1\n"),
    ),
    Control(
        "a rule its own grep would catch",
        "self-application",
        lambda t: edit(t, "rust-style/references/unsafe-ffi.md", HEADER, PUB_FIELD),
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
def controls(skills):
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
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            tree = Path(tmp) / "skills"
            shutil.copytree(source, tree, symlinks=True)
            try:
                control.break_it(tree)
            except FixtureGone as e:
                yield fail(f"{control.name}: cannot be injected any more — {e}", "controls")
                continue
            result = target.run(discover(tree))
            if not any(f.level is Level.FAIL for f in result.findings):
                yield fail(
                    f"{control.name}: `{control.check}` still passes — the control no longer fires",
                    "controls",
                )

    yield from _empty_corpus()


def _empty_corpus():
    """Extraction is the only place that can tell "no defects" from "no input"."""
    from ..lang import toolchain_for
    from ..model import Skill

    for name, toolchain in (("rust-style", "rust"), ("zig-style", "zig")):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            root = Path(tmp) / name
            (root / "references").mkdir(parents=True)
            (root / "SKILL.md").write_text("---\nname: x\n---\n")
            tc = toolchain_for(toolchain)
            if tc and tc.extract(Skill(root), Path(tmp) / "out"):
                yield fail(f"an empty {toolchain} corpus still extracts blocks", "controls")
