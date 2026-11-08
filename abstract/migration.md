# Migration

Scope: moving code to the target release: the spellings it removed, changed or deprecated, and what
replaces each. How a project pins the release it moves to is the build chapter's.

## Contents

- **Finding the old spellings**
  - AS-MIG-01 [M] Search the whole tree for the old spellings, including code no build or test reaches
  - AS-MIG-02 [M!] Fail the build on a hit of that search
- **Deprecated names**
  - AS-MIG-03 [M] Do not call an API the target has deprecated
- **Moving the toolchain**
  - AS-MIG-04 [M] Review every toolchain bump against the release's own list of changes

---

## Finding the old spellings

### AS-MIG-01 [M] Search the whole tree for the old spellings, including code no build or test reaches

Each standard generates a search from its table of old spellings, and the search is run over the
whole tree, before the diff is read. A removed name fails only where the code is reached, and a
build or a test analyses only part of a tree: a branch for a target that is not built, a function
nothing calls, a module nothing imports. The name waits there for the first caller, often on another
platform and long after the migration. A search over the text does not depend on what ran.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-MIG-02 | realises | [M] | |
| rust-style | RS-MIG-01 | realises | [M] | |
| zig-style | ZS-MIG-02 | realises | [M] | |

### AS-MIG-02 [M!] Fail the build on a hit of that search

A spelling the target still accepts, and accepts silently, never fails a build, so it accumulates
until an upgrade removes every one at once and the diff is too large to review. A step in the
continuous-integration workflow that runs the generated search and fails on a hit turns that
migration into a cost of each change. The relaxed form is the same search run by hand before each
release.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-MIG-03 | realises | [M!] | |
| rust-style | RS-MIG-02 | realises | [M!] | |
| zig-style | ZS-MIG-03 | realises | [M!] | |

## Deprecated names

### AS-MIG-03 [M] Do not call an API the target has deprecated

A deprecated API still works, and warns, and a release removes it. The table of old spellings marks
each such name with its replacement, and code written now uses the replacement. A deprecation that
the build turns into an error breaks it on a toolchain bump, in code nobody changed.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-MIG-06 | realises | [M] | |
| rust-style | RS-MIG-04 | realises | [M] | |
| zig-style | ZS-MIG-01 | realises | [M] | |

## Moving the toolchain

### AS-MIG-04 [M] Review every toolchain bump against the release's own list of changes

A table of old spellings is a snapshot, and a release keeps adding to its list of removals and
changes after the snapshot was taken. Moving the toolchain is therefore reviewed against that list:
the removals are added to the table, and the changes that compile before and after and behave
differently are read against the code, because nothing fails when they take effect.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-MIG-09 | realises | [M] | |
| rust-style | RS-MIG-05 | realises | [M] | |
| zig-style | ZS-MIG-04 | realises | [M] | |
