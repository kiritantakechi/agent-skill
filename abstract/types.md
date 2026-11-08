# Types

Scope: how a type states what a seam needs and what a set lists: the interface named before what
provides it, a closed set kept closed and handled in full, and the contract and reach of a generic
parameter. How a value is shaped is the data chapter's; what a public signature accepts and returns
is the API chapter's; how a language spells a type or which checker it runs is its own standard's.

## Contents

- **Interfaces and closed sets**
  - AS-TYPE-01 [M] Name the capability a seam needs as an interface type before writing what provides it
  - AS-TYPE-02 [M] Model a closed set of implementations as a sum type, not an interface
  - AS-TYPE-03 [M] Handle a closed set exhaustively and add no catch-all arm
- **Generics**
  - AS-TYPE-04 [M] Document the contract of a generic parameter that its signature cannot state
  - AS-TYPE-05 [S] Make a parameter generic only where callers use the flexibility

---

## Interfaces and closed sets

### AS-TYPE-01 [M] Name the capability a seam needs as an interface type before writing what provides it

At a seam that will carry two plausible implementations, or a test double, the interface is written
first, in terms of what the caller needs, and the consumer is written against it and not against the
first thing that provides it. A boundary extracted from an existing type inherits its accidents, its
error cases, its argument order and its assumption that a handle is always there; one designed
against the caller's need comes out total and symmetric, and the test double costs nothing because
the seam exists. A type with one implementation and no double stays concrete.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-TYPE-21 | realises | [M] | |
| rust-style | RS-TYPE-01 | realises | [M] | |
| zig-style | ZS-TYPE-01 | realises | [M] | |

### AS-TYPE-02 [M] Model a closed set of implementations as a sum type, not an interface

When every implementation is known and lives in the same tree, the set is one type that lists its
members and a function that handles each, not an interface with dynamic dispatch. An interface is
open: the compiler can never prove every implementation handled, the value cannot carry the derived
behaviour of a plain record, and a new implementation is silent wherever the set is consumed. The
sum type pays nothing for an extensibility a closed set does not want. An interface stays for the
set that someone else extends.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-TYPE-22 | realises | [M] | |
| rust-style | RS-TYPE-02 | realises | [M] | |
| zig-style | ZS-TYPE-02 | realises | [M] | |

### AS-TYPE-03 [M] Handle a closed set exhaustively and add no catch-all arm

A multi-way branch over a closed set names every member and has no arm for the rest. A catch-all
converts the error that a new member would raise at every site that must change into a silent
fallthrough at run time, and so checks nothing. Where the set is open to values from outside, the
arm that covers them is written so that a named member left out is still an error.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-TYPE-14 | realises | [M] | |
| rust-style | `wildcard_enum_match_arm` | decided | | Clippy warns on a `_` arm over an enum of this crate, so the standard states no rule of its own |
| zig-style | ZS-TYPE-03 | realises | [M] | |

## Generics

### AS-TYPE-04 [M] Document the contract of a generic parameter that its signature cannot state

A parameter whose type the caller supplies, an implementation of an interface or a value of any type
that has the right shape, is constrained by its signature in types only. What an implementation must
uphold, what a caller may assume, whether calls may overlap and what happens on error go where the
caller reads, since otherwise the contract can be met only by accident. Where the language checks no
shape at all, the requirement is stated for the one who passes the argument as well.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-TYPE-23 | realises | [M] | |
| rust-style | RS-TYPE-03 | realises | [M] | |
| zig-style | ZS-TYPE-04 | extends | [M] | The parameter carries no signature contract at all, so the rule also requires a compile-time check that names the requirement and the offending type |

### AS-TYPE-05 [S] Make a parameter generic only where callers use the flexibility

A type parameter, a bound or an open type is paid for by every caller and every reader: a name to
track, an inference to make and a message that names an abstraction. It earns its place when callers
hold several different types or when it ties one position in a signature to another. Otherwise the
concrete type is the signature, checked at the call site and shown in the documentation.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-TYPE-24 | realises | [S] | |
| rust-style | RS-TYPE-04 | realises | [S] | |
| zig-style | ZS-TYPE-05 | realises | [S] | |
