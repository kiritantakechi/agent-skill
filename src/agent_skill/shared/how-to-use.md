1. **Read section 2** before emitting {language} code. It is the {language} {target} reality check,
   and some of its entries change behaviour without producing an error, so nothing else will catch
   them.
2. **Apply section 4.** Those core rules bind on their own and reach nearly every file.
3. **Load one chapter** from the reference map in section 6 — the one that matches the task. Each
   opens with a table of contents listing every rule it owns, so you can jump straight to the rule.
   Load a second chapter only when the task genuinely spans two; never load all of them.
{delta_step}
4. **Walk section 5** before handing back a diff.

Rules are cited by ID: `{prefix}-`, then the family of the chapter that owns the rule, then its
number. Section 6 maps each family to its chapter, so cite the ID when justifying a change and the
reader can find the full rule and its rationale. {conflict}

…

A chapter ends with **Decided by tools** when a tool settles part of its subject on its own: each
lint or compiler error, the level it fails a build at, and what it forbids. Those are not rules —
the tool enforces them, so they carry no Why and no Check. When rules are renumbered,
the migration chapter names the file that maps every old ID to its new one.

Every fenced example carries a marker on its first line. `{comment} verified` — the block
{verified_as}, and any test it ships passes. `{comment} fragment` — shown in context rather than run
as a unit, usually because it uses names the chapter declares around it. `{comment} rejected —
<tool>: …` — the rejection is the point, and the marker names the tool that rejects it: {tools}. A
trailing `— GOOD` or `— BAD` names which side of the rule the block illustrates. A block in another
language carries its marker in that language's comment syntax.
