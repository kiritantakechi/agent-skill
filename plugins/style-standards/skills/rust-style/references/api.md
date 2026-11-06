# API: The Public Surface, Signatures, Invariants, and Evolution

Scope: everything a downstream crate can see and therefore everything you must keep working. The
shape of the public namespace, what parameters and returns should be, when fields are private, how
to make illegal states unrepresentable, the attribute contracts (`#[must_use]`, `#[non_exhaustive]`,
`#[track_caller]`), which std traits to implement and why, constructor and builder shape, and which
changes are breaking. Naming of these items is in the naming chapter; error *type* design is in the
errors chapter; trait design proper is in the traits chapter.

The organizing fact: within a major version you are not allowed to change any of this. Design as if
you never will be.

An item is *published* when code you do not control can name it — section 1's library, at the
granularity of one item. A rule here that says "published" applies to exactly those items, at every
tier, and to no others.

Two sources are merged here: the **Rust API Guidelines** (C-CASE, C-CONV, C-COMMON-TRAITS,
C-COLLECT, C-SERDE, C-GENERIC, C-CUSTOM-TYPE, C-STRUCT-PRIVATE, C-STABLE, C-MUST-USE and friends)
and the **empirical shape of `regex`, `ignore`, `grep-searcher`, and `std`**.

## Contents

- **Shape of the public surface**
  - RS-API-01 [M] Keep everything private until proven public
  - RS-API-02 [S] Provide one obvious way to do each thing
  - RS-API-03 [M] Do not expose a dependency's types without adopting its semver
  - RS-API-04 [M] Do not leak a std implementation detail you may want to change
  - RS-API-05 [M] Attach every function to the type it concerns
  - RS-API-06 [M] Compose the public surface out of types, not out of functions

- **Parameters and return types**
  - RS-API-07 [M] Be generic in what you accept, concrete in what you return
  - RS-API-08 [S] Take `impl Into<String>` when you store, `&str` when you read
  - RS-API-09 [M] Return a struct, not a three-element tuple
  - RS-API-10 [S] Justify every out-parameter with buffer reuse

- **Encapsulation and invariants**
  - RS-API-11 [M] Find the invariant before choosing the methods
  - RS-API-12 [M] Return the view from an accessor, never the container
  - RS-API-13 [M] Do not hand out `&mut` to invariant-bearing state
  - RS-API-14 [M] Close every public path that can build an invalid instance
  - RS-API-15 [M] Keep every field of a published struct private, including the ones with no invariant
  - RS-API-16 [M] Give the caller the question it is asking, not the field it would have read
  - RS-API-17 [M] Make every construction path a named one

- **Type safety**
  - RS-API-18 [M] Newtype anything with a unit, a domain, or a validity condition
  - RS-API-19 [M] Replace a `bool` parameter: split the function, or name the flag
  - RS-API-20 [S] Prefer an enum to an `Option` whose `None` has meaning
  - RS-API-21 [M] Collapse correlated fields into the sum type they already are
  - RS-API-22 [M] Do not build stringly-typed APIs
  - RS-API-23 [M] Encode units in types
  - RS-API-24 [S] Use `NonZero*` where zero is invalid
  - RS-API-25 [S] Newtype indices when several index spaces coexist
  - RS-API-26 [M] Model a finite set of states as an enum that lists all of them
  - RS-API-27 [M] Make a bad value unrepresentable, else rejected at construction, else checked

- **Attributes and contracts**
  - RS-API-28 [M] Derive every common trait the type's meaning allows
  - RS-API-29 [M] Never derive a trait whose semantics are wrong for the type
  - RS-API-30 [M] Document what a derived `Ord` orders by, or do not derive it
  - RS-API-31 [S] Choose the `#[default]` variant deliberately
  - RS-API-32 [S] Do not implement `Default` where there is no meaningful default
  - RS-API-33 [S] Put `#[must_use]` on pure functions and pending obligations
  - RS-API-34 [S] Give `#[must_use]` a message when the reason is not obvious
  - RS-API-35 [S] Use `#[track_caller]` on functions that panic on caller error

- **Standard trait implementations**
  - RS-API-36 [M] Implement `Debug` on every public type
  - RS-API-37 [M] Keep `Debug` for programmers and `Display` for users
  - RS-API-38 [S] Implement `Display` only when there is one obvious rendering
  - RS-API-39 [M] Keep `PartialEq`, `Eq`, `Hash`, and `Ord` consistent
  - RS-API-40 [S] Implement `FromStr` for any type with a canonical textual form
  - RS-API-41 [M] Implement `From` for infallible and `TryFrom` for fallible conversions
  - RS-API-42 [S] Implement `FromIterator`, `Extend`, and `IntoIterator` on collections
  - RS-API-43 [S] Implement `AsRef` and `Borrow` only when the type genuinely is the target
  - RS-API-44 [M] Do not abuse `Deref` for inheritance
  - RS-API-45 [S] Gate `serde` behind an off-by-default feature

- **Constructors, builders, conversions**
  - RS-API-46 [S] Let `new()` take only what the type cannot exist without
  - RS-API-47 [S] Reach for a builder past three optional parameters
  - RS-API-48 [S] Prefer the `&mut self -> &mut Self` builder shape
  - RS-API-49 [S] Name builder setters after the property, without `set_`
  - RS-API-50 [M] Validate in `build()`, not in the setters
  - RS-API-51 [M!] Convert through `From`, `TryFrom` and `FromStr`, not an inherent `from_*`
  - RS-API-52 [M] Mark an unchecked constructor `unsafe`, and name it `*_unchecked`

- **Future-proofing and evolution**
  - RS-API-53 [M] Decide `#[non_exhaustive]` for every published enum and struct
  - RS-API-54 [M] Classify every change as breaking or not before tagging a release
  - RS-API-55 [M] Deprecate before removing, and say what to use instead
  - RS-API-56 [S] Prefer additive evolution; batch the breaking changes

- **Symmetry of the public surface**
  - RS-API-57 [M] Give every operation its inverse, or document why there is none
  - RS-API-58 [M] Keep argument order identical across sibling functions
  - RS-API-59 [M] Give sibling error variants a uniform shape
  - RS-API-60 [M] Choose `Option` or `Result` uniformly for the same kind of absence
  - RS-API-61 [S] Give comparable sibling methods the same receiver

- Decided by tools

---

## Shape of the public surface

### RS-API-01 [M] Keep everything private until proven public

Start with the smallest surface that lets the intended use cases work.

**Why:** `pub` is a promise of support that you cannot withdraw within a major version; a
crate-private item promises nothing outside the crate and can be promoted the day someone needs it.
Growing a surface is a minor version, shrinking it a major one — so the asymmetry says start small.

**Check:** for each `pub` item, name the external use case. `cargo public-api` will list the full
surface if you are not sure what is reachable; anything on that list you cannot justify is a
liability you have not noticed yet.

```rust
// verified
/// The public surface is one type and three methods; everything else stays private.
#[derive(Debug, Default)]
pub struct Searcher {
    needle: String,
}

impl Searcher {
    #[must_use]
    pub fn new(needle: String) -> Self {
        Self { needle }
    }

    #[must_use]
    pub fn matches(&self, haystack: &str) -> bool {
        haystack.contains(&self.needle)
    }
}
```

### RS-API-02 [S] Provide one obvious way to do each thing

**Why:** two constructors that differ only in argument order, or a builder plus an equivalent
seven-argument `new`, force the caller to make a meaningless choice and double the surface you must
keep working. Every duplicate path is also a place the two can drift apart in behaviour.

**Check:** for each pair of functions with overlapping purpose, could one be deleted without loss?
If the answer is "one is more convenient", make it the only one.

### RS-API-03 [M] Do not expose a dependency's types without adopting its semver

A dependency's type in a public signature makes its major version yours. An error variant carrying
`regex::Error` is the commonest case, because `#[from]` makes it one line.

**Why:** if `regex::Regex` appears in your signature, a `regex` 2.0 is a breaking change for you
too, and a user already on the other major holds a `Regex` your signature does not accept. Wrap the
type, or re-export it explicitly and document the coupling so users can plan.

**Check:** list the types in your public signatures and every `#[from]` in your error types. Which
come from dependencies? For each, is the coupling deliberate and documented, or should the value be
converted to your own representation?

### RS-API-04 [M] Do not leak a std implementation detail you may want to change

Returning `std::collections::hash_map::Keys<'_, K, V>` pins you to `HashMap` forever.

**Why:** the concrete iterator type names the container. Switching to `BTreeMap`, `IndexMap`, or a
sorted `Vec` then becomes a breaking change for a decision the caller never cared about.
`impl Iterator<Item = &K>` costs nothing and hides it.

**Check:** grep public return types for `std::collections::` and `std::slice::` iterator types.

```rust
// verified
/// A returned iterator borrows, so nothing is allocated for the caller.
#[derive(Debug, Default)]
pub struct Index {
    keys: Vec<String>,
}

impl Index {
    pub fn keys(&self) -> impl Iterator<Item = &str> {
        self.keys.iter().map(String::as_str)
    }
}
```

### RS-API-05 [M] Attach every function to the type it concerns

A free function is right only for an operation that belongs to no type you own
(`fs::read_to_string`) or for the crate's single entry point; everything else has a receiver.

**Why:** methods are discoverable — they appear in autocomplete and on the type's rustdoc page — and
a function that takes your type but sits beside it is hidden from the person holding the value.

**Check:** for each free function, does any parameter have a type you own? Then it is a method on
that type. If several qualify, the first one it would read as a sentence with.

### RS-API-06 [M] Compose the public surface out of types, not out of functions

What a crate exports is a small set of types with methods. A free function at the root is the
exception, and it is one you can justify in a sentence.

**Why:** a crate of thirty loose functions has no centre: the reader must hold the whole list, a new
operation is one more name nobody watches, and any two functions drift apart in naming, argument
order, and error type unnoticed (RS-API-58, RS-NAME-25).

**Check:** list what the crate root exports. What is the ratio of types to free functions? For each
free function, name the type it would be a method on — if you can name one, it belongs there
(RS-API-05).

```rust
// verified
/// The surface is a type with methods, not a row of free functions.
#[derive(Debug, Default)]
pub struct Index {
    entries: Vec<String>,
}

impl Index {
    #[must_use]
    pub fn new() -> Self {
        Self::default()
    }

    pub fn insert(&mut self, key: String) {
        self.entries.push(key);
    }

    #[must_use]
    pub fn contains(&self, key: &str) -> bool {
        self.entries.iter().any(|e| e == key)
    }
}
```

## Parameters and return types

### RS-API-07 [M] Be generic in what you accept, concrete in what you return

Accept `impl AsRef<Path>`, `impl IntoIterator<Item = T>`, `impl Into<String>`; return a named type
or `impl Trait`. A range parameter is `impl RangeBounds<usize>`, which takes every range syntax; a
range a type stores is `core::range::Range`, which is `Copy`.

**Why:** genericity on the input side removes conversions from every call site; genericity on the
output side pushes inference work onto the caller and often forces a turbofish. The asymmetry is
deliberate — you know what you produce, they know what they have.

**Check:** does any public function return a bare type parameter `T` that appears nowhere in its
parameters? That is the caller choosing your return type, which they cannot do usefully.

```rust
// verified
/// Accept the widest useful input, return the most specific useful output.
#[must_use]
pub fn shortest<'a>(candidates: impl IntoIterator<Item = &'a str>) -> Option<&'a str> {
    candidates.into_iter().min_by_key(|item| item.len())
}
```

### RS-API-08 [S] Take `impl Into<String>` when you store, `&str` when you read

**Why:** `Into<String>` lets a caller holding a `String` move it in and one holding a literal
convert once, where `&str` plus an internal clone makes the owned caller allocate again. A function
that only reads needs no ownership, so `&str` serves both callers with no allocation.

**Check:** grep for `String` parameters that are immediately borrowed, and `&str` parameters that
are immediately `to_owned()`.

```rust
// verified
use std::path::Path;

/// `AsRef<Path>` lets the caller pass whatever they hold; the body stays non-generic.
#[must_use]
pub fn stem(path: impl AsRef<Path>) -> Option<String> {
    fn inner(path: &Path) -> Option<String> {
        path.file_stem()?.to_str().map(str::to_owned)
    }
    inner(path.as_ref())
}
```

### RS-API-09 [M] Return a struct, not a three-element tuple

**Why:** `(usize, usize, bool)` is unreadable and silently transposable, since
`let (start, end, empty) = m;` compiles just as well with the first two swapped. Named accessors
cannot be misread, and a fourth piece of information is one more method, not a changed arity.

**Check:** grep public return types for tuples of arity three or more, and for two-tuples whose
elements share a type.

### RS-API-10 [S] Justify every out-parameter with buffer reuse

`&mut Vec<T>` to be filled is justified when reuse is the point, as in `Read::read_to_end`.

**Why:** out-parameters break composition — the result cannot be fed into an adapter, and the
function cannot be used in an expression. Reuse across a loop is a real reason (RS-PERF-07); "it was
easier to write" is not.

**Check:** is the buffer reused across calls by the intended caller? Say so in the docs and name the
parameter `buf` or `out`.

## Encapsulation and invariants

### RS-API-11 [M] Find the invariant before choosing the methods

Any constraint the type maintains — a sorted `Vec`, a cached length that must match, a value
confined to a range, an index into a sibling field — is a contract the type owes, and it decides
which methods may exist.

**Why:** a published type's fields are private either way (RS-API-15), so privacy decides nothing;
the invariant decides what may exist. Unnamed, the next `&mut` method breaks it; named, it tells you
construction is fallible, the field has no setter, and which accessor would leak it (RS-API-13).

**Check:** for each type, state its invariant in one sentence. If you can state one and no method
mentions it, the type has a contract nobody is enforcing.

```rust
// verified
/// The newtype carries the invariant, so callers never re-check it.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub struct Percent(u8);

/// The value was above 100.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct OutOfRange;

impl Percent {
    /// # Errors
    /// Returns [`OutOfRange`] when `value` exceeds 100.
    pub fn new(value: u8) -> Result<Self, OutOfRange> {
        if value > 100 {
            Err(OutOfRange)
        } else {
            Ok(Self(value))
        }
    }

    #[must_use]
    pub fn get(self) -> u8 {
        self.0
    }
}
```

### RS-API-12 [M] Return the view from an accessor, never the container

`fn buffer(&self) -> &[u8]`, never `fn buffer(&self) -> &Vec<u8>`.

**Why:** an accessor returning `&Vec<u8>` publishes `Vec` exactly as a public field would, so
switching to `SmallVec`, a ring buffer, or a memory map still breaks every caller. `&[u8]` names
what the caller may do, not what you store, and all three can produce it.

**Check:** grep accessor return types for `&Vec<T>`, `&String`, and `&PathBuf` — the slice, `&str`,
and `&Path` say the same thing without naming the container. A map or a set has no borrowed view in
std, so the answer there is not a different return type but a smaller question: `get`, `contains`,
or an iterator (RS-API-16).

### RS-API-13 [M] Do not hand out `&mut` to invariant-bearing state

Not `fn entries_mut(&mut self) -> &mut Vec<Entry>`, which lets a caller violate sorting, uniqueness,
or a cached length, and not a row of `&mut` accessors: one `&mut self` method that performs the
whole transition keeps the type consistent between calls.

**Why:** a `&mut` to the inner collection is a public licence to break every invariant the type
maintains, and no amount of documentation prevents it. Targeted mutators (`insert`, `remove`,
`retain`) can maintain the invariant; a raw `&mut` cannot.

**Check:** for each `&mut`-returning accessor, what invariant could a caller break with it, and
could two of them be called in an order that leaves the type invalid? If the answer is "none", the
accessor is still wrong: hand out the operation the caller came for, not the collection it would
have reached through (RS-API-16).

### RS-API-14 [M] Close every public path that can build an invalid instance

Every public path enforces the invariants; a builder is the usual one to miss: if the built type can
also be made by a struct literal or a `From<Options>`, every invariant `build()` enforces is
unenforced on the other path.

**Why:** private fields plus a constructor that takes every field unvalidated is not encapsulation —
it is public fields with extra typing. The point is that the type cannot be constructed in a bad
state, not that the fields have a keyword in front of them.

**Check:** can a caller reach an invalid instance through any public path — a constructor, a setter,
a `Deserialize` impl, a `Default`, a `From<Options>` that skips `build()`? `serde` in particular
bypasses your constructor unless you use `#[serde(try_from = "…")]`.

### RS-API-15 [M] Keep every field of a published struct private, including the ones with no invariant

A published type has no "pure data bag" exemption. A struct whose fields are independent today is
still a struct whose representation you have published. The single exception is a type whose layout
is already the contract — `#[repr(C)]` or `extern` types crossing an ABI boundary (RS-UNSAFE-14). A
constructor or builder replaces the struct literal, and a method replaces field access. A tuple
struct is no exception: `struct Port(u16)` with an accessor, never `struct Port(pub u16)`, whose
`.0` is a public field that also names nothing.

An unpublished struct — private or `pub(crate)`, or in a binary or an internal workspace crate — may
be plain data with public fields, built with a struct literal; a field there that carries an
invariant is a path to an invalid instance, and RS-API-14 closes it.

**Why:** a public field commits to a *representation*: `pub threads: usize` cannot later become
`NonZeroUsize` or a computed value without a major version, and invariants usually arrive later.
What public fields buy, methods give back; the representation they spend is gone for good.

**Check:** `rg -n 'pub [a-z_]*:' -g '*.rs' src/` over struct bodies, and
`rg -n 'struct [A-Za-z_]*\(pub ' -g '*.rs' src/` for tuple structs. Every hit that is not on a
`#[repr(C)]` type is a defect in a published type, whatever invariant it does or does not carry
today; elsewhere, a hit is a defect when the field carries an invariant.

```rust
// verified
use std::num::NonZeroUsize;

/// Private fields even here: nothing about this pair is an invariant today.
#[derive(Debug, Clone)]
pub struct Config {
    threads: NonZeroUsize,
    colour: bool,
}

impl Config {
    #[must_use]
    pub fn new(threads: NonZeroUsize) -> Self {
        Self {
            threads,
            colour: true,
        }
    }

    #[must_use]
    pub fn thread_count(&self) -> NonZeroUsize {
        self.threads
    }
}
```

### RS-API-16 [M] Give the caller the question it is asking, not the field it would have read

A method names the decision — `thread_count()`, `is_saturated()`, `remaining()` — rather than
mirroring storage one accessor per field.

**Why:** a row of `fn x(&self) -> T { self.x }` pins the representation as a public field would and
hands the caller arithmetic that belongs to the type. A named question can be answered differently
later, and its logic lives once, beside the data (RS-API-13).

**Check:** for each accessor, find the expression the caller writes around it. If callers all wrap
it in the same arithmetic or comparison, that expression is the method you owe them.

```rust
// verified
/// The method names the question; no accessor mirrors storage.
#[derive(Debug, Default)]
pub struct Budget {
    spent: u64,
    limit: u64,
}

impl Budget {
    #[must_use]
    pub fn remaining(&self) -> u64 {
        self.limit.saturating_sub(self.spent)
    }

    #[must_use]
    pub fn is_exhausted(&self) -> bool {
        self.spent >= self.limit
    }
}
```

### RS-API-17 [M] Make every construction path a named one

A struct literal is not available once fields are private, so the type states how it is built:
`new`, a named alternative constructor (RS-NAME-21), a builder, or a `TryFrom`.

**Why:** a named entry point is where validation lives (RS-FUNC-37), where defaults are decided, and
where a later invariant is enforced without touching a call site. Every instance traces back to a
function you can grep, named for its starting state.

**Check:** can the type be built without calling one of its own functions? Inside the defining
module a literal is still legal — is one being used where a constructor should be?

```rust
// verified
/// Each starting state has a name; no literal can build one.
#[derive(Debug, Clone)]
pub struct Retry {
    attempts: u32,
    backoff_ms: u64,
}

impl Retry {
    #[must_use]
    pub fn immediate() -> Self {
        Self {
            attempts: 1,
            backoff_ms: 0,
        }
    }

    #[must_use]
    pub fn exponential(attempts: u32) -> Self {
        Self {
            attempts,
            backoff_ms: 100,
        }
    }
}
```

## Type safety

### RS-API-18 [M] Newtype anything with a unit, a domain, or a validity condition

`UserId(u64)`, `Bytes(u64)`, `Utf8Path`. Two adjacent parameters of one primitive type —
`fn copy(src: u32, dst: u32)` — are the commonest case, because they will be called backwards. A
constraint stated in prose ("must be non-empty", "in the range 1..=100") is a validity condition
whose type, such as `NonEmpty<T>`, has not been written yet.

**Why:** the compiler then catches argument transposition, which tests usually do not, because a
transposed pair of `u64`s produces plausible wrong answers rather than a crash. A constraint in a
type is checked once, at the boundary; one in prose is re-checked by every reader.

**Check:** scan every public signature for two consecutive parameters of the same primitive type,
and grep doc comments for "must", "should be", "expects" and range notation; each doc hit is a type
or a `# Panics` section you owe (RS-DOC-11). For the rest of the primitive-typed fields and
parameters, is a different value of the same type nonsense here?

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

### RS-API-19 [M] Replace a `bool` parameter: split the function, or name the flag

A flag that selects behaviour means the function has become two sharing a body: split it, and let
the shared part be a private helper. A flag that is data is a two-variant enum. Three or more flags
read together are an options struct or a policy closure, `impl Fn(&Entry) -> bool`.

**Why:** `search(path, true, false)` is unreadable at the call site and cannot be checked by anyone
reviewing the diff. A mode flag also makes the return type and error set the union of both modes, so
every caller handles cases its mode cannot produce.

**Check:** grep public signatures for `: bool`. Does the body branch on it at the top level, with
little shared? Then it is two functions. Otherwise it is a two-variant enum, or, with three or more,
an options struct or a policy closure.

```rust
// verified
use std::io;

/// Two-variant enums at the call site read as `Flush::Yes`, not a bare `true`.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Flush {
    Yes,
    No,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Durability {
    Sync,
    Buffered,
}

pub trait Sink {
    /// # Errors
    /// Propagates any write error from the underlying device.
    fn write(&mut self, data: &[u8], flush: Flush, durability: Durability) -> io::Result<()>;
}
```

```rust
// verified
/// Two names instead of one mode flag: each caller gets a precise signature.
#[must_use]
pub fn render_plain(items: &[String]) -> String {
    items.join("\n")
}

#[must_use]
pub fn render_numbered(items: &[String]) -> String {
    items
        .iter()
        .enumerate()
        .map(|(index, item)| format!("{}: {item}", index + 1))
        .collect::<Vec<_>>()
        .join("\n")
}
```

### RS-API-20 [S] Prefer an enum to an `Option` whose `None` has meaning

**Why:** `Option<Duration>` for a timeout hides whether `None` means "no timeout" or "use the
default" — and both readings are common, so users guess.
`enum Timeout { None, Default, After(Duration) }` states it and makes the third case possible.

**Check:** for each public `Option<T>`, is `None` genuinely just absence? If it carries a policy,
name it.

### RS-API-21 [M] Collapse correlated fields into the sum type they already are

Two `Option`s where exactly one is always `Some`; a `bool` plus a field only meaningful when it is
set.

**Why:** the correlation is an invariant the compiler cannot see, so every reader must learn it and
every path must handle the impossible combination, usually with an `unwrap` or an `unreachable!`
(RS-ERR-26). The sum type deletes those branches.

**Check:** for each pair of fields, is there a combination of values that cannot legally occur? That
pair is an enum.

### RS-API-22 [M] Do not build stringly-typed APIs

Errors returned as `String`; a config keyed by arbitrary strings; a parameter whose string stands in
for a type. A parameter accepting `"json" | "text" | "csv"` is a finite set, which RS-API-26 makes
an enum.

**Why:** every mistake is deferred to runtime, nothing is discoverable from the signature, and no
refactoring tool can rename anything. A string error cannot be matched on, and a string key cannot
be found by the compiler when it is misspelled.

**Check:** grep public signatures and error types for `&str` and `String`. For each, is the string
the data itself, or a stand-in for a type the crate has not written?

### RS-API-23 [M] Encode units in types

`Duration` rather than `timeout_ms: u64`; a `ByteSize` newtype rather than `size: u64`. Where a
newtype would be disproportionate — a private helper, a single call site — the unit goes in the name
(RS-NAME-09); never omit both.

**Why:** unit confusion is a bug class the type system eliminates completely — the compiler rejects
passing a byte count where a millisecond count belongs, and no test suite reliably catches the
transposition.

**Check:** grep for numeric parameters and fields whose type is a bare integer or float. For each,
is the unit recoverable from the type or the name without reading a comment?

```rust
// fragment — BAD: two u64s, transposable, unit only in the comment
fn retry(timeout: u64, backoff: u64) {} // both milliseconds
```

```rust
// fragment — GOOD: neither transposable nor ambiguous
fn retry(timeout: Duration, backoff: Duration) {}
```

### RS-API-24 [S] Use `NonZero*` where zero is invalid

`NonZeroUsize`, `NonZeroU32`.

**Why:** it removes a runtime check, documents the contract in the signature, and makes
`Option<NonZeroU32>` the same size as `u32` thanks to the niche. The conversion cost is one
`try_from` at the boundary, which you needed anyway.

**Check:** grep for functions that begin by rejecting a zero argument. Each is a `NonZero`.

### RS-API-25 [S] Newtype indices when several index spaces coexist

`NodeId`, `EdgeId`, `ByteOffset`, `CharOffset`.

**Why:** mixing byte offsets and char offsets is the classic Unicode bug, and it is a type error
waiting to be declared. The same applies to indices into two parallel arenas — the compiler can
distinguish them the moment you let it (RS-OWN-21).

**Check:** does the crate hold more than one `Vec` indexed by `usize`? Those are distinct types.

### RS-API-26 [M] Model a finite set of states as an enum that lists all of them

Protocol phases, parser modes, retry outcomes, file kinds. Not an integer with named constants, not
a string tag, not a group of booleans.

**Why:** an enum closes the set, so `match` proves every state handled and a new state breaks every
incomplete site at compile time. The alternatives defer that to runtime: an integer admits values
the set never had, a string admits typos, and *n* booleans admit 2ⁿ combinations (RS-API-21).

**Check:** for each state-like value, can you name a representable value that is not a legal state?
Then the type is wrong. Count the booleans that travel together — three of them is eight states, and
you meant three.

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

### RS-API-27 [M] Make a bad value unrepresentable, else rejected at construction, else checked

Three tiers, in order: the type cannot express the bad value; the constructor refuses it; a runtime
check catches it. Reach for the earliest tier the situation allows.

**Why:** each tier costs more than the last: unrepresentable costs nothing and cannot be forgotten,
rejection costs one check per value, and a runtime check costs one per use at every site. A later
tier leaves defensive branches nobody can prove unreachable, so none is ever deleted.

**Check:** for each validation in the body of a function, ask which tier it belongs to and whether
an earlier tier was available. A check that could have been a `NonZeroUsize` is a defect
(RS-API-24).

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

## Attributes and contracts

### RS-API-28 [M] Derive every common trait the type's meaning allows

Each of `Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash, Default` that the type's meaning
allows: `Copy` only on a value that can never come to own a heap allocation or a handle, `Default`
only where a meaningful default exists (RS-API-32), and an order only where one is meaningful
(RS-API-29).

**Why:** C-COMMON-TRAITS. A missing derive is invisible until a user needs it, and the orphan rule
leaves them a newtype or a pull request. Adding a derive later is a minor version; removing `Copy`
is breaking, because every implicit copy becomes a move.

**Check:** for each public type, which of the nine are missing, and does the type's meaning rule
each one out? Could the type ever grow a `String`, a `Vec` or a handle? Then it is not `Copy` today.

```rust
// verified
/// The standard derive set: nothing here forces an allocation on the caller.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash, Default)]
pub struct Version {
    major: u16,
    minor: u16,
}

impl Version {
    #[must_use]
    pub fn new(major: u16, minor: u16) -> Self {
        Self { major, minor }
    }

    #[must_use]
    pub fn is_compatible_with(self, other: Self) -> bool {
        self.major == other.major && self.minor >= other.minor
    }
}
```

### RS-API-29 [M] Never derive a trait whose semantics are wrong for the type

**Why:** deriving `PartialEq` on a struct with a cache field makes two logically equal values
compare unequal — and the bug surfaces in a `HashMap` lookup three modules away. The derive is
convenient precisely because it is thoughtless, which is the hazard.

**Check:** for each derived `PartialEq`/`Hash`/`Ord`, does every field participate in identity? Any
cache, timestamp, or arena handle is a no.

### RS-API-30 [M] Document what a derived `Ord` orders by, or do not derive it

**Why:** `#[derive(Ord)]` fixes the ordering to the declaration order of the fields, permanently.
Reordering fields for layout or readability then silently changes the sort order of every user's
data. If the ordering matters, document it; if it is arbitrary, do not derive `Ord`.

**Check:** does the type's rustdoc say what the ordering means? If not, either write it or remove
the derive.

### RS-API-31 [S] Choose the `#[default]` variant deliberately

**Why:** `#[derive(Default)]` on an enum requires marking a variant, and the first one you happened
to write is rarely the neutral case. The default is what every `..Default::default()` and every
`Option::unwrap_or_default()` will produce.

**Check:** is the marked variant the one a user would expect from "unset"?

```rust
// verified
/// `unwrap_or_default` where the default is genuinely the identity.
#[must_use]
pub fn first_line(text: &str) -> &str {
    text.lines().next().unwrap_or_default()
}
```

### RS-API-32 [S] Do not implement `Default` where there is no meaningful default

**Why:** `Default` on a `Connection` or a `File` yields an unusable value, which then flows through
`unwrap_or_default()` and every containing `#[derive(Default)]` into places nobody intended. A
`Config` with sensible zero values implements it; a resource handle does not.

**Check:** is `Default::default()` a value you would be happy to see used?

```rust
// verified
/// `Default` is the identity, not an arbitrary configuration.
#[derive(Debug, Clone, Copy, Default, PartialEq, Eq)]
pub struct Counters {
    matched: u64,
    skipped: u64,
}

impl Counters {
    #[must_use]
    pub fn merge(self, other: Self) -> Self {
        Self {
            matched: self.matched + other.matched,
            skipped: self.skipped + other.skipped,
        }
    }
}
```

### RS-API-33 [S] Put `#[must_use]` on pure functions and pending obligations

Pure computations whose return value is the point; guards, builders, futures, and iterator adapters.

**Why:** ignoring the result of `Builder::case_insensitive(true)` on a by-value builder is a silent
no-op — the configured value is dropped and the original is used. The compiler can catch it for the
cost of one attribute.

**Check:** clippy `must_use_candidate` flags a pure public function without the attribute. For each
guard, builder, and other function it cannot judge, would discarding the return value ever be
correct? If never, mark it.

```rust
// verified
/// `#[must_use]` on a value whose whole point is to be inspected.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
#[must_use = "a validation result carries the only signal that the input was rejected"]
pub enum Validation {
    Valid,
    Invalid,
}

pub fn validate(input: &str) -> Validation {
    if input.is_empty() {
        Validation::Invalid
    } else {
        Validation::Valid
    }
}
```

### RS-API-34 [S] Give `#[must_use]` a message when the reason is not obvious

`#[must_use = "iterators are lazy and do nothing unless consumed"]`.

**Why:** the default warning says the value is unused, which the author can already see. The message
says *what will silently not happen*, which is the information they are missing.

**Check:** would a competent user understand the consequence from the default message alone?

### RS-API-35 [S] Use `#[track_caller]` on functions that panic on caller error

**Why:** without it the panic message points at your internals, so the user sees a location inside
your crate for a mistake in theirs. `Vec::remove` and `slice` indexing both use it, which is why
their panics are actionable.

**Check:** for each documented panic (RS-DOC-11), does the message name the caller's line?

## Standard trait implementations

### RS-API-36 [M] Implement `Debug` on every public type

No exceptions for "internal" types that appear in a public struct.

**Why:** a missing `Debug` poisons `#[derive(Debug)]` for every type containing it, makes
`assert_eq!` unusable in users' tests, and makes the value invisible in a debugger and in `tracing`
fields. The blast radius is far larger than the one type.

**Check:** rustc `missing_debug_implementations`, denied by the shipped configuration, fails the
build on a public type without one. Manual impls are fine; absence is not.

### RS-API-37 [M] Keep `Debug` for programmers and `Display` for users

**Why:** `Debug` output may change at any time and favours completeness; `Display` is part of the
contract and favours clarity. A `Display` that delegates to `Debug` publishes internal structure,
the defect in RS-ERR-31.

**Check:** does any `Display` impl call `{:?}`? Does any `Debug` impl omit a field to look tidier?

### RS-API-38 [S] Implement `Display` only when there is one obvious rendering

**Why:** `Display` takes no options, so if there are two reasonable renderings — short and verbose,
coloured and plain, absolute and relative — the trait forces you to pick one and users must
reimplement the other. Explicit methods can take arguments.

**Check:** are there two ways a user would reasonably want to print this? Then ship two methods,
each returning an `impl fmt::Display` built with `fmt::from_fn`, and skip the trait.

```rust
// verified
use std::fmt;

/// `Display` is for users; `Debug` is for developers. They are not the same text.
#[derive(Debug, Clone, Copy)]
pub struct Bytes(u64);

impl fmt::Display for Bytes {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        let Self(raw) = *self;
        if raw < 1024 {
            write!(f, "{raw} B")
        } else {
            write!(f, "{} KiB", raw / 1024)
        }
    }
}
```

```rust
// verified
use std::fmt;

/// Two renderings, so two methods and no `Display`; neither allocates.
#[derive(Debug, Clone, Copy)]
pub struct Elapsed(u64);

impl Elapsed {
    #[must_use]
    pub fn short(self) -> impl fmt::Display {
        fmt::from_fn(move |f| write!(f, "{}s", self.0))
    }

    #[must_use]
    pub fn verbose(self) -> impl fmt::Display {
        fmt::from_fn(move |f| write!(f, "{} seconds", self.0))
    }
}

#[cfg(test)]
mod tests {
    use super::Elapsed;

    #[test]
    fn renders_both_forms() {
        assert_eq!(Elapsed(3).short().to_string(), "3s");
        assert_eq!(Elapsed(3).verbose().to_string(), "3 seconds");
    }
}
```

### RS-API-39 [M] Keep `PartialEq`, `Eq`, `Hash`, and `Ord` consistent

Equal values must hash equally; `Ord` must agree with `PartialOrd` and `Eq`.

**Why:** inconsistency fails silently and far from the impl: a `HashMap` misses a key looked up by
an equal one, a `BTreeMap` loses entries, `BTreeMap::append` may panic, and a derived `PartialOrd`
beside a derived `Ord` answers with `cmp`, not with each field's `partial_cmp`.

**Check:** if you hand-implement one of the four, review all four in the same commit. Property-test
the laws (RS-TEST-20).

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

### RS-API-40 [S] Implement `FromStr` for any type with a canonical textual form

**Why:** it makes `"1.2.3".parse::<Version>()` work and plugs into every argument parser and config
deserializer without them knowing your type. An inherent `parse` works only for callers who read
your docs (RS-API-51).

**Check:** does the type have a textual form used in config, CLI flags, or serialization?

### RS-API-41 [M] Implement `From` for infallible and `TryFrom` for fallible conversions

Never a `From` impl that panics.

**Why:** `From` is understood by the whole ecosystem to be total, and `?` relies on it. A panicking
`From` turns an innocuous `.into()` into an abort, in code that has no visible failure path.
Implement the direction that cannot fail and let the blanket impl give you `Into` free.

**Check:** does any `From` impl contain `unwrap`, `expect`, `panic!`, or an unchecked cast?

```rust
// verified
/// `From` for infallible conversion; the reverse direction is `TryFrom`.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Millis(u64);

impl From<Millis> for std::time::Duration {
    fn from(Millis(raw): Millis) -> Self {
        Self::from_millis(raw)
    }
}
```

### RS-API-42 [S] Implement `FromIterator`, `Extend`, and `IntoIterator` on collections

Including `IntoIterator` for `&Collection` and `&mut Collection` where meaningful.

**Why:** C-COLLECT. Without them, `.collect()` into your type does not work, `for x in &coll` does
not work, and `extend` does not work — so your collection is a second-class citizen in every
pipeline a user writes.

**Check:** can a user build your collection with `collect()` and iterate it with `for x in &coll`?

```rust
// verified
/// `FromIterator` lets the type be built by `collect`, like every std container.
#[derive(Debug, Default, PartialEq, Eq)]
pub struct Tags {
    inner: Vec<String>,
}

impl FromIterator<String> for Tags {
    fn from_iter<I: IntoIterator<Item = String>>(iter: I) -> Self {
        Self {
            inner: iter.into_iter().collect(),
        }
    }
}
```

### RS-API-43 [S] Implement `AsRef` and `Borrow` only when the type genuinely is the target

**Why:** `AsRef<T>` claims a cheap reference conversion; `Borrow<T>` also requires `Eq`, `Ord`, and
`Hash` to agree between the two forms, which is what makes `HashMap<String, _>::get(&str)` work. A
casual `Borrow` impl breaks that guarantee silently.

**Check:** for each `Borrow` impl, do the three traits agree between the two forms? If you are not
sure, implement `AsRef` only.

```rust
// verified
/// `AsRef` gives a cheap borrowed view without committing to a representation.
#[derive(Debug, Clone)]
pub struct Name(String);

impl AsRef<str> for Name {
    fn as_ref(&self) -> &str {
        &self.0
    }
}
```

### RS-API-44 [M] Do not abuse `Deref` for inheritance

**Why:** `Deref` is for smart pointers (`Box`, `Arc`, `MutexGuard`) and transparent newtypes. Using
it to inherit methods produces confusing autocompletion, method resolution that surprises everyone,
no way to override, and a type whose API changes when the inner type's does.

**Check:** does the `Deref` target have methods you would not want on the outer type? Then it is
inheritance, not a smart pointer.

### RS-API-45 [S] Gate `serde` behind an off-by-default feature

And derive with `#[serde(deny_unknown_fields)]` for config types.

**Why:** `serde` and `serde_derive` are a substantial compile-time cost for users who do not
serialize, and `deny_unknown_fields` turns a silently-ignored typo in a config file into an error
the user can act on (RS-BUILD-14).

**Check:** is `serde` in `[dependencies]` without `optional = true`? Does a misspelled config key
produce an error or a silent default?

## Constructors, builders, conversions

### RS-API-46 [S] Let `new()` take only what the type cannot exist without

**Why:** a `new` that takes every option is the builder written badly — positional, unnamable, and
breaking every time an option is added. If the essential argument count is zero, that is
`Default::default()`; provide `new()` as well, because users look for it.

**Check:** how many of `new`'s parameters have an obvious default? Those belong elsewhere.

```rust
// verified
/// Constructors that cannot fail are `new`; the fallible one says `try_`.
#[derive(Debug, Clone, Copy)]
pub struct Ratio {
    numerator: u32,
    denominator: u32,
}

/// The denominator was zero.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct ZeroDenominator;

impl Ratio {
    #[must_use]
    pub fn whole(numerator: u32) -> Self {
        Self {
            numerator,
            denominator: 1,
        }
    }

    /// # Errors
    /// Returns [`ZeroDenominator`] when `denominator` is zero.
    pub fn try_new(numerator: u32, denominator: u32) -> Result<Self, ZeroDenominator> {
        (denominator != 0).ok_or(ZeroDenominator).map(|()| Self {
            numerator,
            denominator,
        })
    }
}
```

### RS-API-47 [S] Reach for a builder past three optional parameters

Or when construction is fallible in several distinct ways, or when options will grow.

**Why:** below that threshold an options struct with `Default` and a few `#[must_use]` setters is
lighter and more transparent. Above it, positional arguments become unreadable and every addition is
a breaking change.

**Check:** count the optional parameters. Three is the line; the direction of travel matters more
than the exact count.

```rust
// verified
use std::borrow::Cow;

/// Two-variant enums, so no option is set with a bare `true` (RS-API-19).
#[derive(Debug, Clone, Copy, Default, PartialEq, Eq)]
pub enum Case {
    #[default]
    Sensitive,
    Insensitive,
}

#[derive(Debug, Clone, Copy, Default, PartialEq, Eq)]
pub enum Scope {
    #[default]
    WholeInput,
    FirstLine,
}

/// An options struct beats four positional parameters of related type.
#[derive(Debug, Clone, Copy, Default)]
#[non_exhaustive]
pub struct SearchOptions {
    case: Case,
    scope: Scope,
    max_matches: Option<usize>,
}

impl SearchOptions {
    #[must_use]
    pub fn with_case(mut self, case: Case) -> Self {
        self.case = case;
        self
    }

    #[must_use]
    pub fn with_scope(mut self, scope: Scope) -> Self {
        self.scope = scope;
        self
    }

    #[must_use]
    pub fn with_max_matches(mut self, cap: usize) -> Self {
        self.max_matches = Some(cap);
        self
    }
}

#[must_use]
pub fn count(haystack: &str, needle: &str, options: SearchOptions) -> usize {
    let hay = match options.scope {
        Scope::WholeInput => haystack,
        Scope::FirstLine => haystack.lines().next().unwrap_or_default(),
    };
    let (hay, needle) = match options.case {
        Case::Sensitive => (Cow::Borrowed(hay), Cow::Borrowed(needle)),
        Case::Insensitive => (
            Cow::Owned(hay.to_lowercase()),
            Cow::Owned(needle.to_lowercase()),
        ),
    };
    let found = hay.matches(needle.as_ref()).count();
    options.max_matches.map_or(found, |cap| found.min(cap))
}
```

### RS-API-48 [S] Prefer the `&mut self -> &mut Self` builder shape

As used by `SearcherBuilder` and `RegexBuilder`, terminating in `fn build(&self) -> Result<T, E>`.

**Why:** it works with a builder stored in a struct, it can be configured in a loop, and it does not
require move gymnastics when a setter is called conditionally. The by-value `self -> Self` shape is
fine for small one-shot builders — mark it `#[must_use]` (RS-API-33).

**Check:** can a caller configure the builder inside an `if` without reassigning it?

### RS-API-49 [S] Name builder setters after the property, without `set_`

`.case_insensitive(true)`, `.max_depth(Some(3))`, `.threads(4)`.

**Why:** the builder call chain reads as a description of the configuration, and `set_` on every
line is noise. It also matches the convention every major crate uses, so users guess correctly
(RS-NAME-17).

**Check:** grep the builder for `fn set_`.

### RS-API-50 [M] Validate in `build()`, not in the setters

**Why:** setters that validate make the result depend on the order options were set — a pattern that
is invalid until a later setter fixes it becomes an error the caller cannot avoid. Validating once
in `build()` lets callers configure in any order and produces one coherent error.

**Check:** does any setter return `Result`, or panic? Move that check to `build()`.

### RS-API-51 [M!] Convert through `From`, `TryFrom` and `FromStr`, not an inherent `from_*`

A conversion from one source type is a trait impl, which gives callers `.into()`, `?` and generic
code for free. Where the impl would be ambiguous — several conversions from one source type, as with
`from_utf8`, `from_utf8_lossy` and `from_raw_parts` — or would leak a type parameter, it is an
inherent `from_*` named for the source, not the target.

*Relaxed form:* an inherent `from_*` alone, named for its source.

**Why:** `From` can be implemented once per source type, so only distinct conversions from one input
need names. An inherent `Config::from_path(p)` works only for a caller who knows to look; a
`TryFrom<&Path>` also works inside `collect::<Result<Vec<_>, _>>()`, behind `impl TryInto`, and `?`.

**Check:** for each inherent `from_*`, could it be a `From`/`TryFrom` impl without ambiguity? If
yes, make it one and keep the inherent version only as a thin forwarder.

### RS-API-52 [M] Mark an unchecked constructor `unsafe`, and name it `*_unchecked`

Document its precondition in a `# Safety` section. The suffix names the check that was skipped; the
keyword makes the caller prove it (RS-UNSAFE-04).

**Why:** a constructor that skips validation is the right tool for a caller who has validated and a
silent source of invalid values for one who has not. The name and the keyword make the difference
visible at the call site.

**Check:** does any safe constructor skip a check that the normal one performs, or any `*_unchecked`
function lack `unsafe`?

## Future-proofing and evolution

### RS-API-53 [M] Decide `#[non_exhaustive]` for every published enum and struct

Mark a published enum whose variant set may grow. A genuinely closed set —
`enum Endianness { Big, Little }` — stays exhaustive, because there the attribute only removes the
caller's exhaustiveness checking; say in the rustdoc that it is closed. A struct needs the attribute
only where its fields are public, which RS-API-15 allows a published type for little but
`#[repr(C)]`: a struct with private fields can already grow without a major version.

**Why:** it costs downstream users a wildcard arm and a constructor call, and it buys you the
ability to ship additions as minor versions for the life of the crate. Without it, every new variant
is a major release — which in practice means the variant gets smuggled into an existing one instead.

**Check:** for each published enum, and each published struct with public fields, could a new case
or field plausibly appear? Protocols, parsers and error types almost always can. If you cannot name
a plausible third variant, leave it exhaustive and write that decision in the rustdoc.

```rust
// verified
/// `#[non_exhaustive]` keeps adding a variant a minor version bump.
#[derive(Debug, Clone, Copy)]
#[non_exhaustive]
pub enum Mode {
    Fast,
    Thorough,
}

/// Closed: a byte order has two values and will never have a third, so this stays exhaustive.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Endianness {
    Big,
    Little,
}
```

### RS-API-54 [M] Classify every change as breaking or not before tagging a release

Breaking: adding a type parameter, changing a concrete return type, narrowing a bound, adding a
non-defaulted trait method, removing a derive, making a public item private. Not breaking: widening
a bound, adding an inherent method, adding a variant to a `#[non_exhaustive]` enum, adding a
defaulted method to a sealed trait.

**Why:** the categories are not intuitive — several changes that look additive break callers — and a
break shipped as a minor version fails every downstream build that trusted the version number.

**Check:** before tagging, classify every change in the diff. If you are unsure,
`cargo semver-checks` is the answer (RS-BUILD-32).

```rust
// verified
/// Adding a field to a `#[non_exhaustive]` struct is a minor change, not a breaking one.
#[derive(Debug, Clone, Default)]
#[non_exhaustive]
pub struct Report {
    matched: u64,
    skipped: u64,
}

impl Report {
    #[must_use]
    pub fn new() -> Self {
        Self::default()
    }

    #[must_use]
    pub fn total(&self) -> u64 {
        self.matched + self.skipped
    }
}
```

### RS-API-55 [M] Deprecate before removing, and say what to use instead

`#[deprecated(since = "1.4.0", note = "use `Searcher::search_reader` instead")]`.

**Why:** the note is the whole value. A deprecation that says only "deprecated" leaves the user to
search the changelog, and many will simply pin the old version. Keep the item for at least one minor
cycle so upgraders get a warning rather than a compile error.

**Check:** does every `#[deprecated]` carry both `since` and a `note` naming the replacement?

### RS-API-56 [S] Prefer additive evolution; batch the breaking changes

**Why:** every major version is a migration cost on every user, and not all of them pay it: the
ecosystem splits across majors whose types do not interoperate. Batching the necessary breaks pays
that cost once instead of three times, as `regex` and `rand` do.

**Check:** does the release contain exactly one breaking change that could have waited? Is there a
migration section in the changelog (RS-BUILD-11)?

## Symmetry of the public surface

### RS-API-57 [M] Give every operation its inverse, or document why there is none

If a type can be built from bytes it should be convertible back to them; `insert` implies `remove`,
`push` implies `pop`, `open` implies `close`, `encode` implies `decode`, `subscribe` implies
`unsubscribe`. How the two halves are named is RS-NAME-35.

**Why:** a caller who learns half a pair looks for the other half. A genuine absence usually means
something — the operation is lossy, irreversible, or belongs to another type — and silence makes the
caller assume an oversight and work around it.

**Check:** list the operations on each public type in pairs. For every unpaired one, either add the
inverse or state in the docs why it cannot exist ("hashing is one-way", "the handle is consumed").

```rust
// verified
/// Every operation has its inverse, so a caller who learns one finds the other.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Key(u64);

#[must_use]
pub fn encode(Key(raw): Key) -> [u8; 8] {
    raw.to_le_bytes()
}

#[must_use]
pub fn decode(bytes: [u8; 8]) -> Key {
    Key(u64::from_le_bytes(bytes))
}
```

### RS-API-58 [M] Keep argument order identical across sibling functions

If `copy(src, dst)` takes source first, then `move`, `link`, and `render` in the same module do too.
Fix the order once per crate and never vary it.

**Why:** siblings are called from the same code, and the reader generalizes from the first one they
learn. When the types match, the compiler cannot catch an inconsistent order, so it becomes a silent
argument swap in code that looks right.

**Check:** list every function in the module with two or more parameters of related type and compare
their orders. Any disagreement is the finding, and the fix is to change the outlier.

```rust
// verified
/// Siblings take `(source, target)` in the same order, so the pair cannot be transposed silently.
#[must_use]
pub fn copy_len(source: &[u8], target: &mut Vec<u8>) -> usize {
    target.extend_from_slice(source);
    source.len()
}

#[must_use]
pub fn move_len(source: &mut Vec<u8>, target: &mut Vec<u8>) -> usize {
    let moved = source.len();
    target.append(source);
    moved
}
```

### RS-API-59 [M] Give sibling error variants a uniform shape

Variants of one error enum carry comparable context: if `Read` records the path, `Write` records it
too. Do not mix one variant with four fields and one with none unless the difference is real.

**Why:** the caller writes one `match` over all the variants, and when some carry a path and some do
not, the reporting code grows a special case per deficient variant. Uniform shape lets one function
render them all.

**Check:** tabulate the enum's variants against their fields. A column that is populated for most
variants and empty for one is either a missing field or a variant that belongs elsewhere.

```rust
// verified
use std::path::PathBuf;

/// Sibling variants carry comparable context, so one reporter renders them all.
#[derive(Debug, thiserror::Error)]
#[non_exhaustive]
pub enum Error {
    #[error("failed to read {path}")]
    Read { path: PathBuf },
    #[error("failed to write {path}")]
    Write { path: PathBuf },
}
```

### RS-API-60 [M] Choose `Option` or `Result` uniformly for the same kind of absence

Within one type, "not found" is always `Option` or always `Result` — never `get` returning `Option`
while `lookup` returns `Result<_, NotFound>` for the same condition.

**Why:** the choice encodes whether absence is ordinary or exceptional, so varying it for the same
condition tells the caller two different things about one fact. It also forces conversion glue at
every site that uses both, which is exactly the patch code this standard is trying to eliminate.

**Check:** for each type, list the operations that can fail to produce a value and the reason each
gives. Same reason with different return shapes is a violation.

```rust
// verified
/// One kind of absence, one return shape: both lookups use `Option`.
#[derive(Debug, Default)]
pub struct Registry {
    entries: Vec<(String, u32)>,
}

impl Registry {
    #[must_use]
    pub fn get(&self, name: &str) -> Option<u32> {
        self.entries
            .iter()
            .find(|(key, _)| key == name)
            .map(|&(_, value)| value)
    }

    #[must_use]
    pub fn lookup(&self, id: u32) -> Option<&str> {
        self.entries
            .iter()
            .find(|&&(_, value)| value == id)
            .map(|(key, _)| key.as_str())
    }
}
```

### RS-API-61 [S] Give comparable sibling methods the same receiver

Methods doing comparable work take comparable receivers: if `len` takes `&self`, `capacity` does
too; if one builder step takes `self`, they all do.

**Why:** a mixed receiver set breaks method chaining at unpredictable points and forces the caller
to remember which methods consume. The information that decides the receiver is usually uniform
across the family, so the variation is nearly always accidental.

**Check:** group the type's methods by what they do — inspect, mutate, consume — and confirm the
receiver matches the group. An inspector taking `self` is the usual finding.

```rust
// verified
/// Inspectors take `&self`, mutators `&mut self`, consumers `self` — uniformly.
#[derive(Debug, Default)]
pub struct Buffer {
    bytes: Vec<u8>,
}

impl Buffer {
    #[must_use]
    pub fn len(&self) -> usize {
        self.bytes.len()
    }

    #[must_use]
    pub fn is_empty(&self) -> bool {
        self.bytes.is_empty()
    }

    #[must_use]
    pub fn capacity(&self) -> usize {
        self.bytes.capacity()
    }

    pub fn push(&mut self, byte: u8) {
        self.bytes.push(byte);
    }

    #[must_use]
    pub fn into_inner(self) -> Vec<u8> {
        self.bytes
    }
}
```

## Decided by tools

A tool settles these on its own; the shipped configuration enables each at the level shown.

| Tool | Lint | Level | Forbids |
|---|---|---|---|
| rustc | `missing_debug_implementations` | deny | a public type without a `Debug` impl |
| clippy | `must_use_candidate` | warn | a pure public function without `#[must_use]` |
