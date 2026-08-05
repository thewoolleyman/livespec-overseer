---
proposal: codex-yolo-structured-question-protocol.md
decision: accept
revised_at: 2026-08-05T03:38:30Z
author_human: thewoolleyman <chad@thewoolleyman.com>
author_llm: claude-opus-5
---

## Decision and Rationale

Accepted as filed on the maintainer's explicit ruling, proxied from the worker's own blocked picker. The proposal corrects a claim this repo measured FALSE on 2026-08-04: a native structured picker rendered and completed in a session verified as running --dangerously-bypass-approvals-and-sandbox, observed by capturing the pane FROM OUTSIDE rather than by asking the model, because a model that declined to call a tool can describe 'not offered' and 'chose not to' equally fluently. The correction is evidence-based in BOTH directions: capability is derived from a live gate rather than a runtime label, and the ABSENCE of a gate is expressly not proof that the session can obtain human input another way. Critically it does NOT delete or conditionalise the blocked: escape hatch, which stays load-bearing because headless codex exec offers no picker, not every human decision is expressible as a multiple-choice question, and the feature is under development and can be withdrawn. Independent read-only ratification review returned NO BLOCKERS against these exact bytes, with the over-fix hazard, the inverse over-claim and anchor resolution all checked explicitly.

## Resulting Changes

- spec.md
- contracts.md
- scenarios.md

## Ratification Review

ratification_review: manual-spawn
reviewer_model: claude-fable-5
reviewer_identity: claude-fable-5
separate_reviewer: True
read_only: True
reviewed_at: 2026-08-05T03:38:20Z
verdict: NO BLOCKERS
proposal_stem: codex-yolo-structured-question-protocol
content_digest: bdbd75212b2da54b820f5b0047a12f7a1e14ae0be3da0028bc8d8d5958bdce9a
