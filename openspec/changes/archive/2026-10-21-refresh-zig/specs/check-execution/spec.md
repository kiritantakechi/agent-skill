# Spec Delta

## MODIFIED Requirements

### Requirement: The executing tool is named, pinned, and required

Every tool the harness depends on to decide whether a check passes SHALL be named in the standard,
pinned to an exact version, and treated as a required dependency rather than an assumed one. Its
absence SHALL be reported by the same mechanism that reports any other missing required tool. The
same holds for a library the standard's examples are verified against, such as an engine crate. That
library is pinned, and the pin is compared, like a tool's.

The declared pin SHALL be verified against reality in two directions. The version that actually
executes SHALL be compared against the pin, and a mismatch SHALL be reported — a statement that the
standard was verified against a version is false if the harness ran a different one. The pin SHALL
also be compared against the newest release of that tool, and a superseded pin SHALL be reported, so
that moving a pin is a reviewed event rather than a note nobody reads.

A standard MAY instead declare that its pin follows the local toolchain. For such a pin, the second
comparison is not made. The first comparison alone is the signal: once the local toolchain moves
past the pin, the mismatch is what reports the pin as superseded. The declaration SHALL state why
the standard follows the local toolchain.

Neither comparison SHALL answer for input it did not understand. A pin whose source cannot be read
and a version that cannot be parsed SHALL each be reported, and SHALL NOT be resolved to a value that
happens to compare as agreement.

#### Scenario: The harness runs where the tool is missing

- **WHEN** verification runs in an environment without a required tool
- **THEN** it reports the tool as unavailable and the affected checks as not run

#### Scenario: A reader adopts a Check

- **WHEN** a reader copies a Check to run against their own code
- **THEN** the standard has told them which tool to install and which version it was verified
  against

#### Scenario: The running version is not the pinned version

- **WHEN** the tool that executes is a different version from the one the pin declares
- **THEN** it is reported as a failure, whichever direction the difference runs, because every claim
  the standard makes about what was verified rests on the two agreeing

#### Scenario: The pin cannot be found

- **WHEN** a tool the harness requires has no pin to compare against
- **THEN** that is itself the finding; an unfindable pin SHALL NOT be read as agreement

#### Scenario: The declaration holding the pins cannot be read

- **WHEN** the harness runs where the file the pins are declared in is not present — installed as a
  distribution rather than run from its source tree
- **THEN** it reports that the pins could not be consulted, by the same mechanism as an unfindable
  pin, rather than raising

#### Scenario: A version cannot be parsed

- **WHEN** a version reported by a tool or an index does not fit the form the comparison expects
- **THEN** it is reported as not compared, because a value that fails to parse and sorts below every
  real version turns "could not tell" into "the pin is current"

#### Scenario: A newer release of a pinned tool exists

- **WHEN** the tool's newest released version is higher than the pinned one
- **THEN** it is reported, naming the available version and what moving the pin requires

#### Scenario: The release list cannot be consulted

- **WHEN** the newest released version cannot be determined — no network, or the index does not
  answer
- **THEN** it is reported as not run rather than as up to date

#### Scenario: A language toolchain is unpinned

- **WHEN** a standard's examples are compiled by a toolchain, such as `rustc` or `zig`, that no pin
  names
- **THEN** that is the finding an unfindable pin produces, rather than the toolchain being trusted
  at whatever version is installed

#### Scenario: A pin follows the local toolchain and upstream has moved

- **WHEN** a standard declares that its pin follows the local toolchain, and upstream has released a
  newer version that this machine does not run
- **THEN** nothing is reported, because the standard is verified against what runs here and that
  has not changed

#### Scenario: A pin follows the local toolchain and the local toolchain has moved

- **WHEN** the local toolchain is upgraded past a pin that follows it
- **THEN** the running-version comparison fails, and that failure is the reviewed event that moves
  the pin

#### Scenario: A pin follows the local toolchain without a reason

- **WHEN** a standard declares a local-following pin and gives no reason
- **THEN** the run fails: such a pin stops tracking upstream on purpose, and only its reason says
  why that is acceptable for this standard
