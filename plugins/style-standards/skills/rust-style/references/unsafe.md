# RS-UNSAFE — `unsafe` and FFI

`unsafe` does not turn off the rules; it transfers responsibility for them from the compiler to you.
Every `unsafe` block is a proof obligation, and an unproven one is a latent memory-safety
vulnerability that safe callers cannot defend against.

The default posture is `unsafe_code = "forbid"` in `[lints.rust]`. These rules apply when that
default has been consciously overridden.

## Contents

- **Discipline**
  - RS-UNSAFE-01 [M] Forbid `unsafe` unless it is the crate's point, and justify each use
  - RS-UNSAFE-02 [M] Confine `unsafe` to the smallest module behind a safe API
  - RS-UNSAFE-03 [M] Give every `unsafe` block a `// SAFETY:` comment that says why it holds *here*
  - RS-UNSAFE-04 [M] Give every `unsafe fn` a mechanically checkable `# Safety` section
  - RS-UNSAFE-05 [M] Keep `unsafe` blocks to one operation
  - RS-UNSAFE-06 [M] Write the inner `unsafe { }` explicitly inside an `unsafe fn`
  - RS-UNSAFE-07 [M] Never expose a safe function whose safety depends on the caller
  - RS-UNSAFE-08 [M] Treat unsoundness as a security bug
  - RS-UNSAFE-09 [S] Prefer an audited crate to hand-rolled `unsafe`
  - RS-UNSAFE-10 [M!] Write the safe version first, keep it, and test the two against each other

- **Undefined behaviour and invariants**
  - RS-UNSAFE-11 [M] Know the UB list and check against it
  - RS-UNSAFE-12 [M] Treat `&mut T` as unique for its entire lifetime
  - RS-UNSAFE-13 [M] Never read uninitialized memory
  - RS-UNSAFE-14 [M] Give any layout-sensitive type an explicit `repr`, and assert its layout
  - RS-UNSAFE-15 [M] Treat `transmute` as the last resort
  - RS-UNSAFE-16 [M] Respect alignment
  - RS-UNSAFE-17 [M] Preserve pointer provenance
  - RS-UNSAFE-18 [M] Choose the `PhantomData` that matches the real relationship
  - RS-UNSAFE-19 [M] Decide variance deliberately and pin it with a test
  - RS-UNSAFE-20 [M] Make a trait `unsafe` when unsafe code relies on its implementors
  - RS-UNSAFE-21 [M] Write the argument next to a manual `unsafe impl Send`/`Sync`
  - RS-UNSAFE-22 [M] Uphold `Drop` correctness in unsafe containers

- **FFI**
  - RS-UNSAFE-23 [S] Generate bindings, and keep any hand-written declaration in the bindings module
  - RS-UNSAFE-24 [M] Never unwind across an `extern "C"` boundary
  - RS-UNSAFE-25 [M] Validate every pointer crossing the boundary
  - RS-UNSAFE-26 [M] Own the memory-management contract explicitly
  - RS-UNSAFE-27 [M] Convert strings deliberately at the boundary
  - RS-UNSAFE-28 [M] Mark FFI structs `#[repr(C)]` and assert their layout
  - RS-UNSAFE-29 [S] Keep the `-sys` crate thin

- **Verification**
  - RS-UNSAFE-30 [M!] Run the suite under Miri in CI
  - RS-UNSAFE-31 [S] Cover FFI paths with ASan, UBSan, and Valgrind, which Miri cannot reach
  - RS-UNSAFE-32 [M!] Have `unsafe` reviewed by a second person
  - RS-UNSAFE-33 [S] Track the `unsafe` block count and treat growth as a design signal

- Decided by tools

---

## Discipline

### RS-UNSAFE-01 [M] Forbid `unsafe` unless it is the crate's point, and justify each use

`unsafe_code = "forbid"` in `[lints.rust]`, as `assets/Cargo.toml` ships it. A crate that exists to
wrap FFI, raw memory, or a lock-free structure lowers it to `deny` and lets the one module that
needs it through. Each `unsafe` there answers to a measurement or a capability, never to "it should
be faster": most `unsafe` written for speed is neutral, because the safe version already optimized
to the same code.

**Why:** `unsafe` buys exactly two things — access to a capability safe Rust cannot express (FFI,
raw memory, a lock-free algorithm) and, occasionally, speed. Requiring evidence keeps the proof
obligations you take on proportional to what you actually get.

**Check:** is `unsafe_code` forbidden in the manifest (the `unsafe_code` row), or is a capability
the crate's purpose? For each `unsafe` block, which of the two justifications applies? If "speed",
find the benchmark; if there is none, delete the block and rerun the tests.

```rust
// verified
/// The safe form is fast enough and has no proof obligation at all.
#[must_use]
pub fn sum(values: &[u32]) -> u64 {
    values.iter().map(|&value| u64::from(value)).sum()
}
```

### RS-UNSAFE-02 [M] Confine `unsafe` to the smallest module behind a safe API

Confine `unsafe` to the smallest possible module, wrapped in a safe API that upholds the invariant
for all callers. The unit of review is the module, because that is the unit within which the
invariant can be checked.

**Why:** soundness is a property of a whole encapsulation boundary, not of a line. If a private
field can be set from anywhere in a 3000-line module, the proof has to consider all 3000 lines;
behind a 100-line module with a narrow API, it considers 100.

**Check:** for each `unsafe` block, identify the smallest region that could break its invariant. If
that region is larger than the module, the boundary is wrong.

```rust
// verified
/// The `unsafe` is confined to this module; the public surface is entirely safe.
#[derive(Debug)]
pub struct Slots {
    data: Vec<u32>,
}

impl Slots {
    #[must_use]
    pub fn new(data: Vec<u32>) -> Self {
        Self { data }
    }

    /// Safe for every caller: the bound is checked here, once.
    #[must_use]
    pub fn get(&self, index: usize) -> Option<u32> {
        (index < self.data.len()).then(|| {
            // SAFETY: `index < self.data.len()` was just checked, and `self.data`
            // is not mutated between the check and the read.
            unsafe { *self.data.get_unchecked(index) }
        })
    }
}
```

### RS-UNSAFE-03 [M] Give every `unsafe` block a `// SAFETY:` comment that says why it holds *here*

Every `unsafe` block carries a `// SAFETY:` comment stating which precondition holds and *why it
holds here* — referencing the specific invariant, bound check, or earlier assertion. Enforce it with
`clippy::undocumented_unsafe_blocks` at deny.

**Why:** the comment is the proof. Restating the precondition ("the pointer must be valid") without
saying what establishes it is not a proof, and it is exactly the form that survives a refactor which
invalidates it — because nobody notices that the justification no longer refers to anything real.

**Check:** read each `// SAFETY:` comment without the code. It should name a specific fact — a check
on line N, a type invariant, a caller obligation — not a restatement of the rule.

### RS-UNSAFE-04 [M] Give every `unsafe fn` a mechanically checkable `# Safety` section

Every `unsafe fn` has a `# Safety` section listing the caller's obligations precisely enough to be
checked mechanically. Every `*_unchecked` method is `unsafe` and documents the check it skips.

**Why:** `unsafe fn` moves the obligation to the caller, and a caller can only discharge an
obligation that is written down in checkable terms. "Must be valid" is not checkable; "`idx` must be
less than `len()`" is.

**Check:** for each `unsafe fn`, write the `// SAFETY:` comment a caller would need using only the
docs. If you cannot, the section is inadequate. `missing_safety_doc` catches a section that is
missing; only reading catches one that says nothing.

```rust
// verified
/// Reads the element at `index` without a bounds check.
///
/// # Safety
/// `index` must be strictly less than `values.len()`.
#[must_use]
pub unsafe fn get_unchecked(values: &[u32], index: usize) -> u32 {
    // SAFETY: the caller guarantees `index < values.len()`.
    unsafe { *values.get_unchecked(index) }
}
```

### RS-UNSAFE-05 [M] Keep `unsafe` blocks to one operation

Keep `unsafe` blocks small — ideally one operation. A twenty-line `unsafe` block means the reviewer
must verify twenty operations rather than one, and the `// SAFETY:` comment cannot honestly cover
them all.

**Why:** the cost of review is superlinear in block size, because the operations interact. One
comment above twenty statements is almost always a comment about the first one.

**Check:** count statements per `unsafe` block. More than two, and ask which of them actually needed
to be inside. A crate that wants the count enforced turns on
`clippy::multiple_unsafe_ops_per_block`, a restriction lint the shipped table leaves off.

### RS-UNSAFE-06 [M] Write the inner `unsafe { }` explicitly inside an `unsafe fn`

In edition 2024, `unsafe_op_in_unsafe_fn` is on: the body of an `unsafe fn` is not automatically an
unsafe block. Write the inner `unsafe { }` explicitly. This is a feature — it distinguishes "this
function has preconditions" from "this line does something dangerous".

**Why:** the two meanings were conflated before edition 2024, which meant a 200-line `unsafe fn` was
entirely unsafe with no indication of which lines mattered. Separating them makes the dangerous
lines visible and lets most of the body be checked normally.

**Check:** the compiler warns. A raw-pointer dereference in an `unsafe fn` body with no inner block
produces `warning[E0133]` under edition 2024 and nothing under 2021, so a crate that changed edition
without clearing its warnings has this outstanding.

```rust
// verified
/// In edition 2024 the body of an `unsafe fn` is not implicitly unsafe.
///
/// # Safety
/// `ptr` must be non-null, aligned, and valid for one initialized `u32`.
#[must_use]
pub unsafe fn read_one(ptr: *const u32) -> u32 {
    // SAFETY: the caller guarantees validity and alignment for one `u32`.
    unsafe { *ptr }
}
```

### RS-UNSAFE-07 [M] Never expose a safe function whose safety depends on the caller

Never expose a safe function whose safety depends on the caller doing something. If a function can
be misused into UB without `unsafe` at the call site, the function is unsound, no matter what the
docs say.

**Why:** the `unsafe` keyword at the call site is the entire mechanism by which Rust localizes
memory-safety review. A safe function with preconditions defeats it silently — reviewers auditing
`unsafe` will never look at the call, because there is nothing to look at.

**Check:** for each safe public function in an `unsafe`-using module, ask whether any input causes
UB. If yes, the function must be `unsafe` or must validate.

```rust
// verified
/// The bound is enforced inside, so no caller can reach undefined behaviour.
#[derive(Debug)]
pub struct Window<'data> {
    data: &'data [u8],
}

impl<'data> Window<'data> {
    #[must_use]
    pub fn new(data: &'data [u8]) -> Self {
        Self { data }
    }

    /// Safe for every input: an out-of-range request yields `None`.
    #[must_use]
    pub fn slice(&self, start: usize, len: usize) -> Option<&'data [u8]> {
        self.data.get(start..start.checked_add(len)?)
    }
}
```

### RS-UNSAFE-08 [M] Treat unsoundness as a security bug

Unsoundness is a security bug: it gets a patch release, an advisory, and a yank if severe — not a
"fixed on main" note.

**Why:** unsoundness in a published crate is exploitable by anyone downstream, and downstream cannot
detect it by reading their own code. The response has to match the exposure, which is the whole
dependency graph.

**Check:** does the project have a stated process for soundness reports — a `SECURITY.md`, a
contact, and a commitment to yank? If not, that is the finding.

### RS-UNSAFE-09 [S] Prefer an audited crate to hand-rolled `unsafe`

Prefer an existing, audited crate to hand-rolled `unsafe`. `bytemuck`, `zerocopy`, `memchr`,
`crossbeam`, and `slab` have already had the scrutiny your module will not get.

**Why:** these crates have had years of fuzzing, Miri runs, and adversarial review by people who
specialize in exactly this. Your version gets one author and one reviewer, and the failure mode is
memory corruption rather than a wrong answer.

**Check:** for each hand-written `unsafe` helper, search crates.io for the operation. If a
maintained crate does it, the burden is on you to say why yours is different.

```rust
// verified
/// An audited crate would do this; `str::find` already does, so no `unsafe` is written.
#[must_use]
pub fn first_index(haystack: &str, needle: char) -> Option<usize> {
    haystack.find(needle)
}
```

### RS-UNSAFE-10 [M!] Write the safe version first, keep it, and test the two against each other

Write the safe version first, test it, keep it, and gate the `unsafe` version behind a feature with
a differential test proving they agree (`RS-TEST-21`).

*Relaxed form:* in an internal binary, keep the safe version in a test rather than behind a feature
flag. What matters is that an independent implementation exists to disagree with the fast one.

**Why:** the safe implementation is the specification and the oracle (`references/testing.md`
RS-TEST-21), and in `unsafe` code the disagreement it catches is memory corruption, not a wrong
answer.

**Check:** is there a test that runs both implementations on the same input and compares? If the
safe version was deleted after the fast one worked, the oracle is gone.

## Undefined behaviour and invariants

### RS-UNSAFE-11 [M] Know the UB list and check against it

Know the list and check against it: dereferencing a dangling or misaligned pointer, aliasing `&mut`
with anything, producing an invalid value (a `bool` that is not 0/1, an out-of-range `char`, a null
`&T`, an uninitialized integer), breaking pointer provenance, data races, and a foreign exception
unwinding into Rust through an `extern "C"` boundary.

Reading a union field produces a value of its type, and a pattern that names a union field beside
other subpatterns may read it even when the rest does not match: test the tag first, then read the
field inside the matched arm. Accessing an `UnsafeCell`'s contents without going through `get` is
not on the list; std guarantees it.

**Why:** UB is not "might crash" — it is a licence for the optimizer to assume the case cannot
happen and delete the code around it. Reasoning about what the machine "would" do is the mistake;
the list is short enough to check mechanically.

**Check:** for each `unsafe` block, walk the seven categories and state which apply and why they are
satisfied. Anything you cannot answer is the finding.

### RS-UNSAFE-12 [M] Treat `&mut T` as unique for its entire lifetime

A `&mut T` is unique for its entire lifetime, even if you never write through it. Creating two from
the same source is UB immediately, not when they are used. Take a raw pointer with `&raw mut place`
or `&raw const place`, never by casting a reference, which creates the `&mut` the pointer exists to
avoid.

**Why:** LLVM is told `&mut` is `noalias`, and it reorders loads and stores on that promise. The UB
is in the *creation*, so "I only read through it" is not a defence — the miscompilation happens
regardless.

**Check:** grep for `&mut *` on raw pointers, for multiple `from_raw`/`as_mut` calls on the same
address, and for `as *mut`/`as *const` on a reference. Each needs an argument that only one is live,
or the `&raw` form.

```rust
// verified
/// One `&mut` at a time: the split proves the two halves cannot alias.
pub fn bump_both(values: &mut [u32]) {
    let mid = values.len() / 2;
    let (head, tail) = values.split_at_mut(mid);
    for value in head.iter_mut().chain(tail) {
        *value = value.saturating_add(1);
    }
}
```

### RS-UNSAFE-13 [M] Never read uninitialized memory

Uninitialized memory is UB to read, including "I will overwrite it first". Use `MaybeUninit<T>`, and
`assume_init` only after every byte is actually written.

**Why:** uninitialized memory is not "some arbitrary value" — it is a value the compiler may treat
as whatever is convenient, and differently at each read. Padding bytes count, which is why
`MaybeUninit` exists rather than a zeroed buffer.

**Check:** grep for `mem::uninitialized`, `mem::zeroed`, and `assume_init`. For each `assume_init`,
identify the code path that wrote every byte.

```rust
// verified
use std::mem::MaybeUninit;

/// `assume_init` only after every byte has actually been written.
#[must_use]
pub fn filled(value: u8) -> [u8; 8] {
    let mut buf: [MaybeUninit<u8>; 8] = [const { MaybeUninit::uninit() }; 8];
    for slot in &mut buf {
        slot.write(value);
    }
    // SAFETY: the loop above wrote every one of the eight slots.
    unsafe { MaybeUninit::<[u8; 8]>::from(buf).assume_init() }
}
```

### RS-UNSAFE-14 [M] Give any layout-sensitive type an explicit `repr`, and assert its layout

Rust's default layout is unspecified and may be reordered. Any type shared with C, mapped over
bytes, or relied on for field order needs an explicit `#[repr(C)]`, `#[repr(transparent)]`, or
`#[repr(u8)]`, and a compile-time assertion on its size, its alignment, and the offset of each field
the code relies on: `const _: () = assert!(…)`, with no crate needed.

**Why:** the default representation is deliberately unstable so the compiler can pack fields, so an
assumed field order is correct by luck. An assertion costs nothing at run time and turns a `repr`
change into a build failure; size and alignment alone miss two same-typed fields swapped.

**Check:** for each type crossing an FFI boundary or reinterpreted from bytes, find the `repr` and
the `size_of`, `align_of`, and `offset_of!` assertions.

```rust
// verified
use std::mem::offset_of;

/// Layout-sensitive, so the representation is explicit and asserted.
#[derive(Debug, Clone, Copy)]
#[repr(C)]
pub struct Header {
    pub magic: u32,
    pub version: u16,
    pub flags: u16,
}

const _: () = assert!(size_of::<Header>() == 8);
const _: () = assert!(align_of::<Header>() == 4);
const _: () = assert!(offset_of!(Header, flags) == 6);
```

### RS-UNSAFE-15 [M] Treat `transmute` as the last resort

Transmute is the last resort. Prefer `as` casts for numbers, `from_bits`/`to_bits` for floats,
`bytemuck`/`zerocopy` for plain-old-data reinterpretation, and pointer casts with explicit alignment
checks for the rest. `transmute` between types whose layouts are not both specified is UB.

**Why:** `transmute` is the one operation with no checks at all — not size beyond a compile-time
equality, not validity, not alignment, not provenance. Every alternative listed checks at least one
of those.

**Check:** grep for `transmute`. For each, name the specified layout of both sides; if either is a
default-`repr` Rust type, it is a violation.

```rust
// verified
/// `from_le_bytes` instead of `transmute`: no layout assumption, no `unsafe`.
#[must_use]
pub fn read_u32(bytes: &[u8]) -> Option<u32> {
    bytes.first_chunk().copied().map(u32::from_le_bytes)
}
```

### RS-UNSAFE-16 [M] Respect alignment

Respect alignment. `ptr::read_unaligned`/`write_unaligned` exist because a `*const u64` into a byte
buffer is not necessarily aligned, and on some targets that is a fault rather than a slowdown. A
field of a `#[repr(packed)]` struct is the same case: `&raw const packed.field` and
`read_unaligned`, never a reference, which is misaligned the moment it exists.

**Why:** x86 tolerates unaligned access, which is why this bug ships. On other targets it is a
SIGBUS, so the code passes CI and fails on a user's machine — the worst possible distribution of the
failure.

**Check:** grep for pointer casts that widen the pointee (`*const u8` to `*const u32` or larger).
Each needs an alignment check or the `_unaligned` variant.

```rust
// verified
/// Alignment is respected: a byte buffer is not assumed to be `u32`-aligned.
#[must_use]
pub fn read_u32_unaligned(bytes: &[u8]) -> Option<u32> {
    if bytes.len() < size_of::<u32>() {
        return None;
    }
    #[expect(
        clippy::cast_ptr_alignment,
        reason = "read_unaligned imposes no alignment requirement on the pointer"
    )]
    let ptr = bytes.as_ptr().cast::<u32>();
    // SAFETY: the length was checked above, and `read_unaligned` imposes no
    // alignment requirement on `ptr`.
    Some(u32::from_le(unsafe { ptr.read_unaligned() }))
}
```

### RS-UNSAFE-17 [M] Preserve pointer provenance

Preserve provenance: derive pointers from the pointer that owns the allocation, not by casting an
integer back. Use `wrapping_add` when the intermediate value may be out of bounds, and the
strict-provenance APIs where available.

**Why:** a pointer carries which allocation it may access, not just an address. Round-tripping
through `usize` discards that, and the optimizer is entitled to conclude the resulting pointer
cannot alias the object you meant.

**Check:** grep for `as usize` on pointers followed by `as *const`/`as *mut`. Each is a provenance
break unless it uses `with_addr`/`map_addr`. An integer-to-pointer `transmute` needs no grep:
`integer_to_ptr_transmutes` warns on it by default.

### RS-UNSAFE-18 [M] Choose the `PhantomData` that matches the real relationship

Choose `PhantomData` to match the real relationship: `PhantomData<T>` for ownership (affects drop
check and auto traits), `PhantomData<&'a T>` for a shared borrow, `PhantomData<*mut T>` to opt out
of `Send`/`Sync`, `PhantomData<fn() -> T>` for a covariant marker that owns nothing.

**Why:** each spelling declares a different thing to drop check, variance, and the auto traits.
Picking one because it silences the "unused parameter" error means declaring a relationship you did
not intend, and the consequence is silent unsoundness rather than an error.

**Check:** for each `PhantomData`, state which of the four you meant and confirm the spelling
matches. The usual mismatch is `PhantomData<T>` on a marker that owns no `T`, which makes it `!Send`
whenever `T` is.

```rust
// verified
use std::marker::PhantomData;

/// `PhantomData<*mut T>` opts the handle out of `Send`/`Sync` deliberately.
#[derive(Debug)]
pub struct ThreadBound<T> {
    raw: usize,
    marker: PhantomData<*mut T>,
}

impl<T> ThreadBound<T> {
    #[must_use]
    pub fn new(raw: usize) -> Self {
        Self {
            raw,
            marker: PhantomData,
        }
    }
}
```

### RS-UNSAFE-19 [M] Decide variance deliberately and pin it with a test

Variance mistakes are silent unsoundness. If your type contains a raw pointer, decide deliberately
whether it should be covariant, contravariant, or invariant, and add a `compile_fail` test pinning
the decision (`RS-TEST-30`). Pin every other forbidden misuse the same way, such as a `Send` the
type must not have.

**Why:** variance is inferred from the fields and an auto trait from their types, so an innocuous
field change can let safe code reach unsoundness, such as a lifetime shortened that the `unsafe`
code assumed was long. Nothing warns, and the use-after-free appears far from the change.

**Check:** is there a `compile_fail` test that would fail if the type became covariant? Without one,
the property is not pinned.

### RS-UNSAFE-20 [M] Make a trait `unsafe` when unsafe code relies on its implementors

A trait whose implementors must uphold an invariant that unsafe code relies on is an `unsafe trait`,
with the obligation documented in a `# Safety` section on the trait itself. If a wrong
implementation only produces wrong answers, the trait stays safe and documents its contract loudly
(`references/traits.md` RS-TRAIT-11).

**Why:** if safe code can write a wrong implementation and thereby cause UB elsewhere, the trait is
the unsound part. `unsafe trait` is how the obligation is transferred to the implementor, which is
the only party who can discharge it.

**Check:** does any `unsafe` block assume a trait method returns something specific — a correct
length, a stable ordering, a valid pointer? Ask what a malicious implementation could do. If it can
cause UB, the trait must be `unsafe`.

```rust
// verified
/// The invariant is relied on by unsafe code, so the trait is `unsafe`.
///
/// # Safety
/// `LEN` must equal the number of bytes `encode` writes into the buffer.
pub unsafe trait FixedWidth {
    /// The exact number of bytes written by `encode`.
    const LEN: usize;

    /// Writes exactly `LEN` bytes.
    fn encode(&self, out: &mut Vec<u8>);
}
```

### RS-UNSAFE-21 [M] Write the argument next to a manual `unsafe impl Send`/`Sync`

Manual `unsafe impl Send`/`Sync` requires a written argument for why concurrent access is sound,
next to the impl. The auto-derive is almost always right; overriding it is where "it works on my
machine" races come from.

**Why:** the compiler withheld the auto impl for a reason, usually a raw pointer or a `Cell`: a type
that is not `Send` is telling you something true. Asserting it manually claims you have synchronized
what the compiler could not see, and that claim must be legible to the next reader.

**Check:** for each manual impl, does the adjacent comment explain what makes concurrent access
safe? "It is fine" is not an argument. An impl on a type the compiler would already derive it for is
noise: delete it.

```rust
// verified
/// Stands in for an FFI handle: an owned raw pointer, for which the compiler withholds `Send`.
/// Real code takes it from a C library that documents the handle as movable between threads;
/// a plain `Box<u64>` is already `Send` and needs none of this.
#[derive(Debug)]
pub struct Slot {
    raw: *mut u64,
}

// SAFETY: a `Slot` is the only owner of the allocation behind `raw`: `new` creates
// it, `drop` frees it, and no copy of the pointer escapes. Moving a `Slot` to
// another thread moves the only access with it.
unsafe impl Send for Slot {}

impl Slot {
    #[must_use]
    pub fn new(value: u64) -> Self {
        Self {
            raw: Box::into_raw(Box::new(value)),
        }
    }

    #[must_use]
    pub fn get(&self) -> u64 {
        // SAFETY: `raw` came from `Box::into_raw` in `new` and is freed only in `drop`.
        unsafe { *self.raw }
    }
}

impl Drop for Slot {
    fn drop(&mut self) {
        // SAFETY: `raw` came from `Box::into_raw` and is reclaimed exactly once, here.
        drop(unsafe { Box::from_raw(self.raw) });
    }
}
```

### RS-UNSAFE-22 [M] Uphold `Drop` correctness in unsafe containers

Uphold `Drop` correctness in unsafe containers: no double drop, no leak on panic in the middle of a
partially initialized buffer. Use a guard struct so that unwinding cleans up the prefix that was
initialized.

**Why:** a panic in the middle of initialization is the path nobody tests, and it is reachable from
any user-supplied `Clone` or iterator. Without a guard, unwinding either drops uninitialized slots
or drops nothing.

**Check:** for each loop that initializes raw memory, ask what happens if iteration `k` panics. If
the answer is not "the first `k` elements are dropped exactly once", add the guard.

## FFI

### RS-UNSAFE-23 [S] Generate bindings, and keep any hand-written declaration in the bindings module

Generate bindings with `bindgen` rather than hand-transcribing headers, and re-generate them in CI
or check them in with the exact bindgen version recorded. A declaration you do write is an
`unsafe extern "C" { … }` block, and a function no input can make unsound is marked `pub safe fn` in
it, so its callers need no `unsafe`. Bindings keep the C names they mirror: the module that holds
them carries the casing lints' `#[expect(…, reason = "the names mirror the C header")]`, and no
other module does.

**Why:** hand-transcription silently encodes the layout of one platform's headers, and drifts the
moment the C library changes a field. The failure is a struct-layout mismatch, which corrupts memory
rather than failing to compile.

**Check:** are the bindings generated, and is the generation reproducible? A hand-written `extern`
block mirroring a non-trivial C struct is a finding, and so is an `allow` or `expect` of
`non_snake_case`, `non_camel_case_types`, or `non_upper_case_globals` outside the bindings module.

```rust
// verified
use std::ffi::{c_char, c_int};

// `unsafe extern`: the block is the claim that these signatures match the C ones.
unsafe extern "C" {
    /// Takes nothing and cannot fail, so it is declared `safe`.
    pub safe fn getpid() -> c_int;

    /// Reads until a NUL, so a call stays `unsafe` and states its pointer contract.
    pub fn strlen(text: *const c_char) -> usize;
}

/// A safe item from an `unsafe extern` block is called like any function.
#[must_use]
pub fn process_id() -> c_int {
    getpid()
}
```

### RS-UNSAFE-24 [M] Never unwind across an `extern "C"` boundary

Never unwind across an `extern "C"` boundary. A Rust panic escaping an `extern "C"` function aborts
the process, and a foreign exception unwinding into Rust through `extern "C"` is undefined
behaviour. Wrap every exported entry point in `catch_unwind` and convert a panic into an error code;
where unwinding across the boundary is intended, declare `extern "C-unwind"`.

An exported `#[unsafe(no_mangle)]` function is never generic, which is a hard error, and it never
takes the name of a symbol std relies on — `memcpy`, `strlen`, `malloc` — with a different
signature, which `invalid_runtime_symbol_definitions` denies.

**Why:** the C frames have no unwinding tables and no destructors to run, so the unwinder cannot
proceed through them. The abort Rust substitutes is still a process death inside someone else's
program, which an error code avoids.

**Check:** every `pub extern "C" fn` and every `#[unsafe(no_mangle)]` function body is wrapped in
`catch_unwind`, and the error path maps to a documented return code. A std symbol redefined is the
`invalid_runtime_symbol_definitions` row.

```rust
// verified
use std::ffi::c_int;
use std::panic::catch_unwind;

const ERR_PANIC: c_int = -1;

/// A panic escaping `extern "C"` aborts the host process, so the boundary catches it.
#[unsafe(no_mangle)]
pub extern "C" fn mylib_length(len: c_int) -> c_int {
    catch_unwind(|| len.saturating_mul(2)).unwrap_or(ERR_PANIC)
}
```

### RS-UNSAFE-25 [M] Validate every pointer crossing the boundary

Validate every pointer crossing the boundary: null checks, alignment, and the length contract. A C
caller is not bound by your invariants and will eventually violate them. A C-variadic definition
(`...`, read through `core::ffi::VaList`) checks nothing at all: each `next_arg::<T>()` trusts the
caller for both the count and the type, so `# Safety` must state both.

**Why:** on the Rust side of an FFI boundary you are the trusted component, and the caller is
untrusted input in the security sense. Assuming a non-null, correctly sized pointer is assuming the
absence of the bug your API exists to survive.

**Check:** each `*const`/`*mut` parameter has a null check before use, and each pointer/length pair
has a documented contract stating who guarantees the length.

```rust
// verified
use std::ffi::c_char;

/// A C caller is untrusted input: the pointer is checked before it is used.
///
/// # Safety
/// If `ptr` is non-null it must point to a NUL-terminated C string that stays
/// valid for the duration of the call.
#[must_use]
pub unsafe fn c_str_len(ptr: *const c_char) -> usize {
    if ptr.is_null() {
        return 0;
    }
    // SAFETY: `ptr` was checked non-null, and the caller guarantees it is a
    // valid NUL-terminated string for the duration of this call.
    unsafe { std::ffi::CStr::from_ptr(ptr) }.count_bytes()
}
```

### RS-UNSAFE-26 [M] Own the memory-management contract explicitly

Own the memory-management contract explicitly: whoever allocates, frees. Export a `mylib_free` for
anything you allocate, document it, and never free a pointer that C allocated with its own
allocator. Hand memory out with `Box::into_raw` or `Box::into_non_null` and take it back with
`from_raw`/`from_non_null`; for a buffer, `Vec::into_raw_parts` or `Vec::into_parts` and the
matching `from_*` keep the capacity the free function needs. Never `Box::leak` and then rebuild a
`Box` from the leaked reference.

**Why:** Rust's allocator and the C allocator are different, and freeing across them is UB even when
both are "malloc" on your machine. Making the ownership explicit in the API is what prevents the
caller from guessing.

**Check:** for each pointer you return, is there a documented free function? For each pointer you
free, did your allocator produce it?

### RS-UNSAFE-27 [M] Convert strings deliberately at the boundary

Convert strings deliberately at the boundary. `CStr`/`CString` for NUL-terminated C strings, and
remember that they are bytes, not UTF-8 — use `to_str()` and handle the error rather than
`to_string_lossy()` silently corrupting data. C string literals (`c"…"`) avoid a class of NUL
mistakes.

**Why:** C strings carry no encoding guarantee, and `to_string_lossy` converts a data-integrity
problem into replacement characters that survive into storage. The lossy path is right for a
diagnostic message and wrong for anything you keep.

**Check:** grep for `to_string_lossy`. Each use must be on a path where corrupting the data is
acceptable — typically only logging.

```rust
// verified
use std::ffi::CStr;

/// C strings are bytes: `to_str` surfaces invalid UTF-8 instead of corrupting it.
///
/// # Errors
/// Returns [`std::str::Utf8Error`] when the bytes are not valid UTF-8.
pub fn as_text(raw: &CStr) -> Result<&str, std::str::Utf8Error> {
    raw.to_str()
}
```

### RS-UNSAFE-28 [M] Mark FFI structs `#[repr(C)]` and assert their layout

Mark FFI structs `#[repr(C)]` and assert their size, alignment and field offsets with RS-UNSAFE-14's
`const` assertions, taking the numbers from the C side. A silent layout mismatch produces garbage
that looks like a logic bug. Declare a C function that returns `void` with no return type, never
`-> c_void`, which `c_void_returns` warns on. On x86_64, build FFI crates with 1.99.1 or later,
which fixes a miscompilation of FFI `bool` returns.

**Why:** `repr(C)` fixes the field order but does not verify that your field *types* match the C
header. The assertion is what catches a `long` that is 32 bits on one platform and 64 on another.

**Check:** each FFI struct has the `const` layout assertions of RS-UNSAFE-14, and the expected
numbers came from the C side rather than from Rust. A `-> c_void` is the `c_void_returns` row.

```rust
// verified
/// The FFI struct's layout is asserted against the C definition at compile time.
#[derive(Debug, Clone, Copy)]
#[repr(C)]
pub struct Point {
    pub x: f64,
    pub y: f64,
}

const _: () = assert!(size_of::<Point>() == 16);
const _: () = assert!(align_of::<Point>() == 8);
```

### RS-UNSAFE-29 [S] Keep the `-sys` crate thin

Keep the `-sys` crate thin: raw declarations, the build script, and nothing else. Put the safe
wrapper in a separate crate, which is the ecosystem convention (`libgit2-sys` / `git2`) and lets
consumers audit the unsafe surface in one place.

**Why:** the split gives the whole ecosystem one crate to audit per C library rather than one per
wrapper, and it lets a consumer who needs the raw API skip your abstraction without vendoring.

**Check:** does the `-sys` crate contain any safe abstraction? If so, it belongs one level up.

## Verification

### RS-UNSAFE-30 [M!] Run the suite under Miri in CI

Run the test suite under Miri (`cargo +nightly miri test`) in CI for every crate containing
`unsafe`. It catches UB that produces correct behaviour on your machine today and a crash on a
user's machine next year. Keep secrets out of the Miri job's environment, and out of any job that
writes a `target/` cache a pull request can read. A hand-rolled concurrent structure also runs under
`loom` or ThreadSanitizer (`references/concurrency.md` RS-CONC-40).

*Relaxed form:* run Miri locally before each release rather than on every push. What is not
acceptable is never having run it.

**Why:** Miri is an interpreter that checks the rules the optimizer assumes — aliasing, provenance,
alignment, initialization. It finds the class of bug that testing cannot, because testing observes
one compilation on one target.

**Check:** the CI pipeline contains a Miri job, and it covers the tests that exercise the `unsafe`
paths rather than only the trivial ones.

### RS-UNSAFE-31 [S] Cover FFI paths with ASan, UBSan, and Valgrind, which Miri cannot reach

Miri cannot see through FFI. For those paths, use ASan, UBSan, and Valgrind on the C side, and keep
the Rust side thin enough to reason about.

**Why:** Miri interprets Rust, so a call into C is an opaque wall. Knowing which tool covers which
side of the boundary is what stops "Miri is clean" from being read as "the crate is clean".

**Check:** for a crate with FFI, is there a sanitizer job covering the C side? If Miri is the only
tool, the FFI paths are unverified.

### RS-UNSAFE-32 [M!] Have `unsafe` reviewed by a second person

Have `unsafe` code reviewed by a second person, and say in the pull request template that `unsafe`
requires it. Self-review of soundness proofs has a poor track record.

*Relaxed form:* on a solo project, re-review the `unsafe` block in a separate sitting from the one
that wrote it, with the `// SAFETY:` comment read first and the code checked against it.

**Why:** the author's mental model is precisely what produced the gap, so re-reading with the same
model finds nothing. A second reader has to reconstruct the argument from the comment, which is also
a test of whether the comment is adequate.

**Check:** does the project require a second approver for diffs touching `unsafe`? A blanket
single-approver policy does not meet this.

### RS-UNSAFE-33 [S] Track the `unsafe` block count and treat growth as a design signal

Track the count of `unsafe` blocks in the crate (`cargo geiger` or a grep in CI) and treat growth as
a design signal. A number that only goes up means the safe abstraction is not being found.

**Why:** individual `unsafe` blocks are each justified in isolation, so nothing pushes back on the
total. A tracked count is the only feedback that the encapsulation strategy is failing.

**Check:** is the count recorded per release? A crate where it doubled without a new capability is
the finding.

## Decided by tools

A tool settles these on its own; the shipped configuration enables each at the level shown.

| Tool | Lint | Level | Forbids |
|---|---|---|---|
| rustc | `unsafe_code` | forbid | any `unsafe` — `deny` only in a crate whose point is `unsafe` (RS-UNSAFE-01) |
| clippy | `missing_safety_doc` | warn | a public `unsafe fn` with no `# Safety` section |
| rustc | `integer_to_ptr_transmutes` | warn | a `transmute` from an integer to a pointer, which carries no provenance |
| rustc | `invalid_runtime_symbol_definitions` | deny | an exported symbol std relies on, defined with another signature |
| rustc | `c_void_returns` | warn | a C function declared `-> c_void` instead of with no return type |
