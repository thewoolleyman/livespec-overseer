---
proposal: slow-cycle-phase-timing.md
decision: accept
revised_at: 2026-10-31T20:54:03Z
author_human: Chad Woolley <thewoolleyman@gmail.com>
author_llm: claude-opus-5-5 (herdr-overseer)
---

## Decision and Rationale

Accepted as filed under the repository's delegated revise_decision_mode, with the coordinator's direction (gitops-fleet-capacity-monitoring, 2026-10-31) to run this revise as the spec-change slice of the overseer-uzvcbn.9 regroom. Both findings state operator-observable behaviour of the event history in contracts.md 'Daemon invocation', each with a BCP14 clause and Given/When/Then scenarios; the slow-cycle notice follows the existing edge-trigger and re-arm rule of spec.md 'Notify, never block' and adds no blocking. The 30-second threshold is a fixed constant, not a command-line option, so the 'no interval options' clause is untouched. No design record is contradicted. Independent read-only Sonnet review returned NO BLOCKERS over the exact final bytes; its non-blocking notes (a fourth scenario for the no-Herdr-request line, asserting the percentage and notice kind in scenarios) are left for a later proposal rather than changing the reviewed bytes. tests/heading-coverage.json rows for the three new scenarios land in the same commit, naming the implementing factory slice.

## Resulting Changes

- contracts.md
- scenarios.md

## Ratification Review

ratification_review: auto-spawn
reviewer_model: sonnet
reviewer_identity: sonnet
separate_reviewer: True
read_only: True
reviewed_at: 2026-10-31T20:52:12Z
verdict: NO BLOCKERS
proposal_stem: slow-cycle-phase-timing
content_digest: 866ea6e6650413aff86517d999f343a27c4e3decb1aa9435db9b05b080b331c9
