# Documentation

Scope: what a codebase says about itself: the comments that document an item and their shape,
examples that run, the comments that explain the code, and the documents beside it, the changelog
and the README. What a thing is called is the naming chapter's.

## Contents

- **Documenting an item**
  - AS-DOC-01 [M] Document every public item
  - AS-DOC-02 [M] Open with one sentence that stands alone, then a blank line
  - AS-DOC-03 [M] State the contract a caller can rely on, never how the code works
  - AS-DOC-04 [M] Document the errors a caller can get, and when
  - AS-DOC-05 [M] Use the ecosystem's fixed form for each part of a contract
  - AS-DOC-06 [M] Write an example that the toolchain runs
- **Comments**
  - AS-DOC-07 [M] Say why in a comment, never what
  - AS-DOC-08 [S] Write a comment as a sentence
  - AS-DOC-09 [M] Delete commented-out code
  - AS-DOC-10 [M] Change a comment in the same edit as the code it describes
- **Beside the code**
  - AS-DOC-11 [S] Keep a changelog with a line per user-visible change, written for the user
  - AS-DOC-12 [S] Open the README with what the project is for and an example, before how to install it

---

## Documenting an item

### AS-DOC-01 [M] Document every public item

Every item a caller outside the file can name has a documentation comment, unless its name already
says all there is to say. The published page is the only thing a distant caller reads, and an item
without a comment shows them a name and a signature, with every promise the type does not carry left
to guess.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | `D103` | decided | | Ruff's missing-docstring rules, D100 to D107, reject a public module, class, method, function or package without one, so the standard states no rule of its own |
| rust-style | `missing_docs` | decided | | The compiler denies a public item with no documentation, so the standard states no rule of its own |
| zig-style | ZS-DOC-01 | realises | [M] | |

### AS-DOC-02 [M] Open with one sentence that stands alone, then a blank line

The first paragraph of a documentation comment is one complete sentence saying what the item is or
does, followed by a blank line. Tooling lifts that sentence alone into every listing and search
result, stripped of its surroundings, so a fragment or a paragraph of five sentences reads as noise
beside eighty siblings.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-DOC-01 | realises | [M] | |
| rust-style | RS-DOC-07 | realises | [M] | |
| zig-style | ZS-DOC-02 | realises | [M] | |

### AS-DOC-03 [M] State the contract a caller can rely on, never how the code works

A documentation comment says what the item promises: what it needs, what it returns, the units and
the edge cases. Why the implementation is the way it is belongs in an ordinary comment beside the
code. A reason in the published page tells the caller about something they may not rely on, and a
promise left in an ordinary comment is invisible to the person who needs it.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-DOC-03 | realises | [M] | |
| rust-style | RS-DOC-15 | realises | [M] | |
| zig-style | ZS-DOC-03 | realises | [M] | |

### AS-DOC-04 [M] Document the errors a caller can get, and when

A function whose failures are part of its contract says under what condition each one occurs. The
type of the failure tells the caller its shape; only prose tells them what causes it, and that
decides whether they retry, report or give up. A failure that no caller can act on is left out.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-DOC-05 | realises | [M] | |
| rust-style | RS-DOC-09 | realises | [M] | |
| zig-style | ZS-DOC-04 | realises | [M] | |

### AS-DOC-05 [M] Use the ecosystem's fixed form for each part of a contract

A contract is stated in the form the language's own libraries have trained every reader to scan: a
documentation convention picked once, a fixed order of sections, or a fixed sentence for each kind
of promise. A reader who knows where an answer sits finds it without reading the page, and a
paraphrase makes them stop and decide whether it means the same thing.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-DOC-06 | realises | [M] | |
| rust-style | RS-DOC-08 | realises | [M] | |
| zig-style | ZS-DOC-05 | realises | [M] | |

### AS-DOC-06 [M] Write an example that the toolchain runs

An example in the documentation is compiled and run with the rest of the tests. One that is not
executed is wrong within two releases, and a wrong example is worse than none because it is the part
people copy.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-DOC-08 | realises | [M] | |
| rust-style | RS-DOC-06 | realises | [M] | |
| zig-style | ZS-DOC-06 | realises | [M] | |

## Comments

### AS-DOC-07 [M] Say why in a comment, never what

The code already says what it does, and says it more reliably than a comment can, since it cannot
drift. A comment records what the code cannot: the reason for a constant, the design rejected, the
invariant kept, the constraint that is not visible locally.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-DOC-13 | realises | [M] | |
| rust-style | RS-DOC-17 | realises | [M] | |
| zig-style | ZS-DOC-07 | realises | [M] | |

### AS-DOC-08 [S] Write a comment as a sentence

A comment opens with a capital letter after its marker and a space, and ends with a full stop. A
comment at the end of a line may be a bare phrase. Sentence shape makes the author state a complete
thought where a fragment lets a half-formed one through, and no formatter touches the text of a
comment.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-DOC-14 | realises | [S] | |
| rust-style | RS-DOC-18 | realises | [S] | |
| zig-style | ZS-DOC-08 | realises | [S] | |

### AS-DOC-09 [M] Delete commented-out code

Version control remembers it, so the file need not. Commented-out code is ambiguous in a way that
costs every later reader: it may be work in progress, a rollback or dead weight, and nobody can tell
which without digging. It is also never updated with the code around it.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | `ERA001` | decided | | Ruff rejects commented-out code, so the standard states no rule of its own |
| rust-style | RS-DOC-19 | realises | [M] | |
| zig-style | ZS-DOC-09 | realises | [M] | |

### AS-DOC-10 [M] Change a comment in the same edit as the code it describes

A comment, or a documentation comment, that contradicts the code is worse than none, because the
reader trusts it and skips the code. It is wrong the moment the code changes and nothing fails when
the two drift, so the same edit updates both.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-DOC-07 | realises | [M] | |
| rust-style | RS-DOC-20 | realises | [M] | |
| zig-style | ZS-DOC-10 | realises | [M] | |

## Beside the code

### AS-DOC-11 [S] Keep a changelog with a line per user-visible change, written for the user

A project others depend on keeps a changelog: a section per version and a line per change a user can
see, written from the user's side and not the implementation's. It is read by people deciding
whether to upgrade, in the two minutes they have, and a history of steps taken answers a question
nobody asked while hiding the change that affects them.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-DOC-10 | realises | [S] | |
| rust-style | RS-DOC-26 | realises | [S] | |
| zig-style | ZS-DOC-11 | realises | [S] | |

### AS-DOC-12 [S] Open the README with what the project is for and an example, before how to install it

A reader arrives not knowing whether this is the right project, and an installation command does not
answer that. A paragraph on the problem it solves and who it is for, and one example, decide it in
seconds, which is all the attention the decision gets.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-DOC-09 | realises | [S] | |
| rust-style | RS-DOC-31 | realises | [S] | |
| zig-style | ZS-DOC-12 | realises | [S] | |
