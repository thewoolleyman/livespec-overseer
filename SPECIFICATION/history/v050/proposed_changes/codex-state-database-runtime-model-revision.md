---
proposal: codex-state-database-runtime-model.md
decision: modify
revised_at: 2026-09-11T08:51:55Z
author_human: Chad Woolley <thewoolleyman@gmail.com>
author_llm: gpt-5.6-sol
---

## Decision and Rationale

Accept the proposal's behavior with one precision repair: define the active state database as the greatest numeric state_<integer>.sqlite candidate, forbid falling back to an older stale database, and consume only the track's already-established exact live identity. The resulting clauses preserve exact session-id plus repository-cwd identity, read-only and fail-soft access, differing-base precedence, same-base launch variants, the statusline's verification-only role, Claude behavior, and the no-rollout-body boundary. Five Gherkin scenarios make each observable edge independently testable.

## Modifications

Define the previously ambiguous active-database selection deterministically; state the stale-lower-version exclusion and Codex-home precedence; require the already-established track identity rather than selecting an fd or crossing a carrier boundary; and expand the filed scenario sketches into exact Given/When/Then coverage, including the review-discovered multi-rollout case.

## Resulting Changes

- spec.md
- scenarios.md

## Ratification Review

ratification_review: auto-spawn
reviewer_model: opus
reviewer_identity: opus
separate_reviewer: True
read_only: True
reviewed_at: 2026-09-11T08:51:31Z
verdict: NO BLOCKERS
proposal_stem: codex-state-database-runtime-model
content_digest: ee9f7f65a7be4fe6d800dd1c4299a42aa957d94c59807fa8092c20e0993422e9
