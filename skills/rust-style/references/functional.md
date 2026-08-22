# Functional Style: Expressions, Iterators, Immutability, Purity

Scope: the shape of a function body. Expression orientation and the `match`/`let else`/`matches!`
vocabulary, the iterator adapter set and when each one is the right word, the discipline around
`mut` and shadowing, closures and their bounds, and the separation of computation from effect.
Ownership consequences of these choices are in the ownership chapter; the allocation cost of the
same choices is in the performance chapter; what a *signature* should look like is in the API
chapter.

Rust is not Haskell and should not pretend to be. But it is an expression-oriented language with
algebraic data types, first-class closures, and the best iterator library of any systems language —
and code that leans on those facilities is shorter, safer, and usually faster than the
loop-and-mutate equivalent, because the optimizer sees more and the reader sees less. The goal is
not purity. It is **fewer moving parts**: fewer mutable bindings to track, fewer intermediate states
that can be wrong, fewer places where an early `return` skips a cleanup.
## Contents

- **Expression orientation**
  - RS-FP-01 [M] Make everything that can be an expression one
  - RS-FP-02 [S] Omit the trailing `return`
  - RS-FP-03 [M] Prefer `match` to an `if`/`else if` chain on one value
  - RS-FP-04 [S] A `for` loop that only pushes is a `collect`
  - RS-FP-05 [S] A `for` loop that only accumulates a scalar is a fold
  - RS-FP-06 [S] A `for` loop that searches and breaks is `find`, `any`, or `position`
  - RS-FP-07 [M] Keep `for` for the three things it is actually better at
  - RS-FP-08 [S] Use `let ... else` for destructure-or-bail
  - RS-FP-09 [S] Use `matches!` for boolean tests on shape
  - RS-FP-10 [S] Flatten nested `if let` with let-chains

- **Iterators and pipelines**
  - RS-FP-11 [S] Reach for the most specific adapter that says the intent
  - RS-FP-12 [M] Never index a slice inside a loop over its own indices
  - RS-FP-13 [M] Choose `iter`, `iter_mut`, or `into_iter` deliberately
  - RS-FP-14 [M] Chain adapters; do not collect in the middle
  - RS-FP-15 [S] Prefer the named aggregate to a hand-rolled fold
  - RS-FP-16 [S] Reserve `fold` for accumulation that no `collect` expresses
  - RS-FP-17 [M] Short-circuit fallible iteration with `try_fold` / `try_for_each`
  - RS-FP-18 [S] Use `scan` only when the state belongs to the pipeline
  - RS-FP-19 [S] Use `peekable` and `by_ref` instead of a manual buffer
  - RS-FP-20 [S] Prefer the one-word adapter to the equivalent closure
  - RS-FP-21 [M] Keep iterators lazy as far up the stack as you can
  - RS-FP-22 [S] Pre-size when `size_hint` cannot
  - RS-FP-23 [S] Collect directly into the collection the caller needs
  - RS-FP-24 [S] Do not build a collection to measure it
  - RS-FP-25 [S] Replace index arithmetic with the adapters that encode it
  - RS-FP-26 [S] Justify `itertools` by naming the adapters you use
  - RS-FP-27 [S] Break a pipeline the reader cannot hold
  - RS-FP-28 [S] Keep the pipeline shape that `rayon` can parallelize

- **Immutability and bindings**
  - RS-FP-29 [S] Treat every `let mut` as a proof obligation
  - RS-FP-30 [S] Prefer shadowing to mutation for stepwise refinement
  - RS-FP-31 [M] Do not shadow across a large scope or with a new meaning
  - RS-FP-32 [M] Declare a binding where it is initialized
  - RS-FP-33 [S] Push constants into `const` and `const fn`
  - RS-FP-34 [S] Use the in-place operations that have functional signatures
  - RS-FP-35 [M] Never mutate a captured variable from inside `map`
  - RS-FP-36 [S] Use `inspect` for legitimate mid-pipeline observation
  - RS-FP-37 [S] Return finished data as `Box<[T]>` or `Arc<[T]>`
  - RS-FP-38 [M] Justify each use of interior mutability in a comment
  - RS-FP-39 [S] Reserve `mem::take` / `mem::replace` for state machines
  - RS-FP-40 [S] Give a build-once type no `&mut self` methods at all

- **Closures and functions as values**
  - RS-FP-41 [S] Pass function paths, not forwarding closures
  - RS-FP-42 [M] Choose the loosest closure bound the callee needs
  - RS-FP-43 [S] Take closures generically when hot, boxed when stored
  - RS-FP-44 [S] Capture as little as possible
  - RS-FP-45 [M] Understand that `move` moves everything captured
  - RS-FP-46 [S] Return `impl Fn` rather than `Box<dyn Fn>` from factories
  - RS-FP-47 [S] Name a closure that outgrows a few lines
  - RS-FP-48 [S] Take a policy function instead of a row of booleans
  - RS-FP-49 [M] Clone explicitly before a closure that is spawned
  - RS-FP-50 [S] Use `fn` pointers for tables of handlers

- **Purity, effects, composition**
  - RS-FP-51 [M] Separate computing from doing
  - RS-FP-52 [S] Push effects to the edges
  - RS-FP-53 [M] Parse, don't validate
  - RS-FP-54 [S] Make functions total where you can
  - RS-FP-55 [S] Take the clock, the RNG, and the filesystem as parameters
  - RS-FP-56 [S] Model state transitions as values or as types
  - RS-FP-57 [S] Keep the happy path linear with combinators
  - RS-FP-58 [M] Know when to stop
  - RS-FP-59 [M!] Use an explicit worklist where recursion depth is unbounded
  - RS-FP-60 [S] Prefer composition to inheritance-shaped hierarchies
  - RS-FP-61 [S] Expose a custom sequence by implementing `Iterator`
  - RS-FP-62 [S] Treat a hard-to-write pipeline as information about the data model

- **Closure and uniformity**
  - RS-FP-63 [M] Prefer operations closed under their own type
  - RS-FP-64 [S] Keep the stages of a pipeline uniform in shape

---

## Expression orientation

### RS-FP-01 [M] Make everything that can be an expression one

`if`, `match`, `loop`, and blocks all produce values.

**Why:** a declared-then-assigned binding is a mutable slot the compiler must track and the reader
must scan forward to resolve — and it permits the bug where one branch forgets to assign. The
expression form makes that unrepresentable and lets the binding be immutable.

**Check:** grep for `let x;` followed by assignment, and for `let mut x = <default>;` immediately
followed by a conditional that overwrites it.

```rust
// fragment — BAD
let label;
if n == 1 { label = "file"; } else { label = "files"; }
```

```rust
// fragment — GOOD
let label = if n == 1 { "file" } else { "files" };
```

### RS-FP-02 [S] Omit the trailing `return`

**Why:** a function's value is its final expression, so a trailing `return` is a keyword that adds
no information. Reserving `return` for genuine early exits makes it a signal — when you see it, you
know control is leaving before the end.

**Check:** grep for `return` on the last statement of a function body. Also
`clippy::needless_return` catches it.

### RS-FP-03 [M] Prefer `match` to an `if`/`else if` chain on one value

**Why:** `match` gives exhaustiveness checking, so adding an enum variant produces a compile error
instead of silently falling through to the `else`. It also reads as a table rather than as a
sequence of tests, which is what it actually is.

**Check:** grep for two or more `else if` arms testing the same subject. If the subject is an enum,
this is a missing exhaustiveness check, not a style preference.

### RS-FP-04 [S] A `for` loop that only pushes is a `collect`

**Why:** it is the single most common non-idiomatic shape in generated Rust. The loop form declares
a mutable binding, decides capacity implicitly, and separates the transformation from its result by
three lines; the pipeline form is one expression, sized from the iterator's `size_hint`, and reads
in the order the data flows.

**Check:** grep for `Vec::new()` or `vec![]` immediately followed by a `for` whose body is a single
`push`.

```rust
// fragment — BAD
let mut ids = Vec::new();
for user in users {
    if user.active {
        ids.push(user.id);
    }
}
```

```rust
// fragment — GOOD
let ids: Vec<_> = users.iter().filter(|u| u.active).map(|u| u.id).collect();
```

### RS-FP-05 [S] A `for` loop that only accumulates a scalar is a fold

`sum`, `product`, `count`, `max_by_key`, `min_by_key`, `fold`, `try_fold`.

**Why:** the named adapter states the intent that `fold(0, |a, b| a + b)` only implies, and it
cannot get the identity element wrong. It also removes the mutable accumulator, which is the thing a
reader has to track across the loop body.

**Check:** grep for `let mut` bound to a number or a `bool` directly above a `for`. Prefer the most
specific name available — `sum()` over `fold`, `any()` over a `bool` accumulator.

### RS-FP-06 [S] A `for` loop that searches and breaks is `find`, `any`, or `position`

**Why:** these short-circuit exactly like the loop, and they cannot forget the `break` or leave the
sentinel value set from a previous iteration. `any`/`all` additionally return the answer directly
rather than through a mutable flag.

**Check:** grep for `break` inside a `for` whose body assigns to a binding declared above it.

### RS-FP-07 [M] Keep `for` for the three things it is actually better at

Side effects over a sequence (writing to a sink, spawning tasks); bodies that need `?` across
several error types; and bodies with labelled control flow (`continue 'outer`).

**Why:** `for` supports `?`, `break`, `continue`, and labels; `for_each` supports none of them.
Converting an effectful loop to `for_each` costs error propagation and gains nothing, which is the
mirror image of RS-FP-04 and just as much a defect.

**Check:** does the loop body contain `?`, `break`, `continue`, or a label? Then it stays a `for`.
Does it produce a value and nothing else? Then it is a pipeline.

### RS-FP-08 [S] Use `let ... else` for destructure-or-bail

**Why:** it keeps the happy path unindented and puts the failure next to the condition. The
alternatives — a `match` with a `_ => return` arm, or an `if let` wrapping the rest of the function
— push the main line one level deeper for no benefit (`references/errors.md` RS-ERR-34).

**Check:** grep for `if let Some(x) = …` whose block runs to the end of the function.

### RS-FP-09 [S] Use `matches!` for boolean tests on shape

`matches!(tok, Token::Ident(_) | Token::Keyword(_))`.

**Why:** it is one expression, it composes inside `filter` and `retain`, and it is clearer than an
`if let` whose arms return `true` and `false`. It also accepts a guard, which covers most of the
cases where people reach for a full `match`.

**Check:** grep for `match` or `if let` whose only outputs are `true` and `false`.

### RS-FP-10 [S] Flatten nested `if let` with let-chains

`if let Some(x) = a && x > 3` — stable since 1.88, edition 2024 only.

**Why:** the pyramid of nested `if let` blocks is the most common source of four-level indentation
in Rust, and every level of it is a `}` the reader has to match up at the bottom.

**Check:** grep for an `if let` whose body is a single `if` or `if let`. Split the chain again when
the condition stops fitting on two lines — a five-clause chain is its own readability problem.

## Iterators and pipelines

### RS-FP-11 [S] Reach for the most specific adapter that says the intent

`filter_map` over `filter().map()` when the predicate and the transform are the same computation;
`flat_map` over `map().flatten()`; `zip` over indexing two slices; `windows`/`chunks` over manual
index arithmetic.

**Why:** the specific adapter names the operation, so the reader recognizes the pattern instead of
reconstructing it. It also usually avoids computing something twice — `filter(|x| parse(x).is_ok())
.map(|x| parse(x).unwrap())` parses everything twice and `unwrap`s.

**Check:** does any `filter` predicate perform work the following `map` repeats? That is a
`filter_map`.

```rust
// verified
/// `any`/`all` say what is being asked; a loop with a flag does not.
#[must_use]
pub fn all_ascii(values: &[String]) -> bool {
    values.iter().all(|value| value.is_ascii())
}
```

### RS-FP-12 [M] Never index a slice inside a loop over its own indices

**Why:** `for i in 0..v.len() { v[i] }` re-checks bounds on every access, breaks the moment the
collection type changes to something without `Index`, and reads worse than the alternative. The
iterator form has no bounds check at all (`references/performance.md` RS-PRF-23).

**Check:** grep `for .* in 0\.\.` followed by an index of the same collection.
`clippy::needless_range_loop` catches the common shape.

```rust
// verified
/// Iterating carries the proof that each element exists, so no bounds check remains.
#[must_use]
pub fn checksum(bytes: &[u8]) -> u32 {
    bytes
        .iter()
        .fold(0_u32, |acc, &byte| acc.rotate_left(5) ^ u32::from(byte))
}
```

### RS-FP-13 [M] Choose `iter`, `iter_mut`, or `into_iter` deliberately

Borrow when reading, borrow mutably when updating in place, consume when the source is finished.

**Why:** `into_iter()` on a `Vec` you still need is a move you then have to undo with a clone.
Conversely, `iter().cloned()` on a collection you were about to drop allocates a copy of everything
for no reason.

**Check:** for each `into_iter`, is the source used afterwards? For each `iter().cloned()`, is the
source used afterwards?

```rust
// verified
/// `IntoIterator` on the reference form, so `for tag in &tags` works.
#[derive(Debug, Default)]
pub struct Tags {
    inner: Vec<String>,
}

impl Tags {
    /// The inherent form, which callers reach for first.
    pub fn iter(&self) -> std::slice::Iter<'_, String> {
        self.inner.iter()
    }
}

impl<'tags> IntoIterator for &'tags Tags {
    type Item = &'tags String;
    type IntoIter = std::slice::Iter<'tags, String>;

    fn into_iter(self) -> Self::IntoIter {
        self.inner.iter()
    }
}
```

### RS-FP-14 [M] Chain adapters; do not collect in the middle

**Why:** every intermediate `.collect::<Vec<_>>()` is an allocation and a full materialization that
laziness would have avoided, plus a second pass over the data. It is also a place the reader has to
stop and hold a value.

**Check:** grep for `collect` followed within a few lines by `.iter()` on the result. That pair is
one pipeline split in half.

```rust
// fragment — BAD: two allocations, two passes
let words: Vec<&str> = line.split_whitespace().collect();
let lengths: Vec<usize> = words.iter().map(|w| w.len()).collect();
```

```rust
// fragment — GOOD: one allocation, one pass
let lengths: Vec<usize> = line.split_whitespace().map(str::len).collect();
```

### RS-FP-15 [S] Prefer the named aggregate to a hand-rolled fold

`sum`, `min`, `max`, `count`, `last`, `nth`, and `min_by_key`/`max_by_key` over
`min_by`/`max_by` when the comparison is a projection.

**Why:** `max_by_key(|e| e.size)` states what it optimizes; `max_by(|a, b| a.size.cmp(&b.size))`
makes the reader derive it, and gets the argument order wrong about a third of the time.

**Check:** does any `fold` reproduce something in the `Iterator` trait? Does any `_by` comparator
just compare one projected field?

### RS-FP-16 [S] Reserve `fold` for accumulation that no `collect` expresses

**Why:** when the accumulator is a collection, `collect` with the right `FromIterator` is both
shorter and better optimized — including into `String`, `HashMap`, `BTreeMap`,
`Result<Vec<_>, _>`, and `(Vec<_>, Vec<_>)`. A `fold` that pushes into a `Vec` is `collect` written
the long way.

**Check:** does the fold's accumulator end up being a collection? Try `collect` first.

### RS-FP-17 [M] Short-circuit fallible iteration with `try_fold` / `try_for_each`

**Why:** they stop at the first error and compose with `?`, replacing a `for` loop with a mutable
`result: Result<(), E>` that gets overwritten — a pattern that silently keeps only the *last* error
and does the remaining work anyway.

**Check:** grep for a mutable `Result` or `Option` binding assigned inside a loop.

```rust
// fragment — BAD: keeps only the last error, and does all the work
let mut result = Ok(());
for item in items { if let Err(e) = write(item) { result = Err(e); } }
result?;
```

```rust
// fragment — GOOD
items.iter().try_for_each(write)?;
```

### RS-FP-18 [S] Use `scan` only when the state belongs to the pipeline

**Why:** `scan` expresses a running state that also yields; `fold` expresses one that does not. If
you find yourself using `scan` while mutating a variable captured from outside the closure, the
state does not belong to the pipeline and the whole thing wants to be a loop or a `fold`.

**Check:** does the `scan` closure touch anything other than its state parameter and its item?

```rust
// verified
/// `scan` carries state through a pipeline without a mutable binding outside it.
#[must_use]
pub fn running_total(values: &[u32]) -> Vec<u32> {
    values
        .iter()
        .scan(0_u32, |total, &value| {
            *total = total.saturating_add(value);
            Some(*total)
        })
        .collect()
}
```

### RS-FP-19 [S] Use `peekable` and `by_ref` instead of a manual buffer

**Why:** `peekable` gives one-token lookahead with the buffering handled and the borrow rules
enforced; a hand-rolled `Option<T>` buffer has to be drained correctly at three call sites and
usually is not. `by_ref` lets you consume a prefix (with `take`, `take_while`, or a `for`) without
losing the rest — which is otherwise the reason people reach for indices.

**Check:** grep for `Option<Item>` fields or locals named `next`, `pending`, `lookahead`, or
`buffered`.

### RS-FP-20 [S] Prefer the one-word adapter to the equivalent closure

`copied()` over `map(|&x| x)`, `cloned()` over `map(|x| x.clone())`, `flatten()` over
`filter_map(|x| x)`.

**Why:** the named form says what happens without the reader parsing a pattern, and `clippy` has a
lint for each because they are recognizable enough to be mechanical.

**Check:** `clippy::map_clone`, `clippy::filter_map_identity`, `clippy::flat_map_identity`.

```rust
// verified
/// `position` says what is wanted; an indexed loop says how to find it.
#[must_use]
pub fn first_blank(lines: &[String]) -> Option<usize> {
    lines.iter().position(|line| line.trim().is_empty())
}
```

### RS-FP-21 [M] Keep iterators lazy as far up the stack as you can

Take `impl IntoIterator<Item = T>`, return `impl Iterator<Item = T>`.

**Why:** materialization is a decision that belongs to whoever knows how much of the sequence is
needed — and that is the caller, not you. A function that returns `Vec<T>` has decided on the
caller's behalf that all of it will be computed and all of it will be stored
(`references/api-design.md` RS-API-15).

**Check:** does the function return a collection the caller might only partially consume, or might
immediately feed into another adapter?

### RS-FP-22 [S] Pre-size when `size_hint` cannot

`Vec::with_capacity(n)` plus `extend` when the count is known independently of the iterator.

**Why:** `collect` pre-sizes from `size_hint`, which is exact for slices, ranges, and `map` over
them — and useless after `filter`, `flat_map`, or `chars`. In those cases the `Vec` grows by
repeated doubling, copying everything so far each time
(`references/performance.md` RS-PRF-06).

**Check:** is there a `filter` or `flat_map` in the chain, and do you know the output size from
somewhere else?

```rust
// verified
/// The count is known independently, so size the collection once.
#[must_use]
pub fn render(ids: &[u32]) -> Vec<String> {
    let mut out = Vec::with_capacity(ids.len());
    out.extend(ids.iter().map(u32::to_string));
    out
}
```

### RS-FP-23 [S] Collect directly into the collection the caller needs

`collect::<HashMap<_, _>>()`, `collect::<BTreeSet<_>>()`, `collect::<String>()`,
`collect::<Result<Vec<_>, _>>()`.

**Why:** collecting into a `Vec` and converting afterwards allocates twice and iterates twice, and
`FromIterator` impls exist for exactly this reason. `Result<Vec<_>, _>` in particular is not a
special case — it is the same mechanism (`references/errors.md` RS-ERR-30).

**Check:** grep for `collect` followed by `into_iter().collect()`, `HashMap::from_iter`, or a
`for` loop that inserts.

### RS-FP-24 [S] Do not build a collection to measure it

**Why:** calling `.len()` on a freshly built `Vec` just to size the next one means two passes and an
allocation you did not need. Either `count()` the iterator (which consumes it, so clone the source
or restructure), or produce both outputs in one pass.

**Check:** grep for `.len()` on a binding created by the immediately preceding `collect`.

### RS-FP-25 [S] Replace index arithmetic with the adapters that encode it

`rev`, `skip`, `take`, `step_by`, `chain`, `cycle`, `zip`.

**Why:** each of these is a place an off-by-one lives. `zip` in particular stops at the shorter
side, which removes the `min(a.len(), b.len())` that people write and occasionally get wrong.

**Check:** grep for `len() - 1`, `..len()`, and `min(.*len` near a loop.

```rust
// verified
/// `zip` pairs two sequences without indexing either.
#[must_use]
pub fn dot(left: &[i64], right: &[i64]) -> i64 {
    left.iter().zip(right).map(|(a, b)| a * b).sum()
}
```

### RS-FP-26 [S] Justify `itertools` by naming the adapters you use

**Why:** it is worth the dependency for `chunk_by`, `dedup_by`, `tuple_windows`, `sorted_by`,
`partition_map`, and `izip!` — all genuinely absent from `std` and genuinely fiddly to hand-roll. It
is not worth it for something `std` already has, and "we already depend on it" is not a
justification for the next crate (`references/cargo-toolchain.md` RS-CAR-21).

**Check:** grep the crate for `itertools::` and list the distinct adapters. If the list is one entry
and `std` has an equivalent, drop the dependency.

### RS-FP-27 [S] Break a pipeline the reader cannot hold

Roughly five adapters, or two screen lines.

**Why:** the limit is working memory, not aesthetics. Past about five transformations the reader is
tracking a type they cannot see, and the named intermediate binding — whose name states what the
pipeline has produced so far — restores it for the cost of one line.

**Check:** can you name the value at the midpoint of the chain? If yes and the chain is long, that
name should exist in the code.

```rust
// verified
/// A named intermediate is clearer than a fourth chained adapter.
#[must_use]
pub fn report(lines: &[String]) -> String {
    let interesting: Vec<&str> = lines
        .iter()
        .map(String::as_str)
        .filter(|line| line.starts_with("ERROR"))
        .collect();
    interesting.join("\n")
}
```

### RS-FP-28 [S] Keep the pipeline shape that `rayon` can parallelize

**Why:** `iter()` → `par_iter()` is a one-word change on a functional pipeline and a redesign on
loop-and-mutate code. That is a concrete argument for the pipeline form even when today's data is
small, because the day the data grows you want the change to be one word
(`references/concurrency-async.md` RS-CNC-41).

**Check:** would `par_iter()` compile here? If not, what state is shared — and does it need to be?

```rust
// verified
/// A pure pipeline: no captured state, so `iter` could become `par_iter` unchanged.
#[must_use]
pub fn total_weight(samples: &[u32]) -> u64 {
    samples.iter().map(|&sample| u64::from(sample)).sum()
}
```

## Immutability and bindings

### RS-FP-29 [S] Treat every `let mut` as a proof obligation

State, at least to yourself, why no fold, `collect`, `scan`, or shadowing expresses this.

**Why:** each mutable binding is a value the reader must track across every line in scope, and a
place two code paths can disagree. The obligation is cheap — most `mut`s dissolve in about ten
seconds of thought — and the ones that survive it are the ones that were genuinely necessary.

**Check:** count `let mut` per function. More than two in a body that is not a parser or a state
machine is worth a second look.

```rust
// verified
/// The whole body is one expression, so there is no intermediate state to track.
#[must_use]
pub fn initials(name: &str) -> String {
    name.split_whitespace()
        .filter_map(|word| word.chars().next())
        .collect()
}
```

### RS-FP-30 [S] Prefer shadowing to mutation for stepwise refinement

**Why:** shadowing keeps each intermediate immutable and lets the *type* change along the way, which
mutation cannot do. It also makes the sequence of transformations visible as a sequence, rather than
as repeated assignment to one name.

**Check:** does the mutable binding hold the same type throughout, and get overwritten rather than
updated? That is shadowing.

```rust
// verified
use std::num::ParseIntError;

/// Shadowing narrows the value one step at a time and leaves no stale binding behind.
///
/// # Errors
/// Returns [`ParseIntError`] when the trimmed input is not a number.
pub fn parse_port(input: &str) -> Result<u16, ParseIntError> {
    let input = input.trim();
    let input: u16 = input.parse()?;
    Ok(input)
}
```

### RS-FP-31 [M] Do not shadow across a large scope or with a new meaning

**Why:** shadowing is a refinement tool, not a name-recycling tool. Two different concepts sharing a
name three screens apart means a reader who scrolls up finds the wrong definition — which is
strictly worse than a second name, because it looks correct.

**Check:** does each shadow refine the same concept, and does it occur within a few lines of the
binding it shadows?

### RS-FP-32 [M] Declare a binding where it is initialized

**Why:** `let x;` with the assignment ten lines later is a mutable slot in disguise. It also defeats
the compiler's move analysis, so a value that could have been moved gets cloned or borrowed
unnecessarily (RS-FP-01).

**Check:** grep for `let \w+;` with no initializer.

```rust
// verified
/// `match` is an expression, so the binding is initialized exactly once.
#[must_use]
pub fn tier(score: u32) -> &'static str {
    match score {
        0..=9 => "low",
        10..=99 => "medium",
        _ => "high",
    }
}
```

### RS-FP-33 [S] Push constants into `const` and `const fn`

**Why:** a `const` is computed at compile time, has no address, and cannot be accidentally mutated
or shadowed by a local. Derived constants computed with `const fn` cost nothing at runtime and keep
the derivation next to the values it depends on, instead of in a comment.

**Check:** grep for `static` bindings that are never mutated and hold no interior mutability — most
are `const`. Grep for magic numbers computed from other constants at runtime.

```rust
// verified
/// A `const fn` computed at compile time, with no runtime cost at all.
#[must_use]
pub const fn kib(count: u64) -> u64 {
    count * 1024
}

pub const BUFFER: u64 = kib(64);
```

### RS-FP-34 [S] Use the in-place operations that have functional signatures

`retain`, `sort_unstable_by_key`, `dedup`, `truncate`, `fill`.

**Why:** in-place mutation is the right answer for large data — it avoids the copy — but it does not
have to mean manual index shuffling. These methods take a predicate or a key function and do the
shuffling correctly, which hand-written versions frequently do not.

**Check:** grep for loops that `remove(i)` inside iteration, or that build a second `Vec` in order
to delete from the first. Both are `retain`.

### RS-FP-35 [M] Never mutate a captured variable from inside `map`

**Why:** `map` with a side effect is `for_each` lying about its purpose. It also breaks the moment
someone adds `.rev()`, `.par_iter()`, or a `take` that short-circuits — because `map` promises
nothing about order or about being run at all.

**Check:** does any `map` closure assign to something declared outside it, or call a method taking
`&mut` on a captured value?

### RS-FP-36 [S] Use `inspect` for legitimate mid-pipeline observation

**Why:** logging, counting, and tracing mid-pipeline are real needs, and `inspect` is the adapter
that does them without pretending to transform. Using `map` for it is the violation in RS-FP-35;
using `inspect` is the sanctioned form.

**Check:** does any `map` closure return its input unchanged?

```rust
// verified
/// `inspect` observes without changing the value or the type.
#[must_use]
pub fn sum_reported(values: &[u32]) -> u32 {
    values
        .iter()
        .inspect(|value| {
            if **value == 0 {
                eprintln!("zero encountered");
            }
        })
        .sum()
}
```

### RS-FP-37 [S] Return finished data as `Box<[T]>` or `Arc<[T]>`

**Why:** `Vec<T>` carries a capacity field that is meaningless once growth is over, and it invites a
caller to push into a collection whose contents you consider final. `Box<[T]>` says "this is the
whole answer" in the type (`references/ownership.md` RS-OWN-20).

**Check:** does the returned `Vec` ever grow after it leaves? If not, `into_boxed_slice()` is one
call.

### RS-FP-38 [M] Justify each use of interior mutability in a comment

`Cell`, `RefCell`, `Mutex`, `OnceLock`.

**Why:** interior mutability moves a check the compiler was doing to runtime — or to nowhere. It is
sometimes the right answer, but it is never the *obvious* answer, and the comment is what
distinguishes a decision from a workaround. Frequently the honest note is "this can be threaded
through `&mut self`, but the refactor is large" — write that down
(`references/ownership.md` RS-OWN-30).

**Check:** does every `RefCell`/`Cell`/`Mutex` field have a comment on the field declaration?

### RS-FP-39 [S] Reserve `mem::take` / `mem::replace` for state machines

**Why:** they are exactly right for moving out of `&mut self` during a state transition, and a
smell everywhere else — where they usually mean the function should have taken `self` by value, or
the field should have been an `Option` the caller manages.

**Check:** for each `mem::take`, is the enclosing type a state machine? If not, what would taking
`self` by value cost?

### RS-FP-40 [S] Give a build-once type no `&mut self` methods at all

**Why:** if a type is constructed and then only read, expressing that in the API means the compiler
enforces the immutability you intended, and callers can share it behind `&` or `Arc` without a lock.
A single `&mut self` method removes that guarantee for every user.

**Check:** list the `&mut self` methods. Are any of them called after construction finishes? If not,
fold them into the builder.

## Closures and functions as values

### RS-FP-41 [S] Pass function paths, not forwarding closures

`map(str::len)`, `filter(char::is_alphanumeric)`, `map(Some)`, `and_then(Result::ok)`.

**Why:** a closure that only forwards its argument is four characters of syntax around a name, and
it makes the reader check whether it does anything else. The path form cannot.

**Check:** grep for closures of the shape `|x| f(x)`. `clippy::redundant_closure` catches most.

```rust
// verified
/// `unzip` splits one pass into two collections without a second traversal.
#[must_use]
pub fn split(pairs: &[(u32, String)]) -> (Vec<u32>, Vec<String>) {
    pairs.iter().cloned().unzip()
}
```

### RS-FP-42 [M] Choose the loosest closure bound the callee needs

`FnOnce` if it is called once, `FnMut` if repeatedly with state, `Fn` only when it must be callable
from a shared reference or in parallel.

**Why:** the bound is a requirement on every caller. Demanding `Fn` when `FnOnce` suffices rejects
closures that consume their captures — which is most of the interesting ones — and the caller's only
workaround is to clone.

**Check:** for each `F: Fn`, is the closure ever called more than once, or from behind `&self`? If
not, loosen it.

### RS-FP-43 [S] Take closures generically when hot, boxed when stored

`f: impl Fn(&T) -> U` for small, frequently called callbacks; `Box<dyn Fn(&T) -> U>` when it must
live in a struct field or when monomorphization bloat is measurable.

**Why:** the generic form inlines and costs a monomorphization per call site; the boxed form costs
an indirect call and an allocation but keeps the code size flat and the type nameable
(`references/traits-generics.md` RS-TRG-16).

**Check:** does the closure get stored, or does the function get instantiated for many types? Either
answer points at boxing.

### RS-FP-44 [S] Capture as little as possible

**Why:** a closure that captures `self` borrows all of `self`, which blocks every other borrow for
as long as the closure lives — the most common cause of "cannot borrow `self` as mutable more than
once". Binding the specific fields first gives the compiler disjoint borrows
(`references/ownership.md` RS-OWN-10).

**Check:** does the closure mention `self.` at all? Hoist those fields to locals before it.

```rust
// fragment — BAD: borrows all of self
self.items.retain(|item| self.filter.matches(item));
```

```rust
// fragment — GOOD: two disjoint borrows
let filter = &self.filter;
self.items.retain(|item| filter.matches(item));
```

### RS-FP-45 [M] Understand that `move` moves everything captured

**Why:** `move` is not selective. To move one field into a closure and borrow another, bind them
outside first — this is the standard fix for "cannot move out of `self`", and reaching for `clone()`
instead is exactly the defect in `references/ownership.md` RS-OWN-12.

**Check:** for each `move` closure, list what it captures. Is anything captured by move that the
surrounding scope still needs?

### RS-FP-46 [S] Return `impl Fn` rather than `Box<dyn Fn>` from factories

**Why:** it is allocation-free and monomorphizes at the call site, and the caller can still box it
if they need to. Returning `Box<dyn Fn>` makes that decision for everyone.

**Check:** does the factory's return value get stored heterogeneously? If not, `impl Fn` is the
better default.

```rust
// verified
/// Returning the closure keeps the configuration captured and the call site clean.
pub fn longer_than(limit: usize) -> impl Fn(&str) -> bool {
    move |value| value.len() > limit
}
```

### RS-FP-47 [S] Name a closure that outgrows a few lines

**Why:** a five-line closure has a purpose, and the purpose deserves a name — for the reader, and
for the profiler, where an anonymous closure shows up as a mangled symbol nobody can attribute.

**Check:** any closure spanning more than about five lines, or containing its own control flow.

### RS-FP-48 [S] Take a policy function instead of a row of booleans

`policy: impl Fn(&Entry) -> bool` beats six `bool` parameters.

**Why:** it is more flexible, it composes, and it does not grow a seventh parameter next quarter.
The boolean row is also the defect in `references/api-design.md` RS-API-30 seen from the other side.

**Check:** does the function take three or more `bool`s that are all consulted in the same place?

### RS-FP-49 [M] Clone explicitly before a closure that is spawned

**Why:** relying on `move` to capture the right thing from a loop is where the shared-instead-of-
cloned bug lives, and it produces either a borrow error you "fix" with an `Arc` you did not need, or
a subtle sharing of state you did not intend
(`references/concurrency-async.md` RS-CNC-13).

**Check:** for each `spawn`, are the clones visible on their own lines above the closure?

```rust
// verified
/// Clone before the closure so the capture is explicit and the loop variable is not shared.
#[must_use]
pub fn prefixed(prefix: &str, items: &[String]) -> Vec<String> {
    items
        .iter()
        .map(|item| {
            let mut line = String::with_capacity(prefix.len() + item.len());
            line.push_str(prefix);
            line.push_str(item);
            line
        })
        .collect()
}
```

### RS-FP-50 [S] Use `fn` pointers for tables of handlers

**Why:** `fn(&str) -> bool` is `Copy`, `'static`, and comparable, so a table of them can be a
`const` array — which is exactly how ripgrep's flag table dispatches. A `Box<dyn Fn>` in the same
position costs an allocation each and cannot be `const`.

**Check:** do the handlers capture anything? If not, they are `fn` pointers.

## Purity, effects, composition

### RS-FP-51 [M] Separate computing from doing

**Why:** a function that both derives a value and writes it somewhere cannot be tested without a
sink, cannot be reused with a different sink, and cannot be parallelized. Returning the value costs
nothing and removes all three limits at once.

**Check:** does the function both compute and print, log, write, or send? Split it and let the
caller connect the two halves.

### RS-FP-52 [S] Push effects to the edges

Parse and read at the entry, compute over plain data in the middle, write and log at the exit.

**Why:** the middle layer then needs no I/O, no clock, and no environment to test — which is the
difference between a suite that runs in milliseconds and one that needs fixtures. It is also the
architecture that makes `run() -> Result<()>` testable (`references/cli-apps.md` RS-CLI-01).

**Check:** how deep in the call stack is the deepest I/O call? Everything below the entry layer
should be pure.

### RS-FP-53 [M] Parse, don't validate

Convert untrusted input into a type that cannot be invalid, at the boundary, and let every
downstream function take the parsed type.

**Why:** `validate(&str) -> Result<(), Error>` followed by code that still handles `&str` will drift
out of sync — someone will call the second without the first, and nothing will catch it. Parsing
into a type makes the check unskippable, because the type cannot be constructed without it
(`references/api-design.md` RS-API-34).

**Check:** grep for functions named `validate_*` or `check_*` returning `Result<(), _>`. Each is a
parse waiting to be written.

```rust
// verified
use std::num::NonZeroU16;
use std::str::FromStr;

/// Parse, do not validate: an invalid port cannot be represented.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Port(NonZeroU16);

/// The input was empty, out of range, or zero.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct InvalidPort;

impl FromStr for Port {
    type Err = InvalidPort;

    fn from_str(input: &str) -> Result<Self, Self::Err> {
        input
            .parse::<NonZeroU16>()
            .map(Port)
            .map_err(|_| InvalidPort)
    }
}
```

### RS-FP-54 [S] Make functions total where you can

**Why:** a signature that cannot fail is easier to call, easier to compose, and easier to test than
one returning `Result` because a caller *might* pass nonsense. Making the nonsense unconstructible
moves the check to one place instead of every entry point (RS-FP-53).

**Check:** for each `Result`-returning function, is the error reachable given properly typed inputs?
If not, the types should absorb it.

### RS-FP-55 [S] Take the clock, the RNG, and the filesystem as parameters

`fn expire(now: Instant, …)` rather than `Instant::now()` inside.

**Why:** the parameterized version is trivially testable with a fixed value and trivially
deterministic; the internal version needs either a fake clock crate or a `sleep` in the test. The
same argument applies to randomness and to the current directory.

**Check:** grep for `Instant::now`, `SystemTime::now`, `rand::random`, `env::var`, and
`env::current_dir` below the entry layer.

### RS-FP-56 [S] Model state transitions as values or as types

Return the new state, or use typestate so the compiler enforces the order.

**Why:** an object that is "not yet initialized" for its first three method calls is two types
wearing one name, and every method has to handle a state it should never see
(`references/traits-generics.md` RS-TRG-51).

**Check:** does any method start by checking a state flag and returning an error if it is wrong?
That check is a type the design has not made yet.

### RS-FP-57 [S] Keep the happy path linear with combinators

`opt.map(f).filter(p).unwrap_or_default()`, `res.and_then(g).or_else(h)`.

**Why:** the linear form reads top to bottom in the order the data flows, without the reader
tracking which branch they are in. Choose the eager or lazy variant deliberately
(`references/errors.md` RS-ERR-29).

**Check:** does any nested `match` on `Option`/`Result` have arms that just forward?

```rust
// verified
/// `map_or` replaces a `match` whose arms are one expression each.
#[must_use]
pub fn width_or_default(value: Option<u32>) -> u32 {
    value.map_or(80, |width| width.max(1))
}
```

### RS-FP-58 [M] Know when to stop

**Why:** readability is the objective; functional style is the usual means, not the end. A chain
that requires the reader to track three type transformations is worse than the `match` it replaced,
and "but it is more functional" is not a defence. This rule outranks every `[S]` in this chapter.

**Check:** read the expression aloud. If you cannot say what it produces without re-reading, split
it (RS-FP-27) or write the `match`.

### RS-FP-59 [M!] Use an explicit worklist where recursion depth is unbounded

**Why:** Rust has no guaranteed tail-call elimination, so recursion over attacker-controlled depth
is a stack overflow — which aborts immediately and cannot be caught. A `Vec` used as a worklist is
still functional in spirit, is bounded by the heap, and can be depth-limited with one comparison.
*Relaxed form:* recursion is fine for tree-shaped data whose depth is bounded by a constant you
assert at entry — an expression AST from your own builder, a directory walk with a depth cap.

**Check:** for each recursive function, what bounds the depth? If the answer is "the input", it
needs a worklist or an asserted cap.

### RS-FP-60 [S] Prefer composition to inheritance-shaped hierarchies

**Why:** a struct holding a `Matcher` and a `Printer` is easier to reason about, test, and change
than a five-level supertrait chain, and Rust does not model "is a" anyway
(`references/traits-generics.md` RS-TRG-08).

**Check:** count the supertraits in the deepest chain. More than one level is usually reuse
pretending to be a prerequisite.

### RS-FP-61 [S] Expose a custom sequence by implementing `Iterator`

**Why:** a newtype with an `Iterator` impl keeps laziness at the boundary and gives users the whole
adapter library for free. Returning a `Vec` from a method named like a query decides materialization
for them (RS-FP-21).

**Check:** does any method named as a query (`entries`, `matches`, `children`) return a collection?

### RS-FP-62 [S] Treat a hard-to-write pipeline as information about the data model

**Why:** when a pipeline resists being written functionally, the usual cause is not that the problem
is imperative — it is that the data has the wrong shape. Flags that should be an enum, a nested loop
that should be a group-by, a pair of parallel `Vec`s that should be one `Vec` of structs. The
functional form falls out once the shape is right.

**Check:** before adding a `mut`, spend one minute on the question: what shape would make this a
`map`? If an answer exists, it is usually also the better data model.

## Closure and uniformity

### RS-FP-63 [M] Prefer operations closed under their own type

An operation on `T` that returns `T` composes with itself; one that returns a near-miss —
`Result<U, _>` where `T` would do, or a tuple that must be unpacked and rebuilt — does not.

**Why:** closure is what makes a chain possible at all. Each escape from the type forces the caller
to unpack, adapt, and repack, and that adapter code is the patch code this standard exists to
remove. Designing the operation to land back in `T` moves the conversion into the operation, where
it is written once.

**Check:** for each transformation in a pipeline, compare its input and output types. Every mismatch
that is not carrying real information is an adapter waiting to be deleted.

```rust
// verified
/// Closed under its own type, so the operations compose without adapters.
#[derive(Debug, Clone, Copy, Default, PartialEq, Eq)]
pub struct Span {
    start: usize,
    end: usize,
}

impl Span {
    #[must_use]
    pub fn join(self, other: Self) -> Self {
        Self {
            start: self.start.min(other.start),
            end: self.end.max(other.end),
        }
    }

    #[must_use]
    pub fn union_all(spans: &[Self]) -> Self {
        spans.iter().copied().fold(Self::default(), Self::join)
    }
}
```

### RS-FP-64 [S] Keep the stages of a pipeline uniform in shape

Stages take one value and return one value. Resist a stage that also mutates a captured
accumulator, one that returns a tuple only the next stage understands, or one that is a `for` loop
because it was easier.

**Why:** uniform stages can be reordered, tested individually, and parallelized (`RS-CNC-41`); a
stage with a side channel can do none of the three, and it removes those properties from the whole
chain rather than from itself. The irregular stage is also where the bugs are, because it is the one
nobody can reason about locally.

**Check:** read the pipeline and name each stage's input and output. A stage that needs a sentence
containing "and also" is the one to fix.

```rust
// verified
/// Every stage takes one value and returns one value, so the chain can be reordered or split.
#[must_use]
pub fn normalize(lines: &[String]) -> Vec<String> {
    lines
        .iter()
        .map(|line| line.trim())
        .filter(|line| !line.is_empty())
        .map(str::to_lowercase)
        .collect()
}
```
