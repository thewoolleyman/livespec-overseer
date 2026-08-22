---
proposal: set-or-scrub-fail-soft-tension.md
decision: accept
revised_at: 2026-08-22T05:09:20Z
author_human: thewoolleyman <chad@thewoolleyman.com>
author_llm: claude-opus-5-1m
---

## Decision and Rationale

ARM A ratified: the set-or-scrub rule wins and fail-soft is narrowed to mean the launch COMMAND rather than the whole behaviour. The proposal deliberately recommended neither arm so that ratification rather than authorship would decide; this pass decides it. Three legs. (1) The narrowing describes shipped, tested reality rather than changing it: the Claude no-profile branch already scrubs, and the scenario's own pinning test (test_scenario_track_without_recorded_launch_profile_restarts_unaffected) already asserts the bare command plus all four controlled variables explicitly unset, so the scenario prose was BEHIND its own test and this revision closes that gap. (2) The risk is asymmetric and points at Arm A: scrubbing variables a runtime does not read is a no-op, while failing to scrub one a future wrapper does read is the documented failure mode the rule exists to name. (3) Arm B is drafted as a permission (the daemon MAY pass no delta), which would leave the Codex path's internal inconsistency permitted but unmotivated and leave a conformance auditor unable to predict which of two conformant behaviours to expect; Arm A yields one testable invariant. The proposal's three factual claims were verified against overseer/_supervisor_launch_profile.py rather than taken on its word: Claude no-profile scrubs, Codex no-profile passes env=None, Codex cloud-profile scrubs. scenarios.md is amended alongside spec.md because the scenario 'A track with no recorded launch profile restarts unaffected' restated the very ambiguity being resolved; its heading is unchanged so no heading-coverage row is owed. The independent read-only fable reviewer returned NO BLOCKERS on these exact bytes, and separately observed the spec-to-impl gap this arm deliberately creates -- two Codex tests currently pin the opposite -- which is carried by work-item overseer-bc55wx.14 and is not a ratification blocker. Decision recorded on ledger item overseer-bc55wx.13.

## Resulting Changes

- spec.md
- scenarios.md

## Ratification Review

ratification_review: auto-spawn
reviewer_model: fable
reviewer_identity: fable
separate_reviewer: True
read_only: True
reviewed_at: 2026-08-22T04:46:34Z
verdict: NO BLOCKERS
proposal_stem: set-or-scrub-fail-soft-tension
content_digest: dc69c0018b58e75e265b82df4bcd567f3e0bc95cf05f820cfdbd47c929e52972
