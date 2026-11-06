# Macros: `macro_rules!` and Procedural Macros

Scope: when a macro is the right tool and when it is not, `macro_rules!` mechanics — fragment
specifiers, hygiene, `$crate`, trailing commas, diagnostics — and procedural macros: their build
cost, crate split, `syn`/`quote` discipline, spans, and testing expansion. `trybuild` and snapshot
testing in general are in the testing chapter.

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
  - RS-MACRO-07 [S] Export deliberately and re-export through the module system
  - RS-MACRO-08 [M] Refer to items by absolute path in every expansion
  - RS-MACRO-09 [M] Choose the tightest fragment specifier
  - RS-MACRO-10 [M] Parenthesize interpolated expressions
  - RS-MACRO-11 [M] Evaluate each captured expression exactly once
  - RS-MACRO-12 [S] Wrap multi-statement expansions in a block
  - RS-MACRO-13 [S] Accept a trailing comma in every list-taking macro
  - RS-MACRO-14 [S] Emit a helpful `compile_error!` from a catch-all arm
  - RS-MACRO-15 [S] Test macros with `trybuild`, unit tests, and an expansion snapshot
  - RS-MACRO-16 [M] Do not rely on hygiene to protect you from caller identifiers

- **Procedural macros**
  - RS-MACRO-17 [M] Reserve proc macros for derives and genuine syntax extensions
  - RS-MACRO-18 [M] Split the proc-macro crate from the crate that re-exports it
  - RS-MACRO-19 [S] Enable only the `syn` features you need
  - RS-MACRO-20 [M] Emit errors at the correct span, never by panicking
  - RS-MACRO-21 [S] Report all the errors you can find, not just the first
  - RS-MACRO-22 [M] Do not generate `unsafe` unless the derive's contract makes it sound

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

Variadic arguments (`vec!`, `format!`); implementing a trait across many concrete types; generating
code from a declarative table; capturing an expression unevaluated (`assert!`, `matches!`, lazy
logging); and boilerplate that genuinely needs identifiers or syntax as input.

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
reason.

**Check:** does the generated code carry `///` docs, `Debug`, and error messages you would accept in
hand-written code?

### RS-MACRO-05 [S] Expand to a call into a normal function

A derive expands to a call into a generic helper in the runtime crate: a few generated lines per
field, not the logic itself.

**Why:** it keeps the logic type-checked, unit-testable, and steppable, and leaves the macro only
what a function cannot do — capture syntax, be variadic, defer evaluation. Two hundred generated
lines per field multiply compile time and binary size across every user of a derive.

**Check:** how many statements does the expansion contain? More than a handful means a helper
function is hiding inside. For a derive, `cargo expand` a representative type and count the lines
per field.

### RS-MACRO-06 [S] Consider committed generated source instead of a proc macro

**Why:** generated `.rs` files you can read, diff, and set a breakpoint in beat a proc macro nobody
can inspect — especially for large, stable output like tables, FFI bindings, or protocol types. The
cost is a regeneration step (RS-MOD-09).

**Check:** does the generated code change less often than the crate does? Then generating it once is
cheaper than generating it on every build.

## `macro_rules!`

### RS-MACRO-07 [S] Export deliberately and re-export through the module system

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

### RS-MACRO-08 [M] Refer to items by absolute path in every expansion

`$crate::module::Item` and `::std::vec::Vec` in a `macro_rules!`; `::core`, `::std`, and the runtime
crate's absolute path in a proc macro's `quote!`.

**Why:** an expansion resolves in the caller's scope, so a bare path depends on whatever they
imported: it works in your crate and fails, or resolves to the wrong item, in theirs. A generated
`Result` can be the user's own alias with different type parameters.

**Check:** does the expansion, or the `quote!` output, name any path not rooted at `$crate` or `::`?

```rust
// verified
/// The ceiling every caller is clamped to.
pub mod limits {
    /// The largest batch the pipeline accepts.
    pub const MAX: u32 = 64;
}

/// `$crate` names this crate from wherever the macro is expanded, and `::core` the real `core`.
#[macro_export]
macro_rules! clamp_to_max {
    ($value:expr) => {
        ::core::cmp::min($value, $crate::limits::MAX)
    };
}

#[cfg(test)]
mod tests {
    #[test]
    fn clamps_from_another_module() {
        assert_eq!(clamp_to_max!(100), 64);
    }
}
```

### RS-MACRO-09 [M] Choose the tightest fragment specifier

`expr`, `ident`, `ty`, `literal`, `path`, `block`, `pat` — not `tt`. In edition 2024 `expr` also
matches `_` and `const { … }`, so an `$e:expr` arm placed before a `_` arm takes the `_` too: put
the `_` arm first, or ask for `expr_2021`, which excludes both.

**Why:** `tt` accepts anything and defers every error to expansion, where the message points inside
your macro at tokens the user never wrote. A tight specifier rejects bad input at the call site with
a comprehensible error.

**Check:** grep for `:tt` outside a recursive muncher, where it is genuinely required.

### RS-MACRO-10 [M] Parenthesize interpolated expressions

`($a) * ($b)`, not `$a * $b`.

**Why:** without parentheses the caller's expression is spliced in raw and re-parsed in your
context, so `my_macro!(1 + 2, 3)` computes `1 + 2 * 3`. An `expr` fragment is atomic in most
positions, but the habit costs nothing and the exceptions are subtle.

**Check:** grep the expansion for `$` variables adjacent to an operator.

```rust
// verified
/// Parenthesized, so the caller's expression is one operand wherever it is spliced.
macro_rules! doubled {
    ($value:expr) => {
        ($value) * 2
    };
}

#[must_use]
pub fn sample() -> u32 {
    doubled!(1 + 2)
}
```

### RS-MACRO-11 [M] Evaluate each captured expression exactly once

Bind it to a local first.

**Why:** a macro that expands `$x` twice evaluates the caller's side effect twice —
`max!(v.pop(), 0)` pops twice — and the caller cannot see why. This is invisible at the call site,
which is what makes it dangerous rather than merely wrong.

**Check:** count the occurrences of each `$` variable in the expansion. More than one means bind it.

### RS-MACRO-12 [S] Wrap multi-statement expansions in a block

`{{ … }}`, ending in an expression with no `;` after it. In expression position that trailing `;` is
an error (`semicolon_in_expressions_from_macros`, deny by default), for a macro from another crate
as much as your own.

**Why:** the outer braces make the macro usable in expression position, and the inner ones scope the
temporaries so they do not leak into the caller's namespace or collide with their bindings.

**Check:** can the macro be used as the right-hand side of a `let`? If not, it needs the block.

### RS-MACRO-13 [S] Accept a trailing comma in every list-taking macro

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

### RS-MACRO-14 [S] Emit a helpful `compile_error!` from a catch-all arm

**Why:** the default failure is `no rules expected this token in macro invocation`, which tells the
user nothing about what shape was expected. A final arm with `compile_error!("expected `name =
value`")` turns that into an instruction.

**Check:** invoke the macro wrongly and read the error. Would a new user know what to fix?

### RS-MACRO-15 [S] Test macros with `trybuild`, unit tests, and an expansion snapshot

`trybuild` pins the error messages, unit tests the success cases, and a reviewed snapshot of the
expansion the generated code. `CONTRIBUTING.md` says how to run `cargo expand`.

**Why:** a macro's messages and its expansion are both interface, and both regress silently:
reordering arms turns a good message into the default one, and a refactor changes the shipped code
with every test green (RS-TEST-30, RS-TEST-25).

**Check:** is there a `tests/ui/` directory with a `.stderr` file per failure case, and a snapshot
of one representative expansion, reviewed rather than auto-accepted?

### RS-MACRO-16 [M] Do not rely on hygiene to protect you from caller identifiers

An item a `macro_rules!` expansion defines, such as a helper `fn`, and any item or local a proc
macro generates, gets a distinctive prefix.

**Why:** `macro_rules!` hygiene covers only local variables and labels, so a defined item lands in
the caller's module and collides with theirs. A proc macro has no hygiene, so its locals collide
too.

**Check:** does the expansion introduce a name the caller did not pass in? Then that name needs the
prefix.

## Procedural macros

### RS-MACRO-17 [M] Reserve proc macros for derives and genuine syntax extensions

What `macro_rules!` can do, it does. A proc macro is for one that must inspect types, parse
attributes, or generate impls from a struct's fields: `serde_derive` and `thiserror` earn their
place, and a proc macro that saves ten lines does not.

**Why:** a proc macro lives in its own crate, pulls `syn` and `quote` into the build, and must be
compiled for the host before anything using it can start, which blocks pipelining for every
downstream build.

**Check:** does the macro inspect types, parse attributes, or read a struct's fields? If not, it is
a `macro_rules!`. For one that does, `cargo tree` the proc-macro crates and multiply the lines each
saves per use by its uses, against its build cost.

### RS-MACRO-18 [M] Split the proc-macro crate from the crate that re-exports it

`mycrate-derive` (proc macro only) and `mycrate` (re-exports the derive behind a feature).

**Why:** a `proc-macro = true` crate can export nothing but macros, so it cannot hold your types.
Splitting also lets users who do not want the derive turn it off and skip the compile cost
(RS-BUILD-14).

**Check:** does a user depend on one crate, and can they disable the derive?

### RS-MACRO-19 [S] Enable only the `syn` features you need

**Why:** `syn`'s `full` feature parses the entire Rust grammar and is a measurable compile-time tax
on everyone downstream — for a derive that only reads struct fields, `derive` alone is enough.

**Check:** is `syn` declared with `default-features = false` and an explicit feature list?

### RS-MACRO-20 [M] Emit errors at the correct span, never by panicking

`syn::Error::new_spanned(field, "…").to_compile_error()`.

**Why:** a panic in a proc macro surfaces as an internal-looking compiler error with no user
location, so the user cannot tell which of their fields is wrong. A spanned error puts the squiggle
under the offending token, which is the whole difference between usable and not.

**Check:** grep the proc-macro crate for `panic!`, `unwrap`, and `expect`. Each is a message a user
will see.

### RS-MACRO-21 [S] Report all the errors you can find, not just the first

`syn::Error::combine`.

**Why:** a user with five bad field attributes otherwise gets five build-edit cycles. Accumulating
is the same argument as RS-ERR-26, applied at compile time where the cycle is slower.

**Check:** does the macro return on the first bad field?

### RS-MACRO-22 [M] Do not generate `unsafe` unless the derive's contract makes it sound

And then document the contract on the derive itself.

**Why:** a derive that emits `unsafe impl Send` or a transmute is asserting an invariant on behalf
of a user who wrote one line and read no documentation. If the derive cannot check the invariant, it
must be an `unsafe` trait the user opts into explicitly (RS-UNSAFE-20).

**Check:** grep the `quote!` blocks for `unsafe`. For each, what stops a user from deriving it on a
type where it is false?
