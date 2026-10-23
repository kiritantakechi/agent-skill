# RS-DOC — Documentation

Rustdoc is not a courtesy; it is the contract in prose plus a test suite that
proves the prose is true. The bar: a competent Rust programmer who has never
seen the crate can accomplish the primary use case from `docs.rs` alone,
without reading the source.
## Contents

- **Crate and module documentation**
  - RS-DOC-01 [M] Answer four questions, in order, in the crate root
  - RS-DOC-02 [M] Document every feature flag with what it enables and its cost
  - RS-DOC-03 [S] Document crate-wide invariants once and link to them
  - RS-DOC-04 [S] Position the crate against its obvious alternatives
  - RS-DOC-05 [S] Keep the crate root example runnable and one screen long

- **Item documentation**
  - RS-DOC-06 [M] Give every public item a summary, and every non-trivial one an example
  - RS-DOC-07 [M] Make the first line one third-person sentence
  - RS-DOC-08 [M] Leave a blank line after the summary
  - RS-DOC-09 [M] Use the standard section order
  - RS-DOC-10 [M] Give every `Result`-returning function an `# Errors` section
  - RS-DOC-11 [M] Give every panicking function a `# Panics` section
  - RS-DOC-12 [S] Document complexity and allocation where users would guess
  - RS-DOC-13 [M] Put trait contracts on the trait, impl behaviour on the impl
  - RS-DOC-14 [M] Document what a type guarantees, not only what it stores
  - RS-DOC-15 [S] Document surprising lifetime and borrowing implications
  - RS-DOC-16 [S] Comment private items where the *why* is non-obvious

- **Prose and style**
  - RS-DOC-17 [S] Write for someone competent but unfamiliar
  - RS-DOC-18 [M] Explain *why*, not *what*
  - RS-DOC-19 [M] Delete commented-out code
  - RS-DOC-20 [M] Update comments in the same edit as the code they describe
  - RS-DOC-21 [S] Prefer active voice and present tense
  - RS-DOC-22 [M] Backtick every identifier, type, and literal
  - RS-DOC-23 [M] Keep examples idiomatic — they will be copied
  - RS-DOC-24 [S] Hide setup noise, never the part that makes the example correct
  - RS-DOC-25 [S] Give a surviving TODO an owner and an issue link
  - RS-DOC-26 [S] Write changelog entries from the user's perspective

- **Linking, rendering, README**
  - RS-DOC-27 [M] Use intra-doc links everywhere
  - RS-DOC-28 [S] Link the first mention, not every mention
  - RS-DOC-29 [S] Add `#[doc(alias)]` for names users will search for
  - RS-DOC-30 [S] Keep the README and the crate docs in sync
  - RS-DOC-31 [S] Cover seven things in the README, above the fold
  - RS-DOC-32 [S] Add a diagram or walkthrough for non-obvious data flow
  - RS-DOC-33 [M] Document supported platforms, MSRV, and semver policy
  - RS-DOC-34 [M!] Write the documentation before finalizing the API
- Decided by tools

---

## Crate and module documentation

### RS-DOC-01 [M] Answer four questions, in order, in the crate root

The crate root `//!` block answers, in order: what this crate is for, the smallest complete working
example (`RS-DOC-05`), the two or three types to read first, and any crate-wide concepts (feature
flags, error type, threading model). This is the single most-read page you will write.

**Why:** it is the page every user lands on from crates.io and docs.rs, and the only one most of
them read. The order matters because a reader who does not get "is this the right crate?" answered
in two sentences never reaches the example.

**Check:** read the rendered front page cold. If you cannot copy a working program out of it in
under a minute, the block is not doing its job.

### RS-DOC-02 [M] Document every feature flag with what it enables and its cost

Document feature flags in the crate root, with what each enables and its cost. Users choosing
`--no-default-features` need this and cannot get it from the item list.

**Why:** features are the part of the API that does not appear in the API. A user auditing
dependencies or building for a constrained target is making a decision with real consequences, and
the manifest alone tells them the names but never the trade.

**Check:** for each entry in `[features]`, find the sentence in the crate docs that says what
turning it on adds and what it costs. A missing sentence is a violation (`RS-BUILD-13`).

### RS-DOC-03 [S] Document crate-wide invariants once and link to them

Document crate-wide invariants once, in the root, and link to them from the items they constrain:
thread-safety guarantees, allocation behaviour, Unicode handling, platform differences.

**Why:** restating an invariant at every item guarantees the copies drift. One authoritative
statement plus intra-doc links keeps them in sync by construction, and gives the reader one place to
learn the model rather than twelve partial views of it.

**Check:** grep the docs for a repeated invariant sentence. More than one copy means it wants to be
a root section with links.

### RS-DOC-04 [S] Position the crate against its obvious alternatives

Include a "Comparison" or "When to use this" section when the crate competes with obvious
alternatives. Honest positioning saves users an evaluation cycle and earns more trust than omission.

**Why:** the user is going to make the comparison anyway, using worse information than you have.
Making it for them costs a paragraph and buys credibility — including from the users you send
elsewhere, who come back for the case you *are* right for.

**Check:** name the two crates a reader would evaluate against yours. If the docs do not mention
them, the section is missing.

### RS-DOC-05 [S] Keep the crate root example runnable and one screen long

Keep the crate root example runnable and small enough to read in one screen. If the primary use case
cannot fit, the API surface is the problem, not the example.

**Why:** the example is a proxy for the API's ergonomics. Needing thirty lines of setup to do the
common thing is a design finding that the example surfaced for free.

**Check:** count the lines in the root example. Past roughly twenty, ask which of them are ceremony
the API could have absorbed.

## Item documentation

### RS-DOC-06 [M] Give every public item a summary, and every non-trivial one an example

Every public item gets a summary line, and every non-trivial one gets an example. Examples are doc
tests, and each must compile and pass, so they are verified on every CI run — this is the mechanism
that keeps documentation honest.

**Why:** an example is the only documentation that cannot silently rot, because the compiler checks
it. Prose describing an API that changed last release is worse than no prose, since the reader
trusts it.

**Check:** `cargo test --doc` runs a test for every example. Compare its count against the number of
public items; a large gap is the list of items with no example.

### RS-DOC-07 [M] Make the first line one third-person sentence

The first line is a single sentence in the third person, describing what the item does: "Returns the
number of matching lines." Not "This function will return…", not a fragment. It becomes the summary
in every index page, so it must stand alone.

**Why:** rustdoc lifts that line into module listings, search results, and the sidebar, stripped of
all surrounding context. A fragment, or a sentence that starts with "This", reads as noise once it
is sitting in a list of eighty siblings.

**Check:** read the module's rendered index page. Every summary should be a complete sentence that
still makes sense with the item name removed from the front.

```rust
// verified
/// Returns the number of matching lines.
///
/// The summary is one third-person sentence that still reads correctly in an
/// index listing, where the item name is shown separately.
#[must_use]
pub fn count_matches(lines: &[String], needle: &str) -> usize {
    lines.iter().filter(|line| line.contains(needle)).count()
}
```

### RS-DOC-08 [M] Leave a blank line after the summary

Leave a blank line after the summary. Rustdoc uses everything up to the first blank line as the
short description; a wall of text without one renders badly in every listing.

**Why:** this is a mechanical rustdoc rule, not a stylistic preference — the blank line is the
delimiter. Omitting it dumps an entire paragraph into every index table.

**Check:** look at the rendered listing, not the source. A summary column containing three sentences
is a missing blank line.

```rust
// verified
/// Returns the trimmed input.
///
/// The blank line above separates the summary from the body, which is what
/// rustdoc uses to build every index listing.
#[must_use]
pub fn trimmed(input: &str) -> &str {
    input.trim()
}
```

### RS-DOC-09 [M] Use the standard section order

Use the standard section order, omitting what does not apply: summary, extended description,
`# Examples`, `# Errors`, `# Panics`, `# Safety`, `# Performance`,
`# Platform-specific behavior`. Consistency lets readers jump straight to what they need.

**Why:** readers scan documentation, they do not read it. A predictable order means "can this
panic?" is answered by looking at a known position rather than reading the whole page — and `std`
has trained every Rust programmer on exactly this order.

**Check:** grep for `# ` headings inside doc comments and confirm the relative order. Any item with
a different order is a finding.

```rust
// verified
/// Parses a duration written as a whole number of seconds.
///
/// Accepts a bare integer with no unit suffix. Leading and trailing
/// whitespace is ignored.
///
/// # Examples
/// ```
/// # use mycrate::parse_seconds;
/// assert!(parse_seconds(" 30 ").is_ok());
/// ```
///
/// # Errors
/// Returns [`std::num::ParseIntError`] when the input is not an integer.
pub fn parse_seconds(input: &str) -> Result<std::time::Duration, std::num::ParseIntError> {
    input.trim().parse().map(std::time::Duration::from_secs)
}
```

### RS-DOC-10 [M] Give every `Result`-returning function an `# Errors` section

Every function returning `Result` has an `# Errors` section stating the conditions under which each
error variant is produced. "Returns an error if the operation fails" is not documentation.

**Why:** the error type tells the caller what *shape* the failure has; only prose tells them what
*causes* it, and that is what they need to decide whether to retry, report, or abort. A caller who
cannot tell which variants are reachable handles all of them badly.

**Check:** for each `Result`-returning public function, list its reachable variants and find each
one named in the `# Errors` section. The `missing_errors_doc` row checks only that the section
exists.

```rust
// verified
/// Loads the configuration file.
///
/// # Errors
/// Returns [`Error::Missing`] when the path does not exist, and
/// [`Error::Empty`] when the file contains no directives — the two are
/// distinguished so a caller can create a default in the first case.
pub fn load(text: Option<&str>) -> Result<usize, Error> {
    let Some(text) = text else {
        return Err(Error::Missing);
    };
    let count = text.lines().filter(|line| !line.trim().is_empty()).count();
    if count == 0 {
        Err(Error::Empty)
    } else {
        Ok(count)
    }
}

/// Why a configuration could not be loaded.
#[derive(Debug, Clone, Copy, PartialEq, Eq, thiserror::Error)]
pub enum Error {
    /// No file was found at the given path.
    #[error("configuration file is missing")]
    Missing,
    /// The file exists but holds no directives.
    #[error("configuration file is empty")]
    Empty,
}
```

### RS-DOC-11 [M] Give every panicking function a `# Panics` section

Every function that can panic has a `# Panics` section naming the exact condition — index out of
bounds, capacity overflow, a violated precondition. An undocumented panic is an undocumented API
contract. Mark a function that panics on caller error `#[track_caller]` (`RS-API-35`).

**Why:** a panic is part of the signature that the type system does not express. A caller in a
server or a plugin needs to know which calls can take the process down, and the docs are the only
place that can be written.

**Check:** grep the body for `panic!`, `unwrap`, `expect`, `assert`, indexing, slicing, integer
division and `Duration` arithmetic. Each reachable one must correspond to a documented condition.
The `missing_panics_doc` row catches only a missing section.

```rust
// verified
/// Returns the element at `index`.
///
/// # Panics
/// Panics when `index` is out of bounds. Use [`get`] for the checked form.
#[must_use]
#[expect(
    clippy::indexing_slicing,
    reason = "the panic is this function's documented contract; `get` is the checked form"
)]
pub fn at(values: &[u32], index: usize) -> u32 {
    values[index]
}

/// Returns the element at `index`, or `None` when it is out of bounds.
#[must_use]
pub fn get(values: &[u32], index: usize) -> Option<u32> {
    values.get(index).copied()
}
```

### RS-DOC-12 [S] Document complexity and allocation where users would guess

Document complexity and allocation behaviour where users would otherwise guess: "runs in O(n log n)
and allocates once", "does not allocate if the input is already normalized". This is what makes a
library usable in a hot loop with confidence.

**Why:** without it, the careful user benchmarks your function to learn what one sentence could have
told them, and the careless user calls it in a loop. Documenting it also pins the behaviour as
something you intend to preserve.

**Check:** for each function on a plausible hot path, does the reader know whether it allocates? If
answering requires reading the body, document it.

```rust
// verified
/// Returns the unique values, in first-seen order.
///
/// Runs in O(n log n) and allocates once for the result and once for the
/// seen-set; the input is left untouched.
#[must_use]
pub fn unique(values: &[u32]) -> Vec<u32> {
    let mut seen = std::collections::BTreeSet::new();
    values
        .iter()
        .filter(|&&value| seen.insert(value))
        .copied()
        .collect()
}
```

### RS-DOC-13 [M] Put trait contracts on the trait, impl behaviour on the impl

Document trait contracts on the trait, and implementation-specific behaviour on the impl. An
implementor reads the trait; a caller of a concrete type reads the impl.

**Why:** the two audiences are different and read different pages. A contract written only on the
impl is invisible to the person writing the next implementation, which is exactly how
implementations that violate the contract get written.

**Check:** for each trait method, is the obligation an implementor must uphold stated on the trait
itself? If it only appears on one impl, it is in the wrong place.

### RS-DOC-14 [M] Document what a type guarantees, not only what it stores

Document what a type *guarantees*, not only what it stores: a `SortedVec` documents that it is
sorted; a `Utf8Path` documents that it is valid UTF-8. Those guarantees are the reason the type
exists.

**Why:** the guarantee is the entire value of the newtype — it is what lets callers skip a check
(`RS-API-18`). Documenting only the field tells the reader what you could have written as `Vec<T>`
and omits the part that matters.

**Check:** for each newtype and each type with a private constructor, state the invariant in one
sentence. If there is no invariant, ask why the type exists.

```rust
// verified
/// A list of names that is always sorted and never empty.
///
/// The guarantee is the reason this type exists: callers may binary-search
/// it without checking, and `first` cannot fail.
#[derive(Debug, Clone)]
pub struct SortedNames {
    names: Vec<String>,
}

impl SortedNames {
    /// Returns `None` when `names` is empty, which the type cannot represent.
    #[must_use]
    pub fn new(mut names: Vec<String>) -> Option<Self> {
        names.sort_unstable();
        (!names.is_empty()).then_some(Self { names })
    }

    /// Returns the first name. Never fails, by construction.
    #[must_use]
    pub fn first(&self) -> &str {
        self.names.first().map_or("", String::as_str)
    }
}
```

### RS-DOC-15 [S] Document surprising lifetime and borrowing implications

Document lifetime and borrowing implications when they are surprising: "the returned iterator
borrows `self`; drop it before calling `insert`".

**Why:** the compiler will enforce it, but a borrow error thirty lines from its cause is a bad way
to learn an API's shape. One sentence turns a confusing rejection into an expected one.

**Check:** for each method returning a borrow of `self`, is the consequence stated? Anything a user
would hit as a surprising borrowck error wants a line.

```rust
// verified
/// An index over a body of text.
#[derive(Debug, Default)]
pub struct Index {
    offsets: Vec<usize>,
}

impl Index {
    /// Returns an iterator over the recorded offsets.
    ///
    /// The returned iterator borrows `self`; drop it before calling
    /// [`Index::record`], which needs a unique borrow.
    pub fn offsets(&self) -> impl Iterator<Item = usize> {
        self.offsets.iter().copied()
    }

    /// Records one offset.
    pub fn record(&mut self, offset: usize) {
        self.offsets.push(offset);
    }
}
```

### RS-DOC-16 [S] Comment private items where the *why* is non-obvious

Private items deserve comments when the *why* is non-obvious (`RS-DOC-18`). Rustdoc will not publish
them, but the next maintainer will read them — and the next maintainer is usually you.

**Why:** the reasoning behind a non-obvious private implementation is the thing that gets lost
first, and it is exactly what a future change needs in order to be safe.

**Check:** for each private function longer than a screen, or containing a non-obvious constant, is
the reason recorded? A magic number with no comment is always a finding.

## Prose and style

### RS-DOC-17 [S] Write for someone competent but unfamiliar

Write for someone competent but unfamiliar. Do not explain what a `Result` is; do explain why this
function returns one.

**Why:** documentation aimed too low wastes the reader's attention and buries the specific
information in generic material; aimed too high it is unusable. "Competent but unfamiliar" is the
audience that actually reads library docs.

**Check:** does any sentence explain a language feature rather than this crate? That sentence
belongs in the Rust book, not here.

### RS-DOC-18 [M] Explain *why*, not *what*

Explain *why*, not *what*. `// increment i` is noise; `// skip the BOM, which some Windows editors
prepend` is the reason the line exists. Code says what; comments say why.

**Why:** the code already states what it does, and states it more reliably than a comment can, since
it cannot drift. The reasoning is the part that is not recoverable from reading the code, so it is
the part worth writing.

**Check:** for each comment, ask whether deleting the code would lose the information. If the
comment merely restates the line, delete the comment.

```rust
// verified
/// Strips a UTF-8 byte-order mark if one is present.
#[must_use]
pub fn strip_bom(input: &str) -> &str {
    // Some Windows editors prepend a BOM; it is not content, and it breaks
    // a leading-anchor match if it survives.
    input.strip_prefix('\u{feff}').unwrap_or(input)
}
```

### RS-DOC-19 [M] Delete commented-out code

Delete commented-out code. Version control remembers it; the file should not.

**Why:** commented-out code is ambiguous in a way that costs every future reader: it might be a
work-in-progress, a rollback, or dead weight, and nobody can tell which without archaeology. It also
never gets updated with the code around it.

**Check:** `rg -n '^[ \t]*// (let |if |\})' src/` — each is a finding.

### RS-DOC-20 [M] Update comments in the same edit as the code they describe

No stale comments. A comment that contradicts the code is worse than no comment, because readers
trust it. Update comments in the same edit as the code they describe.

**Why:** a wrong comment actively causes bugs — the reader believes it and skips reading the code.
Correctness of comments is not a tidiness concern; it is the same category as correctness of code.

**Check:** in review, read every comment adjacent to a changed line and confirm it is still true. A
diff that changes behaviour without touching a nearby comment deserves a second look.

### RS-DOC-21 [S] Prefer active voice and present tense

Prefer active voice and present tense: "Returns the parsed value", not "The parsed value will be
returned".

**Why:** it is shorter, it matches `std`, and it keeps the subject of the sentence the thing being
documented rather than an abstract process.

**Check:** grep doc comments for "will be", "is returned", "can be used to". Each is usually a
passive construction with a shorter active form.

### RS-DOC-22 [M] Backtick every identifier, type, and literal

Use `` `backticks` `` for every identifier, type, and literal. Unformatted identifiers in prose are
invisible when scanning.

**Why:** readers skim documentation looking for the name they care about, and monospace is what
makes a name findable in a paragraph. It also disambiguates ordinary English words used as
identifiers — `match`, `type`, `Box`.

**Check:** clippy's `doc_markdown` (pedantic) flags a `snake_case` or `CamelCase` token outside
backticks. Read the rendered docs for the literals and the plain words it cannot recognise.

```rust
// verified
/// Splits `line` on the first `=`, returning the key and the value.
///
/// Every identifier in this sentence is in backticks — `line`, `=`, `None` —
/// so a reader scanning for a name finds it. Returns `None` when there is no
/// `=` in the input.
#[must_use]
pub fn split_setting(line: &str) -> Option<(&str, &str)> {
    line.split_once('=')
}
```

### RS-DOC-23 [M] Keep examples idiomatic — they will be copied

Keep examples idiomatic — they will be copied. An example using `unwrap()` teaches `unwrap()`; an
example that ignores an error teaches ignoring errors. Use `?` inside a hidden
`# fn main() -> Result<(), Box<dyn std::error::Error>> {`, so the example models the error handling
you want copied.

**Why:** documentation examples are the most-copied code you will ever write, and they are copied
without the surrounding context that made the shortcut acceptable. Whatever the example does becomes
the house style of every crate that depends on you.

**Check:** grep doc comments for `unwrap()`, `expect(`, and `let _ =`. Each needs either a rewrite
or the hidden `main` and a `?` (`RS-DOC-24`).

### RS-DOC-24 [S] Hide setup noise, never the part that makes the example correct

Hide setup noise in doc tests with `#` prefixes, but never hide the part that makes the example
correct. A hidden `?` context is fine; a hidden initialization the reader must replicate is a trap.

**Why:** hiding exists so the example shows the idea rather than the ceremony. Hiding a step the
reader actually needs produces an example that compiles for you and fails for them — the worst
possible outcome, because it looks verified.

**Check:** copy the *visible* lines of the example into a fresh file. If it does not work, something
load-bearing is hidden.

### RS-DOC-25 [S] Give a surviving TODO an owner and an issue link

Avoid TODO comments in published code. If one must stay, give it an owner and an issue link:
`// TODO(#412): handle nested groups`. A bare `// TODO` is a wish.

**Why:** a TODO with no owner and no ticket is invisible to every process that would ever act on it,
so it accumulates forever. With an issue number it is tracked work; without one it is decoration.

**Check:** grep for `TODO`, `FIXME`, `XXX`, `HACK`. Each hit must carry an issue reference.

### RS-DOC-26 [S] Write changelog entries from the user's perspective

Keep a changelog entry per user-visible change, written from the user's perspective ("`Searcher` now
handles CRLF line endings"), not the implementation's ("refactor line-terminator handling")
(`RS-BUILD-11`).

**Why:** the changelog is read by people deciding whether to upgrade. An entry describing an
internal refactor answers a question nobody asked, while hiding the behaviour change that actually
affects them.

**Check:** for each entry, ask "what does this change for someone using the crate?" If the answer is
"nothing", it does not belong; if it differs from the entry, rewrite it.

## Linking, rendering, README

### RS-DOC-27 [M] Use intra-doc links everywhere

Use intra-doc links everywhere: ``[`Searcher`]``, ``[`Searcher::search`]``, ``[`std::io::Read`]``.
They are checked at build time, so they never rot, unlike manual URLs.

**Why:** a hand-written docs.rs URL encodes a version and a path that will both change, and nothing
tells you when it breaks. An intra-doc link is verified by the same command that builds the docs.

**Check:** `rg -n 'https://docs\.rs' src/` — each is a link that should be an intra-doc link.

```rust
// verified
/// Compiles a pattern.
///
/// The result is consumed by [`is_match`], and failures are reported as
/// [`CompileError`]. Intra-doc links are checked at build time, so neither
/// reference can rot.
///
/// # Errors
/// Returns [`CompileError`] when the pattern is empty.
pub fn compile(pattern: &str) -> Result<usize, CompileError> {
    if pattern.is_empty() {
        Err(CompileError)
    } else {
        Ok(pattern.len())
    }
}

/// Reports whether `haystack` matches a pattern compiled by [`compile`].
#[must_use]
pub fn is_match(compiled: usize, haystack: &str) -> bool {
    haystack.len() >= compiled
}

/// The pattern could not be compiled.
#[derive(Debug, Clone, Copy, PartialEq, Eq, thiserror::Error)]
#[error("pattern was empty")]
pub struct CompileError;
```

### RS-DOC-28 [S] Link the first mention, not every mention

Link the first mention of each significant type in a doc block, not every mention. Over-linking
makes prose unreadable.

**Why:** links are visually loud. When every noun is a link the reader loses the ability to skim,
and the useful links stop standing out.

**Check:** read a rendered paragraph. If more than a few words are coloured, cut the repeats.

### RS-DOC-29 [S] Add `#[doc(alias)]` for names users will search for

Use `#[doc(alias = "…")]` for names users will search for but that you did not choose:
`#[doc(alias = "grep")]` on a search function, `#[doc(alias = "sizeof")]` on `size_of`.

**Why:** users search with the vocabulary of the tool or language they came from, not yours. An
alias costs one line and connects them to the item they were looking for, and rustc's "no method
named" error suggests the aliased item to someone who typed the other name.

**Check:** list the words a newcomer from C, Python, or the shell would type. Any that find nothing
want an alias.

```rust
// verified
/// Returns the number of bytes in `value`.
#[doc(alias = "sizeof")]
#[doc(alias = "length")]
#[must_use]
pub fn byte_len(value: &str) -> usize {
    value.len()
}
```

### RS-DOC-30 [S] Keep the README and the crate docs in sync

The README is the crate's landing page on GitHub and often the first paragraph on crates.io. Keep it
in sync with the crate docs — or generate one from the other with
`#![doc = include_str!("../README.md")]`, which also makes the README's examples doc tests.

**Why:** two hand-maintained copies of the same introduction diverge within a release or two, and
the one on GitHub is usually the stale one. `include_str!` makes divergence impossible and upgrades
the README's examples into tested code.

**Check:** does the README example still compile? If it is not included via `include_str!`, nothing
is checking.

### RS-DOC-31 [S] Cover seven things in the README, above the fold

The README covers: what and why in two sentences, installation, a working example, a link to the
docs, feature flags, MSRV (`RS-DOC-33`), and license. In that order, above the fold.

**Why:** the README is evaluated in about fifteen seconds. The order is the order the questions
arrive in, and anything below the fold is not part of the decision.

**Check:** each of the seven items is present, and appears before the reader would have to scroll
twice.

### RS-DOC-32 [S] Add a diagram or walkthrough for non-obvious data flow

Include a diagram or a worked walkthrough for anything with non-obvious data flow — a search
pipeline, a state machine, a plugin protocol. An `ARCHITECTURE.md` at the repository root is the
highest-leverage document for attracting contributors.

**Why:** the shape of a system is the most expensive thing for a newcomer to reconstruct and the
cheapest for a maintainer to describe, because they already hold it. That asymmetry is why the
document pays for itself.

**Check:** could a new contributor name the major components and how data moves between them after
reading the repository's docs? If only the source answers that, the document is missing.

### RS-DOC-33 [M] Document supported platforms, MSRV, and semver policy

Document the supported platforms, the MSRV, and the semver policy explicitly. Users make purchasing
decisions on these and should not have to infer them from CI configuration.

**Why:** these three facts determine whether the crate can be adopted at all in a given environment.
Leaving them implicit means the answer is discovered during integration instead of during
evaluation.

**Check:** all three appear in the README or crate docs, and the MSRV matches `rust-version` in the
manifest (`RS-BUILD-31`).

### RS-DOC-34 [M!] Write the documentation before finalizing the API

Write the documentation before finalizing the API. If a function is hard to describe in one
sentence, it is doing two things — and you have just found that out for the price of a sentence
rather than a release.

**Why:** the summary line is the cheapest design review available. A signature that resists a
one-sentence description is telling you about a cohesion problem while it is still free to fix,
which is a strictly better time to learn it than after publishing.

**Check:** for each new public item, was the summary written before the body? A summary containing
"and" or "or" is the signal this rule exists to catch.

*Relaxed form:* for an internal binary or a prototype, write the summary line before the body and
let the rest follow the implementation. The signal you are buying — "this is hard to describe, so it
does too much" — arrives with the summary line alone.

```rust
// verified
/// Returns the matching lines.
///
/// The summary was written before the body; it needed no "and", which is the
/// signal that the function does one thing.
#[must_use]
pub fn matching<'lines>(lines: &'lines [String], needle: &str) -> Vec<&'lines str> {
    lines
        .iter()
        .filter(|line| line.contains(needle))
        .map(String::as_str)
        .collect()
}
```

## Decided by tools

A tool settles these on its own; the shipped configuration enables each at the level shown.

| Tool | Lint | Level | Forbids |
|---|---|---|---|
| rustdoc | `broken_intra_doc_links` | deny | an intra-doc link that no longer resolves |
| rustc | `missing_docs` | deny | a public item with no documentation |
| clippy | `doc_markdown` | warn | an identifier in doc prose without backticks |
| clippy | `missing_errors_doc` | warn | a public function returning `Result` with no `# Errors` section |
| clippy | `missing_panics_doc` | warn | a public function that can panic with no `# Panics` section |
