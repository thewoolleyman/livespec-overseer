---
proposal: any-tick-stranded-resume-self-heal-authorization.md
decision: accept
revised_at: 2026-08-19T05:52:25Z
author_human: thewoolleyman <chad@thewoolleyman.com>
author_llm: claude-opus-5
---

## Decision and Rationale

Accepted. The ratified letter had drifted from the daemon: spec.md's restarted-but-never-worked paragraph said the condition "MUST NOT authorize or suppress an independently qualified submission-only retry", while the daemon has authorized exactly that since `overseer-xkrwm3.5` shipped — `_supervisor_restart_attention.post_respawn_decision` records the round-scoped `resume_pending` on any acting tick where the track reads stranded, and `_supervisor_resume_retry.resume_retry` then re-sends the SUBMISSION only. The proposal asked for the letter to say what the daemon does, through the propose-change to revise pipeline rather than the auto-backfill that was rejected process-wise as PR #996. The letter now states that authorization in spec.md, records it beside the report-only membership in contracts.md, and pins it with a When/Then pair inside the existing stranded-resume scenario.

The accepted text is NARROWER than the proposal drafted it, and the narrowing is the substance of this decision. The proposal glossed the authorizing evidence as two legs — no context consumed, and a composer holding exactly the expected resume text. The shipped predicate `_supervisor_restart_attention._resume_stranded` has THREE: it also requires `not obs.busy`. Ratifying the two-leg form would have created a MUST the daemon does not honor, and the broader reading is also the wrong behavior, since it would oblige the daemon to keystroke into a pane that reads busy — a state reachable in practice, because a freshly respawned session can read busy for reasons unrelated to the resume, such as SessionStart hooks, without consuming context. All three files therefore enumerate three legs and say so explicitly. The structured-gate carve-out is stated for the same reason: `resume_retry` reports a gated pane as waiting on a human and never keystrokes it, and the ratified letter now says that rather than leaving it to be inferred.

Nothing here weakens the cardinal rule. The self-heal is submission-only and round-scoped, it never re-pastes, respawns, terminates a session, or writes a declaration, and a fresh session-written `ready` remains the sole restart authorization — restated in both spec.md and contracts.md. The 60-second-floor NEEDS YOU surfacing is unchanged and is explicitly independent of whether the self-heal has fired, so neither condition authorizes or suppresses the other.

## Resulting Changes

- spec.md
- scenarios.md
- contracts.md

## Ratification Review

ratification_review: auto-spawn
reviewer_model: fable
reviewer_identity: fable
separate_reviewer: True
read_only: True
reviewed_at: 2026-08-19T05:57:00Z
verdict: NO BLOCKERS
proposal_stem: any-tick-stranded-resume-self-heal-authorization
content_digest: 4d1aa5ede02efaec554e152d7cc0589dd49b0f2644a905ec68f0fff1e4fa1169

Four rounds of independent read-only Fable review ran against this pass, and the first three returned BLOCKERS. Round 1 blocked on this proposal specifically: the two-leg gloss described above, which it caught by re-deriving `_resume_stranded` from the code. The repair added the busy leg and the structured-gate carve-out across spec.md, contracts.md and scenarios.md. Rounds 2 and 3 blocked on the sibling proposal in this same pass (see `ready-identity-turnover-observability-revision.md`) and re-confirmed this proposal's repair against the code each time. Round 4 returned NO BLOCKERS on the exact bytes recorded by the digest above.

`reviewed_at` POSTDATES `revised_at`, and that is a real anomaly rather than a transcription slip. This pass's snapshot was cut and committed out of band, by a concurrent actor, without the revise CLI — which is why no `-revision.md` files were written at the time and why these records were reconstructed afterward, on the merged bytes, rather than emitted by the CLI. The round-4 reviewer was in flight when that happened; it verified by digest that the committed bytes were byte-identical to the candidate bytes it had been reviewing, and returned its NO BLOCKERS verdict against them. The evidence is therefore genuine and is about the bytes that landed, but it was not validated by the CLI's own timing rule, and no `revise_decision` journal event was appended for this pass. Recorded here so the gap is legible rather than silently absent.
