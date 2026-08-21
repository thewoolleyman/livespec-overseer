---
proposal: caam-anthropic-loop-operation.md
decision: accept
revised_at: 2026-08-21T11:05:39Z
author_human: thewoolleyman <chad@thewoolleyman.com>
author_llm: claude-opus-5-1m
---

## Decision and Rationale

Accepted as authored. The proposal specifies an operation being rebuilt feature-identically from a working implementation the maintainer owns, and it was written from a measured per-behavior carrier inventory of that program rather than from its documentation - a distinction that mattered, since the source's own prose was found to contradict its program. Both proposals are purely additive: each adds one new top-level section and amends no existing clause, so ratification cannot disturb the other pending proposals. The spec text was amended three times while pending, each time because re-measuring the source falsified or outgrew a clause - the foreman-model override, the keep-warm deadlock fix, and the honest-reporting obligation - so what is being ratified tracks the source as of vps-info cc9c83e rather than as of authoring. An independent read-only reviewer on a separate model re-derived the claims from the program and returned NO BLOCKERS. Doctor static passes with zero non-pass findings. Implementation children are gated on this ratification and are drafted, not yet filed.

## Resulting Changes

- spec.md
- contracts.md

## Ratification Review

ratification_review: auto-spawn
reviewer_model: fable
reviewer_identity: fable
separate_reviewer: True
read_only: True
reviewed_at: 2026-08-21T11:05:09Z
verdict: NO BLOCKERS
proposal_stem: caam-anthropic-loop-operation
content_digest: cab56357b3c2f91669f747dd7b14c5063d6e7e45bc3d147bb204ade63d49f549
