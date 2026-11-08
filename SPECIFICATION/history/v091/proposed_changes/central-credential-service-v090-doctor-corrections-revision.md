---
proposal: central-credential-service-v090-doctor-corrections.md
decision: accept
revised_at: 2026-11-08T23:20:16Z
author_human: Chad Woolley <thewoolleyman@gmail.com>
author_llm: claude-opus-5-5-central-credential-service
---

## Decision and Rationale

ACCEPT all six proposals. Delegated decision under spec_governance.revise_decision_mode=delegated, taken by the central-credential-service plan session (epic overseer-iyfjbo). When v090 merged, legacy-coordinator-agent ruled under R301 that the six findings of the independent post-step doctor run on v090 land in one follow-up revised as v091, with one scoped post-step review over those six only, and that spec iteration for this plan then stops. This proposal is that follow-up. It corrects the one defect (an enforcement instruction could be served again once the record that stopped it was deleted, breaking at-most-once) and the five advisories (return from silence judged by arrival on the role holder's clock; scenarios for supersession, the return-from-silence filter and refused label reuse; the stopped-service scenario's Givens; the constraints.md rollback scope; Issuance's duplicated uniqueness rules). The one scoped post-step review ran on the draft before filing and found 1 defect and 5 advisories; five are resolved in the filed text, and the sixth (reporting a failed write of the acted-identifier record) is deferred to the P1 regroom of overseer-3vnxkd under the same ruling. No selection, threshold or trigger rule changes, and no design-record contradiction. Four new scenarios land as spec-first TODO rows in tests/heading-coverage.json with matching tests/heading-coverage-debt.json entries, owned by overseer-3vnxkd and co-edited in the same commit.

## Resulting Changes

- constraints.md
- contracts.md
- scenarios.md

## Ratification Review

ratification_review: auto-spawn
reviewer_model: sonnet
reviewer_identity: sonnet
separate_reviewer: True
read_only: True
reviewed_at: 2026-11-08T23:19:40Z
verdict: NO BLOCKERS
proposal_stem: central-credential-service-v090-doctor-corrections
content_digest: c136a0a71ed040f59cf8902b776daee5de4157f1afcbca41ad9b35d09d35b46c
