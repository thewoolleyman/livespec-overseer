---
proposal: caam-capacity-aware-rotation.md
decision: accept
revised_at: 2026-10-15T02:15:30Z
author_human: Chad Woolley <thewoolleyman@gmail.com>
author_llm: claude-fable-5-1
---

## Decision and Rationale

Accepted as-is. The proposal adds four rules to the account-rotation section: a refusal trigger (an account seen refusing requests for a usage limit is left and not returned to until its refusal lapses), a fast-drain trigger (an account whose short-window remaining, projected at its observed burn rate across the projection horizon, would reach the floor before the next pass is left now), a capacity test on eligibility (a candidate the current fleet load would drain to the floor within the horizon is not selected, released only for a refusal-held active account with no passing candidate), and live capacity-class reporting; it keeps v055's capacity-blind ranking and rewords only its rationale, per the maintainer's 2026-10-14 ruling in plan/caam-mixed-plan-capacity/research/002-scope-and-capacity-ruling.md. Six independent read-only ratification review rounds ran on the proposal (PR #2472; round 6 RATIFIABLE, no blockers), a separate Fable review on 2026-10-15 returned APPROVE with no blockers and no wording changes, and the independent opus reviewer recorded below found NO BLOCKERS on these exact resulting bytes. Decision ownership: revise_decision_mode delegated; the human decision is the maintainer's recorded authorization of 2026-10-15 00:08Z (livespec-dev-tooling-dfixhe scope event: the freeze driver may approve spec revises on the maintainer's behalf after a Fable subagent review) exercised as REVISE APPROVAL #6 at 02:07Z on that record, after the maintainer ruled at 02:00Z that this plan is a priority because it would have avoided the 2026-10-15 01:25Z session-limit outage. The sibling proposal caam-quota-resets is left pending for its own revise (v057), which extends its closed trigger list to these two triggers and answers the refusal-held-with-claimable-reset question.

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
reviewed_at: 2026-10-15T02:14:48Z
verdict: NO BLOCKERS
proposal_stem: caam-capacity-aware-rotation
content_digest: 583af5971d676362aa97b688f51a43c658a3b8e04bf585ff967e69fe9ec445ef
