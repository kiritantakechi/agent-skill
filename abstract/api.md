# API

Scope: the surface a unit offers its callers: what it makes public and where that is decided, how
its signatures are shaped, which pairs and siblings it keeps alike, where it applies an effect, and
how it evolves without breaking them. What a caller sees of a failure is the errors chapter's; how a
value is shaped is the data chapter's.

## Contents

- **The public surface**
  - AS-API-01 [M] Keep everything private until a caller needs it
  - AS-API-02 [M] Decide the public surface in one place
  - AS-API-03 [M] Enumerate every name the surface exports; never export by wildcard
- **Signatures**
  - AS-API-04 [M] Accept the most general input and return the most specific output
  - AS-API-05 [M] Never leave two adjacent parameters a caller could transpose
  - AS-API-06 [M] Never take a flag that selects between two behaviours
  - AS-API-07 [M] State who owns what a function returns
- **Symmetry**
  - AS-API-08 [M] Give every operation its inverse, or document why there is none
  - AS-API-09 [M] Keep argument order identical across sibling functions
  - AS-API-10 [M] Give sibling failures a uniform shape
- **Evolution**
  - AS-API-11 [M] Deprecate before removing, and say what to use instead
- **Effects**
  - AS-API-12 [M] Return the change from a function, and apply it in one place

---

## The public surface

### AS-API-01 [M] Keep everything private until a caller needs it

A name starts out private and becomes public when a caller outside its unit needs it. Every public
name is a promise that cannot be withdrawn without breaking someone, while a private one can be
promoted the day it is wanted, so the surface is grown on demand and never trimmed back.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-API-05 | realises | [M] | |
| rust-style | RS-API-01 | realises | [M] | |
| zig-style | ZS-API-01 | realises | [M] | |

### AS-API-02 [M] Decide the public surface in one place

The names a package offers are chosen in a single file, one reviewable list that every addition has
to edit. Where a name is defined and where a caller finds it are then two different things, so a
definition can move without breaking anyone and a new file cannot widen the surface by existing.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-API-03 | realises | [M] | |
| rust-style | RS-API-04 | realises | [M] | |
| zig-style | ZS-API-02 | realises | [M] | |

### AS-API-03 [M] Enumerate every name the surface exports; never export by wildcard

The surface is a list of names, each written out. An export that takes whatever a module happens to
define publishes the next internal addition by accident, and turns a typo into a compatibility
promise.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-API-01 | realises | [M] | |
| rust-style | RS-API-06 | realises | [M] | |
| zig-style | | absent | | Zig has no wildcard export: a declaration is public by its own marker and reaches a caller through the root file's explicit re-export, and the one construct that re-exported a whole namespace no longer exists |

## Signatures

### AS-API-04 [M] Accept the most general input and return the most specific output

A parameter asks no more of the caller than the function uses, so that anything which can serve is
accepted. A return gives the caller everything the function built. The two want opposite generality,
because the author knows what was made and the caller knows only what they hold.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-API-09 | realises | [M] | |
| rust-style | RS-API-15 | realises | [M] | |
| zig-style | ZS-API-06 | realises | [M] | |

### AS-API-05 [M] Never leave two adjacent parameters a caller could transpose

Two arguments of one type can be written in the wrong order, and the call still compiles and
produces a plausible wrong answer. Each such parameter is named at the call site or given a type of
its own, so that swapping them is an error rather than a bug found in production.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-API-08 | realises | [M] | |
| rust-style | RS-API-18 | realises | [M] | |
| zig-style | ZS-API-04 | realises | [M] | |

### AS-API-06 [M] Never take a flag that selects between two behaviours

A parameter that chooses which of two things a function does means two functions share one name and
one body. Splitting them gives each an honest name and a precise signature, and spares every caller
the cases its mode cannot produce. A setting that is data, and not a choice of behaviour, stays a
parameter.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-API-10 | realises | [M] | |
| rust-style | RS-API-24 | realises | [M] | |
| zig-style | ZS-API-03 | realises | [M] | |

### AS-API-07 [M] State who owns what a function returns

The caller is told whether what comes back is a borrowed view that stops being valid, a copy it may
keep, or a resource it must release. The signature of the call cannot always show it, and a caller
who guesses wrong either corrupts a view or leaks a resource.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-API-14 | realises | [M] | |
| rust-style | | absent | | A Rust signature states it: an owned return transfers ownership and a reference borrows, and the compiler checks the claim, so there is no sentence left for the author to owe |
| zig-style | ZS-API-05 | realises | [M] | |

## Symmetry

### AS-API-08 [M] Give every operation its inverse, or document why there is none

A caller who learns one half of a pair looks for the other. Where the other half is missing on
purpose, because the operation loses information, consumes its handle or belongs to another type,
the absence is stated; silence reads as an oversight and is worked around.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-API-17 | realises | [M] | |
| rust-style | RS-API-53 | realises | [M] | |
| zig-style | ZS-API-08 | realises | [M] | |

### AS-API-09 [M] Keep argument order identical across sibling functions

Functions that do comparable work take their arguments in one order, fixed once for the package.
Siblings are called from the same code and the reader generalises from the first one learned, so a
disagreement among them is a swapped argument that no check catches.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-API-18 | realises | [M] | |
| rust-style | RS-API-54 | realises | [M] | |
| zig-style | ZS-API-09 | realises | [M] | |

### AS-API-10 [M] Give sibling failures a uniform shape

The failures one unit reports carry comparable context: if one records where it happened, the others
do too. The caller writes one handler over the whole family, and every member that lacks a field
makes that handler grow a special case.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-API-19 | realises | [M] | |
| rust-style | RS-API-55 | realises | [M] | |
| zig-style | ZS-API-10 | realises | [M] | |

## Evolution

### AS-API-11 [M] Deprecate before removing, and say what to use instead

A public name that is going away stays for at least one release, marked as deprecated, with the
replacement named in the notice. A caller learns of the change while it is still a warning to act
on, and not as a build that no longer compiles.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-API-15 | realises | [M] | |
| rust-style | RS-API-51 | realises | [M] | |
| zig-style | ZS-API-11 | realises | [M] | |

## Effects

### AS-API-12 [M] Return the change from a function, and apply it in one place

A function that derives a result returns it as a value and does not also perform an effect. What
should change is computed by the pure part, and one caller applies it, at the edge where the value
meets its sink or its state. The pure part is tested without the effect, and the one place that
applies it is where an invariant is checked and a failure is made all-or-nothing.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-API-12 | realises | [M] | |
| rust-style | RS-API-19 | realises | [M] | |
| zig-style | ZS-API-07 | realises | [M] | |
