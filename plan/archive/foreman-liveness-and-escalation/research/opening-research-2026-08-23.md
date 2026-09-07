# foreman-liveness-and-escalation — opening research

Thread opened 2026-08-23 by cutting it out of `plan/foreman-actuator-gather-and-roster`
(anchor `overseer-tdfe`). Ledger anchor `overseer-ll9d`.

## Why this thread exists

`overseer-tdfe` held **68 open children** at the moment of the cut, measured
2026-08-23T06:16Z from a 865-row export of the tenant — 43% of the 159 open rows in
the whole tenant, and 82 open rows counting its sub-epics' children. That is the
second junk drawer in three days: `plan/foreman-improvements` was cut up on
2026-08-22 for holding 38, and its successor reached 68.

The carrier is named for the foreman's **actuator, gather and roster** surfaces. This
cluster is about something else: whether a supervised loop is **alive**, and what the
machinery does when it is not. Different subject, different failure mode, different
evidence.

## What this thread holds

| item | what it is |
|---|---|
| `overseer-tdfe.5` | the heartbeat surface for a genuinely DEAD loop repeats identically forever — the escalate-or-decay leg never shipped |
| `overseer-tdfe.6` | an escalated foreman is never delivered a wrap-up round, so it can never obtain a round-backed `ready` |
| `overseer-lhp3mn` | the escalation branch preempts the ready path, so an escalated foreman cannot wind down without retracting its own unanswered maintainer items |
| `overseer-w2nwx5` | the idle-escalation ladder runs against contract-conforming sessions: hourly exhaustion, 241 log lines, unsolicited pane injection |
| `overseer-axql66` | an un-respawnable track is discovered only after its `ready` is armed, as 30s log spam rather than a NEEDS YOU condition |
| `overseer-94fs` | a stale background shell shields a track with no upper bound — a three-day measured instance |
| `overseer-5e5a` | nobody owns restarting a dead foreman loop: two records each cite the other as owner, and one of them is a disclaimer |
| `overseer-6bx5` (+1 child) | implement the RATIFIED foreman self-restart |

`overseer-tdfe.5` and `.6` are themselves successors to `overseer-6tfncs.12` and
`.13` — this cluster has already survived one plan archive without being worked.

## The deferral this thread discharges, and why that is not an absorption

`overseer-tdfe`'s scope event (2026-08-23T06:05Z) deferred foreman self-restart as
**D2**, naming `overseer-6bx5` / `overseer-6bx5.2` as owners and `overseer-5e5a` as
the design call gating them. The deferral existed so that tdfe would not *silently*
absorb the work — the failure `overseer-5e5a` itself documents, where
`overseer-lixhd3` D3 and `overseer-6tfncs.5` criterion 8 each disclaimed self-restart
while citing the other, so nobody owned it.

Moving those rows here changes **where the work is tracked**, not what it requires.
The design gate on `overseer-5e5a` is unchanged and is now a sibling in the same
thread, which is the whole point: the gating question and the gated work finally sit
under one archive gate that will refuse to close over either.

## Seams with siblings

- **`plan/supervision-safety-and-attention-truth`** owns whether a published row
  *correctly describes* a pane. This thread owns what happens *after* a loop is
  correctly judged dead or escalated. A defect in the judgement is theirs; a defect in
  the response is ours.
- **`plan/foreman-actuator-gather-and-roster`** keeps the actuator, gather and roster
  surfaces. Where escalation is *delivered* through `foreman-act`, the delivery
  mechanism is theirs and the escalation policy is ours.
- **`plan/foreman-panel-and-rulings`** owns convene and ruling machinery. An escalation
  that must convene a panel crosses this seam; the convene obligation is theirs.

## Explicit deferrals

- **D1 — peer-foreman federation** (doorbell/inbox spool) is NOT here. It moved to
  `plan/foreman-full-autonomy-option` as `overseer-l7c6`. Named so this thread does not
  quietly grow a communications subsystem.
- **D2 — the daemon's own restart policy.** `overseerd` restart discipline is governed
  by `AGENTS.md` and is not a plan child; this thread is about supervised *sessions*.

## A caveat on the cut mechanics, stated so it can be falsified

Membership was moved by **parent-child edge only** — no dependency edge was used, which
is the documented permanently-undispatchable trap. But the archive gate also matches
children **by id hierarchy** (`plan_child_ids_from_id_hierarchy`, read from the
plugin source, not inferred): any id starting with `overseer-tdfe.` remains a gate
child of `overseer-tdfe` no matter who its parent is. So `overseer-tdfe.5` and `.6`
are bound to **both** gates.

Expect that: a sweep of this thread will show two children that also block tdfe's
archive. That is not an omission and does not need repairing here. `overseer-tdfe.9`
owns the inconsistency. The genuine finding would be the opposite — a child of this
anchor that `overseer-tdfe` can archive over.
