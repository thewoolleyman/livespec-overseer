---
proposal: supersede-void-notice-with-expiry-notice.md
decision: accept
revised_at: 2026-08-16T21:51:25Z
author_human: thewoolleyman <chad@thewoolleyman.com>
author_llm: claude-sonnet-5
---

## Decision and Rationale

Accepted as written. The proposal is round 3 of a design that has been independently reviewed twice before this pass, and it carries the maintainer's explicit 2026-08-16 ruling on plan epic overseer-xkrwm3 to TRANSFER the daemon's declaration-death notification obligation from the retired activity-void trigger to a max-age expiry trigger, superseding the v014 void-notice clauses. The resulting_files implement every bullet of '### Proposed Changes' literally: contracts.md's 'Stale-declaration voiding' bullet is severed into a retargeted ready-side EXPIRY statement (bounded maximum age, thirty minutes by default, expiry instant deterministically 'declaration mtime + maximum age') and a fully self-contained `blocked:`-side voiding statement that restates its own two-minute grace and its own clearing discipline with no cross-reference into the ready-side text; the restart interlock gains the new precondition-3 age backstop closing the aged-but-unrecorded certification window; the sidecar field becomes EXPIRY INSTANT; the attention member is reworded rather than merely renamed because surfacing is no longer the ONLY guard; all eight spec.md sites and all nine scenarios.md scenarios are swept, with one new scenario pinning the age backstop; and non-functional-requirements.md's 'voiding graces' beside-test reference is retargeted. Two deliberate, recorded deviations from the proposal's literal text: the normative sentence 'BOTH checks apply, and either one failing MUST fail this precondition.' is lifted from the proposal's implementer note into precondition 3 itself, because the backstop is only fail-closed as a conjunction; and spec.md cites the retargeted rule as contracts.md §"The state file", its "Stale-declaration voiding" rule, because the label is a bullet rather than a heading and the bare form would be a dangling section reference. Independent read-only ratification review by a separately spawned claude-fable-5 reviewer over four rounds against these exact bytes: round 1 returned BLOCKERS (a self-contradictory 'MUST NOT expire ... on an activity, busy, or gated observation' against 'is EXPIRED, regardless of session activity'), rounds 2 and 3 returned READY WITH MINOR FIXES, and round 4 returned NO BLOCKERS on the final bytes digested here. Decision ownership: this repo's spec_governance.revise_decision_mode is 'consensus', armed by the maintainer in commit 0466b9a on 2026-08-16; the maintainer's own ruling relayed the same day and recorded on overseer-xkrwm3 is the confirmed human decision for this proposal. The corresponding code amendment (PR #1001, work-item overseer-xawpyl) is out of scope for this ratification and follows it.

## Resulting Changes

- contracts.md
- non-functional-requirements.md
- scenarios.md
- spec.md

## Ratification Review

ratification_review: manual-spawn
reviewer_model: claude-fable-5
reviewer_identity: claude-fable-5
separate_reviewer: True
read_only: True
reviewed_at: 2026-08-16T21:51:15Z
verdict: NO BLOCKERS
proposal_stem: supersede-void-notice-with-expiry-notice
content_digest: 0114591fd1b1fa07f82114a8317efc4cacd9a38b1bdde727601d1b1b83b6cc28
