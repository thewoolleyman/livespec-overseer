---
proposal: busy-session-wrapup-delivery.md
decision: modify
revised_at: 2026-10-15T07:12:07Z
author_human: Chad Woolley <thewoolleyman@gmail.com>
author_llm: claude-opus-5-5:herdr-overseer
---

## Decision and Rationale

Both proposals implement the MAINTAINER RULING of 2026-10-15 (plan epic overseer-uzvcbn scope event; livespec-dev-tooling-dfixhe 06:57Z): deliver the wrap-up to a busy session whose input is positively empty, keeping only the input-protecting guards; and stop an un-rounded ready from deadlocking the wind-down, the measured 15h hold of gitops-fleet-capacity-monitoring. The restart interlock and the cardinal rule are unchanged: only a fresh certifiable ready restarts a session, under the unchanged no-busy restart gates. The departure from the prior accepted residual (contracts.md 'surfaced rather than healed') is deliberate and is the ruling's own subject. Ratification review: an independent read-only opus subagent (ratify-busy-wrapup, resolved model claude-opus-5-5) returned BLOCKERS on the first pass (07:07:03Z, five blockers, all addressed as described under Modifications) and NO BLOCKERS on the final bytes (07:11:07Z). Its non-blocking follow-ups: make the two retained context-recovery scenarios state that the latest wrap-up named no compaction; note the latch exception in the closing paragraph of Wind-down expiry on context recovery; the escalation-exhausted attention member still requires no busy evidence, so a busy non-declaring session surfaces only through other members; and the busy-Codex empty-composer probe names no mechanism, so it fails closed.

## Modifications

Refinements made after independent ratification review (blockers B1-B5 and notes N1-N5 of the first review pass), no change to the ruling's substance. (1) Placement: the delivery-only paragraph ('A paste into a busy session is a queued submission ... never killed mid-work') sits inside the first paragraph of spec.md §'The supervision round', before the recovered-round sentence; the residual clarification is a parenthetical inside the residual sentence rather than a following sentence. (2) Lockstep amendments the proposal omitted: constraints.md §'Acting safety' and spec.md's shared informational-paste safety floor (§'The keep-going nudge') now exempt ONLY the low-context wrap-up and its expiry-notice tail from the generating/changing/sub-agent-busy legs, with 'settled' meaning the input region for those two acts; foreign and ambiguous-identity panes stay forbidden, and the keep-going nudge, pair-stall nudge and charter reminder keep every leg. constraints.md is added to resulting_files. (3) Codex arm: contracts.md and spec.md now state that an IDLE Codex session's structural idle-input evidence is sufficient positive evidence of an empty composer, and that a BUSY Codex session needs evidence distinguishing the placeholder from typed text, else the paste is withheld and surfaced; the retained no-generating clause is replaced. (4) Retirement mechanism: instead of writing a new 'ready-unrounded: <detail>' value (outside the closed state-file vocabulary and holding a later round open against recovery), the daemon DELETES the state file under a same-token, same-modification-time guard, exactly as ready-side expiry deletes it, and records an edge-triggered alert; the retirement scenario's Then line follows. (5) The context-compaction latch, used normatively by the proposal, is DEFINED in a new spec.md section §'The context-compaction latch' (set by a rise of more than five points above the lowest known reading under the provably same live identity; cleared only by a changed identity; durable; an obligation never an authorization; re-arms bands once per latch; exempt from the recovered-round closure; latched wrap-ups state the compaction), ratifying behaviour already shipped under overseer-nb7ok7. spec.md §'Wind-down expiry on context recovery' gains the matching exception and §'The supervision round' recovered-round closure gains the latch exemption; four latch scenarios are added. (6) Wording: ambiguous runtime evidence resolves toward withholding a RESTART, and ambiguous input/identity/gate/human-wait evidence toward withholding a paste (Fail-soft bullet and the shell-only scenario's 'Or' line); the expiry-notice paragraph names a round-less `ready`; the retained never-in-a-round certification scenario says 'no round-open timestamp'. (7) tests/heading-coverage.json (outside the spec target) is co-edited: the two replaced scenario rows are removed; the new spec.md section maps to its existing unit test; the nine new scenario headings map to TODO rows owned by overseer-uzvcbn.3 acknowledging an owed integration-tier test.

## Resulting Changes

- constraints.md
- contracts.md
- scenarios.md
- spec.md

## Ratification Review

ratification_review: auto-spawn
reviewer_model: opus
reviewer_identity: opus
separate_reviewer: True
read_only: True
reviewed_at: 2026-10-15T07:11:07Z
verdict: NO BLOCKERS
proposal_stem: busy-session-wrapup-delivery
content_digest: 776437a2df0c68e55de0b7f1170b9ce9defc5fd4998b563782e18b8c6ce19e4c
