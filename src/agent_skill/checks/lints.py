"""The shipped lint table and the one the examples are verified against.

They must be the same table. The asset once set
`indexing_slicing = "warn"` where a rule requires deny, and the verified
crate quietly omitted a third lint while its comment named two.
"""

import re
import tomllib
lazy from collections.abc import Iterator

from agent_skill.checks import check
from agent_skill.report import Finding, fail
lazy from agent_skill.model import Skill


def table(text: str, prefix: str = "") -> dict[str, str]:
    """A manifest's lint table as `section.lint` -> its raw value."""
    out: dict[str, str] = {}
    section: str | None = None
    for line in text.split("\n"):
        if m := re.match(rf"^\[{prefix}lints\.(\w+)\]", line.strip()):
            section = str(m.group(1))
            continue
        if line.strip().startswith("["):
            section = None
            continue
        # Never empty when set: `\w+` matched at least one character.
        if section is not None and "=" in line and not line.strip().startswith("#"):
            key, value = line.split("=", 1)
            out[f"{section}.{key.strip()}"] = value.split("#")[0].strip()
    return out


@check("lints", "the shipped lint table equals the verified one")
def lints(skill: Skill) -> Iterator[Finding]:
    """How the shipped lint tables differ from the verified ones."""
    manifest = skill.root / "assets" / "Cargo.toml"
    crate = skill.profile.crate
    if crate is None or not manifest.exists():
        return
    shipped = table(manifest.read_text(), "workspace.")
    verified = {f"{s}.{k}": v for s, t in crate.lints.items() for k, v in t.items()}

    for key in sorted(set(shipped) - set(verified) - crate.unverifiable):
        yield fail(f"assets/Cargo.toml ships `{key}` that nothing verifies", skill.name)
    for key in sorted(set(verified) - set(shipped)):
        yield fail(
            f"the verified crate has `{key}` the shipped asset does not", skill.name
        )
    for key in sorted(set(shipped) & set(verified)):
        if shipped[key] != verified[key]:
            yield fail(
                f"`{key}` is {shipped[key]} in the asset, "
                f"{verified[key]} in the verified crate",
                skill.name,
            )

    # clippy's own configuration: the same two tables, compared the same
    # way.
    asset = skill.root / "assets" / "clippy.toml"
    shipped_clippy = tomllib.loads(asset.read_text()) if asset.exists() else {}
    if shipped_clippy != crate.clippy:
        yield fail(
            f"assets/clippy.toml is {shipped_clippy} "
            f"and the verified crate's is {crate.clippy}",
            skill.name,
        )
