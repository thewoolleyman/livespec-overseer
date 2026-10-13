---
proposal: caam-expiring-quota-drain.md
decision: accept
revised_at: 2026-10-13T10:18:26Z
author_human: Chad Woolley <thewoolleyman@gmail.com>
author_llm: claude-opus-5-5
---

## Decision and Rationale

Ratifies the expiring-quota drain trigger whose design the maintainer settled on 2026-10-13 (no new configuration; the existing eligibility margin as a buffer from every threshold; at least one-minute-sooner weekly reset; one return per short-window cycle; protection ordering preserved) and directed this session to carry forward autonomously. Five independent read-only opus ratification reviews were run; the first four found blockers that were fixed in the proposal before this decision, and the fifth found NO BLOCKERS on these exact bytes. Decided under revise_decision_mode delegated; the maintainer did not review these final bytes, and the departures from the agreed design that review forced are recorded in plan/caam-expiring-quota-drain/research/003-drain-rule-design.md.

## Resulting Changes

- contracts.md
- scenarios.md
- spec.md

## Ratification Review

ratification_review: auto-spawn
reviewer_model: opus
reviewer_identity: opus
separate_reviewer: True
read_only: True
reviewed_at: 2026-10-13T10:18:25Z
verdict: NO BLOCKERS
proposal_stem: caam-expiring-quota-drain
content_digest: 22dc85c7e96be2d7c4ff2a583fa07ae1788acda01fd796248e40f55395282349
