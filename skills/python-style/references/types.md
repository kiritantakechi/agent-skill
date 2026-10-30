# Typing: Annotations, Generics, Narrowing, and the Checker

Scope: how to spell a type in 3.15, what the annotation machinery actually does now that PEP 649
made it lazy, which narrowing construct to reach for, how to read annotations at runtime without
breaking, and which checker this standard mandates. What to put *in* a type is the data chapter;
what a public signature should accept is the API chapter.

Two sources are merged here: the **Python Typing Spec** at `typing.python.org/spec`, which is the
living specification the typing PEPs now redirect to and which the Typing Council maintains under
PEP 729, and **Ruff's `ANN`, `UP` and `TC` families**, which decide mechanically whether annotations
are present and whether they are spelled the modern way. Correctness of the types themselves is
`ty`'s job — PS-TYPE-01 mandates it — and presence is Ruff's. The two compose rather than overlap.

Unless a block shows its own imports, it assumes `from typing import …` for the names it uses.

## Contents

- **The checker**
  - PS-TYPE-01 [M] Run `ty` at the pinned version, with the shipped configuration
  - PS-TYPE-02 [M] Never rely on a construct no specification defines
  - PS-TYPE-03 [M] Suppress with a code, never with a bare ignore
- **Annotations are lazy now**
  - PS-TYPE-04 [M] Never write `from __future__ import annotations`
  - PS-TYPE-05 [M] Read annotations with `annotationlib`, never off `__annotations__`
  - PS-TYPE-06 [M!] Use `FORWARDREF` when a name may not resolve
- **Spelling a type**
  - PS-TYPE-07 [M] Write unions with `|`, and put `None` last
  - PS-TYPE-08 [M] Use the builtin and `collections.abc` generics
  - PS-TYPE-09 [M] Declare type parameters with PEP 695 syntax
  - PS-TYPE-10 [M] Declare an alias with the `type` statement
  - PS-TYPE-11 [M] Never write variance by hand
  - PS-TYPE-12 [M] Do not use the spellings 3.15 retired
- **Precision**
  - PS-TYPE-13 [M] Use `object` for "anything", and `Any` only with a reason
  - PS-TYPE-14 [M] Narrow with `TypeIs`, not `TypeGuard`
  - PS-TYPE-15 [M] Close an exhaustive match with `assert_never`
  - PS-TYPE-16 [M] Mark what may not be subclassed or reassigned
  - PS-TYPE-17 [S] Reach for `@overload` only when a type parameter cannot express it
- **What 3.15 adds**
  - PS-TYPE-18 [M] Take a `TypeForm` when the argument is a type expression
  - PS-TYPE-19 [S] Close a `TypedDict` that models a fixed wire format
  - PS-TYPE-20 [M] Build a sentinel with `sentinel`, not with `object()`
- Decided by tools

---

## The checker

### PS-TYPE-01 [M] Run `ty` at the pinned version, with the shipped configuration

`ty==0.0.95`, `assets/ty.toml`, in CI, as a gate. Not as an editor convenience. The pin is exact,
and moving it is a reviewed change: bump it, run the suite, read what moved, and update the
configuration in the same commit — never let a resolver do it. Mandated means required, not
exclusive: a second checker is permitted, nothing here promises the two agree, and **no rule is
weakened to make one agree**.

**Why:** an annotation nothing checks is a comment with syntax, and a standard that ships a
configuration without saying whether to run it has said nothing. The pin is exact because `ty` is
`0.0.x`, and its policy allows breaking changes, diagnostics included, between any two versions.

**Check:** `ty check` exits non-zero. Note that it exits non-zero on warnings too —
`error-on-warning` defaults to true — so a `warn` level still blocks and only `ignore` does not.

```sh
uv run ty check
```

### PS-TYPE-02 [M] Never rely on a construct no specification defines

A checker extension that the Typing Spec does not describe is not portable, however useful. `ty`'s
intersection types are the current example. The line runs one way: **specified-but-unimplemented is
fine; implemented-but-unspecified is not.** PEP 728's `extra_items` is specified and not every
checker implements it yet — use it.

**Why:** pinning one checker works only if the *pin* moves and the *rules* do not. A rule that holds
because one tool infers it cannot survive the tool, and it silently makes the codebase un-checkable
by anything else.

**Check:** every construct in a public signature must be findable in `typing.python.org/spec`. One
that is not is the finding.

### PS-TYPE-03 [M] Suppress with a code, never with a bare ignore

`# ty: ignore[invalid-assignment]`, not a bare `# ty: ignore` or `# type: ignore`. And a comment on
the line saying why. Under `ty` a coded `# type: ignore[…]` suppresses nothing at all, even with
`ty`'s own code.

**Why:** a bare suppression silences every diagnostic on its line, including ones that appear later
for unrelated reasons, so it is a permanent blind spot. The coded form expires: when the diagnostic
it names stops firing, the suppression itself becomes reportable.

**Check:** `ty`'s `blanket-ignore-comment`, which the shipped configuration promotes to `error`,
flags a bare `# ty: ignore`; ruff `PGH003` flags a bare `# type: ignore`. Both are enabled because
this one is easy to reach for under time pressure.

## Annotations are lazy now

### PS-TYPE-04 [M] Never write `from __future__ import annotations`

Not in new code, and delete it wherever it remains. Python's porting notes call the import
deprecated and expect it to be removed. Ruff has no rule for it, so this is a written rule and a
grep rather than a lint.

**Why:** PEP 563 is **Superseded** by PEP 649 and PEP 749, and with annotations lazy the import is
harmful: it stringifies annotations at compile time, so `annotationlib`'s `VALUE` and `FORWARDREF`
hand back bare strings without raising, and every consumer then gets text it must evaluate itself.

**Check:** `rg -n 'from __future__ import annotations' src/` — every hit is the finding.

### PS-TYPE-05 [M] Read annotations with `annotationlib`, never off `__annotations__`

`annotationlib.get_annotations(obj, format=...)`. Not `obj.__annotations__`, and not
`typing.get_type_hints` in new code.

**Why:** `__annotations__` is now backed by a compiler-generated function computed on access, so
reading it off a class namespace during class creation sees something different from reading it
afterwards. `annotationlib` is the supported door, and the only one offering PS-TYPE-06's formats.

**Check:** `rg -n '__annotations__' src/` — every hit outside a test of the machinery itself
is the finding.

### PS-TYPE-06 [M!] Use `FORWARDREF` when a name may not resolve

Library code that reads someone else's annotations asks for `Format.FORWARDREF`, not `Format.VALUE`,
and resolves a `ForwardRef` it gets back with `typing.evaluate_forward_ref()` once the name exists.

*Relaxed form:* application code reading its own annotations, where every name is importable at
runtime, may use `VALUE` — and should say so in a comment, because the assumption is invisible
otherwise.

**Why:** `VALUE` evaluates, so a name imported only under `TYPE_CHECKING` raises `NameError`, and
PEP 649 makes such names legitimate in far more code. `FORWARDREF` returns the real object where it
can and a `ForwardRef` where it cannot, so the caller handles the gap instead of a crash.

**Check:** every `get_annotations` call site. A bare one (defaulting to `VALUE`) in a library is the
finding.

```python
# verified — GOOD
import annotationlib
import decimal
from typing import TYPE_CHECKING, evaluate_forward_ref

if TYPE_CHECKING:
    # Not imported at runtime — the common, legitimate reason a name in an
    # annotation cannot be resolved.
    from decimal import Decimal


def price(amount: Decimal) -> None:
    """PEP 649 makes this legal: the annotation is never evaluated here."""


try:
    annotationlib.get_annotations(price, format=annotationlib.Format.VALUE)
    raise AssertionError("VALUE should not have resolved a TYPE_CHECKING-only name")
except NameError:
    pass  # This is what a library reading someone else's annotations would hit.

deferred = annotationlib.get_annotations(price, format=annotationlib.Format.FORWARDREF)
assert isinstance(deferred["amount"], annotationlib.ForwardRef)

# Resolved later, once the caller can supply the name.
resolved = evaluate_forward_ref(deferred["amount"], locals={"Decimal": decimal.Decimal})
assert resolved is decimal.Decimal

as_text = annotationlib.get_annotations(price, format=annotationlib.Format.STRING)
assert as_text["amount"] == "Decimal"
```

## Spelling a type

### PS-TYPE-07 [M] Write unions with `|`, and put `None` last

`int | str`, `Widget | None`. Never `Union[int, str]`, never `Optional[Widget]`, never `None | X`.
`typing.Union` and `types.UnionType` are one type, and a union is not cached, so compare unions with
`==`, not `is`.

**Why:** `Optional` misleads: it reads as "this argument is optional", a claim about whether it must
be *passed*, not about what it may hold. `|` needs no import and reads as the alternation it is, and
`None` last keeps the interesting type where the eye lands first.

**Check:** ruff `UP007` and `UP045` rewrite both automatically at this target version.

### PS-TYPE-08 [M] Use the builtin and `collections.abc` generics

`list[int]`, `dict[str, int]`, `collections.abc.Sequence`, `collections.abc.Callable`. Never
`typing.List`, `typing.Dict`, `typing.Callable`.

**Why:** PEP 585 deprecated the `typing` aliases, which survive only so that old code keeps
importing. And `Sequence` is a real ABC about behaviour, so importing it from `typing` misfiles it
as a typing artefact.

**Check:** ruff `UP006` and `UP035`.

### PS-TYPE-09 [M] Declare type parameters with PEP 695 syntax

`class Box[T]:`, `def first[T](items: Sequence[T]) -> T:`. Never a module-level `TypeVar` plus
`Generic[T]`, and never both styles in one declaration: the spec says they "should not be combined".

**Why:** the syntax scopes the parameter to what it parameterises; a module-level `TypeVar` is a
name that can be — and was — reused across unrelated declarations, silently linking them. Legacy
`TypeVar` is not formally deprecated, so no warning will tell you this.

**Check:** ruff `UP046` and `UP047` for the class and function forms.

```python
# verified — GOOD
from collections.abc import Sequence


class Box[T]:
    """The parameter is scoped to the class; nothing outside can reuse it."""

    def __init__(self, item: T) -> None:
        self.item = item

    def get(self) -> T:
        return self.item


def first[T](items: Sequence[T], fallback: T) -> T:
    return items[0] if items else fallback


assert Box(3).get() == 3
assert first([], "none") == "none"
```

### PS-TYPE-10 [M] Declare an alias with the `type` statement

`type Handler = Callable[[Request], Response]`. Never a bare assignment, and never `TypeAlias`.

**Why:** a bare `X = int` leaves the checker guessing between an alias and a variable holding a
type. The `type` statement says which in the syntax and evaluates lazily, so an alias may name
something defined later without quotes. `typing.TypeAlias` is deprecated in its favour.

**Check:** ruff `UP040`.

### PS-TYPE-11 [M] Never write variance by hand

No `covariant=True`, no `contravariant=True`, no `infer_variance=True`.

**Why:** PEP 695 parameters have their variance inferred from how they are used, which is both
correct more often than a human is and impossible to get out of sync with the class body.
Hand-written variance is a second source of truth about the same fact.

**Check:** `rg -n '(co|contra)variant[ \t]*=|infer_variance' src/` — every hit is either legacy
`TypeVar` (PS-TYPE-09) or a hand-written variance.

### PS-TYPE-12 [M] Do not use the spellings 3.15 retired

`AnyStr` (removal 3.18), `ByteString` (removal 3.17), `Text`, `typing.no_type_check_decorator`
(removed in 3.15), `# type:` comments, and `Unpack` where PEP 695 variadics fit. In place of
`ByteString` take `collections.abc.Buffer`, which every buffer satisfies: `array`, `mmap` and a
third party's types too, all of which `bytes | bytearray | memoryview` rejects.

**Why:** each has a live replacement, and several are on a removal schedule that turns a warning
into an error within two releases. `ByteString` is the subtle one: 3.15 dropped it from `__all__`
but left it importable, so it works, warns on plain access, and fails once 3.17 removes it.

**Check:** `rg -n 'ByteString' src/` — a hit warns today and fails in 3.17. The migration chapter
carries the full table as one runnable grep, and ruff `UP` and `PYI` catch the ones that are
statically decidable.

```python
# verified — GOOD
import array
from collections.abc import Buffer


def checksum(data: Buffer) -> int:
    """Sum the bytes of any buffer: `bytes`, `memoryview`, `array`, `mmap`."""
    return sum(memoryview(data).cast("B"))


assert checksum(b"\x01\x02") == 3
assert checksum(array.array("B", [1, 2])) == 3
```

## Precision

### PS-TYPE-13 [M] Use `object` for "anything", and `Any` only with a reason

If the function truly accepts anything, the type is `object` and you narrow before use. `Any` needs
a comment naming what cannot be expressed: the typing best-practices guidance reserves it for "when
a type cannot be expressed appropriately with the current type system or using the correct type is
unergonomic".

**Why:** the two look alike and are opposites. `object` is the top type, and the checker makes you
narrow it; `Any` disables checking in both directions and is assignable to everything, so one `Any`
in a signature quietly erases the types of everything it touches.

**Check:** ruff `ANN401` for `Any` in a public signature. Every surviving `Any` needs a comment.

### PS-TYPE-14 [M] Narrow with `TypeIs`, not `TypeGuard`

`def is_str(x: object) -> TypeIs[str]:`. Reach for `TypeGuard` only where the narrowed type is not
assignable to the input type, and say why in the docstring.

**Why:** `TypeGuard` narrows only the positive branch, so the `else` keeps the original union and
the reader meets a type error in the arm that should have been obvious. `TypeIs` narrows both ways,
and PEP 742 says "most users should reach for `TypeIs` first".

**Check:** `rg -n 'TypeGuard' src/` — every hit needs the docstring sentence explaining why the
constraint cannot hold.

```python
# verified — GOOD
from typing import TypeIs


def is_str(x: object) -> TypeIs[str]:
    return isinstance(x, str)


def width(x: str | int) -> int:
    if is_str(x):
        return len(x)
    # TypeIs narrows here too: `x` is `int`, not `str | int`.
    return x.bit_length()


assert width("abcd") == 4
assert width(255) == 8
```

### PS-TYPE-15 [M] Close an exhaustive match with `assert_never`

Every `match` and every `if`/`elif` chain over a closed set ends with a branch that asserts the
remainder is `Never`.

**Why:** without it, a new variant is silently accepted wherever the set is consumed, and falls
through to whatever the last branch happens to do. With it, adding a variant is a type error at
every consumption site, which is the whole value of modelling the set as closed.

**Check:** every `match` over an enum or a literal union. A missing `case _:` that calls
`assert_never` is the finding.

```python
# verified — GOOD
import enum
from typing import assert_never


class Kind(enum.Enum):
    READ = "read"
    WRITE = "write"


def describe(kind: Kind) -> str:
    match kind:
        case Kind.READ:
            return "reader"
        case Kind.WRITE:
            return "writer"
        case _:
            # Adding a third member makes this a type error at every call site.
            assert_never(kind)


assert describe(Kind.READ) == "reader"
```

### PS-TYPE-16 [M] Mark what may not be subclassed or reassigned

`@final` on a class nothing should subclass. `Final` on a module constant.

**Why:** without them every class is an extension point whether you meant it or not, and every
constant is a variable; both markers are checked. `@final` also lets the checker narrow more
aggressively, because it knows no subclass can widen the behaviour.

**Check:** ruff `PYI` for the stub cases; the rest is review. A module-level name in
`SCREAMING_SNAKE_CASE` without `Final` is the finding.

### PS-TYPE-17 [S] Reach for `@overload` only when a type parameter cannot express it

Two overloads that differ only in a container's element type are a type parameter written the long
way.

**Why:** every overload is a signature the reader must hold simultaneously and the checker must try
in order, and the failure mode — no overload matched — produces a diagnostic that lists all of them.
Where a `T` expresses the relation, it does so in one signature that also composes.

**Check:** every `@overload` group. If the variants differ only in one position and the return
follows that position, a type parameter replaces the group.

## What 3.15 adds

### PS-TYPE-18 [M] Take a `TypeForm` when the argument is a type expression

`def parse[T](raw: str, into: TypeForm[T]) -> T:`. Not `type[T]`, and not `object`.

**Why:** `type[T]` means "a class object", so it rejects `int | None`, `list[int]` and
`Literal["a"]`, all type expressions a parser may be handed. Before PEP 747 only `object` accepted
them, which left every deserialisation library an untyped seam at its most interesting argument.

**Check:** every parameter documented as "a type" that is annotated `object` or `type[Any]`.

### PS-TYPE-19 [S] Close a `TypedDict` that models a fixed wire format

`class Payload(TypedDict, closed=True):` when the schema forbids extra keys, or `extra_items=` when
it constrains rather than forbids them. Where the schema genuinely allows extension, leave it open.

**Why:** a plain `TypedDict` silently permits unknown keys, so a typo in a producer reaches the
consumer as a missing value rather than an unexpected one, and the two need different fixes. It is
`[S]` because "fixed" is a claim about the protocol, not about the code.

**Check:** every `TypedDict` that models something crossing a process boundary. A checker that
rejects `extra_items` is not a reason to avoid it — see PS-TYPE-02.

### PS-TYPE-20 [M] Build a sentinel with `sentinel`, not with `object()`

`MISSING = sentinel("MISSING")`, and annotate the parameter `int | MISSING`. Bind it at module or
class scope under its own name; so bound, it survives copying and pickling, which `object()` does
not.

**Why:** a hand-rolled `object()` has no type the checker can name, so the parameter ends up
`int | None`, conflating "not supplied" with "supplied as None", or `Any`, which erases the
distinction. PEP 661 sentinels narrow by `is` and have a `repr` readable in a traceback.

**Check:** `rg -n '=[ \t]*object\(\)' src/` — every hit is a sentinel that should be declared.
`ty`'s `mismatched-sentinel-name`, which the shipped configuration enables, catches a sentinel bound
under a name other than its own.

## Decided by tools

A tool settles these on its own; the shipped configuration enables each at the level shown.

| Tool | Lint | Level | Forbids |
|---|---|---|---|
| ruff | `UP037` | error | a quoted annotation — annotations are lazy, so `-> Node` needs no quotes |
