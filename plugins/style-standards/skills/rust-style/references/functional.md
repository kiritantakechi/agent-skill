# Functional: Expressions, Iterators, Immutability, and Purity

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
  - RS-FUNC-01 [M] Make everything that can be an expression one
  - RS-FUNC-02 [M] Write a `match`, not an `if`/`else if` chain, on one value
  - RS-FUNC-03 [S] A `for` loop that only pushes is a `collect`
  - RS-FUNC-04 [S] A `for` loop that only accumulates a scalar is a fold
  - RS-FUNC-05 [S] A `for` loop that searches and breaks is `find`, `any`, or `position`
  - RS-FUNC-06 [M] Keep `for` for the three things it is actually better at
  - RS-FUNC-07 [S] Use `let ... else` for destructure-or-bail
  - RS-FUNC-08 [S] Flatten nested `if let` with let-chains

- **Iterators and pipelines**
  - RS-FUNC-09 [S] Reach for the most specific adapter that says the intent
  - RS-FUNC-10 [M] Choose `iter`, `iter_mut`, or `into_iter` deliberately
  - RS-FUNC-11 [M] Chain adapters; do not collect in the middle
  - RS-FUNC-12 [S] Reserve `fold` for accumulation that no `collect` expresses
  - RS-FUNC-13 [M] Stop fallible iteration at its first error
  - RS-FUNC-14 [S] Use `scan` only when the state belongs to the pipeline
  - RS-FUNC-15 [S] Use `peekable` and `by_ref` instead of a manual buffer
  - RS-FUNC-16 [M] Keep iterators lazy as far up the stack as you can
  - RS-FUNC-17 [S] Collect directly into the collection the caller needs
  - RS-FUNC-18 [S] Do not build a collection to measure it
  - RS-FUNC-19 [S] Replace index arithmetic with the adapters that encode it
  - RS-FUNC-20 [S] Justify `itertools` by naming the adapters you use
  - RS-FUNC-21 [S] Break a pipeline the reader cannot hold

- **Immutability and bindings**
  - RS-FUNC-22 [S] Treat every `let mut` as a proof obligation
  - RS-FUNC-23 [S] Prefer shadowing to mutation for stepwise refinement
  - RS-FUNC-24 [M] Do not shadow across a large scope or with a new meaning
  - RS-FUNC-25 [S] Push constants into `const` and `const fn`
  - RS-FUNC-26 [S] Use the in-place operations that have functional signatures
  - RS-FUNC-27 [M] Never mutate a captured variable from inside `map`
  - RS-FUNC-28 [S] Reserve `mem::take` / `mem::replace` for state machines
  - RS-FUNC-29 [S] Give a build-once type no `&mut self` methods at all

- **Closures and functions as values**
  - RS-FUNC-30 [M] Choose the loosest closure bound the callee needs
  - RS-FUNC-31 [S] Take closures generically when hot, boxed when stored
  - RS-FUNC-32 [S] Capture as little as possible
  - RS-FUNC-33 [M] Bind what a `move` closure should only borrow outside it
  - RS-FUNC-34 [S] Name a closure that outgrows a few lines
  - RS-FUNC-35 [S] Use `fn` pointers for tables of handlers

- **Purity, effects, composition**
  - RS-FUNC-36 [M] Separate computing from doing, and push the doing to the edges
  - RS-FUNC-37 [M] Parse, don't validate
  - RS-FUNC-38 [S] Make functions total where you can
  - RS-FUNC-39 [S] Take the clock, the RNG, and the filesystem as parameters
  - RS-FUNC-40 [S] Model state transitions as values or as types
  - RS-FUNC-41 [S] Keep the happy path linear with combinators
  - RS-FUNC-42 [M] Write the `match` once a chain no longer reads aloud
  - RS-FUNC-43 [M!] Use an explicit worklist where recursion depth is unbounded
  - RS-FUNC-44 [S] Expose a custom sequence by implementing `Iterator`
  - RS-FUNC-45 [S] Treat a hard-to-write pipeline as information about the data model

- **Closure and uniformity**
  - RS-FUNC-46 [M] Make an operation on `T` return `T` where nothing else is carried
  - RS-FUNC-47 [S] Keep the stages of a pipeline uniform in shape

- Decided by tools

---

## Expression orientation

### RS-FUNC-01 [M] Make everything that can be an expression one

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

### RS-FUNC-02 [M] Write a `match`, not an `if`/`else if` chain, on one value

**Why:** `match` gives exhaustiveness checking, so adding an enum variant produces a compile error
instead of silently falling through to the `else`. It also reads as a table rather than as a
sequence of tests, which is what it actually is.

**Check:** grep for two or more `else if` arms testing the same subject. If the subject is an enum,
this is a missing exhaustiveness check, not a style preference.

### RS-FUNC-03 [S] A `for` loop that only pushes is a `collect`

**Why:** the loop declares a mutable binding, decides capacity implicitly, and separates the
transformation from its result by three lines; the pipeline is one expression, sized from the
iterator's `size_hint`, and reads in the order the data flows.

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

### RS-FUNC-04 [S] A `for` loop that only accumulates a scalar is a fold

`sum`, `product`, `count`, `max_by_key`, `min_by_key`, `fold`, `try_fold`.

**Why:** the named adapter states the intent that `fold(0, |a, b| a + b)` only implies, and it
cannot get the identity element wrong. It also removes the mutable accumulator, which is the thing a
reader has to track across the loop body.

**Check:** grep for `let mut` bound to a number or a `bool` directly above a `for`. Prefer the most
specific name available — `sum()` over `fold`, `any()` over a `bool` accumulator, and
`max_by_key(|e| e.size)` over a `max_by` comparator that only compares one projected field.

### RS-FUNC-05 [S] A `for` loop that searches and breaks is `find`, `any`, or `position`

**Why:** these short-circuit exactly like the loop, and they cannot forget the `break` or leave the
sentinel value set from a previous iteration. `any`/`all` additionally return the answer directly
rather than through a mutable flag.

**Check:** grep for `break` inside a `for` whose body assigns to a binding declared above it.

### RS-FUNC-06 [M] Keep `for` for the three things it is actually better at

Side effects over a sequence (writing to a sink, spawning tasks); bodies that need `?` across
several error types; and bodies with labelled control flow (`continue 'outer`).

**Why:** `for` supports `?`, `break`, `continue`, and labels; `for_each` supports none of them.
Converting an effectful loop to `for_each` costs error propagation and gains nothing, which is the
mirror image of RS-FUNC-03 and just as much a defect.

**Check:** does the loop body contain `?`, `break`, `continue`, or a label? Then it stays a `for`.
Does it produce a value and nothing else? Then it is a pipeline.

### RS-FUNC-07 [S] Use `let ... else` for destructure-or-bail

**Why:** it keeps the happy path unindented and puts the failure next to the condition. The
alternatives — a `match` with a `_ => return` arm, or an `if let` wrapping the rest of the function
— push the main line one level deeper for no benefit.

**Check:** grep for `if let Some(x) = …` whose block runs to the end of the function.

### RS-FUNC-08 [S] Flatten nested `if let` with let-chains

`if let Some(x) = a && x > 3`, in edition 2024. A match arm takes an `if let` guard the same way:
`Some(text) if let Ok(n) = text.parse::<u32>() => n`.

**Why:** the pyramid of nested `if let` blocks is the most common source of four-level indentation
in Rust, and every level of it is a `}` the reader has to match up at the bottom.

**Check:** grep for an `if let` whose body is a single `if` or `if let`. Split the chain again when
the condition stops fitting on two lines — a five-clause chain is its own readability problem.

## Iterators and pipelines

### RS-FUNC-09 [S] Reach for the most specific adapter that says the intent

`filter_map` over `filter().map()` when the predicate and the transform are the same computation;
`flat_map` over `map().flatten()`; and the adapters RS-FUNC-19 lists over index arithmetic.

**Why:** the specific adapter names the operation, so the reader recognizes the pattern instead of
reconstructing it. It also usually avoids computing something twice —
`filter(|x| parse(x).is_ok()) .map(|x| parse(x).unwrap())` parses everything twice and `unwrap`s.

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

### RS-FUNC-10 [M] Choose `iter`, `iter_mut`, or `into_iter` deliberately

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

### RS-FUNC-11 [M] Chain adapters; do not collect in the middle

**Why:** every intermediate `.collect::<Vec<_>>()` is an allocation, a full materialization that
laziness would have avoided, a second pass, and the cache pressure of holding all of it. It is also
a place the reader has to stop and hold a value.

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

### RS-FUNC-12 [S] Reserve `fold` for accumulation that no `collect` expresses

**Why:** when the accumulator is a collection, `collect` with the right `FromIterator` is both
shorter and better optimized (RS-FUNC-17); `fold` is for an accumulator no collection is.

**Check:** does the fold's accumulator end up being a collection? Try `collect` first.

### RS-FUNC-13 [M] Stop fallible iteration at its first error

Where the first failure ends the work, collect into `Result<Vec<_>, _>` when the values are wanted,
`try_for_each` for an effect, and `try_fold` for an accumulation: each stops at the first error and
composes with `?`. A run that reports every failure instead is RS-ERR-34's.

**Why:** a `for` loop that carries a mutable `result: Result<(), E>` and overwrites it keeps only
the *last* error and does the remaining work anyway. The short-circuiting forms skip that work and
keep the pipeline an expression.

**Check:** is a `Result` or `Option` held in a `let mut` binding and assigned inside a loop? That is
the finding. A `for` loop over fallible items that pushes into a `Vec` and returns early is the
`collect`.

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

```rust
// verified
/// `collect` into `Result` short-circuits on the first failure.
///
/// # Errors
/// Returns the first parse error encountered.
pub fn parse_all(values: &[String]) -> Result<Vec<u32>, std::num::ParseIntError> {
    values.iter().map(|value| value.parse()).collect()
}
```

### RS-FUNC-14 [S] Use `scan` only when the state belongs to the pipeline

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

### RS-FUNC-15 [S] Use `peekable` and `by_ref` instead of a manual buffer

`peekable` for one-item lookahead, `by_ref` to consume a prefix and keep the rest, and `next_if` or
`next_if_map` to take the next item only when it matches, with no `peek` then `next`.

**Why:** `peekable` handles one-token lookahead; a hand-rolled `Option<T>` buffer has to be drained
correctly at three call sites and usually is not. `by_ref` consumes a prefix (`take`, `take_while`,
a `for`) without losing the rest, which is otherwise the reason people reach for indices.

**Check:** grep for `Option<Item>` fields or locals named `next`, `pending`, `lookahead`, or
`buffered`, and for a peek whose matching branch then advances the iterator.

```rust
// verified
/// `next_if_map` consumes a digit only when the next item is one.
#[must_use]
pub fn leading_digits(text: &str) -> u32 {
    let mut chars = text.chars().peekable();
    let mut value = 0_u32;
    while let Some(digit) = chars.next_if_map(|c| c.to_digit(10).ok_or(c)) {
        value = value.saturating_mul(10).saturating_add(digit);
    }
    value
}

#[cfg(test)]
mod tests {
    #[test]
    fn stops_at_the_first_non_digit() {
        assert_eq!(super::leading_digits("123abc"), 123);
    }
}
```

### RS-FUNC-16 [M] Keep iterators lazy as far up the stack as you can

Take `impl IntoIterator<Item = T>`, and return an iterator rather than a collection whenever the
caller may consume only part of the sequence or feed it to another adapter; RS-TRAIT-15 spells the
return type.

**Why:** materialization belongs to whoever knows how much of the sequence is needed, which is the
caller. Returning `Vec<T>` decides on their behalf that all of it is computed and all of it stored,
and feeding it to another adapter costs a second allocation.

**Check:** does the function return a collection the caller might only partially consume? Does the
caller immediately `.iter()` or `.into_iter()` it, or index only the first element?

```rust
// verified
/// Nothing is computed until the caller asks, and only as much as it asks for.
pub fn non_empty(lines: &[String]) -> impl Iterator<Item = &str> {
    lines
        .iter()
        .map(String::as_str)
        .filter(|line| !line.is_empty())
}
```

### RS-FUNC-17 [S] Collect directly into the collection the caller needs

`collect::<HashMap<_, _>>()`, `collect::<BTreeSet<_>>()`, `collect::<String>()`,
`collect::<Result<Vec<_>, _>>()`.

**Why:** collecting into a `Vec` and converting afterwards allocates twice and iterates twice, and
`FromIterator` impls exist for exactly this reason. `Result<Vec<_>, _>` in particular is not a
special case — it is the same mechanism (RS-FUNC-13).

**Check:** grep for `collect` followed by `into_iter().collect()`, `HashMap::from_iter`, or a `for`
loop that inserts.

### RS-FUNC-18 [S] Do not build a collection to measure it

**Why:** calling `.len()` on a freshly built `Vec` just to size the next one means two passes and an
allocation you did not need. Either `count()` the iterator (which consumes it, so clone the source
or restructure), or produce both outputs in one pass.

**Check:** grep for `.len()` on a binding created by the immediately preceding `collect`.

### RS-FUNC-19 [S] Replace index arithmetic with the adapters that encode it

`rev`, `skip`, `take`, `step_by`, `chain`, `cycle`, `zip`, and over a slice `array_windows` and
`chunks_exact`, which hand each group over as an array to destructure.

**Why:** each of these is a place an off-by-one lives. `zip` stops at the shorter side, which
removes the `min(a.len(), b.len())` people get wrong, and `windows(2)` hands back a slice that the
shipped `indexing_slicing` deny then refuses to index.

**Check:** grep for `len() - 1`, `..len()`, `min(.*len`, and `windows(` followed by an index.

```rust
// verified
/// `zip` pairs two sequences without indexing either.
#[must_use]
pub fn dot(left: &[i64], right: &[i64]) -> i64 {
    left.iter().zip(right).map(|(a, b)| a * b).sum()
}

/// `array_windows` hands each pair over as an array, so nothing is indexed.
#[must_use]
pub fn deltas(values: &[i64]) -> Vec<i64> {
    values.array_windows().map(|&[a, b]| b - a).collect()
}
```

### RS-FUNC-20 [S] Justify `itertools` by naming the adapters you use

**Why:** `tuple_windows`, `sorted_by`, `partition_map`, `izip!`, and `chunk_by` on an iterator have
no `std` equivalent and earn the dependency. On a slice, `chunk_by`, `array_windows`, and
`Vec::dedup_by` are `std`, and "we already depend on it" is no justification (RS-BUILD-19).

**Check:** grep the crate for `itertools::` and list the distinct adapters. If the list is one entry
and `std` has an equivalent, drop the dependency.

### RS-FUNC-21 [S] Break a pipeline the reader cannot hold

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

## Immutability and bindings

### RS-FUNC-22 [S] Treat every `let mut` as a proof obligation

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

### RS-FUNC-23 [S] Prefer shadowing to mutation for stepwise refinement

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

### RS-FUNC-24 [M] Do not shadow across a large scope or with a new meaning

**Why:** shadowing is a refinement tool, not a name-recycling tool. Two different concepts sharing a
name three screens apart means a reader who scrolls up finds the wrong definition — which is
strictly worse than a second name, because it looks correct.

**Check:** does each shadow refine the same concept, and does it occur within a few lines of the
binding it shadows?

### RS-FUNC-25 [S] Push constants into `const` and `const fn`

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

### RS-FUNC-26 [S] Use the in-place operations that have functional signatures

`retain`, `sort_unstable_by_key`, `dedup`, `truncate`, `fill`. To remove by predicate and keep what
was removed, `extract_if`, on `Vec`, `HashMap`, `HashSet`, `BTreeMap`, and `BTreeSet`. To pop an end
only when it matches, `Vec::pop_if` and `VecDeque::pop_front_if`/`pop_back_if`; to keep only the
last `n` of a `VecDeque`, `retain_back`.

**Why:** in-place mutation is the right answer for large data — it avoids the copy — but it does not
have to mean manual index shuffling. These methods take a predicate or a key function and do the
shuffling correctly, which hand-written versions frequently do not.

**Check:** grep for loops that `remove(i)` inside iteration, or that build a second `Vec` in order
to delete from the first. Both are `retain`, or `extract_if` when the removed items are used.
`clippy::manual_pop_if` flags a `last()` test followed by a `pop()`.

### RS-FUNC-27 [M] Never mutate a captured variable from inside `map`

**Why:** `map` with a side effect is `for_each` lying about its purpose. It also breaks the moment
someone adds `.rev()`, `.par_iter()`, or a `take` that short-circuits — because `map` promises
nothing about order or about being run at all.

**Check:** does any `map` closure assign to something declared outside it, or call a method taking
`&mut` on a captured value?

### RS-FUNC-28 [S] Reserve `mem::take` / `mem::replace` for state machines

**Why:** they are exactly right for moving out of `&mut self` during a state transition, and a smell
everywhere else — where they usually mean the function should have taken `self` by value, or the
field should have been an `Option` the caller manages.

**Check:** for each `mem::take`, is the enclosing type a state machine? If not, what would taking
`self` by value cost?

### RS-FUNC-29 [S] Give a build-once type no `&mut self` methods at all

**Why:** if a type is constructed and then only read, expressing that in the API means the compiler
enforces the immutability you intended, and callers can share it behind `&` or `Arc` without a lock.
A single `&mut self` method removes that guarantee for every user.

**Check:** list the `&mut self` methods. Are any of them called after construction finishes? If not,
fold them into the builder.

## Closures and functions as values

### RS-FUNC-30 [M] Choose the loosest closure bound the callee needs

`FnOnce` if it is called once, `FnMut` if repeatedly with state, `Fn` only when it must be callable
from a shared reference or in parallel. An async callback takes the same order over `AsyncFnOnce`,
`AsyncFnMut`, and `AsyncFn`.

**Why:** the bound is a requirement on every caller. Demanding `Fn` when `FnOnce` suffices rejects
closures that consume their captures — which is most of the interesting ones — and the caller's only
workaround is to clone.

**Check:** for each `F: Fn`, is the closure ever called more than once, or from behind `&self`? If
not, loosen it.

### RS-FUNC-31 [S] Take closures generically when hot, boxed when stored

`f: impl Fn(&T) -> U` for small, frequently called callbacks; `Box<dyn Fn(&T) -> U>` when it must
live in a struct field or when monomorphization bloat is measurable. Take an async callback as
`impl AsyncFn(&T) -> U`, not as `F: Fn(&T) -> Fut` with `Fut: Future`, whose future cannot borrow
the argument (nor, under `FnMut`, the captured state).

**Why:** the generic form inlines and costs a monomorphization per call site; the boxed form costs
an indirect call and an allocation but keeps the code size flat and the type nameable (RS-TRAIT-13).

**Check:** does the closure get stored, or does the function get instantiated for many types? Either
answer points at boxing.

### RS-FUNC-32 [S] Capture as little as possible

A closure captures only the fields it names, so `self.filter` inside it borrows that field alone. A
method call on `self` still borrows all of it.

**Why:** a closure that calls `self.keeps(item)` holds `&self` while it lives, which blocks the
`&mut self.items` beside it — the usual cause of "cannot borrow `self` as mutable". Binding what the
method reads first leaves disjoint borrows (RS-OWN-06).

**Check:** does the closure call a method on `self`? Bind what it reads to a local before the
closure, or make the method a function of those fields.

```rust
// fragment — BAD: the method call borrows all of self while `items` is borrowed mutably
self.items.retain(|&item| self.keeps(item));
```

```rust
// fragment — GOOD: the closure reads one local
let limit = self.limit;
self.items.retain(|&item| item <= limit);
```

### RS-FUNC-33 [M] Bind what a `move` closure should only borrow outside it

**Why:** `move` is not selective. To move one field into a closure and borrow another, bind them
outside first — this is the standard fix for "cannot move out of `self`", and reaching for `clone()`
instead is exactly the defect in RS-OWN-08.

**Check:** for each `move` closure, list what it captures. Is anything captured by move that the
surrounding scope still needs?

### RS-FUNC-34 [S] Name a closure that outgrows a few lines

**Why:** a five-line closure has a purpose, and the purpose deserves a name — for the reader, and
for the profiler, where an anonymous closure shows up as a mangled symbol nobody can attribute.

**Check:** any closure spanning more than about five lines, or containing its own control flow.

### RS-FUNC-35 [S] Use `fn` pointers for tables of handlers

Dispatch through them; do not compare two for identity. One function can have several addresses and
two can share one, which `unpredictable_function_pointer_comparisons` warns on.

**Why:** `fn(&str) -> bool` is `Copy` and `'static`, so a table of them can be a `const` array —
which is exactly how ripgrep's flag table dispatches. A `Box<dyn Fn>` in the same position costs an
allocation each and cannot be `const`.

**Check:** do the handlers capture anything? If not, they are `fn` pointers. An `==` between two of
them is the `unpredictable_function_pointer_comparisons` row.

## Purity, effects, composition

### RS-FUNC-36 [M] Separate computing from doing, and push the doing to the edges

Parse and read at the entry, compute over plain data in the middle, write and log at the exit. A
function that derives a value returns it, and its caller connects it to the sink.

**Why:** a function that both computes and writes cannot be tested without a sink, reused with
another, or parallelized. A middle layer with no I/O, clock, or environment tests in milliseconds,
which is what makes `run() -> Result<()>` testable (RS-MOD-19).

**Check:** does the function both compute and print, log, write, or send? Split it. How deep in the
call stack is the deepest I/O call? Everything below the entry layer should be pure.

### RS-FUNC-37 [M] Parse, don't validate

Convert untrusted input into a type that cannot be invalid, at the boundary — a CLI flag, a config
file, a request — and let every downstream function take the parsed type. Its constructor or
`FromStr` is the one place the check lives.

**Why:** after `validate(&str) -> Result<(), Error>` the code still handles `&str`, and someone will
call it without the check. A parsed type makes the check unskippable, and an error raised at the
boundary names the flag or field rather than surfacing three layers down.

**Check:** grep for `validate_*` or `check_*` returning `Result<(), _>`, and for the same validation
in more than one function: each is a constructor waiting to be written. How far does the raw `&str`
travel from the entry point? Past the first layer is a missing type.

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

### RS-FUNC-38 [S] Make functions total where you can

**Why:** a signature that cannot fail is easier to call, easier to compose, and easier to test than
one returning `Result` because a caller *might* pass nonsense. Making the nonsense unconstructible
moves the check to one place instead of every entry point (RS-FUNC-37).

**Check:** for each `Result`-returning function, is the error reachable given properly typed inputs?
If not, the types should absorb it.

### RS-FUNC-39 [S] Take the clock, the RNG, and the filesystem as parameters

`fn expire(now: Instant, …)` rather than `Instant::now()` inside.

**Why:** the parameterized version is trivially testable with a fixed value and trivially
deterministic; the internal version needs either a fake clock crate or a `sleep` in the test. The
same argument applies to randomness and to the current directory.

**Check:** grep for `Instant::now`, `SystemTime::now`, `rand::random`, `env::var`, and
`env::current_dir` below the entry layer.

### RS-FUNC-40 [S] Model state transitions as values or as types

Return the new state as a value; where misuse is costly and the states are few, make them types
(RS-TRAIT-42).

**Why:** an object that is "not yet initialized" for its first three method calls is two types
wearing one name, and every method has to handle a state it should never see.

**Check:** does a transition mutate a state field in place where it could take `self` and return the
next state?

### RS-FUNC-41 [S] Keep the happy path linear with combinators

`opt.map(f).filter(p).unwrap_or_default()`, `res.and_then(g).or_else(h)`.

**Why:** the linear form reads top to bottom in the order the data flows, without the reader
tracking which branch they are in. Choose the eager or lazy variant deliberately (RS-ERR-23).

**Check:** does any nested `match` on `Option`/`Result` have arms that just forward?

```rust
// verified
/// `map_or` replaces a `match` whose arms are one expression each.
#[must_use]
pub fn width_or_default(value: Option<u32>) -> u32 {
    value.map_or(80, |width| width.max(1))
}
```

### RS-FUNC-42 [M] Write the `match` once a chain no longer reads aloud

**Why:** readability is the objective; functional style is the usual means, not the end. A chain
that requires the reader to track three type transformations is worse than the `match` it replaced,
and "but it is more functional" is not a defence. This rule outranks every `[S]` in this chapter.

**Check:** read the expression aloud. If you cannot say what it produces without re-reading, split
it (RS-FUNC-21) or write the `match`.

### RS-FUNC-43 [M!] Use an explicit worklist where recursion depth is unbounded

A recursion whose depth a constant bounds — an expression AST from your own builder, a directory
walk with a depth cap — asserts that constant at entry and stays recursive.

*Relaxed form:* recursion whose depth the input decides, accepting the stack overflow it risks.

**Why:** Rust has no guaranteed tail-call elimination, so recursion over attacker-controlled depth
is a stack overflow — which aborts immediately and cannot be caught. A `Vec` used as a worklist is
still functional in spirit, is bounded by the heap, and can be depth-limited with one comparison.

**Check:** for each recursive function, what bounds the depth? If the answer is "the input", it
needs a worklist or an asserted cap.

### RS-FUNC-44 [S] Expose a custom sequence by implementing `Iterator`

**Why:** a newtype with an `Iterator` impl keeps laziness at the boundary and gives users the whole
adapter library for free. Returning a `Vec` from a method named like a query decides materialization
for them (RS-FUNC-16).

**Check:** does any method named as a query (`entries`, `matches`, `children`) return a collection?

### RS-FUNC-45 [S] Treat a hard-to-write pipeline as information about the data model

**Why:** a pipeline that resists being written usually means the data has the wrong shape, not that
the problem is imperative: flags that should be an enum, parallel `Vec`s that should be one `Vec` of
structs. Once the shape is right, the functional form falls out.

**Check:** before adding a `mut`, spend one minute on the question: what shape would make this a
`map`? If an answer exists, it is usually also the better data model.

## Closure and uniformity

### RS-FUNC-46 [M] Make an operation on `T` return `T` where nothing else is carried

An operation on `T` that returns `T` composes with itself; one that returns a near-miss —
`Result<U, _>` where `T` would do, or a tuple that must be unpacked and rebuilt — does not.

**Why:** closure is what makes a chain possible at all. Each escape from the type forces the caller
to unpack, adapt, and repack — the patch code this standard exists to remove — while an operation
that lands back in `T` writes the conversion once, inside itself.

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

### RS-FUNC-47 [S] Keep the stages of a pipeline uniform in shape

Stages take one value and return one value. Resist a stage that also mutates a captured accumulator
(in a `map`, RS-FUNC-27 forbids it outright), one that returns a tuple only the next stage
understands, or one that is a `for` loop because it was easier.

**Why:** uniform stages can be reordered, tested individually, and parallelized (RS-CONC-36); one
stage with a side channel takes those properties from the whole chain, and it is where the bugs are,
because nobody can reason about it locally.

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

## Decided by tools

A tool settles these on its own; the shipped configuration enables each at the level shown.

| Tool | Lint | Level | Forbids |
|---|---|---|---|
| clippy | `needless_return` | warn | a trailing `return` |
| clippy | `match_like_matches_macro` | warn | a `match` that returns `true` or `false` — `matches!` |
| clippy | `map_clone` | warn | `.map(\|x\| x.clone())` — `.cloned()` |
| clippy | `filter_map_identity` | warn | `.filter_map(\|x\| x)` — `.flatten()` |
| clippy | `flat_map_identity` | warn | `.flat_map(\|x\| x)` — `.flatten()` |
| clippy | `needless_late_init` | warn | a binding declared before it is initialised |
| clippy | `manual_inspect` | warn | a `map` that returns its argument unchanged — `inspect` |
| clippy | `redundant_closure` | warn | `\|x\| f(x)` — pass `f` |
| clippy | `redundant_closure_for_method_calls` | warn | `\|x\| x.method()` — pass `T::method` |
| rustc | `unpredictable_function_pointer_comparisons` | warn | `==` between function pointers, whose addresses are not unique |
