---
topic: ready-activity-downgrade-contract
author: claude-fable-5
created_at: 2026-08-17T03:09:48Z
---

## Proposal: Ready activity downgrades visibly

### Target specification files

- SPECIFICATION/contracts.md
- SPECIFICATION/spec.md
- SPECIFICATION/scenarios.md

### Summary

Ratify the implemented post-ready activity behavior for work-item
`overseer-27ug3t`: when a session writes `ready` and then resumes activity, the
daemon rewrites the state file to `winding-down: auto @<epoch-seconds>` instead
of deleting it or leaving the stale `ready` declaration armed.

### Motivation

Deleting the declaration created a missing-file window in which a supervised
session could invent that a restart had completed. A diagnostic on-disk value
keeps the degradation visible to both the session and the operator, then lets
the ordinary `winding-down` acknowledgement path suppress wrap-ups briefly and
re-arm escalation after staleness.

### Proposed Changes

In `contracts.md`, replace the ready-side rule that said activity does not
alter `ready` with a combined activity-downgrade-and-expiry rule: resumed
activity MUST rewrite the state file to `winding-down: auto @<epoch-seconds>`;
that value is governed as a fresh `winding-down` acknowledgement; the round
remains open; and escalation re-arms once that acknowledgement becomes stale.
The existing maximum-age expiry rule remains, but a `ready` declaration is
eligible to certify only while it has neither been downgraded nor expired.

In `spec.md`, replace the paragraph saying `ready` remains armed through
intervening activity with prose describing the visible downgrade, readable state
file, ordinary fresh-acknowledgement behavior, open round, and later re-arming.
Preserve the separate expiry behavior for non-downgraded declarations.

In `scenarios.md`, replace the scenario assertions under the ready-resumes-work
case: the daemon rewrites the state file to `winding-down: auto
@<epoch-seconds>`, the downgraded value remains readable, the round record and
already-notified bands are unaffected, and escalation re-arms after the fresh
acknowledgement becomes stale.
