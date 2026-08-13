---
topic: make-supervisors-reliable
author: codex
created_at: 2026-08-13T22:03:24Z
spec_commitments:
  impl_followups:
    - id_hint: supervisor-completion-gate-realization
      description: |
        Implement the livespec-overseer supervise-plan realization and tests for the accepted structured supervisor-state, completion-gate, wake-producer, external-reentry, and additive-message contract.
---

## Proposal: Supervisors require a verifiable completion gate and independent re-entry

### Target specification files

- SPECIFICATION/spec.md
- SPECIFICATION/constraints.md
- SPECIFICATION/scenarios.md

### Summary

Make an attended supervisor's ability to end a turn conditional on structured, fail-closed state and an independently verified wake producer, rather than relying on charter prose that an agent can mechanically ignore.

### Motivation

The supervise-plan failure showed that a charter saying 'never end a turn without an armed re-entry' is advisory when no functioning Stop gate evaluates the supervisor's obligation marker. The existing daemon must retain its non-semantic boundary: it may not infer completion from pane or final-response text.

### Proposed Changes

Add a supervisor-pair completion contract: the supervisor's distinct `tmp/overseer/<topic>-supervisor/.supervisor-state` marker is structured state that records `supervision_active`, the objective, open obligations, completion disposition, and a wake-producer descriptor. While `supervision_active` is true, a Driver-owned completion/Stop gate MUST fail closed if the marker is absent, malformed, stale, or has any open obligation. It MAY permit completion only after an explicit structured plan-complete disposition, or exactly one structured maintainer-blocking disposition. It MUST NOT derive either disposition by parsing assistant final-response text or pane text. A completion that leaves supervision active MUST also prove an independently running wake source before it can pass: the producer descriptor must be verified against a live PID plus expected command/identity for a pane watcher or overseer daemon, or against an authoritative registered producer for a forge/CI or ledger watcher; a prose claim is insufficient. The producer's wake action MUST cold-open the supervisor from this marker and re-query the ledger/forge state; the ended turn is never itself the wake mechanism. Define that user messages are additive while `supervision_active` is true; only literal `stop supervising <topic>` or `replace supervision objective` may clear or replace the objective. Preserve the existing daemon boundary by stating that this is a Driver-owned turn-completion control, not daemon semantic judgment. Add scenarios for rejection on an open obligation, malformed marker, stale/wrong producer, and prose-only wake claim; acceptance for an explicit complete disposition and for one genuine maintainer block; external re-entry reading fresh state; and additive user messages versus the two explicit override forms. Add the corresponding contributor-observable constraint that unknown completion or producer evidence resolves to refusal.
