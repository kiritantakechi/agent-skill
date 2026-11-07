# Naming: Casing, Conversions, Word Order, and Generics

Scope: how identifiers are cased and worded, the cost contract carried by the `as_`/`to_`/`into_`
prefixes, getter and predicate shape, how iterators and their types are named, how crates, modules,
features, and files are named, how generic parameters, lifetimes, and associated types are spelled,
and the line width `rustfmt` leaves to the author. Semantics of the things being named live
elsewhere: what a constructor should *take* is in the API chapter, error-type *design* in the errors
chapter, module *boundaries* in the modules chapter, and feature *semantics* in the build chapter.

## Contents

- **Casing**
  - RS-NAME-01 [M] Capitalize acronyms as ordinary English words
  - RS-NAME-02 [M] Let Cargo translate between package and crate names
  - RS-NAME-03 [S] Never prefix or suffix a crate with `rust`
  - RS-NAME-04 [M] Name a module for its concept; never `utils`, `helpers`, `common`
  - RS-NAME-05 [M] Name a feature for the capability, not the dependency
  - RS-NAME-06 [S] Do not prefix a feature with `use-`, `with-`, or `enable-`
  - RS-NAME-07 [M] Do not repeat a type's name in the members it contains
  - RS-NAME-08 [S] Name a quantity for what it measures, with the unit as a suffix
  - RS-NAME-09 [S] Name a type parameter by its role: a conventional letter, else a word
  - RS-NAME-10 [M] Name the file after the module, without re-stating the directory

- **Conversions and access**
  - RS-NAME-11 [M] `as_` is a free borrowed view
  - RS-NAME-12 [M] `to_` costs something
  - RS-NAME-13 [M] `into_` consumes the receiver
  - RS-NAME-14 [M] Do not use a conversion prefix for a computation
  - RS-NAME-15 [M] Getters omit `get_`
  - RS-NAME-16 [M] Match the getter to the field, and suffix the mutable variant `_mut`
  - RS-NAME-17 [M] Mark fallible conversions `try_`
  - RS-NAME-18 [M] Use the three canonical iterator constructor names
  - RS-NAME-19 [S] Name an iterator type after the method that produces it
  - RS-NAME-20 [S] Name secondary constructors `with_*` / `from_*`, never `new_with_*`
  - RS-NAME-21 [M] Predicates read as questions and return `bool`

- **Words and word order**
  - RS-NAME-22 [S] Verbs do something; nouns give something
  - RS-NAME-23 [S] Follow `std`'s word order, extend by suffix, and keep parallel names parallel
  - RS-NAME-24 [M] One term, one meaning, crate-wide
  - RS-NAME-25 [M] Spell names out; abbreviate only where the abbreviation is the standard word
  - RS-NAME-26 [S] Restrict single-letter locals to short, genuinely generic bindings
  - RS-NAME-27 [S] Name the positive; convert negations once, at the boundary
  - RS-NAME-28 [M] Never suffix a name with the language construct
  - RS-NAME-29 [S] Apply role suffixes consistently or not at all
  - RS-NAME-30 [M] Pick one error-type spelling per crate

- **Generic parameters and lifetimes**
  - RS-NAME-31 [S] Name a lifetime for the source of the borrow once several coexist
  - RS-NAME-32 [M] Never restate the kind in a parameter's name

- **Symmetry of names**
  - RS-NAME-33 [M] Name the two halves of a pair symmetrically

- **Formatting**
  - RS-NAME-34 [M] Hold every line to 100 columns, rustfmt's default

- Decided by tools

---

## Casing

### RS-NAME-01 [M] Capitalize acronyms as ordinary English words

`HttpClient`, `Uuid`, `TcpStream`, `OsStr`, `IoSlice`. Never `HTTPClient`, `UUID`, `IOSlice`. In
`snake_case` the acronym is simply lowercase: `to_ascii_uppercase`, `into_os_string`.

**Why:** `std` is uniform about it, and losing the casing loses the word boundary — `HTTPSProxy` has
no readable split, `HttpsProxy` does. Two-letter acronyms are not exempt: `std` writes `Io`, not
`IO`.

**Check:** clippy `upper_case_acronyms`, which the shipped `clippy.toml` makes aggressive, flags
every run of capitals in a type name, two-letter ones included. A hit that mirrors a foreign symbol
byte-for-byte (a C `#define`, an on-disk constant) takes an `#[expect]` saying so.

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

### RS-NAME-02 [M] Let Cargo translate between package and crate names

Package names on crates.io may use hyphens; Cargo maps them to underscores for the crate name. Pick
the hyphenated package name and let the translation happen — do not name the package `foo-bar` and
the lib target `foobar`.

**Why:** a mismatch means `foo-bar` in `Cargo.toml` and `foobar::` in code, so neither name is
searchable from the other, and every new contributor has to learn the exception.

**Check:** in `Cargo.toml`, is there a `[lib] name = …` that is not the package name with hyphens
replaced by underscores? If so, delete it and fix the `use` statements.

### RS-NAME-03 [S] Never prefix or suffix a crate with `rust`

`ignore`, `globset`, `regex-automata` are the model. `rust-ignore`, `ignore-rs`, `rust_globset` are
not.

**Why:** the registry is Rust-only, so the prefix carries zero information and costs four characters
in every dependency line and every `use`. The rare defensible exception is a crate whose unprefixed
name is already taken by an unrelated ecosystem-wide term.

**Check:** does the crate name contain `rust` or end in `-rs`? If yes, is the unprefixed name
actually taken by something a user could confuse it with?

### RS-NAME-04 [M] Name a module for its concept; never `utils`, `helpers`, `common`

Module names are singular nouns describing one concept: `matcher`, `printer`, `config`, `walk`. A
grab-bag name — `utils`, `helpers`, `common`, `misc`, `shared`, or `types`, `lib` and `core` used as
one — names a container, and a container can hold anything.

**Why:** the module name is the first half of every path — `matcher::Config` says which concept
`Config` belongs to. A grab-bag admits the boundary has not been found, so nobody can predict what
landed in it, and it only grows: nothing is ever obviously *not* a utility.

**Check:** `rg -n '\bmod (utils?|helpers?|common|misc|shared)\b' -g '*.rs'` finds each grab-bag
module; every hit is the finding, and each item in it moves to the type or concept it serves. For
the other modules, write one sentence saying what belongs in each: "things used in more than one
place" means it needs dissolving.

```rust
// verified
// Named for the concept it serves, never `utils`.
pub mod escaping {
    //! Escapes text for terminal output.

    #[must_use]
    pub fn escape(input: &str) -> String {
        input.replace('\x1b', "^[")
    }
}
```

### RS-NAME-05 [M] Name a feature for the capability, not the dependency

`simd-accel`, `pcre2`, `unicode`. A feature named after its dependency is acceptable only when it
exists solely to enable that dependency's impls — `serde`, `rayon`.

**Why:** feature names are the vocabulary users reason about when they run `--no-default-features`.
`mycrate/fast-path` tells them what they lose; `mycrate/aho-corasick` tells them only which internal
you chose, and swapping it becomes a breaking change.

**Check:** for each feature, can a user who has never read your source predict what turning it off
removes? If not, rename it.

### RS-NAME-06 [S] Do not prefix a feature with `use-`, `with-`, or `enable-`

Write `features = ["simd"]`, not `features = ["use-simd"]`.

**Why:** the manifest syntax already says "enable". The prefix is three characters of noise on every
line of every dependent's manifest, and it sorts all your features under one letter.

**Check:** `rg -n '^(use|with|enable)-' -g '*.toml'` finds the prefixed features; each hit is the
finding.

### RS-NAME-07 [M] Do not repeat a type's name in the members it contains

`Shape::Circle`, not `Shape::ShapeCircle`. `Error::Io`, not `Error::IoError`. An associated type is
named for the thing it produces — `type Item`, `type Output`, `type Error` — and never prefixed with
the trait's name.

**Why:** the path already carries the type. The repetition costs characters at every match arm and
reads as stuttering: `Error::IoError(e)`, and an associated type is always written qualified —
`I::Item`, `T::Error` — so `type IteratorItem` renders as `I::IteratorItem`.

**Check:** clippy `enum_variant_names` flags three or more variants sharing a prefix or suffix. It
does not see one variant repeating the enum's name, or a synonym for it: for each enum, does any
variant start or end with either? And does any associated type's name begin with the trait's name or
an abbreviation of it?

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

### RS-NAME-08 [S] Name a quantity for what it measures, with the unit as a suffix

`MAX_RETRIES`, `DEFAULT_BUFFER_SIZE`, `TIMEOUT_MS`. Not `BUF_SIZE_USIZE`, and not `TIMEOUT` with the
unit hidden in a comment. For a parameter or field whose type cannot carry the unit, the name must
(RS-API-23).

**Why:** the type is visible in the declaration, so encoding it in the name is redundant; the unit
is *not* visible in `u64`, so it must be somewhere the call site can see it. Better still, make it a
`Duration` and drop the suffix (RS-API-23).

**Check:** every numeric constant, parameter, and field whose value has a physical unit — time,
bytes, counts of a specific thing — either names the unit or has a type that does.

### RS-NAME-09 [S] Name a type parameter by its role: a conventional letter, else a word

A role the ecosystem has a letter for takes it: `T`/`U` for values, `E` for an error, `K`/`V` for
map keys and values, `F` for a closure, `I` for an iterator, `S` for string-like, and `R`/`W` for a
reader and a writer. In a crowded signature the letter matches its bound, as in
`fn copy<R: Read, W: Write>`. Once the roles stop being obvious — three or more parameters of
asymmetric role, or a documented type such as `Cache<Key, Value>` — use words.

**Why:** the letters are ecosystem-wide, so `fn read_from<R: Read>(r: R)` parses without a pause,
and a letter that matches its bound pairs parameter to constraint at a glance. Past that,
`Cache<K, V, S, H>` sends the reader to the prose to find out which is which.

**Check:** in rustdoc, can a reader assign a meaning to every parameter from the signature alone?
Does any parameter use a conventional letter for an unconventional role — `E` for an element type,
`S` for a state?

```rust
// verified
use std::io::{self, Read, Write};

/// `R` and `W` are the conventional letters, and each matches its bound.
///
/// # Errors
/// Propagates any read or write error.
pub fn copy<R: Read, W: Write>(reader: &mut R, writer: &mut W) -> io::Result<u64> {
    io::copy(reader, writer)
}
```

### RS-NAME-10 [M] Name the file after the module, without re-stating the directory

`searcher.rs` inside `grep/`, not `grep_searcher.rs` inside `grep/`.

**Why:** the path is already `grep::searcher`; the prefix duplicates it in the file tree, makes the
directory listing hard to scan, and breaks alphabetical grouping when a second prefix appears.

**Check:** does any file name start with the name of its parent directory?

## Conversions and access

### RS-NAME-11 [M] `as_` is a free borrowed view

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

### RS-NAME-12 [M] `to_` costs something

`str::to_owned`, `f64::to_string`, `Path::to_path_buf`. It allocates, copies, or computes.

**Why:** same contract, other direction. The one established exception is a cheap `Copy`-to-`Copy`
conversion such as `char::to_ascii_uppercase`, where the cost is a register move and `std` has
already fixed the spelling — mirror `std` rather than "correcting" it.

**Check:** an expensive `as_*` and a free `to_*` are both violations; the free case is the milder
one, but it still misinforms.

### RS-NAME-13 [M] `into_` consumes the receiver

`String::into_bytes`, `BufWriter::into_inner`, `Vec::into_boxed_slice`. It takes `self` and hands
back ownership, ideally without copying.

**Why:** `into_` at a call site tells the reader the original binding is gone — which is the single
most useful thing a name can say about a move. A `self`-taking method that does not meaningfully
transfer ownership should not use the prefix.

**Check:** clippy `wrong_self_convention` flags a prefix whose receiver breaks its contract: an
`into_*` that borrows, an `as_*` that takes `self`. It cannot see cost, so read the rest: does every
`self`-by-value conversion use `into_`?

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

### RS-NAME-14 [M] Do not use a conversion prefix for a computation

A method that performs work and happens to return a different type is `compute_*`, `parse`,
`render`, or `build` — not `to_*`.

**Why:** `to_summary()` implies a representation change; `summarize()` implies work. Users budget
for the second and not the first, and the difference shows up as a profiler surprise.

**Check:** would a reader be surprised to learn this method runs a regex, hits the filesystem, or
sorts? If yes, the name must say so.

### RS-NAME-15 [M] Getters omit `get_`

`fn len(&self)`, `fn name(&self)`, `fn config(&self)`.

**Why:** the Rust API Guidelines are explicit (C-GETTER), and `std` is uniform. `get_` is reserved
for the `Index`-like case where the lookup can fail and returns `Option`/`Result` — `HashMap::get`,
`slice::get` — and for the `get_mut`/`get_unchecked` family that pairs with it.

**Check:** `rg -n 'fn get_' -g '*.rs'` lists the `get_` methods; each that returns neither `Option`
nor `Result`, and is not the `_unchecked`/`_mut` sibling of one that does, is the finding.

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

### RS-NAME-16 [M] Match the getter to the field, and suffix the mutable variant `_mut`

`fn matcher(&self) -> &Matcher` and `fn matcher_mut(&mut self) -> &mut Matcher`. Setters are
`set_name`, and exist only when a builder is inappropriate.

**Why:** the pairing lets a reader move between field, getter, and mutator without a search, and the
`_mut` suffix is what the whole ecosystem uses (`iter`/`iter_mut`, `get`/`get_mut`).

**Check:** does every `&mut`-returning accessor end in `_mut`? Does any getter's name differ from
the field it exposes? Note that exposing `&mut` to invariant-bearing state is a separate, more
serious defect (RS-API-13).

### RS-NAME-17 [M] Mark fallible conversions `try_`

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

### RS-NAME-18 [M] Use the three canonical iterator constructor names

`iter`, `iter_mut`, `into_iter`. Any other iterator-returning method describes what it yields:
`lines`, `char_indices`, `split_whitespace`, `ancestors`.

**Why:** C-ITER. Users try `.iter()` first on anything collection-shaped; if you named it
`.elements()`, they find it only by reading the docs. Conversely, a method named `iter` that yields
something other than the collection's elements is actively misleading.

**Check:** does the type have a natural element sequence but no `iter()`? Does any `iter*` method
yield something other than the elements?

```rust
// verified
/// The three canonical iterator constructors, each returning a type named for
/// it (RS-NAME-19) that keeps the `Vec` behind it private (RS-API-04).
#[derive(Debug, Default)]
pub struct Set {
    items: Vec<u32>,
}

/// What `Set::iter` returns.
#[derive(Debug)]
#[must_use = "iterators are lazy and do nothing unless consumed"]
pub struct Iter<'set>(std::slice::Iter<'set, u32>);

impl<'set> Iterator for Iter<'set> {
    type Item = &'set u32;

    fn next(&mut self) -> Option<Self::Item> {
        self.0.next()
    }
}

/// What `Set::iter_mut` returns.
#[derive(Debug)]
#[must_use = "iterators are lazy and do nothing unless consumed"]
pub struct IterMut<'set>(std::slice::IterMut<'set, u32>);

impl<'set> Iterator for IterMut<'set> {
    type Item = &'set mut u32;

    fn next(&mut self) -> Option<Self::Item> {
        self.0.next()
    }
}

/// What `Set::into_iter` returns.
#[derive(Debug)]
#[must_use = "iterators are lazy and do nothing unless consumed"]
pub struct IntoIter(std::vec::IntoIter<u32>);

impl Iterator for IntoIter {
    type Item = u32;

    fn next(&mut self) -> Option<Self::Item> {
        self.0.next()
    }
}

impl Set {
    pub fn iter(&self) -> Iter<'_> {
        Iter(self.items.iter())
    }

    pub fn iter_mut(&mut self) -> IterMut<'_> {
        IterMut(self.items.iter_mut())
    }
}

impl<'set> IntoIterator for &'set Set {
    type Item = &'set u32;
    type IntoIter = Iter<'set>;

    fn into_iter(self) -> Self::IntoIter {
        self.iter()
    }
}

impl<'set> IntoIterator for &'set mut Set {
    type Item = &'set mut u32;
    type IntoIter = IterMut<'set>;

    fn into_iter(self) -> Self::IntoIter {
        self.iter_mut()
    }
}

impl IntoIterator for Set {
    type Item = u32;
    type IntoIter = IntoIter;

    fn into_iter(self) -> Self::IntoIter {
        IntoIter(self.items.into_iter())
    }
}
```

### RS-NAME-19 [S] Name an iterator type after the method that produces it

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

### RS-NAME-20 [S] Name secondary constructors `with_*` / `from_*`, never `new_with_*`

`Vec::with_capacity`, `u32::from_str_radix`, `Searcher::from_parts`.

**Why:** `new_with_config` is `with_config` plus three characters of ceremony, and it breaks the
alphabetical grouping that puts all the `with_*` constructors together in rustdoc.

**Check:** `rg -n 'fn new_' -g '*.rs'` finds a secondary constructor named `new_*`; each hit is the
finding.

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

### RS-NAME-21 [M] Predicates read as questions and return `bool`

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

### RS-NAME-22 [S] Verbs do something; nouns give something

`parse()`, `flush()`, `search()`, `spawn()` versus `len()`, `capacity()`, `stdout()`.

**Why:** the part of speech is the cheapest available signal about whether a call has an effect. A
noun-named method that mutates is a bug in the name, and it will be called inside a `debug!` where
its effect is invisible.

**Check:** for each noun-named method, does it mutate, allocate significantly, or perform I/O?

### RS-NAME-23 [S] Follow `std`'s word order, extend by suffix, and keep parallel names parallel

Verb-object-qualifier: `Vec::insert`, `Result::unwrap_or_else`, `str::parse`. When adding a variant
of an existing method, extend the suffix rather than reordering: `write_all`, `write_fmt`,
`write_vectored`. Parallel names put their words in the same order: `read_timeout` and
`write_timeout`, not `timeout_write`; `max_depth` and `max_width`, not `width_limit`.

**Why:** C-WORD-ORDER. Consistent order means related names sort, complete, and grep together, which
is how users discover the variant they need, and no reader pauses to ask whether a different order
signals a different meaning.

**Check:** sort each module's identifiers and each type's rustdoc method list. Members of one family
should end up adjacent; a stray is a name whose word order differs.

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

### RS-NAME-24 [M] One term, one meaning, crate-wide

If the crate says `matcher`, never introduce `pattern_engine` for the same concept in a new module;
not `path` here and `file` there for one argument, nor `id`, `key`, and `handle` for one identifier.

**Why:** a reader builds a vocabulary from your crate, and every synonym makes them check whether it
is a distinction. It also defeats search: no one finds every site that touches a concept spelled
three ways. Two names for one thing is worse than one imperfect name.

**Check:** list the nouns in the public surface and the words the crate uses for each, and group
them by referent. Any group with more than one spelling needs a decision and a rename.

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

### RS-NAME-25 [M] Spell names out; abbreviate only where the abbreviation is the standard word

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

### RS-NAME-26 [S] Restrict single-letter locals to short, genuinely generic bindings

Closure parameters in a two-line chain, loop indices, and mathematical code where the letter is the
domain notation.

**Why:** a single letter carries no information, which is fine when the binding's meaning is fully
determined by the two lines around it and fatal when it is not.

**Check:** does any single-letter binding live longer than about ten lines, or cross a block
boundary? Give it a name.

### RS-NAME-27 [S] Name the positive; convert negations once, at the boundary

`no_color`, `disable_cache`, and `skip_hidden` compose into double negation: `if !no_color`. The CLI
flag may be negative because the convention demands it — convert to a positive field once, where the
flag is parsed (RS-CLI-12).

**Why:** every reader of `if !no_color` performs a small logic operation to recover the intent, and
under an `&&` with a second negation they will eventually get it wrong.

**Check:** is `!` applied to an identifier containing `no_`, `not_`, `disable`, `skip`, or
`without`?

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

### RS-NAME-28 [M] Never suffix a name with the language construct

No `ConfigTrait`, `ErrorEnum`, `WrapperStruct`, `HandlerImpl`, `FooType`.

**Why:** the declaration already says `trait`/`enum`/`struct`, and the suffix announces the
mechanism instead of the concept — it is the naming equivalent of a comment that restates the code.

**Check:** `rg -n '\b(struct|enum|trait|type) \w+(Trait|Enum|Struct|Impl|Class|Object)\b' -g '*.rs'`
finds a type named for its construct; each hit is the finding.

### RS-NAME-29 [S] Apply role suffixes consistently or not at all

`Builder`, `Guard`, `Handle`, `Ref`, `Iter`, `Error`, `Config`: use the suffix whenever the type
plays that role, and never when it does not.

**Why:** a half-applied convention is worse than none, because the reader cannot tell whether the
absence of `Guard` means "not a guard" or "we forgot". `SearcherBuilder`, `MutexGuard`, and
`JoinHandle` work as a system precisely because there are no exceptions.

**Check:** list every type playing each role. Is the suffix present on all of them, or on none?

### RS-NAME-30 [M] Pick one error-type spelling per crate

Either `Error` inside its own module (`io::Error`, `parse::Error`) or `FooError` at the crate root
when several coexist. Never both spellings in one crate.

**Why:** with both, `use` statements collide unpredictably and readers cannot guess the path of an
error they have not met. The module-scoped spelling scales better; the flat one is fine for a crate
with two error types (RS-ERR-10).

**Check:** is every `Error` in a type position the same shape?

## Generic parameters and lifetimes

### RS-NAME-31 [S] Name a lifetime for the source of the borrow once several coexist

`'a` when there is one. `'src`, `'input`, `'haystack` when there are several and it matters which is
which. Use `'_` wherever it is accepted (rustc `elided_lifetimes_in_paths`).

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

### RS-NAME-32 [M] Never restate the kind in a parameter's name

No `'life`, no `'lifetime`, no type parameter named `Type` or `Generic`.

**Why:** the sigil already conveys the kind, exactly as with RS-NAME-28. `<'lifetime, Type>` is
noise in every signature that mentions it.

**Check:** `rg -n "'life\b|'lifetime\b|<Type\b|<Generic\b" -g '*.rs'` finds a parameter named for
its kind; each hit is the finding.

```rust
// verified
use std::path::Path;

/// The type already says it is a path; the name says which path.
#[must_use]
pub fn read_config(config: &Path) -> Option<&str> {
    config.to_str()
}
```

## Symmetry of names

### RS-NAME-33 [M] Name the two halves of a pair symmetrically

A pair uses matched words: `encode`/`decode`, not `encode`/`parse`; `open`/`close`, not
`open`/`release`; `lock`/`unlock`, not `lock`/`release`. Reuse the ecosystem's pair where one
exists.

**Why:** matched names are what make a pair recognizable as a pair, which is how a reader knows the
inverse exists without looking (RS-API-57). Mismatched halves read as unrelated operations, and the
reader searches for a `decode` that is spelled `parse`.

**Check:** list every operation with an inverse and read the two names together. If they do not
sound like a pair said aloud, rename the odd half.

```rust
// verified
/// A pair uses matched words: `open` / `close`, never `open` / `release`.
#[derive(Debug, Default)]
pub struct Valve {
    open: bool,
}

impl Valve {
    pub fn open(&mut self) {
        self.open = true;
    }

    pub fn close(&mut self) {
        self.open = false;
    }

    #[must_use]
    pub fn is_open(&self) -> bool {
        self.open
    }
}
```

## Formatting

### RS-NAME-34 [M] Hold every line to 100 columns, rustfmt's default

Code, comments, doc comments and string literals stay within 100 columns. `rustfmt` wraps code to
that width and leaves a comment, a string literal and a URL as written, so the author wraps those.
Leave `max_width` unset (RS-BUILD-26).

**Why:** 100 columns is the width `rustfmt` and nearly all of `std` use, and a line past it is the
one a side-by-side diff cuts off. A project that sets another width reopens an argument the default
closes.

**Check:** `rg -n '.{101,}' -g '*.rs'` — a line over 100 characters is the finding, except a URL or
a string literal that cannot be wrapped, which carries a comment saying so.

## Decided by tools

A tool settles these on its own; the shipped configuration enables each at the level shown.

| Tool | Lint | Level | Forbids |
|---|---|---|---|
| rustc | `non_camel_case_types` | warn | a type, trait or enum variant not in `UpperCamelCase` — listed because the casing rule a revision demoted to the three rustc casing lints holds here; `non_snake_case` is the third |
| rustc | `non_upper_case_globals` | warn | a constant, static or const generic parameter not in `SCREAMING_SNAKE_CASE` — listed because the casing rule a revision demoted to the three rustc casing lints holds here |
| clippy | `upper_case_acronyms` | warn | a run of capitals in a type name — `Http`, not `HTTP`, with the shipped aggressive setting — listed because `upper-case-acronyms-aggressive = true` widens it to two-letter runs, and `avoid-breaking-exported-api = false` to public items, both in the shipped `clippy.toml` (RS-NAME-01) |
| clippy | `enum_variant_names` | warn | three or more variants sharing a prefix or suffix, such as `ReadFailed`, `WriteFailed`, `SeekFailed` — listed because `avoid-breaking-exported-api = false` in the shipped `clippy.toml` turns it on for public enums, which RS-NAME-07 is about |
| clippy | `wrong_self_convention` | warn | an `as_`, `to_` or `into_` method whose receiver breaks its prefix: an `into_*` taking `&self` — listed because `avoid-breaking-exported-api = false` in the shipped `clippy.toml` turns it on for public methods, which RS-NAME-11 to RS-NAME-13 are about |
