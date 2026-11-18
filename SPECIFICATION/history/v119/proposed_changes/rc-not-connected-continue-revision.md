---
proposal: rc-not-connected-continue.md
decision: accept
revised_at: 2026-11-18T12:47:18Z
author_human: Chad Woolley <thewoolleyman@gmail.com>
author_llm: central-credential-service
---

## Decision and Rationale

Accepted on legacy-coordinator-agent's R301 decision, made on the maintainer's behalf (message at ~13:0xZ, 2026-11-18), recorded verbatim: "REVISE DECISION (R301, the maintainer's behalf): ACCEPT livespec-overseer#3158, topic rc-not-connected-continue, AS WRITTEN. Basis: today's 12:17Z rotation blocked 15 seats on the not-connected panel, and the ratified Escape answer dismisses it without reconnecting. Enter on a re-read Continue for idle and busy seats, then /remote-control <name> for idle seats after at least 12 s, matches the panel's own text and what cleared all 15 by hand." Executed by central-credential-service as the plan seat, not a self-review. The final bytes also rename the mid-turn scenario heading and add the fresh-session scenario, both in the proposal.

## Resulting Changes

- contracts.md
- scenarios.md

## Ratification Review

ratification_review: auto-spawn
reviewer_model: sonnet
reviewer_identity: sonnet
separate_reviewer: True
read_only: True
reviewed_at: 2026-11-18T12:46:58Z
verdict: NO BLOCKERS
proposal_stem: rc-not-connected-continue
content_digest: 7fb5f8c7d6668c23d6aa07627666e3887741307eba4bbe251a509dfa4649b50a
