# Data

Scope: how a value is shaped: the type that carries a fact and the alternatives it lists, what it
refuses to hold, how it is compared and handed out, and the width and arithmetic of a number. What a
unit exposes is the API chapter's; how a type is spelled and checked is the types chapter's.

## Contents

- **The shape of a value**
  - AS-DATA-01 [M] Model a set of alternatives as one type that lists them
  - AS-DATA-02 [M] Give a value with a unit, a domain or a validity condition a type of its own
  - AS-DATA-03 [S] Prefer a record with named fields to a tuple whose elements could be swapped
  - AS-DATA-04 [S] Refer to a long-lived element by a handle into its container, not by a pointer
- **Validity**
  - AS-DATA-05 [M] Make an invalid state unrepresentable before checking against it
  - AS-DATA-06 [M] Refuse an invalid value where it is built; never correct it
  - AS-DATA-07 [M] Hand out a view of state, never the container or a mutable handle on it
- **Equality**
  - AS-DATA-08 [M] Never let equality and hashing disagree
- **Numbers**
  - AS-DATA-09 [M] Give an integer that is stored or sent a width of its own, never the platform's
  - AS-DATA-10 [M!] Choose the overflow behaviour of arithmetic on untrusted values

---

## The shape of a value

### AS-DATA-01 [M] Model a set of alternatives as one type that lists them

A set of states, kinds or variants is one type with a member for each, and a member that carries its
own data carries it inside that member. A tag beside fields that are meaningful for some tags only,
a string, an integer with named constants, or a group of flags each admits combinations the set
never had, and leaves every reader to learn which are real. The type that lists them lets the
compiler prove every member handled and turns a new member into an error at each site that must
change.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-DATA-03 | realises | [M] | |
| rust-style | RS-DATA-01 | realises | [M] | |
| zig-style | ZS-DATA-24 | realises | [M] | |

### AS-DATA-02 [M] Give a value with a unit, a domain or a validity condition a type of its own

An identifier, an amount in a unit, an offset in one space of indices, or any value constrained in
prose is not a bare number or string. Its own type makes passing one where another belongs an error
the compiler reports, where a swap of two plain numbers yields a plausible wrong answer found in
production, and the constraint is checked once, at the boundary, and not by every reader.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-DATA-15 | realises | [M] | |
| rust-style | RS-DATA-02 | realises | [M] | |
| zig-style | ZS-DATA-04 | overrides | [S] | Zig has no operator overloading and no cheap distinct integer, so a wrapper type loses the arithmetic its value would keep elsewhere; the role and unit travel in the name, and a handle gets a type of its own only where it is stored |

### AS-DATA-03 [S] Prefer a record with named fields to a tuple whose elements could be swapped

A result of several parts is a record whose fields have names, unless the parts are genuinely a
sequence whose position is their meaning. Two elements of one type can be exchanged and the code
still compiles, and a position says nothing to the next reader. A new field is an addition to the
record, where a new element changes the shape at every site that unpacks it.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-DATA-05 | realises | [S] | |
| rust-style | RS-DATA-03 | realises | [S] | |
| zig-style | ZS-DATA-29 | realises | [S] | |

### AS-DATA-04 [S] Refer to a long-lived element by a handle into its container, not by a pointer

An element that lives as long as its container and is referred to from elsewhere is named by an
index or an identifier that is resolved through the container at each use. A pointer to an element
is invalidated when the container grows or moves, and ties the holder to the storage; a handle
survives that, is smaller, can be stored and sent, and makes the absence of an element a value of
its own.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | | absent | | Python holds a reference that the garbage collector keeps alive, so no growth of a container invalidates one and no handle is needed to survive it |
| rust-style | RS-DATA-04 | realises | [S] | |
| zig-style | ZS-DATA-21 | realises | [S] | |

## Validity

### AS-DATA-05 [M] Make an invalid state unrepresentable before checking against it

The earliest defence against a bad value is a type that cannot hold it; the next is a construction
that refuses it; a check at the point of use comes last. Each later step costs more, is repeated at
every site, and can be forgotten at any of them, while a state the type excludes is a branch never
written and a test never needed.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-DATA-14 | realises | [M] | |
| rust-style | RS-DATA-05 | realises | [M] | |
| zig-style | ZS-DATA-30 | realises | [M] | |

### AS-DATA-06 [M] Refuse an invalid value where it is built; never correct it

The code that builds a value with an invariant checks the invariant on every path that builds one,
and reports a failure when it does not hold. Clamping, coercing or substituting a default hides the
caller's mistake and leaves them reasoning about a value other than the one they passed, while a
refusal names the place that made it.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-DATA-13 | realises | [M] | |
| rust-style | RS-DATA-06 | realises | [M] | |
| zig-style | ZS-DATA-31 | realises | [M] | |

### AS-DATA-07 [M] Hand out a view of state, never the container or a mutable handle on it

What a unit returns of its own state is something the caller can read and cannot use to change that
state: a copy, or a read-only view, and never the container the unit keeps or a handle that can
write to it. A writable handle is a licence to break every invariant the unit maintains, which no
documentation prevents, and a view lets the representation change without touching a caller.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-DATA-10 | realises | [M] | |
| rust-style | RS-DATA-07 | realises | [M] | |
| zig-style | ZS-DATA-32 | realises | [M] | |

## Equality

### AS-DATA-08 [M] Never let equality and hashing disagree

Two values that compare equal produce the same hash. A lookup by hash finds a bucket first and
compares second, so an equal pair with different hashes lands in different buckets and the lookup
misses, silently and only for some keys.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-DATA-16 | realises | [M] | |
| rust-style | RS-DATA-08 | realises | [M] | |
| zig-style | ZS-DATA-33 | realises | [M] | |

## Numbers

### AS-DATA-09 [M] Give an integer that is stored or sent a width of its own, never the platform's

A number written to a file, put on a wire or shared with another program has a width, and an
endianness where it matters, fixed by the format. The width of a machine word differs between
targets, so the same program built for two of them cannot read its own files. The platform's width
is for lengths and indices held in memory.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | | absent | | A Python integer has no width: it grows to hold its value, and the width of a stored number is chosen by the serialisation, not by a type |
| rust-style | RS-DATA-09 | extends | [M] | It also requires a checked conversion wherever a narrowing would silently lose bits |
| zig-style | ZS-DATA-02 | realises | [M] | |

### AS-DATA-10 [M!] Choose the overflow behaviour of arithmetic on untrusted values

Arithmetic on a value that comes from outside the program, or on a size computed from one, does not
take the behaviour the build happens to give. It is checked and fails as an error the caller
handles, saturates, or wraps, each chosen on purpose, because an unchosen overflow differs between
builds and ends as a silent wrong answer that becomes a bounds error a few lines later. Where the
bound is proven inside the program, it is asserted instead. Scripts and code that trusts its input
relax this.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | | absent | | A Python integer never overflows, so arithmetic on an untrusted value has no behaviour to choose |
| rust-style | RS-DATA-10 | realises | [M!] | |
| zig-style | ZS-DATA-10 | realises | [M!] | |
