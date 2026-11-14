---
topic: live-seat-record-keyed-by-epic
author: claude-opus-5-5:herdr-overseer
created_at: 2026-11-14T02:07:17Z
---

## Proposal: The live-seat record is held in the plan's ledger under a key naming the epic id, not on the epic

### Target specification files

- SPECIFICATION/spec.md
- SPECIFICATION/constraints.md

### Summary

SPECIFICATION v106 says the topic's live-seat record "is held on the plan's ledger epic". This proposal moves only WHERE it lives: into the plan's ledger, under a key naming the plan's epic id, apart from the epic's own fields. It also amends the two write-boundary sentences to match. Its semantics are unchanged.

### Motivation

Implementing v106 (overseer-fnu5gl) measured that no field of the epic can hold the record safely. The beads CLI's --set-metadata is a client-side read-modify-write of the epic's whole metadata column, so every handoff, next-action or dispatch write that read the epic before a take writes it back without the record, silently erasing a held seat and admitting a second. The epic's claim CAS (bd update --claim) is no fix either: it works only on epics at status open, it rewrites plan lifecycle state, and the fleet's bd lifecycle guard rejects it as non-conformant. A row of its own in the ledger, keyed by the epic id, is touched by no epic writer, and the ledger takes or refuses it atomically. legacy-coordinator-agent accepted that encoding and asked for this narrow amendment.

### Proposed Changes

In SPECIFICATION/spec.md §"Supervision across machines", in the paragraph "**One live seat per plan topic.**", replace the sentence "It is held on the plan's ledger epic, the epic id the mapping store already records for the track, because that is the one record every machine's daemon can reach." with:

> It is held in the plan's ledger, under a key naming the plan's epic id (the epic id the mapping store already records for the track), because the ledger is the one store every machine's daemon can reach. It is held apart from the epic's own fields, so no write to the epic can alter or erase it.

In SPECIFICATION/spec.md, in the filesystem-boundaries sentence that begins "The overseer's daemon writes its runtime state to exactly three places", replace "and, for the live-seat record of §"Supervision across machines" only, the plan's ledger epic." with:

> and, for the live-seat record of §"Supervision across machines" only, the plan's ledger.

In SPECIFICATION/constraints.md §"Filesystem boundaries", replace "and, for the live-seat record of spec.md §"Supervision across machines" only, the plan's ledger epic." with:

> and, for the live-seat record of spec.md §"Supervision across machines" only, the plan's ledger.

In SPECIFICATION/spec.md, if the sentence "The one thing the daemon itself reads and writes on that epic is the topic's live-seat record of §"Supervision across machines", which is not a handoff entry and authorizes no restart on its own." is present (it is introduced by proposal session-start-respects-live-seat-record), replace it with:

> The daemon also reads and writes the topic's live-seat record of §"Supervision across machines", which is held under a key naming that epic id rather than on the epic itself, is not a handoff entry, and authorizes no restart on its own.

No other text changes. The record's contents, its atomic conditional write, its three write moments, its readers, its no-expiry rule and every hold, event and scenario of §"Supervision across machines" are unchanged. No heading changes, so no coverage row changes.
