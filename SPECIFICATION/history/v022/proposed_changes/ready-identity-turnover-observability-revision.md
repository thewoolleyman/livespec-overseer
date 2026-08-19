---
proposal: ready-identity-turnover-observability.md
decision: accept
revised_at: 2026-08-19T05:52:25Z
author_human: thewoolleyman <chad@thewoolleyman.com>
author_llm: claude-opus-5
---

## Decision and Rationale

Accepted. A live successor session can legitimately write a fresh `ready` while the persisted round still names its predecessor. The restart interlock correctly holds that declaration fail-closed under precondition 4, but the letter said nothing about how fast the hold becomes visible — so the ratified tree left it to the generic uncertifiable-ready continuity floor, which made a DETERMINISTIC certification failure surface as undifferentiated `danger` fifteen minutes later. In the fleet-ci-runner-pool-supervisor incident that read as the daemon having IGNORED a `ready`, and it hid the two identities an operator needs to resolve the state safely. contracts.md §"The restart interlock" now requires immediate report-only surfacing in the same completed evaluation, naming the certification failure, the round-open identity, the live identity, and the remediation; scenarios.md pins the case.

This ratifies behavior that already ships: `_supervisor_liveness._must_surface_immediately` bypasses the continuity floor for the identity-mismatch reason, `_supervisor_ready` builds that reason naming both identities, the alert already carries the remediation wording, and `_supervisor_evaluate_idle._apply_uncertifiable_ready` keeps a low remaining-context reading from relabeling the row as ordinary `danger`.

Two successive independent reviews narrowed the accepted clause, and both narrowings are the substance of this decision. The first draft scoped the MUST to "a standing `ready` held by precondition 4" — but precondition 4's own ratified text treats an identity that CANNOT BE DETERMINED as differing, and the daemon deliberately leaves that case under the generic floor, so the broad scoping mandated behavior the daemon does not have and demanded a live identity that by construction does not exist. The repair scoped it to the determined-and-differing case; the repair's own parenthetical then over-included a second case, a round record carrying no identity at all, which is ALSO wrong: `_registry_rounds` classifies such a record as MALFORMED and the malformed branch in `_supervisor_ready._ready_uncertifiable_reason` fires BEFORE the identity comparison, so that case never produces the "differs" reason and never bypasses the floor. The ratified text therefore requires a DETERMINED live identity differing from a DETERMINED round-open identity, and states affirmatively that both indeterminate cases stay under the floor, pointing the no-identity record at the malformed-record membership that already carries it in §"Attention surface".

The row/alert obligation is stated as "MUST between them name", not distributively. The shipped row note carries the failure and both identities while only the alert carries the remediation; the proposal's own phrasing was joint, so the joint form is what was authorized and what is true.

The restart interlock is unaffected. The condition is report-only: it authorizes no restart, no void or clearing of the declaration on account of the mismatch, and no paste, and a later fresh declaration written after a newly delivered current-session round remains the only path to a restart.

## Resulting Changes

- contracts.md
- scenarios.md

## Ratification Review

ratification_review: auto-spawn
reviewer_model: fable
reviewer_identity: fable
separate_reviewer: True
read_only: True
reviewed_at: 2026-08-19T05:57:00Z
verdict: NO BLOCKERS
proposal_stem: ready-identity-turnover-observability
content_digest: acf6fabdb9f62799812baedef8c7d819c2b9382940b84d8d2649f0a2a157b848

Four rounds of independent read-only Fable review ran against this pass; the first three returned BLOCKERS. Round 1 blocked on the sibling proposal (see `any-tick-stranded-resume-self-heal-authorization-revision.md`). Rounds 2 and 3 blocked on this one, in the sequence described above: round 2 caught the precondition-4 over-scoping of the indeterminate live identity, and round 3 caught the no-identity-round-record over-inclusion that the round-2 repair introduced, each by re-deriving the classification order from `_registry_rounds` and `_supervisor_ready` rather than accepting the prior round's account. Round 4 re-derived both repairs, confirmed the clause is now co-extensive with what the daemon surfaces immediately, verified that the malformed-record membership this paragraph points at really exists in §"Attention surface", and returned NO BLOCKERS on the exact bytes recorded by the digest above.

The same `reviewed_at`-postdates-`revised_at` anomaly recorded in this pass's sibling revision file applies here, for the same reason and with the same consequence: the snapshot was cut and committed out of band without the revise CLI, these records were reconstructed afterward on the merged bytes, the round-4 verdict is genuine and is about those exact bytes, and no `revise_decision` journal event was appended for this pass.
