---
topic: uncertifiable-declaration-attention
author: claude-opus-5[1m]
created_at: 2026-07-29T04:53:09Z
---

## Proposal: Surface standing declarations that can never certify

### Target specification files

- spec.md
- contracts.md

### Summary

A declaration the interlock can never honor — a `ready` written with no supervision round open, so no injection stamp exists for it to certify against — currently parks its track in a permanent, plausible-looking `restarting` state that sits outside the attention surface at any context level. This proposal makes any standing declaration that cannot certify operator-visible past a bounded floor, extends the age/duration treatment already ratified for `blocked:` to this case, and records (without yet ratifying) the design question the incident exposed: a session has no sanctioned way to request its own restart outside a round.

### Motivation

Measured live on 2026-07-29, on this plan's own worker: wanting a restart to rebind a stale plugin binding, the session declared `ready` with no round open. The interlock correctly refused every cycle — no stamp, so `ready_valid` can never certify, and that refusal is right and is NOT changed here. But the evaluate cascade's ready branch set row status `restarting`, which is not an attention member, so the pane sat parked indefinitely at 79% remaining context, rendering a plausible-looking status with no operator surface, no duration, and no reconciliation — an absorbing state of exactly the class v003 bounded, in an instance none of v003's members cover: the round-starvation clause is below-threshold only, the busy-shielded arm requires shell-only busy evidence, and the age bands are scoped to `blocked:`. The research note had already recorded this shape as inert debris (two bare-`ready` files that no round would ever reconcile) and deliberately did not engineer around it; this incident shows the shape arises live, on an active track, from a legitimate need. Detection was pure luck: the supervisor read the session's exit report. The daemon-side wake had no producer.

### Proposed Changes

Two edits, wording final at revise time, plus one recorded design question.

EDIT A — spec.md §"Fail-soft posture", appended to the bounded-attention paragraph ratified in v003: a STANDING DECLARATION THAT CANNOT CERTIFY — a `ready` with no round open for it to answer, or any declaration whose certification precondition is structurally absent — MUST be surfaced to the operator past a bounded floor, regardless of remaining context, naming the declaration, its age (carried by the declaration file's own modification time, per the ratified duration rule), and the specific reason it cannot certify. The daemon MUST NOT render an acting status (such as a restart-in-progress status) for a track whose act is structurally impossible; the rendered state names the dead-end instead. Surfacing is the entire response: the interlock's refusal is unchanged, and no age or floor ever authorizes the restart itself.

EDIT B — contracts.md §"Attention surface", membership: add the report-only member — a track carrying a standing declaration that cannot certify, past its bounded floor — with the same coordinates, edge-triggering, quantization, and per-condition re-arm as every other member.

RECORDED DESIGN QUESTION (explicitly NOT ratified by this proposal; carried in the revision record and the implementing slice's design note): whether a session should have a sanctioned way to REQUEST its own restart outside a round — the live incident's legitimate need (a respawn to rebind a stale harness binding). Any such affordance must arrive as its own future proposed change; nothing here licenses inferring one.

Deviation note, same as the v003 proposal and for the same reason: no `## Scenario` heading is added here, because this repository mechanically requires every scenario heading to land atomically with a real integration test and heading-coverage row; the scenario, test, and coverage row are the implementing slice's atomic obligation (overseer-4xfmez.7, filed 2026-07-29 with this proposal as its spec dependency).
