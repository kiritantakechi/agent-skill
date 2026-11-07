# Testing

Scope: what a test asserts, where tests live and what they touch, how tests are shaped and
parametrised, regression, generated-input and snapshot tests, and testing what is concurrent or
random. Running the tests in continuous integration is the build chapter's.

## Contents

- **Where tests live and what they touch**
  - AS-TEST-01 [M] Keep a unit test beside the code it tests
  - AS-TEST-02 [M] Give a test its own scratch directory, never a fixed path
- **What a test asserts**
  - AS-TEST-03 [M] Test behaviour, not implementation
  - AS-TEST-04 [M] Assert one claim per test
  - AS-TEST-05 [M] Name a test for the claim it makes
  - AS-TEST-06 [M] Assert on the value, so a failure shows both sides
  - AS-TEST-07 [M] Assert which failure occurred, never its wording
  - AS-TEST-08 [M] Test the boundaries and the invalid input, not only the happy path
- **Shaping and parametrising tests**
  - AS-TEST-09 [S] Arrange, act, assert, with a blank line between the phases
  - AS-TEST-10 [S] Drive a family of similar cases from one table
- **Bugs, generated input and recorded output**
  - AS-TEST-11 [M] Give every bug fix a test that failed before it
  - AS-TEST-12 [S] Test a fast implementation against a simple reference over generated input
  - AS-TEST-13 [M] Pin every failing input a generator finds as a fixed test
  - AS-TEST-14 [S] Snapshot large, exact output, and review every change to it

---

## Where tests live and what they touch

### AS-TEST-01 [M] Keep a unit test beside the code it tests

A test of one unit's internals lives with that unit, so that a change to the code and to its test
appear in one diff and neither is left behind. Tests of the public contract live apart from the
code, in a place that sees only what a user sees.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | | absent | | Python keeps no test-only code inside the module under test, so its tests are modules of their own and there is no in-file unit test to place |
| rust-style | RS-TEST-04 | realises | [M] | |
| zig-style | ZS-TEST-01 | realises | [M] | |

### AS-TEST-02 [M] Give a test its own scratch directory, never a fixed path

A test that touches the filesystem works in a directory made for it and removed afterwards, even
when the test fails. A fixed path collides with the tests that run beside it and with other jobs on
the same machine, and leaves debris behind.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-TEST-18 | extends | [M] | The fixture also isolates the environment variables and the working directory, which undo themselves the same way |
| rust-style | RS-TEST-17 | realises | [M] | |
| zig-style | ZS-TEST-09 | realises | [M] | |

## What a test asserts

### AS-TEST-03 [M] Test behaviour, not implementation

A test asserts what a caller of the public interface observes. A test that breaks when a private
helper is renamed, with no change in what the caller sees, taxes every refactor and passes while the
behaviour is wrong.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-TEST-05 | realises | [M] | |
| rust-style | RS-TEST-02 | realises | [M] | |
| zig-style | ZS-TEST-11 | realises | [M] | |

### AS-TEST-04 [M] Assert one claim per test

A test makes one claim about its subject. A test that asserts unrelated properties reports only that
something is wrong, and the first failure hides the rest.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-TEST-06 | realises | [M] | |
| rust-style | RS-TEST-03 | realises | [M] | |
| zig-style | ZS-TEST-12 | realises | [M] | |

### AS-TEST-05 [M] Name a test for the claim it makes

A test's name states what holds, so that a failure reported by name alone reads as the sentence that
stopped being true. A noun, a bare function name or a number says nothing about what broke.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-TEST-11 | realises | [M] | |
| rust-style | RS-TEST-07 | realises | [M] | |
| zig-style | ZS-TEST-03 | realises | [M] | |

### AS-TEST-06 [M] Assert on the value, so a failure shows both sides

A test compares the value produced with the value expected through a comparison that reports both
when they differ, and not through a derived property, a bare truth test or the shape of a call.
Asserting on how a collaborator was called verifies that the code is the code that was written, and
passes when the result is wrong.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-TEST-09 | realises | [M] | |
| rust-style | RS-TEST-11 | realises | [M] | |
| zig-style | ZS-TEST-07 | realises | [M] | |

### AS-TEST-07 [M] Assert which failure occurred, never its wording

A test of a failure path asserts which failure occurred, by its kind, and not merely that one did.
The kind is the contract a caller handles; the wording is presentation and changes with every
improvement to a message.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | `PT011` | decided | | A built-in exception class is shared by unrelated failures, so the lint requires a message pattern where the class alone cannot tell them apart |
| rust-style | RS-TEST-13 | realises | [M] | |
| zig-style | ZS-TEST-15 | realises | [M] | |

### AS-TEST-08 [M] Test the boundaries and the invalid input, not only the happy path

A test suite exercises the empty input, the exact limit, one past it, and each way the input can be
invalid. Bugs cluster where valid data becomes invalid, and a suite of valid input verifies the
optimistic path and never the rejection logic.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-TEST-12 | realises | [M] | |
| rust-style | RS-TEST-14 | realises | [M] | |
| zig-style | ZS-TEST-16 | realises | [M] | |

## Shaping and parametrising tests

### AS-TEST-09 [S] Arrange, act, assert, with a blank line between the phases

A test has three phases in order: the setup, the single call under test, and the assertions. The
shape makes the call under test findable at a glance and shows when a test is really two.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-TEST-07 | realises | [S] | |
| rust-style | RS-TEST-10 | realises | [S] | |
| zig-style | ZS-TEST-13 | realises | [S] | |

### AS-TEST-10 [S] Drive a family of similar cases from one table

Cases that differ only in their data are written as a table of inputs and expected results rather
than as copies. Copies drift, with one getting the fix while the others go on passing, and a missing
case is plain in a table and invisible among copies.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-TEST-14 | tightens | [M] | The runner reports each case of a table as a test of its own, with an id, so a table loses nothing against separate tests, where elsewhere a loop stops at its first failing row |
| rust-style | RS-TEST-15 | realises | [S] | |
| zig-style | ZS-TEST-14 | realises | [S] | |

## Bugs, generated input and recorded output

### AS-TEST-11 [M] Give every bug fix a test that failed before it

A bug fix is committed with a test that fails without the fix and passes with it, named for the
behaviour that was wrong. A bug that occurred once shows that its area is easy to get wrong, and the
test is the only thing that prevents its return; writing it first proves the bug was reproduced.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-TEST-13 | realises | [M] | |
| rust-style | RS-TEST-19 | realises | [M] | |
| zig-style | ZS-TEST-32 | realises | [M] | |

### AS-TEST-12 [S] Test a fast implementation against a simple reference over generated input

Where a parser, a matcher or a codec has a slow, obviously correct counterpart, the two run on the
same generated input and must agree. The simple version is the specification, which is a stronger
oracle than an expected value written by the author of the fast one.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-TEST-23 | realises | [S] | |
| rust-style | RS-TEST-21 | realises | [S] | |
| zig-style | ZS-TEST-21 | realises | [S] | |

### AS-TEST-13 [M] Pin every failing input a generator finds as a fixed test

An input that a generator or fuzzer finds failing is reduced and kept as a fixed test with the input
written out. A generator finds a failure by chance and may not find it again, so a fix without the
pinned input has a test that can pass by missing it.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-TEST-24 | realises | [M] | |
| rust-style | RS-TEST-22 | realises | [M] | |
| zig-style | ZS-TEST-25 | realises | [M] | |

### AS-TEST-14 [S] Snapshot large, exact output, and review every change to it

Output that is large, exact and readable by a person is compared with a stored expected value, so
that an intended change is a small diff to review. A snapshot accepted without reading turns the
test into a change log that cannot fail.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-TEST-25 | realises | [S] | |
| rust-style | RS-TEST-25 | realises | [S] | |
| zig-style | ZS-TEST-23 | realises | [S] | |
