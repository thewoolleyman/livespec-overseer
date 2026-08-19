---
topic: ready-identity-turnover-observability
author: codex-gpt-5
created_at: 2026-08-14T01:11:37Z
---

## Proposal: Immediate identity-mismatch certification attention

### Target specification files

- SPECIFICATION/contracts.md
- SPECIFICATION/scenarios.md

### Summary

A live Codex successor can legitimately write a fresh ready declaration while the persisted supervision round still names its predecessor. The restart interlock must remain fail-closed, but the daemon must expose that deterministic identity mismatch immediately instead of presenting generic danger for the fifteen-minute generic uncertifiable-ready delay.

### Motivation

In the live fleet-ci-runner-pool-supervisor incident, the round was bound to codex:019ffccf-4f85-73a0-a83f-aa42a5face36 while the live pane was codex:019ffcf1-3669-78f2-9510-1fea362b3733. A ready marker written by the successor was correctly held, but it appeared only as generic danger, which made the system look like it had ignored ready and obscured the safe remediation.

### Proposed Changes

In contracts.md §The restart interlock, require that a standing `ready` whose live session identity differs from the round-open identity MUST become report-only attention in the same completed evaluation that observes the mismatch, without waiting for the generic uncertifiable-ready continuity floor. The row and edge-triggered alert MUST name the certification failure, the round-open identity, the live identity, and the remediation: the old declaration cannot authorize a restart and the successor must complete a newly delivered current-session round before declaring a fresh `ready`. It MUST NOT restart, void, paste into, or silently relabel the declaration as ordinary `danger`. In scenarios.md, add a Given/When/Then scenario pinning this successor-identity case, including immediate coordinates and both identities, zero respawns, and a later fresh current-session declaration as the only restart path.
