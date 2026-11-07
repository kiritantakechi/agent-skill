---
schema_version: "1.1"
name: rust-style-review-rs-out-03
description: 'The BAD example of RS-OUT-03, sent for review; the reply cites RS-OUT-03.'
tags: [rust-style, review]
runs: 1
max_turns: 10
allowed_tools: [Read, Glob, Grep, Skill]
---

Review this Rust code against the project's standards; report each problem with the rule it breaks:

```rust
#[must_use]
pub fn parse_port(raw: &str) -> u16 {
    raw.parse().unwrap_or_else(|_| {
        eprintln!("port must be a number, got {raw}");
        std::process::exit(2)
    })
}
```
