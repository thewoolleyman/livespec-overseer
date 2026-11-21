---
proposal: session-window-rotation.md
decision: accept
revised_at: 2026-11-21T00:30:26Z
author_human: Chad Woolley <thewoolleyman@gmail.com>
author_llm: claude-sonnet-5-5
---

## Decision and Rationale

Delegated decision (revise_decision_mode: delegated), accepted with modifications made during review. Maintainer direction (livespec-dev-tooling-6tgd2z): "Yes do that. Just get things working the way they're supposed to so they rotate automatically to whatever is available and manage it correctly". The final text adds the 5-hour session-window trigger (default CAAM_ROTATE_FIVE_HOUR_REMAINING 15 -> 20, stated explicitly), a never-select-protected rule under that trigger (declared strengthening of the existing protected-selection clause, no MUST weakened), dry-run reporting, trigger-precedence placement, and protection limited to operator-marked accounts with the committed set marking only anthropic-0. Two earlier review rounds found blockers (refusal-trigger interaction, reset-claim interaction, threshold units, dry-run vs mode resolution, committed-set vs per-account floors); all were resolved in the text before this decision. Three scenarios added with TODO coverage rows and debt rows owned by overseer-xwfyxy (v120 precedent).

## Resulting Changes

- spec.md
- scenarios.md

## Ratification Review

ratification_review: auto-spawn
reviewer_model: sonnet
reviewer_identity: sonnet
separate_reviewer: True
read_only: True
reviewed_at: 2026-11-21T00:26:26Z
verdict: NO BLOCKERS
proposal_stem: session-window-rotation
content_digest: 4e5a75f9317b5da816e7d5b78172094e80f083353d2e6458770da68508dbefb0
