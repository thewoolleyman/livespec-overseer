---
proposal: foreman-operator-hardening.md
decision: accept
revised_at: 2026-08-18T21:43:55Z
author_human: thewoolleyman <chad@thewoolleyman.com>
author_llm: foreman-improvements
---

## Decision and Rationale

Both proposals (relay/escalation evidentiary discipline; non-blocking human-decision escalation) accepted as revised. An independent design review (general-purpose reviewer) returned ACCEPT WITH REVISIONS for both, and the requested revisions (defining 'STILL alert' precisely and splitting its two clauses; removing implementation-specific 'push notification' detail and clarifying composition into the existing attention surface) were applied to the proposed-change file before this revise. A third proposal in the same file (restarted-but-never-worked attention condition) was removed before this revise because it duplicated already-ratified spec text (spec.md lines ~333-346, contracts.md lines ~527-533, shipped via commits 2666ce6/e2388ef/aec745a/335ff41/94134a9) -- documented on ledger item overseer-6ycoi6. A separate independent ratification review (Fable model, per this repo's spec_governance.ratification_review=auto-spawn / ratification_reviewer_model=fable configuration) found one real blocker (scenarios.md missing a scenario for the verbatim-quote rule) plus two non-blocking nits; all three were fixed and a confirmation pass returned NO BLOCKERS.

## Resulting Changes

- spec.md
- scenarios.md
- contracts.md

## Ratification Review

ratification_review: auto-spawn
reviewer_model: fable
reviewer_identity: fable
separate_reviewer: True
read_only: True
reviewed_at: 2026-08-18T21:43:44Z
verdict: NO BLOCKERS
proposal_stem: foreman-operator-hardening
content_digest: 8c25bdf2ff4bed1601117f48e606ee21f7c3c64367d209cd7ee921fe4e3f6793
