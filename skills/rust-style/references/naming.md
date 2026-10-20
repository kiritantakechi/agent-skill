# Naming: Casing, Conversions, Word Order, Generics

Scope: how identifiers are cased and worded, the cost contract carried by the `as_`/`to_`/`into_`
prefixes, getter and predicate shape, how iterators and their types are named, how crates, modules,
features, and files are named, and how generic parameters, lifetimes, and associated types are
spelled. Semantics of the things being named live elsewhere: what a constructor should *take* is in
the API chapter, error-type *design* in the errors chapter, module *boundaries* in the structure
chapter, and feature *semantics* in the Cargo chapter.

Two sources are merged here: the **Rust API Guidelines** naming chapter (C-CASE, C-CONV, C-GETTER,
C-ITER, C-ITER-TY, C-WORD-ORDER, C-FEATURE), quoted in substance where it is normative, and the
**empirical conventions of `std`, `regex`, `ignore`, and `ripgrep`**. Where they are silent, the
tie-break is section 3 of `SKILL.md`.
## Contents

- **Casing**
  - RS-NAME-01 [M] Apply the casing convention mechanically
  - RS-NAME-02 [M] Capitalize acronyms as ordinary English words
  - RS-NAME-03 [M] Let Cargo translate between package and crate names
  - RS-NAME-04 [S] Never prefix or suffix a crate with `rust`
  - RS-NAME-05 [S] Keep crate names short, lowercase, and pronounceable
  - RS-NAME-06 [M] Name a module for its concept; never `utils`, `helpers`, `common`
  - RS-NAME-07 [M] Name a feature for the capability, not the dependency
  - RS-NAME-08 [S] Do not prefix a feature with `use-`, `with-`, or `enable-`
  - RS-NAME-09 [M] Do not repeat the enum's name in its variants
  - RS-NAME-10 [S] Name constants for the quantity, with the unit as a suffix
  - RS-NAME-11 [S] Give a type parameter a real name once the roles stop being obvious
  - RS-NAME-12 [M] Name the file after the module, without re-stating the directory

- **Conversions and access**
  - RS-NAME-13 [M] `as_` is a free borrowed view
  - RS-NAME-14 [M] `to_` costs something
  - RS-NAME-15 [M] `into_` consumes the receiver
  - RS-NAME-16 [M] Do not use a conversion prefix for a computation
  - RS-NAME-17 [M] Getters omit `get_`
  - RS-NAME-18 [M] Match the getter to the field, and suffix the mutable variant `_mut`
  - RS-NAME-19 [M] Mark fallible conversions `try_`
  - RS-NAME-20 [M] Use the three canonical iterator constructor names
  - RS-NAME-21 [S] Name an iterator type after the method that produces it
  - RS-NAME-22 [S] Name secondary constructors `with_*` / `from_*`, never `new_with_*`
  - RS-NAME-23 [M!] Prefer a `From`/`TryFrom`/`FromStr` impl to an inherent `from_*`
  - RS-NAME-24 [M] Predicates read as questions and return `bool`

- **Words and word order**
  - RS-NAME-25 [S] Verbs do something; nouns give something
  - RS-NAME-26 [S] Follow `std`'s word order, and extend by suffix
  - RS-NAME-27 [M] One term, one meaning, crate-wide
  - RS-NAME-28 [S] Spell names out; abbreviate only where the abbreviation is the standard word
  - RS-NAME-29 [S] Restrict single-letter locals to short, genuinely generic bindings
  - RS-NAME-30 [M!] Put the unit in the type; failing that, in the name
  - RS-NAME-31 [S] Name the positive; convert negations once, at the boundary
  - RS-NAME-32 [S] Name a trait for the capability it grants
  - RS-NAME-33 [M] Never suffix a name with the language construct
  - RS-NAME-34 [S] Apply role suffixes consistently or not at all
  - RS-NAME-35 [M] Pick one error-type spelling per crate
  - RS-NAME-36 [S] Name a test for the behaviour it pins

- **Generic parameters and lifetimes**
  - RS-NAME-37 [S] Use the conventional single letters where the role is universal
  - RS-NAME-38 [S] Name a lifetime for the source of the borrow once several coexist
  - RS-NAME-39 [M] Never restate the kind in a parameter's name
  - RS-NAME-40 [S] Spell const generic parameters in `SCREAMING_SNAKE_CASE`
  - RS-NAME-41 [S] Name an associated type for the thing it produces
  - RS-NAME-42 [S] Name a generic parameter for its bound in a crowded signature

- **Symmetry of names**
  - RS-NAME-43 [M] Name the two halves of a pair symmetrically
  - RS-NAME-44 [S] Keep the same word order across parallel names

---

## Casing

### RS-NAME-01 [M] Apply the casing convention mechanically

`UpperCamelCase` for types, traits, and enum variants. `snake_case` for functions, methods, locals,
modules, and crates. `SCREAMING_SNAKE_CASE` for constants and statics.

**Why:** casing carries information. Seeing `foo::Bar` you know `Bar` is a type without looking it
up; seeing `foo::bar()` you know it is not. Mixed conventions destroy that signal, and `clippy`'s
`non_camel_case_types` / `non_snake_case` exist precisely because the ecosystem depends on it.

**Check:** the compiler's default lints catch every case. If any `#[allow(non_snake_case)]` appears
outside FFI declarations mirroring a C symbol, it is a violation.

```rust
// verified
use std::net::IpAddr;

pub const DEFAULT_PORT: u16 = 8080;

#[derive(Debug, Clone, Copy)]
pub struct HttpClient {
    bind: IpAddr,
    port: u16,
}

impl HttpClient {
    #[must_use]
    pub fn endpoint(&self) -> (IpAddr, u16) {
        (self.bind, self.port)
    }
}
```

### RS-NAME-02 [M] Capitalize acronyms as ordinary English words

`HttpClient`, `Uuid`, `TcpStream`, `OsStr`, `IoSlice`. Never `HTTPClient`, `UUID`, `IOSlice`. In
`snake_case` the acronym is simply lowercase: `to_ascii_uppercase`, `into_os_string`.

**Why:** `std` is uniform about it, and losing the casing loses the word boundary — `HTTPSProxy` has
no readable split, `HttpsProxy` does. Two-letter acronyms are not exempt: `std` writes `Io`, not
`IO`.

**Check:** grep new identifiers for two or more consecutive capitals — `[A-Z]{2}`. Every hit must
mirror a foreign symbol byte-for-byte (a C `#define`, an on-disk constant); anything else is a
violation, including a two-letter one.

```rust
// verified
#[derive(Debug)]
pub struct HttpsProxyUrlParser;

#[derive(Debug)]
pub struct Uuid([u8; 16]);

#[must_use]
pub fn parse_utf8(bytes: &[u8]) -> Option<&str> {
    std::str::from_utf8(bytes).ok()
}
```

### RS-NAME-03 [M] Let Cargo translate between package and crate names

Package names on crates.io may use hyphens; Cargo maps them to underscores for the crate name. Pick
the hyphenated package name and let the translation happen — do not name the package `foo-bar` and
the lib target `foobar`.

**Why:** a mismatch means `foo-bar` in `Cargo.toml` and `foobar::` in code, so neither name is
searchable from the other, and every new contributor has to learn the exception.

**Check:** in `Cargo.toml`, is there a `[lib] name = …` that is not the package name with hyphens
replaced by underscores? If so, delete it and fix the `use` statements.

### RS-NAME-04 [S] Never prefix or suffix a crate with `rust`

`ignore`, `globset`, `regex-automata` are the model. `rust-ignore`, `ignore-rs`, `rust_globset` are
not.

**Why:** the registry is Rust-only, so the prefix carries zero information and costs four characters
in every dependency line and every `use`. The rare defensible exception is a crate whose unprefixed
name is already taken by an unrelated ecosystem-wide term.

**Check:** does the crate name contain `rust` or end in `-rs`? If yes, is the unprefixed name
actually taken by something a user could confuse it with?

### RS-NAME-05 [S] Keep crate names short, lowercase, and pronounceable

Two words is the ceiling for a leaf crate; three for a facade (`regex-automata`, `grep-searcher`).

**Why:** the name appears in every dependent's manifest, in every `use`, and in conversation. If it
needs four words to describe the crate, the crate does too much — the name is reporting a design
problem (`references/modules.md` RS-MOD-24).

**Check:** say the name out loud. If you have to spell it, or if it does not fit in the
`Cargo.toml` line without wrapping, shorten it or split the crate.

### RS-NAME-06 [M] Name a module for its concept; never `utils`, `helpers`, `common`

Module names are singular nouns describing one concept: `matcher`, `printer`, `config`, `walk`.

**Why:** the module name is the first half of every path a reader sees — `matcher::Config` tells
them which concept `Config` belongs to before they open anything. A singular noun forces that
concept to exist and to be one thing; a plural or a category name (`utils`, `helpers`, `common`)
names a container instead, and a container can hold anything. `references/modules.md` RS-MOD-02
owns the argument for why those particular names never converge.

**Check:** for each module, write one sentence describing what belongs in it and what does not. If
the sentence is "things used in more than one place", the module needs dissolving.

```rust
// verified
/// The module names one concept, so the item names need not repeat it.
#[derive(Debug, Default)]
pub struct Matcher {
    patterns: Vec<String>,
}

impl Matcher {
    #[must_use]
    pub fn len(&self) -> usize {
        self.patterns.len()
    }

    #[must_use]
    pub fn is_empty(&self) -> bool {
        self.patterns.is_empty()
    }
}
```

### RS-NAME-07 [M] Name a feature for the capability, not the dependency

`simd-accel`, `pcre2`, `unicode`. A feature named after its dependency is acceptable only when it
exists solely to enable that dependency's impls — `serde`, `rayon`.

**Why:** feature names are the vocabulary users reason about when they run
`--no-default-features`. `mycrate/fast-path` tells them what they lose; `mycrate/aho-corasick` tells
them only that you swapped an internal.

**Check:** for each feature, can a user who has never read your source predict what turning it off
removes? If not, rename it.

### RS-NAME-08 [S] Do not prefix a feature with `use-`, `with-`, or `enable-`

Write `features = ["simd"]`, not `features = ["use-simd"]`.

**Why:** the manifest syntax already says "enable". The prefix is three characters of noise on every
line of every dependent's manifest, and it sorts all your features under one letter.

**Check:** grep `[features]` for `^use-|^with-|^enable-`.

### RS-NAME-09 [M] Do not repeat the enum's name in its variants

`Shape::Circle`, not `Shape::ShapeCircle`. `Error::Io`, not `Error::IoError`.

**Why:** the path already carries the type. The repetition costs characters at every match arm and
reads as stuttering: `Error::IoError(e)`.

**Check:** for each enum, does any variant name start or end with the enum's name, or with a word
that is a synonym for it?

### RS-NAME-10 [S] Name constants for the quantity, with the unit as a suffix

`MAX_RETRIES`, `DEFAULT_BUFFER_SIZE`, `TIMEOUT_MS`. Not `BUF_SIZE_USIZE`, and not `TIMEOUT` with the
unit hidden in a comment.

**Why:** the type is visible in the declaration, so encoding it in the name is redundant; the unit
is *not* visible in `u64`, so it must be somewhere the call site can see it. Better still, make it a
`Duration` and drop the suffix (RS-NAME-30).

**Check:** every numeric constant whose value has a physical unit — time, bytes, counts of a
specific thing — either names the unit or has a type that does.

### RS-NAME-11 [S] Give a type parameter a real name once the roles stop being obvious

`fn map<T, U>` is fine because the roles are obvious. `struct Cache<Key, Value>` beats
`struct Cache<K, V>` in a documented public API, and anything with three or more parameters of
asymmetric role needs words.

**Why:** the rustdoc signature is where users learn the API, and `Cache<K, V, S, H>` forces them to
read the prose to find out which is which. A named parameter is self-documenting in the tooltip.

**Check:** in rustdoc, can a reader assign a meaning to every parameter from the signature alone?

### RS-NAME-12 [M] Name the file after the module, without re-stating the directory

`searcher.rs` inside `grep/`, not `grep_searcher.rs` inside `grep/`.

**Why:** the path is already `grep::searcher`; the prefix duplicates it in the file tree, makes the
directory listing hard to scan, and breaks alphabetical grouping when a second prefix appears.

**Check:** does any file name start with the name of its parent directory?

## Conversions and access

### RS-NAME-13 [M] `as_` is a free borrowed view

`str::as_bytes`, `Path::as_os_str`, `String::as_str`. Borrow in, borrow out, no allocation, no
computation beyond a pointer adjustment.

**Why:** the three prefixes form a cost contract that experienced Rust programmers read as a
performance annotation. An `as_*` that allocates breaks that contract silently — the caller puts it
in a loop because the name promised it was free.

**Check:** for every `as_*` method, does the body allocate, iterate, or call anything that does? If
so, it is `to_*`.

```rust
// verified
/// `as_` is a free borrowed view: no allocation, no computation.
#[derive(Debug, Clone)]
pub struct Line(String);

impl Line {
    #[must_use]
    pub fn as_str(&self) -> &str {
        &self.0
    }
}
```

### RS-NAME-14 [M] `to_` costs something

`str::to_owned`, `f64::to_string`, `Path::to_path_buf`. It allocates, copies, or computes.

**Why:** same contract, other direction. The one established exception is a cheap `Copy`-to-`Copy`
conversion such as `char::to_ascii_uppercase`, where the cost is a register move and `std` has
already fixed the spelling — mirror `std` rather than "correcting" it.

**Check:** an expensive `as_*` and a free `to_*` are both violations; the free case is the milder
one, but it still misinforms.

### RS-NAME-15 [M] `into_` consumes the receiver

`String::into_bytes`, `BufWriter::into_inner`, `Vec::into_boxed_slice`. It takes `self` and hands
back ownership, ideally without copying.

**Why:** `into_` at a call site tells the reader the original binding is gone — which is the single
most useful thing a name can say about a move. A `self`-taking method that does not meaningfully
transfer ownership should not use the prefix.

**Check:** does every `into_*` take `self` by value? Does every `self`-by-value conversion use
`into_`?

```rust
// verified
#[derive(Debug, Default)]
pub struct Buffer {
    bytes: Vec<u8>,
}

impl Buffer {
    /// Borrows: free.
    #[must_use]
    pub fn as_slice(&self) -> &[u8] {
        &self.bytes
    }

    /// Copies: allocates.
    #[must_use]
    pub fn to_vec(&self) -> Vec<u8> {
        self.bytes.clone()
    }

    /// Consumes: moves, no copy.
    #[must_use]
    pub fn into_vec(self) -> Vec<u8> {
        self.bytes
    }
}
```

### RS-NAME-16 [M] Do not use a conversion prefix for a computation

A method that performs work and happens to return a different type is `compute_*`, `parse`,
`render`, or `build` — not `to_*`.

**Why:** `to_summary()` implies a representation change; `summarize()` implies work. Users budget
for the second and not the first, and the difference shows up as a profiler surprise.

**Check:** would a reader be surprised to learn this method runs a regex, hits the filesystem, or
sorts? If yes, the name must say so.

### RS-NAME-17 [M] Getters omit `get_`

`fn len(&self)`, `fn name(&self)`, `fn config(&self)`.

**Why:** the Rust API Guidelines are explicit (C-GETTER), and `std` is uniform. `get_` is reserved
for the `Index`-like case where the lookup can fail and returns `Option`/`Result` — `HashMap::get`,
`slice::get` — and for the `get_mut`/`get_unchecked` family that pairs with it.

**Check:** grep `fn get_`. Every hit must return `Option`, `Result`, or be an `_unchecked`/`_mut`
sibling of one that does.

```rust
// verified
/// Getters omit `get_`, and the mutable variant is suffixed `_mut`.
#[derive(Debug, Default)]
pub struct Buffer {
    capacity: usize,
    bytes: Vec<u8>,
}

impl Buffer {
    #[must_use]
    pub fn capacity(&self) -> usize {
        self.capacity
    }

    pub fn bytes_mut(&mut self) -> &mut Vec<u8> {
        &mut self.bytes
    }
}
```

### RS-NAME-18 [M] Match the getter to the field, and suffix the mutable variant `_mut`

`fn matcher(&self) -> &Matcher` and `fn matcher_mut(&mut self) -> &mut Matcher`. Setters are
`set_name`, and exist only when a builder is inappropriate.

**Why:** the pairing lets a reader move between field, getter, and mutator without a search, and the
`_mut` suffix is what the whole ecosystem uses (`iter`/`iter_mut`, `get`/`get_mut`).

**Check:** does every `&mut`-returning accessor end in `_mut`? Does any getter's name differ from
the field it exposes? Note that exposing `&mut` to invariant-bearing state is a separate, more
serious defect (`references/api.md` RS-API-22).

### RS-NAME-19 [M] Mark fallible conversions `try_`

`try_into_inner`, `usize::try_from`, or an implementation of `TryFrom`.

**Why:** an infallible-sounding name that returns `Result` makes the `?` at the call site look like
noise, so it gets `unwrap`ped. The prefix warns before the signature is read.

**Check:** does any `Result`-returning conversion lack `try_` and lack a `TryFrom` impl behind it?

```rust
// verified
/// A fallible conversion says `try_`, so the signature is unsurprising.
#[derive(Debug, Clone, Copy)]
pub struct Age(u8);

/// The value did not fit in a `u8`.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct OutOfRange;

impl Age {
    /// # Errors
    /// Returns [`OutOfRange`] when `years` exceeds 255.
    pub fn try_from_years(years: u32) -> Result<Self, OutOfRange> {
        u8::try_from(years).map(Self).map_err(|_| OutOfRange)
    }
}
```

### RS-NAME-20 [M] Use the three canonical iterator constructor names

`iter`, `iter_mut`, `into_iter`. Any other iterator-returning method describes what it yields:
`lines`, `char_indices`, `split_whitespace`, `ancestors`.

**Why:** C-ITER. Users try `.iter()` first on anything collection-shaped; if you named it
`.elements()`, they find it only by reading the docs. Conversely, a method named `iter` that yields
something other than the collection's elements is actively misleading.

**Check:** does the type have a natural element sequence but no `iter()`? Does any `iter*` method
yield something other than the elements?

```rust
// verified
/// The three canonical iterator constructors, with the conventional receivers.
#[derive(Debug, Default)]
pub struct Set {
    items: Vec<u32>,
}

impl Set {
    pub fn iter(&self) -> std::slice::Iter<'_, u32> {
        self.items.iter()
    }

    pub fn iter_mut(&mut self) -> std::slice::IterMut<'_, u32> {
        self.items.iter_mut()
    }
}

impl<'set> IntoIterator for &'set Set {
    type Item = &'set u32;
    type IntoIter = std::slice::Iter<'set, u32>;

    fn into_iter(self) -> Self::IntoIter {
        self.items.iter()
    }
}

impl<'set> IntoIterator for &'set mut Set {
    type Item = &'set mut u32;
    type IntoIter = std::slice::IterMut<'set, u32>;

    fn into_iter(self) -> Self::IntoIter {
        self.items.iter_mut()
    }
}

impl IntoIterator for Set {
    type Item = u32;
    type IntoIter = std::vec::IntoIter<u32>;

    fn into_iter(self) -> Self::IntoIter {
        self.items.into_iter()
    }
}
```

### RS-NAME-21 [S] Name an iterator type after the method that produces it

`lines()` → `Lines`, `split_terminator()` → `SplitTerminator`, `iter()` → `Iter<'_, T>`.

**Why:** C-ITER-TY. It lets a reader map a return type in rustdoc back to its origin without
searching, which matters because iterator types are otherwise opaque.

**Check:** for each public iterator type, is there a method with the same name in `snake_case`?

```rust
// verified
/// Returning an iterator tied to `self` documents the borrow in the type.
#[derive(Debug, Default)]
pub struct Log {
    lines: Vec<String>,
}

impl Log {
    pub fn errors(&self) -> impl Iterator<Item = &str> {
        self.lines
            .iter()
            .map(String::as_str)
            .filter(|line| line.starts_with("ERROR"))
    }
}
```

### RS-NAME-22 [S] Name secondary constructors `with_*` / `from_*`, never `new_with_*`

`Vec::with_capacity`, `u32::from_str_radix`, `Searcher::from_parts`.

**Why:** `new_with_config` is `with_config` plus three characters of ceremony, and it breaks the
alphabetical grouping that puts all the `with_*` constructors together in rustdoc.

**Check:** grep `fn new_`.

```rust
// verified
use std::time::Duration;

#[derive(Debug, Clone, Copy)]
pub struct Retry {
    attempts: u32,
    backoff: Duration,
}

impl Retry {
    /// The primary constructor is `new`.
    #[must_use]
    pub fn new(attempts: u32) -> Self {
        Self {
            attempts,
            backoff: Duration::from_millis(100),
        }
    }

    /// Secondary constructors say what they add.
    #[must_use]
    pub fn with_backoff(self, backoff: Duration) -> Self {
        Self { backoff, ..self }
    }
}
```

### RS-NAME-23 [M!] Prefer a `From`/`TryFrom`/`FromStr` impl to an inherent `from_*`

Implementing the trait gives callers `.into()`, `?` conversion, and generic code for free.

**Why:** an inherent `Config::from_path(p)` works only when the caller knows to look for it; a
`TryFrom<&Path> for Config` also works inside `collect::<Result<Vec<_>, _>>()`, behind
`impl TryInto<Config>`, and through `?`. *Relaxed form:* keep an inherent `from_*` when the trait
impl would be ambiguous (several sources of the same type, as with `from_utf8` and
`from_utf8_lossy`) or would leak a type parameter — and then name it for the source, not the target.

**Check:** for each inherent `from_*`, could it be a `From`/`TryFrom` impl without ambiguity? If
yes, make it one and keep the inherent version only as a thin forwarder.

### RS-NAME-24 [M] Predicates read as questions and return `bool`

`is_empty`, `is_ascii`, `has_root`, `contains`, `starts_with`.

**Why:** the reader parses `if entry.is_hidden()` as a sentence. `check_*` and `validate_*` read as
commands, so they imply an effect — reserve them for the case that actually returns
`Result<(), Error>`.

**Check:** every `bool`-returning method starts with `is`, `has`, `can`, `should`, or is a verb that
reads as a question (`contains`, `starts_with`, `intersects`).

```rust
// verified
/// A predicate reads as a question and returns `bool`.
#[derive(Debug, Clone, Copy)]
pub struct Entry {
    size: u64,
}

impl Entry {
    #[must_use]
    pub fn is_empty(self) -> bool {
        self.size == 0
    }

    #[must_use]
    pub fn has_content(self) -> bool {
        !self.is_empty()
    }
}
```

## Words and word order

### RS-NAME-25 [S] Verbs do something; nouns give something

`parse()`, `flush()`, `search()`, `spawn()` versus `len()`, `capacity()`, `stdout()`.

**Why:** the part of speech is the cheapest available signal about whether a call has an effect. A
noun-named method that mutates is a bug in the name, and it will be called inside a `debug!` where
its effect is invisible.

**Check:** for each noun-named method, does it mutate, allocate significantly, or perform I/O?

### RS-NAME-26 [S] Follow `std`'s word order, and extend by suffix

Verb-object-qualifier: `Vec::insert`, `Result::unwrap_or_else`, `str::parse`. When adding a variant
of an existing method, extend the suffix rather than reordering: `write_all`, `write_fmt`,
`write_vectored`.

**Why:** C-WORD-ORDER. Consistent order means related methods sort together in rustdoc and
autocomplete, which is how users actually discover the variant they need.

**Check:** do the variants of one operation share a prefix and sort adjacently in the rustdoc method
list?

### RS-NAME-27 [M] One term, one meaning, crate-wide

If the crate says `matcher`, never introduce `pattern_engine` for the same concept in a new module.

**Why:** internal consistency outranks consistency with the outside world, because a reader builds a
vocabulary from your crate and every synonym forces them to check whether it is a distinction. Two
names for one thing is worse than one imperfect name.

**Check:** grep the crate for the synonyms of each core noun. Any pair that refers to the same
concept is a rename waiting to happen.

### RS-NAME-28 [S] Spell names out; abbreviate only where the abbreviation is the standard word

`config`, `regex`, `buf`, `ctx` in narrow scopes, `idx` in a loop, `recv`/`send` on channels — these
are public dictionaries. `rslt`, `mngr`, `hdlr`, `cfgmgr` are private ones.

**Why:** an abbreviation the reader has to expand costs more than the characters it saved, and
private abbreviations do not survive contact with a second contributor. Equal-length related names
also keep call sites aligned: `source`/`target` beats `src`/`dst` in a column of arguments.

**Check:** for each abbreviation, does it appear in `std`, in a major crate's public API, or in the
domain's own literature? If not, expand it.

```rust
// verified
use std::path::Path;

/// `source`/`target`, never `src`/`dst`: equal length, and no reader has to expand them.
#[must_use]
pub fn is_same_volume(source: &Path, target: &Path) -> bool {
    source.components().next() == target.components().next()
}
```

### RS-NAME-29 [S] Restrict single-letter locals to short, genuinely generic bindings

Closure parameters in a two-line chain, loop indices, and mathematical code where the letter is the
domain notation.

**Why:** a single letter carries no information, which is fine when the binding's meaning is fully
determined by the two lines around it and fatal when it is not.

**Check:** does any single-letter binding live longer than about ten lines, or cross a block
boundary? Give it a name.

### RS-NAME-30 [M!] Put the unit in the type; failing that, in the name

`Duration` rather than `timeout_ms: u64`; a `Bytes`/`ByteSize` newtype rather than `size: u64`.

**Why:** unit confusion is a bug class the type system can eliminate completely — the compiler
rejects `sleep(retry_count)` if the parameter is a `Duration`, and cannot if it is a `u64`.
*Relaxed form:* where a newtype would be disproportionate (a private helper, a single call site),
the unit suffix in the name is acceptable — but never omit both.

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

### RS-NAME-31 [S] Name the positive; convert negations once, at the boundary

`no_color`, `disable_cache`, and `skip_hidden` compose into double negation: `if !no_color`.

**Why:** every reader of `if !no_color` performs a small logic operation to recover the intent, and
under an `&&` with a second negation they will eventually get it wrong. The CLI flag may be negative
because the convention demands it — convert to a positive field once, where the flag is parsed
(`references/cli.md` RS-CLI-14).

**Check:** grep for `!` applied to an identifier containing `no_`, `not_`, `disable`, `skip`, or
`without`.

```rust
// verified
/// The command line spells the negative, so the type spells it too — once.
#[derive(Debug, Clone, Copy, Default, PartialEq, Eq)]
pub enum NoColour {
    Set,
    #[default]
    Unset,
}

/// The positive is named; the negation is derived once, at the boundary.
#[derive(Debug, Clone, Copy)]
pub struct Options {
    colour: bool,
}

impl Options {
    #[must_use]
    pub fn from_flags(no_colour: NoColour) -> Self {
        Self {
            colour: no_colour == NoColour::Unset,
        }
    }

    #[must_use]
    pub fn wants_colour(self) -> bool {
        self.colour
    }
}

impl Default for Options {
    /// The same answer as passing no flag at all, so the two cannot drift apart.
    fn default() -> Self {
        Self::from_flags(NoColour::default())
    }
}
```

### RS-NAME-32 [S] Name a trait for the capability it grants

`Read`, `Write`, `Display`, `Matcher`, `Searcher`, `Sink` — verbs, or agent nouns derived from
verbs.

**Why:** a trait is a capability, not a category (`references/traits.md` RS-TRAIT-02), and
the name should say so. `-able` reads naturally only occasionally: `std` has `IntoIterator`, not
`Iterable`.

**Check:** does the trait's name describe something you can *do*, or something a type *is*? The
second is usually a design error surfacing as a naming one.

### RS-NAME-33 [M] Never suffix a name with the language construct

No `ConfigTrait`, `ErrorEnum`, `WrapperStruct`, `HandlerImpl`, `FooType`.

**Why:** the declaration already says `trait`/`enum`/`struct`, and the suffix announces the
mechanism instead of the concept — it is the naming equivalent of a comment that restates the code.

**Check:** grep identifiers ending in `Trait`, `Enum`, `Struct`, `Impl`, `Type`, `Class`, `Object`.

### RS-NAME-34 [S] Apply role suffixes consistently or not at all

`Builder`, `Guard`, `Handle`, `Ref`, `Iter`, `Error`, `Config`: use the suffix whenever the type
plays that role, and never when it does not.

**Why:** a half-applied convention is worse than none, because the reader cannot tell whether the
absence of `Guard` means "not a guard" or "we forgot". `SearcherBuilder`, `MutexGuard`, and
`JoinHandle` work as a system precisely because there are no exceptions.

**Check:** list every type playing each role. Is the suffix present on all of them, or on none?

### RS-NAME-35 [M] Pick one error-type spelling per crate

Either `Error` inside its own module (`io::Error`, `parse::Error`) or `FooError` at the crate root
when several coexist. Never both spellings in one crate.

**Why:** with both, `use` statements collide unpredictably and readers cannot guess the path of an
error they have not met. The module-scoped spelling scales better; the flat one is fine for a crate
with two error types (`references/errors.md` RS-ERR-19).

**Check:** grep for `Error` in type positions. Are all of them the same shape?

### RS-NAME-36 [S] Name a test for the behaviour it pins

`rejects_pattern_with_unclosed_group`, `preserves_order_of_equal_keys`. Not `test_parse_2`.

**Why:** the test name is what the failure output shows, so it should state what broke without the
reader opening the file. The `test_` prefix is redundant with `#[test]`, and a number pins nothing.

**Check:** read the list of test names as a specification. Does it describe the contract, or does it
describe the functions that happen to exist? (`references/testing.md` RS-TEST-08.)

## Generic parameters and lifetimes

### RS-NAME-37 [S] Use the conventional single letters where the role is universal

`T`/`U` for values, `E` for error, `K`/`V` for map keys and values, `F` for closures, `I` for
iterators, `S` for string-like, `R`/`W` for reader and writer.

**Why:** these are ecosystem-wide, so a reader parses `fn read_from<R: Read>(r: R)` without pausing.
Inventing `Reader` where `R` is conventional costs a moment of "is this different?".

**Check:** does any parameter use a conventional letter for an unconventional role — `E` for an
element type, `S` for a state?

```rust
// verified
use std::fmt::Display;

/// `T` for the element, `E` for the error: conventional where the role is universal.
pub fn first_line<T: Display, E>(
    items: &[T],
    _marker: std::marker::PhantomData<E>,
) -> Option<String> {
    items.first().map(ToString::to_string)
}
```

### RS-NAME-38 [S] Name a lifetime for the source of the borrow once several coexist

`'a` when there is one. `'src`, `'input`, `'haystack` when there are several and it matters which is
which. Use `'_` wherever it is accepted (`references/ownership.md` RS-OWN-06).

**Why:** `fn find<'a, 'b>(h: &'a str, n: &'b str) -> &'a str` requires the reader to track two
letters back to their bindings; `<'haystack, 'needle>` does not.

**Check:** does any signature carry two or more named lifetimes with single-letter names?

```rust
// verified
/// The lifetime is named for the source of the borrow, not `'a`.
#[derive(Debug, Clone, Copy)]
pub struct Cursor<'input> {
    rest: &'input str,
}

impl<'input> Cursor<'input> {
    #[must_use]
    pub fn new(input: &'input str) -> Self {
        Self { rest: input }
    }

    #[must_use]
    pub fn rest(&self) -> &'input str {
        self.rest
    }
}
```

### RS-NAME-39 [M] Never restate the kind in a parameter's name

No `'life`, no `'lifetime`, no type parameter named `Type` or `Generic`.

**Why:** the sigil already conveys the kind, exactly as with RS-NAME-33. `<'lifetime, Type>` is
noise in every signature that mentions it.

**Check:** grep for `'life`, `'lifetime`, `<Type`, `<Generic`.

```rust
// verified
use std::path::Path;

/// The type already says it is a path; the name says which path.
#[must_use]
pub fn read_config(config: &Path) -> Option<&str> {
    config.to_str()
}
```

### RS-NAME-40 [S] Spell const generic parameters in `SCREAMING_SNAKE_CASE`

`struct Matrix<const ROWS: usize, const COLS: usize>`, `struct Chunk<const N: usize>`. A single
uppercase letter is fine when the domain uses one.

**Why:** it matches the casing of the constants they are instantiated with, so the connection
between `Chunk::<64>::new()` and `const N` is visible. The compiler warns on `snake_case` here
anyway.

**Check:** the `non_upper_case_globals` lint covers it.

```rust
// verified
/// Const generic parameters are `SCREAMING_SNAKE_CASE`.
#[derive(Debug)]
pub struct RingBuffer<T, const CAPACITY: usize> {
    slots: [Option<T>; CAPACITY],
}

impl<T, const CAPACITY: usize> RingBuffer<T, CAPACITY> {
    #[must_use]
    pub fn capacity(&self) -> usize {
        CAPACITY
    }
}
```

### RS-NAME-41 [S] Name an associated type for the thing it produces

`type Item`, `type Output`, `type Error`, `type Iter<'a>`. Do not prefix with the trait name.

**Why:** the associated type is always written qualified — `I::Item`, `T::Error` — so the trait name
is already present at every use site. `type IteratorItem` renders as `I::IteratorItem`.

**Check:** does any associated type's name begin with the trait's name or an abbreviation of it?

```rust
// verified
/// The associated type is named for the thing it produces.
pub trait Decoder {
    type Frame;
    type Error;

    /// # Errors
    /// Returns `Self::Error` when the input is not a complete frame.
    fn decode(&mut self, input: &[u8]) -> Result<Option<Self::Frame>, Self::Error>;
}
```

### RS-NAME-42 [S] Name a generic parameter for its bound in a crowded signature

`fn copy<R: Read, W: Write>(reader: R, writer: W)`. The letter matches the bound so the reader can
pair parameter to constraint at a glance.

**Why:** in a signature with four parameters and a `where` clause, matching `T3` to its bound
requires scrolling. Matching `W` to `W: Write` does not.

**Check:** in each multi-parameter signature, can a reader pair every parameter with its bound
without moving their eyes to the `where` clause?

## Symmetry of names

### RS-NAME-43 [M] Name the two halves of a pair symmetrically

A pair uses matched words: `encode`/`decode`, not `encode`/`parse`; `open`/`close`, not
`open`/`release`; `lock`/`unlock`, not `lock`/`release`. Reuse the ecosystem's pair where one
exists.

**Why:** matched names are what make a pair recognizable as a pair, which is how a reader knows the
inverse exists without looking (`RS-API-79`). Mismatched halves read as unrelated operations, and
the reader searches for a `decode` that is spelled `parse`.

**Check:** list every operation with an inverse and read the two names together. If they do not
sound like a pair said aloud, rename the odd half.

```rust
// verified
/// A pair uses matched words: `encode` / `decode`.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Frame(u32);

#[must_use]
pub fn encode(frame: Frame) -> [u8; 4] {
    frame.0.to_be_bytes()
}

#[must_use]
pub fn decode(bytes: [u8; 4]) -> Frame {
    Frame(u32::from_be_bytes(bytes))
}
```

### RS-NAME-44 [S] Keep the same word order across parallel names

Parallel names put their words in the same order: `read_timeout` and `write_timeout`, not
`read_timeout` and `timeout_write`; `max_depth` and `max_width`, not `max_depth` and `width_limit`.

**Why:** consistent order makes names sort together, complete together, and grep together, so the
family is discoverable from any one member. It also removes the pause where the reader wonders
whether the different order signals a different meaning (`RS-NAME-06`).

**Check:** sort the identifiers in each module alphabetically. Members of one family should end up
adjacent; a stray is a name whose word order differs.

```rust
// verified
use std::time::Duration;

/// Parallel names put their words in the same order, so the family sorts together.
#[derive(Debug, Clone, Copy)]
pub struct Limits {
    read_timeout: Duration,
    write_timeout: Duration,
    max_depth: u32,
    max_width: u32,
}

impl Limits {
    #[must_use]
    pub fn read_timeout(&self) -> Duration {
        self.read_timeout
    }

    #[must_use]
    pub fn write_timeout(&self) -> Duration {
        self.write_timeout
    }

    #[must_use]
    pub fn max_depth(&self) -> u32 {
        self.max_depth
    }

    #[must_use]
    pub fn max_width(&self) -> u32 {
        self.max_width
    }
}
```
