---
topic: busy-session-wrapup-delivery
author: claude-opus-5-5:herdr-overseer
created_at: 2026-10-15T07:02:55Z
---

## Proposal: Deliver the wrap-up to a busy session whose input box is empty

### Target specification files

- SPECIFICATION/spec.md
- SPECIFICATION/contracts.md
- SPECIFICATION/scenarios.md

### Summary

A low-context or compaction-latched session MUST receive the wrap-up whenever its input is positively empty, however busy it is (a running turn, sub-agents, monitors, background shells). Only the guards that protect the INPUT survive at paste time: typed or unreadable input, an open gate or picker, a runtime-reported human wait, a standing declaration, and ambiguous identity or input evidence. Winding down, including stopping its own background work, is the session's responsibility. The restart interlock and its no-busy gates are unchanged.

### Motivation

MAINTAINER RULING 2026-10-15, recorded on plan epic overseer-uzvcbn and on livespec-dev-tooling-dfixhe at 06:57Z: the idle-only delivery rule is WRONG. If the input box is empty, the daemon MUST be able to deliver the wrap-up or wind-down however busy the session is; otherwise a busy session can never be restarted. Measured on daemon 5.28.3 for gitops-fleet-capacity-monitoring (livespec-dev-tooling, herdr w2J:p5): the session never idles (monitors, background agents), so it accumulated 373 winddown-starved alerts and a 21:10:55Z context-compaction latch (3% -> 93%, restart REQUIRED) that never produced a wrap-up. The ruling reverses the busy-cancels-paste guard. A paste into a running Claude Code turn is queued by the harness and submitted when it can be, so delivering it interrupts nothing the session has not already been told to wind down.

### Proposed Changes

spec.md §"The supervision round", first paragraph: replace the sentences from "A round opens when" through "Affirmatively recognized background-shell evidence alone does not prevent the round." with:

> A round opens when a session at or below its wind-down threshold, or carrying a context-compaction latch, presents a POSITIVELY EMPTY input. Claude MUST show a positively empty input box. Codex cannot distinguish its empty placeholder from typed text in a plain capture, so it MUST present positive evidence that its composer is empty; when that evidence is unavailable the round MUST NOT open and the track MUST be surfaced naming that reason. The input region MUST be identical across the two settle captures. The pane MUST NOT show a structured gate or picker, MUST NOT be runtime-reported as waiting on a human, and MUST NOT carry `blocked:`, `ready`, `done`, or a fresh `winding-down`; a stale acknowledgement MAY resume escalation. Busy evidence MUST NOT prevent the round: a generating turn, sub-agents, monitors, background shells, and a capture that changes OUTSIDE the input region all leave the round eligible. Winding down, including stopping its own background processes, monitors and sub-agents before declaring `ready`, is the SESSION's responsibility, and a session that never idles could otherwise never be restarted.

In the same paragraph, replace "then pastes the wrap-up while leaving the shell running" with "then pastes the wrap-up, leaving all running work untouched". After the paragraph, add:

> A paste into a busy session is a queued submission. Its submission MUST still be confirmed by runtime-appropriate evidence that the payload left the input; an unconfirmed submission MUST be handled as a failed opening paste. This rule governs DELIVERY only. The restart interlock is unchanged: a `ready` declaration restarts a session only under contracts.md §"The restart interlock", including its no-busy gates, so a busy session that declared `ready` is never killed mid-work.

spec.md §"Fail-soft posture": replace "Generating and sub-agent-busy detection deliberately over-fire: a false positive suppresses action, while a miss could inject into a working session." with "Generating and sub-agent-busy detection deliberately over-fire for the RESTART: a false positive withholds a restart, while a miss could kill a working session. Busy evidence MUST NOT suppress a wrap-up, wind-down, or expiry-notice paste into a positively empty input." Replace "Action suppression remains unbounded for generating, changing, sub-agent-busy, and ambiguous evidence, and bounded for ATTENTION (see below)." with "RESTART suppression remains unbounded for generating, changing, sub-agent-busy, and ambiguous evidence. PASTE suppression remains unbounded only for typed, unreadable, or unproven-empty input, gates, human waits, standing declarations, and ambiguous identity evidence. Both are bounded for ATTENTION (see below)." In the following paragraph, replace "Suppressing action without limit for generating, changing, sub-agent-busy, or ambiguous evidence is correct" with "Suppressing a RESTART without limit for generating, changing, sub-agent-busy, or ambiguous evidence is correct".

contracts.md §"The wrap-up injection", Trigger bullet: replace "Both settle captures MUST retain the runtime-appropriate eligible input shape and be identical. The pane MUST NOT be generating, changing, sub-agent-busy, gated, runtime-reported as waiting on a human, carrying `blocked:`, `ready`, or `done`, or carrying a fresh `winding-down`; a stale acknowledgement MAY resume escalation. Shell-only eligibility MUST be affirmative — recognized Claude registry `status=shell`, or the Codex descendant-shell fallback — and any unknown, conflicting, malformed, or unavailable authoritative status suppresses the paste." with "The trigger also fires for a track carrying a context-compaction latch, at any remaining context. The input region of both settle captures MUST retain the runtime-appropriate positively-empty shape and be identical. For Codex the positively-empty shape MUST be established by evidence that distinguishes the placeholder from typed text; the structural idle-input evidence suffices when the session is idle, and when a busy Codex session's composer cannot be proven empty the paste MUST be withheld and the reason surfaced. The pane MUST NOT be gated, runtime-reported as waiting on a human, carrying `blocked:`, `ready`, or `done`, or carrying a fresh `winding-down`; a stale acknowledgement MAY resume escalation. Busy evidence — generating, sub-agent-busy, monitors, background shells, or a capture that changes outside the input region — MUST NOT suppress the paste. Unknown, conflicting, malformed, or unavailable evidence about the input, the managed-pane identity, a gate, or a human wait suppresses the paste." In the same bullet, replace "Immediately before paste, the daemon MUST re-read managed-pane identity, authoritative runtime busy evidence, declaration, gate, and eligible-input state; any change or unreadable input cancels the act for that tick. No-busy and affirmatively shell-only-busy panes can satisfy this predicate; any other busy evidence cannot. A certifiable `ready` takes only the restart path after its stricter no-busy interlock passes;" with "Immediately before paste, the daemon MUST re-read managed-pane identity, declaration, gate, human-wait, and eligible-input state; any change or unreadable input cancels the act for that tick. A change in busy evidence alone MUST NOT cancel it. A certifiable `ready` takes only the restart path after its stricter no-busy interlock passes;". The message-delivery bullet gains: "A paste into a busy session is queued by the runtime; its submission MUST be confirmed by evidence that the payload left the input, never by the pane going busy alone."

scenarios.md: replace the scenario headed "## Scenario: Generating or sub-agent-busy evidence suppresses a low-context paste" with:

```
## Scenario: A busy session with an empty input box receives the wrap-up

Given a tracked session at or below its wind-down threshold

And the pane is generating or the runtime reports sub-agents, monitors, or background shells

And its input box is positively empty and unchanged across both settle captures

When the daemon observes the track

Then the daemon records an injection stamp and pastes and submits the wrap-up

And it performs no restart

## Scenario: Typed input, a gate, or a human wait suppresses the wrap-up of a busy session

Given a busy tracked session at or below its wind-down threshold

When its input box holds typed text, or it shows a structured gate, or the runtime reports it waiting on a human

Then the daemon records no injection stamp and pastes no wrap-up

## Scenario: A busy Codex session whose empty composer cannot be proven is surfaced, not pasted

Given a busy Codex session at or below its wind-down threshold

When its composer cannot be positively proven empty

Then the daemon records no injection stamp and pastes no wrap-up

And the track is surfaced naming that reason
```

In "## Scenario: A changing pane or changed evidence cancels a pending wrap-up", replace "When the second capture differs or an authorization input changes before paste" with "When the input region of the second capture differs or an authorization input changes before paste".

The revise MUST co-edit `tests/heading-coverage.json` in the same change: the replaced heading's entry MUST be removed, and each new scenario heading MUST be linked to `"test": "TODO"` with `"work_item": "overseer-uzvcbn.3"` until that item lands its tests.

## Proposal: Retire a ready declaration that stands with no delivered round

### Target specification files

- SPECIFICATION/spec.md
- SPECIFICATION/contracts.md
- SPECIFICATION/scenarios.md

### Summary

A `ready` standing on a track with no delivered round (no round-open timestamp and no recorded expiry, including a track whose opening paste failed and was un-opened) certifies nothing, and today it also blocks every wrap-up, because no paste is ever made over a standing declaration. Nothing exits that state. The daemon MUST instead retire such a declaration once the track owes a wind-down: it replaces the declaration with a daemon-written diagnostic and lets the ordinary predicate open a fresh round. The retirement authorizes nothing and never restarts. This replaces the accepted residual that such a track is surfaced rather than healed.

### Motivation

Measured on daemon 5.28.3, gitops-fleet-capacity-monitoring (livespec-dev-tooling, herdr w2J:p5): the wrap-up paste failed at 2026-10-14T11:12:50Z, the daemon un-opened the round per spec.md §"The supervision round" (the stamp entry was left with no round-open timestamp), the session wrote `ready` at 11:20:59Z, and from 11:36:38Z the daemon reported ready-uncertifiable and held the restart for about 15h. Nothing cleared the declaration or delivered a new round. A 21:10:55Z compaction latch also produced no wrap-up, because the paste predicate excludes any standing `ready`. The operator had to remove the state file by hand. MAINTAINER RULING 2026-10-15 (plan epic overseer-uzvcbn, folded into overseer-uzvcbn.3): when a ready cannot be certified because the daemon itself closed the round, the daemon MUST clear the stale declaration and re-deliver a fresh round, or at least let a compaction latch force one, and MUST NOT alert indefinitely. The un-rounded `ready` holds no authorization, so retiring it removes nothing the cardinal rule protects. It only removes the obstacle to the one route that can produce a certifiable `ready`.

### Proposed Changes

spec.md §"Fail-soft posture": replace the paragraph beginning "A declaration standing on a track that has NEVER been in a round" through "while its remaining context runs down." with:

> A `ready` declaration standing on a track with NO DELIVERED ROUND — no round-open timestamp and no recorded expiry, as after a failed opening paste whose round was un-opened, an out-of-band session replacement, a lost sidecar, or an unprompted write — carries no certification floor and cannot certify. It MUST NOT be left to block the wind-down. When the daemon's supervising loop (never a read-only listing surface) observes such a `ready` on a track whose remaining context is KNOWN and at or below its wind-down threshold, or which carries a context-compaction latch, and the declaration has stood unchanged past the same two-minute grace, measured from the declaration's own modification time, that governs voiding a `blocked:` declaration, the daemon MUST retire it. It MUST re-read the state file immediately before writing, MUST replace the declaration with the daemon-written diagnostic `ready-unrounded: <detail>` only if the file still holds that same `ready`, and MUST NOT restart, keystroke, or open a round in the same act. The ordinary wrap-up predicate of §"The supervision round" then opens a fresh round on that or a later observation, and a `ready` the session writes in answer certifies against that round normally. The diagnostic is daemon-written, authorizes NOTHING, and is treated by the paste predicate as no declaration. A failed retirement write MUST be surfaced through the attention surface and MUST NOT be retried as anything but the same write. A `ready` on an un-rounded track that owes no wind-down (above threshold, no latch) is left standing and surfaced exactly as before. A fresh session-written `ready` remains the SOLE restart authorization.

spec.md §"The supervision round": in the residual sentence "One residual is accepted and surfaced rather than closed: a standing declaration that can neither certify nor expire holds its round open indefinitely", add after it: "A `ready` that stands with no delivered round is not this residual; it is retired under §\"Fail-soft posture\"." In the expiry-notice paragraph, replace "has no round to expire within and remains governed entirely by that existing, separate, continuously-surfaced rule — it is neither expired nor notice-eligible under this paragraph" with "has no round to expire within and is governed entirely by the retirement rule of §\"Fail-soft posture\" — it is neither expired nor notice-eligible under this paragraph".

contracts.md §"The wrap-up injection": replace the sentences "It leaves a residual that is a REGRESSION against shipped behavior for one class of track and MUST be stated rather than discovered — a declaration standing on a track that was never in a round, which the floor deliberately does not reach, is surfaced rather than healed (per spec.md §\"Fail-soft posture\")." with "A `ready` standing on a track with no delivered round, which the floor deliberately does not reach, is RETIRED rather than left standing once the track owes a wind-down (per spec.md §\"Fail-soft posture\"): the daemon replaces it with the daemon-written `ready-unrounded: <detail>` diagnostic, which the paste predicate MUST treat as no declaration, so the next eligible observation opens a fresh round."

scenarios.md: replace the scenario headed "## Scenario: A declaration on a track that was never in a round is surfaced, not healed" with:

```
## Scenario: A ready with no delivered round is retired and a fresh round delivered

Given a track whose state file declares ready

And the track has no round-open timestamp and no recorded expiry

And the track is at or below its wind-down threshold or carries a context-compaction latch

And the declaration is older than the two-minute declaration grace

When the daemon's supervising loop observes the track

Then the daemon replaces the declaration with a ready-unrounded diagnostic

And it performs no restart

And a later eligible observation opens a fresh round and pastes the wrap-up

And a ready the session writes after that wrap-up certifies against the fresh round

## Scenario: A ready with no delivered round on a track that owes no wind-down is surfaced, not retired

Given a track whose state file declares ready

And the track has no round-open timestamp and no recorded expiry

And the track is above its wind-down threshold and carries no context-compaction latch

When the daemon observes the track

Then the declaration is left standing and certifies nothing

And the track is surfaced to the operator
```

The existing "## Scenario: A ready declaration on a track that was never in a round certifies nothing" is unchanged. The revise MUST co-edit `tests/heading-coverage.json`: the replaced heading's entry MUST be removed, and each new heading MUST be linked to `"test": "TODO"` with `"work_item": "overseer-uzvcbn.3"`.
