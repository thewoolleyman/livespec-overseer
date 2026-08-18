---
proposal: winddown-rationale-expiry.md
decision: accept
revised_at: 2026-08-18T22:17:21Z
author_human: thewoolleyman <chad@thewoolleyman.com>
author_llm: claude-sonnet-5
---

## Decision and Rationale

Accepts the winddown-declaration-expiry-on-recovery proposal as-is. It was independently adversarially reviewed once already (verdict: ACCEPT WITH REVISIONS, 8 items), all 8 items were incorporated into this exact text, and a second, separately-spawned Fable-model ratification review of these exact clause bytes returned NO BLOCKERS. This re-cut (v018 collided with a concurrently-landed sibling proposal, model-preserving-restarts; rebased onto fresh master and re-cut as the next version) carries byte-identical added prose, only its surrounding file offsets moved. The rule is the session-side complement to the already-ratified daemon-side recovered-round closure, introduces no new restart path, and the daemon's cardinal rule (restart only on a fresh session-written ready) is unchanged.

## Resulting Changes

- spec.md
- scenarios.md
- contracts.md

## Ratification Review

ratification_review: auto-spawn
reviewer_model: fable
reviewer_identity: fable
separate_reviewer: True
read_only: True
reviewed_at: 2026-08-18T22:10:00Z
verdict: NO BLOCKERS
proposal_stem: winddown-rationale-expiry
content_digest: ea9e5e856232ab9a791d6fd6adbd2a5ccd5cf41349efbdfcc7f3701685111349
