---
schema_version: "1.1"
name: bevy-style-migration-remove-children
description: 'What Bevy 0.20 writes for `remove_children`; the reply gives `detach_children` and cites BV-ECS-11.'
tags: [bevy-style, migration]
runs: 1
max_turns: 10
allowed_tools: [Read, Glob, Grep, Skill]
---

This Bevy code was written for an earlier release, and Bevy 0.20 rejects it:

```rust
remove_children
```

What does Bevy 0.20 write in its place, and which rule of the project's standards says so?
