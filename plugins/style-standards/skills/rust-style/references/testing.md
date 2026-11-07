# Testing: Layers, Assertions, Properties, Fuzzing, and Snapshots

Scope: the test suite — the unit, integration and doc test layers, what a test asserts and how it is
named, table-driven, property and differential testing, fuzzing, snapshots, end-to-end tests of a
CLI, and flaky tests. Testing concurrent code deterministically is the concurrency chapter's; Miri
and the sanitizers are the unsafe chapter's; `trybuild` for a macro is the macros chapter's.

A test suite is a specification that runs. Its job is to make the contract explicit, to fail loudly
when the contract breaks, and to say clearly what broke. Coverage percentage is a byproduct, not a
goal.

## Contents

- **Organization**
  - RS-TEST-01 [M] Keep all three layers: unit, integration, and doc tests
  - RS-TEST-02 [M] Test behaviour, not implementation
  - RS-TEST-03 [M] Assert one concept per test
  - RS-TEST-04 [M] Put unit tests in `#[cfg(test)] mod tests` at the bottom of the file
  - RS-TEST-05 [M] Put integration tests in `tests/`, one crate per file
  - RS-TEST-06 [M] Share integration helpers through `#[path]`, not a `mod.rs`
  - RS-TEST-07 [M] Name tests as sentences about behaviour
  - RS-TEST-08 [S] Group related tests in nested `mod` blocks
  - RS-TEST-09 [S] Keep fixtures small; generate large corpora from a seed

- **Writing good tests**
  - RS-TEST-10 [S] Arrange, act, assert — visibly
  - RS-TEST-11 [M] Assert on values, not on shapes
  - RS-TEST-12 [S] Give assertions context when the values are not self-explanatory
  - RS-TEST-13 [M] Match on the error variant, not its `Display` string
  - RS-TEST-14 [M] Test the boundaries, because they are enumerable
  - RS-TEST-15 [S] Use table-driven tests for families of similar cases
  - RS-TEST-16 [M] Keep tests deterministic and order-independent
  - RS-TEST-17 [M] Use `tempfile::TempDir`, never a fixed path
  - RS-TEST-18 [S] Test at the highest level that still gives a precise failure
  - RS-TEST-19 [M] Give every bug fix a regression test that failed before it

- **Property, fuzz, and snapshot testing**
  - RS-TEST-20 [S] Use property testing where a law holds over a domain
  - RS-TEST-21 [S] Reach for differential testing first for parsers, matchers, and codecs
  - RS-TEST-22 [M] Pin every shrunk counterexample as a fixed regression test
  - RS-TEST-23 [M] Fuzz anything that parses untrusted input
  - RS-TEST-24 [S] Run fuzz targets briefly per PR and long on a schedule
  - RS-TEST-25 [S] Use snapshot testing for large, exact, human-reviewable output
  - RS-TEST-26 [M] Review snapshot diffs; never `--accept` reflexively
  - RS-TEST-27 [M] Normalize timestamps, paths, hashes, and map order before snapshotting
  - RS-TEST-28 [M] Test a CLI binary end to end, including its exit code

- **Doc tests, CI, and hygiene**
  - RS-TEST-29 [M] Use `no_run` for examples that must not execute, and `ignore` almost never
  - RS-TEST-30 [S] Use `compile_fail` doc tests to prove misuse is rejected
  - RS-TEST-31 [M] Fix a flaky test as a bug, or quarantine it with an owner and a date
  - RS-TEST-32 [S] Keep the fast suite fast, and split the slow cases behind `#[ignore]`
  - RS-TEST-33 [S] Measure coverage to find untested branches, not to hit a number
  - RS-TEST-34 [S] Delete tests that no longer test anything

- Decided by tools

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

A test that breaks when you rename a private helper, without any change in observable behaviour, is
a tax on refactoring rather than a safety net.

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

Unit tests live in `#[cfg(test)] mod tests` at the bottom of the file they test, with
`use super::*;`. Proximity is what keeps them updated, and they can reach private items.

**Why:** a test in the same file is visible in the same diff as the change, so it gets updated. A
test in a distant directory does not, and that is how suites rot. The child module also has access
to private items, which is what makes unit testing possible at all.

**Check:** for each module with non-trivial logic, is there a `mod tests`? Clippy's
`items_after_test_module` holds it at the bottom, where RS-MOD-40's file order puts it.

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

### RS-TEST-06 [M] Share integration helpers through `#[path]`, not a `mod.rs`

Put shared test code in a subdirectory of `tests/` and pull it in with
`#[path = "support/fixtures.rs"] mod fixtures;`, or promote it to a `test-support` workspace crate
once several suites need it or it gains dependencies or tests of its own.

**Why:** Cargo compiles every *top-level* file in `tests/` as its own test binary, so
`tests/helpers.rs` becomes a test crate with no tests. A subdirectory escapes that, and `#[path]`
reaches into it without the `mod.rs` filename this standard rejects (clippy `mod_module_files`).

**Check:** `ls tests/*.rs` — every file listed must contain at least one `#[test]`. Helper-only
files belong in a subdirectory reached by `#[path]`.

### RS-TEST-07 [M] Name tests as sentences about behaviour

`returns_none_for_empty_input`, `preserves_order_of_equal_keys`, `errors_when_depth_exceeds_limit`.
Do not prefix with `test_` (clippy `redundant_test_prefix`), and do not number them.

**Why:** the name is what you read in the failure output, often months later and without context. A
name that states the expected behaviour turns a failure line into a diagnosis; `test_parse_2` turns
it into an investigation.

**Check:** read the test names alone. They should form a readable specification of the module. A
`test_` prefix is the `redundant_test_prefix` row.

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

### RS-TEST-08 [S] Group related tests in nested `mod` blocks

Inside the tests module, `mod parsing { … }` and `mod rendering { … }` let `cargo test parsing`
select a coherent subset.

**Why:** the module path becomes the filter, so grouping gives you a fast inner loop on the area you
are working in. It also gives the suite a visible structure once it passes a few dozen tests.

**Check:** does `cargo test <area>` select something meaningful? If every name has to be typed in
full, there is no grouping.

### RS-TEST-09 [S] Keep fixtures small; generate large corpora from a seed

Keep test fixtures small and checked in; generate large corpora deterministically from a seed rather
than committing megabytes. A fixture nobody can regenerate is a fixture nobody will update.

**Why:** a large binary fixture bloats every clone forever, and once its provenance is forgotten
nobody dares change it. A generator plus a seed is smaller, reproducible, and can be adjusted when
the format changes.

**Check:** is any fixture large enough that a reviewer cannot read it? If so, can it be generated?

## Writing good tests

### RS-TEST-10 [S] Arrange, act, assert — visibly

A blank line between the three phases makes a test skimmable, and makes it obvious when a "test" is
actually three tests.

**Why:** the structure is already there; the blank lines just make it legible. The diagnostic
benefit is that a test with three "act" phases becomes visually obvious, which is RS-TEST-03
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

### RS-TEST-11 [M] Assert on values, not on shapes

`assert_eq!(result, vec!["a", "b"])` beats `assert!(result.len() == 2 && result[0] == "a")`: the
failure message shows both sides.

**Why:** `assert!` on a boolean prints only "assertion failed", discarding everything you needed.
`assert_eq!` prints both values, which is usually enough to diagnose without rerunning under a
debugger.

**Check:** does an `assert!(` contain `==`, `.len()`, or `&&`? Each is usually an `assert_eq!` that
would print more. Clippy's `manual_assert_eq` and `assert_is_empty` (pedantic) already flag an
assertion that is a single comparison or a single emptiness test.

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

### RS-TEST-12 [S] Give assertions context when the values are not self-explanatory

`assert_eq!(got, want, "pattern {pattern:?} over input {input:?}")`. A bare `assert!(x)` failure
tells you nothing.

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

### RS-TEST-13 [M] Match on the error variant, not its `Display` string

Test the error path as carefully as the success path. Match on the error variant, not on its
`Display` string — the string is allowed to change, the variant is the contract. Use
`assert_matches!`, which prints the actual value on failure; it is not in the prelude, so import it
with `use std::assert_matches;`.

**Why:** the message is presentation and may be reworded, translated, or given more context at any
time; the variant is the part semver protects. Asserting on the string couples the suite to prose
and breaks on improvements.

**Check:** does a test assert on `err.to_string()` or `format!("{e}")`? Each should be an
`assert_matches!` on the variant.

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
    use std::assert_matches;

    use super::{Error, compile};

    #[test]
    fn reports_the_offset_of_the_bad_byte() {
        assert_matches!(compile("ab?c"), Err(Error::Pattern { offset: 2 }));
    }
}
```

### RS-TEST-14 [M] Test the boundaries, because they are enumerable

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

### RS-TEST-15 [S] Use table-driven tests for families of similar cases

An array of `(input, expected)` and a loop, with the input echoed in the assertion message
(RS-TEST-12). This gets ten cases for the price of one and makes adding the eleventh trivial.

**Why:** when adding a case costs one line, cases get added. When it costs a whole function, they do
not — and the coverage of exactly the boundary conditions in RS-TEST-14 is what suffers.

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

### RS-TEST-16 [M] Keep tests deterministic and order-independent

Tests must be deterministic and order-independent. `cargo test` runs them in parallel on multiple
threads; anything relying on a shared directory, a fixed port, an environment variable, or the
current working directory will flake. Pass a test its environment through a lookup, as RS-CLI-30's
`read` takes one: `env::set_var` is `unsafe` in edition 2024, so `unsafe_code = "forbid"` rejects
it.

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

### RS-TEST-17 [M] Use `tempfile::TempDir`, never a fixed path

Use `tempfile::TempDir` for filesystem tests, never a fixed path under `/tmp` or the repository.
Cleanup happens on drop, including on failure.

**Why:** a fixed path collides between parallel tests and between concurrent CI jobs on the same
runner, and it leaves debris when a test fails. `TempDir` gives isolation and cleanup without any
teardown code.

**Check:** `rg -n -F '"/tmp/' -g '*.rs'` finds a fixed temporary path; each hit in a test is the
finding, and so is a path relative to the repository root.

### RS-TEST-18 [S] Test at the highest level that still gives a precise failure

An end-to-end test that fails with "output differs" is less useful than a unit test that fails with
"escaping of `\t` is wrong" — but you need both.

**Why:** high-level tests catch integration bugs but diagnose poorly; low-level tests diagnose well
but miss wiring. The rule picks the highest level that still names the fault, which maximizes
coverage per test without giving up diagnosis.

**Check:** when a test fails, does the name and message tell you where to look? If it says only
"output differs", a lower-level test is missing.

### RS-TEST-19 [M] Give every bug fix a regression test that failed before it

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

### RS-TEST-20 [S] Use property testing where a law holds over a domain

Use property testing (`proptest`, `quickcheck`) where a law holds over a domain: round-trips
(`parse(render(x)) == x`), invariants (a sorted output is sorted), and equivalences (the optimized
path agrees with the naive one, RS-TEST-21).

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

### RS-TEST-21 [S] Reach for differential testing first for parsers, matchers, and codecs

The differential-testing pattern — run a simple reference implementation and the fast one on the
same random input and compare — is the highest-yield property test for parsers, matchers, and
codecs. It is how `regex` and `regex-automata` are validated.

**Why:** for these domains the correct output is hard to state as a property but easy to compute
slowly. The naive implementation is the specification, and any disagreement is a bug in one of them
— which is a far stronger oracle than a hand-written expectation.

**Check:** does the fast path have a slow reference to disagree with? If the naive version was
deleted, the oracle went with it (RS-UNSAFE-10).

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

### RS-TEST-22 [M] Pin every shrunk counterexample as a fixed regression test

Shrinking is the point of property testing: when a case fails, report the minimal input, and add it
as a fixed regression test (RS-TEST-19).

**Why:** a 4KB random failing input is nearly undebuggable; the three-byte shrunk version usually
makes the bug obvious. Pinning it as a fixed test also means the property test does not have to
rediscover it by chance.

**Check:** for each historical property-test failure, is there now a deterministic test with the
minimal input?

### RS-TEST-23 [M] Fuzz anything that parses untrusted input

`cargo fuzz` with `libfuzzer`, or `afl`. Check the corpus into a separate repository or CI cache,
and add every crash as a unit test. A crash blocks the release; in a parser with `unsafe` it is
memory corruption whose trigger an attacker chooses.

**Why:** a parser on untrusted input is a security boundary, and fuzzing is the only technique that
explores it adversarially. Coverage-guided fuzzers find the malformed inputs that reach the paths no
test author thinks about.

**Check:** does every entry point that accepts external data have a fuzz target? And is the corpus
retained between runs, so progress accumulates?

### RS-TEST-24 [S] Run fuzz targets briefly per PR and long on a schedule

Run fuzz targets in CI for a bounded time on every pull request and for a long time on a schedule.
Five minutes per PR finds the shallow bugs that would otherwise reach users.

**Why:** fuzzing has no natural stopping point, so it has to be budgeted two ways: a short run that
gates changes without slowing review, and a long run that makes real progress. Only doing the long
one means regressions land and are found days later.

**Check:** are both jobs configured? A fuzzing setup that only runs manually is one nobody runs.

### RS-TEST-25 [S] Use snapshot testing for large, exact, human-reviewable output

Use snapshot testing (`insta`) for output that is large, exact, and human-reviewable: rendered
reports, error messages, generated code, CLI help text. It makes intentional changes a one-line
review.

**Why:** hand-writing an expected 60-line output is tedious enough that nobody does it, so that
output goes untested. A snapshot makes creating the assertion free and turns review into reading a
diff.

**Check:** is there any large output asserted with string concatenation? It wants a snapshot.

### RS-TEST-26 [M] Review snapshot diffs; never `--accept` reflexively

Review snapshot diffs; do not accept them reflexively. `cargo insta review` exists because
`--accept` on every change turns the snapshot suite into a change log rather than a test.

**Why:** the entire assertion in a snapshot test is the human decision that the new output is
correct. Accepting without reading removes the assertion and leaves a file that records whatever the
code happened to produce.

**Check:** does CI run with `--check` so unreviewed snapshots fail? A pipeline that accepts
automatically has no snapshot testing.

### RS-TEST-27 [M] Normalize timestamps, paths, hashes, and map order before snapshotting

Do not snapshot anything containing timestamps, paths, hashes, or iteration order of a `HashMap`.
Normalize those first, or the suite becomes a flake generator.

**Why:** each of these varies between runs and machines for reasons unrelated to correctness. A
snapshot containing them fails constantly, and the team learns to accept diffs without reading them
— which destroys RS-TEST-26.

**Check:** does a snapshot hold an absolute path, a date, or a hex digest? Each needs a redaction or
a sort.

### RS-TEST-28 [M] Test a CLI binary end to end, including its exit code

For CLI tools, test the binary end to end: run it with arguments in a temporary directory and assert
on stdout, stderr, and the exit code (`assert_cmd`, `trycmd`, or a hand-rolled harness as ripgrep
uses). This is the only layer that catches argument-parsing and exit-code regressions. Cover the
three cases nobody tests by hand: output to a pipe, stdin that is not a terminal, and a non-UTF-8
filename. A hand-rolled harness finds the binary through `CARGO_BIN_EXE_<name>`.

**Why:** argument parsing, stream routing, and exit codes exist only in the assembled binary, so no
unit test reaches them. They are also the surface scripts depend on, which makes regressions there
especially expensive.

**Check:** does any test assert on the exit code and on stderr? Asserting only on stdout misses half
the contract. And does any test use a non-UTF-8 filename?

## Doc tests, CI, and hygiene

### RS-TEST-29 [M] Use `no_run` for examples that must not execute, and `ignore` almost never

Use `no_run` for examples that must compile but should not execute (network calls, long
computations), and `ignore` almost never — an `ignore`d example is unverified documentation. Explain
any `ignore` in a comment.

**Why:** `no_run` still type-checks, so it catches the API drift that matters; `ignore` checks
nothing at all and is indistinguishable from a code block in a blog post. The distinction is the
difference between verified and decorative.

**Check:** is a doc-comment code block tagged `ignore`? Each needs a justification, and most should
be `no_run`.

### RS-TEST-30 [S] Use `compile_fail` doc tests to prove misuse is rejected

Use `compile_fail` doc tests to prove that misuse is rejected: a typestate that forbids
write-before-connect, a sealed trait, a lifetime that must not escape.

**Why:** these designs are valuable exactly because certain code does not compile, and nothing else
in the suite can assert that. A `compile_fail` test is the only kind that fails when a restriction
is accidentally relaxed.

**Check:** for each "this must not compile" claim in the docs, is there a test? Unpinned claims
drift.

### RS-TEST-31 [M] Fix a flaky test as a bug, or quarantine it with an owner and a date

Quarantining is a temporary measure with an owner and a deadline, not a resolution.

**Why:** flakiness destroys the suite's authority — once reruns are normal, real failures get rerun
too. A flaky test is also frequently reporting a real race that happens to be rare, so the flakiness
is the bug rather than a property of the test.

**Check:** is there a quarantine list? Every entry needs an owner and a date, or it is permanent.

### RS-TEST-32 [S] Keep the fast suite fast, and split the slow cases behind `#[ignore]`

Keep the fast suite fast. If `cargo test` takes more than a minute or two, split the slow cases
behind `#[ignore = "slow: run with --ignored"]` plus a nightly CI job that runs
`cargo test -- --ignored`, and say so in `CONTRIBUTING.md`. The reason string is required: clippy's
`ignore_without_reason` (pedantic) rejects a bare `#[ignore]`.

**Why:** a suite slower than the developer's patience stops being run before committing, which moves
every failure to CI and lengthens the feedback loop enormously. Speed is a feature of the suite.

**Check:** time `cargo test`. Past a couple of minutes, find the slow tests and move them.

### RS-TEST-33 [S] Measure coverage to find untested branches, not to hit a number

Measure coverage (`cargo llvm-cov`) to find untested branches, not to hit a number. Uncovered error
paths are the finding that matters; a coverage target invites tests that execute code without
asserting anything.

**Why:** coverage measures execution, not verification, so it is easy to raise without improving
anything. Used as a search tool it is genuinely useful — the uncovered error arms are usually real
gaps.

**Check:** look at the uncovered lines rather than the percentage. Uncovered `Err` arms are the list
worth working through.

### RS-TEST-34 [S] Delete tests that no longer test anything

A suite that everyone has learned to skim is worse than a smaller suite that everyone reads. The
commonest case tests the standard library, the compiler or a dependency — that `Vec::push` increases
length — and can never fail for a reason you can act on.

**Why:** every test costs runtime and attention forever. Tests that assert nothing, duplicate
another, or cover deleted behaviour spend that budget without paying it back, and they dilute the
signal from the ones that matter.

**Check:** for each test, name the line of *your* code that would have to be wrong for it to fail.
If there is none, delete it.

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

## Decided by tools

A tool settles these on its own; the shipped configuration enables each at the level shown.

| Tool | Lint | Level | Forbids |
|---|---|---|---|
| clippy | `should_panic_without_expect` | warn | `#[should_panic]` without `expected = "…"` — or return an `Err` instead — listed because a panic test names its message, the rule a revision demoted to it |
| clippy | `redundant_test_prefix` | warn | a `test_` prefix on a function `#[test]` already marks |
