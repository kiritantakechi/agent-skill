## Context

15 main-spec requirements state more than one behaviour in more than 500 characters of text. The
change rewrites no obligation; it only moves clauses between requirements.

## Constraint: meaning preserved exactly

- A split moves whole sentences, verbatim, between requirements. It never rewords what a clause
  demands. The one exception is naming an antecedent: where a moved sentence leans on a neighbour
  it no longer sits beside, the pronoun or positional reference is replaced by the noun it stood
  for, and nothing else in the sentence changes. There are 12 such edits, listed under "Antecedents".
  A sentence is cut only where a requirement could not otherwise be split; none was.
- Every existing scenario is kept verbatim and moves with the behaviour it exercises. No scenario is
  added, so a new requirement exists only where an old scenario fits it.
- OpenSpec requires a MODIFIED requirement to carry every scenario the main spec holds under that
  heading, so a heading cannot stay and also give a scenario away. Each of the 15 is REMOVED and its
  parts are ADDED. A delta cannot REMOVE a heading and ADD it again either: validation refuses
  ("Requirement present in both ADDED and REMOVED"). So the part that stays takes a new heading
  naming what it states; no original heading is kept.
- Archiving places each part where its original stood (the part that stays first, then the split-off
  parts in the order of the sentences they took), rather than at the end of the spec, where the
  CLI appends them.
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

## Antecedents named

Each edit replaces words that pointed at a neighbour with the noun they stood for.

- "The distinction SHALL hold" becomes "The distinction between *a pattern that ran and found
  nothing* and *a pattern that could not run or could not match* SHALL hold".
- "the second comparison is not made" becomes "the comparison against the newest release is not
  made".
- "The first comparison alone is the signal" becomes "The comparison against the running version
  alone is the signal".
- "Neither comparison SHALL answer" becomes "Neither the comparison against the running version nor
  the comparison against the newest release SHALL answer".
- "and is outside both." becomes "and is outside both the rule that a branch has one control or one
  exemption and the rule that a could-not-look branch is reached by an absent tool."
- "It SHALL NOT raise the severity" becomes "The configuration SHALL NOT raise the severity".
- "It SHALL fail, leaving the tree unchanged" becomes "The operation SHALL fail, leaving the tree
  unchanged".
- "The first SHALL be the migration table's" becomes "The first subsection SHALL be the migration
  table's", and "and the second its `gone` rows" becomes "and the second subsection its `gone`
  rows".
- "SHALL be the table restricted" becomes "SHALL be the migration table restricted", and "rendered
  from the table." becomes "rendered from the migration table.".
- In check-execution's scenario "A pattern is syntactically valid but inert", "the requirement below"
  becomes the requirement's heading, "A pattern carries no syntax from a dialect it will not be read
  in", the requirement that followed it.
