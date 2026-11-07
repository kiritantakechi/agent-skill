# Output

Scope: what a program writes: its output and its diagnostics, the stream each goes to, formatting
and logging, and the status it exits with. How a failure is carried to the place that reports it is
the errors chapter's.

## Contents

- **Where output goes**
  - AS-OUT-01 [M] Send program output to stdout and diagnostics to stderr
  - AS-OUT-02 [M] Write each record to a shared stream whole, so another writer cannot split it
  - AS-OUT-03 [M] Never print, and never end the process, from a library
  - AS-OUT-04 [M] Flush buffered output explicitly, and handle the result
  - AS-OUT-05 [M] Colour output only for a terminal, and honour the conventional variables
- **Logging**
  - AS-OUT-06 [M] Report diagnostics through the logging facade, never by printing
  - AS-OUT-07 [M] A library logs under a name of its own and leaves the configuration to the application
- **Failure and exit status**
  - AS-OUT-08 [M] Report a failure to the user as a message, not a dump
  - AS-OUT-09 [M] Exit non-zero on failure, with a code of its own for each class a caller must tell apart
- **Rendering a value**
  - AS-OUT-10 [M] Give every type a rendering for programmers
  - AS-OUT-11 [M] Never present a programmer's rendering as output meant for a user
  - AS-OUT-12 [S] Give a second user-facing rendering its own name, not a second use of the protocol

---

## Where output goes

### AS-OUT-01 [M] Send program output to stdout and diagnostics to stderr

What a program exists to produce goes to the standard output stream, and everything said about the
run, such as progress, warnings and errors, goes to the standard error stream. The two are routed
separately by a pipe or a redirection, so a consumer of the output receives results and nothing
else, and an operator who redirects the output still sees the diagnostics.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-OUT-13 | realises | [M] | |
| rust-style | RS-OUT-01 | realises | [M] | |
| zig-style | ZS-OUT-16 | realises | [M] | |

### AS-OUT-02 [M] Write each record to a shared stream whole, so another writer cannot split it

A line of output reaches a stream that other threads write to in a way that keeps it in one piece:
one write of the whole record, or a lock held across its parts. A record assembled from several
writes lets another writer's output land inside it, and the log that results cannot be parsed.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-OUT-14 | realises | [M] | |
| rust-style | RS-OUT-02 | realises | [M] | |
| zig-style | ZS-OUT-17 | realises | [M] | |

### AS-OUT-03 [M] Never print, and never end the process, from a library

A library returns a value or an error and leaves the process alone. Writing to the process's streams
and ending the process belong to the application's entry point, which alone knows where output goes
and whether the caller can recover. A library that has something to say writes to a sink its caller
passed in, or logs through the host's facade.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-OUT-15 | realises | [M] | |
| rust-style | RS-OUT-03 | realises | [M] | |
| zig-style | ZS-OUT-19 | realises | [M] | |

### AS-OUT-04 [M] Flush buffered output explicitly, and handle the result

Output that is buffered is flushed by an explicit step before the program ends, and the result of
that step is checked. A flush left to the program's teardown cannot report its failure, so a full
disk or a closed pipe silently truncates the output, or is reported where nothing can act on it.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-OUT-16 | realises | [M] | |
| rust-style | RS-OUT-04 | realises | [M] | |
| zig-style | ZS-OUT-18 | realises | [M] | |

### AS-OUT-05 [M] Colour output only for a terminal, and honour the conventional variables

Escape sequences are written only when the user asked for them or the stream is a terminal, and the
conventional environment variables are honoured: one that forbids colour, and one that forces it
into a redirected stream. A flag with an automatic default settles it over both, and one place makes
the decision. Escape codes written unconditionally are visible garbage in a file and a log.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-OUT-17 | realises | [M] | |
| rust-style | RS-OUT-05 | realises | [M] | |
| zig-style | ZS-OUT-20 | realises | [M] | |

## Logging

### AS-OUT-06 [M] Report diagnostics through the logging facade, never by printing

Diagnostics are records sent through the language's logging facade, which gives each a level, a
source and a destination the operator can filter and change. A print call gives none of these,
cannot be turned off by the user, and is how a forgotten debugging line, and any secret in it,
reaches a shipped program.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | `T201` | decided | | Ruff's `T201` rejects a `print` call, and the standard sends diagnostics to `logging`, so it states no rule of its own |
| rust-style | RS-OUT-06 | realises | [M] | |
| zig-style | ZS-OUT-24 | realises | [M] | |

### AS-OUT-07 [M] A library logs under a name of its own and leaves the configuration to the application

A library emits its records under a name that identifies it, so the application can raise or silence
that one component, and never configures the logging system: no handler, no level, no destination.
The application decides all three once, and a library that decides them wins whichever import or
initialisation happens last.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-OUT-11 | realises | [M] | |
| rust-style | RS-OUT-07 | realises | [M] | |
| zig-style | ZS-OUT-23 | realises | [M] | |

## Failure and exit status

### AS-OUT-08 [M] Report a failure to the user as a message, not a dump

A failure the user can fix is reported as a sentence that names the problem and each cause beneath
it, not as the language's debugging form of the error or a stack trace. A trace is a message to the
programmer and is kept for a failure that is a bug, where it is the only record of where it
happened.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-OUT-22 | realises | [M] | |
| rust-style | RS-OUT-08 | realises | [M] | |
| zig-style | ZS-OUT-21 | realises | [M] | |

### AS-OUT-09 [M] Exit non-zero on failure, with a code of its own for each class a caller must tell apart

A run that did not succeed ends with a non-zero status, and a class of failure that a script must
tell from another, such as a usage mistake from a failed run, has a status of its own. Scripts
branch on the status and cannot branch on prose, and the codes are documented where the user reads
them.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-OUT-23 | realises | [M] | |
| rust-style | RS-OUT-09 | realises | [M] | |
| zig-style | ZS-OUT-22 | realises | [M] | |

## Rendering a value

### AS-OUT-10 [M] Give every type a rendering for programmers

A type has a rendering that says what it is, complete enough to read in a debugger, a failed
assertion or a log, and its author does not leave the language's default, which shows an address or
nothing of the contents, to stand in for it. Writing the rendering is cheap where the language
derives it, and its absence costs every user of a type that contains this one.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-OUT-18 | realises | [M] | |
| rust-style | RS-OUT-10 | realises | [M] | |
| zig-style | | absent | | The formatter renders any value structurally without a declaration, so no type has a programmer's rendering to write |

### AS-OUT-11 [M] Never present a programmer's rendering as output meant for a user

The rendering a programmer reads may change at any time and favours completeness, while the one a
user reads is a contract and favours clarity. The first is not shown to a user, written to a file or
compared by a test, and a user-facing rendering is not written as a delegation to it, which
publishes the type's internal structure.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-OUT-19 | overrides | [S] | `str` falls back to `repr`, so the two are kept apart by defining `str` only where the human form differs from the programmer's, and a type with one form needs no second rendering |
| rust-style | RS-OUT-11 | realises | [M] | |
| zig-style | ZS-OUT-07 | realises | [M] | |

### AS-OUT-12 [S] Give a second user-facing rendering its own name, not a second use of the protocol

A type with one obvious user-facing rendering implements the language's formatting protocol for it.
A type with two reasonable ones, such as short and verbose or absolute and relative, gives the
second a name of its own or a format option, because the protocol offers one rendering and every
caller who wants the other would otherwise rebuild it.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-OUT-20 | realises | [S] | |
| rust-style | RS-OUT-12 | realises | [S] | |
| zig-style | ZS-OUT-03 | realises | [S] | |
