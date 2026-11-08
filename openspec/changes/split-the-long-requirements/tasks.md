# Tasks

## 1. Split the 15 long requirements

- [x] 1.1 check-authoring: split "A pattern that accuses ships with a positive control" (913 → 473 and
  438); the candidates paragraph leaves with the scenario that promotes a candidate to an accusation
- [x] 1.2 check-execution: split the four (580 → 296 and 282; 1494 → 453, 466, 336 and 233; 584 → 404
  and 179; 702 → 411 and 290); the pin verification, the local-toolchain pin and the unreadable-input
  rule leave the tool requirement
- [x] 1.3 harness-integrity: split the three (579 → 306 and 271; 619 → 488 and 130; 883 → 388, 260 and
  233); the could-not-look branches leave with the informing branch
- [x] 1.4 python-style: split the two (560 → 399 and 160; 517 → 359 and 157); the `SKILL.md` reference
  map and the one-tool-per-role rule leave
- [x] 1.5 python-verification: split "Blocks are type-checked under a pinned strict configuration"
  (529 → 140 and 388); the rules named one by one and the ban on a wildcard leave
- [x] 1.6 standard-structure: split the four (1073 → 435, 334 and 301; 603 → 417 and 185; 576 → 232
  and 343; 1230 → 470, 443 and 315); the failure conditions and the inverse properties leave the
  renumbering, the one-row-per-lint rule leaves the lint table, the rendering of 2.1 and 2.2 leaves
- [x] 1.7 Verify that nothing was lost: `openspec validate split-the-long-requirements --strict`
  passes; archived in a scratch copy, all nine main specs pass `--strict` with no warning; every
  scenario of the six capabilities is present once, unchanged (229 of 229), every sentence of the 15
  requirements appears once in the 35 that replace them (SHALL and SHALL NOT clauses 78 of 78), and
  every other requirement is byte-identical; `tests/test_openspec.py` and `check --fast` pass
