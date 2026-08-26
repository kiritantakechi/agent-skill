# Testing: Configuration, Shape, Fixtures, and Testing Concurrency

Scope: configuring pytest 9, what a test should assert and how it should be shaped, fixture
discipline, and the particular difficulty of testing code that runs in parallel. What to document
about a function is the documentation chapter; the interpreter and tool pins are the packaging
chapter.

Two sources are merged here: the **pytest 9 documentation**, which added a native TOML table, a
`strict` umbrella and subtests, and **Ruff's `PT` family**, thirty-one rules on pytest style. The
configuration half of this chapter is new in pytest 9 and most Python on the internet predates it.

Unless a block shows its own imports, it assumes `import pytest`.

## Contents

- **Configuration**
  - PS-TEST-01 [M] Configure pytest in the native `[tool.pytest]` table
  - PS-TEST-02 [M] Know the discovery order, and that an empty file wins
  - PS-TEST-03 [M] Turn on `strict`
  - PS-TEST-04 [M] Declare every marker
- **What a test asserts**
  - PS-TEST-05 [M] Test the behaviour, never the implementation
  - PS-TEST-06 [M] Assert one thing, and name the test after it
  - PS-TEST-07 [M] Arrange, act, assert — in that order, with blank lines between
  - PS-TEST-08 [M] Never put a branch or a loop in a test
  - PS-TEST-09 [M] Assert on values, not on the shape of a call
  - PS-TEST-10 [M] Make every test fail before you make it pass
- **Parametrisation**
  - PS-TEST-11 [M] Parametrise over cases rather than repeating a test
  - PS-TEST-12 [S] Use subtests when the cases are not a product
  - PS-TEST-13 [M] Give every parametrised case a readable id
- **Fixtures**
  - PS-TEST-14 [M] Use the narrowest fixture scope that works
  - PS-TEST-15 [M] Use `tmp_path` and `monkeypatch`, never the real filesystem or environment
  - PS-TEST-16 [M] Never let a fixture assert
  - PS-TEST-17 [S] Prefer a factory fixture to a fixture per variation
- **Failures and time**
  - PS-TEST-18 [M] Match the exception, not just its type
  - PS-TEST-19 [M] Never sleep in a test
  - PS-TEST-20 [M] Inject the clock rather than reading it
- **Concurrency**
  - PS-TEST-21 [M!] Assert an invariant, not merely that threads ran
  - PS-TEST-22 [M] Know that pytest itself is not thread-safe

---

## Configuration

### PS-TEST-01 [M] Configure pytest in the native `[tool.pytest]` table

`[tool.pytest]` in `pyproject.toml`, or a standalone `pytest.toml`. Not `[tool.pytest.ini_options]`.

**Why:** pytest 9 added a table that takes real TOML types — arrays, booleans, integers — where
the older one takes INI strings that each option parses itself. The two **cannot coexist**;
pytest errors out and names its preference in the message: *"Please use `[tool.pytest]` with
native TOML types (recommended)."* Migrating is mechanical, and the INI table exists now only for
backwards compatibility.

**Check:** `grep -rn 'tool.pytest.ini_options' .` — every hit is the legacy table.

```toml
# verified — GOOD
[tool.pytest]
testpaths = ["tests"]
strict = true
markers = ["slow: needs a real toolchain"]
```

### PS-TEST-02 [M] Know the discovery order, and that an empty file wins

`pytest.toml`, `.pytest.toml`, `pytest.ini`, `.pytest.ini`, `pyproject.toml`, `tox.ini`,
`setup.cfg` — first match wins, and configuration files are **never merged**.

**Why:** an empty `pytest.toml` in the repository root outranks a fully configured
`pyproject.toml` and discards it entirely. Your `testpaths`, your markers and your `strict`
setting all stop applying, and the tests still run — differently. pytest does say so, in the
session header: `configfile: pytest.toml (WARNING: ignoring pytest config in pyproject.toml!)`.
That is one line in a header nobody reads, which makes this a precedence trap rather than a
silent change, and worth a rule either way.

**Check:** `ls pytest.toml .pytest.toml pytest.ini .pytest.ini 2>/dev/null` alongside a configured
`pyproject.toml` — any of them existing is the finding. Confirm with the `configfile:` line in the
header, which names the file actually in force.

### PS-TEST-03 [M] Turn on `strict`

`strict = true`, which pytest 9 added as one switch for `strict_config`, `strict_markers`,
`strict_parametrization_ids` and `strict_xfail`.

**Why:** each of the four turns a silent tolerance into an error, and each tolerance hides a real
mistake: an unknown config key that does nothing, an undeclared marker that silently selects
nothing, duplicate parametrisation ids that quietly renumber, and an `xfail` that passes and is
ignored. All four are the kind of thing that works until it matters.

**Check:** the `strict` key in the configuration. Its absence is the finding.

### PS-TEST-04 [M] Declare every marker

`markers = ["slow: needs a real toolchain"]`, with a description.

**Why:** under `strict` an undeclared marker is an error rather than a typo that silently matches
nothing — which is the failure it prevents: `@pytest.mark.slwo` selects no tests and reports
success. The description is what makes `pytest --markers` a usable index.

**Check:** `pytest --markers` against every `@pytest.mark.` in the suite.

## What a test asserts

### PS-TEST-05 [M] Test the behaviour, never the implementation

Assert what the caller observes. Never assert that a private helper was called.

**Why:** a test coupled to the implementation fails on every refactor that changes nothing
observable, which trains everyone to update tests without reading them — and a test nobody reads
is a test that no longer checks anything. It also cannot catch the bug where the helper is called
correctly and the result is wrong.

**Check:** every assertion mentioning a private name, a call count, or a mock's internals.

### PS-TEST-06 [M] Assert one thing, and name the test after it

`test_rejects_a_port_above_the_range`, not `test_port`.

**Why:** when a test with six assertions fails, the name tells you nothing and the first failure
hides the rest. One behaviour per test means the name is the failure message, and the report
reads as a specification. The setup can be shared through a fixture; the assertion should not be.

**Check:** every test with assertions on unrelated properties, and every test whose name is a noun.

### PS-TEST-07 [M] Arrange, act, assert — in that order, with blank lines between

Three blocks. Setup, the single call under test, the assertions.

**Why:** the shape makes the call under test findable at a glance, which is the first thing a
reader of a failing test needs. Interleaving them hides which call is the subject, and it is how
a test ends up asserting on the arrangement rather than on the result.

**Check:** every test with more than one call to the system under test.

### PS-TEST-08 [M] Never put a branch or a loop in a test

No `if`, no `for`, no `try` around the assertion.

**Why:** logic in a test is untested logic, and it can make the test pass by skipping the
assertion — a `for` over an empty list asserts nothing and reports success. Loops over cases are
parametrisation; branches are two tests.

**Check:** `grep -rnE '^\s+(if|for|while) ' tests/` — every hit inside a test function is the
finding.

### PS-TEST-09 [M] Assert on values, not on the shape of a call

`assert result == expected`. Not `mock.assert_called_once_with(...)` as the only assertion.

**Why:** asserting the call verifies that you wrote the code you wrote. It passes when the
collaborator is called perfectly and returns the wrong thing, and it fails when you rename a
parameter. Where an effect genuinely is the behaviour — a message published, a row written —
assert the effect, not the call that caused it.

**Check:** every test whose assertions are all on mocks.

### PS-TEST-10 [M] Make every test fail before you make it pass

Break the code, watch the test fail, restore it.

**Why:** a test that has never failed is a test that might be asserting nothing, and there are many
ways to write one: an assertion in a skipped branch, a fixture that returns early, an `assert` on a
truthy object rather than a value. This is the only check that catches all of them, and it takes ten
seconds.

**Check:** the repository's own mutation check does this mechanically — delete a statement and see
whether any test notices.

## Parametrisation

### PS-TEST-11 [M] Parametrise over cases rather than repeating a test

`@pytest.mark.parametrize` with the cases as data.

**Why:** copies drift — one gets a fix and the others do not — and the copy that was not updated
goes on passing, which is worse than it failing. Parametrising makes the cases a table, which is
also the form in which a missing case is visible.

**Check:** ruff `PT006` and `PT007` for the argument shapes. Two tests differing only in literals
are the finding.

```python
# verified — GOOD
import pytest


def clamp(value: int, low: int, high: int) -> int:
    return max(low, min(value, high))


@pytest.mark.parametrize(
    ("value", "expected"),
    [(-5, 0), (0, 0), (5, 5), (15, 10)],
    ids=["below", "at-low", "inside", "above"],
)
def test_clamp(value: int, expected: int) -> None:
    assert clamp(value, 0, 10) == expected
```

### PS-TEST-12 [S] Use subtests when the cases are not a product

New in pytest 9. `with subtests.test(path=p):` inside one test, when the cases are discovered rather
than enumerated.

**Why:** `parametrize` needs the cases at collection time, so a check over every file in a directory
either becomes one test that stops at the first failure or a fixture that fakes parametrisation.
Subtests give you independent failures inside one test, which is the right shape for "assert this
property of everything I found".

**Check:** every test that loops over discovered items with one assertion inside — see PS-TEST-08.
That loop is what subtests replace.

### PS-TEST-13 [M] Give every parametrised case a readable id

`ids=[...]`, or parameters whose `repr` is already readable.

**Why:** without ids the report says `test_clamp[value3-expected3]`, which tells you nothing about
which case broke. With them it says `test_clamp[above]`. Under `strict` a duplicate id is an error
rather than a silent renumbering, which is the other half of this rule.

**Check:** run `pytest --collect-only -q` and read the generated ids. Any containing a bare index is
the finding.

## Fixtures

### PS-TEST-14 [M] Use the narrowest fixture scope that works

Function scope by default. Widen only when the setup is genuinely expensive, and say why.

**Why:** a session-scoped fixture is shared mutable state between tests, so one test can change
what another sees and the suite becomes order-dependent — which shows up as a failure that only
happens in CI. The narrow scope costs setup time and buys independence, and independence is what
makes a failure mean something.

**Check:** ruff `PT003` for the redundant explicit scope. Every non-function scope needs a comment.

### PS-TEST-15 [M] Use `tmp_path` and `monkeypatch`, never the real filesystem or environment

`tmp_path` for files, `monkeypatch.setenv` for the environment, `monkeypatch.chdir` for the
directory.

**Why:** both fixtures undo themselves, so a failing test cannot leave the next one in a strange
state. Writing to a real path or setting a real environment variable makes the suite order-dependent
and machine-dependent, and the failure appears somewhere other than the test that caused it.

**Check:** `grep -rnE 'os\.environ\[|open\(["\x27]/|Path\(["\x27]/' tests/` — every hit is the
finding.

### PS-TEST-16 [M] Never let a fixture assert

A fixture arranges. Assertions belong in the test.

**Why:** an assertion in a fixture reports as an error rather than a failure, and it attributes the
problem to every test that uses the fixture rather than to the thing that is wrong. If the setup can
fail meaningfully, that is a test of the setup.

**Check:** `grep -rnA10 '@pytest.fixture' tests/` for an `assert` in the body.

### PS-TEST-17 [S] Prefer a factory fixture to a fixture per variation

One fixture returning a callable, rather than `user`, `admin_user`, `locked_user`.

**Why:** the variations multiply, and each is a name the reader must learn. A factory keeps one name
and puts the variation at the call site where it is visible in the test that needs it.

**Check:** three or more fixtures differing only in their arguments.

## Failures and time

### PS-TEST-18 [M] Match the exception, not just its type

`pytest.raises(ValueError, match="out of range")`.

**Why:** `pytest.raises(ValueError)` passes on any `ValueError`, including one raised by a typo
in the test's own setup — so the test passes while testing nothing. The `match` argument pins
which failure you meant. Keep the block to the single call that should raise, for the same
reason.

**Check:** ruff `PT011` for a broad `raises` without `match`, and `PT012` for a `raises` block
containing more than one statement.

```python
# verified — GOOD
import pytest


def port(raw: str) -> int:
    number = int(raw)
    if not 1 <= number <= 65535:
        msg = f"port out of range: {number}"
        raise ValueError(msg)
    return number


def test_rejects_a_port_above_the_range() -> None:
    with pytest.raises(ValueError, match="out of range"):
        port("70000")
```

### PS-TEST-19 [M] Never sleep in a test

No `time.sleep` to wait for something. Poll with a deadline, or make the thing synchronous.

**Why:** a sleep is either too short — so the test is flaky on a loaded machine — or too long, so
the suite is slow, and usually both at different times. It is also the single largest contributor
to a suite that people stop running. Wait on the condition instead of on the clock.

**Check:** `grep -rn 'sleep(' tests/` — every hit is the finding.

### PS-TEST-20 [M] Inject the clock rather than reading it

Take `now: Callable[[], datetime]` as a parameter, or freeze it with `monkeypatch`.

**Why:** code that calls `datetime.now()` internally cannot be tested at a boundary — midnight, a
leap day, a timezone transition — without waiting for one. Injecting makes those cases ordinary
tests. It also removes a source of flakiness where a test straddles a second boundary.

**Check:** ruff `DTZ005` for a naive `datetime.now()`. `grep -rn 'datetime.now\|time.time' src/` for
the injection question.

## Concurrency

### PS-TEST-21 [M!] Assert an invariant, not merely that threads ran

The test must check a property that a race would break — a count, a sum, a set of unique values.

*Relaxed form:* a smoke test that merely runs the code under threads is worth having as a crash
check, provided it is named as one and is not the only concurrency test.

**Why:** running a racy function under eight threads and asserting it did not raise is a test
that passes on racy code. A demonstration of this is worth internalising: a test whose body raced
a shared dict passed under a parallel-test plugin until an assertion on the invariant was added,
at which point it reported tens of thousands of lost updates. The plugin supplies concurrency; it
does not supply an oracle.

**Check:** every test that starts threads. If deleting the assertion would not change the result,
the assertion is not an invariant.

```python
# verified — GOOD
import threading


def test_counter_loses_no_updates() -> None:
    lock = threading.Lock()
    count = 0

    def bump() -> None:
        nonlocal count
        for _ in range(1_000):
            with lock:
                count += 1

    threads = [threading.Thread(target=bump) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # The invariant, not "it did not raise": a race shows up as a shortfall.
    assert count == 4_000
```

### PS-TEST-22 [M] Know that pytest itself is not thread-safe

`capsys`, `monkeypatch` and `tmp_path` are not safe to use from several threads, and the maintainers
have said they do not intend to make pytest thread-safe.

**Why:** a parallel-test plugin runs your test body in several threads, which means the fixtures run
there too — so a test that uses `monkeypatch` under parallelism is testing the plugin's interaction
with pytest rather than your code. The plugins detect and skip the known-unsafe fixtures, which is
why the marker exists; code that needs those fixtures must be tested single-threaded.

**Check:** every test marked for parallel execution. A `capsys`, `monkeypatch` or `tmp_path` in its
signature is the finding.
