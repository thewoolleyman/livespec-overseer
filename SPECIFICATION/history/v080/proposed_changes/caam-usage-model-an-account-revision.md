---
proposal: caam-usage-model-an-account.md
decision: accept
revised_at: 2026-10-31T19:01:28Z
author_human: Chad Woolley <thewoolleyman@gmail.com>
author_llm: claude-opus-5-5
---

## Decision and Rationale

Accepted as written. The three proposals state the behavior the caam usage reader is missing: a usage reading is a per-reading set of limits, an absent short window is a readable reading evaluated without short-window triggers, unrecognised limits from any provider are shown but never make an account unreadable, and contracts.md pins the Anthropic mapping (null five_hour = no short-window limit) plus a zero exit for such passes. Measured evidence: anthropic-1/-5/-6 return five_hour null and every scheduled pass on active anthropic-5 has exited 2 since 2026-10-31T09:21:57Z. The flagged design choice is settled as written: a candidate whose current reading carries no short-window limit is unconstrained on that dimension, so treating it as holding full short-window headroom (eligible, clear of the threshold for the drain, not excluded by the capacity test on that dimension) is the faithful reading of the provider's plan tier, and every weekly, refusal, protection and scoped rule still applies to it. Five scenarios are added, linked in tests/heading-coverage.json as TODOs owned by overseer-e6bvmt with matching debt-register rows. Revised under delegated decision mode with an auto-spawned independent read-only reviewer.

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
reviewed_at: 2026-10-31T18:59:30Z
verdict: NO BLOCKERS
proposal_stem: caam-usage-model-an-account
content_digest: eb37103b258bd331ffd8c090b8fafabb485b7dc56651b01b0f130ba465acabbc
