# RS-TEST — Testing

A test suite is a specification that runs. Its job is to make the contract
explicit, to fail loudly when the contract breaks, and to say clearly what
broke. Coverage percentage is a byproduct, not a goal.
## Contents

- **Organization**
  - RS-TEST-01 [M] Keep all three layers: unit, integration, and doc tests
  - RS-TEST-02 [M] Test behaviour, not implementation
  - RS-TEST-03 [M] Assert one concept per test
  - RS-TEST-04 [M] Put unit tests in `#[cfg(test)] mod tests` at the bottom of the file
  - RS-TEST-05 [M] Put integration tests in `tests/`, one crate per file
  - RS-TEST-06 [M] Let integration tests use only the public API
  - RS-TEST-07 [M] Share integration helpers through `#[path]`, not a `mod.rs`
  - RS-TEST-08 [M] Name tests as sentences about behaviour
  - RS-TEST-09 [S] Group related tests in nested `mod` blocks
  - RS-TEST-10 [S] Keep fixtures small; generate large corpora from a seed

- **Writing good tests**
  - RS-TEST-11 [S] Arrange, act, assert — visibly
  - RS-TEST-12 [M] Assert on values, not on shapes
  - RS-TEST-13 [S] Give assertions context when the values are not self-explanatory
  - RS-TEST-14 [M] Match on the error variant, not its `Display` string
  - RS-TEST-15 [M] Test the boundaries, because they are enumerable
  - RS-TEST-16 [S] Use table-driven tests for families of similar cases
  - RS-TEST-17 [M] Always give `#[should_panic]` an `expected = "…"`
  - RS-TEST-18 [M] Keep tests deterministic and order-independent
  - RS-TEST-19 [M] Use `tempfile::TempDir`, never a fixed path
  - RS-TEST-20 [M] Do not test the standard library or your dependencies
  - RS-TEST-21 [S] Test at the highest level that still gives a precise failure
  - RS-TEST-22 [M] Give every bug fix a regression test that failed before it

- **Property, fuzz, and snapshot testing**
  - RS-TEST-23 [S] Use property testing where a law holds over a domain
  - RS-TEST-24 [S] Reach for differential testing first for parsers, matchers, and codecs
  - RS-TEST-25 [M] Treat the shrunk counterexample as the deliverable
  - RS-TEST-26 [M!] Fuzz anything that parses untrusted input
  - RS-TEST-27 [S] Run fuzz targets briefly per PR and long on a schedule
  - RS-TEST-28 [S] Use snapshot testing for large, exact, human-reviewable output
  - RS-TEST-29 [M] Review snapshot diffs; never `--accept` reflexively
  - RS-TEST-30 [M] Normalize timestamps, paths, hashes, and map order before snapshotting
  - RS-TEST-31 [M] Test a CLI binary end to end, including its exit code
  - RS-TEST-32 [S] Build benchmarks in CI even when you do not time them

- **Doc tests, CI, and hygiene**
  - RS-TEST-33 [M] Make every public item's example a passing doc test
  - RS-TEST-34 [M] Prefer `?` to `unwrap()` in doc tests
  - RS-TEST-35 [M] Use `no_run` for examples that must not execute, and `ignore` almost never
  - RS-TEST-36 [S] Use `compile_fail` doc tests to prove misuse is rejected
  - RS-TEST-37 [M] Run the whole feature matrix in CI
  - RS-TEST-38 [M!] Run Miri for `unsafe`, and `loom` or TSan for concurrency
  - RS-TEST-39 [M] Treat a flaky test as a bug of the same severity as the code
  - RS-TEST-40 [S] Keep the fast suite fast, and split the slow cases behind `#[ignore]`
  - RS-TEST-41 [S] Measure coverage to find untested branches, not to hit a number
  - RS-TEST-42 [S] Delete tests that no longer test anything

---

## Organization

### RS-TEST-01 [M] Keep all three layers: unit, integration, and doc tests

Unit tests verify internals; integration tests verify the public contract; doc tests verify that the
documentation is true. Each layer catches what the others cannot, and a healthy crate has all three.

**Why:** they fail for different reasons. A unit test catches a wrong algorithm, an integration test
catches an API that cannot actually be used from outside, and a doc test catches documentation that
stopped being true. Dropping a layer removes a whole class of detection, not just some redundancy.

**Check:** does the crate have `#[cfg(test)]` modules, a `tests/` directory, and examples in its doc
comments? A missing layer is a finding.

### RS-TEST-02 [M] Test behaviour, not implementation

Test behaviour, not implementation. A test that breaks when you rename a private helper, without any
change in observable behaviour, is a tax on refactoring rather than a safety net.

**Why:** the purpose of a suite is to let you change the inside safely. Tests coupled to the inside
invert that — they make refactoring expensive, which is exactly when you most want tests. They also
pass while the behaviour is wrong, because they assert on structure.

**Check:** rename a private function and reorganize a module. Any test that fails without a
behaviour change is coupled to the implementation.

```rust
// verified
/// The test names a behaviour, so renaming the private helper cannot break it.
#[must_use]
pub fn normalize(input: &str) -> String {
    input.trim().to_lowercase()
}

#[cfg(test)]
mod tests {
    use super::normalize;

    #[test]
    fn trims_and_lowercases() {
        assert_eq!(normalize("  Hello  "), "hello");
    }
}
```

### RS-TEST-03 [M] Assert one concept per test

One assertion concept per test. A test named `rejects_empty_pattern` should fail for exactly one
reason; a test that exercises seven behaviours tells you only that something is wrong.

**Why:** the value of a failing test is the diagnosis it hands you. A test with seven assertions
stops at the first, hides the other six, and names none of them — so you learn less than the test
knew.

**Check:** count assertions per test. Several unrelated ones, or a name containing "and", means it
is several tests.

```rust
// verified
/// One concept per test: each fails for exactly one reason.
#[must_use]
pub fn parse_pair(input: &str) -> Option<(&str, &str)> {
    input.split_once(':')
}

#[cfg(test)]
mod tests {
    use super::parse_pair;

    #[test]
    fn returns_none_without_a_separator() {
        assert_eq!(parse_pair("nope"), None);
    }

    #[test]
    fn splits_on_the_first_separator_only() {
        assert_eq!(parse_pair("a:b:c"), Some(("a", "b:c")));
    }
}
```

### RS-TEST-04 [M] Put unit tests in `#[cfg(test)] mod tests` at the bottom of the file

Unit tests live in `#[cfg(test)] mod tests` at the bottom of the file they test, with `use
super::*;`. Proximity is what keeps them updated, and they can reach private items.

**Why:** a test in the same file is visible in the same diff as the change, so it gets updated. A
test in a distant directory does not, and that is how suites rot. The child module also has access
to private items, which is what makes unit testing possible at all.

**Check:** for each module with non-trivial logic, is there a `mod tests` at the bottom?

```rust
// verified
/// Unit tests sit at the bottom of the file they test and can reach private items.
fn digits(input: &str) -> usize {
    input.chars().filter(char::is_ascii_digit).count()
}

#[cfg(test)]
mod tests {
    use super::digits;

    #[test]
    fn counts_only_digits() {
        assert_eq!(digits("a1b2c3"), 3);
    }
}
```

### RS-TEST-05 [M] Put integration tests in `tests/`, one crate per file

Integration tests live in `tests/`, each file a separate crate that links your library as an
external user would. This is the only place that proves your public API is actually usable.

**Why:** each file being its own crate is the point — it can only see what a real dependent sees. A
missing `pub`, an un-exported type, or a trait that is not in scope shows up here and nowhere else.

**Check:** is there at least one test in `tests/` exercising the primary use case exactly as the
README shows it?

### RS-TEST-06 [M] Let integration tests use only the public API

Integration tests may use only the public API. If a test needs a private item, either the item
should be public, or the test belongs in the unit layer — never add `pub` purely to satisfy `tests/`
(`RS-MOD-18`).

**Why:** widening visibility for a test permanently enlarges the API you must support, in exchange
for a test that could have lived one directory away. The forced choice is the useful part: it makes
you decide whether the item is genuinely part of the contract.

**Check:** grep for `pub` items with a comment mentioning tests, or `#[doc(hidden)] pub`. Each is
probably a unit test in the wrong place.

### RS-TEST-07 [M] Share integration helpers through `#[path]`, not a `mod.rs`

Put helpers in a subdirectory of `tests/` and pull them in with `#[path = "support/helpers.rs"]
mod helpers;`, or promote them to a `testutil` workspace crate once several suites need them.

**Why:** Cargo compiles every *top-level* file in `tests/` as its own test binary, so
`tests/helpers.rs` becomes a test crate with no tests — a wasted link and a `running 0 tests` line.
A subdirectory escapes that, and `#[path]` reaches into it without the `mod.rs` filename this
standard rejects everywhere else (`references/modules.md` RS-MOD-06). The `testutil` crate is the
better answer once the helpers have their own dependencies or their own tests.

**Check:** `ls tests/*.rs` — every file listed must contain at least one `#[test]`. Helper-only
files belong in a subdirectory reached by `#[path]`.

### RS-TEST-08 [M] Name tests as sentences about behaviour

Name tests as sentences about behaviour: `returns_none_for_empty_input`,
`preserves_order_of_equal_keys`, `errors_when_depth_exceeds_limit`. Do not prefix with `test_`, and
do not number them (`RS-NAME-36`).

**Why:** the name is what you read in the failure output, often months later and without context. A
name that states the expected behaviour turns a failure line into a diagnosis; `test_parse_2` turns
it into an investigation.

**Check:** read the test names alone. They should form a readable specification of the module.

```rust
// verified
/// Each name is a sentence about behaviour, readable in the failure output.
#[must_use]
pub fn first_word(line: &str) -> Option<&str> {
    line.split_whitespace().next()
}

#[cfg(test)]
mod tests {
    use super::first_word;

    #[test]
    fn returns_none_for_empty_input() {
        assert_eq!(first_word("   "), None);
    }

    #[test]
    fn returns_the_leading_token() {
        assert_eq!(first_word("alpha beta"), Some("alpha"));
    }
}
```

### RS-TEST-09 [S] Group related tests in nested `mod` blocks

Group related tests in nested `mod` blocks inside the tests module (`mod parsing { … }`,
`mod rendering { … }`) so `cargo test parsing` selects a coherent subset.

**Why:** the module path becomes the filter, so grouping gives you a fast inner loop on the area you
are working in. It also gives the suite a visible structure once it passes a few dozen tests.

**Check:** does `cargo test <area>` select something meaningful? If every name has to be typed in
full, there is no grouping.

### RS-TEST-10 [S] Keep fixtures small; generate large corpora from a seed

Keep test fixtures small and checked in; generate large corpora deterministically from a seed rather
than committing megabytes. A fixture nobody can regenerate is a fixture nobody will update.

**Why:** a large binary fixture bloats every clone forever, and once its provenance is forgotten
nobody dares change it. A generator plus a seed is smaller, reproducible, and can be adjusted when
the format changes.

**Check:** is any fixture large enough that a reviewer cannot read it? If so, can it be generated?

## Writing good tests

### RS-TEST-11 [S] Arrange, act, assert — visibly

Arrange, act, assert — visibly. A blank line between the three phases makes a test skimmable, and
makes it obvious when a "test" is actually three tests.

**Why:** the structure is already there; the blank lines just make it legible. The diagnostic
benefit is that a test with three "act" phases becomes visually obvious, which is `RS-TEST-03`
enforced by layout.

**Check:** can you find the single line under test at a glance? If the act step is buried in setup,
the phases are not separated.

```rust
// verified
/// Arrange, act, assert — separated by blank lines so the phases are visible.
#[must_use]
pub fn dedup(values: &[u32]) -> Vec<u32> {
    let mut out: Vec<u32> = Vec::with_capacity(values.len());
    for &value in values {
        if !out.contains(&value) {
            out.push(value);
        }
    }
    out
}

#[cfg(test)]
mod tests {
    use super::dedup;

    #[test]
    fn keeps_the_first_occurrence_of_each_value() {
        let input = [3, 1, 3, 2, 1];

        let result = dedup(&input);

        assert_eq!(result, vec![3, 1, 2]);
    }
}
```

### RS-TEST-12 [M] Assert on values, not on shapes

Assert on values, not on shapes. `assert_eq!(result, vec!["a", "b"])` beats
`assert!(result.len() == 2 && result[0] == "a")`: the failure message shows both sides.

**Why:** `assert!` on a boolean prints only "assertion failed", discarding everything you needed.
`assert_eq!` prints both values, which is usually enough to diagnose without rerunning under a
debugger.

**Check:** grep for `assert!(` containing `==`, `.len()`, or `&&`. Each is usually an `assert_eq!`
that would print more.

```rust
// verified
/// `assert_eq!` prints both sides; `assert!(a == b)` prints neither.
#[must_use]
pub fn split_csv(line: &str) -> Vec<&str> {
    line.split(',').map(str::trim).collect()
}

#[cfg(test)]
mod tests {
    use super::split_csv;

    #[test]
    fn splits_and_trims_each_field() {
        assert_eq!(split_csv("a, b ,c"), vec!["a", "b", "c"]);
    }
}
```

### RS-TEST-13 [S] Give assertions context when the values are not self-explanatory

Give assertions context when the values are not self-explanatory: `assert_eq!(got, want, "pattern
{pattern:?} over input {input:?}")`. A bare `assert!(x)` failure tells you nothing.

**Why:** in a table-driven test the values alone do not identify which case failed. The message is
what turns "one of forty cases is wrong" into "case seven is wrong".

**Check:** for each assertion inside a loop, does the message identify the iteration?

```rust
// verified
/// The message names the case, so a table failure identifies itself.
#[must_use]
pub fn slug(input: &str) -> String {
    input.trim().replace(' ', "-").to_lowercase()
}

#[cfg(test)]
mod tests {
    use super::slug;

    #[test]
    fn slugifies_each_case() {
        for (input, want) in [(" Hello World ", "hello-world"), ("A B", "a-b")] {
            assert_eq!(slug(input), want, "input {input:?}");
        }
    }
}
```

### RS-TEST-14 [M] Match on the error variant, not its `Display` string

Test the error path as carefully as the success path. Match on the error variant, not on its
`Display` string — the string is allowed to change, the variant is the contract.

**Why:** the message is presentation and may be reworded, translated, or given more context at any
time; the variant is the part semver protects. Asserting on the string couples the suite to prose
and breaks on improvements.

**Check:** grep tests for `err.to_string()` and `format!("{e}")` in assertions. Each should be a
`matches!` on the variant.

```rust
// verified
/// Matching the variant, not its `Display` string, keeps the test stable across rewording.
#[derive(Debug, thiserror::Error, PartialEq, Eq)]
pub enum Error {
    #[error("invalid pattern at byte {offset}")]
    Pattern { offset: usize },
}

/// # Errors
/// Returns [`Error::Pattern`] when the input contains `?`.
pub fn compile(pattern: &str) -> Result<usize, Error> {
    match pattern.find('?') {
        Some(offset) => Err(Error::Pattern { offset }),
        None => Ok(pattern.len()),
    }
}

#[cfg(test)]
mod tests {
    use super::{Error, compile};

    #[test]
    fn reports_the_offset_of_the_bad_byte() {
        assert!(matches!(compile("ab?c"), Err(Error::Pattern { offset: 2 })));
    }
}
```

### RS-TEST-15 [M] Test the boundaries, because they are enumerable

Test boundaries: empty input, a single element, the exact capacity, one past the limit, maximum
values, invalid UTF-8 if bytes are accepted. Bugs live at the edges, and edges are enumerable.

**Why:** the interior of the input space is covered by any test; the edges are where off-by-one,
overflow, and empty-case bugs live. Unlike the interior, the edge set is finite and can be listed.

**Check:** for each function, list its boundaries and find a test for each. Empty and
one-past-the-end are the two most commonly missing.

```rust
// verified
/// The boundaries are finite, so they are enumerated rather than sampled.
#[must_use]
pub fn clamp_percent(value: i32) -> u8 {
    value.clamp(0, 100).try_into().unwrap_or(0)
}

#[cfg(test)]
mod tests {
    use super::clamp_percent;

    #[test]
    fn saturates_at_both_ends() {
        assert_eq!(clamp_percent(-1), 0);
        assert_eq!(clamp_percent(0), 0);
        assert_eq!(clamp_percent(100), 100);
        assert_eq!(clamp_percent(101), 100);
    }
}
```

### RS-TEST-16 [S] Use table-driven tests for families of similar cases

Use table-driven tests for families of similar cases: an array of `(input, expected)` and a loop,
with the input echoed in the assertion message. This gets ten cases for the price of one and makes
adding the eleventh trivial.

**Why:** when adding a case costs one line, cases get added. When it costs a whole function, they do
not — and the coverage of exactly the boundary conditions in `RS-TEST-15` is what suffers.

**Check:** are there several near-identical test functions differing only in literals? They want to
be a table.

```rust
// verified
/// Table-driven: adding the eleventh case costs one line.
#[must_use]
pub fn is_ident(input: &str) -> bool {
    let mut chars = input.chars();
    chars
        .next()
        .is_some_and(|c| c.is_ascii_alphabetic() || c == '_')
        && chars.all(|c| c.is_ascii_alphanumeric() || c == '_')
}

#[cfg(test)]
mod tests {
    use super::is_ident;

    #[test]
    fn classifies_each_case() {
        let cases = [("abc", true), ("_a1", true), ("1abc", false), ("", false)];
        for (input, want) in cases {
            assert_eq!(is_ident(input), want, "input {input:?}");
        }
    }
}
```

### RS-TEST-17 [M] Always give `#[should_panic]` an `expected = "…"`

`#[should_panic]` is a weak assertion — it passes if *any* panic occurs, including one from a typo
in the test setup. Always give it `expected = "…"`, and prefer testing a returned `Err` over a panic
entirely.

**Why:** a bare `#[should_panic]` passes when the test panics for the wrong reason, including an
`unwrap` in the setup, so it can pass while the behaviour under test is entirely broken. The
`expected` string is what makes it an actual assertion.

**Check:** grep for `#[should_panic]` with no `expected`. Each is a test that may be asserting
nothing.

```rust
// verified
/// `expected` is what turns `#[should_panic]` from a wish into an assertion.
#[must_use]
pub fn split_at_half(input: &str) -> (&str, &str) {
    let mid = input.len() / 2;
    input.split_at(mid)
}

#[cfg(test)]
mod tests {
    use super::split_at_half;

    #[test]
    #[should_panic(expected = "byte index")]
    fn panics_when_the_midpoint_is_not_a_char_boundary() {
        let _ = split_at_half("é");
    }
}
```

### RS-TEST-18 [M] Keep tests deterministic and order-independent

Tests must be deterministic and order-independent. `cargo test` runs them in parallel on multiple
threads; anything relying on a shared directory, a fixed port, an environment variable, or the
current working directory will flake.

**Why:** the default harness is multi-threaded, so shared mutable state is a race by construction. A
flaky test is worse than no test, because it trains everyone to rerun CI instead of reading
failures.

**Check:** run the suite repeatedly and with `--test-threads=1` and compare. Any difference is
shared state.

```rust
// verified
/// No shared directory, no fixed port, no environment: the test is order-independent.
#[must_use]
pub fn checksum(bytes: &[u8]) -> u32 {
    bytes
        .iter()
        .fold(0_u32, |acc, &b| acc.rotate_left(3) ^ u32::from(b))
}

#[cfg(test)]
mod tests {
    use super::checksum;

    #[test]
    fn is_a_pure_function_of_its_input() {
        assert_eq!(checksum(b"abc"), checksum(b"abc"));
    }
}
```

### RS-TEST-19 [M] Use `tempfile::TempDir`, never a fixed path

Use `tempfile::TempDir` for filesystem tests, never a fixed path under `/tmp` or the repository.
Cleanup happens on drop, including on failure.

**Why:** a fixed path collides between parallel tests and between concurrent CI jobs on the same
runner, and it leaves debris when a test fails. `TempDir` gives isolation and cleanup without any
teardown code.

**Check:** grep tests for `/tmp/` and for paths relative to the repository root.

### RS-TEST-20 [M] Do not test the standard library or your dependencies

Do not test the standard library, the compiler, or your dependencies. A test that asserts
`Vec::push` increases length is noise in every future test run.

**Why:** those tests can never fail for a reason you can act on, so they cost runtime and reading
attention forever while providing no signal. They also give a misleading impression of coverage.

**Check:** for each test, ask which line of *your* code would have to be wrong for it to fail. If
there is none, delete it.

```rust
// verified
/// The test exercises this crate's logic, not `Vec`'s.
#[must_use]
pub fn merge_sorted(left: &[u32], right: &[u32]) -> Vec<u32> {
    let mut out = Vec::with_capacity(left.len() + right.len());
    out.extend_from_slice(left);
    out.extend_from_slice(right);
    out.sort_unstable();
    out
}

#[cfg(test)]
mod tests {
    use super::merge_sorted;

    #[test]
    fn interleaves_two_sorted_inputs() {
        assert_eq!(merge_sorted(&[1, 4], &[2, 3]), vec![1, 2, 3, 4]);
    }
}
```

### RS-TEST-21 [S] Test at the highest level that still gives a precise failure

Test at the highest level that still gives a precise failure. An end-to-end test that fails with
"output differs" is less useful than a unit test that fails with "escaping of `\t` is wrong" — but
you need both.

**Why:** high-level tests catch integration bugs but diagnose poorly; low-level tests diagnose well
but miss wiring. The rule picks the highest level that still names the fault, which maximizes
coverage per test without giving up diagnosis.

**Check:** when a test fails, does the name and message tell you where to look? If it says only
"output differs", a lower-level test is missing.

### RS-TEST-22 [M] Give every bug fix a regression test that failed before it

Every bug fix gets a regression test that fails before the fix and passes after, named for the
behaviour, with the issue number in a comment. This is the highest-value test you will ever write.

**Why:** a bug that occurred once is evidence that this area is easy to get wrong, so it is where
recurrence is most likely. Writing the test first also proves you have actually reproduced the bug
rather than changed something adjacent.

**Check:** revert the fix. The new test must fail. If it passes, it does not test the bug.

```rust
// verified
/// The regression test pins the exact input that was wrong before the fix.
#[must_use]
pub fn strip_bom(input: &str) -> &str {
    input.strip_prefix('\u{feff}').unwrap_or(input)
}

#[cfg(test)]
mod tests {
    use super::strip_bom;

    /// Regression: a leading BOM used to be counted as a content character (#412).
    #[test]
    fn removes_a_leading_byte_order_mark() {
        assert_eq!(strip_bom("\u{feff}name"), "name");
    }
}
```

## Property, fuzz, and snapshot testing

### RS-TEST-23 [S] Use property testing where a law holds over a domain

Use property testing (`proptest`, `quickcheck`) where a law holds over a domain: round-trips
(`parse(render(x)) == x`), invariants (a sorted output is sorted), and equivalences (the optimized
path agrees with the naive one).

**Why:** example-based tests check the cases you thought of, which excludes the ones causing your
bugs. A property plus a generator explores the space you did not enumerate, and the failures it
finds are the ones you would never have written by hand.

**Check:** for each module, name a law that should hold for all inputs. If one exists and is
untested, that is the finding.

```rust
// verified
/// A law that holds over the whole domain: `decode(encode(x)) == x`.
#[must_use]
pub fn encode(value: u32) -> [u8; 4] {
    value.to_be_bytes()
}

#[must_use]
pub fn decode(bytes: [u8; 4]) -> u32 {
    u32::from_be_bytes(bytes)
}

#[cfg(test)]
mod tests {
    use super::{decode, encode};

    #[test]
    fn round_trips_every_sampled_value() {
        for value in (0..u32::MAX).step_by(0x0100_0000) {
            assert_eq!(decode(encode(value)), value);
        }
    }
}
```

### RS-TEST-24 [S] Reach for differential testing first for parsers, matchers, and codecs

The differential-testing pattern — run a simple reference implementation and the fast one on the
same random input and compare — is the highest-yield property test for parsers, matchers, and
codecs. It is how `regex` and `regex-automata` are validated.

**Why:** for these domains the correct output is hard to state as a property but easy to compute
slowly. The naive implementation is the specification, and any disagreement is a bug in one of them
— which is a far stronger oracle than a hand-written expectation.

**Check:** does the fast path have a slow reference to disagree with? If the naive version was
deleted, the oracle went with it (`RS-UNSAFE-10`).

```rust
// verified
/// Differential: the naive implementation is the oracle for the fast one.
#[must_use]
pub fn count_naive(haystack: &str, needle: char) -> usize {
    haystack.chars().filter(|&c| c == needle).count()
}

#[must_use]
pub fn count_fast(haystack: &str, needle: char) -> usize {
    haystack.matches(needle).count()
}

#[cfg(test)]
mod tests {
    use super::{count_fast, count_naive};

    #[test]
    fn both_implementations_agree() {
        for input in ["", "aaa", "abcabc", "  a  "] {
            assert_eq!(
                count_naive(input, 'a'),
                count_fast(input, 'a'),
                "input {input:?}"
            );
        }
    }
}
```

### RS-TEST-25 [M] Treat the shrunk counterexample as the deliverable

Shrinking is the point of property testing: when a case fails, report the minimal input, and add it
as a fixed regression test (`RS-TEST-22`).

**Why:** a 4KB random failing input is nearly undebuggable; the three-byte shrunk version usually
makes the bug obvious. Pinning it as a fixed test also means the property test does not have to
rediscover it by chance.

**Check:** for each historical property-test failure, is there now a deterministic test with the
minimal input?

### RS-TEST-26 [M!] Fuzz anything that parses untrusted input

Fuzz anything that parses untrusted input: `cargo fuzz` with `libfuzzer`, or `afl`. Check the corpus
into a separate repository or CI cache, and add every crash as a unit test.

**Why:** a parser on untrusted input is a security boundary, and fuzzing is the only technique that
explores it adversarially. Coverage-guided fuzzers find the malformed inputs that reach the paths no
test author thinks about.

**Check:** does every entry point that accepts external data have a fuzz target? And is the corpus
retained between runs, so progress accumulates?

*Relaxed form:* for a tool that only ever sees input you generate, a seeded property test over the
same grammar is enough. The rule binds the moment the input crosses a trust boundary.

### RS-TEST-27 [S] Run fuzz targets briefly per PR and long on a schedule

Run fuzz targets in CI for a bounded time on every pull request and for a long time on a schedule.
Five minutes per PR finds the shallow bugs that would otherwise reach users.

**Why:** fuzzing has no natural stopping point, so it has to be budgeted two ways: a short run that
gates changes without slowing review, and a long run that makes real progress. Only doing the long
one means regressions land and are found days later.

**Check:** are both jobs configured? A fuzzing setup that only runs manually is one nobody runs.

### RS-TEST-28 [S] Use snapshot testing for large, exact, human-reviewable output

Use snapshot testing (`insta`) for output that is large, exact, and human-reviewable: rendered
reports, error messages, generated code, CLI help text. It makes intentional changes a one-line
review.

**Why:** hand-writing an expected 60-line output is tedious enough that nobody does it, so that
output goes untested. A snapshot makes creating the assertion free and turns review into reading a
diff.

**Check:** is there any large output asserted with string concatenation? It wants a snapshot.

### RS-TEST-29 [M] Review snapshot diffs; never `--accept` reflexively

Review snapshot diffs; do not accept them reflexively. `cargo insta review` exists because
`--accept` on every change turns the snapshot suite into a change log rather than a test.

**Why:** the entire assertion in a snapshot test is the human decision that the new output is
correct. Accepting without reading removes the assertion and leaves a file that records whatever the
code happened to produce.

**Check:** does CI run with `--check` so unreviewed snapshots fail? A pipeline that accepts
automatically has no snapshot testing.

### RS-TEST-30 [M] Normalize timestamps, paths, hashes, and map order before snapshotting

Do not snapshot anything containing timestamps, paths, hashes, or iteration order of a `HashMap`.
Normalize those first, or the suite becomes a flake generator.

**Why:** each of these varies between runs and machines for reasons unrelated to correctness. A
snapshot containing them fails constantly, and the team learns to accept diffs without reading them
— which destroys `RS-TEST-29`.

**Check:** grep snapshots for absolute paths, dates, and hex digests. Each needs a redaction or a
sort.

### RS-TEST-31 [M] Test a CLI binary end to end, including its exit code

For CLI tools, test the binary end to end: run it with arguments in a temporary directory and assert
on stdout, stderr, and the exit code (`assert_cmd`, `trycmd`, or a hand-rolled harness as ripgrep
uses). This is the only layer that catches argument-parsing and exit-code regressions.

**Why:** argument parsing, stream routing, and exit codes exist only in the assembled binary, so no
unit test reaches them. They are also the surface scripts depend on, which makes regressions there
especially expensive.

**Check:** does any test assert on the exit code? Asserting only on stdout misses half the contract
(`RS-CLI-38`).

### RS-TEST-32 [S] Build benchmarks in CI even when you do not time them

Benchmarks are not tests, but a benchmark that fails to compile is still a broken build — build them
in CI even if you do not run them for timing (`RS-PERF-44`).

**Why:** benchmarks are excluded from a default `cargo test`, so they rot silently until the day you
need to measure something and first have to fix the harness. Compiling them is nearly free.

**Check:** does CI run `cargo build --benches` or `cargo test --benches --no-run`?

## Doc tests, CI, and hygiene

### RS-TEST-33 [M] Make every public item's example a passing doc test

Every public item's example is a doc test, and it must compile and pass. This is the cheapest
guarantee that the documentation is not lying (`RS-DOC-08`).

**Why:** doc tests are the only mechanism that ties prose to a compiler check. Without them,
documentation drifts from the API silently and the first person to notice is a user copying a broken
example.

**Check:** `cargo test --doc` passes and its count is close to the number of public items.

### RS-TEST-34 [M] Prefer `?` to `unwrap()` in doc tests

Prefer `?` in doc tests over `unwrap()`, using the `# fn main() -> Result<(), Box<dyn Error>> {`
hidden-line trick, so examples model the error handling you want users to copy.

**Why:** examples are copied verbatim into real programs (`RS-DOC-27`). An example full of
`unwrap()` teaches that error handling is optional, and the resulting panics land in your users'
production code.

**Check:** grep doc comments for `unwrap()`. Each needs the hidden `main` and a `?`.

### RS-TEST-35 [M] Use `no_run` for examples that must not execute, and `ignore` almost never

Use `no_run` for examples that must compile but should not execute (network calls, long
computations), and `ignore` almost never — an `ignore`d example is unverified documentation. Explain
any `ignore` in a comment.

**Why:** `no_run` still type-checks, so it catches the API drift that matters; `ignore` checks
nothing at all and is indistinguishable from a code block in a blog post. The distinction is the
difference between verified and decorative.

**Check:** grep doc comments for fenced blocks tagged `ignore`. Each needs a justification, and most
should be `no_run`.

### RS-TEST-36 [S] Use `compile_fail` doc tests to prove misuse is rejected

Use `compile_fail` doc tests to prove that misuse is rejected: a typestate that forbids
write-before-connect, a sealed trait, a lifetime that must not escape.

**Why:** these designs are valuable exactly because certain code does not compile, and nothing else
in the suite can assert that. A `compile_fail` test is the only kind that fails when a restriction
is accidentally relaxed.

**Check:** for each "this must not compile" claim in the docs, is there a test? Unpinned claims
drift.

### RS-TEST-37 [M] Run the whole feature matrix in CI

Run the whole matrix in CI: default features, `--all-features`, and `--no-default-features`. A
feature-gated `cfg` that nobody compiles is a feature-gated `cfg` that does not build
(`RS-BUILD-20`).

**Why:** feature combinations are compiled independently, so code behind a rarely-used flag is never
type-checked by a default build. The failure surfaces for the one user who enabled it.

**Check:** does the pipeline build all three configurations? `--all-features` alone hides the
`--no-default-features` breakage.

### RS-TEST-38 [M!] Run Miri for `unsafe`, and `loom` or TSan for concurrency

Run tests under Miri for any crate containing `unsafe`, and under ThreadSanitizer or `loom` for
concurrent data structures (`RS-UNSAFE-30`, `RS-CONC-45`).

**Why:** ordinary tests observe one compilation on one machine, and both UB and races are invisible
under that observation. These tools change what is being checked rather than adding more cases.

**Check:** does CI include the tool matching what the crate contains? A crate with `unsafe` and no
Miri job has an unverified soundness claim.

*Relaxed form:* run them before each release rather than on every push. For a crate with no `unsafe`
and no hand-rolled synchronization, the rule is vacuous.

### RS-TEST-39 [M] Treat a flaky test as a bug of the same severity as the code

Treat a flaky test as a bug of the same severity as the code it tests. Quarantining is a temporary
measure with an owner and a deadline, not a resolution.

**Why:** flakiness destroys the suite's authority — once reruns are normal, real failures get rerun
too. A flaky test is also frequently reporting a real race that happens to be rare, so the flakiness
is the bug rather than a property of the test.

**Check:** is there a quarantine list? Every entry needs an owner and a date, or it is permanent.

### RS-TEST-40 [S] Keep the fast suite fast, and split the slow cases behind `#[ignore]`

Keep the fast suite fast. If `cargo test` takes more than a minute or two, split the slow cases
behind `#[ignore]` plus a nightly CI job that runs `cargo test -- --ignored`, and say so in
`CONTRIBUTING.md`.

**Why:** a suite slower than the developer's patience stops being run before committing, which moves
every failure to CI and lengthens the feedback loop enormously. Speed is a feature of the suite.

**Check:** time `cargo test`. Past a couple of minutes, find the slow tests and move them.

### RS-TEST-41 [S] Measure coverage to find untested branches, not to hit a number

Measure coverage (`cargo llvm-cov`) to find untested branches, not to hit a number. Uncovered error
paths are the finding that matters; a coverage target invites tests that execute code without
asserting anything.

**Why:** coverage measures execution, not verification, so it is easy to raise without improving
anything. Used as a search tool it is genuinely useful — the uncovered error arms are usually real
gaps.

**Check:** look at the uncovered lines rather than the percentage. Uncovered `Err` arms are the list
worth working through.

### RS-TEST-42 [S] Delete tests that no longer test anything

Delete tests that no longer test anything. A suite that everyone has learned to skim is worse than a
smaller suite that everyone reads.

**Why:** every test costs runtime and attention forever. Tests that assert nothing, duplicate
another, or cover deleted behaviour spend that budget without paying it back, and they dilute the
signal from the ones that matter.

**Check:** for each test, name the change that would make it fail. If nothing plausible would,
delete it (`RS-TEST-20`).
