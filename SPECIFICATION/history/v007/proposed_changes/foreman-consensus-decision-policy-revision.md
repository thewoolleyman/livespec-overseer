---
proposal: foreman-consensus-decision-policy.md
decision: accept
revised_at: 2026-08-04T13:57:31Z
author_human: thewoolleyman <chad@thewoolleyman.com>
author_llm: claude-opus-5
---

## Decision and Rationale

Accepted as filed on the maintainer's explicit ruling. The proposal supplies the consensus-decision policy that spec.md's own self-retiring clause deferred to, so that clause retires by its own terms rather than by reversal. It reverses nothing: the governing orchestrator contract's floor is preserved verbatim, and every human-gated-by-design category - drift acceptance included - stays escalated even under a unanimous panel. The safe default is report-only, so a tree that declares nothing behaves exactly as before. The cross-vendor panel this policy authorizes is already built and released in this repo; what was missing was the ratified policy authorizing it to act. Independent read-only ratification review returned NO BLOCKERS against these exact bytes after one blocking finding (a dangling section anchor in contracts.md) was corrected and re-reviewed.

## Resulting Changes

- spec.md
- constraints.md
- contracts.md
- scenarios.md

## Ratification Review

ratification_review: manual-spawn
reviewer_model: claude-fable-5
reviewer_identity: claude-fable-5
separate_reviewer: True
read_only: True
reviewed_at: 2026-08-04T13:57:16Z
verdict: NO BLOCKERS
proposal_stem: foreman-consensus-decision-policy
content_digest: d6e4fd5572031c5ebd1e535b91414f5c0ff24ef5d900bfe3252d5058bf18320f
