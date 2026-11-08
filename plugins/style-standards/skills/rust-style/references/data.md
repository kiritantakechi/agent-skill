# Data

Scope: how a value is shaped: the type that carries a fact, what an instance may be, what its
equality means, and the width and arithmetic of a number. A finite set of states is an enum, a type
refuses the values it cannot hold, an accessor hands out a view of its state and never the state
itself, and an integer is as wide as the fact it carries. The surface a type offers and its
constructors are the API chapter's; a lifetime or a pointer is the ownership chapter's; a trait impl
is the traits chapter's.

## Contents

- **Shape of a value**
  - RS-DATA-01 [M] Model a finite set of states as an enum that lists all of them
  - RS-DATA-02 [M] Newtype anything with a unit, a domain, or a validity condition
  - RS-DATA-03 [S] Prefer a struct to a tuple whose elements could be swapped
  - RS-DATA-04 [S] Prefer indices to references for graph-shaped data
- **Validity**
  - RS-DATA-05 [M] Make a bad value unrepresentable, else rejected at construction, else checked
  - RS-DATA-06 [M] Close every public path that can build an invalid instance
  - RS-DATA-07 [M] Return the view from an accessor, never the container
- **Equality**
  - RS-DATA-08 [M] Keep `PartialEq`, `Eq`, `Hash`, and `Ord` consistent
- **Numbers**
  - RS-DATA-09 [M] Choose integer widths deliberately and convert with `try_from`
  - RS-DATA-10 [M!] Make overflow behaviour explicit on untrusted arithmetic and computed sizes

---

## Shape of a value

### RS-DATA-01 [M] Model a finite set of states as an enum that lists all of them

Protocol phases, parser modes, retry outcomes, file kinds. Not an integer with named constants, not
a string tag, not a group of booleans. Fields that only make sense together are the same rule: two
`Option`s where exactly one is always `Some`, or a `bool` plus a field meaningful only when it is
set, are the sum type they already are, each variant carrying its own data.

**Why:** an enum closes the set, so `match` proves every state handled and a new state breaks every
incomplete site. An integer admits values the set never had, a string admits typos, *n* booleans
admit 2ⁿ combinations, and correlated fields leave an impossible one (RS-ERR-24) to every path.

**Check:** for each state-like value, can you name a representable value that is not a legal state?
Then the type is wrong. Count the booleans that travel together — three of them is eight states, and
you meant three — and for each pair of fields, ask whether some combination of their values cannot
legally occur; that pair is an enum.

```rust
// verified
/// The set is closed, so `match` proves every phase is handled.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Phase {
    Handshake,
    Streaming,
    Draining,
    Closed,
}

impl Phase {
    #[must_use]
    pub fn accepts_writes(self) -> bool {
        matches!(self, Self::Handshake | Self::Streaming)
    }
}
```

### RS-DATA-02 [M] Newtype anything with a unit, a domain, or a validity condition

`UserId(u64)`, `Bytes(u64)`, `Utf8Path`; `Duration` rather than `timeout_ms: u64`. Where a newtype
would be disproportionate — a private helper, a single call site — the unit goes in the name
(RS-NAME-08); never omit both. Indices into different spaces are types of their own, `NodeId`,
`EdgeId`, `ByteOffset`, `CharOffset`: mixing byte and char offsets is the classic Unicode bug. Two
adjacent parameters of one primitive type are the commonest case (RS-API-18). A constraint stated in
prose ("must be non-empty", "in the range 1..=100") is a validity condition whose type, such as
`NonEmpty<T>`, has not been written yet.

**Why:** the compiler then catches a value passed where another belongs, which tests usually do not,
because a swapped pair of `u64`s produces plausible wrong answers. A constraint in a type is checked
once, at the boundary; one in prose is re-checked by every reader.

**Check:** read every public signature, and its doc comment, for "must", "should be", "expects" and
range notation; each such phrase is a type or a `# Panics` section you owe (RS-DOC-10). For the rest
of the primitive-typed fields and parameters, is a different value of the same type nonsense here?
Does the crate hold more than one `Vec` indexed by `usize`? Those are distinct types.

```rust
// verified
/// Illegal states are unrepresentable: there is no way to build an empty selection.
#[derive(Debug, Clone)]
pub struct Selection {
    first: String,
    rest: Vec<String>,
}

impl Selection {
    #[must_use]
    pub fn new(first: String) -> Self {
        Self {
            first,
            rest: Vec::new(),
        }
    }

    /// Never zero: the type cannot represent an empty selection, so there is no `is_empty`.
    #[must_use]
    pub fn count(&self) -> usize {
        1 + self.rest.len()
    }
}
```

### RS-DATA-03 [S] Prefer a struct to a tuple whose elements could be swapped

**Why:** `(usize, usize, bool)` is unreadable and silently transposable, since
`let (start, end, empty) = m;` compiles just as well with the first two swapped. Named accessors
cannot be misread, and a fourth piece of information is one more method, not a changed arity.

**Check:** does any public function return a tuple of three or more elements, or a pair whose two
elements share a type? Each is a struct with named fields.

### RS-DATA-04 [S] Prefer indices to references for graph-shaped data

`Vec<Node>` plus `NodeId(u32)`.

**Why:** it sidesteps lifetimes entirely, it is cache-friendly, it serializes trivially, and it
makes cycles representable without `Weak`. Newtype the index so it cannot be confused with a length
or with an index into a different arena (RS-DATA-02).

**Check:** does the graph type have a lifetime parameter? Indices remove it.

```rust
// verified
/// Index newtypes instead of pointers: one allocation, and the graph stays `Send`.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct NodeId(u32);

#[derive(Debug, Default)]
pub struct Tree {
    nodes: Vec<Node>,
}

#[derive(Debug)]
struct Node {
    parent: Option<NodeId>,
}

impl Tree {
    pub fn push(&mut self, parent: Option<NodeId>) -> NodeId {
        let id = NodeId(u32::try_from(self.nodes.len()).unwrap_or(u32::MAX));
        self.nodes.push(Node { parent });
        id
    }

    #[must_use]
    pub fn parent(&self, NodeId(index): NodeId) -> Option<NodeId> {
        self.nodes.get(index as usize).and_then(|node| node.parent)
    }
}
```

## Validity

### RS-DATA-05 [M] Make a bad value unrepresentable, else rejected at construction, else checked

Three tiers, in order: the type cannot express the bad value; the constructor refuses it; a runtime
check catches it. Reach for the earliest tier the situation allows.

**Why:** each tier costs more than the last: unrepresentable costs nothing and cannot be forgotten,
rejection costs one check per value, and a runtime check costs one per use at every site. A later
tier leaves defensive branches nobody can prove unreachable, so none is ever deleted.

**Check:** for each validation in the body of a function, ask which tier it belongs to and whether
an earlier tier was available. A check that could have been a `NonZeroUsize` is a defect
(RS-API-27).

```rust
// verified
use std::num::NonZeroU16;

/// Tier one: zero is not representable, so no check is written anywhere.
#[derive(Debug, Clone, Copy)]
pub struct Chunking {
    size: NonZeroU16,
}

impl Chunking {
    #[must_use]
    pub fn new(size: NonZeroU16) -> Self {
        Self { size }
    }

    #[must_use]
    pub fn chunks_for(self, total: usize) -> usize {
        total.div_ceil(usize::from(self.size.get()))
    }
}
```

### RS-DATA-06 [M] Close every public path that can build an invalid instance

Every public path enforces the invariants; a builder is the usual one to miss: if the built type can
also be made by a struct literal or a `From<Options>`, every invariant `build()` enforces is
unenforced on the other path.

**Why:** private fields plus a constructor that takes every field unvalidated is not encapsulation —
it is public fields with extra typing. The point is that the type cannot be constructed in a bad
state, not that the fields have a keyword in front of them.

**Check:** can a caller reach an invalid instance through any public path — a constructor, a setter,
a `Deserialize` impl, a `Default`, a `From<Options>` that skips `build()`? `serde` in particular
bypasses your constructor unless you use `#[serde(try_from = "…")]`.

### RS-DATA-07 [M] Return the view from an accessor, never the container

`fn buffer(&self) -> &[u8]`, never `fn buffer(&self) -> &Vec<u8>`. Nor hand out `&mut` to
invariant-bearing state, as in `fn entries_mut(&mut self) -> &mut Vec<Entry>`, which lets a caller
violate sorting, uniqueness, or a cached length: one `&mut self` method that performs the whole
transition keeps the type consistent between calls.

**Why:** an accessor returning `&Vec<u8>` publishes `Vec` as a public field would, so a switch to a
ring buffer still breaks every caller; `&[u8]` names what the caller may do. A raw `&mut` is a
licence to break every invariant, which targeted mutators (`insert`, `remove`) can maintain.

**Check:** `rg -n 'fn \w+\(&self\) -> &(Vec<|String\b|PathBuf\b)' -g '*.rs'` finds an accessor
returning the container; each hit is the finding — the slice, `&str` and `&Path` say the same thing
without naming it. A map or a set has no borrowed view in std, so the answer there is not a
different return type but a smaller question: `get`, `contains`, or an iterator (RS-API-22). For
each `&mut`-returning accessor, ask what invariant a caller could break with it; if the answer is
"none", the accessor is still wrong, since the operation the caller came for is the thing to hand
out, not the collection it would have reached through.

## Equality

### RS-DATA-08 [M] Keep `PartialEq`, `Eq`, `Hash`, and `Ord` consistent

Equal values must hash equally; `Ord` must agree with `PartialOrd` and `Eq`.

**Why:** inconsistency fails silently and far from the impl: a `HashMap` misses a key looked up by
an equal one, a `BTreeMap` loses entries, `BTreeMap::append` may panic, and a derived `PartialOrd`
beside a derived `Ord` answers with `cmp`, not with each field's `partial_cmp`.

**Check:** if you hand-implement one of the four, review all four in the same commit. Property-test
the laws (RS-TEST-21).

```rust
// verified
use std::cmp::Ordering;

/// `Ord` agrees with `PartialEq`: equal values compare `Equal`, and both use the same fields.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Priority {
    weight: u32,
    tiebreak: u32,
}

impl Ord for Priority {
    fn cmp(&self, other: &Self) -> Ordering {
        self.weight
            .cmp(&other.weight)
            .then(self.tiebreak.cmp(&other.tiebreak))
    }
}

impl PartialOrd for Priority {
    fn partial_cmp(&self, other: &Self) -> Option<Ordering> {
        Some(self.cmp(other))
    }
}
```

## Numbers

### RS-DATA-09 [M] Choose integer widths deliberately and convert with `try_from`

Prefer `u32`/`u64` deliberately over `usize` for values that are serialized or bounded, and `usize`
for lengths and indices. Casting with `as` truncates silently — use `try_from` on any conversion
that could lose data. A same-width sign change loses no bits and is not a `try_from` case: spell it
`cast_signed()` or `cast_unsigned()` rather than `as`.

**Why:** `usize` varies by platform, so a serialized `usize` has a different width on a 32-bit
target — a portability bug that only appears there. `as` truncates at run time without any error,
which is why it is the wrong default for narrowing.

**Check:** is `as u32`, `as usize` or `as i32` applied to a value that could exceed the target
range? Each wants `try_from`; the `cast_*` rows below flag the casts that can lose data.

```rust
// verified
/// `try_from` on any narrowing conversion; `as` would truncate silently.
///
/// # Errors
/// Returns the conversion error when `len` exceeds `u32::MAX`.
pub fn header_len(len: usize) -> Result<u32, std::num::TryFromIntError> {
    u32::try_from(len)
}
```

### RS-DATA-10 [M!] Make overflow behaviour explicit on untrusted arithmetic and computed sizes

Integer overflow panics in debug and wraps in release, by default. On untrusted values and on sizes
computed from the input — lengths, offsets, parsed numbers — choose the behaviour: `checked_*`,
`saturating_*`, `wrapping_*`, or `strict_*`, which panics in both profiles where overflow is a bug
rather than an input. A value with a proven internal bound, such as a counter over a fixed array,
asserts that bound instead.

*Relaxed form:* the default behaviour, with a `debug_assert!` of each bound the arithmetic assumes.

**Why:** that is a correctness fork: debug and release are two different programs on the same input.
On attacker-influenced values the release behaviour is a silent wrong answer that frequently becomes
a bounds bug two lines later.

**Check:** for each arithmetic on lengths, offsets, and parsed numbers, can either operand originate
outside the process, or grow with the input? If yes, it must be one of the four, chosen
deliberately, not whichever compiles.

```rust
// verified
/// On untrusted sizes the behaviour must not depend on the build profile.
#[must_use]
pub fn total_len(parts: &[usize]) -> Option<usize> {
    parts
        .iter()
        .try_fold(0_usize, |acc, &part| acc.checked_add(part))
}
```
