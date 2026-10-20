# Macros: `macro_rules!` and Procedural Macros

Scope: when a macro is the right tool and when it is not, `macro_rules!` mechanics — fragment
specifiers, hygiene, `$crate`, trailing commas, diagnostics — and procedural macros: crate split,
`syn`/`quote` discipline, spans, and testing expansion. The compile-time cost of proc-macro
dependencies is in the Cargo chapter; `trybuild` and snapshot testing are in the testing chapter.

Macros are the abstraction of last resort. They defeat type inference, produce poor error messages,
resist `go to definition`, slow compilation, and are invisible to most refactoring tools. Reach for
them only when generics, traits, and functions genuinely cannot express the pattern.
## Contents

- **When to use a macro**
  - RS-MACRO-01 [M] Exhaust functions, generics, and traits first
  - RS-MACRO-02 [S] Know the legitimate reasons for a macro
  - RS-MACRO-03 [M] Do not write a macro to save typing at one call site
  - RS-MACRO-04 [M] Hold macro-generated public API to the same documentation standard
  - RS-MACRO-05 [S] Expand to a call into a normal function
  - RS-MACRO-06 [S] Consider committed generated source instead of a proc macro

- **`macro_rules!`**
  - RS-MACRO-07 [S] Prefer `macro_rules!` to a proc macro whenever it suffices
  - RS-MACRO-08 [S] Export deliberately and re-export through the module system
  - RS-MACRO-09 [M] Refer to items by absolute path with `$crate`
  - RS-MACRO-10 [M] Choose the tightest fragment specifier
  - RS-MACRO-11 [M] Parenthesize interpolated expressions
  - RS-MACRO-12 [M] Evaluate each captured expression exactly once
  - RS-MACRO-13 [S] Wrap multi-statement expansions in a block
  - RS-MACRO-14 [S] Accept a trailing comma in every list-taking macro
  - RS-MACRO-15 [S] Emit a helpful `compile_error!` from a catch-all arm
  - RS-MACRO-16 [S] Test macros with `trybuild` and ordinary unit tests
  - RS-MACRO-17 [M] Do not rely on hygiene to protect you from caller identifiers

- **Procedural macros**
  - RS-MACRO-18 [M] Reserve proc macros for derives and genuine syntax extensions
  - RS-MACRO-19 [M] Split the proc-macro crate from the crate that re-exports it
  - RS-MACRO-20 [S] Enable only the `syn` features you need
  - RS-MACRO-21 [M] Emit errors at the correct span, never by panicking
  - RS-MACRO-22 [S] Report all the errors you can find, not just the first
  - RS-MACRO-23 [M] Generate hygienic code with absolute paths
  - RS-MACRO-24 [M] Do not generate `unsafe` unless the derive's contract makes it sound
  - RS-MACRO-25 [S] Keep generated code small and delegating
  - RS-MACRO-26 [S] Make expansion inspectable and test it

---

## When to use a macro

### RS-MACRO-01 [M] Exhaust functions, generics, and traits first

In order: a function, a generic function, a trait with a blanket impl, a const generic, a builder.

**Why:** each of those is discoverable in autocomplete, type-checked at its definition site rather
than at every call, steppable in a debugger, and renameable by tooling. A macro is none of these.
The ordering is by how much the tooling still works.

**Check:** for each macro, which of the five was tried and why did it fail? "It would need a type
parameter" is not a failure.

```rust
// verified
/// A function does this, so no macro is warranted.
#[must_use]
pub fn kib(count: u64) -> u64 {
    count * 1024
}
```

### RS-MACRO-02 [S] Know the legitimate reasons for a macro

Variadic arguments (`vec!`, `format!`); implementing a trait across many concrete types;
generating code from a declarative table; capturing an expression unevaluated (`assert!`,
`matches!`, lazy logging); and boilerplate that genuinely needs identifiers or syntax as input.

**Why:** all five are things the type system cannot express. Naming them makes the boundary
checkable — a macro whose reason is not on this list needs a written justification.

**Check:** which of the five applies? If none, see RS-MACRO-03.

```rust
// verified
/// A declarative macro where a function genuinely cannot express the shape.
macro_rules! field_names {
    ($($name:ident),+ $(,)?) => {
        [$(stringify!($name)),+]
    };
}

#[must_use]
pub fn names() -> [&'static str; 3] {
    field_names![line, column, offset]
}
```

### RS-MACRO-03 [M] Do not write a macro to save typing at one call site

Nor to avoid a small amount of duplication in a single file, nor to build a DSL because it looks
clever.

**Why:** duplication is cheap and legible; a macro is expensive and opaque. Three similar lines cost
the reader nothing; a macro that generates them costs everyone who ever has to debug the expansion.

**Check:** how many call sites does the macro have? One or two, with no variadic or syntactic need,
means delete it.

### RS-MACRO-04 [M] Hold macro-generated public API to the same documentation standard

**Why:** users read the generated type's rustdoc, hit its errors, and see it in their backtraces —
they do not care that a macro produced it. Generated items with no docs fail `missing_docs` for a
reason (`references/documentation.md` RS-DOC-01).

**Check:** does the generated code carry `///` docs, `Debug`, and error messages you would accept in
hand-written code?

### RS-MACRO-05 [S] Expand to a call into a normal function

**Why:** it keeps the macro to a few lines and keeps the logic type-checked, unit-testable, and
steppable. The macro then does only the thing a function cannot — capture syntax, be variadic, defer
evaluation.

**Check:** how many lines does the expansion contain? More than a handful of statements usually
means a helper function is hiding inside.

### RS-MACRO-06 [S] Consider committed generated source instead of a proc macro

**Why:** generated `.rs` files you can read, diff, and set a breakpoint in beat a proc macro nobody
can inspect — especially for large, stable output like tables, FFI bindings, or protocol types. The
cost is a regeneration step (`references/modules.md` RS-MOD-11).

**Check:** does the generated code change less often than the crate does? Then generating it once is
cheaper than generating it on every build.

## `macro_rules!`

### RS-MACRO-07 [S] Prefer `macro_rules!` to a proc macro whenever it suffices

**Why:** no extra crate, no `syn`/`quote` in the build graph, no host-target compilation step that
blocks pipelining. The proc macro is a real cost imposed on every downstream build
(`references/build.md` RS-BUILD-54).

**Check:** does the macro need to inspect types, parse attributes, or generate impls from a struct's
fields? If not, `macro_rules!` will do.

### RS-MACRO-08 [S] Export deliberately and re-export through the module system

**Why:** `#[macro_export]` puts the macro at the crate root regardless of where it is defined, which
breaks the module organization you carefully built. `pub use` of the macro path restores it, so the
macro lives where its subject lives.

**Check:** is the macro reachable at a path that matches its concept, or only at the crate root?

```rust
// verified
/// `#[macro_export]` puts the macro at the crate root, so it is named like an item.
#[macro_export]
macro_rules! rs_style_bail_on_empty {
    ($slice:expr) => {
        if $slice.is_empty() {
            return None;
        }
    };
}

#[must_use]
pub fn first(values: &[u32]) -> Option<u32> {
    rs_style_bail_on_empty!(values);
    values.first().copied()
}
```

### RS-MACRO-09 [M] Refer to items by absolute path with `$crate`

`$crate::module::Item`, `::std::vec::Vec`.

**Why:** without it, the macro silently depends on whatever the caller happens to have imported —
so it works in your crate and fails, or worse, resolves to the wrong item, in theirs. This is the
single most common `macro_rules!` bug.

**Check:** does the expansion name any path that is not rooted at `$crate` or `::`?

```rust
// verified
/// Hygiene: the macro's own binding cannot capture or be captured by the caller's.
macro_rules! swapped {
    ($left:expr, $right:expr) => {{
        let tmp = $left;
        ($right, tmp)
    }};
}

#[must_use]
pub fn sample() -> (u32, u32) {
    let tmp = 7;
    swapped!(tmp, 9)
}
```

### RS-MACRO-10 [M] Choose the tightest fragment specifier

`expr`, `ident`, `ty`, `literal`, `path`, `block`, `pat` — not `tt`.

**Why:** `tt` accepts anything and defers every error to expansion, where the message points inside
your macro at tokens the user never wrote. A tight specifier rejects bad input at the call site with
a comprehensible error.

**Check:** grep for `:tt` outside a recursive muncher, where it is genuinely required.

### RS-MACRO-11 [M] Parenthesize interpolated expressions

`($a) * ($b)`, not `$a * $b`.

**Why:** without parentheses the caller's expression is spliced in raw and re-parsed in your
context, so `my_macro!(1 + 2, 3)` computes `1 + 2 * 3`. An `expr` fragment is atomic in most
positions, but the habit costs nothing and the exceptions are subtle.

**Check:** grep the expansion for `$` variables adjacent to an operator.

```rust
// verified
/// `expr` binds as a unit, so precedence at the call site cannot leak in.
macro_rules! doubled {
    ($value:expr) => {
        $value * 2
    };
}

#[must_use]
pub fn sample() -> u32 {
    doubled!(1 + 2)
}
```

### RS-MACRO-12 [M] Evaluate each captured expression exactly once

Bind it to a local first.

**Why:** a macro that expands `$x` twice evaluates the caller's side effect twice — `max!(v.pop(),
0)` pops twice — and the caller cannot see why. This is invisible at the call site, which is what
makes it dangerous rather than merely wrong.

**Check:** count the occurrences of each `$` variable in the expansion. More than one means bind it.

### RS-MACRO-13 [S] Wrap multi-statement expansions in a block

`{{ … }}`.

**Why:** the outer braces make the macro usable in expression position, and the inner ones scope the
temporaries so they do not leak into the caller's namespace or collide with their bindings.

**Check:** can the macro be used as the right-hand side of a `let`? If not, it needs the block.

### RS-MACRO-14 [S] Accept a trailing comma in every list-taking macro

`$(,)?`

**Why:** users write one, `rustfmt` adds one when the invocation wraps, and a macro that rejects it
produces a parse error that looks like a bug in the caller's code. It is four characters.

**Check:** does every repetition arm end with `$(,)?`?

```rust
// verified
/// `$( … ),* $(,)?` accepts a trailing comma, as every std macro does.
macro_rules! ids {
    ($($value:expr),* $(,)?) => { vec![$($value),*] };
}

#[must_use]
pub fn sample() -> Vec<u32> {
    ids![1, 2, 3,]
}
```

### RS-MACRO-15 [S] Emit a helpful `compile_error!` from a catch-all arm

**Why:** the default failure is `no rules expected this token in macro invocation`, which tells the
user nothing about what shape was expected. A final arm with
`compile_error!("expected `name = value`")` turns that into an instruction.

**Check:** invoke the macro wrongly and read the error. Would a new user know what to fix?

### RS-MACRO-16 [S] Test macros with `trybuild` and ordinary unit tests

**Why:** a macro's error messages are part of its interface and they regress silently — a
refactoring that changes arm order can turn a good message into the default one with nothing
failing. `trybuild` pins the messages; unit tests pin the success cases
(`references/testing.md` RS-TEST-36).

**Check:** is there a `tests/ui/` directory with a `.stderr` file per failure case?

### RS-MACRO-17 [M] Do not rely on hygiene to protect you from caller identifiers

**Why:** `macro_rules!` hygiene covers identifiers the *macro* introduces. Anything captured as
`$ident` belongs to the caller and can collide with the locals you named — so a caller passing an
identifier called `a` breaks the `max!` above. Prefix internal bindings distinctively when the macro
takes identifiers.

**Check:** does the macro take an `ident` fragment and also declare locals? Then the locals need
unlikely names.

## Procedural macros

### RS-MACRO-18 [M] Reserve proc macros for derives and genuine syntax extensions

**Why:** they live in a separate crate, must be compiled for the host before anything depending on
them can build, and therefore block build pipelining for every downstream user. That cost is worth
it for `serde`'s derive and not worth it for saving ten lines.

**Check:** how many lines of hand-written code does the macro replace per use, and how many uses are
there? Multiply before deciding.

### RS-MACRO-19 [M] Split the proc-macro crate from the crate that re-exports it

`mycrate-derive` (proc macro only) and `mycrate` (re-exports the derive behind a feature).

**Why:** a `proc-macro = true` crate can export nothing but macros, so it cannot hold your types.
Splitting also lets users who do not want the derive turn it off and skip the compile cost
(`references/build.md` RS-BUILD-16).

**Check:** does a user depend on one crate, and can they disable the derive?

### RS-MACRO-20 [S] Enable only the `syn` features you need

**Why:** `syn`'s `full` feature parses the entire Rust grammar and is a measurable compile-time tax
on everyone downstream — for a derive that only reads struct fields, `derive` alone is enough.

**Check:** is `syn` declared with `default-features = false` and an explicit feature list?

### RS-MACRO-21 [M] Emit errors at the correct span, never by panicking

`syn::Error::new_spanned(field, "…").to_compile_error()`.

**Why:** a panic in a proc macro surfaces as an internal-looking compiler error with no user
location, so the user cannot tell which of their fields is wrong. A spanned error puts the squiggle
under the offending token, which is the whole difference between usable and not.

**Check:** grep the proc-macro crate for `panic!`, `unwrap`, and `expect`. Each is a message a user
will see.

### RS-MACRO-22 [S] Report all the errors you can find, not just the first

`syn::Error::combine`.

**Why:** a user with five bad field attributes otherwise gets five build-edit cycles. Accumulating
is the same argument as `references/errors.md` RS-ERR-31, applied at compile time where the cycle is
slower.

**Check:** does the macro return on the first bad field?

### RS-MACRO-23 [M] Generate hygienic code with absolute paths

`::core`, `::std`, `$crate`-equivalent absolute paths; prefix generated identifiers distinctively.

**Why:** proc macros have no hygiene by default for the paths they emit, so generated code that says
`Result` resolves to whatever the user has in scope — including a local type alias with different
type parameters. Generated locals collide the same way (RS-MACRO-17).

**Check:** does the `quote!` output name any path without a leading `::` or crate root?

### RS-MACRO-24 [M] Do not generate `unsafe` unless the derive's contract makes it sound

And then document the contract on the derive itself.

**Why:** a derive that emits `unsafe impl Send` or a transmute is asserting an invariant on behalf
of a user who wrote one line and read no documentation. If the derive cannot check the invariant, it
must be an `unsafe` trait the user opts into explicitly (`references/unsafe.md` RS-UNSAFE-20).

**Check:** grep the `quote!` blocks for `unsafe`. For each, what stops a user from deriving it on a
type where it is false?

### RS-MACRO-25 [S] Keep generated code small and delegating

**Why:** expanding to two hundred lines per field multiplies compile time and binary size across
every user of the derive. Expanding to a call into a generic helper in the runtime crate keeps the
generated part to a few lines (RS-MACRO-05).

**Check:** run `cargo expand` on a representative type. How many lines per field?

### RS-MACRO-26 [S] Make expansion inspectable and test it

`cargo expand` in the contributor docs; snapshot tests of the output; `trybuild` for the error
messages.

**Why:** the expansion is the actual code that ships, and without a snapshot nobody notices when a
refactor changes it. `cargo expand` in `CONTRIBUTING.md` is what lets a contributor debug the macro
at all (`references/testing.md` RS-TEST-28).

**Check:** is there a snapshot test for at least one representative input, and is it reviewed rather
than auto-accepted?
