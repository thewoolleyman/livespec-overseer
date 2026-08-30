---
proposal: servable-pin-survives-fable-exhaustion.md
decision: accept
revised_at: 2026-08-30T06:51:28Z
author_human: thewoolleyman <chad@thewoolleyman.com>
author_llm: claude-opus-4-8-1m
---

## Decision and Rationale

Maintainer-directed accept (2026-08-30): the servability-bounded reading is the maintainer's confirmed choice, and this corrects the ambiguous v040 exception that the shipped impl (#2045) read as a blanket reset. Independent read-only opus ratification review returned NO BLOCKERS over the exact final bytes.

## Resulting Changes

- spec.md

## Ratification Review

ratification_review: auto-spawn
reviewer_model: opus
reviewer_identity: opus
separate_reviewer: True
read_only: True
reviewed_at: 2026-08-30T06:50:58Z
verdict: NO BLOCKERS
proposal_stem: servable-pin-survives-fable-exhaustion
content_digest: 3e95b59b90a40636dda69c1979b7b6777baf3198ef227a2f62728f44d40a9b65
