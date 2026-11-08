---
schema_version: "1.1"
name: rust-style-review-rs-out-02
description: 'The BAD example of RS-OUT-02, sent for review; the reply cites RS-OUT-02.'
tags: [rust-style, review]
runs: 1
max_turns: 10
allowed_tools: [Read, Glob, Grep, Skill]
---

Review this Rust code against the project's standards; report each problem with the rule it breaks:

```rust
pub fn print_record(name: &str, detail: &str) {
    print!("{name}: ");
    println!("{detail}");
}
```
