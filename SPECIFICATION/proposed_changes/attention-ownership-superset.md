---
topic: attention-ownership-superset
author: claude-fable-5
created_at: 2026-08-02T06:48:46Z
---

## Proposal: Attention ownership admits a composing superset surface without weakening the daemon's

### Target specification files

- SPECIFICATION/contracts.md
- SPECIFICATION/spec.md
- SPECIFICATION/scenarios.md

### Summary

contracts.md §"Attention surface" currently opens with an exclusive-ownership sentence — "The daemon owns 'what needs attention now'" — which a second, foreman-composed attention surface would contradict as written. This proposal narrows the sentence to what it actually protects (the daemon's mechanical session-liveness attention surface is authoritative, self-refreshing, and unchanged) while explicitly admitting a consuming operator surface that composes a SUPERSET from the status snapshot. It also ratifies the foreman heartbeat artifact (path, cadence, staleness bound) and adds a stale-heartbeat member to the daemon's report-only membership, with scenarios.

### Motivation

Maintainer decision 3 (plan/foreman/research/brainstorm.md §3): keep the daemon's logic UNCHANGED, including its NEEDS YOU reporting, with the daemon's surface a SUBSET of the foreman's attention-managing surface. External review finding O7 identified that this decision requires amending the exclusive-ownership clause rather than merely leaving the daemon untouched; finding O6 fixed the inversion that the deterministic process watches the LLM — the daemon, which re-renders token-free every tick, is the correct home for "the foreman itself has gone stale".

### Proposed Changes

EDIT 1 — contracts.md §"Attention surface", the opening sentence: reword to state that the daemon owns and renders the MECHANICAL attention surface — the session-liveness membership enumerated in that section — and that this surface MUST remain authoritative, self-refreshing, and complete on its own terms.

EDIT 2 — contracts.md, same section: a consuming operator surface MAY compose a superset attention view from the status snapshot (ratified by the status-snapshot-store proposal); such a consumer MUST NOT suppress, filter, re-rank, or replace the daemon's own rendering, and MUST NOT introduce any surface that requires the daemon's rendering to be ignored. The daemon's report-only members still authorize no act regardless of who consumes them.

EDIT 3 — contracts.md, same section, the heartbeat contract (ratified here so the new attention member consumes a defined artifact): a foreman MUST write a heartbeat file at `<repo>/tmp/overseer/foreman/heartbeat.json` on every loop tick, carrying its written-at timestamp, its pid, and its own declared tick interval in seconds. The heartbeat is PRESENT-but-STALE when its age exceeds twice its self-declared interval (with a floor of thirty minutes, so a short declared interval cannot make healthy jitter read as staleness).

EDIT 4 — contracts.md, the membership enumeration, one new report-only member: a PRESENT-but-STALE heartbeat MUST be surfaced with coordinates, edge-triggered like every other member. An ABSENT heartbeat MUST NOT be attention — no foreman adopted means nothing is wrong, mirroring the unassigned-is-not-attention rule. This member is report-only and MUST NOT authorize any act.

EDIT 5 — spec.md §"Notify, never block": the sentence motivating alert self-sufficiency ("that relay is the operator's only handover") narrows to "the daemon's only handover", since an admitted superset surface gives the operator a second one; the self-sufficiency requirement itself is unchanged.

EDIT 6 — scenarios.md, two new scenarios: (a) Given a heartbeat whose age exceeds twice its declared interval, When the daemon ticks, Then the attention surface names the stale foreman with coordinates, once per episode (edge-triggered); (b) Given a watched repository with no heartbeat file at all, When the daemon ticks, Then no foreman-related attention member is rendered.

EDIT 7 — tests/heading-coverage.json (outside the spec target; the atomic behavior-coverage co-edit): link the new clauses to the two scenarios.

Composition: depends on status-snapshot-store (the snapshot the superset consumer reads) and on unattended-reader-carve-out (which admits the `tmp/overseer/foreman/` scratch home the heartbeat lives in); accept together.
