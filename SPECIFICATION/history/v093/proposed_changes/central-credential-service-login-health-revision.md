---
proposal: central-credential-service-login-health.md
decision: accept
revised_at: 2026-11-10T20:59:49Z
author_human: Chad Woolley <thewoolleyman@gmail.com>
author_llm: claude-opus-5-5-central-credential-service
---

## Decision and Rationale

ACCEPT all three proposals exactly as filed. Delegated decision under spec_governance.revise_decision_mode=delegated, taken by the central-credential-service plan session (epic overseer-iyfjbo), carrying out the maintainer's 2026-11-10 rulings recorded as that plan's Definition-of-Done assertions 12 (a dark or expired login is an automatic rotation trigger), 13 (track login age and warn ahead of the lifetime cap) and 14 (push alerts to the maintainer for near-dark logins and unusable factory credentials). The evidence is the 2026-11-10 outage: anthropic-3, the active account, reached its login lifetime cap at about 15:14Z and about 25 seats stalled for about 4.5 h, because no rotation trigger covers a dead login and the scheduled passes were driven by a session on that same dark login. The proposals add a trigger, a hold, login records, a host-started schedule on the role holder and push alerts; they change no eligibility or ranking rule, so the hold keeping caam selection rules unchanged until the central instance is proven stands. No design-record contradiction. Placement note: the first proposal anchors its two dark-login paragraphs AFTER the usage-limit refusal paragraph and its two named continuation paragraphs ("The operation MUST remember each attributed refusal" and "The refusal trigger fires only while") and BEFORE "**Which credential a refusing session used.**", but in spec.md that paragraph precedes both named continuations, so the two constraints cannot both hold. The paragraphs are placed after "The refusal trigger fires only while" and before "**Trigger precedence.**", honouring the two explicitly named continuation paragraphs; their text is unchanged. Every other edit lands at its stated anchor verbatim. Twenty new scenarios land as spec-first TODO rows in tests/heading-coverage.json with matching tests/heading-coverage-debt.json entries, owned by overseer-iyfjbo and co-edited in the same commit.

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
reviewed_at: 2026-11-10T20:59:22Z
verdict: NO BLOCKERS
proposal_stem: central-credential-service-login-health
content_digest: aa78b729cb677bbc02deed34055430c4bf9124496f3a5575bdfed74cb34d7fa8
