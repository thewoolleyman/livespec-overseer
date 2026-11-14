---
proposal: session-start-respects-live-seat-record.md
decision: accept
revised_at: 2026-11-14T05:53:48Z
author_human: Chad Woolley <thewoolleyman@gmail.com>
author_llm: claude-opus-5-5:herdr-overseer
---

## Decision and Rationale

Accepted unmodified. SPECIFICATION v106 section 'Supervision across machines' requires the sanctioned out-of-band relaunch entrypoint and every other session-starting surface to take or verify a plan topic's live-seat record for its own machine before launching, and not to launch when the record names another machine. The v106 post-step doctor found that no scenario pins this MUST (doctor-llm-subjective-behavior-coverage), and the implementation item overseer-bluagz waits on one. The new scenario states exactly the existing requirement and adds no new behaviour. The reworded OPAQUE LOCATOR sentence removes the reading that the daemon touches nothing on the plan epic besides handoff entries, which v106's live-seat record made untrue. The coordinator asked for this in its grade of #3022. Both edits stay within existing sections, and no heading changes.

## Resulting Changes

- scenarios.md
- spec.md

## Ratification Review

ratification_review: auto-spawn
reviewer_model: sonnet
reviewer_identity: sonnet
separate_reviewer: True
read_only: True
reviewed_at: 2026-11-14T05:53:06Z
verdict: NO BLOCKERS
proposal_stem: session-start-respects-live-seat-record
content_digest: 6fada35deecdfb47ad975af6bab7d798b60a29a926d60ae0d7b5eeb78eaa12e3
