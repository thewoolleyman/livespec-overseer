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

FIRST, the values were ungoverned when this was filed. **SUPERSEDED IN PART
BY v023**, ratified the same day: v023 put the `blocked:human` literal into the
tree and established that the derived row status is the daemon's own
classification. What survives is that the PUBLISHED row value and its
promotion remain ungoverned, which is what this proposal now addresses; the
paragraph below is preserved as the original finding. `spec.md` governs the STATE FILE vocabulary
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

THREE INDEPENDENT INCIDENTS NOW TRACE TO THIS ONE AMBIGUITY, which is the
strongest evidence that it needs governing rather than explaining. First,
overseer-v7io as a P1 above. Second, a near-miss caught in v023's own
ratification review, where a drafted episode-end clause read, on its plain
reading, as though the act re-armed every tick — because a reader checking the
PUBLISHED row would see the promoted status and conclude the episode had ended;
that clause was reworded before ratifying. Third, this proposal. An ambiguity
that has produced a shipped P1, a caught-in-review defect, and a governance
change is not one a careful reader will reliably navigate unaided.

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

**NARROWED 2026-08-19 after SPECIFICATION v023 ratified.** v023 §"The
stalled-picker charter reminder" now states that the daemon's derived row
status is "the daemon's own classification, NOT one of the three values a
session may write", and puts the `blocked:human` literal into the ratified
tree. That is part of what this proposal originally drafted, so the
restatement is REDUCED TO A DEFERRING CROSS-REFERENCE rather than ratified
twice: contracts.md now cites the spec.md section by name and does not restate
its definition. A compressed anchoring clause remains deliberately, because a
snapshot consumer reading contracts.md would otherwise have no reason to visit
an act-predicate bullet in spec.md. v023 also deliberately
left the published-row promotion undefined — its episode-end clause says the
evaluated status "is not necessarily the status finally published on the
track's row" — and that seam is exactly what remains here.

In contracts.md §"Durable stores", in the status-snapshot bullet that already
enumerates the row's governed fields, govern the PUBLISHED status and the
promotion.

The row's `status` is the daemon's derived classification of the track, in the
sense already governed by spec.md §"The stalled-picker charter reminder"; it
is NOT the session's state-file declaration. The status the daemon EVALUATES
for a track is not necessarily the status it PUBLISHES on that track's row: a
track that is waiting on a human AND whose pane shows an open structured
picker MUST be published under a picker-stall status once its capture has been
unchanged past the bounded stall floor, while continuing to be evaluated as
`blocked:human`. The published promotion changes no underlying condition — the
session is waiting on the same human, for the same reason, before and after.

Because of that promotion, a consumer of the snapshot MUST NOT infer from the
ABSENCE of `blocked:human` on a row that the track is not waiting on a human. A
consumer testing whether a track is parked on a picker MUST use the row's
`picker_open` field, which exists precisely so that test does not depend on the
status vocabulary. A consumer that must act on a human-waiting track MUST treat
the published `blocked:human` and picker-stall statuses alike for that purpose.

State also that this promotion IS the "picker-stall surface" and the
"picker-stall status" that contracts.md's own NEEDS YOU membership paragraph
names when distinguishing itself from them. Both terms are v020's names for one
mechanism, and after v023 neither resolves anywhere by name — v023's section is
titled "The stalled-picker charter reminder" and uses neither phrase. Saying so
in the ratified text means a reader chasing either term lands on the governed
rule, rather than relying on the identification being obvious from context.

In scenarios.md, add a Given/When/Then pinning the promotion and the inference
it forbids: given a tracked session waiting on a human with an open picker,
when its capture has been unchanged past the bounded stall floor, then its row
publishes a picker-stall status rather than `blocked:human`, and a consumer
keyed on `blocked:human` alone does not observe the track as human-waiting,
and a consumer keyed on `picker_open` does.
