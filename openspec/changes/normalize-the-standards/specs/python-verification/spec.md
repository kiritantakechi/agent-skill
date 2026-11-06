## MODIFIED Requirements

### Requirement: Blocks are linted against the shipped rule table

Every verified block SHALL be linted with the configuration the standard ships as an asset, minus a
named allowlist of rules about the shape of a project that a fenced snippet cannot have, each entry
with its reason. Nothing else SHALL differ between the asset and the configuration examples are
linted with, and a divergence SHALL be reported.

#### Scenario: The asset and the verified selection diverge

- **WHEN** the shipped lint configuration enables a rule the verification does not use, other than
  an allowlisted one, or sets a severity the standard's rules do not require
- **THEN** the check reports a failure naming the rule and both settings

#### Scenario: A lint rule fires on an example

- **WHEN** an enabled lint rule reports a diagnostic on an extracted block
- **THEN** the check reports a failure at that block's source line, unless the block is evidence
  rather than advice

#### Scenario: An allowlist entry without a reason

- **WHEN** the allowlist names a rule and gives no reason a snippet cannot satisfy it
- **THEN** the run fails, as any exemption without a reason does
