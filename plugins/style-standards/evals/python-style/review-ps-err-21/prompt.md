---
schema_version: "1.1"
name: python-style-review-ps-err-21
description: 'The BAD example of PS-ERR-21, sent for review; the reply cites PS-ERR-21.'
tags: [python-style, review]
runs: 1
max_turns: 10
allowed_tools: [Read, Glob, Grep, Skill]
---

Review this Python code against the project's standards; report each problem with the rule it
breaks:

```python
def flatten(node: object) -> list[object]:
    if not isinstance(node, list):
        return [node]
    return [leaf for child in node for leaf in flatten(child)]


nested = 0
for _ in range(5_000):
    nested = [nested]

try:
    flatten(nested)
except RecursionError as exc:
    assert "recursion" in str(exc)
```
