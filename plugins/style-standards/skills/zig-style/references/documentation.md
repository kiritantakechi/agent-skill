# Documentation: Doc Comments, Comments, and the Documents Beside the Code

Scope: what a Zig declaration says about itself in its `///` and `//!` comments (every `pub` item,
the summary sentence, the errors it returns, std's contract phrasings, examples as tests), the `//`
comments that explain the code and their typography, and the documents beside the code: the
changelog and the README. Which of the three comment forms may stand where is the compiler's, and
its rows are at the end. What a name is called, and the file and declaration order, are the naming
chapter's; the `test` mechanics are the testing chapter's; the ownership phrasings std puts on
allocating functions are the memory chapter's (ZS-API-05).

Unless a block shows its own imports, it assumes the preamble `const std = @import("std");`.

## Contents

- **Doc comments**
  - ZS-DOC-01 [M] Give every `pub` declaration a `///` comment, unless its name says it all
  - ZS-DOC-02 [M] Open a doc comment with one sentence that stands alone, then a blank `///` line
  - ZS-DOC-03 [M] Write a declaration's contract in `///` and the reasoning behind it in `//`
  - ZS-DOC-04 [M] Document the errors a function returns and when it returns each
  - ZS-DOC-05 [M] Use std's contract phrasings verbatim
  - ZS-DOC-06 [M] Write an example as a `test` block, never as a code block in a `///` comment
- **Comments**
  - ZS-DOC-07 [M] Say why, not what — including at the top of every test
  - ZS-DOC-08 [S] Comment typography: space after the slashes, capital letter, full stop
  - ZS-DOC-09 [M] Delete commented-out code
  - ZS-DOC-10 [M] Change the comment in the same edit as the code it describes
- **Documents beside the code**
  - ZS-DOC-11 [S] Keep a changelog with a line per user-visible change, written for the user
  - ZS-DOC-12 [S] Open the README with what the package is for and one example, before how to fetch it
- Decided by tools

---

## Doc comments

### ZS-DOC-01 [M] Give every `pub` declaration a `///` comment, unless its name says it all

A `pub` function, type, constant or field carries a `///` comment. One whose name already says all
there is to say is left bare (langref rule 1): `handle: Handle` is undocumented in `Io/File.zig` for
a reason.

**Why:** the generated docs are the only thing a caller outside the file reads, and a `pub`
declaration without a comment shows them a name and a signature, with every promise that is not in
the type left for them to guess.

**Check:** read each `pub` declaration of a changed file for a `///` above it. The compiler rejects
a `///` that documents nothing, but not a declaration that has none.

```zig
// verified — GOOD
const std = @import("std");

/// A fixed-capacity stack of `u32` values.
pub const Stack = struct {
    items: [8]u32 = undefined,
    /// Number of values held; never more than `items.len`.
    len: usize = 0,

    /// Pushes `value`, or returns `error.Full` when the stack is at capacity.
    pub fn push(stack: *Stack, value: u32) error{Full}!void {
        if (stack.len == stack.items.len) return error.Full;
        stack.items[stack.len] = value;
        stack.len += 1;
    }
};

test "push stops at capacity" {
    var stack: Stack = .{};
    for (0..8) |i| try stack.push(@intCast(i));
    try std.testing.expectError(error.Full, stack.push(8));
}
```

### ZS-DOC-02 [M] Open a doc comment with one sentence that stands alone, then a blank `///` line

The first paragraph of a `///` comment is a single complete sentence saying what the declaration is
or does. A blank `///` line follows it, and everything else goes below.

**Why:** the generated docs lift the first paragraph into every listing, stripped of its
surroundings. A fragment, or a paragraph of five sentences, reads as noise in a list of eighty
siblings.

**Check:** read the declaration's entry in the generated docs' listing, not the source. Each summary
should be a complete sentence that still makes sense with the name removed from its front, and a
listing entry holding more than one sentence is a missing blank line.

```zig
// verified — GOOD
/// Returns the number of bytes in `text` equal to `needle`.
///
/// The summary is one sentence that reads correctly in a listing; the blank
/// line above is what ends it.
pub fn count(text: []const u8, needle: u8) usize {
    var n: usize = 0;
    for (text) |c| {
        if (c == needle) n += 1;
    }
    return n;
}
```

### ZS-DOC-03 [M] Write a declaration's contract in `///` and the reasoning behind it in `//`

`///` documents the declaration, field or parameter it precedes; `//!` documents the module; `//` is
an implementation note that stays out of the generated docs. Where each may stand is the compiler's
(the three doc-comment rows below). Which of `///` and `//` a sentence belongs in is not: a contract
goes in `///`, and why the design is so goes in `//`, on the line above it.

std places both on adjacent lines to separate "why the design" from "what the contract is", as the
first example shows.

std also documents **individual parameters in place**, inside the signature, and so may you, as the
second example does.

**Why:** the generated docs show `///` and `//!` and nothing else, so a contract in `//` is
invisible to the caller, and an implementation reason in `///` tells the caller about something they
may not rely on.

**Check:** a `///` that states an implementation reason ("we do it this way because…") rather than a
contract — that one belongs on `//`, immediately above the `///`.

```zig
// fragment
// Having a countdown to grow reduces the number of instructions to
// execute when determining if the hashmap has enough capacity already.
/// Number of available slots before a grow is needed to satisfy the
/// `max_load_percentage`.
available: Size = 0,
```

```zig
// fragment
pub fn allocWithOptions(
    self: Allocator,
    comptime Elem: type,
    n: usize,
    /// null means naturally aligned
    comptime optional_alignment: ?Alignment,
    comptime optional_sentinel: ?Elem,
) ...
```

### ZS-DOC-04 [M] Document the errors a function returns and when it returns each

A function whose error set is part of its contract says, in its `///` comment, under what condition
each error is returned: "Returns `error.Empty` when…". "Returns an error if the operation fails" is
not documentation.

**Why:** the error set tells the caller the shape of a failure; only prose tells them what causes
it, and that decides whether they retry, report or give up. A caller who cannot tell which members
are reachable handles all of them badly.

**Check:** for each `pub` function returning an error union, list the members it can return (the
compiler knows them) and find each one named in the comment.

```zig
// verified — GOOD
const std = @import("std");

pub const ParseError = error{ Empty, Overflow };

/// Parses `text` as a decimal `u8`.
///
/// Returns `error.Empty` when `text` holds no digits, and `error.Overflow`
/// when the value does not fit in a `u8`. The two are distinct so a caller
/// can supply a default for the first and reject the second.
pub fn parseU8(text: []const u8) ParseError!u8 {
    if (text.len == 0) return error.Empty;
    var value: u16 = 0;
    for (text) |c| {
        value = value * 10 + (c - '0');
        if (value > std.math.maxInt(u8)) return error.Overflow;
    }
    return @intCast(value);
}

test parseU8 {
    // Both failures are reachable and distinct, as the comment above promises.
    try std.testing.expectEqual(42, try parseU8("42"));
    try std.testing.expectError(error.Empty, parseU8(""));
    try std.testing.expectError(error.Overflow, parseU8("300"));
}
```

### ZS-DOC-05 [M] Use std's contract phrasings verbatim

Reuse the house sentences rather than inventing synonyms:

Counts are occurrences of the **bolded stem** of each phrase over `lib/zig/std/**/*.zig` at 0.17.0,
case-sensitive — reproduce any row with `rg -I -o '<stem>' -g '*.zig' . | wc -l`. They count the
phrase family, not the full sentence in the left column.

| Phrase | Meaning | std count |
|---|---|---|
| **`Asserts that`** … | violating it trips a safety-checked assertion | 135 |
| **`Assumes`** … | violating it is unchecked Illegal Behavior | 55 |
| **`Invalidates`** element pointers if additional memory is needed. | reallocation may move them | 94 |
| **`Deinitialize with`** \`deinit\`. | ownership: call this | 10 |
| **`Caller owns`** returned memory. | ownership transfers out | 19 |
| **`Thread-safe.`** / **`Not threadsafe`**. | concurrency contract | 18 / 9 |
| **`It is illegal to`** … | hard precondition | 4 |
| **`Deprecated in favor of`** \`x\`. | one line, immediately above the alias | 36, of 237 `/// Deprecated` |
| **`See also:`** + `* \`decl\`` bullets | cross-reference block | 136 |

The full invalidation sentence, `Invalidates element pointers if additional memory is needed.`,
appears 33 times across std, 24 of them in `array_list.zig`. Cross-reference by backticked
identifier always: only backticks become links in generated docs, and 5473 `///` lines in std carry
a backticked identifier (lines matching `^\s*///` that contain `` `name` ``, 0.17.0).

Omit doc comments that restate the name (langref rule 1). `handle: Handle` is undocumented in
`Io/File.zig` for a reason.

**Why:** these are pattern-matched, not read: a reader who has seen the invalidation sentence across
std recognizes the pointer-invalidation hazard at a glance, while a paraphrase forces them to parse
the sentence and decide whether it means the same thing.

**Check:** a doc comment that paraphrases a row of the table — "the caller must free this" instead
of `Caller owns returned memory.`, "pointers may move" instead of the invalidation sentence, "this
is thread-safe" instead of `Thread-safe.` And: any declaration named in a doc comment without
backticks, which is a cross-reference that will not become a link.

### ZS-DOC-06 [M] Write an example as a `test` block, never as a code block in a `///` comment

An example a caller will copy is a `test` block beside the declaration (ZS-TEST-02), which
`zig build test` compiles and runs. A fenced block in a `///` comment is prose to the compiler and
is checked by nobody.

**Why:** an example that is not executed will be wrong within two releases, and a wrong example is
worse than none because it is the part people copy. A test block is both the example and the proof
that it works.

**Check:** a fenced code block in a `///` or `//!` comment is the finding, unless a `test` block
beside it holds the same code.

```zig
// verified — GOOD
const std = @import("std");

/// Returns the number of bytes in `text` equal to `needle`.
pub fn count(text: []const u8, needle: u8) usize {
    var n: usize = 0;
    for (text) |c| {
        if (c == needle) n += 1;
    }
    return n;
}

// The example a reader copies; `zig build test` compiles and runs it.
test count {
    try std.testing.expectEqual(2, count("banana", 'n'));
}
```

## Comments

### ZS-DOC-07 [M] Say why, not what — including at the top of every test

Comments explain the reasoning that is not in the code: why this constant, why not the obvious
design, what invariant is being preserved, what upstream bug is being worked around and when the
workaround can be deleted. Open each test with a sentence stating its goal and method.

TigerBeetle's highest-frequency comment categories, in order, are: why this number; why this design
and not the obvious one; invariants; correctness proofs for derived constants; links to the paper or
issue the idea came from; upstream-bug annotations with a removal condition.

**Why:** TigerStyle: "Code alone is not documentation." Restating the code duplicates a fact that
will drift, while a rationale cannot be recovered from the source at all, so it is the only thing a
comment adds that the code cannot.

**Check:** a comment whose words are the identifiers on the line below it —
`// Increment the sector count.` above `sector_count += 1` — is the canonical violation; delete it
or replace it with the reason. Second: a magic number introduced with no comment naming its
derivation. Third: a `test` block whose first line is code rather than a sentence stating goal and
method.

```zig
// fragment — BAD
// Increment the sector count.
journal.sector_count += 1;
```

```zig
// fragment — GOOD
// Bump before the fsync so a torn write is detected as a short journal on
// replay rather than as a valid sector with garbage contents.
journal.sector_count += 1;

// TODO(zig): remove once https://github.com/ziglang/zig/issues/NNNNN lands;
// the alignment downcast works around a 0.16.0 codegen bug.
```

### ZS-DOC-08 [S] Comment typography: space after the slashes, capital letter, full stop

Comments are sentences: `// Like this.` A colon replaces the full stop when the comment introduces
what follows: `// Two cases:`. End-of-line comments may be unpunctuated phrases:
`+ two index blocks`.

**Why:** TigerStyle N19. Sentence-shaped comments force the author to state a complete thought;
fragments let half-formed ones through. The cost is zero and the consistency is visible at a
distance.

**Check:** `rg -n '//[^ /!\n]'` catches the missing space. Then scan standalone comment lines for a
lower-case first word or a missing `.`/`:` terminator. End-of-line comments are exempt, so restrict
the scan to comments that start their own line.

### ZS-DOC-09 [M] Delete commented-out code

Version control remembers it; the file should not.

**Why:** commented-out code is ambiguous in a way that costs every future reader: it might be work
in progress, a rollback or dead weight, and nobody can tell which without archaeology. It also never
changes with the code around it.

**Check:** a `//` comment whose text parses as a statement or a declaration (`const x = …;`,
`if (…) {`, a lone `}`) is the finding. Each is deleted, or replaced by the reason it was kept.

### ZS-DOC-10 [M] Change the comment in the same edit as the code it describes

A doc comment, a `//` comment or a test's opening sentence that contradicts the code is wrong the
moment the code changes. Update it in the same edit, in the same commit.

**Why:** a wrong comment is worse than none, because the reader trusts it and skips reading the
code. Correctness of comments belongs to the same category as correctness of code, and unlike code
nothing fails when they drift.

**Check:** in review, read every comment adjacent to a changed line and confirm it is still true. A
diff that changes behaviour without touching a nearby comment deserves a second look.

## Documents beside the code

### ZS-DOC-11 [S] Keep a changelog with a line per user-visible change, written for the user

A package other people depend on keeps a `CHANGELOG.md`: a section per version, and a line per
user-visible change, written from the user's side ("`Reader.readAll` now returns `error.EndOfStream`
at a short read"), not the implementation's ("refactor read loop"). Write the line in the commit
that makes the change, and bump `.version` in `build.zig.zon` in the commit that closes the section.

**Why:** the changelog is read by people deciding whether to upgrade, in the two minutes they have.
A commit log records steps taken, and an entry for an internal refactor answers a question nobody
asked while hiding the change that affects them.

**Check:** can a user tell from the changelog alone whether an upgrade affects them? For each entry,
ask what it changes for someone importing the package; "nothing" means the entry does not belong.

### ZS-DOC-12 [S] Open the README with what the package is for and one example, before how to fetch it

The README says what problem the package solves, who it is for, and shows one example, before it
gives the `zig fetch --save` line or any build instruction.

**Why:** a reader arrives not knowing whether this is the right package, and a fetch command does
not answer that. One paragraph and one example decide it in seconds, which is all the attention the
decision gets.

**Check:** read the first screen of the README. If it begins with an install or build command, it
answers the second question first.

## Decided by tools

The compiler rejects each of these on its own; no setting turns one off.

| Tool | Lint | Level | Forbids |
|---|---|---|---|
| zig | `unattached documentation comment` | error | a `///` comment with no declaration after it |
| zig | `expected statement, found 'a document comment'` | error | a `///` comment on a statement inside a function body |
| zig | `expected type expression, found 'a document comment'` | error | a `//!` comment after the first declaration of a file |
