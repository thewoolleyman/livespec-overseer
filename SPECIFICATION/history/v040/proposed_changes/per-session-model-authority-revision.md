---
proposal: per-session-model-authority.md
decision: accept
revised_at: 2026-08-30T03:14:36Z
author_human: thewoolleyman <chad@thewoolleyman.com>
author_llm: claude-opus-4-8
---

## Decision and Rationale

Implements the two maintainer rulings of 2026-08-30 verbatim in direction: (a) a per-session Fable pin counts as an operator pin for scoped-model selection -- protection floor still outranks it, the pin waives only the relative-headroom margin, and anti-oscillation is preserved; and (b) model enforcement leaves an operator-set non-default model alone except when the scoped (Fable) allowance is unavailable on the active account, and never treats an unknown observed model as an operator choice. Independent read-only opus reviewer returned NO BLOCKERS on the exact resulting bytes.

## Resulting Changes

- spec.md

## Ratification Review

ratification_review: auto-spawn
reviewer_model: opus
reviewer_identity: opus
separate_reviewer: True
read_only: True
reviewed_at: 2026-08-30T03:12:55Z
verdict: NO BLOCKERS
proposal_stem: per-session-model-authority
content_digest: b7226dcf5867cc56426902408219cd1f43690f49c5e3c1c3800c35c7aad3e71a
