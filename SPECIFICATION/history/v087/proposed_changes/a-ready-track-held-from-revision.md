---
proposal: a-ready-track-held-from.md
decision: accept
revised_at: 2026-11-05T14:58:49Z
author_human: Chad Woolley <thewoolleyman@gmail.com>
author_llm: claude-opus-5-5
---

## Decision and Rationale

Accepted all three proposal sections (Bounded ready-hold event; Stuck harness session-status diagnosis in the ready-hold event; Latched wrap-up names the latch and the live context reading) under delegated decision mode per coordinator ruling R301, which pre-accepted this revise as observability-only. The changes add a report-only ready-hold diagnostic event, a stuck-status diagnosis in that event, a third overseerd launch option with a corrected option list, and latched wrap-up wording; no restart gate, interlock precondition, cascade order or authorization changes. No design-record contradiction is introduced: the departure from §"Notify, never block"'s per-condition re-arm is stated explicitly by the proposal itself. Three cosmetic reviewer nits were applied in the resulting bytes without changing meaning: the replaced spec.md §"The context-compaction latch" bullet ends with '.' since it is now the last bullet; the contracts.md §"The wrap-up injection" insertion is rendered as continuation paragraphs of the 'Message obligations' list item; and the spec.md §"The restart" sentence names the holding condition 'pane-identity' (the immediate pre-act identity re-check) to match contracts.md. tests/heading-coverage.json receives TODO entries (work item overseer-qz7ez7) for all 18 new scenario headings.

## Resulting Changes

- contracts.md
- scenarios.md
- spec.md

## Ratification Review

ratification_review: auto-spawn
reviewer_model: sonnet
reviewer_identity: sonnet
separate_reviewer: True
read_only: True
reviewed_at: 2026-11-05T14:55:00Z
verdict: NO BLOCKERS
proposal_stem: a-ready-track-held-from
content_digest: 3e47b5b1c99deea2fc559e6bfdcae67968735302d9e458b14a80536a13a8a1dd
