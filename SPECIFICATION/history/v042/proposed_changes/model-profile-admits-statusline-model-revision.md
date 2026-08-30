---
proposal: model-profile-admits-statusline-model.md
decision: accept
revised_at: 2026-08-30T05:26:46Z
author_human: thewoolleyman <chad@thewoolleyman.com>
author_llm: claude-opus-4-8
---

## Decision and Rationale

Route A of overseer-5a4q: legalize the statusline_model key in the model_profile contract, the only coherent direction once v041's surfacing MUST reads model_profile[statusline_model]. Admits it as an optional fourth key with its verification-baseline purpose stated; the no-secret half of the clause is preserved verbatim and statusline_model is noted to hold a rendered model name, never credential material. No behavior added (the veto is already ratified in v041). Independent read-only opus reviewer: NO BLOCKERS on the exact resulting bytes.

## Resulting Changes

- contracts.md

## Ratification Review

ratification_review: auto-spawn
reviewer_model: opus
reviewer_identity: opus
separate_reviewer: True
read_only: True
reviewed_at: 2026-08-30T05:25:31Z
verdict: NO BLOCKERS
proposal_stem: model-profile-admits-statusline-model
content_digest: 3e3cf5151ee4f817e07aac9a759057b88015544970d45f376e3287a6c3d1243f
