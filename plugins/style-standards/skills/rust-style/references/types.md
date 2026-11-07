# Types

Scope: how a type states what a seam needs and what a set lists: the capability named as a trait
before the type that provides it, a closed set kept an enum, the contract of a trait written down,
and how far a parameter is generic. How a trait is shaped, dispatched, bounded and sealed is the
traits chapter's; how a value is shaped is the data chapter's; what a public signature accepts is
the API chapter's.

The discipline here is **trait-first** at every seam that will carry two plausible implementations
or a test double: name the capability as a trait before writing the type that provides it, and
program against the trait rather than the concrete type. Where there is one implementation and no
double, the concrete type is the design, and where the set is closed the design is an enum.

The Rust API Guidelines and the BurntSushi crates advise the opposite — extract a trait only once a
second implementation exists. Trait-first buys a boundary that is total and symmetric because no
concrete type shaped it, and costs indirection, extra rustdoc, and a generic parameter at use sites
a concrete struct would not need. RS-TRAIT-01 and RS-TRAIT-41 keep that cost from becoming damage:
if either is being bent to make a trait fit, the fallback is a concrete type, not a partial impl.

## Contents

- **Interfaces and closed sets**
  - RS-TYPE-01 [M] Name the capability as a trait before writing the type that provides it
  - RS-TYPE-02 [M] Model a closed set of implementations as an enum, not a trait object
- **Generics**
  - RS-TYPE-03 [M] Document the trait's contract, not just its signatures
  - RS-TYPE-04 [S] Genericize a parameter only where the flexibility is used
- Decided by tools

---

## Interfaces and closed sets

### RS-TYPE-01 [M] Name the capability as a trait before writing the type that provides it

At a seam that will carry two plausible implementations, or a test double, write the trait first, in
terms of what a caller needs, then implement it. Program against the trait — take `impl Read`, not
`File` — so the first implementation is never privileged. A type with one implementation and no
double stays concrete (RS-TYPE-04), and a closed set is an enum (RS-TYPE-02).

**Why:** a boundary extracted from an existing type inherits its accidents: its error cases, its
argument order, its assumption that a handle is always available. Designed against the caller's
need, it comes out total and symmetric, and the test double is free because the seam exists.

**Check:** for each concrete type used across a module boundary that has a second implementation or
a test double, is the consumer written against a trait or against the type? A function taking
`&File` where it only reads is the finding.

```rust
// verified
use std::io::{self, Read};

/// Program against the capability, not the type that provides it.
///
/// # Errors
/// Propagates any read error from the source.
pub fn first_line(source: &mut impl Read) -> io::Result<String> {
    let text = io::read_to_string(source)?;
    Ok(text.lines().next().unwrap_or_default().to_owned())
}
```

### RS-TYPE-02 [M] Model a closed set of implementations as an enum, not a trait object

**Why:** an enum has no allocation, no vtable, exhaustive matching when a variant is added, and
derivable `Clone`, `PartialEq`, `Debug`, and `Serialize`, none of which `Box<dyn Trait>` gives. For
two to six known implementations it loses only on extensibility, which a closed set does not want.

**Check:** is the set of implementations known at compile time and controlled by you? Then it is an
enum.

```rust
// fragment — BAD: allocation, vtable, no derives, no exhaustiveness
fn make(kind: &str) -> Box<dyn Encoder> { /* … */ }
```

```rust
// fragment — GOOD: the set is closed, so name it
#[derive(Debug, Clone, PartialEq)]
enum Encoder { Json, Csv, Text }
```

## Generics

### RS-TYPE-03 [M] Document the trait's contract, not just its signatures

What invariants an implementor must uphold, what a caller may assume, whether methods may be called
concurrently, and what happens on error.

**Why:** a trait without a documented contract cannot be implemented correctly except by accident,
because the signatures constrain types and say nothing about behaviour. `Iterator`'s contract around
`next()` after `None` is the canonical example of why this matters.

**Check:** could someone write a conforming implementation from the rustdoc alone, without reading
yours?

```rust
// verified
/// The contract is documented, not just the signature.
pub trait Normalizer {
    /// Returns `input` in canonical form.
    ///
    /// Implementors must be idempotent: `normalize(normalize(x)) == normalize(x)`,
    /// and must never lengthen the input.
    fn normalize(&self, input: &str) -> String;
}
```

### RS-TYPE-04 [S] Genericize a parameter only where the flexibility is used

**Why:** `impl AsRef<Path>` is worth it because callers genuinely hold four different path-like
types. `impl Into<u32>` is not, because they hold a `u32`. Genericity has an inference cost, a
documentation cost, and a monomorphization cost.

**Check:** list the concrete types this parameter will be instantiated with. One means make it
concrete.

## Decided by tools

A tool settles these on its own; the shipped configuration enables each at the level shown.

| Tool | Lint | Level | Forbids |
|---|---|---|---|
| clippy | `wildcard_enum_match_arm` | warn | a `_` arm in a `match` over an enum of this crate — a new variant must break every site that has to change; an enum from another crate that is `#[non_exhaustive]` is not flagged |
