---
topic: attention-ownership-superset
author: claude-fable-5
created_at: 2026-08-02T06:48:46Z
---

## Proposal: Attention ownership admits a composing superset surface without weakening the daemon's

### Target specification files

- SPECIFICATION/contracts.md

### Summary

contracts.md §"Attention surface" currently opens with an exclusive-ownership sentence — "The daemon owns 'what needs attention now'" — which a second, foreman-composed attention surface would contradict as written. This proposal narrows the sentence to what it actually protects (the daemon's mechanical session-liveness attention surface is authoritative, self-refreshing, and unchanged) while explicitly admitting a consuming operator surface that composes a SUPERSET from the snapshot, and adds a foreman-heartbeat staleness member to the daemon's own report-only membership.

### Motivation

Maintainer decision 3 (plan/foreman/research/brainstorm.md §3): keep the daemon's logic UNCHANGED, including its NEEDS YOU reporting, with the daemon's surface a SUBSET of the foreman's attention-managing surface. External review finding O7 identified that this decision requires amending the exclusive-ownership clause rather than merely leaving the daemon untouched; finding O6 fixed the inversion that the deterministic process watches the LLM — the daemon, which re-renders token-free every tick, is the correct home for "the foreman itself has gone stale".

### Proposed Changes

In contracts.md §"Attention surface": (1) Reword the opening sentence to state that the daemon owns and renders the MECHANICAL attention surface — the session-liveness membership enumerated in that section — and that this surface MUST remain authoritative, self-refreshing, and complete on its own terms. (2) Add: a consuming operator surface MAY compose a superset attention view from the status snapshot; such a consumer MUST NOT suppress, filter, re-rank, or replace the daemon's own rendering, and MUST NOT introduce any surface that requires the daemon's rendering to be ignored. The daemon's report-only members still authorize no act regardless of who consumes them. (3) Extend the membership enumeration with one new report-only member: a PRESENT-but-STALE foreman heartbeat (written under the watched repo's gitignored scratch) MUST be surfaced with coordinates, edge-triggered like every other member; an ABSENT heartbeat MUST NOT be attention — no foreman adopted means nothing is wrong, mirroring the unassigned-is-not-attention rule. This member is report-only and MUST NOT authorize any act.
