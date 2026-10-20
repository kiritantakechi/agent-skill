# Public API Design: Surface, Signatures, Invariants, Evolution

Scope: everything a downstream crate can see and therefore everything you must keep working. The
shape of the public namespace, what parameters and returns should be, when fields are private, how
to make illegal states unrepresentable, the attribute contracts (`#[must_use]`,
`#[non_exhaustive]`, `#[track_caller]`), which std traits to implement and why, constructor and
builder shape, and which changes are breaking. Naming of these items is in the naming chapter;
error *type* design is in the errors chapter; trait design proper is in the traits chapter.

The organizing fact: within a major version you are not allowed to change any of this. Design as if
you never will be.

Two sources are merged here: the **Rust API Guidelines** (C-CASE, C-CONV, C-COMMON-TRAITS,
C-COLLECT, C-SERDE, C-GENERIC, C-CUSTOM-TYPE, C-STRUCT-PRIVATE, C-STABLE, C-MUST-USE and friends)
and the **empirical shape of `regex`, `ignore`, `grep-searcher`, and `std`**.
## Contents

- **Shape of the public surface**
  - RS-API-01 [M] Keep everything private until proven public
  - RS-API-02 [S] Curate a flat public namespace with `pub use`
  - RS-API-03 [S] Make the crate do one thing
  - RS-API-04 [S] Provide one obvious way to do each thing
  - RS-API-05 [M] Do not expose a dependency's types without adopting its semver
  - RS-API-06 [M] Do not leak a std implementation detail you may want to change
  - RS-API-07 [M] Attach every function to the type it concerns
  - RS-API-08 [M] Treat the crate root documentation as part of the API
  - RS-API-09 [M] Compose the public surface out of types, not out of functions

- **Parameters and return types**
  - RS-API-10 [M] Be generic in what you accept, concrete in what you return
  - RS-API-11 [S] Do not over-genericize
  - RS-API-12 [M] Take `&[T]`, `&str`, `&Path` — never their owned forms
  - RS-API-13 [M] Take ownership only when you keep it
  - RS-API-14 [S] Take `impl Into<String>` when you store, `&str` when you read
  - RS-API-15 [S] Return `impl Iterator` rather than `Vec` where the caller may not need all of it
  - RS-API-16 [S] Return owned data only when the caller needs ownership
  - RS-API-17 [M] Return a struct, not a three-element tuple
  - RS-API-18 [S] Justify every out-parameter with buffer reuse

- **Encapsulation and invariants**
  - RS-API-19 [M] Find the invariant before choosing the methods
  - RS-API-20 [M] Validate once, at construction, and let the type carry the proof
  - RS-API-21 [M] Return the view from an accessor, never the container
  - RS-API-22 [M] Do not hand out `&mut` to invariant-bearing state
  - RS-API-23 [M] Close every public path that can build an invalid instance
  - RS-API-24 [M] Keep every struct field private, including the ones with no invariant
  - RS-API-25 [M] Give the caller the question it is asking, not the field it would have read
  - RS-API-26 [M] Keep tuple-struct fields private too
  - RS-API-27 [M] Make every construction path a named one

- **Type safety**
  - RS-API-28 [S] Newtype anything with a unit, a domain, or a validity condition
  - RS-API-29 [M] Never leave two same-typed parameters adjacent
  - RS-API-30 [M] Replace `bool` parameters with two-variant enums
  - RS-API-31 [S] Prefer an enum to an `Option` whose `None` has meaning
  - RS-API-32 [M] Collapse correlated fields into the sum type they already are
  - RS-API-33 [M] Do not build stringly-typed APIs
  - RS-API-34 [M] Parse strings into types at the boundary
  - RS-API-35 [M] Encode units in types
  - RS-API-36 [S] Use `NonZero*` where zero is invalid
  - RS-API-37 [S] Newtype indices when several index spaces coexist
  - RS-API-38 [M] Model a finite set of states as an enum that lists all of them
  - RS-API-39 [M] Prefer unrepresentable to rejected, and rejected to checked
  - RS-API-40 [M] Give every documented constraint a type that carries it

- **Attributes and contracts**
  - RS-API-41 [S] Derive the full common trait set where semantics allow
  - RS-API-42 [M] Never derive a trait whose semantics are wrong for the type
  - RS-API-43 [M] Treat a derived `Ord` as a documented contract
  - RS-API-44 [S] Choose the `#[default]` variant deliberately
  - RS-API-45 [S] Do not implement `Default` where there is no meaningful default
  - RS-API-46 [M] Decide exhaustiveness deliberately for every public enum
  - RS-API-47 [S] Put `#[must_use]` on pure functions and pending obligations
  - RS-API-48 [S] Give `#[must_use]` a message when the reason is not obvious
  - RS-API-49 [S] Treat `#[inline]` as a cross-crate codegen claim
  - RS-API-50 [S] Use `#[track_caller]` on functions that panic on caller error

- **Standard trait implementations**
  - RS-API-51 [M] Implement `Debug` on every public type
  - RS-API-52 [M] Keep `Debug` for programmers and `Display` for users
  - RS-API-53 [S] Implement `Display` only when there is one obvious rendering
  - RS-API-54 [M] Implement `Clone` where possible and `Copy` where it is also a value
  - RS-API-55 [M] Keep `PartialEq`, `Eq`, `Hash`, and `Ord` consistent
  - RS-API-56 [S] Implement `FromStr` for any type with a canonical textual form
  - RS-API-57 [M] Implement `From` for infallible and `TryFrom` for fallible conversions
  - RS-API-58 [S] Implement `FromIterator`, `Extend`, and `IntoIterator` on collections
  - RS-API-59 [S] Implement `AsRef` and `Borrow` only when the type genuinely is the target
  - RS-API-60 [M] Do not abuse `Deref` for inheritance
  - RS-API-61 [M] Implement `Error` and put it in the public API
  - RS-API-62 [S] Gate `serde` behind an off-by-default feature

- **Constructors, builders, conversions**
  - RS-API-63 [S] Let `new()` take only what the type cannot exist without
  - RS-API-64 [S] Reach for a builder past three optional parameters
  - RS-API-65 [S] Prefer the `&mut self -> &mut Self` builder shape
  - RS-API-66 [S] Name builder setters after the property, without `set_`
  - RS-API-67 [M] Validate in `build()`, not in the setters
  - RS-API-68 [M] Do not provide both a builder and a struct-literal path
  - RS-API-69 [S] Reserve inherent `from_*` for several sources of one type
  - RS-API-70 [M] Mark unchecked constructors `unsafe` or `*_unchecked`

- **Future-proofing and evolution**
  - RS-API-71 [M!] Use `#[non_exhaustive]` where the shape may grow
  - RS-API-72 [S] Do not apply `#[non_exhaustive]` reflexively
  - RS-API-73 [S] Prefer sealing up front to regretting it later
  - RS-API-74 [M] Know which changes are breaking before promising semver
  - RS-API-75 [M] Run `cargo semver-checks` and trust it over intuition
  - RS-API-76 [M] Deprecate before removing, and say what to use instead
  - RS-API-77 [S] Prefer additive evolution; batch the breaking changes

- **Symmetry of the public surface**
  - RS-API-78 [M] Give every operation its inverse, or document why there is none
  - RS-API-79 [M] Keep argument order identical across sibling functions
  - RS-API-80 [M] Give sibling error variants a uniform shape
  - RS-API-81 [M] Choose `Option` or `Result` uniformly for the same kind of absence
  - RS-API-82 [S] Give comparable sibling methods the same receiver
  - RS-API-83 [M] Use one term for one concept across the whole surface

---

## Shape of the public surface

### RS-API-01 [M] Keep everything private until proven public

Start with the smallest surface that lets the intended use cases work.

**Why:** `pub` is a promise of support that you cannot withdraw within a major version;
`pub(crate)` costs nothing and can be promoted the day someone needs it. Growing a surface is a
minor version, shrinking it is a major one — so the asymmetry says start small.

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

### RS-API-02 [S] Curate a flat public namespace with `pub use`

Users should write `grep::Searcher`, not `grep::searcher::internal::Searcher`.

**Why:** internal module structure is an implementation detail, and once it appears in a user's
`use` statement it becomes an API you cannot reorganize. Re-exporting from the root decouples the
two, so you can move the file without a breaking change.

**Check:** read the crate's own doc examples. Does any path have more than one module segment?
Enumerate the re-exports rather than globbing (`references/modules.md` RS-MOD-18).

```rust
// verified
/// The module's surface is what it exports, not what it contains.
mod detail {
    pub(super) fn helper(value: u32) -> u32 {
        value.saturating_mul(2)
    }
}

#[must_use]
pub fn doubled(value: u32) -> u32 {
    detail::helper(value)
}
```

### RS-API-03 [S] Make the crate do one thing

If the README needs "and" twice, split it into a workspace of focused crates with a thin facade.

**Why:** ripgrep's split into `grep-matcher`, `grep-regex`, `grep-searcher`, `grep-printer`, and
the `grep` facade is why each piece is independently usable, testable, and versionable. A monolith
makes every consumer compile everything and accept every dependency.

**Check:** can you describe the crate in one sentence with no conjunction?
(`references/modules.md` RS-MOD-22.)

```rust
// verified
/// The smallest surface that does the job: one entry point, one result type.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Match {
    line: u32,
}

impl Match {
    #[must_use]
    pub fn line(self) -> u32 {
        self.line
    }
}

#[must_use]
pub fn search(haystack: &str, needle: &str) -> Option<Match> {
    haystack
        .lines()
        .position(|line| line.contains(needle))
        .and_then(|index| u32::try_from(index).ok())
        .map(|line| Match { line })
}
```

### RS-API-04 [S] Provide one obvious way to do each thing

**Why:** two constructors that differ only in argument order, or a builder plus an equivalent
seven-argument `new`, force the caller to make a meaningless choice and double the surface you must
keep working. Every duplicate path is also a place the two can drift apart in behaviour.

**Check:** for each pair of functions with overlapping purpose, could one be deleted without loss?
If the answer is "one is more convenient", make it the only one.

### RS-API-05 [M] Do not expose a dependency's types without adopting its semver

**Why:** if `regex::Regex` appears in your signature, a `regex` 2.0 is a breaking change for you
too, and a user already on the other major holds a `Regex` your signature does not accept. Wrap the
type, or re-export it explicitly and document the coupling so users can plan.

**Check:** list the types in your public signatures. Which come from dependencies? For each, is the
coupling deliberate and documented, or accidental?

### RS-API-06 [M] Do not leak a std implementation detail you may want to change

Returning `std::collections::hash_map::Keys<'_, K, V>` pins you to `HashMap` forever.

**Why:** the concrete iterator type names the container. Switching to `BTreeMap`, `IndexMap`, or a
sorted `Vec` then becomes a breaking change for a decision the caller never cared about.
`impl Iterator<Item = &K> + '_` costs nothing and hides it.

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

### RS-API-07 [M] Attach every function to the type it concerns

A free function is right only for an operation that belongs to no type you own
(`fs::read_to_string`) or for the crate's single entry point; everything else has a receiver.

**Why:** methods are discoverable — they appear in autocomplete and on the type's rustdoc page — and
a function that takes your type but sits beside it is hidden from the person holding the value.

**Check:** for each free function, does any parameter have a type you own? Then it is a method on
that type. If several qualify, the first one it would read as a sentence with.

### RS-API-08 [M] Treat the crate root documentation as part of the API

`//!` on `lib.rs` states what the crate is for, shows a complete working example, and links to the
two or three types a new user should read first.

**Why:** it is the most-read page you will ever write and the only one a user sees before deciding
to depend on you. Without it they land in the item index, which is alphabetical and so useless as
an introduction (`references/documentation.md` RS-DOC-02).

**Check:** can someone accomplish the primary use case from docs.rs alone, without opening the
source?

### RS-API-09 [M] Compose the public surface out of types, not out of functions

What a crate exports is a small set of types with methods. A free function at the root is the
exception, and it is one you can justify in a sentence.

**Why:** a crate of thirty loose functions has no centre: the reader must hold the whole list, a new
operation is one more name in a flat namespace nobody watches, and any two functions can drift
apart in naming, argument order, and error type unnoticed (RS-API-79, RS-API-83).

**Check:** list what the crate root exports. What is the ratio of types to free functions? For each
free function, name the type it would be a method on — if you can name one, it belongs there
(RS-API-07).

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

### RS-API-10 [M] Be generic in what you accept, concrete in what you return

Accept `impl AsRef<Path>`, `impl IntoIterator<Item = T>`, `impl Into<String>`; return a named type
or `impl Trait`. A range parameter is `impl RangeBounds<usize>`, which takes every range syntax; a
range a type stores is `core::range::Range` (1.96), which is `Copy`.

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

### RS-API-11 [S] Do not over-genericize

**Why:** each type parameter costs a monomorphization per instantiation, rustdoc every reader must
decode, and an inference hazard at every call site. It pays only when callers really hold different
types (`references/traits.md` RS-TRAIT-38).

**Check:** for each type parameter, list the instantiations that will actually occur. One means it
should be concrete.

### RS-API-12 [M] Take `&[T]`, `&str`, `&Path` — never their owned forms

Not `&Vec<T>`, not `&String`, not `&PathBuf`, not `&Box<T>`.

**Why:** the owned forms deref to the borrowed ones, so the borrowed form accepts strictly more
callers at zero cost — arrays, slices, subslices, string literals, static data. Taking `&Vec<T>`
rejects all of those for no benefit. This is the single most common signature defect in Rust.

**Check:** `rg -n '&Vec<|&String\b|&PathBuf\b|&Box<'` over the public surface.
`clippy::ptr_arg` catches the common cases.

```rust
// fragment — BAD: rejects arrays, slices, literals, and static data
fn longest(words: &Vec<String>) -> Option<&String>;
```

```rust
// fragment — GOOD
fn longest<'a>(words: &[&'a str]) -> Option<&'a str>;
```

### RS-API-13 [M] Take ownership only when you keep it

**Why:** a function that borrows, reads, and drops should take `&T` — taking `T` forces every caller
who still needs the value to clone. Conversely, if you will store it, take it by value: taking `&T`
and cloning internally charges the caller who already had an owned value twice.

**Check:** for each by-value parameter, is it stored or consumed? For each `&T` parameter, is it
cloned in the body?

### RS-API-14 [S] Take `impl Into<String>` when you store, `&str` when you read

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

### RS-API-15 [S] Return `impl Iterator` rather than `Vec` where the caller may not need all of it

**Why:** materialization belongs to whoever knows how much is needed. A `Vec` computes and stores
everything even when the caller wanted `.next()`, and feeding it to another adapter costs a second
allocation (`references/functional.md` RS-FUNC-18).

**Check:** does the caller immediately `.iter()`, `.into_iter()`, or index only the first element?

```rust
// verified
/// Returning `impl Iterator` keeps the concrete adapter chain private.
pub fn non_empty(lines: &[String]) -> impl Iterator<Item = &str> {
    lines
        .iter()
        .map(String::as_str)
        .filter(|line| !line.is_empty())
}
```

### RS-API-16 [S] Return owned data only when the caller needs ownership

**Why:** a method that has the `&str` in hand and returns `String` charges every caller for an
allocation they may not want. Where the answer is only sometimes computed, `Cow<'_, str>` keeps the
borrowed path free (`references/ownership.md` RS-OWN-15).

**Check:** does the function allocate on a path where it could have returned a borrow of `self`?

### RS-API-17 [M] Return a struct, not a three-element tuple

**Why:** `(usize, usize, bool)` is unreadable and silently transposable, since
`let (start, end, empty) = m;` compiles just as well with the first two swapped. Named accessors
cannot be misread, and a fourth piece of information is one more method, not a changed arity.

**Check:** grep public return types for tuples of arity three or more, and for two-tuples whose
elements share a type.

### RS-API-18 [S] Justify every out-parameter with buffer reuse

`&mut Vec<T>` to be filled is justified when reuse is the point, as in `Read::read_to_end`.

**Why:** out-parameters break composition — the result cannot be fed into an adapter, and the
function cannot be used in an expression. Reuse across a loop is a real reason
(`references/ownership.md` RS-OWN-14); "it was easier to write" is not.

**Check:** is the buffer reused across calls by the intended caller? Say so in the docs and name the
parameter `buf` or `out`.

## Encapsulation and invariants

### RS-API-19 [M] Find the invariant before choosing the methods

Any constraint the type maintains — a sorted `Vec`, a cached length that must match, a value
confined to a range, an index into a sibling field — is a contract the type owes, and it decides
which methods may exist.

**Why:** every field is private either way (RS-API-24), so privacy decides nothing; the invariant
decides which operations may exist. Unnamed, the next `&mut` method breaks it; named, it tells you
construction is fallible, the field has no setter, and which accessor would leak it (RS-API-22).

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

### RS-API-20 [M] Validate once, at construction, and let the type carry the proof

**Why:** a `Port(u16)` whose constructor rejects zero means no downstream function re-checks or
*forgets* to re-check, and the invariant lives in one place instead of at every entry point. This
is `references/functional.md` RS-FUNC-47 seen from the type's side.

**Check:** grep for the same validation appearing in more than one function. That repetition is a
constructor that has not been written.

### RS-API-21 [M] Return the view from an accessor, never the container

`fn buffer(&self) -> &[u8]`, never `fn buffer(&self) -> &Vec<u8>`.

**Why:** an accessor returning `&Vec<u8>` publishes `Vec` exactly as a public field would, so
switching to `SmallVec`, a ring buffer, or a memory map still breaks every caller. `&[u8]` names
what the caller may do, not what you store, and all three can produce it (RS-CORE-07).

**Check:** grep accessor return types for `&Vec<T>`, `&String`, and `&PathBuf` — the slice, `&str`,
and `&Path` say the same thing without naming the container. A map or a set has no borrowed view in
std, so the answer there is not a different return type but a smaller question: `get`, `contains`,
or an iterator (RS-API-25).

### RS-API-22 [M] Do not hand out `&mut` to invariant-bearing state

`fn entries_mut(&mut self) -> &mut Vec<Entry>` lets a caller violate sorting, uniqueness, or a
cached length.

**Why:** a `&mut` to the inner collection is a public licence to break every invariant the type
maintains, and no amount of documentation prevents it. Targeted mutators (`insert`, `remove`,
`retain`) can maintain the invariant; a raw `&mut` cannot.

**Check:** for each `&mut`-returning accessor, what invariant could a caller break with it? If the
answer is "none", the accessor is still wrong: hand out the operation the caller came for, not the
collection it would have reached through (RS-API-25).

### RS-API-23 [M] Close every public path that can build an invalid instance

**Why:** private fields plus a constructor that takes every field unvalidated is not encapsulation —
it is public fields with extra typing. The point is that the type cannot be constructed in a bad
state, not that the fields have a keyword in front of them.

**Check:** can a caller reach an invalid instance through any public path — a constructor, a setter,
a `Deserialize` impl, a `Default`? `serde` in particular bypasses your constructor unless you use
`#[serde(try_from = "…")]`.

### RS-API-24 [M] Keep every struct field private, including the ones with no invariant

There is no "pure data bag" exemption. A struct whose fields are independent today is still a
struct whose representation you have published. The single exception is a type whose layout is
already the contract — `#[repr(C)]` or `extern` types crossing an ABI boundary
(`references/unsafe.md` RS-UNSAFE-14). A constructor or builder replaces the struct literal, a
method replaces field access, and `#[non_exhaustive]` plus `Default` replaces
`..Default::default()`.

**Why:** a public field commits to a *representation*: `pub threads: usize` cannot later become
`NonZeroUsize` or a computed value without a major version, and invariants usually arrive later.
What public fields buy, methods give back; the representation they spend is gone for good.

**Check:** `rg -n 'pub [a-z_]*:' -g '*.rs' src/` over struct bodies. Every hit that is
not on a `#[repr(C)]` type is a defect, whatever invariant it does or does not carry today.

```rust
// verified
use std::num::NonZeroUsize;

/// Private fields even here: nothing about this pair is an invariant today.
#[derive(Debug, Clone)]
#[non_exhaustive]
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

### RS-API-25 [M] Give the caller the question it is asking, not the field it would have read

A method names the decision — `thread_count()`, `is_saturated()`, `remaining()` — rather than
mirroring storage one accessor per field.

**Why:** a row of `fn x(&self) -> T { self.x }` pins the representation as a public field would and
hands the caller arithmetic that belongs to the type. A named question can be answered differently
later, and its logic lives once, beside the data (`references/ownership.md` RS-OWN-06).

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

### RS-API-26 [M] Keep tuple-struct fields private too

`struct Port(u16)` with an inherent accessor, never `struct Port(pub u16)`.

**Why:** `.0` is a public field that also names nothing, so it adds an unreadable call site to every
cost of RS-API-24. The newtype exists so the representation can change, to `NonZeroU16` or a packed
field, and `pub` on the inner value spends exactly that freedom.

**Check:** `rg -n 'struct [A-Za-z_]*\(pub ' -g '*.rs' src/`. Every hit is a defect.

```rust
// verified
/// The inner value stays private, so the representation can still change.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub struct Port(u16);

impl Port {
    #[must_use]
    pub fn new(raw: u16) -> Self {
        Self(raw)
    }

    #[must_use]
    pub fn get(self) -> u16 {
        self.0
    }
}
```

### RS-API-27 [M] Make every construction path a named one

A struct literal is not available once fields are private, so the type states how it is built:
`new`, a named alternative constructor, a builder, or a `TryFrom`.

**Why:** a named entry point is where validation lives (RS-API-20), where defaults are decided, and
where a later invariant is enforced without touching a call site. Every instance traces back to a
function you can grep, named for its starting state (`references/naming.md` RS-NAME-22).

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

### RS-API-28 [S] Newtype anything with a unit, a domain, or a validity condition

`UserId(u64)`, `Bytes(u64)`, `Utf8Path`.

**Why:** the compiler then catches argument transposition, which tests usually do not, because a
transposed pair of `u64`s produces plausible wrong answers rather than a crash. The wrapper is
zero-cost and usually `#[repr(transparent)]`.

**Check:** list the primitive-typed fields and parameters in the public API. For each, is there a
different value of the same primitive type that would be nonsense here?

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

### RS-API-29 [M] Never leave two same-typed parameters adjacent

`fn copy(src: u32, dst: u32)` will be called backwards.

**Why:** nothing in the type system or the call site distinguishes them, so the mistake compiles,
passes review, and shows up as data corruption. Newtypes or a struct parameter make the error
impossible rather than unlikely.

**Check:** scan every public signature for two consecutive parameters of the same primitive type.
This is a mechanical grep and it finds real bugs.

```rust
// verified
/// Newtypes keep two `u32`s from being transposed at the call site.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Width(u32);

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Height(u32);

impl Width {
    #[must_use]
    pub fn new(cells: u32) -> Self {
        Self(cells)
    }

    #[must_use]
    pub fn get(self) -> u32 {
        self.0
    }
}

impl Height {
    #[must_use]
    pub fn new(rows: u32) -> Self {
        Self(rows)
    }

    #[must_use]
    pub fn get(self) -> u32 {
        self.0
    }
}

#[must_use]
pub fn area(width: Width, height: Height) -> u64 {
    u64::from(width.get()) * u64::from(height.get())
}
```

### RS-API-30 [M] Replace `bool` parameters with two-variant enums

**Why:** `search(path, true, false)` is unreadable at the call site and cannot be checked by anyone
reviewing the diff. The enum costs one declaration and makes every call self-documenting, with no
runtime difference.

**Check:** grep public signatures for `: bool`. Each one is either a two-variant enum or, if there
are three or more of them, an options struct or a policy closure
(`references/functional.md` RS-FUNC-42).

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

### RS-API-31 [S] Prefer an enum to an `Option` whose `None` has meaning

**Why:** `Option<Duration>` for a timeout hides whether `None` means "no timeout" or "use the
default" — and both readings are common, so users guess. `enum Timeout { None, Default,
After(Duration) }` states it and makes the third case possible.

**Check:** for each public `Option<T>`, is `None` genuinely just absence? If it carries a policy,
name it.

### RS-API-32 [M] Collapse correlated fields into the sum type they already are

Two `Option`s where exactly one is always `Some`; a `bool` plus a field only meaningful when it is
set.

**Why:** the correlation is an invariant the compiler cannot see, so every reader must learn it and
every path must handle the impossible combination, usually with an `unwrap` or an `unreachable!`
(`references/errors.md` RS-ERR-35). The sum type deletes those branches.

**Check:** for each pair of fields, is there a combination of values that cannot legally occur? That
pair is an enum.

### RS-API-33 [M] Do not build stringly-typed APIs

A parameter accepting `"json" | "text" | "csv"`; a config keyed by arbitrary strings; errors
returned as `String`.

**Why:** every mistake is deferred to runtime, nothing is discoverable from the signature, no
refactoring tool can rename anything, and there is no exhaustiveness checking when a fourth format
appears. The enum costs one declaration.

**Check:** grep public signatures for `&str` and `String` parameters. For each, is the set of
accepted values finite and known? Then it is an enum.

### RS-API-34 [M] Parse strings into types at the boundary

Where a string genuinely comes from outside — a CLI flag, a config file, a request — parse it into
the enum via `FromStr` at the edge, and let nothing downstream see the string.

**Why:** this is parse-don't-validate applied to the API surface. If the parsed type only exists
inside the parser, every downstream function re-derives the meaning, and they will not all agree
(`references/functional.md` RS-FUNC-47).

**Check:** how deep does the raw `&str` travel from the entry point? Anything past the first layer
is a missing type.

### RS-API-35 [M] Encode units in types

`Duration` rather than `timeout_ms: u64`; a `ByteSize` newtype rather than `size: u64`.

**Why:** unit confusion is a bug class the type system eliminates completely — the compiler rejects
passing a byte count where a millisecond count belongs, and no test suite reliably catches the
transposition (`references/naming.md` RS-NAME-30).

**Check:** any numeric parameter whose correct value depends on a unit the signature does not state.

### RS-API-36 [S] Use `NonZero*` where zero is invalid

`NonZeroUsize`, `NonZeroU32`.

**Why:** it removes a runtime check, documents the contract in the signature, and makes
`Option<NonZeroU32>` the same size as `u32` thanks to the niche. The conversion cost is one
`try_from` at the boundary, which you needed anyway.

**Check:** grep for functions that begin by rejecting a zero argument. Each is a `NonZero`.

### RS-API-37 [S] Newtype indices when several index spaces coexist

`NodeId`, `EdgeId`, `ByteOffset`, `CharOffset`.

**Why:** mixing byte offsets and char offsets is the classic Unicode bug, and it is a type error
waiting to be declared. The same applies to indices into two parallel arenas — the compiler can
distinguish them the moment you let it (`references/ownership.md` RS-OWN-23).

**Check:** does the crate hold more than one `Vec` indexed by `usize`? Those are distinct types.

### RS-API-38 [M] Model a finite set of states as an enum that lists all of them

Protocol phases, parser modes, retry outcomes, file kinds. Not an integer with named constants, not
a string tag, not a group of booleans.

**Why:** an enum closes the set, so `match` proves every state handled and a new state breaks every
incomplete site at compile time. The alternatives defer that to runtime: an integer admits values
the set never had, a string admits typos, and *n* booleans admit 2ⁿ combinations (RS-API-32).

**Check:** for each state-like value, can you name a representable value that is not a legal
state? Then the type is wrong. Count the booleans that travel together — three of them is eight
states, and you meant three.

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

### RS-API-39 [M] Prefer unrepresentable to rejected, and rejected to checked

Three tiers, in order: the type cannot express the bad value; the constructor refuses it; a runtime
check catches it. Reach for the earliest tier the situation allows.

**Why:** each tier costs more than the last: unrepresentable costs nothing and cannot be forgotten,
rejection costs one check per value (RS-API-20), and a runtime check costs one per use at every
site. A later tier leaves defensive branches nobody can prove unreachable, so none is ever deleted.

**Check:** for each validation in the body of a function, ask which tier it belongs to and whether
an earlier tier was available. A check that could have been a `NonZeroUsize` is a defect
(RS-API-36).

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

### RS-API-40 [M] Give every documented constraint a type that carries it

A constraint stated in prose — "must be non-empty", "must be sorted", "must be a valid UTF-8
path", "in the range 1..=100" — is a type you have not written yet.

**Why:** prose is unchecked, invisible at the call site, and re-verified by every reader unsure it
still holds. As a type, the constraint is enforced once at the boundary, and a function taking
`NonEmpty<T>` has no empty case left to document, test, or handle.

**Check:** grep doc comments for "must", "should be", "expects", and range notation. Each hit is
either a type you have not introduced or a `# Panics` section you owe (`RS-DOC-13`).

```rust
// verified
/// "Must be non-empty" is carried by the type, so callers get a proof.
#[derive(Debug, Clone)]
pub struct NonEmpty<T> {
    head: T,
    tail: Vec<T>,
}

impl<T> NonEmpty<T> {
    /// # Errors
    /// Returns [`Empty`] when `items` has no elements.
    pub fn new(items: Vec<T>) -> Result<Self, Empty> {
        let mut it = items.into_iter();
        let head = it.next().ok_or(Empty)?;
        Ok(Self {
            head,
            tail: it.collect(),
        })
    }

    /// Element count, which is never zero.
    #[must_use]
    pub fn count(&self) -> usize {
        self.tail.len() + 1
    }

    #[must_use]
    pub fn first(&self) -> &T {
        &self.head
    }
}

/// The input sequence was empty.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Empty;
```

## Attributes and contracts

### RS-API-41 [S] Derive the full common trait set where semantics allow

`Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash, Default`.

**Why:** C-COMMON-TRAITS. A missing derive is invisible until a user needs it, at which point they
cannot add it themselves because of the orphan rule — their only options are a newtype wrapper or a
pull request. Adding a derive later is not breaking; omitting it is a wall.

**Check:** for each public type, which of the nine are missing, and is each omission deliberate?

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

### RS-API-42 [M] Never derive a trait whose semantics are wrong for the type

**Why:** deriving `PartialEq` on a struct with a cache field makes two logically equal values
compare unequal — and the bug surfaces in a `HashMap` lookup three modules away. The derive is
convenient precisely because it is thoughtless, which is the hazard.

**Check:** for each derived `PartialEq`/`Hash`/`Ord`, does every field participate in identity? Any
cache, timestamp, or arena handle is a no.

### RS-API-43 [M] Treat a derived `Ord` as a documented contract

**Why:** `#[derive(Ord)]` fixes the ordering to the declaration order of the fields, permanently.
Reordering fields for layout or readability then silently changes the sort order of every user's
data. If the ordering matters, document it; if it is arbitrary, do not derive `Ord`.

**Check:** does the type's rustdoc say what the ordering means? If not, either write it or remove
the derive.

### RS-API-44 [S] Choose the `#[default]` variant deliberately

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

### RS-API-45 [S] Do not implement `Default` where there is no meaningful default

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

### RS-API-46 [M] Decide exhaustiveness deliberately for every public enum

**Why:** adding a variant to a public enum without `#[non_exhaustive]` is a breaking change, so the
attribute is a decision you make once and live with. Making it by default in either direction is
how crates end up either unable to grow or unable to be matched (RS-API-71, RS-API-72).

**Check:** for each public enum, is the variant set genuinely closed? Write the answer in the
rustdoc.

```rust
// verified
/// The enum makes the states exhaustive, so no `else` branch can be forgotten.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Outcome {
    Matched { line: u32 },
    Skipped,
    Failed,
}

#[must_use]
pub fn describe(outcome: Outcome) -> &'static str {
    match outcome {
        Outcome::Matched { .. } => "matched",
        Outcome::Skipped => "skipped",
        Outcome::Failed => "failed",
    }
}
```

### RS-API-47 [S] Put `#[must_use]` on pure functions and pending obligations

Pure computations whose return value is the point; guards, builders, futures, and iterator adapters.

**Why:** ignoring the result of `Builder::case_insensitive(true)` on a by-value builder is a silent
no-op — the configured value is dropped and the original is used. The compiler can catch it for the
cost of one attribute.

**Check:** for each public function, would discarding the return value ever be correct? If never,
mark it.

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

### RS-API-48 [S] Give `#[must_use]` a message when the reason is not obvious

`#[must_use = "iterators are lazy and do nothing unless consumed"]`.

**Why:** the default warning says the value is unused, which the author can already see. The message
says *what will silently not happen*, which is the information they are missing.

**Check:** would a competent user understand the consequence from the default message alone?

### RS-API-49 [S] Treat `#[inline]` as a cross-crate codegen claim

**Why:** since 1.75 rustc makes the smallest non-generic functions inlinable downstream on its own,
and generic ones always were; anything larger needs `#[inline]` to cross the boundary. Applied
wholesale it bloats the binary and slows compilation (`references/performance.md` RS-PERF-31).

**Check:** is the function non-generic, small, and on a hot path in another crate? Otherwise remove
the attribute.

### RS-API-50 [S] Use `#[track_caller]` on functions that panic on caller error

**Why:** without it the panic message points at your internals, so the user sees a location inside
your crate for a mistake in theirs. `Vec::remove` and `slice` indexing both use it, which is why
their panics are actionable.

**Check:** for each documented panic (`references/errors.md` RS-ERR-34), does the message name the
caller's line?

## Standard trait implementations

### RS-API-51 [M] Implement `Debug` on every public type

No exceptions for "internal" types that appear in a public struct.

**Why:** a missing `Debug` poisons `#[derive(Debug)]` for every type containing it, makes
`assert_eq!` unusable in users' tests, and makes the value invisible in a debugger and in `tracing`
fields. The blast radius is far larger than the one type.

**Check:** `missing_debug_implementations` at deny in `[lints.rust]`
(`references/build.md` RS-BUILD-25). Manual impls are fine; absence is not.

### RS-API-52 [M] Keep `Debug` for programmers and `Display` for users

**Why:** `Debug` output may change at any time and favours completeness; `Display` is part of the
contract and favours clarity. A `Display` that delegates to `Debug` publishes internal structure,
the defect in `references/errors.md` RS-ERR-42.

**Check:** does any `Display` impl call `{:?}`? Does any `Debug` impl omit a field to look tidier?

### RS-API-53 [S] Implement `Display` only when there is one obvious rendering

**Why:** `Display` takes no options, so if there are two reasonable renderings — short and verbose,
coloured and plain, absolute and relative — the trait forces you to pick one and users must
reimplement the other. Explicit methods can take arguments.

**Check:** are there two ways a user would reasonably want to print this? Then ship two methods and
skip `Display`.

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

### RS-API-54 [M] Implement `Clone` where possible and `Copy` where it is also a value

**Why:** `Clone` is nearly always implementable, and its absence blocks patterns you did not
anticipate. `Copy` promises the type will never own a heap allocation, and removing it is breaking:
every implicit copy becomes a move, and code that reuses the value stops compiling.

**Check:** could this type ever grow a `String`, a `Vec`, or a handle? Then do not make it `Copy`
today.

### RS-API-55 [M] Keep `PartialEq`, `Eq`, `Hash`, and `Ord` consistent

Equal values must hash equally; `Ord` must agree with `PartialOrd` and `Eq`.

**Why:** inconsistency fails silently and far from the impl: a `HashMap` misses a key looked up by
an equal one, a `BTreeMap` loses entries, `BTreeMap::append` may panic (1.96), and a derived
`PartialOrd` beside a derived `Ord` answers with `cmp` (1.98), not with each field's `partial_cmp`.

**Check:** if you hand-implement one of the four, review all four in the same commit. Property-test
the laws (`references/testing.md` RS-TEST-22).

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

### RS-API-56 [S] Implement `FromStr` for any type with a canonical textual form

**Why:** it makes `"1.2.3".parse::<Version>()` work and plugs into every argument parser and config
deserializer without them knowing your type. An inherent `parse` works only for callers who read
your docs (`references/naming.md` RS-NAME-23).

**Check:** does the type have a textual form used in config, CLI flags, or serialization?

### RS-API-57 [M] Implement `From` for infallible and `TryFrom` for fallible conversions

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

### RS-API-58 [S] Implement `FromIterator`, `Extend`, and `IntoIterator` on collections

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

### RS-API-59 [S] Implement `AsRef` and `Borrow` only when the type genuinely is the target

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

### RS-API-60 [M] Do not abuse `Deref` for inheritance

**Why:** `Deref` is for smart pointers (`Box`, `Arc`, `MutexGuard`) and transparent newtypes.
Using it to inherit methods produces confusing autocompletion, method resolution that surprises
everyone, no way to override, and a type whose API changes when the inner type's does.

**Check:** does the `Deref` target have methods you would not want on the outer type? Then it is
inheritance, not a smart pointer.

### RS-API-61 [M] Implement `Error` and put it in the public API

With a correct `source()`; `core::error::Error` in no-std, stable since 1.81.

**Why:** the error type is part of every fallible signature, so it is public whether you documented
it or not, and every reporting layer walks `source()` (`references/errors.md` RS-ERR-05).

**Check:** is the error type reachable and nameable from outside the crate, and does it implement
`Error`?

```rust
// verified
use std::io;

/// `#[source]` builds the chain; the reporter walks it rather than re-printing it.
#[derive(Debug, thiserror::Error)]
#[error("could not open the index")]
pub struct OpenFailed {
    #[source]
    source: io::Error,
}

impl OpenFailed {
    #[must_use]
    pub fn new(source: io::Error) -> Self {
        Self { source }
    }
}
```

### RS-API-62 [S] Gate `serde` behind an off-by-default feature

And derive with `#[serde(deny_unknown_fields)]` for config types.

**Why:** `serde` and `serde_derive` are a substantial compile-time cost for users who do not
serialize, and `deny_unknown_fields` turns a silently-ignored typo in a config file into an error
the user can act on (`references/build.md` RS-BUILD-16).

**Check:** is `serde` in `[dependencies]` without `optional = true`? Does a misspelled config key
produce an error or a silent default?

## Constructors, builders, conversions

### RS-API-63 [S] Let `new()` take only what the type cannot exist without

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

### RS-API-64 [S] Reach for a builder past three optional parameters

Or when construction is fallible in several distinct ways, or when options will grow.

**Why:** below that threshold an options struct with `Default` and a few `#[must_use]` setters is
lighter and more transparent. Above it, positional arguments become unreadable and every addition is
a breaking change.

**Check:** count the optional parameters. Three is the line; the direction of travel matters more
than the exact count.

```rust
// verified
use std::borrow::Cow;

/// Two-variant enums, so no option is set with a bare `true` (RS-API-30).
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

### RS-API-65 [S] Prefer the `&mut self -> &mut Self` builder shape

As used by `SearcherBuilder` and `RegexBuilder`, terminating in `fn build(&self) -> Result<T, E>`.

**Why:** it works with a builder stored in a struct, it can be configured in a loop, and it does not
require move gymnastics when a setter is called conditionally. The by-value `self -> Self` shape is
fine for small one-shot builders — mark it `#[must_use]` (RS-API-47).

**Check:** can a caller configure the builder inside an `if` without reassigning it?

### RS-API-66 [S] Name builder setters after the property, without `set_`

`.case_insensitive(true)`, `.max_depth(Some(3))`, `.threads(4)`.

**Why:** the builder call chain reads as a description of the configuration, and `set_` on every
line is noise. It also matches the convention every major crate uses, so users guess correctly
(`references/naming.md` RS-NAME-18).

**Check:** grep the builder for `fn set_`.

### RS-API-67 [M] Validate in `build()`, not in the setters

**Why:** setters that validate make the result depend on the order options were set — a pattern that
is invalid until a later setter fixes it becomes an error the caller cannot avoid. Validating once
in `build()` lets callers configure in any order and produces one coherent error.

**Check:** does any setter return `Result`, or panic? Move that check to `build()`.

### RS-API-68 [M] Do not provide both a builder and a struct-literal path

**Why:** the builder becomes a lie the moment someone bypasses it, and every invariant `build()`
enforces is now unenforced on the other path. This is RS-API-23 in a different costume.

**Check:** are the built type's fields public, or is there a `From<Options>` that skips validation?

### RS-API-69 [S] Reserve inherent `from_*` for several sources of one type

`from_utf8`, `from_utf8_lossy`, `from_raw_parts`.

**Why:** `From` can only be implemented once per source type, so genuinely distinct conversions from
the same input need names. Everything else should be the trait, so callers get `.into()` and `?`
(`references/naming.md` RS-NAME-23).

**Check:** for each inherent `from_*`, is there another conversion from the same input type?

### RS-API-70 [M] Mark unchecked constructors `unsafe` or `*_unchecked`

And document the precondition in a `# Safety` section.

**Why:** a constructor that skips validation is the right tool for a caller who has validated and a
silent source of invalid values for one who has not. The name and the keyword make the difference
visible at the call site (`references/unsafe.md` RS-UNSAFE-04).

**Check:** does any safe constructor skip a check that the normal one performs?

## Future-proofing and evolution

### RS-API-71 [M!] Use `#[non_exhaustive]` where the shape may grow

On public enums whose variant set may grow and public structs whose field set may grow.
*Relaxed form:* internal crates within one workspace, where you control every consumer, can omit it.

**Why:** it costs downstream users a wildcard arm and a constructor call, and it buys you the
ability to ship additions as minor versions for the life of the crate. Without it, every new variant
is a major release — which in practice means the variant gets smuggled into an existing one instead.

**Check:** for each public enum and struct, could a new case or field plausibly appear? Protocols,
parsers, error types, and config structs almost always can.

```rust
// verified
/// `#[non_exhaustive]` keeps adding a field or variant a minor version bump.
#[derive(Debug, Clone, Copy, Default)]
#[non_exhaustive]
pub struct Limits {
    max_depth: u32,
}

impl Limits {
    #[must_use]
    pub fn with_max_depth(max_depth: u32) -> Self {
        Self { max_depth }
    }

    #[must_use]
    pub fn max_depth(self) -> u32 {
        self.max_depth
    }
}

#[derive(Debug, Clone, Copy)]
#[non_exhaustive]
pub enum Mode {
    Fast,
    Thorough,
}
```

### RS-API-72 [S] Do not apply `#[non_exhaustive]` reflexively

**Why:** on a genuinely closed enum — `enum Endianness { Big, Little }` — it removes the caller's
exhaustiveness checking and gains nothing, because there will never be a third variant. The wildcard
arm they are forced to write is where a future bug hides.

**Check:** can you name a plausible third variant? If not, leave it exhaustive and say so in the
rustdoc.

### RS-API-73 [S] Prefer sealing up front to regretting it later

**Why:** adding a defaulted method to an unsealed trait is technically breaking — it can conflict
with an inherent method on a downstream type. Sealing after publication is unambiguously breaking.
The decision is cheap before release and expensive after.

**Check:** at release time, for each public trait: extension point, or enumeration?

### RS-API-74 [M] Know which changes are breaking before promising semver

Breaking: adding a type parameter, changing a concrete return type, narrowing a bound, adding a
non-defaulted trait method, removing a derive, making a public item private. Not breaking: widening
a bound, adding an inherent method, adding a variant to a `#[non_exhaustive]` enum, adding a
defaulted method to a sealed trait.

**Why:** the categories are not intuitive — several changes that look additive break callers — and a
break shipped as a minor version fails every downstream build that trusted the version number.

**Check:** before tagging, classify every change in the diff. If you are unsure, RS-API-75 is the
answer.

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

### RS-API-75 [M] Run `cargo semver-checks` and trust it over intuition

**Why:** it catches removed impls, narrowed bounds, changed variant shapes, and newly private items
that human review misses — and it does so mechanically, on every release, without anyone having to
remember RS-API-74.

**Check:** is it in CI on release branches (`references/build.md` RS-BUILD-34)? A green run
is a claim you can make; intuition is not.

### RS-API-76 [M] Deprecate before removing, and say what to use instead

`#[deprecated(since = "1.4.0", note = "use `Searcher::search_reader` instead")]`.

**Why:** the note is the whole value. A deprecation that says only "deprecated" leaves the user to
search the changelog, and many will simply pin the old version. Keep the item for at least one minor
cycle so upgraders get a warning rather than a compile error.

**Check:** does every `#[deprecated]` carry both `since` and a `note` naming the replacement?

### RS-API-77 [S] Prefer additive evolution; batch the breaking changes

**Why:** every major version is a migration cost on every user, and not all of them pay it: the
ecosystem splits across majors whose types do not interoperate. Batching the necessary breaks pays
that cost once instead of three times, as `regex` and `rand` do.

**Check:** does the release contain exactly one breaking change that could have waited? Is there a
migration section in the changelog (`references/build.md` RS-BUILD-12)?

## Symmetry of the public surface

### RS-API-78 [M] Give every operation its inverse, or document why there is none

If a type can be built from bytes it should be convertible back to them; `insert` implies
`remove`, `push` implies `pop`, `open` implies `close`, `encode` implies `decode`, `subscribe`
implies `unsubscribe`.

**Why:** a caller who learns half a pair looks for the other half. A genuine absence usually means
something — the operation is lossy, irreversible, or belongs to another type — and silence makes
the caller assume an oversight and work around it.

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

### RS-API-79 [M] Keep argument order identical across sibling functions

If `copy(src, dst)` takes source first, then `move`, `link`, and `render` in the same module do
too. Fix the order once per crate and never vary it.

**Why:** siblings are called from the same code, and the reader generalizes from the first one they
learn. When the types match, the compiler cannot catch an inconsistent order, so it becomes a
silent argument swap in code that looks right.

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

### RS-API-80 [M] Give sibling error variants a uniform shape

Variants of one error enum carry comparable context: if `Read` records the path, `Write` records
it too. Do not mix one variant with four fields and one with none unless the difference is real.

**Why:** the caller writes one `match` over all the variants, and when some carry a path and some
do not, the reporting code grows a special case per deficient variant. Uniform shape lets one
function render them all (`RS-ERR-23`).

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

### RS-API-81 [M] Choose `Option` or `Result` uniformly for the same kind of absence

Within one type, "not found" is always `Option` or always `Result` — never `get` returning
`Option` while `lookup` returns `Result<_, NotFound>` for the same condition.

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

### RS-API-82 [S] Give comparable sibling methods the same receiver

Methods doing comparable work take comparable receivers: if `len` takes `&self`, `capacity`
does too; if one builder step takes `self`, they all do.

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

### RS-API-83 [M] Use one term for one concept across the whole surface

One concept gets one word, everywhere: not `path` here and `file` there for the same argument,
nor `id`, `key`, and `handle` for one identifier.

**Why:** synonyms make the reader ask whether the difference is meaningful, and they have to read
the implementation to find out that it is not. It also defeats search: nobody can find every site
that touches the concept if it is spelled three ways (`RS-NAME-42`).

**Check:** list the nouns in the public surface and group them by referent. Any group with more than
one spelling needs a decision and a rename.

```rust
// verified
use std::path::Path;

/// One concept, one word: it is `path` in every signature, never `file` in some.
#[must_use]
pub fn is_hidden(path: &Path) -> bool {
    path.file_name()
        .and_then(|name| name.to_str())
        .is_some_and(|name| name.starts_with('.'))
}

#[must_use]
pub fn parent_of(path: &Path) -> Option<&Path> {
    path.parent()
}
```
