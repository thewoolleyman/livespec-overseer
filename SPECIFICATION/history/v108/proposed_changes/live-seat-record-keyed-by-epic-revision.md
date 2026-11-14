---
proposal: live-seat-record-keyed-by-epic.md
decision: accept
revised_at: 2026-11-14T05:55:38Z
author_human: Chad Woolley <thewoolleyman@gmail.com>
author_llm: claude-opus-5-5:herdr-overseer
---

## Decision and Rationale

Accepted unmodified. Implementing v106 (overseer-fnu5gl) measured that no field of the plan epic can hold the live-seat record safely. The beads CLI's --set-metadata is a client-side read-modify-write of the epic's whole metadata column, so any epic writer that read before a take writes the record away and admits a second seat. The epic claim CAS works only at status open, rewrites lifecycle state, and is refused by the fleet's bd lifecycle guard. Holding the record in the plan's ledger under a key naming the epic id, apart from the epic's own fields, keeps every v106 guarantee: the record is still reachable by every machine's daemon and is still taken or refused atomically. The proposal changes only where the record lives, plus the two write-boundary sentences and the v107 OPAQUE LOCATOR follow-on sentence that named its location. Its contents, conditional write, write moments, readers, no-expiry rule, holds, events and scenarios are untouched, and no heading changes. legacy-coordinator-agent accepted the encoding and asked for this narrow amendment.

## Resulting Changes

- constraints.md
- spec.md

## Ratification Review

ratification_review: auto-spawn
reviewer_model: sonnet
reviewer_identity: sonnet
separate_reviewer: True
read_only: True
reviewed_at: 2026-11-14T05:55:13Z
verdict: NO BLOCKERS
proposal_stem: live-seat-record-keyed-by-epic
content_digest: b28f7d4cb4e74fd1209c990fdde74c383e9f8f0c77b2a2113263c74458fbd202
