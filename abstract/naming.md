# Naming

Scope: what things are called: casing, word choice, names that come in pairs and in families, one
name for one concept, and the width and trailing commas a formatter leaves to the author. What a
comment says is the documentation chapter's.

## Contents

- **Casing**
  - AS-NAME-01 [M] Case a name by one fixed rule for its kind of item
  - AS-NAME-02 [M] Capitalize an acronym as an ordinary word
- **Word choice**
  - AS-NAME-03 [M] Spell names out; abbreviate only where the short form is already known
  - AS-NAME-04 [M] Put a name's unit and qualifiers last, the most significant first
  - AS-NAME-05 [M] Name a predicate so it reads as a question
  - AS-NAME-06 [M] Name a thing for its concept, never for a container
  - AS-NAME-07 [M] Do not repeat in a name what the type or module containing it already says
- **Families of names**
  - AS-NAME-08 [S] Give related names one shape
  - AS-NAME-09 [M] Name the two halves of a pair symmetrically
  - AS-NAME-10 [M] Give one concept one term, project-wide
- **Layout**
  - AS-NAME-11 [M] Hold every line to one fixed width
  - AS-NAME-12 [M] Let a trailing comma decide when a list explodes
  - AS-NAME-13 [M!] Hold a function to a length it can be read within

---

## Casing

### AS-NAME-01 [M] Case a name by one fixed rule for its kind of item

Types, functions, variables, constants and modules each have one casing, applied without exception.
Casing carries information only while it is uniform: a reader who sees a name cased as a type knows
it is one without looking it up, and one mixed convention takes that signal away for every reader
after.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-NAME-01 | realises | [M] | |
| rust-style | `non_camel_case_types` | decided | | The compiler's casing lints reject a type, a constant or a function whose casing breaks its kind's rule, so the standard states no rule of its own |
| zig-style | ZS-NAME-01 | realises | [M] | |

### AS-NAME-02 [M] Capitalize an acronym as an ordinary word

An acronym is cased like any other word of the name, in capitals only where the language's rules put
a capital: a name keeps its word boundaries readable only if a run of capitals is never two words.
In a lower-case name the acronym is lower case like the rest.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-NAME-02 | overrides | [M] | PEP 8 and the standard library write every letter of an acronym in capitals, and a project that wrote them otherwise beside them would spell one acronym two ways |
| rust-style | RS-NAME-01 | realises | [M] | |
| zig-style | ZS-NAME-02 | realises | [M] | |

## Word choice

### AS-NAME-03 [M] Spell names out; abbreviate only where the short form is already known

A name is paid for by every reader who has to reconstruct it, and an abbreviation the reader has
never met is a private dictionary. A short form is allowed where the reader already holds it: in a
scope small enough that the declaration is in view, or where the language's own library has fixed
the word.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-NAME-04 | realises | [M] | |
| rust-style | RS-NAME-25 | realises | [M] | |
| zig-style | ZS-NAME-04 | realises | [M] | |

### AS-NAME-04 [M] Put a name's unit and qualifiers last, the most significant first

A quantity's name ends with its unit, after the qualifiers, and the qualifiers run from the most
significant to the least, so that names sort into meaningful groups and a missing member of a family
shows. A value whose type carries its unit needs none in its name.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-NAME-05 | realises | [M] | |
| rust-style | RS-NAME-08 | overrides | [S] | Rust names follow the order of the standard library, which the API Guidelines set as verb, object, qualifier (RS-NAME-23): it leads a limit with its qualifier, as in `max_depth`, so RS-NAME-08 keeps only the unit last |
| zig-style | ZS-NAME-07 | realises | [M] | |

### AS-NAME-05 [M] Name a predicate so it reads as a question

A function that answers yes or no is named so that its call reads as a question. A noun in that
place reads as an assignment, and the reader cannot tell a question from a command that reports
whether it succeeded.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-NAME-06 | realises | [M] | |
| rust-style | RS-NAME-21 | realises | [M] | |
| zig-style | ZS-NAME-09 | realises | [M] | |

### AS-NAME-06 [M] Name a thing for its concept, never for a container

A module or a type is named for the one concept it holds. A word that fits anything, such as a
utility, a helper, a manager or a bare piece of data, names a container, and a container can hold
anything: it admits that the boundary has not been found, and it only grows.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-NAME-08 | realises | [M] | |
| rust-style | RS-NAME-04 | realises | [M] | |
| zig-style | ZS-NAME-06 | realises | [M] | |

### AS-NAME-07 [M] Do not repeat in a name what the type or module containing it already says

A member is written behind the path of what contains it, so a word of that path repeated in the
member's name is said twice at every use. The name carries what the path does not.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-NAME-09 | realises | [M] | |
| rust-style | RS-NAME-07 | realises | [M] | |
| zig-style | ZS-NAME-05 | realises | [M] | |

## Families of names

### AS-NAME-08 [S] Give related names one shape

Names that belong to a family follow one pattern, in the same word order and with the same suffixes,
so that a reader who has learned one can guess the next, and a family sorts and searches together. A
variant of an operation extends the base name rather than reordering it.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-NAME-07 | realises | [S] | |
| rust-style | RS-NAME-23 | realises | [S] | |
| zig-style | ZS-NAME-21 | realises | [S] | |

### AS-NAME-09 [M] Name the two halves of a pair symmetrically

Operations that come in pairs are named with matched words, so that a pair is recognised as a pair
and a reader knows the inverse exists without looking. Where the language's library has already
fixed a pair, it is copied.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-NAME-12 | realises | [M] | |
| rust-style | RS-NAME-33 | realises | [M] | |
| zig-style | ZS-NAME-20 | realises | [M] | |

### AS-NAME-10 [M] Give one concept one term, project-wide

A word that names a concept in a project names that concept everywhere and only that concept. A
synonym makes the reader ask whether it marks a distinction, and defeats a search for every place
that touches the concept.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-NAME-13 | realises | [M] | |
| rust-style | RS-NAME-24 | realises | [M] | |
| zig-style | ZS-NAME-18 | realises | [M] | |

## Layout

### AS-NAME-11 [M] Hold every line to one fixed width

No line, comment or string included, runs past the width the project fixes, and the width is the
formatter's own default. A line past it is hidden by the side-by-side view a review is read in, and
a project that picks another width reopens an argument the default closes.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-NAME-10 | realises | [M] | |
| rust-style | RS-NAME-34 | realises | [M] | |
| zig-style | ZS-NAME-16 | realises | [M] | |

### AS-NAME-12 [M] Let a trailing comma decide when a list explodes

Where the formatter honours it, a trailing comma after the last element of a list means one element
per line, and its absence means one line if the list fits. The author's one formatting decision is
then made deliberately, and a list that grows adds one line to a diff, not a rewrite of every
element. Running the formatter in the build is the build chapter's.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-NAME-11 | realises | [M] | |
| rust-style | | absent | | rustfmt lays a list out by width alone and ignores a trailing comma, so the author holds no such lever |
| zig-style | ZS-NAME-15 | realises | [M] | |

### AS-NAME-13 [M!] Hold a function to a length it can be read within

A function is held to a bound counted in lines or statements, so that a reader sees all of it at
once and can tell by looking whether every case is handled. The bound is a number the standard or a
tool fixes, not a taste. A function over it is split at a seam, the control flow staying in the
parent and each piece narrow at both ends, or states in a comment why one flat dispatch is longer.

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | `PLR0915` | decided | | Ruff enables it at its default of 50 statements through the `ALL` selection, so the standard states no rule of its own |
| rust-style | RS-NAME-35 | realises | [M!] | |
| zig-style | ZS-NAME-17 | realises | [M!] | |
