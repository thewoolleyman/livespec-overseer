---
proposal: attention-ownership-superset.md
decision: modify
revised_at: 2026-08-03T04:22:39Z
author_human: thewoolleyman <chad@thewoolleyman.com>
author_llm: claude-opus-5
---

## Decision and Rationale

The mechanical daemon attention surface must remain authoritative and complete while a consuming operator surface may compose a superset from the ratified snapshot. Stale-foreman attention belongs in the daemon, but the filed heartbeat schema omitted the ledger-required generation field.

## Modifications

Applied the filed attention ownership, superset-consumer, stale/absent heartbeat, handover, and scenario changes, replacing the heartbeat-field sentence with the assessment's exact wording requiring `written_at`, `pid`, monotonically increasing `tick_generation`, and `tick_interval_seconds`, with staleness after twice the declared interval subject to the thirty-minute floor.

## Resulting Changes

- contracts.md
- spec.md
- scenarios.md
- ../tests/heading-coverage.json
