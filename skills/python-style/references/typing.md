# Typing: Annotations, Generics, Narrowing, and the Checker

Scope: how to spell a type in 3.15, what the annotation machinery actually does now that PEP 649
made it lazy, which narrowing construct to reach for, how to read annotations at runtime without
breaking, and which checker this standard mandates. What to put *in* a type is the data-modelling
chapter; what a public signature should accept is the API chapter.

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
  - PS-TYPE-05 [M] Never quote a forward reference inside an annotation
  - PS-TYPE-06 [M] Read annotations with `annotationlib`, never off `__annotations__`
  - PS-TYPE-07 [M!] Use `FORWARDREF` when a name may not resolve
- **Spelling a type**
  - PS-TYPE-08 [M] Write unions with `|`, and put `None` last
  - PS-TYPE-09 [M] Use the builtin and `collections.abc` generics
  - PS-TYPE-10 [M] Declare type parameters with PEP 695 syntax
  - PS-TYPE-11 [M] Declare an alias with the `type` statement
  - PS-TYPE-12 [M] Never write variance by hand
  - PS-TYPE-13 [M] Do not use the spellings 3.15 retired
- **Precision**
  - PS-TYPE-14 [M] Take a protocol or an abstract type; return a concrete one
  - PS-TYPE-15 [M] Use `object` for "anything", and `Any` only with a reason
  - PS-TYPE-16 [M] Narrow with `TypeIs`, not `TypeGuard`
  - PS-TYPE-17 [M] Close an exhaustive match with `assert_never`
  - PS-TYPE-18 [M] Mark what may not be subclassed or reassigned
  - PS-TYPE-19 [S] Reach for `@overload` only when a type parameter cannot express it
- **What 3.15 adds**
  - PS-TYPE-20 [M] Take a `TypeForm` when the argument is a type expression
  - PS-TYPE-21 [S] Close a `TypedDict` that models a fixed wire format
  - PS-TYPE-22 [M] Build a sentinel with `sentinel`, not with `object()`

---

## The checker

### PS-TYPE-01 [M] Run `ty` at the pinned version, with the shipped configuration

`ty==0.0.74`, `assets/ty.toml`, in CI, as a gate. Not as an editor convenience.

**Why:** an annotation nothing checks is a comment with syntax. `ty` is mandated for the same
reason `ruff` is: a standard that ships a configuration while declining to say whether you should
run it has not said anything. It also accepts PEP 728 `extra_items` and PEP 661 sentinels in type
expressions — specified constructs, and part of what makes 3.15 worth targeting at all.

The pin is exact and that is not fussiness. `ty` is `0.0.x` and its own version policy reads:
*"ty does not yet have a stable API; breaking changes, including changes to diagnostics, may
occur between any two versions."* Its last twenty releases were zero to six days apart. So moving
the pin is a reviewed change: bump it, run the suite, read what moved, and update the
configuration in the same commit — never let a resolver do it.

Mandated means required, not exclusive. A second checker is permitted; nothing here promises the two
agree, and **no rule is weakened to make one agree**.

**Check:** `ty check` exits non-zero. Note that it exits non-zero on warnings too —
`error-on-warning` has defaulted true since 0.0.52 — so a `warn` level still blocks and only
`ignore` does not.

```sh
uv run ty check
```

### PS-TYPE-02 [M] Never rely on a construct no specification defines

A checker extension that the Typing Spec does not describe is not portable, however useful. `ty`'s
intersection types are the current example.

**Why:** the whole point of pinning one checker is that the *pin* moves and the *rules* do not. A
rule that holds only because one tool infers it cannot survive the tool, and it silently makes the
codebase un-checkable by anything else. The boundary is worth stating precisely, because the obvious
version of it is wrong in one direction: **specified-but-unimplemented is fine; implemented-but-
unspecified is not.** PEP 728's `extra_items` is specified and not every checker implements it yet —
use it. An intersection type is implemented and unspecified — do not.

**Check:** every construct in a public signature must be findable in `typing.python.org/spec`. One
that is not is the finding.

### PS-TYPE-03 [M] Suppress with a code, never with a bare ignore

`# type: ignore[assignment]`, not `# type: ignore`. And a comment on the line saying why.

**Why:** a bare suppression silences every diagnostic on that line, including the ones that appear
later for unrelated reasons — so it is a permanent blind spot rather than a targeted exception. The
coded form expires naturally: when the diagnostic it names stops firing, the suppression itself
becomes reportable.

**Check:** `ty`'s `blanket-ignore-comment` rule, which the shipped configuration promotes to
`error`, plus ruff `PGH003`. Both are enabled precisely because this one is easy to reach for
under time pressure.

## Annotations are lazy now

### PS-TYPE-04 [M] Never write `from __future__ import annotations`

Not in new code, and delete it from old code that no longer supports 3.13.

**Why:** PEP 563 is **Superseded** by PEP 649 and PEP 749, and on 3.14+ the import is not merely
unnecessary — it is harmful. It stringifies annotations at compile time, which silently degrades
`annotationlib`: `Format.VALUE` returns bare strings instead of objects, and `Format.FORWARDREF`
returns bare strings instead of `ForwardRef`s, violating the format contract without raising. Every
downstream consumer that reads annotations — dataclasses, validators, dependency injection,
serialisers — then receives text it must evaluate itself. The 3.14 porting notes call the import
deprecated and expect it to be removed.

Note that ruff has no rule for this yet, so it is a written rule and a grep rather than a lint.

**Check:** `grep -rn 'from __future__ import annotations' src/` — every hit is the finding.

### PS-TYPE-05 [M] Never quote a forward reference inside an annotation

`def sibling(self) -> Node | None:` inside `class Node`. Not `-> "Node | None"`.

**Why:** PEP 649 made annotations lazily evaluated, so a name that is not yet defined is no longer a
problem to work around. Quoting still *works*, which is what makes it linger — but it hides the
annotation from anything reading it as a value, and if the module also carries the future import the
string ends up quoted twice. Quotes remain necessary outside annotations, which is what the `type`
statement in PS-TYPE-11 is for.

**Check:** `grep -rnE '->\s*"' src/` and `grep -rnE ':\s*"[A-Z]' src/`. Ruff `UP037` removes the
quotes automatically.

```python
# verified — GOOD
class Node:
    """`Node` is not defined yet when this annotation is written, and that is fine."""

    def __init__(self, value: int, parent: Node | None = None) -> None:
        self.value = value
        self.parent = parent

    def root(self) -> Node:
        node = self
        while node.parent is not None:
            node = node.parent
        return node


leaf = Node(2, Node(1))
assert leaf.root().value == 1
```

### PS-TYPE-06 [M] Read annotations with `annotationlib`, never off `__annotations__`

`annotationlib.get_annotations(obj, format=...)`. Not `obj.__annotations__`, and not
`typing.get_type_hints` in new code.

**Why:** the annotations HOWTO states it directly — *"You should avoid accessing `__annotations__`
directly on any object."* The attribute is now backed by a compiler-generated function whose result
is computed on access, so reading the raw dict off a class namespace during class creation sees
something different from reading it afterwards. `annotationlib` is the supported door, and it is the
only one that offers the formats PS-TYPE-07 needs.

**Check:** `grep -rn '__annotations__' src/` — every hit outside a test of the machinery itself
is the finding.

### PS-TYPE-07 [M!] Use `FORWARDREF` when a name may not resolve

Library code that reads someone else's annotations asks for `Format.FORWARDREF`, not `Format.VALUE`.

*Relaxed form:* application code reading its own annotations, where every name is importable at
runtime, may use `VALUE` — and should say so in a comment, because the assumption is invisible
otherwise.

**Why:** `VALUE` evaluates, so it raises `NameError` on any name imported only under `TYPE_CHECKING`
— and PS-TYPE-05 plus PEP 649 mean far more code now contains such names legitimately. `FORWARDREF`
returns a `ForwardRef` for whatever cannot be resolved and the real object for everything else, so
the caller decides what to do about the gap rather than the library crashing on it.

**Check:** every `get_annotations` call site. A bare one (defaulting to `VALUE`) in a library is the
finding.

```python
# verified — GOOD
import annotationlib
from typing import TYPE_CHECKING

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

as_text = annotationlib.get_annotations(price, format=annotationlib.Format.STRING)
assert as_text["amount"] == "Decimal"
```

## Spelling a type

### PS-TYPE-08 [M] Write unions with `|`, and put `None` last

`int | str`, `Widget | None`. Never `Union[int, str]`, never `Optional[Widget]`, never `None | X`.

**Why:** PEP 604 syntax is shorter, needs no import, and reads as the alternation it is.
`Optional` is worse than merely verbose — it reads as "this argument is optional", which is a
statement about whether it must be *passed*, and that is a different claim. Putting `None` last
keeps the interesting type where the eye lands first. Note that 3.14 merged `typing.Union` and
`types.UnionType` and stopped caching them, so unions must be compared with `==` rather than
`is`.

**Check:** ruff `UP007` and `UP045` rewrite both automatically at this target version.

### PS-TYPE-09 [M] Use the builtin and `collections.abc` generics

`list[int]`, `dict[str, int]`, `collections.abc.Sequence`, `collections.abc.Callable`. Never
`typing.List`, `typing.Dict`, `typing.Callable`.

**Why:** PEP 585 deprecated the `typing` aliases in 3.9 and they exist now only for code that must
run on older interpreters, which this standard does not support. Importing from `collections.abc`
also puts the abstract types where they belong: `Sequence` is a protocol about behaviour, and
importing it from `typing` suggests it is a typing artefact rather than a real ABC.

**Check:** ruff `UP006` and `UP035`.

### PS-TYPE-10 [M] Declare type parameters with PEP 695 syntax

`class Box[T]:`, `def first[T](items: Sequence[T]) -> T:`. Never a module-level `TypeVar` plus
`Generic[T]`.

**Why:** the modern syntax scopes the parameter to the thing it parameterises, which is what it
always meant; the `TypeVar` form put a module-level name in scope that could be — and was —
reused across unrelated declarations, silently linking them. The spec is explicit that the two
styles "should not be combined" in one declaration. Legacy `TypeVar` is not formally deprecated,
so this is a rule rather than a warning you will see.

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

### PS-TYPE-11 [M] Declare an alias with the `type` statement

`type Handler = Callable[[Request], Response]`. Never a bare assignment, and never `TypeAlias`.

**Why:** a bare assignment is ambiguous — the checker must guess whether `X = int` declares an alias
or a variable holding a type — which is why `TypeAlias` existed at all. The `type` statement says it
in the syntax, and it evaluates lazily, so an alias may reference a name defined later in the file
without quotes. `typing.TypeAlias` has been deprecated since 3.12.

**Check:** ruff `UP040`.

### PS-TYPE-12 [M] Never write variance by hand

No `covariant=True`, no `contravariant=True`, no `infer_variance=True`.

**Why:** PEP 695 parameters have their variance inferred from how they are used, which is both
correct more often than a human is and impossible to get out of sync with the class body.
Hand-written variance is a second source of truth about the same fact.

**Check:** `grep -rnE '(co|contra)variant\s*=|infer_variance' src/` — every hit is either legacy
`TypeVar` (PS-TYPE-10) or a hand-written variance.

### PS-TYPE-13 [M] Do not use the spellings 3.15 retired

`AnyStr` (removal 3.18), `ByteString` (removal 3.17), `Text`, `typing.no_type_check_decorator`
(removed in 3.15), `# type:` comments, the functional `NamedTuple`/`TypedDict` forms, and
`Unpack` where PEP 695 variadics fit.

**Why:** each is a spelling with a live replacement, and several are on a removal schedule that will
turn a warning into an error inside two releases. `ByteString` is the subtle one: 3.15 removed it
from `__all__` while leaving the name importable, so it now emits a `DeprecationWarning` on plain
access where previously only subclassing warned — the name works, and warns, until 3.17.

**Check:** the migration chapter carries the full table as one runnable grep. Ruff `UP` and `PYI`
catch the ones that are statically decidable.

## Precision

### PS-TYPE-14 [M] Take a protocol or an abstract type; return a concrete one

`def render(items: Sequence[str]) -> list[str]:`. Not `list[str]` in and not `Sequence[str]` out.

**Why:** the parameter is a constraint on your callers and the return is a promise to them, so the
two want opposite generality. Accepting `Sequence` lets a caller pass a tuple; returning `Sequence`
denies the caller the `.append` you actually gave them, and they will cast it back. This is the
typing form of "be liberal in what you accept".

**Check:** every public signature. A concrete container in a parameter, or an abstract one in a
return, is the finding — a mutable parameter type is the exception, because mutating the argument is
the point.

### PS-TYPE-15 [M] Use `object` for "anything", and `Any` only with a reason

If the function truly accepts anything, the type is `object` and you narrow before use. `Any`
needs a comment naming what cannot be expressed.

**Why:** they are opposites that look alike. `object` is the top type — safe, and the checker forces
you to narrow. `Any` disables checking in both directions and is assignable to everything, so one
`Any` in a signature quietly erases the types of everything it touches. The typing best-practices
guidance is to use `Any` only "when a type cannot be expressed appropriately with the current type
system or using the correct type is unergonomic" — a genuine limit, not a shrug.

**Check:** ruff `ANN401` for `Any` in a public signature. Every surviving `Any` needs a comment.

### PS-TYPE-16 [M] Narrow with `TypeIs`, not `TypeGuard`

`def is_str(x: object) -> TypeIs[str]:`. Reach for `TypeGuard` only where the narrowed type is not
assignable to the input type, and say why in the docstring.

**Why:** `TypeGuard` narrows only the positive branch, so the `else` keeps the original union and
the reader is surprised by a type error in the arm that should have been obvious. `TypeIs`
narrows both ways, which is what everyone assumed `TypeGuard` did. PEP 742 says outright that
"most users should reach for `TypeIs` first"; PEP 724, the attempt to fix `TypeGuard` in place,
was withdrawn in its favour.

**Check:** `grep -rn 'TypeGuard' src/` — every hit needs the docstring sentence explaining why the
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

### PS-TYPE-17 [M] Close an exhaustive match with `assert_never`

Every `match` and every `if`/`elif` chain over a closed set ends with a branch that asserts the
remainder is `Never`.

**Why:** without it, adding a variant to the enum or the union is silently accepted everywhere it
is consumed, and the new case falls through to whatever the last branch happens to do. With it,
adding a variant is a type error at every consumption site — which is the entire value of
modelling the set as closed in the first place.

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

### PS-TYPE-18 [M] Mark what may not be subclassed or reassigned

`@final` on a class nothing should subclass. `Final` on a module constant.

**Why:** both are statements the reader cannot otherwise make, and both are checked. `@final`
also lets the checker narrow more aggressively, because it knows no subclass can widen the
behaviour. Without it, every class is an extension point whether or not you meant it to be, and
every constant is a variable.

**Check:** ruff `PYI` for the stub cases; the rest is review. A module-level name in
`SCREAMING_SNAKE_CASE` without `Final` is the finding.

### PS-TYPE-19 [S] Reach for `@overload` only when a type parameter cannot express it

Two overloads that differ only in a container's element type are a type parameter written the long
way.

**Why:** every overload is a signature the reader must hold simultaneously and the checker must try
in order, and the failure mode — no overload matched — produces a diagnostic that lists all of them.
Where a `T` expresses the relation, it does so in one signature that also composes.

**Check:** every `@overload` group. If the variants differ only in one position and the return
follows that position, a type parameter replaces the group.

## What 3.15 adds

### PS-TYPE-20 [M] Take a `TypeForm` when the argument is a type expression

`def parse[T](raw: str, into: TypeForm[T]) -> T:`. Not `type[T]`, and not `object`.

**Why:** `type[T]` means "a class object", so it rejects `int | None`, `list[int]` and
`Literal["a"]` — all of which are type *expressions* a parser might legitimately be handed.
Before PEP 747 the only way to accept those was `object`, which is why every deserialisation
library has an untyped seam where its most interesting argument should be. `TypeForm` is that
missing spelling.

**Check:** every parameter documented as "a type" that is annotated `object` or `type[Any]`.

### PS-TYPE-21 [S] Close a `TypedDict` that models a fixed wire format

`class Payload(TypedDict, closed=True):` when the schema forbids extra keys, or `extra_items=` when
it constrains rather than forbids them.

**Why:** a plain `TypedDict` silently permits unknown keys, so a typo in a producer reaches the
consumer as a missing value rather than as an unexpected one — and the two need different fixes.
This is `[S]` because "fixed" is a claim about the protocol rather than about the code; where the
schema genuinely allows extension, closing it is wrong.

**Check:** every `TypedDict` that models something crossing a process boundary. A checker that
rejects `extra_items` is not a reason to avoid it — see PS-TYPE-02.

### PS-TYPE-22 [M] Build a sentinel with `sentinel`, not with `object()`

`MISSING = sentinel("MISSING")`, and annotate the parameter `int | MISSING`.

**Why:** the hand-rolled `_MISSING = object()` has no type the checker can name, so the parameter
ends up `int | None` — which conflates "not supplied" with "supplied as None" and is the exact
distinction the sentinel exists to draw — or `Any`, which erases it. PEP 661 gives sentinels a
spelling the type system understands, with narrowing by `is`, and a `repr` that is readable in a
traceback. They also survive copying and pickling, which `object()` does not.

**Check:** `grep -rnE '=\s*object\(\)' src/` — every hit is a sentinel that should be declared.
