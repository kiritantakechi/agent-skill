# Build

Scope: how a project is built, configured, checked and released: its manifest, its dependencies and
their pins, what a package ships, the tools it runs, and the continuous integration that runs them.
Moving code to a new release is the migration chapter's.

## Contents

- **Dependencies and pins**
  - AS-BUILD-01 [M] Pin the toolchain and every tool that decides whether the build passes
  - AS-BUILD-02 [M] Commit the lock file, and keep it the only one
  - AS-BUILD-03 [M] Give a library version ranges, never exact pins
  - AS-BUILD-04 [M] Justify every dependency; the default is none
- **What ships**
  - AS-BUILD-05 [M] Publish an allowlist of what ships, never a list of what is left out
- **Continuous integration**
  - AS-BUILD-06 [M] Gate continuous integration on the formatter's check
  - AS-BUILD-07 [M] Pin every third-party CI action to a full commit, with its release as a comment

---

## Dependencies and pins

### AS-BUILD-01 [M] Pin the toolchain and every tool that decides whether the build passes

The compiler or interpreter, and every tool whose verdict can fail the build, are held to one exact
release. A floor lets a new release fail the build on code nobody touched, and differently for two
developers on one commit; a pin makes each upgrade a reviewed change with its own diff.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-BUILD-08 | realises | [M] | |
| rust-style | RS-BUILD-35 | realises | [M] | |
| zig-style | ZS-BUILD-25 | realises | [M] | |

### AS-BUILD-02 [M] Commit the lock file, and keep it the only one

The file that records the exact versions a build resolved is committed with the source, so that a
build is reproducible and fails on the project's schedule rather than on a dependency's release
schedule. A second artefact recording the same thing is a source of truth nothing reads.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-BUILD-10 | realises | [M] | |
| rust-style | RS-BUILD-10 | realises | [M] | |
| zig-style | | absent | | Zig has no resolver and no lock file: the manifest names each dependency by the hash of its content, and that hash is the pin |

### AS-BUILD-03 [M] Give a library version ranges, never exact pins

A library states the range of each dependency it accepts and leaves the choice of version to the
build that uses it. An exact pin makes the library uninstallable beside any other package that wants
a different version; reproducibility belongs to the application's lock file.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-BUILD-09 | realises | [M] | |
| rust-style | RS-BUILD-20 | realises | [M] | |
| zig-style | | absent | | Zig has no version ranges: a dependency is one address and one content hash, so there is no range to widen |

### AS-BUILD-04 [M] Justify every dependency; the default is none

Each dependency is justified, in the change that adds it, by something it does that would take
meaningfully longer to write and maintain than to depend on. Each adds an author who can compromise
the users, a constraint that can conflict with theirs, and an install for every consumer, and those
costs are permanent and shared.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-BUILD-12 | realises | [M] | |
| rust-style | RS-BUILD-18 | realises | [M] | |
| zig-style | ZS-BUILD-27 | realises | [M] | |

## What ships

### AS-BUILD-05 [M] Publish an allowlist of what ships, never a list of what is left out

A package is built from a list of what it contains. A list of exclusions publishes every file added
next until someone remembers it, a fixture directory or a credentials file among them, and a
published release cannot be taken back.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-BUILD-15 | realises | [M] | |
| rust-style | RS-BUILD-06 | realises | [M] | |
| zig-style | ZS-BUILD-11 | realises | [M] | |

## Continuous integration

### AS-BUILD-06 [M] Gate continuous integration on the formatter's check

A formatter is run by the tool, not by discipline, and the build fails on a file it would change.
Formatting has no right answer, so the only way to end the argument is to take the choice away, and
a formatter that runs sometimes puts its diff noise on whoever touches the file next.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-BUILD-19 | realises | [M] | |
| rust-style | RS-BUILD-26 | realises | [M] | |
| zig-style | ZS-BUILD-22 | realises | [M] | |

### AS-BUILD-07 [M] Pin every third-party CI action to a full commit, with its release as a comment

A workflow names each action it runs by the full identifier of one commit, with the release that
commit belongs to beside it for a reviewer to read, and takes the newest release at least seven days
old. A tag or a branch can be moved after review and the commit moves with it, so the action would
run someone else's code with the workflow's credentials.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-BUILD-20 | realises | [M] | |
| rust-style | RS-BUILD-46 | realises | [M] | |
| zig-style | ZS-BUILD-28 | realises | [M] | |
