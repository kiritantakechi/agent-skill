---
schema_version: "1.1"
name: bevy-style-review-bv-arch-01
description: 'The BAD example of BV-ARCH-01, sent for review; the reply cites BV-ARCH-01.'
tags: [bevy-style, review]
runs: 1
max_turns: 10
allowed_tools: [Read, Glob, Grep, Skill]
---

Review this Bevy code against the project's standards; report each problem with the rule it breaks:

```rust
use bevy::prelude::*;

#[derive(Component, Debug)]
struct Health(pub f32);

#[derive(Component, Debug)]
struct Shield(pub f32);

#[derive(Message, Debug, Clone, Copy)]
struct Hit {
    target: Entity,
    amount: f32,
    pierces_shield: bool,
}

fn absorb(mut hits: MessageReader<Hit>, mut targets: Query<(&mut Health, &mut Shield)>) {
    for hit in hits.read() {
        let Ok((mut health, mut shield)) = targets.get_mut(hit.target) else {
            continue;
        };
        if hit.pierces_shield {
            health.0 -= hit.amount;
            continue;
        }
        let to_shield = hit.amount.min(shield.0);
        shield.0 -= to_shield;
        health.0 -= hit.amount - to_shield;
    }
}
```
