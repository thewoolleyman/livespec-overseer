---
proposal: supervision-across-machines-one-live-seat-per-topic.md
decision: accept
revised_at: 2026-11-13T23:53:10Z
author_human: Chad Woolley <thewoolleyman@gmail.com>
author_llm: claude-opus-5-5:herdr-overseer
---

## Decision and Rationale

Accepted unmodified after an independent read-only sonnet ratification review reporting NO BLOCKERS on these exact bytes. legacy-coordinator-agent graded the proposal PASS (re-graded PASS WITH ONE FIX; fix 7, the epic-less-track carve-out, was applied at 6af8686a and checked, and it merged as #3013). The change ratifies design (b) for overseer-5y7ebe: a daemon per supervised machine, with every interlock input kept host-local, and a LIVE-SEAT RECORD on the plan's ledger epic giving one live seat per plan topic across machines. The record is written only by an atomic conditional write, never expires with time, and fails toward one seat when it cannot be verified. Reviewer non-blocking notes: the amended filesystem-boundaries sentences in spec.md and constraints.md leave one over-long wrapped line each (style only, left as reviewed so the evidence still binds); and the fail-closed rule while the ledger is unreachable also holds BINDING, which is intended (observation and wrap-up are exempt). Coverage: the five new headings get TODO and debt rows owned by overseer-5y7ebe in the same change; overseer-5y7ebe stays open until the four implementation children of overseer-uzvcbn are filed and the rows are re-pointed to them.

## Resulting Changes

- constraints.md
- scenarios.md
- spec.md

## Ratification Review

ratification_review: auto-spawn
reviewer_model: sonnet
reviewer_identity: sonnet
separate_reviewer: True
read_only: True
reviewed_at: 2026-11-13T23:51:42Z
verdict: NO BLOCKERS
proposal_stem: supervision-across-machines-one-live-seat-per-topic
content_digest: 57a15d160498a1fc5fc83f188aaea32411841dcd446ba222c625c4529e2e67c5
