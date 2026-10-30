---
topic: malformed-state-rejection
author: claude-opus-5-5
created_at: 2026-10-30T19:45:59Z
---

## Proposal: A malformed state value is moved aside and named in the next wrap-up

### Target specification files

- SPECIFICATION/contracts.md
- SPECIFICATION/scenarios.md

### Summary

A state file holding a value outside the token table currently stays on disk indefinitely, and in the implementation it also suppressed the low-context wrap-up, so a session that invented a token opted itself out of restart. This proposal makes the existing fail-closed rule explicit for the wrap-up (a malformed value MUST NOT suppress it), and adds one minimal recovery act: on the tick the daemon observes a malformed value at an entity's canonical state path it renames the file to `.overseer-state.rejected` beside it, and every wrap-up delivered while that rejected copy stands carries one line naming the rejected value and the four session-writable tokens. No new paste type, no new command, and no new operator surface: the track stays an attention member through the existing malformed-value membership for as long as the rejected copy stands.

### Motivation

Incident 2026-10-26 to 2026-10-30 (plan overseer-malformed-state-recovery, epic overseer-c2oqve): the gitops-fleet-capacity-monitoring coordinator wrote `working: ...` into its .overseer-state. The daemon logged it as MALFORMED and treated it as no declaration, but stopped injecting the wrap-up; the session ran four days without restart, compacted repeatedly, fell to 4% context, and 68 `A human must act` alerts reached no human. The wrap-up suppression is a conformance defect fixed separately (overseer-xo2ka7). This proposal closes the second half: even with the wrap-up restored, the bad file keeps standing and nothing tells the session WHAT was wrong with it. Maintainer direction 2026-10-30: implement fixes 1 and 2, keep fix 2 minimal (no over-design); a validated write command (fix 3) is explicitly out of scope.

### Proposed Changes

In `SPECIFICATION/contracts.md` §"The state file", replace the first Contract-rules bullet ("Any value outside the table is malformed: ...") with the two bullets below, and insert the third bullet immediately after the existing bullet "The daemon DELETES the file as it restarts the session, together with the round's stamp, so a declaration can never re-trigger.":

- Any value outside the table is malformed: surfaced to the operator by name and treated as NO declaration (fail-closed). It is never coerced or fuzzy-matched. While it stands it suppresses the keep-going nudge — the safe direction for an ambiguous file — but it MUST NOT suppress the low-context wrap-up of §"The wrap-up injection": a track carrying a malformed value MUST receive the wrap-up exactly as the same track with no state file would.
- MALFORMED-VALUE REJECTION. On the tick the daemon observes a malformed value in an entity's state file at its canonical state path, it MUST rename that file to `.overseer-state.rejected` in the same track directory, replacing any earlier rejected copy. The rename MUST be guarded exactly as the daemon's other removals of a session-written file are: it fires only while the file still holds the first line and modification time the daemon observed, so a valid declaration the session wrote in the meantime is never moved. A path-aliased state file MUST NOT be renamed. The rejected copy is evidence only: the daemon MUST NOT read it as a declaration and it MUST NOT authorize any act. A failed rename MUST be surfaced to the operator and leaves the track treated as no declaration. While the rejected copy stands the track MUST remain an attention member through the malformed-value membership of §"Attention surface", naming the rejected value.
- The daemon MUST delete the rejected copy, if one stands, together with the state file as it restarts the session. A session or the operator MAY delete it at any time; doing so clears the membership above and changes nothing else.

In `SPECIFICATION/contracts.md` §"The wrap-up injection", in the Trigger bullet replace "a malformed state value remains fail-closed as no declaration." with "a malformed state value remains fail-closed as no declaration and MUST NOT suppress the paste." In the "Message obligations" bullet append the sentence: "While a rejected copy of the track's state file stands (§\"The state file\"), every wrap-up MUST also carry one line naming the rejected value — the first non-empty line of the rejected copy — and the four session-writable values."

In `SPECIFICATION/contracts.md` §"Attention surface", in the membership sentence replace "a malformed or path-aliased state value" with "a malformed or path-aliased state value (including a malformed value whose rejected copy still stands)". No other attention wording changes.

In `SPECIFICATION/scenarios.md`, extend `## Scenario: A malformed state value is surfaced and treated as no declaration` by appending the line "And it does not suppress the low-context wrap-up" after "And no act is ever authorized by the malformed value", and insert immediately after that scenario a new scenario:

```
## Scenario: A malformed state value is moved aside and named in the next wrap-up

Given a tracked session whose state file's first line is not one of the protocol's values

When the daemon observes the track on a tick

Then it renames the state file to .overseer-state.rejected in the same track directory, replacing any earlier rejected copy

And the track is treated as having declared nothing

And the track remains surfaced to the operator, by the rejected value, while the rejected copy stands

And the next wrap-up delivered to that track names the rejected value and the four session-writable values

But a state file the session rewrote with a valid value after the observation is not moved
```

The implementation MUST add the new scenario heading to `tests/heading-coverage.json` (a `TODO` entry acknowledging the integration tier, with a matching `tests/heading-coverage-debt.json` row owned by an open work item) in the same revision, and the implementation child MUST replace that `TODO` with an integration-tier test.
