---
proposal: remote-control-reissue-preserves-session-name.md
decision: modify
revised_at: 2026-11-15T22:06:41Z
author_human: Chad Woolley <thewoolleyman@gmail.com>
author_llm: claude-opus-5-5
---

## Decision and Rationale

DoD 4 of plan central-credential-service (epic overseer-iyfjbo, carrier overseer-fdwat6). Two measured defects on the role holder's journal across the 2026-11-15T16:47:30Z account switch: seats reconnected under auto-generated names that no other seat can address, and /remote-control opened the not-connected status panel, which the sweep dismissed as an ordinary panel before holding the seat for the whole ten-minute cap (about 12 minutes off Remote Control against a two-minute requirement). The proposal names the reconnect command from the session record and gives the not-connected panel a bounded, prompt retry. Its implementation, livespec-overseer#3099, was graded PASS WITH FIXES by legacy-coordinator-agent; those fixes are reflected in the proposal (null name treated as absent; the journal names panes dismissed at the not-connected panel; the dialog judged on a re-read record; a 40-second typing budget). Decided under spec_governance.revise_decision_mode delegated. The independent sonnet reviewer found no blockers and raised wording nits only: the per-sweep run limit and the offline journal key are named but not defined elsewhere; the control-character scenario names the refused name's pane while the clause says the refused name is named in the journal (the implementation journals the pane, deliberately keeping control characters out of the journal); the re-read rule's scope beyond the status panel is not pinned by a scenario. These are left for a follow-up proposal rather than changing the reviewed bytes.

## Modifications

Changes 1-7 are applied as written, with two modifications. (a) Two scenarios are added after the change-7 scenarios, because change 6 introduces two behaviours with no scenario: 'A sweep that runs out of time leaves the remaining seats to the next sweep' (the 40-second typing budget) and 'A seat that starts a turn after its reconnect command gets no key' (the dialog judged on the record read again after the command). (b) Change 2's journal statement is folded into the existing contracts.md sentence 'Each sweep MUST write one journal line per host naming ...', which now names the reconnect command with its name included and every name refused. Change 8's heading-coverage rows are a co-edit outside SPECIFICATION/, landed in the same pull request.

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
reviewed_at: 2026-11-15T22:05:56Z
verdict: NO BLOCKERS
proposal_stem: remote-control-reissue-preserves-session-name
content_digest: 78bedabd0c5883758d17953231d7124e39b87203f25148b7bd30decd8653fcfc
