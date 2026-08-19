---
proposal: acting-safety-third-keystroke-act.md
decision: accept
revised_at: 2026-08-19T12:15:41Z
author_human: thewoolleyman <chad@thewoolleyman.com>
author_llm: claude-opus-5-supervision-safety-thread
---

## Decision and Rationale

ACCEPTED. Both findings in this proposal are accepted in ONE pass: finding 2's five-act enumeration names the stalled-picker charter reminder as a member and therefore presupposes finding 1, so they are not separable.

WHAT WAS RATIFIED. (a) constraints.md §"Acting safety" now enumerates FIVE keystroke-bearing acts by name instead of two by section reference, and reconciles its blanket prohibition: gated and human-waiting panes MUST never be pasted into by any DAEMON informational act EXCEPT the stalled-picker charter reminder under its own complete predicate, which MUST NOT be widened to any other daemon act, pane class, or topic class. Its opening sentence now names that exception rather than reading universally. (b) spec.md gains §"The stalled-picker charter reminder" stating the act's complete independent predicate. (c) spec.md's separate closed count, which read "Exactly three acts", is amended in the SAME pass to the identical five-act enumeration, with the fifth member explicitly qualified as the one act that INVERTS the floor's gated and human-waiting legs while remaining subject to every leg not named in that sentence. (d) Three scenarios pin the act, including a negative control on ordinary worker topics and a paste-echo leg.

PANEL DISPOSITIONS APPLIED. Q1 both reserved suffixes (-supervisor AND -foreman); Q2 the once-per-episode clause lands only with the code made true; Q3 five acts with the ready-expiry notice enumerated as a member but characterized as the wrap-up's round-scoped tail. Panel record: tmp/overseer/foreman/consensus/4e066523c6948156e4a2b8497ddcecc61b66ea17b39364188ec3d394f06ad2d4.json.

Q2's PRECONDITION WAS VERIFIED DISCHARGED, not assumed. overseer-6tfncs.1 merged as PR #1209 at 2026-08-19T10:53:08Z, and _supervisor_progress.blocked_human_stall_seconds was read directly: on a capture change it preserves picker_stall_nudged when the new capture equals the recorded paste echo, and resets it otherwise. PR #1215, which removed the passages instructing a revise session to WITHHOLD that clause, was confirmed merged at 11:19:28Z before this pass began.

THE INDEPENDENT RATIFICATION REVIEW REJECTED THIS TEXT THREE TIMES BEFORE PASSING, and every rejection was a case of the letter claiming something untrue of the daemon -- the exact defect class this proposal exists to close, reproduced in the drafting of its own remedy. Recorded because the corrections are load-bearing:
  (1) The draft said the session's DECLARED status is `blocked:human`. That value is not declarable: spec.md §"Out-of-band state declaration" fixes the writable set at ready / blocked: <reason> / winding-down, while `blocked:human` is DERIVED by the daemon (_supervisor_evaluate.py:214 from a foreman pane claim, :250 from live gate evidence ALONE). The clause named a value in a vocabulary that does not contain it AND added a precondition the daemon does not enforce, putting the act's common case outside its own specification. Corrected in the spec bullet, the episode-end sentence, and both scenario Givens.
  (2) The draft enrolled the act in spec.md's shared suppression floor, which mandates suppression while gated and human-waiting -- a floor this act inverts by firing ONLY when gated and human-waiting. spec.md was left self-contradictory. Corrected by qualifying the fifth member in that sentence while keeping membership and count at five.
  (3) The FIX to (1) introduced a fresh overstatement: it listed three sources for how `blocked:human` is reached, as a closed list. Four independent enumerations of the producers -- two by the author, two by reviewers -- returned four different answers, which is why the ratified text now declares the list non-exhaustive and makes only one positive claim, scoped to the act's own firing envelope. That envelope claim was then verified exhaustively rather than by construction, including that _supervisor_foreman_escalation yields `foreman-escalated` and never `blocked:human`.
  (4) A MINOR that was corrected anyway: the row a consumer sees after promotion is `picker-stalled`, not `blocked:human` (_supervisor_picker_stall.py returns the promoted status while the clock keys on the INPUT status). The episode-end sentence was technically true but its plain reading would have a reader conclude the episode ends at promotion and the act re-arms every tick -- the inverse of the bound PR #1209 established. It now names the EVALUATED status and states it is not necessarily the status finally published.

INTENT-PRESERVATION ACKNOWLEDGMENT. This resolution settles a conflict BETWEEN RATIFIED STATEMENTS: spec.md counted the ready-expiry notice as one of three distinct acts, while §"The escalating wrap-up" subjects that same notice to the wrap-up's complete guarded-paste predicate and calls it a bounded companion; constraints.md meanwhile said "exactly two". NO DESIGN RECORD EXISTS IN THIS SPEC TREE for either statement -- there is no design-record file at all -- so no cited record could be consulted, and that absence is surfaced here rather than silently resolved (revise_decision_context carries design_record_unavailable). The resolution takes NEITHER reading exclusively: the notice is ENUMERATED as a member and CHARACTERIZED as the wrap-up's round-scoped tail firing under the wrap-up's own predicate, so both ratified sentences are preserved in substance and made to agree in form. The departure was decided by the unanimous panel cited above under maintainer delegation, and is reversible by reverting this revision.

THE PROPOSAL FILE RETAINS ITS ORIGINAL WORDING, DELIBERATELY. It still says "declared status" and still carries the three-source list. It is the record of what was PROPOSED; correcting it to match what was ratified would falsify the provenance. The divergence is recorded here instead. Do not repair the archived proposal.

COVERAGE RESIDUAL, recorded rather than hidden. The three new scenarios map to TODO in tests/heading-coverage.json because this repo requires scenario headings to map to integration-tier-or-above tests and no integration-tier exercise of this act exists. The behavior IS covered at beside tier (test_supervisor_liveness_starvation and tests/test_picker_stall_nudge_echo). Filed as overseer-6tfncs.3 and named in each TODO entry's work_item field, which is what makes them owned rather than orphaned under check-no-todo-registry. The spec.md heading maps to a real beside-tier test, which its tier permits.

SCOPE. This pass used --only-topic and disposed ONLY this proposal. derived-row-status-promotion.md, authored by a different live thread, remains PENDING and untouched. It governs the picker-stalled promotion vocabulary, which is the seam this text deliberately describes only from its own side.

## Resulting Changes

- constraints.md
- spec.md
- scenarios.md

## Ratification Review

ratification_review: auto-spawn
reviewer_model: fable
reviewer_identity: fable
separate_reviewer: True
read_only: True
reviewed_at: 2026-08-19T12:14:00Z
verdict: NO BLOCKERS
proposal_stem: acting-safety-third-keystroke-act
content_digest: 9ea406633a4ba5e5ed2a23ece56781ad280e13d0fdbdae019dc8b246df14723c
