---
proposal: unconfirmed-wrapup-delivery.md
decision: modify
revised_at: 2026-10-15T09:47:18Z
author_human: Chad Woolley <thewoolleyman@gmail.com>
author_llm: claude-opus-5-5:herdr-overseer
---

## Decision and Rationale

Implements the MAINTAINER DIRECTIVE of 2026-10-15 (plan epic overseer-uzvcbn, highest priority): the herdr submit path reported delivered wrap-ups as failed pastes, un-opened the round so the session's later ready could never certify, and held a stuck per-pane attempt that suppressed every later paste (petri-factory-on-gmktec 08:09Z; gitops-fleet-capacity-monitoring 2026-10-14). Ratified as MODIFIED after two independent read-only Opus review passes; the maintainer chose to tighten before ratifying and confirmed the decision in this attended session.

## Modifications

Review pass 1 blockers resolved: (B1) the v058 busy-delivery sentence that required an unconfirmed submission to be handled as a failed opening paste now defers to the delivery outcomes; (B2) DELIVERED / FAILED / UNCONFIRMED are defined as three exclusive outcomes, UNCONFIRMED being the remainder and explicitly including a payload still standing in the input; (B3) completing an UNCONFIRMED delivery MUST NOT rewrite the stamp or raise the certification floor, and the residual exposure (a post-stamp ready when the paste did not land) is stated as accepted and bounded by stamp-before-paste and the restart interlock; (B4) the paragraph follows the 'That deletion' paragraph. Tightening pass (maintainer-requested): DELIVERED by turn start is scoped to a pane that was not already busy; FAILED requires an observation after the paste and before any Enter, and an unavailable observation never makes a paste FAILED; a held UNCONFIRMED attempt suppresses further pastes to that pane, stays surfaced, and is released when it resolves or when its round closes (so the post-restart resume line is not suppressed); no re-paste of a possibly queued payload. Scenarios added: a provably failed paste still un-opens its round; an unconfirmed delivery is completed without re-stamping or re-pasting; a held unconfirmed attempt is released when its round closes. Non-blocking review notes carried forward: (1) once Enter is sent a held attempt can only resolve DELIVERED, so 'or FAILED' in the release clause is reachable only before Enter; (2) a Codex UNCONFIRMED paste that never landed is held and surfaced, with the operator as the remedy; (3) completion only submits a payload the daemon still observes as its own; (4) holds are per pane, which is one-to-one with a track; (5) tests/heading-coverage.json maps every new heading.

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
reviewed_at: 2026-10-15T09:46:00Z
verdict: NO BLOCKERS
proposal_stem: unconfirmed-wrapup-delivery
content_digest: fd2341eee9b1b80549e4e6b1400faa350307c1d4e2955f91ec02d94ea7612cbc
