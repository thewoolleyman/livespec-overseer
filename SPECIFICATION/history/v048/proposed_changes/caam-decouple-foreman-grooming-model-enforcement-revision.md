---
proposal: caam-decouple-foreman-grooming-model-enforcement.md
decision: accept
revised_at: 2026-09-06T18:57:09Z
author_human: thewoolleyman <chad@thewoolleyman.com>
author_llm: caam-anthropic-loop-plan
---

## Decision and Rationale

Re-cut as v048 on top of the sibling plan overseer-5ugiuj's v047 (foreman/grooming/supervise-plan SEAT retirement). Same caam decoupling as the ratified-then-superseded v047 attempt: removes the foreman-suffix derived-model rule + global --foreman-model pin, drops the global-foreman arm of scoped-pin arming; keeps the per-session pin, observed-running/per-session arming (overseer-dyt6 Fable-drain fix) and the name-independent servability reset. Standalone foreman/grooming surfaces untouched.

## Resulting Changes

- spec.md

## Ratification Review

ratification_review: auto-spawn
reviewer_model: opus
reviewer_identity: opus
separate_reviewer: True
read_only: True
reviewed_at: 2026-09-06T18:56:50Z
verdict: NO BLOCKERS
proposal_stem: caam-decouple-foreman-grooming-model-enforcement
content_digest: c652b010be1f864072c40c4b6cf76c66d77bb8417e7546094631588eb8dc2f1b
