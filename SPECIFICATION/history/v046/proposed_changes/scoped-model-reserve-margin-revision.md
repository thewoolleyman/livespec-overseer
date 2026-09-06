---
proposal: scoped-model-reserve-margin.md
decision: accept
revised_at: 2026-09-06T11:22:05Z
author_human: thewoolleyman <chad@thewoolleyman.com>
author_llm: claude-opus-4-8
---

## Decision and Rationale

Adds a configurable scoped-model reserve (CAAM_ROTATE_FABLE_REMAINING, default 15% remaining) so a Fable-dependent session is rotated off an account before its Fable reaches zero, with the anti-oscillation guarantee that a reserve-triggered move lands only on an account holding Fable above the reserve (else it holds). Reduces byte-exactly to the ratified v045 cannot-serve behaviour at reserve 0; protection floors and the no-fourth-way bound unchanged. Fixes incident overseer-dyt6.

## Resulting Changes

- spec.md

## Ratification Review

ratification_review: auto-spawn
reviewer_model: opus
reviewer_identity: opus
separate_reviewer: True
read_only: True
reviewed_at: 2026-09-06T11:19:56Z
verdict: NO BLOCKERS
proposal_stem: scoped-model-reserve-margin
content_digest: e9020120ac069e6f36cf4ab3dafa13660587fa6a37c5833418ef973bd9eb086e
