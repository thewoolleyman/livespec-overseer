---
proposal: caam-weekly-reserve-release-ignores-serveability.md
decision: accept
revised_at: 2026-10-25T16:15:05Z
author_human: Chad Woolley <thewoolleyman@gmail.com>
author_llm: claude-opus-5-5
---

## Decision and Rationale

Accepted as proposed. Measured 2026-10-25 evidence (09:48Z switch onto protected anthropic-0 and 11:18Z-13:10Z empty-set hold, both at the default 10% reserve) shows the weekly-only release predicate keeps the reserve in force for accounts that cannot spend it while excluding the only unprotected accounts that can, contradicting the clause's own 'it protects nothing' rationale and the maintainer's goal 'All non-protected accounts should be able to be drained to zero.' The amendment keys the release on whether any unprotected account above the reserve is usable, leaves every per-account protection floor and the drain's condition (d) untouched, and adds eleven scenarios. Independently reviewed read-only to NO BLOCKERS over six rounds: the ratification reviewer is a separate read-only Opus Agent session spawned by seat caam-reserve-release (round 6, draft 6), with Codex gpt-6-astra concurring NO BLOCKERS on the same bytes per the plan brief.

## Resulting Changes

- spec.md
- scenarios.md

## Ratification Review

ratification_review: auto-spawn
reviewer_model: opus
reviewer_identity: opus
separate_reviewer: True
read_only: True
reviewed_at: 2026-10-25T16:14:32Z
verdict: NO BLOCKERS
proposal_stem: caam-weekly-reserve-release-ignores-serveability
content_digest: 971c9b73d1f02252dd7a81e5ddf5cba525fb24d1465345d297eb4d58fcaf19aa
