---
topic: round-recovery-and-escalation-exhaustion
author: claude-sonnet-5
created_at: 2026-08-14T23:08:54Z
---

## Proposal: recovered-round closure

### Target specification files

- SPECIFICATION/spec.md
- SPECIFICATION/scenarios.md

### Summary

Adds a second, non-restart closure to the delivered-round lifecycle: when a delivered round's session recovers ABOVE its wind-down threshold with no ready declaration on file and no pending resume submission, the daemon closes the round as RECOVERED, so a later threshold crossing opens a fresh round and the escalation fires again. This repairs the round model's unstated premise that remaining context only falls while a round is open, which runtime compaction (Codex auto-compaction, operator-invoked compaction) violates; today one fully-escalated round permanently silences the daemon's only lever for the rest of a compaction-extended session's life.

### Motivation

Live incident, measured 2026-08-14 on track fleet-ci-runner-pool (Codex): a round opened 2026-08-13T19:05Z delivered every band (50/40/30/20); the session's one ready declaration was correctly voided; the session then auto-compacted back to 56% remaining and re-descended to 35%, re-crossing the 50 and 40 bands with no wrap-up (bands consumed in the still-open round), hence no fresh ready, hence no restart, indefinitely. The daemon obeyed the ratified letter at every step; the letter's restart-only-closure clause is the latch. Diagnosis: plan/resume-submit-integrity/research/codex-restart-latch-diagnosis.md; plan epic overseer-xkrwm3, scope event of 2026-08-14T22:00:32Z (front 7).

### Proposed Changes

In spec.md section "The supervision round": (1) Replace the sentence "The restart is the ONLY event that closes a DELIVERED round." with: "A DELIVERED round is closed by exactly TWO events and no other: the restart, and the recovered-round closure defined below. No other daemon behavior - voiding a declaration included - MAY delete such a round's durable record or reset its notified escalation bands." (2) Append a new paragraph: "A delivered round presumes remaining context only falls while the round stays open; runtime compaction breaks that premise. When an acting evaluation observes a DELIVERED round whose track's effective remaining context is strictly ABOVE the track's wind-down threshold, the daemon MUST close that round as RECOVERED: it MUST delete the round's durable record - the stamp, the notified bands, any recorded void floor, and the round-open identity - together, and MUST NOT touch any state file, MUST NOT keystroke the pane, and MUST NOT restart anything. A recovered-round closure MUST NOT occur while a ready declaration is on file (the interlock MUST first consume or void it), MUST NOT occur while the round's resume submission is pending, and MUST NOT occur from a read-only evaluation. An unknown context reading MUST NOT count as above-threshold. After a recovered-round closure the track is un-rounded: a later threshold crossing opens a fresh round and every escalation band MAY fire again, and any declaration surviving from the closed round certifies nothing, exactly as for a declaration on a track that was never in a round." In scenarios.md, add: "## Scenario: A compacted session that re-crosses its threshold is re-warned in a fresh round -- Given a delivered round whose every escalation band has been notified / When the session's effective remaining context recovers strictly above the track's wind-down threshold with no ready declaration on file and no pending resume submission / Then the daemon closes the round as recovered by deleting its durable record without touching any state file or pane / And when the session later crosses the threshold again a fresh round opens and the wrap-up fires again / And a ready declaration left over from the recovered round certifies nothing". The project's heading-coverage link file MUST gain the corresponding clause-to-scenario row atomically with this edit.

## Proposal: bounded void-notice after a voided ready

### Target specification files

- SPECIFICATION/spec.md
- SPECIFICATION/scenarios.md

### Summary

When a ready declaration is voided as stale inside a delivered round, the session is currently never told: the void is logged daemon-side, and any band at or above its current context is already consumed, so nothing re-solicits a fresh declaration unless context happens to fall through a not-yet-notified band. Adds a VOID-NOTICE: one bounded, escalation-adjacent message per round, sent under the same paste-authorization gates as the wrap-up, telling the session its declaration was voided because it resumed work and how to re-declare. Bands remain at-most-once per round; the existing repeated-voiding spam guard is preserved and its scenario amended explicitly rather than contradicted.

### Motivation

Front 8 of plan epic overseer-xkrwm3 (scope event 2026-08-14T22:00:32Z). In the fleet-ci-runner-pool incident the post-void descent still met un-notified lower bands (30/20), so the session kept being prompted; but a void observed when every band at or below the current context is already consumed leaves a protocol-compliant session permanently un-prompted: it believes it has declared, the daemon has discarded the declaration, and neither party ever learns of the disagreement. Diagnosis: plan/resume-submit-integrity/research/codex-restart-latch-diagnosis.md.

### Proposed Changes

In spec.md section "The escalating wrap-up", append: "When a ready declaration is voided as stale inside a DELIVERED round, the daemon MUST send the session one VOID-NOTICE: a message stating that its ready declaration was voided because the session resumed work, restating the exact state-file path and the three values it may write, and restating that a restart requires a fresh ready. The void-notice is subject to every paste-authorization gate that governs a wrap-up, and is sent at most ONCE per round however many voids the round accumulates - the void-notice is a bounded companion to the escalation, not a band, and it MUST NOT re-open, re-fire, or reset any notified band. A failed void-notice paste MUST NOT un-open the round and MAY be retried on a later observation within the same round's single-notice bound. The void-notice authorizes nothing." In scenarios.md: (1) amend "## Scenario: Repeated voiding never re-sends an already-notified band" by appending the line "And at most one void-notice is sent within the round however many declarations are voided"; (2) add "## Scenario: A voided ready declaration is answered with one bounded void-notice -- Given a delivered round in which a session's ready declaration was voided as stale / When the daemon next completes an acting evaluation whose paste-authorization gates all pass / Then the session receives one void-notice naming the state-file path and the fresh-ready requirement / And a second void within the same round sends no second notice / And no notified escalation band is re-sent and no restart is authorized". The heading-coverage link file MUST gain the corresponding rows atomically with this edit.

## Proposal: escalation-exhausted attention membership

### Target specification files

- SPECIFICATION/contracts.md
- SPECIFICATION/scenarios.md

### Summary

Adds a report-only mechanical attention member covering the state where the daemon has no lever left: a DELIVERED round at or below threshold whose every band at or above the current effective context is already notified, with the session structurally idle continuously past a bounded floor and no declaration on file. Today that state renders as plain warned outside NEEDS YOU, so a latched track is invisible until the danger line. The member's rendered note MUST also surface the distinction operators conflate: a runtime UI idle indicator (Codex renders the literal word Ready in its statusline) is an input-state display, while restart authorization is solely the out-of-band state file containing exactly ready - which this member reports as ABSENT.

### Motivation

Front 9 of plan epic overseer-xkrwm3 (scope event 2026-08-14T22:00:32Z). In the fleet-ci-runner-pool incident the latched track sat warned at 35% remaining, idle ~15 hours, outside the attention surface, while its pane displayed Codex's own Ready indicator - the operator-directed acceptance (epic comment 2026-08-14T21:45Z) explicitly requires observability of the UI-Ready-versus-protocol-ready distinction. Diagnosis: plan/resume-submit-integrity/research/codex-restart-latch-diagnosis.md.

### Proposed Changes

In contracts.md section "Attention surface", append to the mechanical membership enumeration: "Membership also includes an ESCALATION-EXHAUSTED track: a DELIVERED round whose track's effective remaining context is at or below its wind-down threshold, where every escalation band at or above that effective context is already notified, no declaration is on file, no resume submission is pending, and the session has satisfied its runtime's structural idle evidence continuously past a ten-minute floor. This member is REPORT-ONLY with normal coordinates; it participates in the NEEDS YOU count and window badge, is edge-triggered like every other member, clears when any of its conditions ceases, and MUST NOT authorize any act - a fresh session-written ready remains the sole restart authorization. Its rendered note MUST state that the runtime's own idle indicator is an input-state display and that the restart authorization - the state file containing exactly ready - is absent, naming the state-file path." In scenarios.md, add: "## Scenario: An exhausted escalation below threshold is surfaced, never acted on -- Given a delivered round at or below its wind-down threshold whose every band at or above the current effective context is already notified / When the session stays structurally idle past the ten-minute floor with no declaration on file and no pending resume submission / Then the track enters the mechanical attention surface as escalation-exhausted with its coordinates and is counted in the window badge / And the rendered note names the state-file path and states that the runtime's idle indicator is not the protocol ready / And the daemon sends no keystroke and performs no restart on this member's account / And the member clears edge-triggered when the session works, declares, or the round closes". The heading-coverage link file MUST gain the corresponding rows atomically with this edit.
