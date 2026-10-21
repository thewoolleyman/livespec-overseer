---
proposal: herdr-held-attempt-scope.md
decision: modify
revised_at: 2026-10-21T10:13:59Z
author_human: Chad Woolley <thewoolleyman@gmail.com>
author_llm: claude-opus-5-5:herdr-overseer
---

## Decision and Rationale

Accepted in substance: the held-UNCONFIRMED rule read two ways, and under one reading a herdr Codex replacement can never complete, because the daemon's own /rename can never be confirmed and the hold then suppresses the resume line (factory run 01M5EVBNK0X1, code-confirmed in overseer/pane_router_submit.py). Modified after an independent opus ratification review returned two blockers against the proposal's literal text. First, 'Only those deliveries are ever held' contradicted contracts.md §'Daemon message delivery channel' (held channel deliveries, including the keep-going nudge). Second, the same-payload limit of the never-re-paste rule lived only in proposal prose while the spec sentence stayed ambiguous. The final text fixes both, and also states the unnamed-successor failure path. The re-review on these exact bytes returned NO BLOCKERS. No design record is contradicted: the change aligns the herdr arm with the tmux arm's session-index naming proof.

## Modifications

(1) Dropped 'Only those deliveries are ever held.' The hold is now an UNCONFIRMED wrap-up or expiry-notice PASTE, and an UNCONFIRMED channel delivery is held as contracts.md §'Daemon message delivery channel' defines. (2) The never-re-paste sentence is reworded so that a runtime whose empty input cannot be proven 'never has that payload pasted into it again while that payload's delivery is unconfirmed' (same payload only). While such a paste is held, no other daemon payload is pasted into that pane, with exactly two exceptions: the no-turn naming payload and the resume line to a proven successor. (3) Added a failure path: when the naming evidence does not appear within the replacement's bounded wait, the replacement keeps the ready declaration, surfaces the unnamed successor, and does not deliver the resume line. (4) Reworded the rename reference to 'the `/rename` command that names a fresh Codex successor after its topic'. (5) The scenario is unchanged from the proposal. The tests/heading-coverage.json TODO entry for it (work_item overseer-uzvcbn.5) lands in the same commit, outside the revise payload, because that file lies outside the spec target.

## Resulting Changes

- spec.md
- scenarios.md

## Ratification Review

ratification_review: auto-spawn
reviewer_model: opus
reviewer_identity: opus
separate_reviewer: True
read_only: True
reviewed_at: 2026-10-21T10:13:58Z
verdict: NO BLOCKERS
proposal_stem: herdr-held-attempt-scope
content_digest: 906019b7204640e994855c791487f57d383f81e76f1b42be9d89f9b4c3fb9be3
