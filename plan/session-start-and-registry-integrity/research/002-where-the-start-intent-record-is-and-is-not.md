# 002 — Where the start-intent record is, and is not

Created 2026-08-26 by the `homelab-loop-hardening-overseer` session, read
against the working tree at `eba4e925`. Research note 001 recorded the matrix
08 baseline from the registry side. This note answers the matrix 07 half by
tracing the two start paths in `overseer/` from proposal to spawn, because the
matrix's claim — "no journal record, no error, no evidence it was attempted" —
is a claim about ORDERING, and ordering is not visible from a defect report.

## The measurement

**`foreman-act` journals exactly ONCE, and it journals AFTER the act.**

`foreman_act.act()` (`overseer/foreman_act.py`) validates, gathers,
re-validates, dispatches the action, and only then, at the tail of the
function, calls `seams.append_journal(...)` with `_journal_record(result=...)`.
There is no earlier append on any branch. The record's fields are exactly:

    {"at": <utc>, "stage": "foreman-act", "action_id": ..., "outcome": ...,
     "reason": ..., "mutated": ...}

written by `foreman_act_record.append_journal` to
`<repo>/tmp/fabro-dispatch-journal.jsonl`.

Three consequences follow directly, and together they are matrix 07:

1. **A start that dies takes its own record with it.** The only journal write
   happens after the action returns. If the `foreman-act` process does not
   survive the spawn — or the spawn wedges — nothing is ever appended. The
   absence in the journal is not a logging gap downstream of the event; the
   write was scheduled after the thing that failed.
2. **The record carries no invoker.** Matrix 07's fix text says "with invoker
   per section 06". Section 06 is an orchestrator-side obligation on the
   Dispatcher's journal; this journal is a SEPARATE record shape owned by this
   repository, written by this repository's own `append_journal`. Adopting the
   orchestrator's field does not reach it. The invoker obligation has to be
   discharged here, on this record.
3. **A non-zero spawn is refused but not recorded as an attempt.** In
   `foreman_work_item_sessions._act_start`, a non-zero exit returns
   `_refused(reason=f"command_exit_{code}")`; the post-hoc journal then records
   `outcome=refused`. That is a record — but only when the process lived to
   write it, and it still names no invoker.

## What ALREADY exists, and why it is not the fix

The `work_item_session_start` path is NOT bare. Before spawning,
`_act_start` writes `claim.json` into a per-work-item state directory and
appends a `{"event": "claim", ...}` record beside it, carrying `attempt`,
`session_name` and `work_item_id`. That is a genuine pre-spawn durable record,
and any design here must build on it rather than duplicate it.

It is nonetheless not what matrix 07 asks for, on three counts:

- It is **per-work-item repo state**, not the journal, so a reader asking "what
  did the foreman try" does not see it.
- It carries **no invoker** and no action id.
- On a failed spawn it is **never reconciled**. `_act_start` returns refused and
  leaves `claim.json` in place, so the claim reads as live work while nothing
  is running — the same phantom-claim shape this fleet already documents on the
  dispatch side, reproduced locally. The failure branch is annotated
  `# pragma: no cover`, so no test exercises it.

**And `plan_start` has no equivalent at all.** `plan_start` is one of
`_START_ACTIONS` in `foreman_act_dispatch.py` alongside
`qualifying_session_start` and `supervisor_pair_start`; that path's only
pre-spawn step is `_revalidate_start_tmux_occupancy`, which REFUSES on an
occupied session name and writes nothing when it passes. So the action named
first in matrix 07's own problem statement is the one with no pre-spawn record
whatsoever, while the action that does have one is `work_item_session_start`.
A fix scoped from the existing `claim.json` machinery alone would repair the
better-instrumented half and leave the reported half untouched.

## Why this is worth a note rather than a line in the scope event

Matrix 07 reads as one defect. It is three, in two different stores, across two
action families, and the strongest of them — a post-hoc-only journal — is
invisible to any test that asserts on the record's CONTENT rather than on when
it is written. A negative control for this must kill the process between the
spawn and the return, not merely assert that a field is present.

That is also the negative control the charter names: "a killed spawn leaves an
attempted-and-failed record". It is satisfiable only if the record exists
BEFORE the spawn, which is why the ordering measurement above is the load-
bearing one and not background colour.

## Requirement carriers this note implies

Recorded here as candidates for the scope event, not as ratified scope:

1. A start-intent record written BEFORE the spawn, for every action in
   `_START_ACTIONS` plus `work_item_session_start`, carrying action id, target,
   and invoker.
2. An outcome record reconciling that intent — including the failure paths that
   are currently `# pragma: no cover`.
3. Invoker identity on this repository's own `foreman-act` journal record shape.
4. Reconciliation of a stale `claim.json` left by a failed spawn, so a dead
   attempt stops reading as live work.

Whether 4 belongs to this thread or to the registry half of matrix 08 is a cut
for the scope event to make; it is named here so it is not lost between them.
