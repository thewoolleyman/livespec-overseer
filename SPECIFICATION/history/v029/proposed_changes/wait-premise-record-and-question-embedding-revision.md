---
proposal: wait-premise-record-and-question-embedding.md
decision: accept
revised_at: 2026-08-22T00:18:29Z
author_human: thewoolleyman <chad@thewoolleyman.com>
author_llm: claude-fable-5
---

## Decision and Rationale

Accepted after independent adversarial review returned APPROVE twice, the second time re-confirming after amendments. The pair closes the false-wait-premise class measured 2026-08-18/19, where sessions waited on targets that did not exist because a wait stated only in prose supplies nothing a later reader can re-query. The contracts half defines the record as a governed durable store — schema version, field set, the closed four-kind vocabulary enumerated here because this tree owns it, exact path, collision-free filename derivation, atomic write, fail-soft individually-scoped read, expiry and lifecycle — so the spec half's vocabulary is defined before it is used normatively. The spec half obliges a governed actor to record a premise before raising a wait question, to identify it by kind and target identifier, and critically to RE-VERIFY it by its recheck instant, since review established that a record nothing must re-check would have let the motivating incident survive ratification. It is fail-soft throughout: an inexpressible kind or a failed write never suppresses the question, and nothing authorizes altering or answering a raised option.

## Resulting Changes

- contracts.md
- spec.md
- scenarios.md

## Ratification Review

ratification_review: auto-spawn
reviewer_model: fable
reviewer_identity: fable
separate_reviewer: True
read_only: True
reviewed_at: 2026-08-22T00:12:50Z
verdict: NO BLOCKERS
proposal_stem: wait-premise-record-and-question-embedding
content_digest: b4d141edba67adc50e0153661373762fe4fcea271fe07dde9ebbb03513b03760
