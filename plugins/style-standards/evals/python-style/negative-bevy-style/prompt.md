---
schema_version: "1.1"
name: python-style-negative-bevy-style
description: 'The first review prompt of bevy-style, in another language; python-style''s skill does not fire, with the plugin or without it.'
tags: [python-style, negative]
runs: 1
max_turns: 10
allowed_tools: [Read, Glob, Grep, Skill]
---

Review this Bevy code against the project's standards; report each problem with the rule it breaks:

```rust
use bevy::prelude::*;

#[derive(Component, Debug)]
struct Stats {
    health: f32,
    shield: f32,
    speed: f32,
}

fn regenerate_shields(mut stats: Query<&mut Stats>) {
    for mut stats in &mut stats {
        stats.shield = (stats.shield + 1.0).min(100.0);
    }
}
```
