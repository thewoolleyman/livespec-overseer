---
topic: restarted-never-worked-attention
author: codex-gpt-5
created_at: 2026-08-12T02:12:17Z
---

## Proposal: Surface a restarted session that never began work

### Target specification files

- SPECIFICATION/spec.md
- SPECIFICATION/contracts.md
- SPECIFICATION/scenarios.md

### Summary

Add a report-only, edge-triggered NEEDS YOU membership for a successfully restarted session whose exact expected resume text remains in the composer and whose fresh session has consumed no context after a short bounded floor. This closes the false-success gap even when the resume-pending retry flag was never armed, while preserving the rule that only a fresh ready declaration can authorize a respawn.

### Motivation

The restart submit path can falsely confirm an empty input box before a queued paste has rendered. The fresh session then remains alive with its resume text unsubmitted, consumes no context, and receives neither retry nor attention for an unbounded period. The daemon must make this state visible without treating detection as permission to kill, respawn, submit, or alter the session.

### Proposed Changes

Update SPECIFICATION/spec.md §"The restart" to require that, after a respawn succeeds, the daemon retain enough live observation to recognize a fresh session that has consumed no context and whose composer holds exactly the track's expected resume text. If those facts remain continuously observed for a bounded 60-second post-respawn floor, the daemon MUST surface the track as report-only NEEDS YOU attention, even when the ordinary resume_pending retry state is absent. The daemon MUST re-evaluate this condition on every supervision tick, MUST emit the attention edge only on entry, and MUST clear and re-arm it when the session begins work or the composer no longer exactly matches the expected resume text. An unknown or unreadable context signal MUST NOT satisfy the no-consumption predicate. This condition MUST NOT authorize or suppress an independently qualified submission-only retry, MUST NOT write a declaration, and MUST NOT authorize a respawn; the fresh session-written ready declaration remains the sole restart authorization.

Update SPECIFICATION/contracts.md §"Attention surface" to enumerate this as a distinct report-only mechanical member: a successfully restarted fresh session with no observed context consumption and an exact expected resume payload still in its composer continuously past the 60-second floor, including the case where resume_pending was not recorded. State that it carries normal coordinates, participates in the NEEDS YOU count and window badge, is edge-triggered, and authorizes no act. Preserve the existing rule that discovered-but-unassigned tracks are not attention.

Add a Gherkin scenario to SPECIFICATION/scenarios.md named "A restarted session that never begins work is surfaced without a second kill". Given a successful respawn, the exact expected resume text in the fresh composer, no observed context consumption, and no resume_pending flag, when the evidence remains continuous beyond the 60-second floor, then the track is in NEEDS YOU, the attention count badges the overseer window, and the daemon reports coordinates without respawning, submitting, writing state, or terminating the session. When the session begins work or the composer changes, the membership and badge clear and a later qualifying episode can edge-trigger again. The scenario MUST also state that an unassigned track never enters this membership. Ratification MUST co-edit ../tests/heading-coverage.json with the new scenario heading and its implementation-test reference.
