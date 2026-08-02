---
topic: status-snapshot-store
author: claude-fable-5
created_at: 2026-08-02T06:48:46Z
---

## Proposal: The status snapshot store — a fourth operator-home file, observation-only and failure-contained

### Target specification files

- SPECIFICATION/contracts.md
- SPECIFICATION/scenarios.md

### Summary

contracts.md §"Durable stores" grows from three operator-home files to four: a daemon-written status snapshot (~/.livespec-overseer-status.json) that serializes the daemon's per-tick view for machine consumers (the foreman), atomically, with a schema version, a daemon instance id, a completed-tick generation counter, per-row session-identity tokens, and session-authored note text elided at serialization. The snapshot is observation-only, its write failures are contained rather than fatal, and readers fail closed on an unknown schema. The governed field set is enumerated here, in the durable-store contract — not by reference to the ungoverned pane rendering.

### Motivation

The foreman plan thread (plan/foreman/, epic overseer-z5fo4y; maintainer decision 2 in plan/foreman/research/brainstorm.md §3) fixed a daemon-written JSON snapshot as the transport by which the foreman consumes the daemon's view. The daemon currently exposes no machine-readable state: its world-view is in-memory plus a terminal paint. External review findings C4, O4, O11, and O19 (plan/foreman/research/review-findings.md) pinned the failure-containment, identity-token, elision, and fail-closed-reader requirements this proposal ratifies. The "Three operator-home files" enumeration is deliberately closed, so the new store MUST be ratified here before any implementation lands (ledger slice overseer-z5fo4y.1 names this ratification as its precondition).

### Proposed Changes

EDIT 1 — contracts.md §"Durable stores", the enumeration heading: "Three operator-home files" becomes "Four operator-home files", and a new bullet ratifies the status snapshot (~/.livespec-overseer-status.json). The daemon MUST rewrite it atomically on each completed tick.

EDIT 2 — contracts.md, the same new bullet, the governed field set (enumerated here so the store's schema does not lean on the ungoverned pane rendering): top-level `schema_version` (integer), `daemon_instance_id`, `tick_generation` (monotonically increasing per completed tick), and `written_at`; per evaluated track, one row carrying `topic`, `repo`, `tmux`, `runtime`, `status`, `note` (elided), `ctx`, `progress_now`, `human_wait`, `round_open`, `acked`, and `session_identity` (a token derived from the live session join, sufficient for a consumer to detect that the session behind a row changed). Session-authored free text (the blocked-reason note) MUST be elided and length-bounded at serialization — the snapshot MUST NOT become an unelided surface for session-authored text.

EDIT 3 — contracts.md, same bullet, failure and authority posture: a snapshot write failure MUST be contained and edge-reported and MUST NOT terminate or degrade the supervision loop. The snapshot is OBSERVATION-ONLY: nothing in it authorizes any act, and no daemon behavior may read it back as an input. Consumers MUST treat an absent, unreadable, or unknown-or-newer `schema_version` snapshot as absent (fail-closed) and MUST NOT best-effort-parse it. Staleness is detectable from `tick_generation` plus file mtime; a stale snapshot proves only that no fresh snapshot exists — it does NOT prove the daemon is down.

EDIT 4 — scenarios.md, two new scenarios: (a) Given a daemon whose snapshot writer raises on every write, When ticks proceed, Then supervision continues, the failure is edge-reported once per episode, and no snapshot claims currency; (b) Given a consumer reading a snapshot whose `schema_version` is newer than it knows, When it loads the file, Then it treats the snapshot as absent and surfaces that it could not read it.

EDIT 5 — tests/heading-coverage.json (outside the spec target; named here as the atomic behavior-coverage co-edit): link the new clauses to the two scenarios.

Composition: this proposal is self-contained, but attention-ownership-superset and unattended-reader-carve-out reference the store it ratifies — accepting either of those without this one strands their references.
