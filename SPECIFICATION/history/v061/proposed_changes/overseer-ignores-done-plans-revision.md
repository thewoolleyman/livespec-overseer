---
proposal: overseer-ignores-done-plans.md
decision: modify
revised_at: 2026-10-19T01:44:30Z
author_human: Chad Woolley <thewoolleyman@gmail.com>
author_llm: overseer-ignore-done-plans
---

## Decision and Rationale

Delegated decision (revise_decision_mode=delegated) by plan session overseer-ignore-done-plans under the maintainer's 2026-10-19 ~01:15Z direction, verbatim: "This is clearly a bug in the overseer. It should be doing absolutely nothing with done plans, much less burning any tokens on them. It should be completely ignoring them. The only reason they should not be closed is because I need to be able to read the wrap-up and ensure that they are completed. Open a new session with a plan to change the overseer to make it behave this way and drive it to completion." Scope approved by the coordinator gitops-fleet-capacity-monitoring at the session restart (done track = archived or holding done; no paste, keys, restart or void; quiet row; session stays open; generation-based void removed; re-open explicit only). Measured defect: plan epic overseer-jfp23f research 001. Departs deliberately from the supervision half of the 2026-09-12 archived-live maintainer ruling (code-only; never in SPECIFICATION/); its visibility half is ratified here. Independent Opus ratification review: NO BLOCKERS on digest 148e23dd866c9b41b3fabeba346ec948528e46a93de7dbeee9dcadf0b21dfb67.

## Modifications

Accepted with modification after an independent Opus ratification review (first pass: three BLOCKERS; fixed; second and third passes NO BLOCKERS). (1) The attention exemption now names 'a done track', and is split by kind: a track done by its own declaration keeps the malformed/aliased/resume-unsubmitted/wait-inventory/live-gate members; a track done because its plan is archived is an attention member only through live gate evidence and otherwise renders quiet whatever its state file holds. (2) The done-track paragraph gains a precedence sentence over every spec.md and contracts.md clause that would authorize an act on a done track or a write to its state file or round record, and spells out the read-only scope (no state-file write/delete/void/expire, no round close/delete/advance; event log and alert edge bookkeeping permitted). The contracts.md interlock 'Archived or gone' outcome states a done track never reaches it. (3) One session predicate everywhere: 'still exists (running or exited)'; the archived scenario heading reads 'An archived plan whose session still exists receives nothing'. (4) Re-open requires BOTH no standing done AND an unarchived directory; clearing is deleting the state file or overwriting it with a value other than done; the daemon keys on the directory alone and whoever moves it back must reopen the epic. (5) The contracts.md state-table row and the pair-stall exclusion point at the done-track rule. (6) One added scenario: 'An archived plan showing a picker is surfaced but not acted on'. All seven new or renamed scenarios carry TODO heading-coverage rows owned by overseer-jfp23f, replaced by the implementation child's tests.

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
reviewed_at: 2026-10-19T01:43:27Z
verdict: NO BLOCKERS
proposal_stem: overseer-ignores-done-plans
content_digest: 148e23dd866c9b41b3fabeba346ec948528e46a93de7dbeee9dcadf0b21dfb67
