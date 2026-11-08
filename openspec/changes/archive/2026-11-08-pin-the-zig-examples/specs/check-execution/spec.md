## ADDED Requirements

### Requirement: A mutant deletes only a statement a test could see deleted

Mutation SHALL delete, one at a time, each line of a verified block that holds one whole statement
outside the block's tests, unless the language keeps it. A language SHALL keep a statement that
binds or declares, an assertion, and an equivalent mutant: a statement no well-defined run can tell
from its deletion. Zig SHALL name a store of `undefined` as equivalent, since reading it is illegal.

#### Scenario: A poison write

- **WHEN** a zig example's `deinit` ends with `journal.* = undefined;` and its tests pass
- **THEN** no mutant deletes that line, and mutation reports no survivor at it

#### Scenario: A store a test can see

- **WHEN** a zig example assigns `cli.output = value;` and no test reads `cli.output`
- **THEN** a mutant deletes it, and mutation notes the survivor at its line

#### Scenario: A binding

- **WHEN** a zig example declares `var x: u32 = undefined;`
- **THEN** no mutant deletes it, because the binding is kept before its value is read
