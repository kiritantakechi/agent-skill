---
schema_version: "1.1"
name: rust-style-migration-no-mangle
description: 'What Rust 1.99 writes for `#[no_mangle]`; the reply gives `#[unsafe(no_mangle)]` and cites RS-BUILD-01.'
tags: [rust-style, migration]
runs: 1
max_turns: 10
allowed_tools: [Read, Glob, Grep, Skill]
---

This Rust code was written for an earlier release, and Rust 1.99 rejects it:

```rust
#[no_mangle]
```

What does Rust 1.99 write in its place, and which rule of the project's standards says so?
