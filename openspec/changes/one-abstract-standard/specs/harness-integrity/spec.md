## ADDED Requirements

### Requirement: The repository runs its own harness in CI, in the shape it ships

The repository SHALL have a workflow that runs, on every push and pull request, the fast check, the
tests that need no toolchain, and the linters and type checker the shipped Python configuration
names. A second job SHALL run the full harness, toolchains included, on a schedule and on demand. The
workflow SHALL use python-style's shipped CI steps, at the same pins, and SHALL meet the
action-pinning requirement the shipped assets meet.

#### Scenario: The workflow drifts from the asset

- **WHEN** the repository's workflow sets up uv at a version other than the one python-style's
  `ci.yml` pins, or names an action at another commit
- **THEN** the run fails, naming the step

#### Scenario: A pull request

- **WHEN** a pull request is opened
- **THEN** the fast job runs every check but the toolchain and mutation runs, with the tools those
  checks call (the compilers `assets`, `citations` and `pins` ask for a version, and the plugin
  validator), and its result shows on the pull request

#### Scenario: The full harness

- **WHEN** the schedule fires or the owner dispatches the workflow
- **THEN** the full job installs the pinned Python, Rust and Zig and runs `agent-skill check`
  with toolchains and mutation included
