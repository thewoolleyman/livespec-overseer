---
topic: derived-row-status-promotion
author: foreman-fixes-to-blocking-pickers
created_at: 2026-08-19T06:20:00Z
---

## Proposal: Govern the snapshot row's derived status, and the picker-stall promotion consumers key on

### Target specification files

- SPECIFICATION/contracts.md
- SPECIFICATION/scenarios.md

### Summary

The status snapshot's per-track row carries a `status` field that consumers
read and branch on. The field is governed; its VALUES are not, anywhere in the
tree. The daemon also PROMOTES that value — a human-waiting track sitting on an
open picker past a bounded stall stops reporting the human-blocked value and
reports a picker-stall value instead — and nothing ratified says so. A consumer
that reasonably keys on the human-blocked value silently loses the track at the
moment it most needs it. That has already happened once, as a P1.

### Motivation

Three facts, each verified against the tree on 2026-08-19.

FIRST, the values are ungoverned. `spec.md` governs the STATE FILE vocabulary
exactly — the three values a session may write are named — but the daemon's
DERIVED row status is a different vocabulary, and the literals it uses appear
ZERO times in `spec.md`, `contracts.md`, and `constraints.md`. The snapshot
contract in contracts.md §"Durable stores" names `status` among the row's
governed fields and stops there. So a consumer has a governed field whose
inhabitants are undefined.

SECOND, the daemon promotes the value rather than only setting it. A track
whose declared status is the human-blocked value, whose pane shows an open
structured picker, and whose capture has been unchanged past a bounded floor is
re-reported under a picker-stall value. The underlying condition has not
changed — the session is still waiting on the same human — but the wire value a
consumer sees has. Nothing in the ratified tree warns a consumer that the field
behaves this way.

THIRD, this is not hypothetical. Work-item `overseer-v7io` (P1, since fixed)
was exactly this defect: the actuator that delivers a human-gated answer into a
pane accepted only the human-blocked literal and refused everything else, so a
fully-satisfied, unanimous, evidence-carrying gated answer was refused for every
picker-stalled pane — the valve failed in precisely the state it exists for, and
the verdict had to be delivered by raw keystrokes instead. The fix keyed that
consumer on the governed `picker_open` field instead. But the fix was to ONE
consumer; the contract that would stop the next consumer making the same
inference is still absent.

There is a fourth, smaller motivation. v020's ratified membership paragraph
refers to "a picker-stall status" and to "the picker-stall surface" in order to
distinguish itself from them. Both terms currently resolve to nothing in the
tree. Governing the promotion gives those references a referent.

This proposal deliberately does NOT govern the daemon's full derived-status
vocabulary. Enumerating every value the daemon may report is a larger change
with no incident behind it, and an enumeration is the kind of list that rots
silently. What is governed here is the narrower, load-bearing property: that
the field is derived, that it may be promoted while the underlying condition
persists, and what a consumer may therefore NOT infer from its absence.

### Proposed Changes

In contracts.md §"Durable stores", in the status-snapshot bullet that already
enumerates the row's governed fields, state the derived-status contract.

The row's `status` is the daemon's own DERIVED classification of the track. It
MUST NOT be read as the session's state-file declaration, which is a separate
and separately governed vocabulary. The daemon MAY report a MORE SPECIFIC
derived status while the underlying condition persists: in particular, a track
that is waiting on a human AND whose pane shows an open structured picker MUST
be reported under a picker-stall status once its capture has been unchanged past
the bounded stall floor, rather than continuing to report the human-blocked
status.

Because of that promotion, a consumer MUST NOT infer from the ABSENCE of the
human-blocked status that the track is not waiting on a human. A consumer
testing whether a track is parked on a picker MUST use the row's `picker_open`
field, which exists precisely so that test does not depend on the status
vocabulary. A consumer that must act on a human-waiting track MUST treat the
human-blocked and picker-stall statuses alike for that purpose.

In scenarios.md, add a Given/When/Then pinning the promotion and the inference
it forbids: given a tracked session waiting on a human with an open picker,
when its capture has been unchanged past the bounded stall floor, then its row
reports a picker-stall status rather than the human-blocked status, and a
consumer keyed on the human-blocked status alone does not observe the track as
human-waiting, and a consumer keyed on `picker_open` does.
