---
proposal: blocked-onboarding-classification.md
decision: modify
revised_at: 2026-10-26T04:14:35Z
author_human: Chad Woolley <thewoolleyman@gmail.com>
author_llm: claude-opus-5-5
---

## Decision and Rationale

Accepted in substance. Modified for consistency with existing ratified MUSTs, following four rounds of independent review (the final round returned NO BLOCKERS). The onboarding-screen resolution is a keystroke into a gated pane, which constraints.md §"Acting safety" forbade. Classifying those screens outside the waiting-on-a-human class contradicted the contracts.md keep-going-nudge, restart-interlock and status-snapshot rules. Those sections now carry explicit, bounded carve-outs, so the existing guards are not widened.

## Modifications

(1) constraints.md §"Acting safety": the first sentence names a first-run onboarding exception; the gated-pane sentence states that the exception is not an informational act and does not widen the charter reminder; a new paragraph defines the exception with its guards (exact match, re-read before each keystroke, trust only for the track's recorded repository, no bare Enter on the exit option, no other gate or pane). (2) spec.md: the pane-text trust sentence admits the exact-match onboarding classification, including the trust prompt's folder. `blocked-onboarding` is defined as a distinct KIND of waiting on a human that suppresses the keep-going nudge and the wrap-up paste, and the new section cites the constraints.md carve-out. (3) contracts.md: the keep-going-nudge gate sentence and the restart-interlock 'never keystroked' bullet name the exception. The status-snapshot paragraph lists `blocked-onboarding` among the human-waiting statuses consumers treat alike and never promotes it to picker-stall. (4) tests/heading-coverage.json gains four TODO entries owned by overseer-q156, landed in the same commit (the file lies outside the spec target, so it is not a resulting file); the reviewer reviewed those bytes too.

## Resulting Changes

- spec.md
- scenarios.md
- constraints.md
- contracts.md

## Ratification Review

ratification_review: auto-spawn
reviewer_model: opus
reviewer_identity: opus
separate_reviewer: True
read_only: True
reviewed_at: 2026-10-26T04:13:59Z
verdict: NO BLOCKERS
proposal_stem: blocked-onboarding-classification
content_digest: d3ab7c2b0f2d8b4ec76eec9694e49bd8380564dc0189807ae5f7ed5c11927db2
