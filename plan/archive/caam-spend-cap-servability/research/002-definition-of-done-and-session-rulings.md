# caam-spend-cap-servability — Definition of Done and session rulings (2026-10-11)

## The maintainer's statement of what done means

The released caam loop selects an account that hit its extra-usage cap but has included quota again, that account actually serves, and the loop's ALERT and hold messages tell the truth about why.

## Definition of Done assertions derived from that statement

Confirmed with the maintainer in an attended resume on 2026-10-11 and recorded as
the `## Definition of Done` section of epic `overseer-gi62im`. All four are
`host_captured`.

- The released caam-anthropic-loop running on host hp selects an account whose extra-usage spend cap is reached while its five-hour and weekly included windows are both above zero.
- After the loop selects a capped account with healthy included windows, `claude -p` answers on that account.
- The loop's ALERT for a capped account with healthy included windows states that included quota remains and does not say the account can serve no request.
- When the loop holds because the spend cap excluded a candidate, the hold reason names the spend cap rather than the headroom margin.

The carrier map lives only in the epic's scope event. It is not repeated here.

## What the factory's DoD gate taught about the children

All five children were filed without a `## Definition of Done` section, which the
filing display reports as a mechanical finding that withholds `ready`. The
sections were authored this session, and the first dispatch of `overseer-vc4nza`
(run `01M4M6P0381GN3AB6FVC7NTSV7`) was stopped by `dod_gate` before any
implementation, for two faults in that text:

- A bullet carrying two assertions ("never selects ... and a pass ... holds").
  `filing_display` did not flag it; the gate did. Split every compound bullet
  before dispatch rather than relying on the host-side display.
- A bullet about a test docstring is not governed by the referenced spec heading.
  The requirement now lives as an implementation note under the item's
  `## Context`, where the implementer still reads it.

## The pane-sensitive pre-push failure

Confirmed 2026-10-11 before the fix: the three declare tests named on
`overseer-axti2d` failed inside a herdr pane and passed from a `setsid -f` tree.
Fixed by PR #2398 (`3ef9df66`).
