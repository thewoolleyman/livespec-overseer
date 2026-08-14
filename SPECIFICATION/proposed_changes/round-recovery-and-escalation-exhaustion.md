---
topic: round-recovery-and-escalation-exhaustion
author: claude-sonnet-5
created_at: 2026-08-14T23:08:54Z
---

## Proposal: recovered-round closure

### Target specification files

- SPECIFICATION/spec.md
- SPECIFICATION/contracts.md
- SPECIFICATION/scenarios.md

### Summary

Adds a second, non-restart closure to the delivered-round lifecycle: when a delivered round's session recovers ABOVE its wind-down threshold with an absent state file and no pending resume submission, the daemon closes the round as RECOVERED, so a later threshold crossing opens a fresh round and the escalation fires again. This repairs the round model's unstated premise that remaining context only falls while a round is open, which runtime compaction (Codex auto-compaction, operator-invoked compaction) violates; today one fully-escalated round permanently silences the daemon's only lever for the rest of a compaction-extended session's life. This revision (post-adversarial-review, 2026-08-14) amends EVERY ratified restatement of restart-only closure — including the un-opened-round paragraph in spec.md and the key-deletion sentence in contracts.md §"Durable stores" — and hardens the closure guard to fail closed against the round's own in-flight answer.

### Motivation

Live incident, measured 2026-08-14 on track fleet-ci-runner-pool (Codex): a round opened 2026-08-13T19:05Z delivered every band (50/40/30/20); the session's one ready declaration was correctly voided; the session then auto-compacted back to 56% remaining and re-descended to 35%, re-crossing the 50 and 40 bands with no wrap-up (bands consumed in the still-open round), hence no fresh ready, hence no restart, indefinitely. The daemon obeyed the ratified letter at every step; the letter's restart-only-closure clause is the latch. Diagnosis: plan/resume-submit-integrity/research/codex-restart-latch-diagnosis.md; plan epic overseer-xkrwm3, scope event of 2026-08-14T22:00:32Z (front 7). An independent adversarial review of the first filing (VERDICT: BLOCKERS, recorded on the plan epic) found the closure guard insufficiently fail-closed and two unamended restart-only restatements; this filing incorporates every blocker remedy.

### Proposed Changes

In spec.md section "The supervision round":

1. Replace the sentence "The restart is the ONLY event that closes a DELIVERED round." with: "A DELIVERED round is closed by exactly TWO events and no other: the restart, and the recovered-round closure defined below. No other daemon behavior — voiding a declaration included — MAY delete such a round's durable record or reset its notified escalation bands."

2. In the same section's un-opened-round paragraph, replace "Only a DELIVERED round is closed by the restart alone; a merely attempted one is un-opened at once and was never a round at all." with: "Only a DELIVERED round is closed by the restart or by the recovered-round closure; a merely attempted one is un-opened at once and was never a round at all."

3. In the same section, amend "The round closes when the daemon restarts the session — which deletes the state file and the round's stamp together — so a declaration can never re-trigger, and a stamp can never outlive its round." by appending: "The recovered-round closure defined below is the one other closure, and it deletes the round's durable record only when the state file is already absent."

4. Append a new paragraph: "A delivered round presumes remaining context only falls while the round stays open; runtime compaction breaks that premise. When the daemon's supervising loop — never a read-only listing surface — observes a DELIVERED round whose track's effective remaining context is KNOWN, not stale under the bounded staleness window, and strictly ABOVE the track's wind-down threshold, it MUST close that round as RECOVERED: it MUST delete the round's durable record — the stamp, the notified bands, any recorded void floor, and the round-open identity — together, and MUST NOT touch any state file, MUST NOT keystroke the pane, and MUST NOT restart anything. The closure is guarded fail-closed against the round's own in-flight answer: it MUST NOT occur unless the track's state file is ABSENT — any session-written token (`ready`, `blocked`, `winding-down`), however stale, holds the round open, an unreadable or malformed state file holds the round open exactly as a declaration would, and only the daemon's own idle marker is treated as absence. It MUST NOT occur while the round's resume submission is pending, and an unknown or stale context reading MUST NOT count as above-threshold. The daemon MUST re-read every one of these closure inputs immediately before deleting the record, exactly as it re-checks every authorization input immediately before a paste; a declaration that appears between observation and deletion holds the round open. After a recovered-round closure the track is un-rounded: a later threshold crossing opens a fresh round and every escalation band MAY fire again, and a declaration written after the closure certifies nothing, exactly as for a declaration on a track that was never in a round. One residual is accepted and surfaced rather than closed: a standing declaration that can neither certify nor be voided holds its round open indefinitely, and such a track remains visible through the existing standing-declaration attention members."

In contracts.md section "Durable stores", amend the round-sidecar key-deletion sentence "the RESTART deletes the key entirely, so no round datum — floor and identity included — outlives its round. Key deletion is tied to the restart specifically rather than to any round-ending event." to: "the RESTART and the RECOVERED-ROUND CLOSURE each delete the key entirely, so no round datum — floor and identity included — outlives its round. Key deletion is tied to those two round-closing events specifically rather than to any other round event."

In contracts.md section "The restart interlock", amend "the floor is CLEARED at restart, not raised, and plays no part" to "the floor is CLEARED when the round closes — at restart, or at a recovered-round closure — not raised, and plays no part".

In scenarios.md, add:

"## Scenario: A compacted session that re-crosses its threshold is re-warned in a fresh round — Given a delivered round whose every escalation band has been notified / When the session's effective remaining context is known, not stale, and strictly above the track's wind-down threshold, its state file is absent, and no resume submission is pending / Then the daemon closes the round as recovered by deleting its durable record without touching any state file or pane / And when the session later crosses the threshold again a fresh round opens and the wrap-up fires again / And a declaration written after the closure certifies nothing"

"## Scenario: A recovered-round closure defers to any standing state-file content — Given a delivered round whose session's effective remaining context has recovered above the track's wind-down threshold / When the state file holds any session-written token however stale, or is unreadable or malformed / Then the round's durable record survives and no closure occurs / And the daemon re-reads the state file immediately before any deletion so a declaration appearing between observation and deletion also holds the round open"

The project's heading-coverage link file MUST gain the corresponding clause-to-scenario rows atomically with these edits.

## Proposal: bounded void-notice after a voided ready

### Target specification files

- SPECIFICATION/spec.md
- SPECIFICATION/scenarios.md

### Summary

When a ready declaration is voided as stale inside a delivered round, the session is currently never told: the void is logged daemon-side, and any band at or above its current context is already consumed, so nothing re-solicits a fresh declaration unless context happens to fall through a not-yet-notified band. Adds a VOID-NOTICE: one durable, bounded, escalation-adjacent message per round, sent under the same guarded-paste predicate as the wrap-up but triggered by the void rather than by the below-threshold trigger, telling the session its declaration was voided because it resumed work and how to re-declare. Bands remain at-most-once per round; the existing repeated-voiding spam guard is preserved and its scenario amended explicitly rather than contradicted; spec.md's closed two-act guarded-paste enumeration is widened to three, explicitly.

### Motivation

Front 8 of plan epic overseer-xkrwm3 (scope event 2026-08-14T22:00:32Z). In the fleet-ci-runner-pool incident the post-void descent still met un-notified lower bands (30/20), so the session kept being prompted; but a void observed when every band at or below the current context is already consumed leaves a protocol-compliant session permanently un-prompted: it believes it has declared, the daemon has discarded the declaration, and neither party ever learns of the disagreement. Diagnosis: plan/resume-submit-integrity/research/codex-restart-latch-diagnosis.md. The adversarial review of the first filing required the closed "exactly two acts" enumeration to be amended rather than silently contradicted, the once-per-round bound to be durable, and the trigger relationship to the below-threshold gate to be stated; all three are incorporated.

### Proposed Changes

In spec.md section "The escalating wrap-up", append: "When a ready declaration is voided as stale inside a DELIVERED round, the daemon MUST send the session one VOID-NOTICE: a message stating that its ready declaration was voided because the session resumed work, restating the exact state-file path and the three values it may write, and restating that a restart requires a fresh ready. The void-notice is subject to the complete guarded-paste predicate that governs a wrap-up, with one difference: its trigger is the void itself, not the below-threshold context trigger, so it MAY fire at any known context while its round remains open — though a round closed as recovered before the notice lands sends no notice, the fresh round's own wrap-up re-teaching the protocol instead. The notice is sent at most ONCE per round however many voids the round accumulates, and that bound is DURABLE alongside the round's notified bands, so a daemon restart never re-sends a notice already sent. The void-notice is a bounded companion to the escalation, not a band, and it MUST NOT re-open, re-fire, or reset any notified band. A failed void-notice paste MUST NOT un-open the round and MAY be retried on a later observation within the same round's single-notice bound. The void-notice authorizes nothing."

In spec.md section "The keep-going nudge", amend the sentence "Exactly two acts apply that rule" (the enumeration of keystroke-bearing informational pastes) to enumerate exactly THREE acts, adding the void-notice of §"The escalating wrap-up" as the third, under the same rule.

In scenarios.md: (1) amend "## Scenario: Repeated voiding never re-sends an already-notified band" by appending the line "And at most one void-notice is sent within the round however many declarations are voided"; (2) add "## Scenario: A voided ready declaration is answered with one durable bounded void-notice — Given a delivered round in which a session's ready declaration was voided as stale / When the daemon next completes an observation whose guarded-paste predicate passes / Then the session receives one void-notice naming the state-file path and the fresh-ready requirement / And a second void within the same round sends no second notice, even across a daemon restart / And no notified escalation band is re-sent and no restart is authorized".

The heading-coverage link file MUST gain the corresponding rows atomically with these edits.

## Proposal: escalation-exhausted attention membership

### Target specification files

- SPECIFICATION/contracts.md
- SPECIFICATION/scenarios.md

### Summary

Adds a report-only mechanical attention member covering a delivered round the daemon is getting no answer from: at or below threshold, every band at or above the KNOWN current effective context already notified, no declaration on file, no recognized busy or background-shell evidence, and the session continuously idle past a ten-minute floor. Today that state renders as plain warned outside NEEDS YOU, so a latched track is invisible until the danger line. The member's rendered note MUST also surface the distinction operators conflate: a runtime UI idle indicator (Codex renders the literal word Ready in its statusline) is an input-state display, while restart authorization is solely the out-of-band state file containing exactly ready — which this member reports as ABSENT. This membership is deliberately broader than the compaction latch that motivated it: any post-wrap-up track idling undeclared past the floor is a protocol violation in progress and is surfaced; the fully-exhausted latch is its worst case.

### Motivation

Front 9 of plan epic overseer-xkrwm3 (scope event 2026-08-14T22:00:32Z). In the fleet-ci-runner-pool incident the latched track sat warned at 35% remaining, idle ~15 hours, outside the attention surface, while its pane displayed Codex's own Ready indicator — the operator-directed acceptance (epic comment 2026-08-14T21:45Z) explicitly requires observability of the UI-Ready-versus-protocol-ready distinction. Diagnosis: plan/resume-submit-integrity/research/codex-restart-latch-diagnosis.md. The adversarial review of the first filing required a KNOWN-context clause, a background-work exclusion honoring the ratified floor-sizing rule, per-runtime idle vocabulary, and the observation-gap anchoring; all four are incorporated, and the breadth of the condition is now stated rather than implied.

### Proposed Changes

In contracts.md section "Attention surface", append to the mechanical membership enumeration: "Membership also includes an ESCALATION-EXHAUSTED track: a DELIVERED round whose track's effective remaining context is KNOWN, not stale, and at or below its wind-down threshold, where every escalation band at or above that effective context is already notified, no declaration is on file, no resume submission is pending, no generating, sub-agent, or recognized background-shell evidence is present, and the session has satisfied its runtime's idle predicate — a positively empty input box for Claude, the structural idle-input evidence for Codex — continuously past a ten-minute floor, an observation gap restarting the floor per the ratified floor rules. An unknown or stale context reading MUST NOT establish membership. This member is REPORT-ONLY with normal coordinates; it participates in the NEEDS YOU count and window badge, is edge-triggered like every other member, clears when any of its conditions ceases, and MUST NOT authorize any act — a fresh session-written ready remains the sole restart authorization. Its rendered note MUST state that the runtime's own idle indicator is an input-state display and that the restart authorization — the state file containing exactly ready — is absent, naming the state-file path. The membership deliberately covers ANY delivered-round track idling undeclared past the floor, not only a round whose every band is consumed: an undeclared post-wrap-up idle session is itself the reportable condition."

In scenarios.md, add: "## Scenario: An exhausted escalation below threshold is surfaced, never acted on — Given a delivered round at or below its wind-down threshold whose every band at or above the known current effective context is already notified / When the session stays idle under its runtime's idle predicate past the ten-minute floor with no declaration on file, no pending resume submission, and no recognized busy or background-shell evidence / Then the track enters the mechanical attention surface as escalation-exhausted with its coordinates and is counted in the window badge / And the rendered note names the state-file path and states that the runtime's idle indicator is not the protocol ready / And the daemon sends no keystroke and performs no restart on this member's account / And the member clears edge-triggered when the session works, declares, or the round closes / And an unknown or stale context reading establishes no membership".

The heading-coverage link file MUST gain the corresponding rows atomically with these edits.
