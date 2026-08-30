---
proposal: launch-profile-records-the-launch-model.md
decision: accept
revised_at: 2026-08-30T04:03:50Z
author_human: thewoolleyman <chad@thewoolleyman.com>
author_llm: claude-opus-5-1m
---

## Decision and Rationale

RATIFIED ON THE PROPOSAL'S OWN RECOMMENDED BRANCH by explicit maintainer ruling, 2026-08-30, carried by work-item overseer-0y69 under plan epic overseer-ebik5q (model-mismatch-veto-residue). Explicitly NOT Alternative A (amend clause (ii) to permit the statusline for context-variant recovery) and NOT Alternative B (permit the transcript message.model as a source); both were put to the decision-maker with their documented costs and neither was selected. WHY THE NARROWING RATHER THAN A CODE FIX: the ratified clause was measured unsatisfiable as written -- a mid-session model switch rewrites neither argv nor environ, so for a hand-launched session clause (i) cannot be honored under clause (ii), which forbids the statusline as a primary source. The narrowing resolves that without reopening clause (ii), which is left intact and byte-identical. WHAT IS RETAINED AND WHAT NARROWS: the capture-at-adoption and re-check-at-wrap-up obligation is retained in full; only the guarantee attached to it narrows, to the model the track was LAUNCHED with. The conceded case is stated explicitly with a MUST-surface obligation rather than left as a silent outcome. THE SURFACING OBLIGATION IS SCOPED TO BASELINED TRACKS, and that scoping is itself a maintainer ruling rather than a drafting choice. The independent review measured that restart_blocked_by_statusline_mismatch returns with no alert AT ALL when a profiled row carries no recorded statusline baseline, so an unscoped MUST would have been breached on the day it was ratified. The maintainer ruled to scope the obligation to what the daemon honors and to file the remainder rather than ratify a knowingly-breached clause. A following paragraph states the scoping is NOT a blessing: an unbaselined track has nothing to compare against, and the daemon MUST NOT be reported, or relied upon, as having verified the re-asserted model for it. The remainder is overseer-ebik5q.2. THE PROPOSAL'S ONE STATED PRECONDITION was that a revise pass may reasonably require overseer-zkwf closed first, because the concession is sound only if the surfacing obligation rests on real machinery. overseer-zkwf is closed and its work landed as merged PR 1513 -- but the review established that it closed the case only for rows that CARRY a baseline, which is exactly why the obligation is scoped rather than taken as fully met. COVERAGE: one new scenario, linked to a new integration-tier test asserting the DISTINCTION rather than either half of it -- a baselined row whose statusline no longer parses restarts anyway AND raises the unreadable alert, while the same baseline rendering in agreement raises none. Mutation-verified in three directions. The coverage link rides as a sibling working-tree edit because resulting_files paths are spec-target-relative and cannot name a repo file outside the spec tree. CUT AS v041 AFTER A VERSION COLLISION: this ratification was first cut locally as v040 while an unrelated thread merged its own v040 (585d21b1, per-session model authority in the caam rotation contract). The collision was the version DIRECTORY, not the text -- the two sections sit 744 lines apart and the review found no semantic interaction. It re-cut cleanly on the new base, where the reviewed change was proven byte-identical by reconstruction. REVIEW PROVENANCE: the independent read-only reviewer blocked FOUR times before clearing these bytes, and twice retracted its own earlier finding after running what it had previously only read. Exactly one of its findings ever touched the ratified files; the rest concerned records describing the change and were resolved outside the specification. NOT IN SCOPE: the model_profile fourth-key divergence against contracts.md, tracked as overseer-5a4q, whose baseline this ratification decides rather than performs.

## Resulting Changes

- spec.md
- scenarios.md

## Ratification Review

ratification_review: auto-spawn
reviewer_model: opus
reviewer_identity: opus
separate_reviewer: True
read_only: True
reviewed_at: 2026-08-30T04:03:44Z
verdict: NO BLOCKERS
proposal_stem: launch-profile-records-the-launch-model
content_digest: 5192f6e09b7c56a87923d13de4886ec0160627ca33ce136e07f3617348e605dd
