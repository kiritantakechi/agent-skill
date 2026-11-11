## Why

The owner wants to list the skills on agent-skill marketplaces, starting with Agensi. Agensi takes
one `.zip` per skill. The zip holds a single top-level folder named after the skill, with `SKILL.md`
directly inside it and a `name` equal to the folder's.

`agent-skill build` already writes exactly that layout: each skill rooted at its name, holding what
the repository ships. But it names the file `<name>.skill`. That is still a zip, but a marketplace
upload that wants `.zip` refuses it, so every upload starts with renaming files by hand. Nothing
builds the packages in CI either, so a release is uploaded from whatever a laptop last built.

## What Changes

- **`agent-skill build` writes `<name>.zip`.** The layout is unchanged. The suffix names the
  format, which a skill upload such as Agensi's asks for.
- **A `package` workflow builds every skill in CI.**
  - **On a `style-standards--v*` tag:** it attaches each skill's zip to that tag's GitHub release,
    one asset per skill.
  - **On dispatch:** it uploads the zips as one artifact.
  - **Setup:** it uses python-style's setup steps at their pins, as `check.yml` does, and pins
    `actions/upload-artifact` to a commit.
- **The package test also holds what a marketplace checks.** The file is a `.zip`, `SKILL.md`
  sits directly in the one top-level folder, and the frontmatter `name` equals that folder.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `harness-integrity`: two requirements added, on what a package is and on the workflow that
  publishes the packages.

## Impact

- **Code:** `src/agent_skill/build.py` and `src/agent_skill/cli.py` (the suffix and its help), and
  `tests/test_install.py`.
- **CI and docs:** a new `.github/workflows/package.yml`, and the README.
- **Users:** a `dist/<name>.skill` from an earlier build is now `dist/<name>.zip`. `dist/` is
  ignored, so nothing tracked changes.
- **Skill content:** none.
