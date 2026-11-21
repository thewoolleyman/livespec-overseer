---
proposal: retire-remote-control-support.md
decision: accept
revised_at: 2026-11-21T03:36:05Z
author_human: Chad Woolley <thewoolleyman@gmail.com>
author_llm: remote-control-retirement
---

## Decision and Rationale

Maintainer direction, 2026-11-21 ~00:2xZ: disable Remote Control support completely. The code half is merged (livespec-overseer#3191 service wiring, #3197 launches pass -n only), so the spec now states what the code does. Independent review: NO BLOCKERS on the exact final bytes after one blocker (the debt-register row) was fixed and re-reviewed. Reviewer: read-only subagent abcc24d50dd3f949e, model sonnet.

## Resulting Changes

- contracts.md
- scenarios.md
- spec.md

## Ratification Review

ratification_review: auto-spawn
reviewer_model: sonnet
reviewer_identity: sonnet
separate_reviewer: True
read_only: True
reviewed_at: 2026-11-21T03:35:38Z
verdict: NO BLOCKERS
proposal_stem: retire-remote-control-support
content_digest: 312da7d51d3ad0f5de0199210ab632f8769738029576e7c18959c6f0dd3fd248
