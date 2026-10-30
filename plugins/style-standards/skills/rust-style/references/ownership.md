# Ownership, Borrowing, Lifetimes, Resources

Scope: who owns what and for how long. Choosing between `&T`, `&mut T`, and `T` in a signature;
clone discipline and `Cow`; lifetimes, elision, and when a type should not have one; smart pointers
and interior mutability; `Drop` and RAII. The *allocation cost* of these choices is in the
performance chapter; the *style* of the resulting function bodies is in the functional chapter;
`Send`/`Sync` and lock discipline are in the concurrency chapter.

Ownership is the design language of Rust, not an obstacle to route around. Most "the borrow checker
won't let me" moments are the compiler correctly reporting that the data model has two owners for
one thing, or one owner for two things. The fix is almost never `.clone()`.
## Contents

- **Borrowing and signatures**
  - RS-OWN-01 [M] Let the signature declare the ownership contract
  - RS-OWN-02 [M] Take by value when you store, transform, or consume
  - RS-OWN-03 [S] Return borrows for views and owned values for computations
  - RS-OWN-04 [M] Do not put a lifetime on a struct unless the borrow is the point
  - RS-OWN-05 [S] Treat two input references and one output as a design question
  - RS-OWN-06 [M] Split borrows by destructuring instead of fighting them
  - RS-OWN-07 [M] Use the slice-splitting APIs for disjoint mutation

- **Clone and allocation discipline**
  - RS-OWN-08 [M] Never clone to silence the borrow checker
  - RS-OWN-09 [S] Clone deliberately and locally
  - RS-OWN-10 [S] Write `Arc::clone(&x)` for a refcount bump
  - RS-OWN-11 [S] Prefer `to_owned` to `to_string` for `&str`
  - RS-OWN-12 [M] Do not allocate to compare, search, or slice
  - RS-OWN-13 [S] Return `Cow` when the fast path is a borrow
  - RS-OWN-14 [S] Do not use `Cow` in a field to postpone an ownership decision
  - RS-OWN-15 [S] Use `Box<[T]>`, `Box<str>`, and `Arc<[T]>` for finished data

- **Lifetimes**
  - RS-OWN-16 [M] Read every lifetime parameter as a constraint on your users
  - RS-OWN-17 [S] Do not require `'static` unless you spawn, erase, or store
  - RS-OWN-18 [M] Do not leak to satisfy a `'static` bound
  - RS-OWN-19 [S] Write higher-ranked bounds rather than avoiding borrowed callbacks
  - RS-OWN-20 [M] Do not build self-referential structs
  - RS-OWN-21 [S] Prefer indices to references for graph-shaped data
  - RS-OWN-22 [M] Narrow edition-2024 `impl Trait` capture with `use<>`
  - RS-OWN-23 [S] Re-examine the data model when a lifetime error resists three attempts

- **Smart pointers and interior mutability**
  - RS-OWN-24 [M] Justify every use of interior mutability in a comment
  - RS-OWN-25 [S] Pick the interior-mutability primitive for the actual access pattern
  - RS-OWN-26 [M] Keep `RefCell` borrows short and out of `Drop`
  - RS-OWN-27 [S] Use `Rc` in one thread and `Arc` across threads
  - RS-OWN-28 [M] Break reference cycles with `Weak`
  - RS-OWN-29 [S] Use `Box` for heap placement, not for borrow-checker relief
  - RS-OWN-30 [S] Avoid double indirection in pointer types
  - RS-OWN-31 [S] Use `make_mut` and `unwrap_or_clone` for copy-on-write

- **`Drop` and resources**
  - RS-OWN-32 [M] Acquire in the constructor, release in `Drop`
  - RS-OWN-33 [M] Make `Drop` infallible and offer an explicit `finish`
  - RS-OWN-34 [S] Do not implement `Drop` for logging alone
  - RS-OWN-35 [S] Keep guard types small
  - RS-OWN-36 [M] Name a guard binding; never bind it to `_`
  - RS-OWN-37 [M] Confine `ManuallyDrop` and `mem::forget` to the module that owns the invariant
  - RS-OWN-38 [S] Prefer scope-based cleanup to defer-style crates
  - RS-OWN-39 [M] Install process-wide resources once, at the top of `main`
- Decided by tools

---

## Borrowing and signatures

### RS-OWN-01 [M] Let the signature declare the ownership contract

`&T` means "I will read it and give it back". `&mut T` means "I will change it and give it back".
`T` means "it is mine now".

**Why:** the signature is the only place this is stated, and callers plan around it. Choosing the
weakest form that does the job is what makes a function accept the most callers — and choosing a
stronger one than you need imposes a clone on everyone who has something else in hand.

**Check:** for each parameter, does the body actually require the strength the signature demands?

```rust
// verified
use std::path::Path;

/// Take the borrowed form: every owner can call this, no caller is forced to allocate.
#[must_use]
pub fn extension_of(path: &Path) -> Option<&str> {
    path.extension().and_then(std::ffi::OsStr::to_str)
}
```

### RS-OWN-02 [M] Take by value when you store, transform, or consume

Take `T` when the body keeps it; a parameter it only reads is a borrow. Where a stored `String` may
arrive as a literal, take `impl Into<String>`, so an owner moves it in and a literal converts once.

**Why:** taking `&T` and cloning inside is strictly worse than taking `T`: the caller who had an
owned value now pays for a clone they could have avoided by moving, and the caller who had a borrow
pays exactly what they would have paid anyway.

**Check:** grep for `.clone()` and `.to_owned()` on a parameter in the first few lines of a
function. Each is a signature that should have taken ownership. The other direction is the
`needless_pass_by_value` row below.

```rust
// verified
/// Taking ownership only where the value is genuinely stored.
#[derive(Debug, Default)]
pub struct Registry {
    names: Vec<String>,
}

impl Registry {
    pub fn insert(&mut self, name: String) {
        self.names.push(name);
    }

    #[must_use]
    pub fn contains(&self, name: &str) -> bool {
        self.names.iter().any(|held| held == name)
    }
}
```

### RS-OWN-03 [S] Return borrows for views and owned values for computations

`fn name(&self) -> &str` for a field; `fn rendered(&self) -> String` for something built. Where the
result is only sometimes computed, `Cow<'_, str>` keeps the borrowed path free (RS-OWN-13).

**Why:** returning `String` from a function that already holds the `&str` charges every caller for
an allocation, including the ones who only compare it. Returning a borrow ties the result to
`&self`, which is correct when it *is* part of `self`.

**Check:** does the returned owned value get dropped immediately by most callers?

### RS-OWN-04 [M] Do not put a lifetime on a struct unless the borrow is the point

**Why:** a lifetime parameter is one of the most contagious decisions in the language: it spreads
into every type that holds yours and every impl written over it. Owning the data, holding an `Arc`,
or using an index into an arena usually costs less than the ergonomic tax it imposes.

**Check:** for each `struct Foo<'a>`, what does the borrow buy? If the answer is "avoids one clone
at construction", the trade is almost certainly wrong.

### RS-OWN-05 [S] Treat two input references and one output as a design question

**Why:** elision cannot choose between them, so you must annotate — and the moment you do, you are
declaring which input the output borrows from, permanently. That is usually the signal to ask
whether the output should be owned instead.

**Check:** for each such signature, would returning an owned value simplify every call site? Often
it does, at the cost of one allocation on a path that was not hot.

### RS-OWN-06 [M] Split borrows by destructuring instead of fighting them

`let Self { input, output, .. } = self;`

**Why:** the compiler tracks borrows per field but not through a method call, so
`self.parse(&self.input)` fails while destructuring first succeeds. This resolves the majority of
"cannot borrow `self` as mutable more than once" errors without a clone.

**Check:** for each "second mutable borrow" error, try destructuring before reaching for `clone` or
`RefCell`.

```rust
// fragment — BAD: borrows all of self twice
self.output.extend(self.transform(&self.input));
```

```rust
// fragment — GOOD: two disjoint field borrows
let Self { input, output, transformer } = self;
output.extend(transformer.transform(input));
```

### RS-OWN-07 [M] Use the slice-splitting APIs for disjoint mutation

`split_at_mut`, `chunks_mut`, `iter_mut`, `split_first_mut`, `get_disjoint_mut`.

**Why:** they encode the disjointness the compiler needs, so you get mutable access to two parts of
one slice without `unsafe`. Reaching for raw pointers here is the most common unnecessary `unsafe`
in Rust (`references/unsafe.md` RS-UNSAFE-01).

**Check:** grep for `unsafe` near slice indexing. Is there a splitting method that expresses it?

```rust
// verified
/// One `&mut` at a time: `split_at_mut` proves the halves are disjoint.
pub fn reverse_halves(values: &mut [u32]) {
    let mid = values.len() / 2;
    let (left, right) = values.split_at_mut(mid);
    left.reverse();
    right.reverse();
}
```

## Clone and allocation discipline

### RS-OWN-08 [M] Never clone to silence the borrow checker

Try, in order: shortening the borrow's scope, splitting the borrow (RS-OWN-06), giving the data one
owner, using an index or a handle — and only then cloning, with a comment saying which of those you
rejected and why.

**Why:** a clone that exists to make an error go away is an unexamined design flaw plus a permanent
runtime cost, and it hides the signal the compiler was sending.

**Check:** for each `.clone()`, would the code compile without it after one of the four moves above?
This is worth doing as an exercise on any codebase you inherit; the hit rate is high.

```rust
// verified
/// `std::mem::take` moves the value out and leaves the default, with no clone.
#[derive(Debug, Default)]
pub struct Batch {
    pending: Vec<String>,
}

impl Batch {
    #[must_use]
    pub fn drain(&mut self) -> Vec<String> {
        std::mem::take(&mut self.pending)
    }
}
```

### RS-OWN-09 [S] Clone deliberately and locally

**Why:** a `.clone()` on a hot path needs a justification in review, and a `String` clone inside a
loop over a million lines is a performance bug rather than a style preference. The problem is not
that clones are bad — it is that unexamined ones accumulate invisibly.

**Check:** `rg -c '\.clone\(\)'` per file, then look at the outliers rather than every hit.

```rust
// verified
/// Borrow to inspect; the caller keeps ownership and no clone happens.
#[must_use]
pub fn total_len(lines: &[String]) -> usize {
    lines.iter().map(String::len).sum()
}
```

### RS-OWN-10 [S] Write `Arc::clone(&x)` for a refcount bump

**Why:** it makes the cheap pointer copy visually distinct from a deep clone, which matters when
scanning a function for allocation. `x.clone()` on an `Arc<HashMap<..>>` reads exactly like cloning
the map.

**Check:** grep `.clone()` on bindings whose type is `Arc` or `Rc`.

### RS-OWN-11 [S] Prefer `to_owned` to `to_string` for `&str`

**Why:** `to_owned` says "take ownership of the same bytes"; `to_string` routes through the
`Display` machinery, which is a formatting call the optimizer usually but not always removes.
`String::from` is equally clear. Be consistent within a crate rather than mixing all three.

**Check:** `clippy::str_to_string` flags it if you want it mechanical.

### RS-OWN-12 [M] Do not allocate to compare, search, or slice

`trim`, `strip_prefix`, `split_once`, `find`, `ends_with` and `eq_ignore_ascii_case` all work on
borrows and return borrows: sub-slicing is pointer arithmetic.

**Why:** an owned copy made only to be compared, searched or sliced is allocated and dropped without
ever being needed. Building a lowercase `String` just to compare is the most common avoidable
allocation in text-handling code, and it is usually inside a loop.

**Check:** grep for `to_lowercase()`, `to_uppercase()`, `to_string()` and `format!` inside a
condition or a comparison. For each, find where the owned value is stored or returned; if it is only
read locally, delete the conversion.

```rust
// verified
/// Comparing and searching work on `&str`; no owned copy is needed.
#[must_use]
pub fn has_prefix(haystack: &str, prefix: &str) -> bool {
    haystack.starts_with(prefix)
}
```

### RS-OWN-13 [S] Return `Cow` when the fast path is a borrow

Normalization, escaping, path canonicalization — anything that usually returns its input unchanged.

**Why:** it gives the zero-allocation common case without forcing every caller to own, and the
caller can still call `.into_owned()` when they need to. Returning `String` unconditionally
allocates on the path where nothing changed, which is usually the overwhelming majority.

**Check:** does the function have an early return that would be `input.to_owned()`? That is a
`Cow::Borrowed`.

```rust
// verified
use std::borrow::Cow;

/// Allocates only when there is something to strip.
#[must_use]
pub fn strip_ansi(input: &str) -> Cow<'_, str> {
    if input.contains('\x1b') {
        Cow::Owned(input.replace('\x1b', ""))
    } else {
        Cow::Borrowed(input)
    }
}
```

### RS-OWN-14 [S] Do not use `Cow` in a field to postpone an ownership decision

**Why:** a `Cow` field is a lifetime parameter on your type (RS-OWN-04) plus an enum discriminant
checked on every access, bought in exchange for not deciding who owns the data. Decide.

**Check:** for each `Cow` field, is the borrowed variant ever actually constructed? Frequently it is
not, and the field should be `String`.

### RS-OWN-15 [S] Use `Box<[T]>`, `Box<str>`, and `Arc<[T]>` for finished data

For a field that never grows after construction, and for a return value that is the whole answer.
Nested finished data is `Box<[Box<str>]>`.

**Why:** one word less per value than `Vec`/`String`, and no spare capacity, which for a million
small values is megabytes. The type also says the length is final, where a `Vec` invites a caller to
push into data you consider done.

**Check:** does the collection grow after construction, or after it is returned? If not,
`into_boxed_slice()` is one call.

```rust
// verified
/// Finished data: one word smaller per value, and no spare capacity.
#[derive(Debug)]
pub struct Manifest {
    name: Box<str>,
    entries: Box<[u32]>,
}

impl Manifest {
    #[must_use]
    pub fn new(name: String, entries: Vec<u32>) -> Self {
        Self {
            name: name.into_boxed_str(),
            entries: entries.into_boxed_slice(),
        }
    }
}
```

## Lifetimes

### RS-OWN-16 [M] Read every lifetime parameter as a constraint on your users

**Why:** `<'a>` means "this value cannot outlive that borrow", and your users are the ones who have
to satisfy it — in their struct fields, their return types, and their spawned tasks. Adding one is
a decision about their code, not just yours.

**Check:** write the sentence "your value cannot outlive X" for each lifetime. Is X something users
will reasonably keep alive?

### RS-OWN-17 [S] Do not require `'static` unless you spawn, erase, or store

**Why:** `T: 'static` means "contains no borrows", which is normal for thread spawning and type
erasure and needlessly exclusionary everywhere else. It is the most over-applied bound in Rust, and
it rejects perfectly good borrowed types for no reason.

**Check:** for each `'static`, does the value cross a thread boundary, get boxed into a `dyn`, or
outlive the call? If not, remove it.

### RS-OWN-18 [M] Do not leak to satisfy a `'static` bound

Memory you mean to reclaim leaves through `Box::into_raw` or `Box::into_non_null` and comes back
through `from_raw`/`from_non_null`. Never rebuild a `Box` from a leaked reference: std's docs
call that "unleaking" and say to avoid it.

**Why:** `Box::leak` to make a `&'static str` is a memory leak dressed as a type fix, and in a
server it is an unbounded one. It is acceptable exactly once, at program start, for genuinely
process-lifetime configuration — and then it should be commented as such.

**Check:** grep `Box::leak`, `String::leak`, and `Vec::leak`. Each must be reachable only once per
process.

### RS-OWN-19 [S] Write higher-ranked bounds rather than avoiding borrowed callbacks

`for<'a> Fn(&'a str) -> &'a str`.

**Why:** the syntax is unfamiliar but the alternative — restructuring the API around owned data
purely to avoid it — imposes an allocation on every call for the sake of not writing eight
characters.

**Check:** does a callback signature force `String` where `&str` would do?

### RS-OWN-20 [M] Do not build self-referential structs

**Why:** they are not expressible safely, and every hand-rolled attempt with raw pointers is unsound
under move — which the compiler will not stop you from doing. Use indices into a shared arena, an
`id`-keyed map, or a crate built for the problem (`ouroboros`, `yoke`), and say in the docs which.

**Check:** does any struct hold a pointer or reference into another of its own fields?

### RS-OWN-21 [S] Prefer indices to references for graph-shaped data

`Vec<Node>` plus `NodeId(u32)`.

**Why:** it sidesteps lifetimes entirely, it is cache-friendly, it serializes trivially, and it
makes cycles representable without `Weak`. Newtype the index so it cannot be confused with a length
or with an index into a different arena (`references/api.md` RS-API-25).

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

### RS-OWN-22 [M] Narrow edition-2024 `impl Trait` capture with `use<>`

Write `+ use<'a, T>` (precise capturing) to state what is actually borrowed.

**Why:** in edition 2024 an `impl Trait` return captures *all* in-scope lifetimes by default, so a
returned iterator borrows every argument whether it needs to or not — and the caller cannot then
mutate an unrelated argument while holding it.

**Check:** does a returned `impl Trait` keep an argument borrowed that its implementation never
touches?

### RS-OWN-23 [S] Re-examine the data model when a lifetime error resists three attempts

**Why:** almost every intractable lifetime puzzle in application code is a design that has a borrow
where it wants ownership. Adding parameters makes the signature worse without fixing the cause; the
cost of stepping back is minutes, and the cost of not doing so is a type nobody can use.

**Check:** after the third failed annotation, ask: what if this owned its data? What if this were an
index?

## Smart pointers and interior mutability

### RS-OWN-24 [M] Justify every use of interior mutability in a comment

When the honest note is "this could be threaded through `&mut self`, but the refactor is large",
write that down rather than leaving it implied.

**Why:** `Cell`, `RefCell`, `Mutex`, and `OnceLock` all move a compile-time check to runtime or
remove it, and every `&self` method that mutates through them still reads as a pure query. The
declaration is the one place a reader can learn that state changes behind a shared reference.

**Check:** does every such field have a comment on its declaration?

### RS-OWN-25 [S] Pick the interior-mutability primitive for the actual access pattern

`Cell<T>` for `Copy` types, `RefCell<T>` for the rest in single-threaded code, `Mutex`/`RwLock`
across threads, `OnceLock`/`LazyLock` for one-time initialization.

**Why:** `Cell` has no runtime check at all and cannot panic; `RefCell` can. `OnceLock` and
`LazyLock` are in `std`, so `lazy_static` and `once_cell` are dependency weight for the common cases
(`references/concurrency.md` RS-CONC-27).

**Check:** grep for `RefCell<T>` where `T: Copy`.

### RS-OWN-26 [M] Keep `RefCell` borrows short and out of `Drop`

**Why:** a `RefCell` borrow conflict is a panic rather than a compile error, and a panic inside
`Drop` during unwinding aborts the process (RS-OWN-33). Holding a `Ref`
across a call that can re-enter is the classic way to hit it.

**Check:** does any `borrow()`/`borrow_mut()` result live across a function call? Bind it in the
smallest possible scope.

### RS-OWN-27 [S] Use `Rc` in one thread and `Arc` across threads

**Why:** `Arc`'s refcount operations are atomic, which is not free — and using it in
single-threaded code out of habit pays for a guarantee nobody needs. The compiler tells you when you
need `Arc`; it does not tell you when you do not.

**Check:** does the `Arc` ever cross a thread boundary or enter a `Send` bound? If not, `Rc`.

### RS-OWN-28 [M] Break reference cycles with `Weak`

**Why:** `Rc`/`Arc` cycles never drop — the memory and everything it owns leaks for the life of the
process. Parent pointers, observer registries, and back-references in doubly-linked structures are
the usual sites. Document which direction is strong.

**Check:** for each `Rc`/`Arc` field, can the graph contain a cycle through it? A tree with parent
pointers always can.

### RS-OWN-29 [S] Use `Box` for heap placement, not for borrow-checker relief

**Why:** `Box` is for recursive types, large values you move often, and trait objects. It is not a
general-purpose wrapper that makes lifetime errors go away — reaching for it in that role usually
means the value should have been owned somewhere else.

**Check:** for each `Box`, which of the three reasons applies?

### RS-OWN-30 [S] Avoid double indirection in pointer types

`Box<[T]>` not `Box<Vec<T>>`; `Arc<str>` not `Arc<String>`; `Rc<[T]>` not `Rc<Vec<T>>`.

**Why:** the second form in each pair is a pointer to a struct containing a pointer, so every access
is two dereferences and every value carries an extra two words. The first form stores the length in
the fat pointer.

**Check:** grep for `Arc<String>`, `Arc<Vec<` and `Rc<String>`. `Box<Vec<T>>` and a box inside an
`Rc` or `Arc` are the `box_collection` and `redundant_allocation` rows below.

### RS-OWN-31 [S] Use `make_mut` and `unwrap_or_clone` for copy-on-write

`Arc::make_mut` and `Rc::make_mut` to change the value in place; `Arc::unwrap_or_clone` and
`Rc::unwrap_or_clone` to take it out.

**Why:** each clones only when the refcount is greater than one, in a single call, correctly. The
manual alternative — `try_unwrap`, match, clone on failure — is four lines that do the same thing
with more places to get it wrong.

**Check:** grep for `Arc::try_unwrap` or `Rc::try_unwrap` followed by a clone.

```rust
// verified
use std::sync::Arc;

/// The last owner moves the list out; any other clones it, in one call.
#[must_use]
pub fn into_sorted(shared: Arc<Vec<u32>>) -> Vec<u32> {
    let mut values = Arc::unwrap_or_clone(shared);
    values.sort_unstable();
    values
}
```

## `Drop` and resources

### RS-OWN-32 [M] Acquire in the constructor, release in `Drop`

**Why:** RAII makes the release unforgettable, including on early return and on panic. Exposing
`open`/`close` pairs means every caller must get every path right, and the one they miss is the
error path they never tested.

**Check:** does the API have a `close`, `release`, `unlock`, or `end` that a caller must remember to
call? That is a guard type.

### RS-OWN-33 [M] Make `Drop` infallible and offer an explicit `finish`

Offer `fn finish(self) -> Result<T, Error>` for the path that can fail, and let `Drop` be the
best-effort fallback for the path that forgot.

**Why:** `Drop` cannot return a `Result`, so a failing flush or commit is silently swallowed —
`BufWriter` loses the last block and nobody finds out. A `Drop` that panics while another panic
unwinds aborts the process, with no cleanup anywhere.

**Check:** does any `Drop` impl perform I/O, commit, or flush? Is there a fallible alternative the
caller can use? Does any `Drop` call `unwrap`, `expect`, `assert`, or anything else that can panic?

```rust
// verified
use std::io::{self, Write};

/// `Drop` on a buffered writer swallows the error, so flush explicitly and check it.
///
/// # Errors
/// Returns the first write or flush error encountered.
pub fn write_all(mut sink: impl Write, lines: &[String]) -> io::Result<()> {
    for line in lines {
        writeln!(sink, "{line}")?;
    }
    sink.flush()
}
```

### RS-OWN-34 [S] Do not implement `Drop` for logging alone

**Why:** a `Drop` impl prevents destructuring the type by move, prevents partial moves out of it,
and surprises callers who expected a plain value. That is a large ergonomic cost for a log line.

**Check:** does the `Drop` release a resource, or only observe? If only observe, remove it.

### RS-OWN-35 [S] Keep guard types small

**Why:** a type with `Drop` cannot be partially moved out of, so anything the guard holds is held
until the guard dies. A guard that carries the whole context keeps the whole context alive and
borrowed.

**Check:** does the guard hold more than the release needs?

### RS-OWN-36 [M] Name a guard binding; never bind it to `_`

**Why:** `let _ = cell.borrow_mut();` drops the guard at once, ending the borrow before the code
that needed it runs: a bug that compiles and looks correct. rustc rejects it for a std lock guard
(`let_underscore_lock`), not for a `RefCell`'s or another crate's lock; `let _guard = …` holds both.

**Check:** `rg -n 'let _ = .*\.(borrow|borrow_mut|enter|read|write)\('`. A std `Mutex` or `RwLock`
guard is the `let_underscore_lock` row below; any other hit compiles, and is the defect.

```rust
// rejected — rustc: non-binding let on a synchronization lock (`let_underscore_lock`)
let _ = self.state.lock();
```

```rust
// fragment — GOOD: held until end of scope
let _guard = self.state.lock();
```

### RS-OWN-37 [M] Confine `ManuallyDrop` and `mem::forget` to the module that owns the invariant

**Why:** both are safe functions with unsafe consequences for other people's invariants — leaking a
guard, skipping a `Drop` that another type relies on. They are legitimate inside an abstraction that
knows the whole picture and dangerous anywhere else.

**Check:** grep `ManuallyDrop`; each needs a comment and should be inside the module that defines
the type it applies to. `mem::forget` is the `mem_forget` row below, so each needs an `#[expect]`
with its reason.

### RS-OWN-38 [S] Prefer scope-based cleanup to defer-style crates

**Why:** a block, a guard struct, or a closure taking `&mut T` all express "cleanup happens" using
only the language, with no dependency and no macro. A `defer!` macro also runs at end of scope, so
it buys nothing except unfamiliarity.

**Check:** is there a `defer`-style dependency? What does it do that a guard struct does not?

### RS-OWN-39 [M] Install process-wide resources once, at the top of `main`

Signal handlers, terminal raw mode, the global logger, panic hooks.

**Why:** installing from a library constructor makes the crate unusable inside another program —
two callers fight over one handler, and the second silently wins. Pass handles downward instead.

**Check:** grep for `set_hook`, `signal`, `set_logger`, and terminal-mode calls outside `main`.

```rust
// verified
/// The library takes a handle; installing process-wide state is the binary's job.
#[derive(Debug)]
pub struct Reporter<W> {
    sink: W,
}

impl<W: std::io::Write> Reporter<W> {
    #[must_use]
    pub fn new(sink: W) -> Self {
        Self { sink }
    }

    /// # Errors
    /// Propagates any write error from the sink.
    pub fn report(&mut self, message: &str) -> std::io::Result<()> {
        writeln!(self.sink, "{message}")
    }
}
```

## Decided by tools

A tool settles these on its own; the shipped configuration enables each at the level shown.

| Tool | Lint | Level | Forbids |
|---|---|---|---|
| clippy | `ptr_arg` | warn | `&Vec<T>`, `&String` or `&PathBuf` where `&[T]`, `&str` or `&Path` serves |
| clippy | `needless_pass_by_value` | warn | an owned parameter the body only reads — borrow it |
| rustc | `elided_lifetimes_in_paths` | warn | a type whose lifetime the path hides — write `Iter<'_, T>` |
| rustc | `mismatched_lifetime_syntaxes` | warn | a lifetime hidden in the return type while the input names it |
| clippy | `elidable_lifetime_names` | warn | a named lifetime where `'_` says the same |
| clippy | `needless_lifetimes` | warn | a lifetime parameter elision would supply |
| clippy | `box_collection` | warn | `Box<Vec<T>>`, `Box<String>`: a pointer to a pointer |
| clippy | `redundant_allocation` | warn | `Rc<Box<T>>`, `Box<&T>` and the other boxes around a pointer |
| rustc | `let_underscore_lock` | deny | `let _ = mutex.lock()`, which unlocks before the next line |
| clippy | `mem_forget` | deny | `mem::forget`, which skips a `Drop` someone relies on |
