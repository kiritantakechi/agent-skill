# Traits, Generics, Dispatch, Type-Level Design

Scope: when a trait should exist at all, how to shape one so implementors and callers both benefit,
the static-versus-dynamic dispatch decision, coherence and sealing, where to put bounds, and the
type-level tools — associated types, GATs, const generics, typestate. Naming of traits and their
parameters is in the naming chapter; the semver consequences of trait changes are in the API
chapter; the code-size consequences of monomorphization are in the performance chapter.

Traits are Rust's only abstraction mechanism. The discipline here is **trait-first** at every seam
that will carry two plausible implementations or a test double: name the capability as a trait
before writing the type that provides it, and program against the trait rather than the concrete
type. Where there is one implementation and no double, the concrete type is the design.

The Rust API Guidelines and the BurntSushi crates advise the opposite — extract a trait only once a
second implementation exists. Trait-first buys a boundary that is total and symmetric because no
concrete type shaped it, and costs indirection, extra rustdoc, and a generic parameter at use sites
a concrete struct would not need. RS-TRAIT-46 and RS-TRAIT-02 keep that cost from becoming damage:
if either is being bent to make a trait fit, the trait is wrong and the fallback is a concrete type,
not a partial impl.

## Contents

- **Designing traits**
  - RS-TRAIT-01 [M] Name the capability as a trait before writing the type that provides it
  - RS-TRAIT-02 [M] Describe a capability, not a category
  - RS-TRAIT-03 [S] Keep the required-method set small and push the rest into defaults
  - RS-TRAIT-04 [S] Make provided methods correct by default and overridable for speed
  - RS-TRAIT-05 [S] Add functionality to foreign types through a sealed `…Ext` trait
  - RS-TRAIT-06 [S] Prefer composition to supertrait hierarchies
  - RS-TRAIT-07 [M] Treat a supertrait as a requirement on every implementor
  - RS-TRAIT-08 [S] Do not require `Sized` when you do not need it
  - RS-TRAIT-09 [S] Mark description-shaped traits `#[must_use]`
  - RS-TRAIT-10 [S] Use `#[diagnostic::on_unimplemented]` where the error would be cryptic
  - RS-TRAIT-11 [M] Document the trait's contract, not just its signatures

- **Static versus dynamic dispatch**
  - RS-TRAIT-12 [S] Default to static dispatch
  - RS-TRAIT-13 [S] Choose `dyn` for open sets, heterogeneous storage, or measured bloat
  - RS-TRAIT-14 [S] Do not use argument-position `impl Trait` where callers may want to name the type
  - RS-TRAIT-15 [S] Use return-position `impl Trait` for iterators, futures, and closures
  - RS-TRAIT-16 [M] Keep a trait dyn-compatible if it might ever be boxed
  - RS-TRAIT-17 [S] Write the lifetime on a borrowing trait object
  - RS-TRAIT-18 [M] Prefer an enum to a trait object for a closed set
  - RS-TRAIT-19 [S] Do not mix dispatch strategies for one abstraction
  - RS-TRAIT-20 [S] Do not nest generics three deep in a public signature

- **Coherence, blanket impls, sealing**
  - RS-TRAIT-21 [M] Work with the orphan rule, not around it
  - RS-TRAIT-22 [M] Newtype to implement a foreign trait on a foreign type
  - RS-TRAIT-23 [M] Treat a blanket impl as permanent
  - RS-TRAIT-24 [S] Bound on a trait rather than impl for each std type
  - RS-TRAIT-25 [S] Seal a trait that enumerates a fixed set of types
  - RS-TRAIT-26 [M] Document that a trait is sealed and why
  - RS-TRAIT-27 [M] Do not seal a trait users are meant to implement
  - RS-TRAIT-28 [M] Do not design around specialization
  - RS-TRAIT-29 [M] Know that a blanket `From<T>` conflicts with the reflexive impl

- **Bounds, where clauses, inference**
  - RS-TRAIT-30 [S] Put simple bounds inline and anything longer in a `where` clause
  - RS-TRAIT-31 [S] Bound at the point of use, not on the struct
  - RS-TRAIT-32 [M] Minimize bounds
  - RS-TRAIT-33 [S] Genericize a parameter only where the flexibility is used
  - RS-TRAIT-34 [S] Do not return a type the caller must turbofish
  - RS-TRAIT-35 [S] Use type aliases to tame long generic types
  - RS-TRAIT-36 [S] Comment a type alias that hides genuine complexity
  - RS-TRAIT-37 [S] Use `where Self: Sized` on methods rather than losing dyn compatibility

- **Associated types, GATs, const generics**
  - RS-TRAIT-38 [M] Associated type for one-per-implementor, parameter for many
  - RS-TRAIT-39 [S] Bound associated types at their declaration
  - RS-TRAIT-40 [S] Reach for a GAT only after a plain associated type has failed
  - RS-TRAIT-41 [S] Use const generics where the size is genuinely compile-time
  - RS-TRAIT-42 [S] Do not emulate variadics past a small arity
  - RS-TRAIT-43 [S] Use typestate where misuse is costly and the states are few
  - RS-TRAIT-44 [S] Do not build a typestate machine with many states
  - RS-TRAIT-45 [M] Make marker traits zero-method and documented

- **Totality and symmetry of impls**
  - RS-TRAIT-46 [M] Make every impl total — no `unimplemented!()` arms
  - RS-TRAIT-47 [S] Keep the impl set symmetric across a family of types

---

## Designing traits

### RS-TRAIT-01 [M] Name the capability as a trait before writing the type that provides it

At a seam that will carry two plausible implementations, or a test double, write the trait first, in
terms of what a caller needs, then implement it. Program against the trait — take `impl Read`, not
`File` — so the first implementation is never privileged. A type with one implementation and no
double stays concrete (RS-TRAIT-33), and a closed set is an enum (RS-TRAIT-18).

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

### RS-TRAIT-02 [M] Describe a capability, not a category

`Read`, `Write`, `Display`, `Matcher`, `Sink` — not `Animal`, `Entity`, `Base`. The name is a verb
or an agent noun derived from one; `-able` rarely reads well, and `std` has `IntoIterator`, not
`Iterable`.

**Why:** Rust has no inheritance and does not model "is a". A trait says what you can *do* with a
value, and designing one as a category leads directly to a supertrait hierarchy trying to be a class
tree — which fights the language at every step.

**Check:** does the trait's name and method set describe an action set, or a taxonomy position? A
name for what a type *is* is usually a design error surfacing as a naming one.

```rust
// verified
/// A capability, not a category: it says what you can do, not what the value *is*.
pub trait Matcher {
    /// Returns `true` when `haystack` satisfies the matcher.
    fn matches(&self, haystack: &str) -> bool;
}

#[derive(Debug, Clone)]
pub struct Literal(String);

impl Matcher for Literal {
    fn matches(&self, haystack: &str) -> bool {
        haystack.contains(&self.0)
    }
}
```

### RS-TRAIT-03 [S] Keep the required-method set small and push the rest into defaults

**Why:** each required method is work for every implementor, including ones you never meet, and one
more way an implementation can disagree with itself; provided methods are free ergonomics. That is
why `grep-matcher`'s `Matcher`, a handful required and many provided, is pleasant to implement.

**Check:** for each required method, could it have a default in terms of the others? More than three
required methods is worth a redesign pass.

```rust
// verified
/// One required method; everything else is a default the implementor may override.
pub trait Encoder {
    /// Encodes a single frame.
    fn encode(&self, frame: &[u8]) -> Vec<u8>;

    /// Encodes many frames. Override when a batch form is cheaper.
    fn encode_all(&self, frames: &[&[u8]]) -> Vec<u8> {
        frames.iter().flat_map(|frame| self.encode(frame)).collect()
    }
}
```

### RS-TRAIT-04 [S] Make provided methods correct by default and overridable for speed

**Why:** `Iterator::size_hint` and `Iterator::fold` are the model — the default is always right, and
an implementor who can do better overrides it. That is the shape that lets a trait serve both a
five-line implementor and a highly tuned one.

**Check:** does the rustdoc say when overriding is worthwhile, and what the override must preserve?

```rust
// verified
/// The default is correct for everyone; an implementor overrides it only for speed.
pub trait Counter {
    /// Counts one item.
    fn count_one(&self, item: &str) -> usize;

    /// Counts many. The default is correct; override it when a batch form is cheaper.
    fn count_all(&self, items: &[String]) -> usize {
        items.iter().map(|item| self.count_one(item)).sum()
    }
}
```

### RS-TRAIT-05 [S] Add functionality to foreign types through a sealed `…Ext` trait

`ItertoolsExt`, `SliceRandom`. For a whole family, a blanket impl (`impl<T: Iterator> MyExt for T`)
puts the methods on values users already hold, with nothing to wrap.

**Why:** it is the only way the orphan rule permits (RS-TRAIT-21), it keeps the added methods
discoverable through autocomplete, and sealing it means you can add methods later without breaking
anyone (RS-TRAIT-25).

**Check:** is the extension trait sealed? Is the name suffixed so users can tell where the method
came from? Does using the crate require constructing a wrapper first? A blanket impl removes it.

```rust
// verified
mod sealed {
    pub trait Sealed {}
    impl Sealed for str {}
}

/// An extension trait on a foreign type, sealed so the impl set stays closed.
pub trait StrExt: sealed::Sealed {
    /// Returns the text with any single trailing newline removed.
    fn trim_one_newline(&self) -> &str;
}

impl StrExt for str {
    fn trim_one_newline(&self) -> &str {
        self.strip_suffix('\n').unwrap_or(self)
    }
}
```

### RS-TRAIT-06 [S] Prefer composition to supertrait hierarchies

**Why:** a struct holding a `Matcher` and a `Printer` is easier to understand, test, and change than
a five-level supertrait chain. Supertraits are for genuine prerequisites — `trait Ord: PartialOrd` —
not for reuse.

**Check:** how deep is the deepest supertrait chain? More than one level usually means reuse
pretending to be a prerequisite.

### RS-TRAIT-07 [M] Treat a supertrait as a requirement on every implementor

**Why:** adding one is a breaking change, and adding `Debug` or `Clone` "for convenience" excludes
every implementor that cannot provide them — a type holding a file handle, a closure, or a foreign
pointer. The convenience is yours; the exclusion is theirs.

**Check:** for each supertrait, is it needed by the trait's own default methods, or only by your
call sites? If the latter, bound at the call site instead (RS-TRAIT-31).

```rust
// verified
use std::fmt::Debug;

/// A supertrait is a requirement every implementor must already meet.
pub trait Record: Debug {
    /// Returns the record's stable identifier.
    fn id(&self) -> u64;
}

#[derive(Debug)]
pub struct Row(u64);

impl Record for Row {
    fn id(&self) -> u64 {
        self.0
    }
}
```

### RS-TRAIT-08 [S] Do not require `Sized` when you do not need it

`T: ?Sized + Display` lets callers pass `str` and `[T]` directly.

**Why:** `Sized` is an implicit default bound, so it is easy to require without noticing. Relaxing
it costs nothing when the caller has a sized type and enables the unsized case for free.

**Check:** does the body ever move or store a `T` by value? If not, `?Sized` is available.

```rust
// verified
/// `?Sized` so the bound also accepts `str` and slices.
#[must_use]
pub fn describe<T: std::fmt::Debug + ?Sized>(value: &T) -> String {
    format!("{value:?}")
}
```

### RS-TRAIT-09 [S] Mark description-shaped traits `#[must_use]`

Matchers, queries, builders — values that describe rather than act. Mark each concrete implementor
`#[must_use]` too.

**Why:** constructing one and discarding it is always a mistake. On the trait the attribute covers
only an `impl Trait` or `dyn Trait` value; a discarded concrete implementor warns only if its own
type carries the attribute (`references/api.md` RS-API-33).

**Check:** would discarding a value of this trait ever be correct? Does every implementor carry the
attribute as well?

```rust
// verified
/// A description-shaped trait: the value exists to be inspected, so it is `#[must_use]`.
#[must_use = "a plan describes work that only happens once it is executed"]
pub trait Plan {
    /// Returns how many steps the plan contains.
    fn steps(&self) -> usize;
}

/// The trait's attribute covers `impl Plan` values only, so the type carries its own.
#[must_use = "a plan describes work that only happens once it is executed"]
#[derive(Debug)]
pub struct Steps(usize);

impl Plan for Steps {
    fn steps(&self) -> usize {
        self.0
    }
}
```

### RS-TRAIT-10 [S] Use `#[diagnostic::on_unimplemented]` where the error would be cryptic

`#[diagnostic::on_unimplemented(message = "…", note = "…")]` on the trait. On a blanket impl, add
`#[diagnostic::do_not_recommend]`, so the error names the trait the bound asked for rather than the
blanket impl's own bound.

**Why:** the default message names the trait and the type and leaves the user to work out which of
five bounds failed and why. A one-line message here saves every user of the crate a search, and it
costs nothing at runtime.

**Check:** deliberately break a bound and read the error. Would a new user know what to do?

### RS-TRAIT-11 [M] Document the trait's contract, not just its signatures

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

## Static versus dynamic dispatch

### RS-TRAIT-12 [S] Default to static dispatch

`impl Trait` in argument position for simple cases; a named generic parameter when the type appears
more than once (and when a caller may name it, RS-TRAIT-14).

**Why:** it is the zero-overhead default, it preserves the concrete type for the optimizer, and it
keeps the door open — a generic taking `&T` where `T: Trait + ?Sized` also accepts a `&dyn Trait`
(without `?Sized`, E0277), but a `dyn`-taking function cannot be specialized.

**Check:** is there a measured reason for the vtable? If not, start static.

```rust
// verified
/// Static dispatch by default: monomorphized, inlinable, no vtable.
pub fn count_matching<P: Fn(&str) -> bool>(lines: &[String], predicate: P) -> usize {
    lines.iter().filter(|line| predicate(line)).count()
}
```

### RS-TRAIT-13 [S] Choose `dyn` for open sets, heterogeneous storage, or measured bloat

**Why:** a vtable call costs a few nanoseconds and a predictable indirect branch; forty
monomorphized copies of a large function cost kilobytes of instruction cache. A `Vec` of mixed
implementations needs `dyn` outright (`references/performance.md` RS-PERF-27).

**Check:** how many instantiations does this generic actually get? `cargo bloat` will tell you if
you suspect the answer is "too many".

```rust
// verified
/// `dyn` where the set is open and the values are stored heterogeneously.
pub trait Stage {
    /// Transforms one record.
    fn apply(&self, input: String) -> String;
}

#[derive(Default)]
pub struct Pipeline {
    stages: Vec<Box<dyn Stage>>,
}

impl std::fmt::Debug for Pipeline {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("Pipeline")
            .field("stages", &self.stages.len())
            .finish()
    }
}

impl Pipeline {
    #[must_use]
    pub fn run(&self, input: String) -> String {
        self.stages
            .iter()
            .fold(input, |value, stage| stage.apply(value))
    }
}
```

### RS-TRAIT-14 [S] Do not use argument-position `impl Trait` where callers may want to name the type

**Why:** it is sugar for an anonymous generic parameter, which means the caller cannot turbofish it
— so a call that needs an explicit type has no way to give one. In a public API that is a one-way
door.

**Check:** would a caller ever need `::<T>` on this function? Then use a named parameter.

```rust
// verified
/// A named parameter, so a caller passing an empty slice can name its element type.
#[must_use]
pub fn total<N: Copy + Into<u64>>(values: &[N]) -> u64 {
    values.iter().map(|&value| value.into()).sum()
}

#[cfg(test)]
mod tests {
    #[test]
    fn an_empty_slice_names_its_type_with_a_turbofish() {
        assert_eq!(super::total::<u8>(&[]), 0);
    }
}
```

### RS-TRAIT-15 [S] Use return-position `impl Trait` for iterators, futures, and closures

Return-position `impl Trait` works in trait methods as well as free functions. A factory returns
`impl Fn`, not `Box<dyn Fn>`: it allocates nothing, and a caller who needs a box can still make one.

**Why:** it hides an unnameable or noisy concrete type while preserving static dispatch and
zero-cost composition. The cost is that users cannot name the type for storage — where they need to,
return a named type or expose a type alias instead.

**Check:** does a caller need to put this return value in a struct field, or store closures from
several factories side by side? Then name the type, or box at that one site.

```rust
// verified
/// Return-position `impl Trait` keeps the concrete iterator private and unnameable.
pub fn evens(limit: u32) -> impl Iterator<Item = u32> {
    (0..limit).filter(|value| value.is_multiple_of(2))
}

/// A factory returns the closure itself, with its configuration captured.
pub fn longer_than(limit: usize) -> impl Fn(&str) -> bool {
    move |value| value.len() > limit
}
```

### RS-TRAIT-16 [M] Keep a trait dyn-compatible if it might ever be boxed

No generic methods, no `Self` in return position, no associated constants. An associated constant
becomes a method returning the value, one indirect call that keeps `Box<dyn Trait>` available. A
generic method takes `where Self: Sized` (RS-TRAIT-37), or the trait splits into a dyn-compatible
core plus a generic extension trait.

**Why:** dyn compatibility (formerly "object safety") cannot be added later without a breaking
change, and discovering you need `Box<dyn Trait>` after publication is common.

**Check:** does `fn _assert(_: &dyn MyTrait) {}` compile? That one line is the whole test.

```rust
// verified
/// Dyn-compatible: no generic methods, no `Self` by value, so it can be boxed.
pub trait Sink {
    /// Accepts one already-rendered line.
    fn accept(&mut self, line: &str);
}

#[derive(Debug, Default)]
pub struct Collect(Vec<String>);

impl Sink for Collect {
    fn accept(&mut self, line: &str) {
        self.0.push(line.to_owned());
    }
}

#[must_use]
pub fn boxed() -> Box<dyn Sink> {
    Box::new(Collect::default())
}
```

### RS-TRAIT-17 [S] Write the lifetime on a borrowing trait object

`Box<dyn Matcher + 'a>`.

**Why:** `Box<dyn Trait>` defaults to `+ 'static`, so a trait object holding a borrow fails to
compile with an error that points at the wrong place. Being explicit turns a confusing lifetime
error at the call site into a correct signature.

**Check:** does any `dyn` type hold borrowed data? Then the lifetime is not `'static`.

### RS-TRAIT-18 [M] Prefer an enum to a trait object for a closed set

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

### RS-TRAIT-19 [S] Do not mix dispatch strategies for one abstraction

**Why:** if half the API takes `impl Matcher` and half takes `&dyn Matcher`, users must learn which
is which and convert between them at boundaries. Pick one per abstraction so there is one pattern to
learn.

**Check:** grep for the trait's name. Is it used both generically and as `dyn` in the public API?

### RS-TRAIT-20 [S] Do not nest generics three deep in a public signature

`Searcher<M: Matcher, S: Sink<M::Error>>` nested three levels.

**Why:** the type in the error message becomes a paragraph, inference fails in ways that are hard to
diagnose, and the rustdoc is unreadable. Erase one level with `dyn`, or provide a type alias for the
default configuration so the common case is one word.

**Check:** read the fully-expanded type from a deliberate error. Does it fit on a line?

## Coherence, blanket impls, sealing

### RS-TRAIT-21 [M] Work with the orphan rule, not around it

**Why:** it exists so two crates cannot define the same impl and break linking, and there is no
workaround — only a local trait or a local newtype. Time spent looking for one is time not spent on
the newtype that would have worked.

**Check:** is either the trait or the type local to this crate? If neither, you need a newtype
(RS-TRAIT-22).

### RS-TRAIT-22 [M] Newtype to implement a foreign trait on a foreign type

**Why:** it is the sanctioned mechanism, it is zero-cost with `#[repr(transparent)]`, and it lets
you add the impl without any coordination. Add `AsRef`/`Deref` only if the newtype genuinely *is*
the inner type for all purposes (`references/api.md` RS-API-45).

**Check:** does the newtype expose the inner type's whole API, or only the part that makes sense?

```rust
// verified
use std::fmt;

/// A newtype is how you implement a foreign trait on a foreign type.
#[derive(Debug, Clone, Copy)]
pub struct Hex(u32);

impl Hex {
    #[must_use]
    pub fn new(bits: u32) -> Self {
        Self(bits)
    }
}

impl fmt::Display for Hex {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{:#010x}", self.0)
    }
}
```

### RS-TRAIT-23 [M] Treat a blanket impl as permanent

`impl<T: Foo> Bar for T`.

**Why:** it forbids every downstream `Bar` impl that could overlap, forever, and removing it is
breaking. It is the most powerful and least reversible thing in the trait system, so it should only
express an implication that is genuinely universal.

**Check:** is there any type for which this impl would be wrong or unwanted? One is enough to make
it a bad blanket.

### RS-TRAIT-24 [S] Bound on a trait rather than impl for each std type

**Why:** `AsRef<[T]>` covers `Vec<T>`, `[T; N]`, `&[T]`, `Box<[T]>`, and types you have never heard
of, in one impl. Writing separate impls for `Vec<T>` and `String` covers two of them and dates
immediately.

**Check:** is there a std trait that generalizes the set of impls you are writing?

### RS-TRAIT-25 [S] Seal a trait that enumerates a fixed set of types

Private-supertrait pattern.

**Why:** sealing means you know every implementor, so you can add methods later without breaking
anyone. Unsealed, even a defaulted method can collide with a downstream inherent method, and sealing
after publication is breaking outright, so the decision is cheap only before release.

**Check:** is the trait an extension point or an enumeration? Only the second gets sealed, and the
question is answered for each public trait before its first release.

```rust
// verified
use std::borrow::Cow;

mod sealed {
    pub trait Sealed {}
}

/// Sealed because the set of encodings is an enumeration, not an extension point.
pub trait Encoding: sealed::Sealed {
    /// Decodes bytes, borrowing when the input is already valid.
    fn decode<'bytes>(&self, bytes: &'bytes [u8]) -> Cow<'bytes, str>;
}

#[derive(Debug, Clone, Copy)]
pub struct Utf8;

impl sealed::Sealed for Utf8 {}
impl Encoding for Utf8 {
    fn decode<'bytes>(&self, bytes: &'bytes [u8]) -> Cow<'bytes, str> {
        String::from_utf8_lossy(bytes)
    }
}
```

### RS-TRAIT-26 [M] Document that a trait is sealed and why

**Why:** without a note, someone who tries to implement it gets `trait 'Sealed' is private`, which
names a type they cannot see and explains nothing. One sentence in the rustdoc turns a confusing
error into an understood constraint.

**Check:** does every sealed trait's rustdoc say so in its first paragraph?

### RS-TRAIT-27 [M] Do not seal a trait users are meant to implement

**Why:** sealing an extension point is a design error that only a major version can fix, and it
turns your crate from a library into a closed system. The two categories are decided at design time,
not discovered later.

**Check:** for each sealed trait, is there a plausible downstream implementor? If yes, unseal it now
while it is free.

### RS-TRAIT-28 [M] Do not design around specialization

**Why:** it is unstable with no stabilization date, `min_specialization` is unsound in its general
form, and code written to "use it later" gets rewritten. Use an enum, an explicit impl per type, or
a runtime check.

**Check:** grep for `default fn` and `#![feature(specialization)]`. Both mean nightly-only forever.

### RS-TRAIT-29 [M] Know that a blanket `From<T>` conflicts with the reflexive impl

**Why:** `impl<T> From<T> for MyType` overlaps with core's `impl<T> From<T> for T` at `T = MyType`,
so rustc rejects it with E0119 and names the reflexive impl in `core`. A conversion API designed
around a blanket `From` is redesigned the first time it is compiled.

**Check:** narrow the bound (`impl<T: Display> From<T> for MyType` still conflicts at `T = MyType`
if `MyType: Display`) or write per-type impls.

## Bounds, where clauses, inference

### RS-TRAIT-30 [S] Put simple bounds inline and anything longer in a `where` clause

**Why:** a signature that wraps across three lines because of inline bounds is harder to read than
the same one with the bounds moved below, where they align and can be commented individually.

**Check:** does the signature fit on one line with the bounds inline? If not, use `where`.

```rust
// verified
use std::fmt::Display;
use std::hash::Hash;

/// One bound inline; several go in a `where` clause where they can be read.
pub fn render<K, V>(pairs: &[(K, V)]) -> Vec<String>
where
    K: Display + Eq + Hash,
    V: Display,
{
    pairs
        .iter()
        .map(|(key, value)| format!("{key}={value}"))
        .collect()
}
```

### RS-TRAIT-31 [S] Bound at the point of use, not on the struct

**Why:** `struct Cache<K, V>` with bounds only on the `impl` blocks that need them stays usable in
contexts where the bound is irrelevant — a field declaration, a `PhantomData`, a `Default` impl.
Bounds on the struct propagate to every one of those.

**Check:** does the struct definition carry a bound that only one method needs?

```rust
// verified
/// The bound is at the point of use, so the struct itself stays unconstrained.
#[derive(Debug, Default)]
pub struct Bag<T> {
    items: Vec<T>,
}

impl<T> Bag<T> {
    pub fn push(&mut self, item: T) {
        self.items.push(item);
    }
}

impl<T: std::fmt::Display> Bag<T> {
    #[must_use]
    pub fn render(&self) -> String {
        self.items
            .iter()
            .map(ToString::to_string)
            .collect::<Vec<_>>()
            .join(", ")
    }
}
```

### RS-TRAIT-32 [M] Minimize bounds

**Why:** each bound is a requirement on every caller. `T: Clone` when you only need `&T` is a
needless restriction; `T: Ord` when `PartialOrd` suffices excludes floats; `T: Debug` for a log line
excludes everything without a `Debug` impl.

**Check:** remove each bound and see whether it still compiles. The ones that were unnecessary are
the ones you would never have found by reading.

```rust
// verified
/// Bound only on what the body uses: `Display`, not `Display + Clone + Debug`.
pub fn render<T: std::fmt::Display>(items: &[T]) -> String {
    items
        .iter()
        .map(ToString::to_string)
        .collect::<Vec<_>>()
        .join(", ")
}
```

### RS-TRAIT-33 [S] Genericize a parameter only where the flexibility is used

**Why:** `impl AsRef<Path>` is worth it because callers genuinely hold four different path-like
types. `impl Into<u32>` is not, because they hold a `u32`. Genericity has an inference cost, a
documentation cost, and a monomorphization cost.

**Check:** list the concrete types this parameter will be instantiated with. One means make it
concrete.

### RS-TRAIT-34 [S] Do not return a type the caller must turbofish

**Why:** if users must write `::<Vec<_>>` at every call site, the API is asking them to do
inference's job. Either return a concrete type or take the target as a parameter they already have.

**Check:** write a call in a doc example without any annotation. Does it compile?

### RS-TRAIT-35 [S] Use type aliases to tame long generic types

`pub type Result<T> = std::result::Result<T, Error>;`

**Why:** it is the single highest-value alias in most crates — it removes the error type from every
signature in the crate and from every doc example, and it is what users expect from `io::Result` and
`fmt::Result`.

**Check:** does the crate's error type appear in more than a handful of signatures?

```rust
// verified
/// A type alias tames a signature that would otherwise be unreadable.
pub type Handler = Box<dyn Fn(&str) -> Option<String> + Send + Sync>;

#[derive(Default)]
pub struct Router {
    routes: Vec<(String, Handler)>,
}

impl std::fmt::Debug for Router {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("Router")
            .field("routes", &self.routes.len())
            .finish()
    }
}
```

### RS-TRAIT-36 [S] Comment a type alias that hides genuine complexity

**Why:** an alias for
`Box<dyn Fn(&Request) -> Pin<Box<dyn Future<Output = Result<Response, Error>> + Send>> + Send + Sync>`
is right, and so is a comment explaining the shape — otherwise the alias hides the complexity from
the maintainer as well as the user.

**Check:** could a new contributor reconstruct the expansion from the alias name alone?

### RS-TRAIT-37 [S] Use `where Self: Sized` on methods rather than losing dyn compatibility

**Why:** this is how `Iterator` keeps `Box<dyn Iterator>` working while still offering `map`,
`collect`, and the rest — the generic methods are excluded from the vtable rather than excluding the
trait from `dyn` (RS-TRAIT-16).

**Check:** which method is breaking dyn compatibility? Can it take `where Self: Sized`?

## Associated types, GATs, const generics

### RS-TRAIT-38 [M] Associated type for one-per-implementor, parameter for many

`Iterator` has one `Item`; `From<T>` has many `T`. Were `Item` a parameter, every use site would
write `fn f<I: Iterator<Item = T>, T>` where `fn f<I: Iterator>` does.

**Why:** getting this backwards is the most consequential trait-design mistake available. An
associated type where a parameter belongs makes the trait implementable only once per type; a
parameter where an associated type belongs makes every use site annotate.

**Check:** would one type reasonably implement this trait more than once? Yes means parameter.

```rust
// verified
/// One output type per implementor is an associated type, not a parameter.
pub trait Source {
    /// The item this source yields.
    type Item;

    /// Returns the next item, if any.
    fn next_item(&mut self) -> Option<Self::Item>;
}
```

### RS-TRAIT-39 [S] Bound associated types at their declaration

`type Error: std::error::Error + Send + Sync + 'static;`

**Why:** the bound then holds everywhere the associated type appears, so no use site has to repeat
it and no implementor can supply something unusable. Adding the bound later is breaking.

**Check:** does any generic function repeat a bound on `T::Error` or `I::Item`? That bound belongs
on the declaration.

### RS-TRAIT-40 [S] Reach for a GAT only after a plain associated type has failed

**Why:** GATs are the right tool for lending iterators and for associated types that borrow from
`&self`, and they are a significant complexity cost in error messages and in implementor burden.
Most designs that reach for them first do not need them.

**Check:** does the associated type genuinely need to name a lifetime from `&self`? Write the plain
version first and let it fail.

### RS-TRAIT-41 [S] Use const generics where the size is genuinely compile-time

`struct Chunk<const N: usize>`, `fn hash<const OUT: usize>(…) -> [u8; OUT]`.

**Why:** each distinct `N` is a separate monomorphization, so const generics buy stack allocation
and unrolling at the cost of code size. That is a good trade when the sizes are few and known and a
bad one when they come from configuration.

**Check:** how many distinct values of `N` will exist? More than a handful means use a runtime
length.

```rust
// verified
/// Const generics where the size is genuinely compile-time.
#[derive(Debug, Clone, Copy)]
pub struct Digest<const BYTES: usize>([u8; BYTES]);

impl<const BYTES: usize> Digest<BYTES> {
    #[must_use]
    pub fn as_bytes(&self) -> &[u8; BYTES] {
        &self.0
    }
}
```

### RS-TRAIT-42 [S] Do not emulate variadics past a small arity

**Why:** the ecosystem convention is tuple impls up to 12, generated by a macro. Past that the
compile time and the rustdoc noise grow faster than the convenience, and a slice or a struct is
clearer anyway.

**Check:** is the macro generating impls for arities nobody uses?

### RS-TRAIT-43 [S] Use typestate where misuse is costly and the states are few

`Connection<Idle>` → `Connection<Open>`.

**Why:** it turns "write before connect" from a runtime panic into a compile error, which is
strictly better when the mistake is expensive and the transitions are few
(`references/functional.md` RS-FUNC-40).

**Check:** does any method start by checking a state flag and erroring? That check is a type.

```rust
// verified
/// Typestate: `send` does not exist until the connection is open.
use std::marker::PhantomData;

#[derive(Debug)]
pub struct Closed;

#[derive(Debug)]
pub struct Open;

#[derive(Debug)]
pub struct Connection<State> {
    addr: String,
    sent: usize,
    state: PhantomData<fn() -> State>,
}

impl Connection<Closed> {
    #[must_use]
    pub fn new(addr: impl Into<String>) -> Self {
        Self {
            addr: addr.into(),
            sent: 0,
            state: PhantomData,
        }
    }

    #[must_use]
    pub fn open(self) -> Connection<Open> {
        Connection {
            addr: self.addr,
            sent: self.sent,
            state: PhantomData,
        }
    }
}

impl Connection<Open> {
    pub fn send(&mut self, payload: &[u8]) {
        self.sent += payload.len();
    }

    #[must_use]
    pub fn sent(&self) -> usize {
        self.sent
    }

    #[must_use]
    pub fn addr(&self) -> &str {
        &self.addr
    }
}
```

### RS-TRAIT-44 [S] Do not build a typestate machine with many states

**Why:** the error messages and the documentation cost grow faster than the safety benefit. Past a
handful of states, users cannot tell which method is available when, and a runtime state enum with a
clear error is kinder.

**Check:** count the states. More than about four and the rustdoc becomes a state diagram nobody
reads.

### RS-TRAIT-45 [M] Make marker traits zero-method and documented

**Why:** a marker trait's whole content is its invariant, so if the invariant is not written down
the trait means nothing. If violating it causes unsoundness, it must be `unsafe trait`
(`references/unsafe.md` RS-UNSAFE-20).

**Check:** does the marker trait's rustdoc state exactly what implementing it asserts?

```rust
// verified
/// A marker trait is zero-method and says what it guarantees.
///
/// Implementors promise their `Debug` output contains no secrets.
pub trait RedactionFree {}

#[derive(Debug, Clone, Copy)]
pub struct RequestId(u64);

impl RedactionFree for RequestId {}
```

## Totality and symmetry of impls

### RS-TRAIT-46 [M] Make every impl total — no `unimplemented!()` arms

Every implementor supports every method for real. An impl that panics, returns `Err(Unsupported)`,
or silently does nothing for part of the trait is a partial impl, and partial impls are the failure
mode trait-first design has to avoid (RS-TRAIT-01). A method only one implementor can support is an
inherent method or a separate trait.

**Why:** the whole value of programming against a trait is that the caller need not know which
implementor they hold. A partial impl destroys exactly that: the caller must now know, and the
compiler cannot tell them. The trait is then worse than the concrete types it replaced.

**Check:** grep impls for `unimplemented!`, `todo!`, `panic!`, and error variants meaning "not
supported", and provided methods whose default does the same. Each says the trait is too wide —
split it, or narrow it to what all implementors can do.

```rust
// verified
/// Reading is what every store supports, so it is all `Storage` asks for.
pub trait Storage {
    /// Reads a value if present.
    fn read(&self, key: &str) -> Option<&str>;
}

/// Writing is a separate capability, so a read-only store need not pretend.
pub trait MutableStorage: Storage {
    /// Writes a value.
    fn write(&mut self, key: &str, value: String);
}

/// A read-only snapshot: total over `Storage`, and never a `MutableStorage`.
#[derive(Debug, Default)]
pub struct Snapshot {
    entries: Vec<(String, String)>,
}

impl Storage for Snapshot {
    fn read(&self, key: &str) -> Option<&str> {
        self.entries
            .iter()
            .find(|(k, _)| k == key)
            .map(|(_, v)| v.as_str())
    }
}
```

### RS-TRAIT-47 [S] Keep the impl set symmetric across a family of types

Related types carry the same trait impls: if one wrapper is `Serialize`, `Debug`, and `Clone`, its
siblings are too, or the omission is documented.

**Why:** a caller writing generic code over the family bounds on the traits they need, and one
sibling missing one impl excludes it from every such function — usually discovered long after the
type was added. The asymmetry is almost never deliberate.

**Check:** tabulate the family against the trait set. A missing cell is either an oversight or a
documented restriction; there is no third case (`RS-API-36`).

```rust
// verified
/// The family carries the same impl set, so generic code over it excludes nobody.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub struct Meters(u32);

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub struct Seconds(u32);

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub struct Bytes(u32);
```
