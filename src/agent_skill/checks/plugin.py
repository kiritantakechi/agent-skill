"""The Claude Code plugin the skills ship as, against its manifests.

The skills reach a reader as the `style-standards` plugin, installed
from this repository's marketplace. Two JSON files describe it, and
nothing read them: a skill added beside the others, a version stated
twice, or a manifest naming a path that moved would ship as written. So
the manifests are held to the layout and the skills, and Claude Code's
own validator runs over both.
"""

import json
from pathlib import Path
lazy from collections.abc import Iterator, Sequence

from agent_skill.checks import check
from agent_skill.layout import PLUGIN, SKILLS, root_of
from agent_skill.proc import have, run
from agent_skill.report import fail, unrun
lazy from agent_skill.model import Skill
lazy from agent_skill.report import Finding

#: Where Claude Code reads each manifest, relative to what it describes.
MANIFEST = Path(".claude-plugin") / "plugin.json"
MARKETPLACE = Path(".claude-plugin") / "marketplace.json"


@check(
    "plugin",
    "the plugin and marketplace manifests, against the skills",
    scope="all",
    needs=("claude",),
)
def plugin(skills: Sequence[Skill]) -> Iterator[Finding]:
    """The manifests agree with the layout, and the validator passes."""
    if not skills:
        return
    root = root_of(skills[0].root.parent)
    manifest, unread = _load(root / PLUGIN / MANIFEST)
    market, unread_market = _load(root / MARKETPLACE)
    # Every path that read nothing is reported. Only a missing file used
    # to be: one that was there and did not parse, or parsed to a list,
    # returned with no finding at all, and the check passed having held
    # nothing to the layout.
    for path, problem in ((PLUGIN / MANIFEST, unread), (MARKETPLACE, unread_market)):
        if problem:
            yield fail(f"`{path}` {problem}", "plugin")
    if manifest is None or market is None:
        return
    yield from _manifest(manifest, root)
    yield from _marketplace(market)
    shipped = {p.parent.name for p in (root / SKILLS).glob("*/SKILL.md")}
    if shipped != {s.name for s in skills}:
        yield fail(
            f"the plugin ships {sorted(shipped)}, and the checks read "
            f"{sorted(s.name for s in skills)}",
            "plugin",
        )
    yield from _validate(root)


def _load(path: Path) -> tuple[dict[str, object] | None, str]:
    """The manifest as an object, or None and why it is not one."""
    try:
        text = path.read_text()
    except OSError:
        return None, "is missing"
    try:
        loaded = json.loads(text)
    except ValueError as e:
        return None, f"is not JSON: {e}"
    if not isinstance(loaded, dict):
        return None, "is JSON, but not an object"
    return {str(key): value for key, value in loaded.items()}, ""


def _manifest(manifest: dict[str, object], root: Path) -> Iterator[Finding]:
    """The plugin is named by its directory, versioned, and licensed."""
    where = f"{PLUGIN / MANIFEST}"
    if manifest.get("name") != PLUGIN.name:
        yield fail(
            f"names the plugin {manifest.get('name')!r}, not {PLUGIN.name!r}", where
        )
    if not manifest.get("version"):
        yield fail("states no `version`, so an update cannot reach anyone", where)
    if not manifest.get("license") or not (root / "LICENSE").is_file():
        yield fail("needs both a `license` and a LICENSE file at the root", where)


def _marketplace(market: dict[str, object]) -> Iterator[Finding]:
    """One entry for this plugin, from its directory, versioned once."""
    where = f"{MARKETPLACE}"
    entries = market.get("plugins")
    found = (
        [e for e in entries if isinstance(e, dict) and e.get("name") == PLUGIN.name]
        if isinstance(entries, list)
        else []
    )
    if not found:
        yield fail(f"lists no `{PLUGIN.name}` plugin", where)
        return
    if found[0].get("source") != f"./{PLUGIN.as_posix()}":
        yield fail(f"sources `{PLUGIN.name}` from {found[0].get('source')!r}", where)
    if "version" in found[0]:
        yield fail(
            "states a `version` for the plugin, which its manifest states; two "
            "can disagree, and Claude Code reads the manifest's",
            where,
        )


def _validate(root: Path) -> Iterator[Finding]:
    """Claude Code's validator, over the marketplace and the plugin."""
    if not have("claude"):
        yield unrun("`claude` is not available, so no manifest was validated", "plugin")
        return
    for target, strict in ((root, False), (root / PLUGIN, True)):
        ran = run(
            [
                "claude",
                "plugin",
                "validate",
                str(target),
                *(["--strict"] if strict else []),
            ],
            timeout=120,
        )
        if not ran.ok:
            tail = " ".join((ran.out + ran.err).split()[-40:])
            yield fail(f"`claude plugin validate` refuses it: {tail}", f"{target.name}")
