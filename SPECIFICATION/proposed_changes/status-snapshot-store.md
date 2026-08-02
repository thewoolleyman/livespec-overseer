---
topic: status-snapshot-store
author: claude-fable-5
created_at: 2026-08-02T06:48:46Z
---

## Proposal: The status snapshot store — a fourth operator-home file, observation-only and failure-contained

### Target specification files

- SPECIFICATION/contracts.md
- SPECIFICATION/spec.md
- SPECIFICATION/scenarios.md

### Summary

contracts.md §"Durable stores" grows from three operator-home files to four: a daemon-written status snapshot (~/.livespec-overseer-status.json) that serializes the per-tick row view for machine consumers (the foreman), atomically, with a schema version, a daemon instance id, a completed-tick generation counter, per-row session-identity tokens, and session-authored note text elided at serialization. The snapshot is observation-only, its write failures are contained rather than fatal, and readers fail closed on an unknown schema.

### Motivation

The foreman plan thread (plan/foreman/, epic overseer-z5fo4y; maintainer decision 2 in plan/foreman/research/brainstorm.md §3) fixed a daemon-written JSON snapshot as the transport by which the foreman consumes the daemon's view. The daemon currently exposes no machine-readable state: its world-view is in-memory plus a terminal paint. External review findings C4, O4, O11, and O19 (plan/foreman/research/review-findings.md) pinned the failure-containment, identity-token, elision, and fail-closed-reader requirements this proposal ratifies. The "Three operator-home files" enumeration is deliberately closed, so the new store MUST be ratified here before any implementation lands (ledger slice overseer-z5fo4y.1 names this ratification as its precondition).

### Proposed Changes

In contracts.md §"Durable stores": retitle the enumeration from three operator-home files to four, and add a bullet for the status snapshot (~/.livespec-overseer-status.json). The daemon MUST rewrite it atomically on each completed tick with: a schema_version integer; the daemon instance id and a monotonically increasing completed-tick generation counter; the written-at timestamp; and one row per evaluated track carrying the row-view fields plus a session-identity token derived from the live session join. Session-authored free text (the blocked-reason note) MUST be elided and length-bounded at serialization — the snapshot MUST NOT become an unelided surface for session-authored text. A snapshot write failure MUST be contained and edge-reported and MUST NOT terminate or degrade the supervision loop. The snapshot is OBSERVATION-ONLY: nothing in it authorizes any act, and no daemon behavior may read it back as an input. Consumers MUST treat an absent, unreadable, or unknown-or-newer schema_version snapshot as absent (fail-closed) and MUST NOT best-effort-parse it; staleness is detectable from the generation counter plus file mtime, and a stale snapshot proves only that no fresh snapshot exists — it does NOT prove the daemon is down. In spec.md §"Non-interference with tracked work", the "exactly two places" sentence for overseer state widens to name this home-directory store alongside the existing ones. In scenarios.md, add two scenarios: (1) Given a daemon whose snapshot writer raises on every write, When ticks proceed, Then supervision continues, the failure is edge-reported once per episode, and no snapshot claims currency; (2) Given a consumer reading a snapshot with a schema_version newer than it knows, When it loads the file, Then it treats the snapshot as absent and surfaces that it could not read it. Co-edit tests/heading-coverage.json (outside the spec target, named here as the atomic co-edit) to link the new clauses to those scenarios.
