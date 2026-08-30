---
proposal: launch-profile-records-the-launch-model.md
decision: accept
revised_at: 2026-08-30T03:36:02Z
author_human: thewoolleyman <chad@thewoolleyman.com>
author_llm: claude-opus-5-1m
---

## Decision and Rationale

RATIFIED ON THE PROPOSAL'S OWN RECOMMENDED BRANCH by explicit maintainer ruling, 2026-08-30, carried by work-item overseer-0y69 under plan epic overseer-ebik5q (model-mismatch-veto-residue). Explicitly NOT Alternative A (amend clause (ii) to permit the statusline for context-variant recovery) and NOT Alternative B (permit the transcript message.model as a source); both were put in front of the decision-maker with their documented costs and neither was selected. WHY THE NARROWING RATHER THAN A CODE FIX: the ratified clause was measured unsatisfiable as written -- a mid-session /model switch rewrites neither argv nor environ, so for a hand-launched session clause (i) cannot be honored under clause (ii), which forbids the statusline as a primary source. The narrowing resolves that without reopening clause (ii), which is left intact. THE PROPOSAL'S ONE RATIFICATION PRECONDITION IS SATISFIED RATHER THAN WAIVED: it states a revise pass may reasonably require overseer-zkwf closed first, because the concession is sound only if the surfacing obligation rests on real machinery rather than on the implementation being assumed adequate. overseer-zkwf is closed and its work landed as merged PR 1513. SCOPE: the capture-at-adoption and re-check-at-wrap-up obligation is retained in full; only the guarantee it carries is narrowed, to the model the track was LAUNCHED with. The conceded case is stated explicitly with a MUST-surface obligation rather than left as a silent outcome, and that surfacing must distinguish having read the verification signal and agreed from not having read it at all -- the fail-soft hole overseer-zkwf closed. A new scenario pins that obligation and is linked in tests/heading-coverage.json to the already-shipped test that asserts both halves, so the ratified behavior is covered rather than merely asserted. That coverage link rides as a sibling working-tree edit in the same commit, because resulting_files[] paths are spec-target-relative and cannot name a repo file outside the spec tree. THE SURFACING OBLIGATION IS SCOPED TO BASELINED TRACKS, AND THE SENTENCES ABOVE PREDATE THAT RULING. This rationale was composed before the ratification's independent review ran; the paragraph above describes the surfacing obligation UNSCOPED, which is not what was ratified. The ratified text scopes it: surfacing must distinguish read-and-agreed from not-read-at-all FOR A TRACK WHOSE PROFILE CARRIES A RECORDED VERIFICATION BASELINE, and a following paragraph states that the scoping is not a blessing -- an unbaselined track has nothing to compare against, and the daemon must not be reported, or relied upon, as having verified the re-asserted model for such a track. The earlier sentences are left in place rather than rewritten because they record what was believed at the time, but the scoped form is what governs.

WHY IT WAS SCOPED: the independent review measured that the daemon emits no alert at all when a profiled row carries no recorded baseline, so an unscoped MUST would have been violated on the day it was ratified. The maintainer ruled to scope the obligation to what the daemon honors and to file the remainder rather than ratify a knowingly-breached clause. That remainder is overseer-ebik5q.2.

PROVENANCE OF THE REVIEW, recorded because it bears on how much the NO BLOCKERS verdict is worth. The independent read-only reviewer blocked FOUR times before clearing these bytes, and twice retracted its own earlier finding after running what it had previously only read -- once about a whole harness class it had wrongly declared structurally excluded, once about the completeness of its own enumeration. Exactly one of its five findings ever touched the ratified files (a scenario that overclaimed relative to its test, fixed and re-reviewed); the rest concerned records describing the change and were resolved outside the specification. The digest-covered bytes were confirmed unmoved by content hash across three consecutive passes.

NOT IN SCOPE: the model_profile fourth-key divergence against contracts.md, which is tracked separately as overseer-5a4q and whose resolution this ratification decides the baseline for rather than performs.

## Resulting Changes

- spec.md
- scenarios.md

## Ratification Review

ratification_review: auto-spawn
reviewer_model: opus
reviewer_identity: opus
separate_reviewer: True
read_only: True
reviewed_at: 2026-08-30T03:35:56Z
verdict: NO BLOCKERS
proposal_stem: launch-profile-records-the-launch-model
content_digest: d30fde49c8b6a5815dbd66781fc45ae883597cf4d23d05cbac226b377c581d6d
