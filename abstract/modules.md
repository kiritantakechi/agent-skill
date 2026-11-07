# Modules

Scope: how code is divided into modules and packages, what a boundary costs, how a project is laid
out on disk and how imports and the declarations of a file are ordered, the graph of dependencies
between modules, and the discipline that keeps a codebase's modules alike. What a module exports is
the API chapter's; what a module is called, beyond how long its name runs, is the naming chapter's.

## Contents

- **Dividing code into modules**
  - AS-MOD-01 [M] Give every module a documented concept
  - AS-MOD-02 [S] Split a module on a seam, not on its size
  - AS-MOD-03 [M] Count the encapsulation a boundary costs, not only what it buys
  - AS-MOD-04 [S] Keep a module's name to few words
- **Layout**
  - AS-MOD-05 [S] Keep the shipped source apart from tests, tools and examples
  - AS-MOD-06 [S] Name a directory for the module it roots
- **Imports and the graph**
  - AS-MOD-07 [M] Keep the dependency graph between modules acyclic
  - AS-MOD-08 [S] Group imports by origin, in one fixed order
  - AS-MOD-09 [M] Never import every name of a module at once
- **Order within a file**
  - AS-MOD-10 [S] Put a file's public surface before its details
  - AS-MOD-11 [S] Order the parts of a type in one fixed sequence
- **Orthogonality**
  - AS-MOD-12 [M] Give one concept one mechanism
  - AS-MOD-13 [S] Keep sibling modules structurally parallel
  - AS-MOD-14 [M] Absorb a special case into the general path, or give it its own type

---

## Dividing code into modules

### AS-MOD-01 [M] Give every module a documented concept

A module opens with a statement of what it holds, in a sentence that names its role and does not
list its members. A boundary whose sentence needs a conjunction has two concepts in it. The same
sentence tells the next contributor where new code goes.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-MOD-01 | realises | [M] | |
| rust-style | RS-MOD-01 | realises | [M] | |
| zig-style | ZS-MOD-01 | realises | [M] | |

### AS-MOD-02 [S] Split a module on a seam, not on its size

A module is divided when its contents fall into two groups with different callers or different
reasons to change, and each half can be named with a noun. Length alone is a symptom: a split made
on size yields modules named after nothing, and the reader then holds two files and the relation
between them.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-MOD-02 | realises | [S] | |
| rust-style | RS-MOD-03 | realises | [S] | |
| zig-style | ZS-MOD-02 | realises | [S] | |

### AS-MOD-03 [M] Count the encapsulation a boundary costs, not only what it buys

Dividing a module out turns whatever its siblings need from it into names every importer may depend
on. A seam that exposes a handful of names is a seam; one that exposes dozens is the wrong seam,
whatever audiences or settings are said to justify it. What the boundary makes public is counted
beside what it buys.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-MOD-03 | realises | [M] | |
| rust-style | RS-MOD-22 | realises | [M] | |
| zig-style | ZS-MOD-03 | realises | [M] | |

### AS-MOD-04 [S] Keep a module's name to few words

A name that needs many words usually names a module doing several things, so the name is reporting a
design problem. A module is named in a word or two, and one whose name will not shorten is split.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-MOD-04 | realises | [S] | |
| rust-style | RS-MOD-04 | realises | [S] | |
| zig-style | ZS-MOD-04 | realises | [S] | |

## Layout

### AS-MOD-05 [S] Keep the shipped source apart from tests, tools and examples

The source a project ships lives in one directory, and its tests, tools and examples live beside it
rather than inside it. A contributor finds the entry points and the library without reading
anything, and an integration test reaches the library the way a consumer does.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-MOD-05 | tightens | [M] | Python puts the working directory on the import path, so a package outside its own source directory lets the tests import the working copy and the packaging is never exercised; a Cargo or Zig test reaches the library by name |
| rust-style | RS-MOD-11 | realises | [S] | |
| zig-style | ZS-MOD-05 | realises | [S] | |

### AS-MOD-06 [S] Name a directory for the module it roots

A directory that holds a module's sources carries that module's name, so the name in the build, the
name in the import and the name on disk agree. One search then finds every mention of a module and a
rename is one operation; where the names differ, every reader keeps the mapping by hand.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-MOD-06 | tightens | [M] | A Python build backend finds the package by normalising the distribution name, so a mismatch fails the build outright; Cargo and Zig read the path from the manifest, where a difference costs only the reader |
| rust-style | RS-MOD-24 | realises | [S] | |
| zig-style | ZS-MOD-06 | realises | [S] | |

## Imports and the graph

### AS-MOD-07 [M] Keep the dependency graph between modules acyclic

Two modules that depend on each other are one module under two names, and merging them is the fix.
Kept directed, the graph lets each module be understood from the ones below it, and a change ripples
along a path a reader can follow instead of around a loop.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-MOD-09 | realises | [M] | |
| rust-style | RS-MOD-15 | realises | [M] | |
| zig-style | ZS-MOD-07 | realises | [M] | |

### AS-MOD-08 [S] Group imports by origin, in one fixed order

Imports are written in groups, ordered from the most general origin to the most local and separated
from one another, so a reader sees at a glance how much of a file's vocabulary is foreign and where
a name came from. Where a tool fixes the order, the order is that tool's.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | `I001` | decided | | Ruff's import-sorting rule rejects imports out of the standard library, third party and local grouping, so the standard states no rule of its own |
| rust-style | RS-MOD-27 | realises | [S] | |
| zig-style | ZS-MOD-09 | realises | [S] | |

### AS-MOD-09 [M] Never import every name of a module at once

An import names what it takes. A wholesale import makes the importing file's names depend on
whatever the other module defines next, hides where a name came from, and turns an addition there
into a collision here.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | `F403` | decided | | Ruff rejects a star import outright, so the standard states no rule of its own |
| rust-style | `wildcard_imports` | decided | | Clippy rejects a glob import outside a test module and a prelude, so the standard states no rule of its own |
| zig-style | | absent | | Zig has no wholesale import: a declaration is reached through the namespace it was imported as, and `usingnamespace`, the one construct that re-exported a namespace's names, no longer exists |

## Order within a file

### AS-MOD-10 [S] Put a file's public surface before its details

A file is read from the top, so its entry point and the names its callers use come first and the
helpers they rely on follow. Order carries no meaning to the compiler, which makes it free for the
reader, and a private helper first makes the reader take in the implementation before the interface.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-MOD-10 | realises | [S] | |
| rust-style | RS-MOD-32 | realises | [S] | |
| zig-style | ZS-MOD-10 | realises | [S] | |

### AS-MOD-11 [S] Order the parts of a type in one fixed sequence

The data a type holds comes first, then how it is constructed, then its public operations, then its
private ones. Everything below derives from what is above it, so a reader who rebuilds the
invariants reads top-down, and a reviewer knows where to look.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-MOD-11 | realises | [S] | |
| rust-style | RS-MOD-33 | realises | [S] | |
| zig-style | ZS-MOD-11 | realises | [S] | |

## Orthogonality

### AS-MOD-12 [M] Give one concept one mechanism

A project configures itself one way, reports progress one way and starts work one way. Two
mechanisms for one concept mean that every future change must choose between them and every reader
must learn both, and the second is usually added for one inconvenience and then multiplies the
states a maintainer has to hold.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-MOD-12 | realises | [M] | |
| rust-style | RS-MOD-36 | realises | [M] | |
| zig-style | ZS-MOD-12 | realises | [M] | |

### AS-MOD-13 [S] Keep sibling modules structurally parallel

Modules at one level of the tree have the same internal shape, or the difference is explained. A
reader who has learned one navigates the next without reading it, and a missing piece shows as a
hole in the pattern instead of an absence nobody notices.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-MOD-13 | realises | [S] | |
| rust-style | RS-MOD-38 | realises | [S] | |
| zig-style | ZS-MOD-13 | realises | [S] | |

### AS-MOD-14 [M] Absorb a special case into the general path, or give it its own type

A branch that exists for one input is an unfinished generalisation. Either the general path handles
that input, usually by widening a parameter or adding a variant, or the case differs enough to
deserve its own type and its own function. Left as a branch, it compounds: every later change must
be checked against it.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-MOD-14 | realises | [M] | |
| rust-style | RS-MOD-37 | realises | [M] | |
| zig-style | ZS-MOD-14 | realises | [M] | |
