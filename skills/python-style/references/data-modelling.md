# Data Modelling: Dataclasses, Enums, Protocols, and Immutability

Scope: choosing the shape a value takes — dataclass, enum, protocol, `TypedDict`, `NamedTuple`,
plain class — and what each obliges you to. How to spell the annotation on a field is the typing
chapter; whether the value is safe to share is the free-threading chapter; what a constructor should
accept is the API chapter.

Two sources are merged here: the **empirical conventions of the CPython standard library**, whose
`dataclasses`, `enum` and `collections.abc` modules are the reference implementations of every shape
here, and **Ruff's `RUF`, `B`, `SLOT` and `PYI` families**, which decide the mechanical half. What
3.15 adds — `frozendict` and `sentinel` — is stated where it replaces something.

Unless a block shows its own imports, it assumes `from dataclasses import dataclass`.

## Contents

- **Choosing the shape**
  - PS-DATA-01 [M] Model a record as a frozen dataclass by default
  - PS-DATA-02 [M] Add `slots=True` unless something needs the instance dict
  - PS-DATA-03 [M] Model a closed set of alternatives as an enum
  - PS-DATA-04 [M] Use `StrEnum` or `IntEnum` only when the value crosses a boundary
  - PS-DATA-05 [S] Prefer a dataclass to a `NamedTuple` unless the value is genuinely a tuple
  - PS-DATA-06 [M] Use a `TypedDict` for a wire format, never for a domain object
  - PS-DATA-07 [M] Define an interface as a `Protocol`, not an ABC, unless you ship behaviour
- **Fields and defaults**
  - PS-DATA-08 [M] Never give a mutable default
  - PS-DATA-09 [M] Use `field(default_factory=...)` for a mutable default
  - PS-DATA-10 [M] Never compute a default at import time
  - PS-DATA-11 [M] Order fields so every default follows every required field
  - PS-DATA-12 [S] Make a field `KW_ONLY` when its meaning is not obvious positionally
- **Immutability**
  - PS-DATA-13 [M] Freeze anything that crosses a boundary
  - PS-DATA-14 [M] Replace rather than mutate, with `dataclasses.replace`
  - PS-DATA-15 [M] Use `frozendict` for an immutable mapping, and test `Mapping` not `dict`
  - PS-DATA-16 [S] Return a copy, or return something immutable
- **Validity**
  - PS-DATA-17 [M] Validate in `__post_init__`, and raise rather than correct
  - PS-DATA-18 [M!] Make the invalid state unrepresentable before validating against it
  - PS-DATA-19 [M] Give a domain value its own type rather than a bare `str` or `int`
  - PS-DATA-20 [M] Never let `__eq__` and `__hash__` disagree
- **Symmetry of a data type**
  - PS-DATA-21 [M] Give every serialiser its inverse
  - PS-DATA-22 [S] Keep sibling types structurally parallel

---

## Choosing the shape

### PS-DATA-01 [M] Model a record as a frozen dataclass by default

`@dataclass(frozen=True, slots=True)`. Reach for a mutable one, or a plain class, only when you can
say what it buys.

**Why:** the dataclass gives you `__init__`, `__repr__`, `__eq__` and a field list that tooling
can read, for one decorator. Freezing it removes the largest class of bug a record can have —
being changed by something you handed it to — and it makes the value hashable, so it can be a
dict key or live in a set without further thought. The cost is one call to `replace` where you
would have written an assignment, which is a smaller cost than it looks because it makes the
change visible at the call site.

**Check:** `grep -rn '@dataclass' src/` — every decorator without `frozen=True` needs a reason on
the line above it.

```python
# verified — GOOD
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Money:
    amount_cents: int
    currency: str


price = Money(amount_cents=1999, currency="GBP")
assert {price} == {Money(1999, "GBP")}  # hashable, so it works in a set
```

### PS-DATA-02 [M] Add `slots=True` unless something needs the instance dict

Anything assigning attributes dynamically, or using `functools.cached_property`, or being weak-
referenced by something that predates 3.11, needs the dict. Everything else does not.

**Why:** `slots=True` removes the per-instance `__dict__`, which is both smaller and faster to
access, and it turns a typo in an attribute name from a silently-created new attribute into an
`AttributeError` at the moment of the mistake. That second property is the one worth having. On the
free-threaded build the memory saving matters more than it used to, because object headers are
already larger there.

**Check:** ruff `SLOT000`–`SLOT002` for the subclass cases. For dataclasses,
`grep -rn '@dataclass' src/` and read for `slots=`.

### PS-DATA-03 [M] Model a closed set of alternatives as an enum

Not string constants, not a `Literal` union of strings, not integers with a comment.

**Why:** an enum gives the set a name, makes the members discoverable, gives each a readable `repr`
in a traceback, and — with PS-TYPE-17's `assert_never` — makes adding a member a type error at every
place that consumes it. A `Literal["read", "write"]` gets you the narrowing but not the name, the
repr, or the single place to add the third member.

**Check:** `grep -rnE '^[A-Z_]+\s*[:=]\s*["\x27]' src/` — a group of module-level string constants
that are only ever compared against each other is an enum.

### PS-DATA-04 [M] Use `StrEnum` or `IntEnum` only when the value crosses a boundary

A plain `Enum` inside your own code. `StrEnum` when the member must serialise as its value into
JSON, a URL, or a database column.

**Why:** the mixin classes make the member compare equal to its raw value, which is exactly what you
want at a boundary and exactly what you do not want inside — because it means `Kind.READ == "read"`
is true, so a typo'd string silently satisfies a comparison that should have failed. Reach for the
mixin at the edge, and convert at the edge.

**Check:** every `StrEnum`/`IntEnum`. If no serialisation crosses a process boundary, it should be a
plain `Enum`.

```python
# verified — GOOD
import enum
import json


class Status(enum.StrEnum):
    """`StrEnum` because these values go into JSON, and come back."""

    ACTIVE = "active"
    RETIRED = "retired"


assert json.dumps({"status": Status.ACTIVE}) == '{"status": "active"}'
assert Status("active") is Status.ACTIVE
```

### PS-DATA-05 [S] Prefer a dataclass to a `NamedTuple` unless the value is genuinely a tuple

A `NamedTuple` is right when the value has a natural order and callers legitimately unpack it —
coordinates, a version triple, the return of `divmod`.

**Why:** a `NamedTuple` is a tuple, so it is iterable, indexable, and compares equal to a plain
tuple of the same values. That is a feature for a coordinate and a hazard for a record: `if user
== (1, "a"):` type-checks and works, and nobody meant it to. It also cannot have a mutable
variant later without changing every unpacking call site.

**Check:** every `NamedTuple`. If no caller unpacks it and no caller indexes it, it wants to be a
frozen dataclass.

### PS-DATA-06 [M] Use a `TypedDict` for a wire format, never for a domain object

A `TypedDict` describes a `dict` that already exists — a parsed JSON body, a `**kwargs` bundle. It
does not describe a thing your code owns.

**Why:** a `TypedDict` is a `dict` at runtime, so it has no methods, no validation, no `repr`
worth reading, and no identity — and every access is a key lookup that can `KeyError`. Those are
acceptable properties for the five lines between `json.loads` and constructing the real object,
and unacceptable for anything that lives longer. Parse at the boundary into a dataclass; do not
carry the dict inward.

**Check:** every `TypedDict`. If an instance is passed to more than one function, it should have
been a dataclass by then.

### PS-DATA-07 [M] Define an interface as a `Protocol`, not an ABC, unless you ship behaviour

`class Reader(Protocol)` when you need a shape. An ABC when you have concrete methods subclasses
inherit.

**Why:** a protocol is structural, so a caller may satisfy it with a type they already have and
neither party needs to import the other — which is what makes it usable across a package boundary.
An ABC requires the implementer to inherit, so it couples them to you and forbids satisfying two
interfaces whose bases conflict. Use the ABC when the inheritance buys something real: shared
implementation.

**Check:** every ABC with no concrete method is a protocol written the coupling way.

```python
# verified — GOOD
from typing import Protocol


class Sink(Protocol):
    """Structural: a caller satisfies this without importing it."""

    def write(self, line: str) -> None: ...


class Collector:
    def __init__(self) -> None:
        self.lines: list[str] = []

    def write(self, line: str) -> None:
        self.lines.append(line)


def emit(sink: Sink, lines: list[str]) -> None:
    for line in lines:
        sink.write(line)


collector = Collector()
emit(collector, ["a", "b"])
assert collector.lines == ["a", "b"]
```

## Fields and defaults

### PS-DATA-08 [M] Never give a mutable default

`def f(items: list[int] = [])` and `field(default=[])` are the same bug.

**Why:** the default is evaluated once, at definition time, and shared by every call that does not
supply one — so a caller mutating it changes the default for every future caller. This is Python's
oldest sharp edge and it is still sharp. Under free threading it is worse: the shared default is
shared across threads too, so the mutation races as well as leaking.

**Check:** ruff `B006` for the argument form and `RUF008`/`RUF009` for the dataclass forms. All
three are enabled.

### PS-DATA-09 [M] Use `field(default_factory=...)` for a mutable default

`field(default_factory=list)`, `field(default_factory=dict)`.

**Why:** the factory runs per instance, which is what "each object gets its own empty list"
requires. `dataclasses` refuses a bare mutable default outright, which is the library enforcing
PS-DATA-08 for you — but only for the types it recognises as unhashable, so a custom mutable
class slips through.

**Check:** every `field(` call. A `default=` holding anything a caller can mutate is the finding.

```python
# verified — GOOD
from dataclasses import dataclass, field


@dataclass(slots=True)
class Batch:
    name: str
    items: list[int] = field(default_factory=list)


first, second = Batch("a"), Batch("b")
first.items.append(1)
assert second.items == []  # not shared
```

### PS-DATA-10 [M] Never compute a default at import time

`created_at: datetime = datetime.now()` freezes one timestamp into the class. So does reading an
environment variable, or a file, or a random seed.

**Why:** the value is captured when the module is imported, which is a moment nobody chose and which
PEP 810's lazy imports make genuinely unpredictable. Every instance then shares one stale value. The
factory form defers it to construction, which is when the caller meant it.

**Check:** `grep -rnE 'field\(default=|=\s*[a-z_]+\.[a-z_]+\(\)' src/` inside class bodies — a call
in a default is the finding unless it is `default_factory`.

### PS-DATA-11 [M] Order fields so every default follows every required field

Or make the defaulted ones keyword-only with `KW_ONLY`.

**Why:** `dataclasses` raises `TypeError` at class-definition time otherwise, so this rule is mostly
the language's. What it does not do for you is the *design* consequence: a field acquiring a default
must move, and moving it silently changes the meaning of every positional call. Making the defaulted
fields keyword-only removes that coupling permanently.

**Check:** every dataclass with more than three fields, and every one whose defaults are
interleaved.

### PS-DATA-12 [S] Make a field `KW_ONLY` when its meaning is not obvious positionally

`Rect(width=3, height=4)` reads; `Rect(3, 4)` does not say which is which.

**Why:** two adjacent parameters of the same type are a call site waiting to be transposed, and
the transposition type-checks. Keyword-only removes the possibility rather than documenting
against it. This is `[S]` because a two-field value with an obvious order — a coordinate —
genuinely reads better positionally.

**Check:** any two adjacent fields of the same type without `KW_ONLY` above them.

```python
# verified — GOOD
from dataclasses import KW_ONLY, dataclass


@dataclass(frozen=True, slots=True)
class Rect:
    _: KW_ONLY
    width_px: int
    height_px: int


assert Rect(width_px=3, height_px=4).width_px == 3
```

## Immutability

### PS-DATA-13 [M] Freeze anything that crosses a boundary

Anything returned from a public function, stored in a cache, used as a dict key, or handed to a
thread.

**Why:** once a value leaves your module you no longer know who holds a reference, so mutating it is
an effect at a distance with no call site to read. Freezing converts the whole question into a
`FrozenInstanceError` at the moment someone tries. For a threaded caller it is stronger still: an
immutable value needs no lock at all.

**Check:** every public return type. A mutable dataclass, `list`, `dict` or `set` is the finding
unless the docstring transfers ownership explicitly.

### PS-DATA-14 [M] Replace rather than mutate, with `dataclasses.replace`

`updated = replace(original, status=Status.RETIRED)`.

**Why:** `replace` keeps the type, runs `__post_init__` so the new value is validated like any
other, and produces a new object rather than making the old one's history unknowable.
Hand-writing the constructor call instead is the same thing minus the validation and plus a
maintenance burden every time a field is added.

**Check:** `grep -rn 'replace(' src/` should be roughly as common as frozen dataclasses are. Their
absence, alongside frozen types, means someone is rebuilding by hand.

### PS-DATA-15 [M] Use `frozendict` for an immutable mapping, and test `Mapping` not `dict`

`frozendict` for the value. `isinstance(x, collections.abc.Mapping)` for the check.

**Why:** new in 3.15, and it replaces `types.MappingProxyType`, which was a *view* — it forbade
writing through the proxy while the underlying dict stayed mutable, so it never actually made
anything immutable. The trap is that `frozendict` is **not a `dict` subclass**; it inherits directly
from `object`. So every `isinstance(x, dict)` in the codebase is now potentially wrong. The standard
library was updated for this; third-party code was not.

**Check:** `grep -rn 'isinstance(.*, dict)' src/` — every hit is a place a `frozendict` would fail
the test. `grep -rn 'MappingProxyType' src/` finds the spelling it replaces.

```python
# verified — GOOD
from collections.abc import Mapping

DEFAULTS = frozendict({"retries": 3, "timeout_ms": 500})

assert isinstance(DEFAULTS, Mapping)
assert not isinstance(DEFAULTS, dict)  # the trap: it is not a dict subclass
assert DEFAULTS["retries"] == 3
```

### PS-DATA-16 [S] Return a copy, or return something immutable

`return tuple(self._items)` or `return list(self._items)`. Never `return self._items`.

**Why:** returning the internal container hands the caller a live handle on your state, so a
caller appending to what they were given mutates you — usually much later, and from a call site
that reads as read-only. Returning a copy costs an allocation; returning a tuple costs one too
and also says the result is not meant to be edited.

**Check:** every method returning a container held on `self`. A bare `return self._x` is the
finding.

## Validity

### PS-DATA-17 [M] Validate in `__post_init__`, and raise rather than correct

Raise `ValueError`. Do not clamp, coerce, or substitute a default.

**Why:** `__post_init__` runs for every construction path including `replace`, so it is the one
place that cannot be bypassed. Correcting instead of raising hides the caller's bug and produces
a value nobody asked for — and the caller then reasons about the value they passed rather than
the one they got. Raise at the boundary; the traceback names the construction site.

**Check:** every dataclass with a field whose valid range is narrower than its type. No
`__post_init__` is the finding.

```python
# verified — GOOD
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Port:
    number: int

    def __post_init__(self) -> None:
        if not 1 <= self.number <= 65535:
            msg = f"port out of range: {self.number}"
            raise ValueError(msg)


assert Port(8080).number == 8080
try:
    Port(0)
except ValueError as exc:
    assert "out of range" in str(exc)
```

### PS-DATA-18 [M!] Make the invalid state unrepresentable before validating against it

An enum instead of a validated string. A `Port` type instead of an `int` you check. Two types
instead of one type with a flag that says which it is.

*Relaxed form:* application code at a boundary may validate a primitive rather than introduce a
type, provided the validation happens exactly once and the validated value is not passed on as
the primitive.

**Why:** validation is a check that must be repeated at every construction site and can be forgotten
at any of them; a type is a check the compiler performs everywhere for free. The design question is
the second of this standard's five: what can be made unrepresentable? Every state you remove is a
branch you never write and a test you never need.

**Check:** every `if not valid: raise` in the codebase. Ask what type would make the check
unnecessary.

### PS-DATA-19 [M] Give a domain value its own type rather than a bare `str` or `int`

`UserId`, `Email`, `Cents` — a `NewType` at minimum, a frozen dataclass where there is behaviour.

**Why:** `def transfer(from_: str, to: str, amount: int)` has three parameters and six ways to
call it wrongly, all of which type-check. With distinct types, the transposition is a type error.
`NewType` costs nothing at runtime — it is the identity function — and buys the whole class of
confusion.

**Check:** any signature with two adjacent parameters of the same primitive type.

```python
# verified — GOOD
from typing import NewType

UserId = NewType("UserId", int)
Cents = NewType("Cents", int)


def credit(user: UserId, amount: Cents) -> str:
    return f"{user}:{amount}"


# Transposing these is now a type error rather than a silent bug.
assert credit(UserId(7), Cents(250)) == "7:250"
```

### PS-DATA-20 [M] Never let `__eq__` and `__hash__` disagree

If two objects are equal they must hash equal. A mutable object that defines `__eq__` must not
define `__hash__`.

**Why:** a dict and a set both find a key by hash first and equality second, so a pair that is equal
with different hashes lands in different buckets and the lookup silently misses. `dataclass` gets
this right for you — `eq=True` without `frozen=True` sets `__hash__` to `None`, which makes the type
unhashable rather than subtly broken. Hand-written `__eq__` is where it goes wrong.

**Check:** `grep -rn 'def __eq__' src/` — every hit needs a matching `__hash__` or a documented
reason the type is unhashable.

## Symmetry of a data type

### PS-DATA-21 [M] Give every serialiser its inverse

If `to_json` exists, `from_json` exists. If `__str__` is meant to round-trip, something parses it.

**Why:** a one-way conversion is a value you can produce and never recover, and its absence is
invisible — nobody notices a missing `from_json` until they need it, at which point the format has
already shipped. Writing the pair together also tests the format: a round-trip assertion is the
cheapest schema check there is.

**Check:** every `to_*` and `__str__` on a data type. A missing inverse is either deliberate —
say so in the docstring — or the finding.

```python
# verified — GOOD
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Point:
    x: int
    y: int

    def to_dict(self) -> dict[str, int]:
        # Not `asdict`: it returns `dict[str, Any]`, and laundering `Any` into an
        # annotated return is what PS-TYPE-15 exists to stop.
        return {"x": self.x, "y": self.y}

    @classmethod
    def from_dict(cls, raw: dict[str, int]) -> Point:
        return cls(x=raw["x"], y=raw["y"])


original = Point(1, 2)
assert Point.from_dict(original.to_dict()) == original
```

### PS-DATA-22 [S] Keep sibling types structurally parallel

If `Request` is a frozen slotted dataclass with `to_dict`/`from_dict`, so is `Response`.

**Why:** a reader who has learned one should be able to use the other without checking. Divergence
between siblings is also where the asymmetry of PS-DATA-21 usually starts: one of the pair gets the
inverse and the other does not.

**Check:** list the sibling types and their public members side by side. A gap is either deliberate
or the finding.
