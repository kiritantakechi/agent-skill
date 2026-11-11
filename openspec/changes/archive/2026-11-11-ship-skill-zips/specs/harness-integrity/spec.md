## ADDED Requirements

### Requirement: A skill's package is a zip a skill marketplace accepts

`agent-skill build` SHALL write each skill as `<name>.zip`. The archive SHALL hold one top-level
folder, named after the skill, with the skill's `SKILL.md` directly inside it and every other file
the skill ships below it. It SHALL hold nothing the repository ignores.

#### Scenario: A package is built

- **WHEN** `agent-skill build` packages `zig-style`
- **THEN** it writes `dist/zig-style.zip`, whose every entry starts with `zig-style/`, and which holds
  `zig-style/SKILL.md`

#### Scenario: A cache in a skill's directory

- **WHEN** a tool has left `__pycache__/` or `.ruff_cache/` inside a skill's directory
- **THEN** the package leaves it out

### Requirement: A release tag publishes every skill's package

The repository SHALL have a workflow that builds every skill's package with `agent-skill build`.
On a `style-standards--v*` tag, it SHALL attach each package to the tag's release as its own asset.
On dispatch, it SHALL upload the packages as an artifact. It SHALL meet the action-pinning and
self-application requirements the repository's other workflow meets.

#### Scenario: The owner tags a release

- **WHEN** `style-standards--v2.1.0` is pushed
- **THEN** its release holds `python-style.zip`, `rust-style.zip`, `bevy-style.zip` and
  `zig-style.zip`, each ready to upload

#### Scenario: A setup step drifts

- **WHEN** the workflow sets up uv at a version other than the one python-style's `ci.yml` pins
- **THEN** `self-application` fails, naming the step
