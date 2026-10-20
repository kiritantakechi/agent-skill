# Spec Delta

## ADDED Requirements

### Requirement: The harness meets the standard it ships for its own language

The harness is written in Python, and SHALL pass the configuration `python-style` ships: its ruff
selection, its type-checker rules, and its target version. A deviation SHALL be declared where the
configuration is extended, with the reason, and SHALL NOT be made by weakening the shipped asset.

#### Scenario: A harness module breaks a shipped rule

- **WHEN** a file under `src/` or `tests/` fails the shipped `ruff.toml` or `ty.toml`
- **THEN** the test suite fails, naming the file and the rule

#### Scenario: The harness needs a rule off

- **WHEN** a rule does not fit the harness, such as `print` in the command-line entry point
- **THEN** the repository's own configuration disables it for that file with a comment giving the
  reason, and the asset readers copy is unchanged

#### Scenario: The standard moves its target

- **WHEN** `python-style` moves to a new Python version
- **THEN** the harness's own `requires-python` and target version move with it, because a harness
  that verifies against a version it does not itself run on is checking a claim it does not live by
