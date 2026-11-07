# Errors

Scope: what a unit does when it meets a failure, how its caller learns of it, and the shapes of
control flow that keep a function readable around it. What a program prints when it fails is the
output chapter's.

## Contents

- **Classifying a failure**
  - AS-ERR-01 [M] Classify a failure by who can cause it before choosing how to report it
  - AS-ERR-02 [M!] Never assert that a failure which can happen cannot
- **Reporting a failure**
  - AS-ERR-03 [M] Report a failure as a failure, never as an absent or sentinel value
  - AS-ERR-04 [M] Never discard an error silently
  - AS-ERR-05 [M] Handle a failure where it can be repaired, and otherwise pass it to the caller
  - AS-ERR-06 [M] A failure translated from a layer below keeps that failure as its cause
  - AS-ERR-07 [M] A failure carries the facts that tell this occurrence from another
- **Designing the failures a package reports**
  - AS-ERR-08 [M] A package gives its callers one name for every failure it reports
  - AS-ERR-09 [M] Never report a public failure as a catch-all
- **Cleanup**
  - AS-ERR-10 [M] Release a resource by a construct that runs on every path out
  - AS-ERR-11 [M] A cleanup path does not itself fail
- **The shape of a function**
  - AS-ERR-12 [M] State a branch condition as the invariant that holds
  - AS-ERR-13 [S] Dispatch on one value with a multi-way branch, not a chain of tests
  - AS-ERR-14 [M!] Use an explicit worklist where the input decides the recursion depth

---

## Classifying a failure

### AS-ERR-01 [M] Classify a failure by who can cause it before choosing how to report it

A condition that input from outside the unit can produce, such as a caller's data, a file, a peer or
the disk, is an operating condition: the unit validates its input and reports the failure as an
error its caller can handle. A condition only the unit's own mistake can produce is a bug, and is
stated as an assertion. An assertion is never the mechanism that validates input.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-ERR-07 | realises | [M] | |
| rust-style | RS-ERR-01 | realises | [M] | |
| zig-style | ZS-ERR-01 | realises | [M] | |

### AS-ERR-02 [M!] Never assert that a failure which can happen cannot

Where a failure is impossible, the unit restructures so the fallible step is not on that path, or
states the proof beside the claim. Unwrapping a result or forcing it to succeed turns an operating
condition into an unconditional abort. Scripts and tests, where aborting is the intended outcome,
relax this.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | | absent | | A failed call raises to a handler the caller can still write, and no operator turns that into an unconditional abort, so there is nothing to unwrap |
| rust-style | RS-ERR-03 | realises | [M!] | |
| zig-style | ZS-ERR-09 | realises | [M!] | |

## Reporting a failure

### AS-ERR-03 [M] Report a failure as a failure, never as an absent or sentinel value

A function whose work can fail reports the failure through the language's failure channel, not as an
empty result, a missing value or a flag the caller is free to forget to test. A value that is absent
by the domain's own meaning, such as an optional field, is not a failure and keeps its own type.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-ERR-20 | realises | [M] | |
| rust-style | RS-ERR-23 | realises | [M] | |
| zig-style | ZS-ERR-17 | realises | [M] | |

### AS-ERR-04 [M] Never discard an error silently

Ignoring an error is a decision, and a decision records its reason. An empty handler or a dropped
result reads the same whether its author weighed the failure or forgot it, so every reader must
re-derive which, unless a comment says.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-ERR-09 | realises | [M] | |
| rust-style | RS-ERR-02 | realises | [M] | |
| zig-style | ZS-ERR-10 | realises | [M] | |

### AS-ERR-05 [M] Handle a failure where it can be repaired, and otherwise pass it to the caller

A unit that can repair a failure does so. A unit that cannot passes it to the caller, who has the
context to decide, and does not carry on as if nothing had happened. Each place that stops a failure
from travelling is a place its information is lost.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-ERR-08 | realises | [M] | |
| rust-style | RS-ERR-09 | realises | [M] | |
| zig-style | ZS-ERR-07 | realises | [M] | |

### AS-ERR-06 [M] A failure translated from a layer below keeps that failure as its cause

When a unit turns a failure of a lower layer into one of its own, the new failure keeps the original
as its cause, so that a reporter can show the whole chain. Dropping the cause discards the message
that was usually the whole diagnostic, and nothing downstream can recover it.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-ERR-06 | realises | [M] | |
| rust-style | RS-ERR-08 | realises | [M] | |
| zig-style | | absent | | An error is a code in an error set with no payload and no cause field, so there is nothing to chain; the context travels in a diagnostics out-parameter |

### AS-ERR-07 [M] A failure carries the facts that tell this occurrence from another

The path, the key, the offset or the address that distinguishes this failure from the forty others
is carried as data a handler can read, not only as prose in a message. The facts are free where the
failure is found and unrecoverable afterwards, because the code that knew them has already returned.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-ERR-03 | realises | [M] | |
| rust-style | RS-ERR-12 | realises | [M] | |
| zig-style | ZS-ERR-31 | overrides | [S] | An error value carries no payload, so the position and context travel in an optional diagnostics out-parameter, needed only where a user has to fix the input |

## Designing the failures a package reports

### AS-ERR-08 [M] A package gives its callers one name for every failure it reports

A caller can handle everything a package reports without listing its parts, and a part added later
does not break that handler. Beneath the one name, failures are told apart by what a caller does
differently, not by the call site that found them or the component that noticed.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-ERR-01 | realises | [M] | |
| rust-style | RS-ERR-10 | realises | [M] | |
| zig-style | ZS-ERR-04 | overrides | [S] | A failure set is declared per operation and composed from reusable sets, so a caller of several operations holds their union and the package has no single name for it |

### AS-ERR-09 [M] Never report a public failure as a catch-all

A public interface does not report a failure as a bare general-purpose error, an erased dynamic
error, or a variant that holds only a message. A caller cannot handle selectively what it cannot
tell apart, and every failure nobody modelled lands in the catch-all and stays there.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-ERR-05 | realises | [M] | |
| rust-style | RS-ERR-13 | realises | [M] | |
| zig-style | ZS-ERR-05 | realises | [M] | |

## Cleanup

### AS-ERR-10 [M] Release a resource by a construct that runs on every path out

A resource is released by a construct bound to the scope that acquires it, placed where the
acquisition is, so that it runs on the normal path and on every failing one. A release the caller
must remember at each exit is missed on the exit nobody tested.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-ERR-14 | realises | [M] | |
| rust-style | RS-ERR-32 | realises | [M] | |
| zig-style | ZS-ERR-11 | realises | [M] | |

### AS-ERR-11 [M] A cleanup path does not itself fail

Cleanup runs where a failure may already be in flight, and a second failure there replaces or aborts
the first. It therefore performs no fallible work, and where releasing can fail in a way the caller
must see, that is a separate, explicit step.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-ERR-15 | realises | [M] | |
| rust-style | RS-ERR-33 | realises | [M] | |
| zig-style | ZS-ERR-16 | realises | [M] | |

## The shape of a function

### AS-ERR-12 [M] State a branch condition as the invariant that holds

A branch that splits the input space is written with the condition that holds for its first case,
not the negation of the condition that does not. A positive condition is read once; a negated one is
read and then inverted. A guard that rejects and leaves is exempt, because stating the rejection is
its whole purpose.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-ERR-17 | realises | [M] | |
| rust-style | RS-ERR-36 | realises | [M] | |
| zig-style | ZS-ERR-20 | realises | [M] | |

### AS-ERR-13 [S] Dispatch on one value with a multi-way branch, not a chain of tests

A choice among the cases of one value is a multi-way branch over that value, checked for coverage
where the language can check it, not a chain of tests of the same subject. A chain over unrelated
conditions is not this concept.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-ERR-18 | overrides | [S] | A match destructures structure, and against constants it reads as an if chain wearing a costume, so a chain over plain values stays a chain |
| rust-style | RS-ERR-34 | tightens | [M] | A Rust enum is the usual subject of the chain, and a match turns a missed variant into a compile error where a chain falls through silently |
| zig-style | ZS-ERR-19 | realises | [S] | |

### AS-ERR-14 [M!] Use an explicit worklist where the input decides the recursion depth

A recursion whose depth the input decides is written with a worklist of bounded size instead, since
deep input otherwise exhausts the stack in a way its caller cannot handle. Recursion stays where a
constant bounds the depth, asserted at the entry.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-ERR-21 | realises | [M!] | |
| rust-style | RS-ERR-35 | realises | [M!] | |
| zig-style | ZS-ERR-23 | realises | [M!] | |
