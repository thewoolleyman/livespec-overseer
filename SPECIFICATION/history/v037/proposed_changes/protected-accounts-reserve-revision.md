---
proposal: protected-accounts-reserve.md
decision: accept
revised_at: 2026-08-27T00:10:14Z
author_human: thewoolleyman <chad@thewoolleyman.com>
author_llm: caam-anthropic-loop-planner
---

## Decision and Rationale

ACCEPTED AS PROPOSED. This ratification is unusual and the record should say why: THE IMPLEMENTATION ALREADY SHIPPED. Children overseer-54k2za.33 and .35 are CLOSED, the code is on master, and protection is running on the live host with one account protected at a 10 percent floor, persisted in state. So the question was not whether to build this but whether the specification correctly describes behaviour already running, and whether that behaviour is sound to bless. Both the independent reviewer and the delegated decider checked every added MUST against the shipped code rather than against the proposal's prose, and each MUST is implemented the way the text describes. IT ALSO REPAIRS A DANGLING REFERENCE. v036 cites 'any per-account protection floor' twice with no defining clause anywhere in SPECIFICATION/; this supplies the referent and inserts it ABOVE both citations, so two forward references become backward ones. ONE THING THE RECORD MUST CARRY, because it is a real limit on what was ratified and it falsifies a sentence in the proposal's own Summary. THE FLOOR CAN BE BREACHED. The leave-at-the-floor trigger fires, but triggering rotation does not stop the spend: the pre-existing relative-headroom margin still gates selection and nothing waives it for a protection trigger. Worked at shipped defaults (reserve 10, margin 10) and reproduced independently by both seats: protected active A at seven_day 91 triggers, unprotected B at 82 clears the reserve but fails is_eligible on 91-82=9 < 10, every_live_account_under_reserve is False, and the pass HOLDS while A keeps being spent below its floor. The RATIFIED TEXT does not promise otherwise -- it requires only that the condition trigger rotation, which it does -- but the proposal's Summary sentence 'MUST NOT spend a protected account below its floor while any unprotected account remains usable' IS falsified by that case, and accepted proposals are archived under history/vNNN/proposed_changes/, so that sentence lands in permanent history. Do not let it become the section's remembered meaning. ACCEPTED DESPITE, all filed as implementation work rather than spec work: the floor breach is unreported (the hold line names the margin and says nothing about the floor just crossed); empty_release_note is dead twice over, its output never read and its guard additionally requiring the ACTIVE account to be protected, so the hold-reporting MUST is met by the always-emitted protected-accounts summary line rather than by the mechanism built for it; and is_eligible's current_protection_floor is an unwired seam whose wiring would close the breach but needs its own oscillation analysis first.

## Resulting Changes

- spec.md

## Ratification Review

ratification_review: auto-spawn
reviewer_model: opus
reviewer_identity: opus
separate_reviewer: True
read_only: True
reviewed_at: 2026-08-26T11:00:00Z
verdict: NO BLOCKERS
proposal_stem: protected-accounts-reserve
content_digest: a412e49794d1c581054f7594f99c3faab1e2169d8d1057d456dc256b14144b5e
