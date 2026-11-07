# harness-integrity Specification

## Purpose
The discipline the harness applies to itself: that suppressing one of its own checks justifies
itself the way suppressing a rule does, and that a list of what must be verified is derived from the
thing it verifies rather than maintained beside it.

## Requirements

### Requirement: A check exempted from a guarantee records why

Where a check is excluded from a property the harness otherwise requires of every check, the
exclusion SHALL name the check and state the reason. An exclusion SHALL NOT be expressed as a bare
list of names. An exclusion naming a check that no longer exists SHALL be reported.

#### Scenario: A check has no negative control

- **WHEN** a check is not covered by any control that proves it can fail
- **THEN** the exclusion records why that check is different, so a reader can tell whether the reason
  still holds

#### Scenario: An exclusion outlives its check

- **WHEN** a check named by an exclusion is renamed or removed
- **THEN** the exclusion is reported, because an exemption standing over nothing is an exemption
  nobody re-examined

#### Scenario: A new check is added

- **WHEN** a check is added and given no control
- **THEN** it fails the guarantee rather than being absorbed by an existing exclusion

### Requirement: What must be verified is derived from what is being verified

A list of subjects a guarantee applies to SHALL be computed from those subjects rather than written
alongside them. A subject that acquires the property the guarantee is about SHALL be covered by that
guarantee without anyone editing a list.

A derivation SHALL NOT skip a subject it fails to resolve. Where a derived guarantee locates each
subject by some means — a lookup, a search, a name — failing to locate one SHALL be a failure of the
guarantee, not an omission from it.

#### Scenario: A check gains a dependency on an external tool

- **WHEN** a check begins to require a tool it did not require before
- **THEN** the guarantee that a missing tool withholds the pass covers it immediately, without a
  separate list being updated

#### Scenario: A derivation produces nothing

- **WHEN** the computed set of subjects is empty, or smaller than the set known to qualify
- **THEN** that is a failure, because a guarantee that applies to nothing passes trivially and reads
  exactly like one that applies to everything

#### Scenario: A subject cannot be located

- **WHEN** a derived guarantee cannot resolve one of its subjects — the lookup that finds it returns
  nothing
- **THEN** the guarantee fails naming that subject, rather than passing over it, because a subject
  silently skipped is indistinguishable from a subject that satisfied the guarantee

#### Scenario: The means of locating a subject is incidental to it

- **WHEN** a guarantee resolves a subject by matching against how it happens to be written rather
  than by asking the thing itself
- **THEN** a reformatting that changes nothing about the subject silently removes it from coverage,
  so the resolution is made from the registered object rather than from its source text

#### Scenario: A category of check needs different treatment

- **WHEN** a guarantee must treat some checks differently — those that read one skill against
  another, for instance
- **THEN** the distinction is declared by the check itself rather than by a set of names maintained
  elsewhere

### Requirement: Machinery that nothing reaches is removed, not carried

Code that nothing calls or reads SHALL be deleted rather than moved. A restructuring SHALL NOT
preserve a member solely because it was there before.

#### Scenario: A refactor moves a module's contents

- **WHEN** code is split or relocated
- **THEN** what nothing reaches is removed as part of the move, because a restructuring that
  relocates without examining has changed where the code is and not what it is

#### Scenario: A member is computed and never read

- **WHEN** a value is assigned and no caller reads it
- **THEN** it is deleted, and the work that produced it with it

### Requirement: A claim the repository makes about its own checks is verified against them

Where the repository states in prose which checks exist, what they cover, or that something holds of
every check, that statement SHALL be compared against the registry and SHALL fail when the two
disagree. A claim written for a reader SHALL NOT be exempt from verification because its audience is
a person.

Where the verification asks whether a field is present, it SHALL read the whole field. A parse that
truncates the field it is judging can find content in what is empty, or emptiness in what is not, and
either way it decides something other than the question it was asked.

#### Scenario: A check ships without being documented

- **WHEN** a check is registered and the documented list does not name it
- **THEN** the run fails, because the file that promises a reason for every check is missing one

#### Scenario: Documentation names a check that no longer exists

- **WHEN** the documented list names something the registry does not
- **THEN** the run fails, the same way an exemption outliving its check does

#### Scenario: A universal claim is made about checks

- **WHEN** prose states that something holds of every check
- **THEN** what it quantifies over is derived from the registry, so the claim cannot become false by
  a check being added

#### Scenario: A documented scope is narrower than the claim

- **WHEN** a check covers some checks and not others, and the prose says it covers all of them
- **THEN** the run fails, and the number or the exemptions it names come from the registry rather
  than from what someone typed

#### Scenario: A documented field contains the delimiter of the format it is written in

- **WHEN** a recorded reason contains a character the surrounding format uses as a separator, escaped
  the way that format requires
- **THEN** the whole reason is read, because a check that stops at the escape judges a fragment and
  reports that a reason is present when only its first character is

#### Scenario: Prose drifts for reasons that are not defects

- **WHEN** wording, column order, or style changes without changing which checks are named or
  whether each carries a note
- **THEN** nothing fails, because the claim has not changed

### Requirement: A negative control exercises the mechanism it names

A control SHALL fail when the mechanism it is named for stops working, and SHALL NOT be satisfied by
a different part of the same check reporting on the same injected defect. Where a check reaches its
verdict by more than one branch, the injected defect SHALL be one that only the named branch can
report.

A control is the evidence that a check can fail. A control that passes through a sibling branch
proves that the check can fail, which was never in doubt, and proves nothing about the branch it
claims to cover — so the branch can be deleted, made unreachable, or narrowed to nothing while the
control stays green.

#### Scenario: A check reaches its verdict by several branches

- **WHEN** a check reports on more than one property of its input, and a control is written for one
  of them
- **THEN** the injected defect is one the other branches do not report, so the control's passing is
  evidence about the branch it names

#### Scenario: The named mechanism is made unreachable

- **WHEN** the code path a control covers stops executing — by a restructuring, a misplaced early
  return, or a narrowed condition
- **THEN** that control fails, rather than continuing to pass because the injected defect also trips
  something else

#### Scenario: A control is written or rewritten

- **WHEN** a control is added for a branch of an existing check
- **THEN** it is verified against the working code and against the code with that branch disabled,
  and it must fail in the second case before it is accepted

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

### Requirement: Negative controls are a bijection onto branches

Every place a check can report a finding SHALL be a named branch, declared with the one level it
reports at, and every finding SHALL carry the branch that produced it. Every branch that can report
a failure SHALL have exactly one negative control or exactly one recorded exemption with its
reason, never both. A control SHALL pass only when a failure from its own branch is reported; a
failure from any other branch SHALL NOT satisfy it, and a failure from another branch beside it
SHALL fail the control unless the control states why the defect reaches that branch too. Every
branch that reports that a check could not look SHALL be reached by making a tool the check
declares absent, or be listed with the reason no absence reaches it. A branch that only informs
SHALL fail no run, and is outside both. The `controls` check and the test suite SHALL run controls
through one runner.

#### Scenario: A control fires through a neighbouring branch

- **WHEN** a control's injected defect is reported only by a branch other than the one it names
- **THEN** the control fails, because the branch it exists to guard could be deleted and it would
  still pass

#### Scenario: A control fires a neighbour as well

- **WHEN** a control's own branch fires, and another branch of the same check fires beside it
- **THEN** the control fails, unless it names that branch with the reason its defect cannot help
  reaching it

#### Scenario: A branch is added

- **WHEN** a check gains a new failure site
- **THEN** the suite fails until that branch has a control or a stated exemption

#### Scenario: A branch reports that a check could not look

- **WHEN** a check gains a branch at `UNRUN`
- **THEN** the suite fails until making some declared tool absent reaches it, or it is listed with
  the reason none does

#### Scenario: A branch is removed

- **WHEN** a control or exemption names a branch no check declares
- **THEN** the suite fails, because an exemption standing over nothing is one nobody re-examined

### Requirement: Per-skill facts live only in profiles, and profiles are data

Everything the harness knows about one skill or one toolchain SHALL be declared in that skill's
profile or that toolchain's module, as data. Generic code SHALL NOT branch on a skill name, a
language name or a check name, and SHALL NOT hold a table keyed by any of them. Profiles SHALL have
no behaviour beyond what one shared engine interprets.

#### Scenario: A delta's anchor

- **WHEN** a check needs to know which standard a delta extends
- **THEN** it reads the profile's declared anchor, never a constant in the check and never a value
  derived from the content under check

#### Scenario: A skill name in generic code

- **WHEN** a module outside `profiles/` and `lang/` contains a skill or toolchain name as a literal
- **THEN** the test suite fails and names the module

### Requirement: The repository runs its own harness in CI, in the shape it ships

The repository SHALL have a workflow that runs, on every push and pull request, the fast check, the
tests that need no toolchain, and the linters and type checker the shipped Python configuration
names. A second job SHALL run the full harness, toolchains included, on a schedule and on demand. The
workflow SHALL use python-style's shipped CI steps, at the same pins, and SHALL meet the
action-pinning requirement the shipped assets meet.

#### Scenario: The workflow drifts from the asset

- **WHEN** the repository's workflow sets up uv at a version other than the one python-style's
  `ci.yml` pins, or names an action at another commit
- **THEN** the run fails, naming the step

#### Scenario: A pull request

- **WHEN** a pull request is opened
- **THEN** the fast job runs every check but the toolchain and mutation runs, with the tools those
  checks call (the compilers `assets`, `citations` and `pins` ask for a version, and the plugin
  validator), and its result shows on the pull request

#### Scenario: The full harness

- **WHEN** the schedule fires or the owner dispatches the workflow
- **THEN** the full job installs the pinned Python, Rust and Zig and runs `agent-skill check`
  with toolchains and mutation included
