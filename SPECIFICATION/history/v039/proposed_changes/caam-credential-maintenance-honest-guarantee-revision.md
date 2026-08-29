---
proposal: caam-credential-maintenance-honest-guarantee.md
decision: accept
revised_at: 2026-08-29T02:13:32Z
author_human: thewoolleyman <chad@thewoolleyman.com>
author_llm: caam-anthropic-loop-planner
---

## Decision and Rationale

Maintainer accepted the wording in the planning session (spec_governance manual mode). The clause's pre-lapse refresh MUST is unsatisfiable with the delegated agent (measured on overseer-54k2za.47: agent refreshes only an already-expired credential); this states the honest guarantee the shipped code now delivers -- detect expiry immediately, decoupled from the cached-figure reporting ceiling, and refresh promptly to minimise the unselectable window. Every other obligation in the clause is preserved verbatim.

## Resulting Changes

- spec.md

## Ratification Review

ratification_review: manual-spawn
reviewer_model: opus
reviewer_identity: opus
separate_reviewer: True
read_only: True
reviewed_at: 2026-08-29T02:11:29Z
verdict: NO BLOCKERS
proposal_stem: caam-credential-maintenance-honest-guarantee
content_digest: d7d96acb5551bfc810317199019394808700066821779659e5168ce72e82981a
