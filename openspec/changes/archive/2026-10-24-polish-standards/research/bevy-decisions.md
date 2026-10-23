# bevy-style: decisions taken for the apply

What `research/bevy.md` left open, decided once, so the chapters edited in parallel agree.

## The `demote` plan

| Merged | Into | | Merged | Into |
|---|---|---|---|---|
| ARCH-14 | ARCH-11 | | ERR-10 | MIG-13 |
| STATE-03 | ARCH-11 | | STATE-13 | STATE-11 |
| SCHED-21 | SCHED-17 | | TEST-08 | ECS-30 |
| EVENT-17 | SCHED-17 | | TEST-02 | TEST-04 |
| ASSET-03 | ASSET-02 | | TEST-09 | TEST-07 |
| STATE-07 | ECS-16 | | TEST-15 | SCHED-23 |
| ASSET-11 | ECS-16 | | TEST-01 | ARCH-01 |
| ECS-08 | ECS-06 | | ARCH-19 | ARCH-16 |
| ERR-11 | ERR-01 | | ERR-13 | ERR-05 |
| SCHED-14 | SCHED-12 | | BUILD-15 | BUILD-14 |
| SCHED-04 | SCHED-01 | | | |

Removed, with the reason the rename table gives:

- **MIG-19:** its three bullets are BV-ECS-21, BV-ERR-05 and BV-VIEW-08, and its grep becomes the
  migration chapter's list of silent changes.
- **ERR-09:** RS-ERR-02 states it.
- **BUILD-16:** RS-MOD-29 and RS-BUILD-25 state it, and `assets/Cargo.toml` does it.
- **BUILD-19:** RS-BUILD-07 and RS-BUILD-36 state it.
- **BUILD-20:** RS-BUILD-42 states it.

The other A.2 rules keep their Bevy content only and cite the rust-style rule: ERR-08 (the
hot-reload Check, RS-ERR-33), ERR-12 (the wasm line, RS-CLI-28), TEST-12 (its example, RS-TEST-02),
BUILD-17, BUILD-07 (RS-BUILD-45, the tier it tightens), TEST-13 (RS-TEST-21), and ECS-03, whose
`Debug` half becomes a citation of RS-API-50.

The no-merge overlaps of A.1 (STATE-02/05, STATE-18/19, SCHED-10 with BUILD-14, EVENT-07 and ECS-28
with SCHED-07, ECS-15/17, the view rules against the migration rows) are deduplicated in place: the
shared part stays in the owner, and the other rule cites it.

## Decisions

1. **Auto-registration (B3).** ECS-13 is turned around: a reflected type is registered by the
   derive, and only a generic instantiation needs `register_type`. BUILD-03's hand-picked feature
   list gains `reflect_auto_register`. CORE-10, ARCH-11's absorbed registration text and the review
   protocol's step 7 agree.
2. **Absence (B4).** A system that expects zero or one match takes `Single` or `Option<Single>`,
   which skips the system. `?` is kept for a failure that is not expected, and the examples' "a
   skipped frame, not a crash" becomes true.
3. **The core rules (A.3).**
   - CORE-14 says `Res<Time>` in `Update`, as SCHED-06 does.
   - CORE-18 cites the `indexing_slicing` row for "no indexing".
   - CORE-15 cites EVENT-03 for its second sentence.
   - CORE-09 states ECS-20's trigger, and BUILD-14 cites ECS-20.
4. **SCHED-10's threshold** is `too_many_arguments`. The build chapter gains its row if the shipped
   configuration sets the lint at the level the row states (`citations` decides), and SCHED-10
   keeps only how to group.
5. **The error handler (B1).** `App::set_error_handler` everywhere a handler is installed. ERR-05's
   "exactly one" Check becomes "`set_error_handler` is called once", which a second call enforces by
   panicking.
6. **Deprecated spellings (B2, B6).** `uuid_handle!` in ASSET-04 and the MIG-07 row.
   `.matched()` is named only for `QueryManyIter` and `QueryManyUniqueIter`; the sorted and `par_`
   forms are given their own fixes.
