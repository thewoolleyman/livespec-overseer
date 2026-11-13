---
proposal: caam-reset-best-value.md
decision: modify
revised_at: 2026-11-13T04:12:22Z
author_human: Chad Woolley <thewoolleyman@gmail.com>
author_llm: claude-opus-5-5:herdr-overseer
---

## Decision and Rationale

Accepted with modifications after an independent read-only sonnet ratification review (two rounds; first round reported three blockers, second NO BLOCKERS). Ratifies the maintainer's 2026-11-12 direction (relayed verbatim by legacy-coordinator-agent): burn through one account and claim its reset at the weekly trigger while at least the claim horizon (default three days) remains, spend resets before they lapse, and keep one reset in reserve on a protected account unless it lapses within the expiry horizon, with protected-account, weekly-reserve, scoped-model and spend-cap precedence unchanged. Spec half of overseer-gejlii; code half overseer-sozqxs.

## Modifications

Three review blockers fixed. (1) The best-value clause fires on the active account's weekly trigger, meaning the weekly reserve or, for a protected account, its own protection floor, whichever fires first, so the protected-account reserve scenario reaches the clause. (2) Exclusions now also cover a dark active login, a login-held account and the scoped-model reserve trigger; when a trigger still fires after the claim's re-read, the rotation and exhausted-window rules apply unchanged. (3) A reached monthly extra-usage spend cap is an explicit exclusion rather than an appeal to SPEND-BLOCKED, which the reserve state never meets. Also: scenario givens say the weekly remaining has fallen below the reserve, matching the rotation trigger; the exhausted-window clause still requires the claim, including of a protected account's last reset; a lapse claim earlier in the same pass makes the best-value clause evaluate on its re-read and not claim again.

## Resulting Changes

- spec.md
- scenarios.md

## Ratification Review

ratification_review: auto-spawn
reviewer_model: sonnet
reviewer_identity: sonnet
separate_reviewer: True
read_only: True
reviewed_at: 2026-11-13T04:11:09Z
verdict: NO BLOCKERS
proposal_stem: caam-reset-best-value
content_digest: 59686737167cb4b142e83638e12cbd1118b988e46926c93fb33d6da6cab5d22b
