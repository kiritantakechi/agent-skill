## Context

15 main-spec requirements state more than one behaviour in more than 500 characters of text. The
change rewrites no obligation; it only moves clauses between requirements.

## Constraint: meaning preserved exactly

- A split moves whole sentences, verbatim, between requirements. It never rewords what a clause
  demands. A sentence is cut only where a requirement could not otherwise be split; none was.
- Every existing scenario is kept verbatim and moves with the behaviour it exercises. No scenario is
  added, so a new requirement exists only where an old scenario fits it.
- OpenSpec requires a MODIFIED requirement to carry every scenario the main spec holds under that
  heading, so a heading cannot stay and also give a scenario away. Each of the 15 is REMOVED and its
  parts are ADDED, the part that stays under a new heading naming what it states. The alternative,
  keeping the heading and repeating the moved scenarios in the new requirements, would duplicate
  scenarios.
- Added requirements are appended at the end of a spec. One scenario points by position: "the
  requirement below" in check-execution's "A pattern that cannot match" scenario (the inert pattern),
  kept verbatim, now points past the end of the spec rather than at the translation requirement
  that followed the original.
- Each new requirement is named by a declarative sentence, as its neighbours are.

## Decisions: the seam chosen for each requirement

Each line names the original, then what leaves it; the rest is the part that stays.

- check-authoring, "A pattern that accuses ships with a positive control": the candidates paragraph,
  which demands no fixture, leaves; the rule for accusing patterns stays.
- check-execution, "A pattern that cannot match is a failure, never a pass": the clause that the
  distinction holds at every consumer of a search leaves.
- check-execution, "The executing tool is named, pinned, and required": the two-direction pin
  verification, the local-toolchain pin and the unreadable-input rule leave; naming, pinning and
  requiring the tool stay.
- check-execution, "A positive control is prepared the way the corpus is": the clause that a
  transformed corpus means an identically transformed fixture leaves; the general rule and its
  reason stay.
- check-execution, "Every toolchain runs through one driver": the shape of a toolchain and the
  formatting composition leave; the driver and its one policy stay.
- harness-integrity, "A claim the repository makes about its own checks is verified against them":
  reading the whole field leaves.
- harness-integrity, "A negative control exercises the mechanism it names": the clause that the
  injected defect be one only the named branch can report leaves.
- harness-integrity, "Negative controls are a bijection onto branches": the rule that a control
  passes only through its own branch, and the could-not-look branches with the informing branch,
  leave; the bijection and the one runner stay.
- python-style, "Chapter coverage and a reference map": the `SKILL.md` reference map leaves; the
  chapters and the coverage stay.
- python-style, "The standard names the tools it requires and ships their configuration": one tool
  per role leaves.
- python-verification, "Blocks are type-checked under a pinned strict configuration": the opt-in
  rules named one by one, and the ban on a wildcard, leave.
- standard-structure, "A renumbering is one operation that preserves every citation": the failure
  conditions, and the inverse and empty-plan properties, leave; the operation, the move and the
  rewrite stay.
- standard-structure, "A claim a tool decides is a lint-table row, not a rule": the one-row-per-lint
  rule leaves.
- standard-structure, "Section 2 has three subsections in one order": the rendering of the first two
  subsections from the migration table leaves.
- standard-structure, "Migration is a function from old spelling to row": the meaning of since with
  the command generated from the rows and the verification of `gone` rows, and the rendering of
  sections 2.1 and 2.2, leave; the table, its statuses and the definition of a shape stay. Since
  states no `SHALL` of its own, so it goes with the command clause.

## Risks

A moved sentence can lean on its old neighbour ("the second comparison", "the first", "both", "It").
Each such sentence is kept verbatim under a heading that names its subject, and the sentence it
leans on is in the sibling requirement of the same capability.
