---
proposal: a-codex-replacement-or-relaunch.md
decision: accept
revised_at: 2026-11-13T12:01:18Z
author_human: Chad Woolley <thewoolleyman@gmail.com>
author_llm: claude-opus-5-5:herdr-overseer
---

## Decision and Rationale

Accepted unmodified after an independent read-only sonnet ratification review reporting NO BLOCKERS. Ratifies the behaviour overseer-dd5qus implements: every Codex launch the daemon or the sanctioned relaunch composes passes check_for_update_on_startup=false, so a launched successor never opens at Codex's update picker, a structured gate the daemon correctly never keystrokes. Measured need: the isolated Codex herdr exercise on released v5.55.6 failed its replacement stage 3/3 plus an independent replay, with the successor parked at 'Update available 0.167.1 -> 0.169.0'. Reviewer's non-blocking notes (the no-profile scenario's 'exactly the COMMAND' wording, the wrapper pass-through, an optional no-profile scenario) are left to the implementation item; none changes the clause.

## Resulting Changes

- spec.md
- scenarios.md

## Ratification Review

ratification_review: auto-spawn
reviewer_model: sonnet
reviewer_identity: sonnet
separate_reviewer: True
read_only: True
reviewed_at: 2026-11-13T12:01:16Z
verdict: NO BLOCKERS
proposal_stem: a-codex-replacement-or-relaunch
content_digest: fce1556b46b4f13049fbdc42b4925ef989c260283df696a73c8875f5166aa773
