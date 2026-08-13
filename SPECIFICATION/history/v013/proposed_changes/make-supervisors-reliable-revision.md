---
proposal: make-supervisors-reliable.md
decision: modify
revised_at: 2026-08-13T23:12:35Z
author_human: thewoolleyman <chad@thewoolleyman.com>
author_llm: codex
---

## Decision and Rationale

Accept the completion-gate contract while correcting the marker path to the existing shared supervisor-protocol location and placing its wire grammar in contracts.md. The change preserves the daemon's non-semantic boundary.

## Modifications

Use the established <repo>/tmp/overseer/<topic>/.supervisor-state path rather than a conflicting supervisor-suffixed path; add the wire-level contract to contracts.md; defer heading-coverage entries to the implementation slice, because revise may update only files inside the spec target.

## Resulting Changes

- contracts.md
- spec.md
- constraints.md
- scenarios.md

## Ratification Review

ratification_review: manual-spawn
reviewer_model: codex-gpt-5
reviewer_identity: codex-gpt-5
separate_reviewer: True
read_only: True
reviewed_at: 2026-08-13T23:11:29Z
verdict: NO BLOCKERS
proposal_stem: make-supervisors-reliable
content_digest: da7870af913c6f66b91bb2eb22b48aec2c37e5cdb2a46182da1e6b6588c665b7
