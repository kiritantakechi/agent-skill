# Review protocol

How to audit existing Rust against this standard. Read this before reviewing; read the domain files
as the code demands them.

## Severity model

Report every finding with one of these labels. The label sets the ordering of the review and tells
the author what must change before merge.

| Severity | Meaning | Examples |
|---|---|---|
| **Unsound** | Corrupts memory or data, or crashes the runtime, from code that looks safe | Missing `// SAFETY:` proof that is actually wrong, manual `Send`/`Sync`, transmute between unspecified layouts |
| **Stale** | A spelling the target superseded — fails to build, or worse, builds and means something else | `lazy_static` where `LazyLock` fits, `fetch_update`, `#[async_trait]` without `dyn`, a pre-2024 `unsafe fn` body with no inner `unsafe` |
| **Incorrect** | Produces wrong results or crashes on reachable input | `unwrap` on user input, silent `as` truncation, off-by-one, swallowed error |
| **Contract** | Breaks or under-specifies the public surface | Undocumented panic, missing `# Errors`, leaked dependency type, breaking change shipped as a patch |
| **Design** | Works, but the shape will cost later | Concrete type used across a module boundary, `Arc<Mutex<_>>` where partitioning fits, stringly-typed config, god module, a branch that exists for one input |
| **Performance** | Measurable, avoidable cost | Allocation in a hot loop, unbuffered I/O, `println!` per line, `collect` in the middle of a pipeline |
| **Style** | Idiom and readability | `for`+`push` instead of `collect`, `&Vec<T>` parameter, naming, import grouping |

Unsound, Stale and Incorrect findings block a merge. Contract findings block a release. Design and
Performance findings need a decision, not necessarily a change. Style findings are batched — do not
spend a review's attention on them while an Unsound or Incorrect finding sits unaddressed.

## Review order

Do not read the diff top to bottom. Read in this order, because a finding at each stage can
invalidate the work of reading the next.

1. **Soundness.** Every `unsafe` block: does the `// SAFETY:` comment state a real precondition, and
   is it actually established at that point? Every manual `Send`/`Sync`/`unsafe impl`. Every
   `transmute`, raw pointer, and `repr`. (`RS-UNSAFE`)
2. **Panics and error handling.** Grep for `unwrap`, `expect`, `panic!`, `todo!`, `unreachable!`,
   `[` indexing, integer arithmetic on untrusted values, and `as` casts. Each one is either
   justified in a comment or a finding. (`RS-ERR`, RS-DATA-10)
3. **Public API.** What is newly `pub`? Is it documented? Is it the surface you would want to
   support for five years? Does it leak a dependency's types? Would `cargo semver-checks` complain?
   (`RS-API`, `RS-DOC`)
4. **Concurrency.** Lock scopes, lock ordering, `.await` while holding a lock, unbounded channels,
   detached tasks, shutdown paths. (`RS-CONC`)
5. **Data model.** Are illegal states representable? Are there `bool` parameters, paired `Option`s,
   or stringly-typed fields that want an enum? (`RS-DATA`, RS-API-23 … RS-API-26)
6. **Function bodies.** Now read the code. Loops that are pipelines, `mut` that folds away, clones
   that borrows would remove, allocation in loops. (`RS-FUNC`, `RS-OWN`, `RS-PERF`)
7. **Tests.** Do they test the contract or the implementation? Is the error path covered? Would they
   catch the bug this change fixes? (`RS-TEST`)
8. **Symmetry.** Unpaired operations, sibling functions disagreeing on argument order, error
   variants with uneven context, two mechanisms for one concept, a branch that exists for one input.
   (RS-API-52 … RS-API-56, RS-NAME-24, RS-MOD-36 … RS-MOD-38)
9. **Manifest and lints.** New dependencies justified? Features additive? Lints still enforced?
   (`RS-BUILD`)

## Mechanical pass

Run these before reading anything, and report what could not be run rather than implying it passed.

```bash
# fragment — the commands, in the order to run them
cargo fmt --check
CARGO_BUILD_WARNINGS=deny cargo clippy --all-targets --all-features
cargo test --all-features
cargo test --no-default-features
CARGO_BUILD_WARNINGS=deny cargo doc --no-deps --all-features
cargo semver-checks            # if the crate is published
cargo +nightly miri test       # if the crate contains `unsafe`
cargo audit                    # or: cargo deny check
```

The clippy line above already denies `unwrap`, `expect`, `dbg!`, an `unsafe` block without `SAFETY`,
a lossy `as` cast and a `&Vec` parameter. Fast greps for what no shipped lint decides:

```bash
# fragment — each hit is a place to read, not a finding
rg -n 'Arc<Mutex<|Rc<RefCell<'
rg -n '\.clone\(\)' -c                   # a count, then look at the outliers
rg -n 'println!|eprintln!' src/          # in library code
rg -n -A3 'lock\(\)' src/ | rg -v 'lock\(\)' | rg '\.await'   # an await after a lock: guard alive?
rg -n '\.fetch_update\(|std::[iu](8|16|32|64|128|size)::(MAX|MIN)\b' src/   # RS-MIG-02
```

## Output format

Deliver reviews as a table ordered by severity, then a short prose section for the two or three
findings that deserve discussion.

```markdown
<!-- fragment — the shape of a review; the rows are examples -->
## Findings

| Severity | Rule | Location | Finding | Fix |
|---|---|---|---|---|
| Incorrect | RS-ERR-03 | `src/config.rs:88` | `unwrap()` on a user-supplied path | Return `Error::Config` and propagate with `?` |
| Design | RS-API-23 | `src/search.rs:31` | Three `bool` parameters in `search()` | Replace with `SearchOptions` or three two-variant enums |
| Performance | RS-PERF-08 | `src/scan.rs:54` | `String` allocated per line | Hoist the buffer and `clear()` per iteration |

## Discussion

<the two or three findings where the right answer depends on context the author
has and you do not — with the trade-off stated and a recommendation>
```

Rules for the review itself:

- **Cite the rule ID.** It makes the standard checkable and the review impersonal.
- **Give the fix, not just the complaint.** A finding without a suggested change is a chore assigned
  to someone else.
- **Do not deliver a review that is only praise.** If the code is genuinely good, say so in one line
  and spend the rest on the three most valuable improvements. There are always three.
- **Do not pad with style findings.** Batch them at the end under one row, or offer to apply them
  directly.
- **Separate "this is wrong" from "I would have done it differently".** Only the first is a finding;
  the second is a discussion item, clearly labelled.
- **Say what you did not check.** A review that silently skipped the `unsafe` module is worse than
  one that says it did.

## Refactoring a codebase to this standard

Do it in this order, one mechanical step per commit, so that each commit is reviewable and
revertible:

1. Add `[lints]` at `warn`, commit the noise, then fix by lint category — one category per commit.
2. Replace `unwrap`/`expect` with real errors, introducing the error type first and converting
   module by module.
3. Fix signatures: `&Vec<T>` → `&[T]`, over-tight bounds, owned parameters that should borrow. These
   are usually non-breaking and mechanical.
4. Convert loops to pipelines only where it shortens the code — this is the step most likely to
   introduce bugs, so it goes after the safety net of tests is in place, and never in the same
   commit as a behaviour change.
5. Add documentation and `#[must_use]`, then turn `missing_docs` to `deny`.
6. Escalate the lint levels to `deny` and add the CI jobs.

State up front which of these steps you are doing, and do not mix a behavioural change into any of
them.
