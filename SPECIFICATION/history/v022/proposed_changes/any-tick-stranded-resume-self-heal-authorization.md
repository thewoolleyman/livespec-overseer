---
topic: any-tick-stranded-resume-self-heal-authorization
author: claude-sonnet-5
created_at: 2026-08-16T17:32:46Z
---

## Proposal: Any-tick stranded-resume self-heal authorization

### Target specification files

- SPECIFICATION/spec.md
- SPECIFICATION/scenarios.md
- SPECIFICATION/contracts.md

### Summary

Ratify that the exact-expected-composer-text evidence already used to surface the restarted-but-never-worked NEEDS YOU attention member also independently authorizes a submission-only self-heal retry (record resume_pending, re-send Enter only) on any acting tick, not only the report-only surfacing.

### Motivation

Work-item overseer-xkrwm3.5 (epic overseer-xkrwm3, resume-submit-integrity, repo livespec-overseer) implemented an any-tick self-heal in overseer/_supervisor_restart_attention.py: when a fresh post-respawn pane's composer holds EXACTLY the track's expected resume text and no resume_pending flag is recorded, the daemon now records resume_pending and re-sends Enter only on the next acting tick -- never a re-paste, never a respawn, never a session termination, never a declaration write. This shipped as an implementation-only change (PR #998, livespec-overseer) because the work-item's own scope note classified it as implementation-only per an earlier spec sweep. A separate factory-dispatched attempt to also rewrite the ratified spec text for this behavior (PR #996) was rejected process-wise -- it bypassed the propose-change -> independent review -> revise pipeline via an auto-backfill mechanism, not because its content was judged wrong. The current spec.md text for this condition ('This condition MUST NOT authorize or suppress an independently qualified submission-only retry...') therefore no longer accurately describes the shipped daemon behavior, which now DOES authorize a submission-only retry from this same evidence. This proposal exists so the maintainer can review and, if agreed, ratify the letter to match the implementation through the proper pipeline, rather than leaving the gap silently unresolved.

### Proposed Changes

In `SPECIFICATION/spec.md`, in the paragraph describing the restarted-but-never-worked NEEDS YOU member (currently ending '...This condition MUST NOT authorize or suppress an independently qualified submission-only retry, MUST NOT write a declaration, and MUST NOT authorize a respawn; the fresh session-written `ready` declaration remains the sole restart authorization.'), amend the letter so that: on any acting tick where the daemon observes that exact expected-composer-text evidence, the daemon MUST re-arm the round-scoped `resume_pending` retry and re-send Enter only; it MUST NOT re-paste the resume text, MUST NOT respawn the session, MUST NOT terminate the session, and MUST NOT treat any non-exact composer text as retry authority. The 60-second-floor NEEDS YOU surfacing behavior described in the rest of the paragraph is unchanged and continues to apply independently of whether the self-heal retry has fired.

In `SPECIFICATION/scenarios.md`, extend the 'A restarted session that never begins work is surfaced without a second kill' scenario (or add a sibling scenario) with a When/Then pair covering: When the daemon observes the track on a later acting tick with no `resume_pending` flag recorded and the composer still holding exactly the expected resume text, Then it MUST record `resume_pending` and re-send Enter only, and it MUST NOT re-paste, respawn, terminate the session, or write a declaration.

In `SPECIFICATION/contracts.md`, in the NEEDS YOU membership clause for this condition, add that the same exact-composer-match evidence independently authorizes the submission-only self-heal described above, alongside (not replacing) the existing report-only NEEDS YOU membership.

Reference wording (as originally drafted by the implementing agent, preserved for review convenience -- not to be merged verbatim without independent review) is available in the closed PR #996, branch `feat/overseer-xkrwm3.5`, commit `f5c388a733` in the `livespec-overseer` repository, and in ledger comments on work-item `overseer-xkrwm3.5`.
