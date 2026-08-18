---
proposal: model-preserving-restarts.md
decision: accept
revised_at: 2026-08-18T22:00:49Z
author_human: thewoolleyman <chad@thewoolleyman.com>
author_llm: claude-sonnet-5
---

## Decision and Rationale

Maintainer-directed track; the reasoning note and handoff at plan/model-preserving-restarts/research/ already worked through the design tradeoffs (wrapper-or-flag only, no statusline lookup table, SET-OR-SCRUB env rule, stale-profile surface+skip, unknown-harness report-only) and this proposal implements those resolutions faithfully. Independent Fable review confirmed no contradiction with the cardinal rule or the restart interlock (the launch profile governs WHAT is relaunched, never WHEN), correct BCP14 usage, consistent {harness, model, wrapper} shape across spec.md/contracts.md/scenarios.md, and no secret-value storage. Accepting as proposed.

## Resulting Changes

- spec.md
- contracts.md
- scenarios.md

## Ratification Review

ratification_review: auto-spawn
reviewer_model: fable
reviewer_identity: fable
separate_reviewer: True
read_only: True
reviewed_at: 2026-08-18T22:00:10Z
verdict: NO BLOCKERS
proposal_stem: model-preserving-restarts
content_digest: 3cfd12f56cf4b4538fb40ef85fc4d4cd9e79bed644be13853021c4e2781bcdaf
