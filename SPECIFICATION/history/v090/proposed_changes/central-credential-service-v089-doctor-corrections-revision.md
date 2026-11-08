---
proposal: central-credential-service-v089-doctor-corrections.md
decision: accept
revised_at: 2026-11-08T21:43:40Z
author_human: Chad Woolley <thewoolleyman@gmail.com>
author_llm: claude-opus-5-5-central-credential-service
---

## Decision and Rationale

ACCEPT all five proposals. Delegated decision under spec_governance.revise_decision_mode=delegated, taken by the central-credential-service plan session (epic overseer-iyfjbo). When v089 merged, legacy-coordinator-agent ruled under R301 that every finding of the independent post-step doctor run on v089 lands in one follow-up revised as v090. This proposal is that follow-up. It corrects the blocking expired-before-stale tracking contradiction, the three defects (forwarded-refusal report fields, report-store retention, the enforcement-instruction store) and the advisories. It passed two further independent post-step review rounds before filing. No selection, threshold or trigger rule changes, and no design-record contradiction. Seven new scenarios land as spec-first TODO rows in tests/heading-coverage.json with matching tests/heading-coverage-debt.json entries, owned by overseer-3vnxkd and co-edited in the same commit. overseer-3vnxkd's dispatch hold lifts once this lands.

## Resulting Changes

- README.md
- constraints.md
- contracts.md
- scenarios.md
- spec.md

## Ratification Review

ratification_review: auto-spawn
reviewer_model: sonnet
reviewer_identity: sonnet
separate_reviewer: True
read_only: True
reviewed_at: 2026-11-08T21:42:57Z
verdict: NO BLOCKERS
proposal_stem: central-credential-service-v089-doctor-corrections
content_digest: 473be861c56d459afedb55235ae1d84328124358f6e043a9b1e09cbb5061a2c8
