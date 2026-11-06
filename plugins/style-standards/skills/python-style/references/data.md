# Data: Dataclasses, Enums, Protocols, and Immutability

Scope: choosing the shape a value takes — dataclass, enum, protocol, `TypedDict`, `NamedTuple`,
plain class — and what each obliges you to. How to spell the annotation on a field is the types
chapter; whether the value is safe to share is the concurrency chapter; what a constructor should
accept is the API chapter.

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
  - PS-DATA-09 [M] Never compute a default at import time
  - PS-DATA-10 [M] Order fields so every default follows every required field
- **Immutability**
  - PS-DATA-11 [M] Freeze anything that crosses a boundary
  - PS-DATA-12 [M] Replace rather than mutate, with `dataclasses.replace`
  - PS-DATA-13 [M] Use `frozendict` for an immutable mapping, and test `Mapping` not `dict`
- **Validity**
  - PS-DATA-14 [M] Validate in `__post_init__`, and raise rather than correct
  - PS-DATA-15 [M!] Make the invalid state unrepresentable before validating against it
  - PS-DATA-16 [M] Give a domain value its own type rather than a bare `str` or `int`
  - PS-DATA-17 [M] Never let `__eq__` and `__hash__` disagree
- **Symmetry of a data type**
  - PS-DATA-18 [M] Give every serialiser its inverse
- Decided by tools

---

## Choosing the shape

### PS-DATA-01 [M] Model a record as a frozen dataclass by default

`@dataclass(frozen=True, slots=True)`. Reach for a mutable one, or a plain class, only when you can
say what it buys. One that two threads can reach is frozen, or owns a lock that every write takes
(PS-CONC-11).

**Why:** one decorator buys `__init__`, `__repr__`, `__eq__` and a field list tooling can read.
Freezing removes the largest class of record bug — being changed by whoever you handed it to — and
makes it hashable; the cost is a `replace` call, which makes the change visible.

**Check:** `rg -n '@dataclass' src/` — every decorator without `frozen=True` needs a reason on the
line above it.

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

Anything assigning attributes dynamically, or using `functools.cached_property`, needs the dict.
Everything else does not. A weak reference is not a reason to keep it: `weakref_slot=True` gives it
a slot. On a plain class, write the same thing as `__slots__ = ("name",)`.

**Why:** without the instance `__dict__`, a misspelt attribute raises `AttributeError` at the moment
of the mistake instead of silently becoming a new one. The instance is also smaller and faster, the
more so on the free-threaded build: a non-GC object is 32 bytes there, against 16 on the default.

**Check:** the `SLOT000`–`SLOT002` rows for the subclass cases. For dataclasses,
`rg -n '@dataclass' src/` and read for `slots=`. A class instantiated more than a few thousand times
with no slots is the finding.

```python
# verified — GOOD
import weakref
from dataclasses import dataclass


@dataclass(frozen=True, slots=True, weakref_slot=True)
class Node:
    name: str


node = Node("root")
reference = weakref.ref(node)  # held in a slot, not in an instance dict
assert reference() is node
assert not hasattr(node, "__dict__")
```

### PS-DATA-03 [M] Model a closed set of alternatives as an enum

Not string constants, not a `Literal` union of strings, not integers with a comment.

**Why:** an enum names the set, gives each member a readable `repr` in a traceback, and is the one
place to add a member, which PS-TYPE-14's `assert_never` turns into a type error wherever the set is
consumed. A `Literal` union gets the narrowing and none of the rest.

**Check:** `rg -n '^[A-Z_]+[ \t]*[:=][ \t]*["\x27]' src/` — a group of module-level string constants
that are only ever compared against each other is an enum.

### PS-DATA-04 [M] Use `StrEnum` or `IntEnum` only when the value crosses a boundary

A plain `Enum` inside your own code. `StrEnum` when the member must serialise as its value into
JSON, a URL, or a database column, and convert at that edge.

**Why:** a mixin member compares equal to its raw value, which a boundary wants and the inside does
not: `Kind.READ == "read"` is true, so a stray string silently satisfies a comparison that should
have failed.

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

**Why:** a `NamedTuple` is a tuple: iterable, indexable, and equal to a plain tuple of the same
values. That suits a coordinate and endangers a record: `if user == (1, "a"):` type-checks and
works, and nobody meant it to. Nor can it turn mutable without changing every unpacking site.

**Check:** every `NamedTuple`. If no caller unpacks it and no caller indexes it, it wants to be a
frozen dataclass.

### PS-DATA-06 [M] Use a `TypedDict` for a wire format, never for a domain object

A `TypedDict` describes a `dict` that already exists — a parsed JSON body, a `**kwargs` bundle. It
does not describe a thing your code owns. Parse it at the boundary into a dataclass; do not carry
the dict inward.

**Why:** a `TypedDict` is a `dict` at runtime: no methods, no validation, no `repr` worth reading,
no identity, and every access a lookup that can `KeyError`. That is acceptable for the five lines
after `json.loads`, and not for anything that lives longer.

**Check:** every `TypedDict`. If an instance is passed to more than one function, it should have
been a dataclass by then.

### PS-DATA-07 [M] Define an interface as a `Protocol`, not an ABC, unless you ship behaviour

`class Reader(Protocol)` when you need a shape. An ABC when you have concrete methods subclasses
inherit.

**Why:** a protocol is structural, so a caller satisfies it with a type they already have and
neither side imports the other, which is what makes it usable across a package boundary. An ABC
forces inheritance, coupling the implementer to you and barring two interfaces whose bases conflict.

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

`def f(items: list[int] = [])` and `field(default=[])` are the same bug. A field takes
`field(default_factory=list)`, which runs once per instance.

**Why:** the default is evaluated once, at definition time, and shared by every call that omits it,
so one caller's mutation changes it for every later caller. Under free threading it is shared across
threads too, so the mutation races as well as leaking.

**Check:** the `B006` row for the argument form, `RUF008` for the dataclass field and `RUF012` for
the class attribute. `dataclasses` refuses a default whose type is unhashable, so a mutable class
that keeps `object`'s hash slips through, and a `field(default=` holding one is still the finding.

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

### PS-DATA-09 [M] Never compute a default at import time

`created_at: datetime = datetime.now()` freezes one timestamp into the class. So does reading an
environment variable, or a file, or a random seed.

**Why:** the value is captured when the module is imported, which is a moment nobody chose and which
PEP 810's lazy imports make genuinely unpredictable. Every instance then shares one stale value. The
factory form defers it to construction, which is when the caller meant it.

**Check:** `rg -n 'field\(default=|=[ \t]*[a-z_]+\.[a-z_]+\(\)' src/` inside class bodies — a call
in a default is the finding unless it is `default_factory`.

### PS-DATA-10 [M] Order fields so every default follows every required field

Or make the defaulted ones keyword-only with `KW_ONLY`.

**Why:** `dataclasses` already raises `TypeError` at class definition otherwise. What it misses is
the design consequence: a field gaining a default must move, which silently changes the meaning of
every positional call; keyword-only defaults remove that coupling for good.

**Check:** every dataclass with more than three fields, and every one whose defaults are
interleaved.

## Immutability

### PS-DATA-11 [M] Freeze anything that crosses a boundary

Anything returned from a public function, stored in a cache, used as a dict key, or handed to a
thread. A container held on `self` leaves as `tuple(self._items)`, which also says the result is not
for editing, and never as `self._items`, a live handle on your state.

**Why:** once a value leaves your module you do not know who holds a reference, so a mutation is an
effect at a distance with no call site to read. Freezing turns that into a `FrozenInstanceError` at
the attempt, and an immutable value needs no lock at all.

**Check:** every public return type. A mutable dataclass, `list`, `dict` or `set` is the finding
unless the docstring transfers ownership explicitly, and a bare `return self._x` of a container is
the finding outright.

### PS-DATA-12 [M] Replace rather than mutate, with `dataclasses.replace`

`updated = replace(original, status=Status.RETIRED)`.

**Why:** `replace` keeps the type, runs `__post_init__` so the new value is validated like any
other, and leaves the original intact rather than making its history unknowable. A hand-written
constructor call is one more site to update every time a field is added.

**Check:** `rg -n 'replace\(' src/` should be roughly as common as frozen dataclasses are. Their
absence, alongside frozen types, means someone is rebuilding by hand.

### PS-DATA-13 [M] Use `frozendict` for an immutable mapping, and test `Mapping` not `dict`

`frozendict`, new in 3.15, for the value, in place of `types.MappingProxyType`.
`isinstance(x, collections.abc.Mapping)` for the check: `frozendict` is **not a `dict` subclass**;
it inherits directly from `object`. The standard library was updated for this — `copy`, `json`,
`pickle`, `pprint` and others — and third-party code was not.

**Why:** `MappingProxyType` is a *view*: it forbids writing through the proxy while the dict behind
it stays mutable, so it never made anything immutable. And `isinstance(x, dict)` is `False` for a
mapping that behaves like a dict in every way that matters, so a function taking one rejects it.

**Check:** `rg -n 'isinstance\(.*, dict\)' src/` — every hit is a place a `frozendict` would fail
the test. `rg -n 'MappingProxyType' src/` finds the spelling it replaces.

```python
# verified — GOOD
from collections.abc import Mapping
from typing import Final

DEFAULTS: Final = frozendict({"retries": 3, "timeout_ms": 500})

assert isinstance(DEFAULTS, Mapping)
assert not isinstance(DEFAULTS, dict)  # the trap: it is not a dict subclass
assert DEFAULTS["retries"] == 3
```

## Validity

### PS-DATA-14 [M] Validate in `__post_init__`, and raise rather than correct

Raise `ValueError`. Do not clamp, coerce, or substitute a default.

**Why:** `__post_init__` runs on every construction path, `replace` included, so it is the one place
that cannot be bypassed. Correcting hides the caller's bug and leaves them reasoning about the value
they passed, not the one they got; a raise puts the construction site in the traceback.

**Check:** every dataclass with a field whose valid range is narrower than its type. No
`__post_init__` is the finding.

```python
# verified — GOOD
from dataclasses import dataclass

import pytest


@dataclass(frozen=True, slots=True)
class Port:
    number: int

    def __post_init__(self) -> None:
        if not 1 <= self.number <= 65535:
            msg = f"port out of range: {self.number}"
            raise ValueError(msg)


def test_out_of_range_is_rejected() -> None:
    with pytest.raises(ValueError, match="out of range"):
        Port(0)


assert Port(8080).number == 8080
```

### PS-DATA-15 [M!] Make the invalid state unrepresentable before validating against it

An enum instead of a validated string. A `Port` type instead of an `int` you check. Two types
instead of one type with a flag that says which it is.

*Relaxed form:* application code at a boundary may validate a primitive rather than introduce a
type, provided the validation happens exactly once and the validated value is not passed on as the
primitive.

**Why:** validation must be repeated at every construction site and can be forgotten at any of them;
a type is a check the type checker makes everywhere for free. Every state made unrepresentable is a
branch you never write and a test you never need.

**Check:** every `if not valid: raise` in the codebase. Ask what type would make the check
unnecessary.

### PS-DATA-16 [M] Give a domain value its own type rather than a bare `str` or `int`

`UserId`, `Email`, `Cents` — a `NewType` at minimum, a frozen dataclass where there is behaviour.

**Why:** in `def transfer(from_: str, to: str, amount: int)`, swapping the two accounts type-checks;
with distinct types, the transposition is a type error. `NewType` costs nothing at runtime — it is
the identity function — and removes that whole class of confusion.

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

### PS-DATA-17 [M] Never let `__eq__` and `__hash__` disagree

If two objects are equal they must hash equal. A mutable object that defines `__eq__` must not
define `__hash__`.

**Why:** a dict or set finds a key by hash first and equality second, so an equal pair with
different hashes lands in different buckets and the lookup silently misses. `dataclass` gets this
right: `eq=True` without `frozen=True` sets `__hash__` to `None`, leaving it unhashable, not broken.

**Check:** `rg -n 'def __eq__' src/` — every hit needs a matching `__hash__` or a documented reason
the type is unhashable.

## Symmetry of a data type

### PS-DATA-18 [M] Give every serialiser its inverse

If `to_json` exists, `from_json` exists. If `__str__` is meant to round-trip, something parses it.
The same holds for every verb a type pairs, `encode` with `decode` and `push` with `pop`; how the
two are spelled is PS-NAME-14.

**Why:** a one-way conversion produces a value you can never recover, and the gap stays invisible
until someone needs the inverse, by which point the format has already shipped. Writing the pair
together also tests the format: a round-trip assertion is the cheapest schema check there is.

**Check:** every `to_*`, `__str__` and paired verb on a data type. A missing inverse is either
deliberate — say so in the docstring — or the finding.

```python
# verified — GOOD
from dataclasses import dataclass
from typing import Self
lazy from collections.abc import Mapping


@dataclass(frozen=True, slots=True)
class Point:
    x: int
    y: int

    def to_dict(self) -> dict[str, int]:
        # Not `asdict`: it returns `dict[str, Any]`, and laundering
        # `Any` into an annotated return is what PS-TYPE-12 stops.
        return {"x": self.x, "y": self.y}

    @classmethod
    def from_dict(cls, raw: Mapping[str, int]) -> Self:
        return cls(x=raw["x"], y=raw["y"])


original = Point(1, 2)
assert Point.from_dict(original.to_dict()) == original
assert Point.from_dict(frozendict(x=1, y=2)) == original  # any mapping, not only a dict
```

## Decided by tools

A tool settles these on its own; the shipped configuration enables each at the level shown.

| Tool | Lint | Level | Forbids |
|---|---|---|---|
| ruff | `SLOT000` | error | a `str` subclass with no `__slots__` |
| ruff | `SLOT001` | error | a `tuple` subclass with no `__slots__` |
| ruff | `SLOT002` | error | a `namedtuple` subclass with no `__slots__` |
| ruff | `B006` | error | a mutable default argument |
| ruff | `RUF008` | error | a mutable default on a dataclass field |
| ruff | `RUF012` | error | a mutable class attribute without `ClassVar` |
