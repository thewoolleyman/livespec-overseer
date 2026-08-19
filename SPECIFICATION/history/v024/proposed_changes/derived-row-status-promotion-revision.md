---
proposal: derived-row-status-promotion.md
decision: accept
revised_at: 2026-08-19T13:55:45Z
author_human: thewoolleyman <chad@thewoolleyman.com>
author_llm: claude-opus-5
---

## Decision and Rationale

Accepted after two rounds of independent ratification review of these exact bytes, both NO BLOCKERS. The snapshot row's status field was governed while its values were not, and the daemon promotes a human-waiting track on an open picker past a bounded stall floor from blocked:human to a picker-stall status on the PUBLISHED row. A consumer keyed on the blocked:human literal therefore loses the track at the moment it most matters -- which shipped as overseer-v7io, a P1, where an actuator refused a unanimous evidence-carrying human-gated answer on every promoted row. Three independent incidents now trace to that one ambiguity: the P1, a near-miss corrected during v023's own ratification review, and this change. The proposal was NARROWED after v023 ratified the same day, reducing an overlapping restatement to a deferring cross-reference rather than ratifying the same rule in two documents. It governs the narrow load-bearing property -- the field is derived, the evaluated status is not necessarily the published one, and what a consumer may therefore not infer from absence -- rather than enumerating a status vocabulary, which would rot. It also states that the promotion is the referent for both 'picker-stall surface' and 'picker-stall status', v020's two names for one mechanism, which round 2 verified in code: apply_picker_stall is one function with one predicate producing both outputs. The cardinal rule is untouched and the snapshot's OBSERVATION-ONLY sentence stands unmodified.

## Resulting Changes

- contracts.md
- scenarios.md

## Ratification Review

ratification_review: auto-spawn
reviewer_model: fable
reviewer_identity: fable
separate_reviewer: True
read_only: True
reviewed_at: 2026-08-19T13:54:00Z
verdict: NO BLOCKERS
proposal_stem: derived-row-status-promotion
content_digest: 19929701c01b611130fd1326a08db35366e8440526c5c3dbfd39bf51e1b528e9
