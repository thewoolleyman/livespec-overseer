---
proposal: codex-unidentified-session.md
decision: modify
revised_at: 2026-10-26T15:38:53Z
author_human: Chad Woolley <thewoolleyman@gmail.com>
author_llm: claude-opus-5-5
---

## Decision and Rationale

Accepted in substance; modified after two rounds of independent opus review, the final one NO BLOCKERS. As filed, recorded-pane identification checked only the repository binding, so a sibling plan's Codex session in the same repository could be adopted and later restarted under the wrong track, contradicting exact-name adoption; a vanished pane with no rebind candidate read unidentified instead of session-gone or misnamed; only the harness was re-recorded, defeating the stale-profile safeguard; the rebind was optional while its scenario required it; and the live-recorded-session guard had no scenario.

## Modifications

(1) Recorded-pane identification requires the backend-reported session to be bound to the repository by the state database AND named exactly the derived session name or equal to the row's recorded identity AND bound to no other track; this is exact-name adoption with per-carrier evidence, and a near-miss name stays unidentified. Pane resolution follows the contracts.md backend, instance and pane rules. (2) The whole launch profile is re-captured per The launch profile; an unreadable field leaves it stale (surfaced, restart skipped). Covers both a cross-runtime and an earlier same-runtime recorded session whose process is gone; a live recorded session keeps identity and profile. (3) Vanished-pane rebind is MUST with exactly one qualifying pane; zero leaves ordinary classification (session-gone or misnamed); several reads unidentified-session with refusing condition ambiguous panes. (4) The log event's dedup identity is the condition, re-arming on clear. (5) contracts.md membership widened to the ambiguous-panes case. (6) Four scenarios, including the live-recorded-session guard; coverage debt owned by overseer-5eqavc lands in the same commit outside the spec target.

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
reviewed_at: 2026-10-26T15:38:19Z
verdict: NO BLOCKERS
proposal_stem: codex-unidentified-session
content_digest: 9e8b963ab0c543fd9de14c8f8c53cf58a6abcddb9783275eab0665ebb58de5b3
