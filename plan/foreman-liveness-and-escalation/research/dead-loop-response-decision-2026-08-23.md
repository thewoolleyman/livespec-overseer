# The sanctioned response to a dead foreman loop — decision, 2026-08-23

Discharges `overseer-5e5a` criterion 1. The full text is on that item's ledger
comment of 2026-08-23T06:47Z; this note is the readable form for a resuming seat.

**Decision: (b) an operator-initiated restore, ordered behind `overseer-tdfe.5`.**
(c) an automatic daemon re-arm is deferred to `overseer-ll9d.1` and is **not** ruled
out. (a) doing nothing is **rejected**.

Recorded as *decided for objection*, not as a maintainer ratification: the option
chosen grants no new automatic authority, which is precisely why a seat may take it.
The option that would need ratification is the one deliberately not taken.

## The fact the question turns on, which was not in the item

**The loop's only clock is session-scoped, so a dead loop cannot revive itself by
construction.** `.claude-plugin/prose/foreman.md` arms the recurring tick by calling
`CronCreate` directly, and states it is "session-only by construction — this plugin's
`CronCreate` has no durable/cloud persistence". `foreman-runtime` is a one-shot
per-tick invocation; nothing outside the session holds a timer for it.

So "should a dead loop restart itself" has no mechanically available *yes* — the thing
that would perform the restart is the thing that died. Every sanctioned response must
come from **outside** the dead session, and the only two actors there are the daemon
and a human.

## The SESSION/LOOP distinction is real, and it does not license what it appears to

`overseer-5e5a` criterion 3 requires this be stated and ratified, never assumed in
code. Stated, from source:

| object | what it is | authority |
|---|---|---|
| foreman **SEAT** | a tracked session — `register_foreman_track` upserts a `registry.ForemanSeat` Track, run through `_supervisor_evaluate.evaluate` | the ordinary ready-gated state machine; cardinal rule applies |
| foreman **LOOP** | its own heartbeat and stop-state files; `_supervisor_foreman`'s docstring: "does not enter the session state machine and never authorizes a daemon act" | report-only |

Two objects, different authority, already in the code. **But the fact above removes
the payoff**: re-arming a loop means arming a session-scoped cron, which requires a
live session in the pane. There is no act that re-arms a dead loop without engaging a
session. The distinction is genuine, it opens no cardinal-rule-free path, and nothing
in this decision is built on it.

## The ratified self-restart does not cover this case

`overseer-6bx5`'s ratified trigger is *the daemon has not acted within N of the seat's
own **ready declaration*** — a live seat with a satisfied precondition, where
self-restart changes only **who** acts on it. A dead loop has no current-round ready
declaration; that is what makes it dead.

Recorded explicitly, because a reader who knows self-restart was ratified will
otherwise conclude `overseer-5e5a` is covered — which would be a third instance of the
exact misreading that item was filed to end.

## Why (a) is not honestly available today

Live control from the acting daemon's status snapshot written **2026-08-23T06:46:15Z**
at version 1.44.4 (matching the current release):

| repo | state | age |
|---|---|---|
| `livespec` | `died` | 1578m |
| `livespec-dev-tooling` | `died` | 1588m |
| `livespec-console-beads-fabro` | `died` | 2175m |
| `homelab` | `held` | 5879m — correctly **not** an unattended failure |

So the died/held/completed discrimination `overseer-6tfncs.5` shipped genuinely works.
What never shipped is that item's **criterion 5**, the escalate-or-decay leg, carried
here as `overseer-tdfe.5`: the surface for a dead loop repeats identically forever, and
a condition that cannot stop being true is one operators learn to skip.

**(a) is therefore not a policy failing on its merits — it is a policy whose input has
never worked.** Choosing it today would be choosing a response conditioned on a surface
that reaches nobody. That is also why (b) is *ordered behind* `overseer-tdfe.5` rather
than beside it.

## Why (b), and what it costs

- No automatic authority, so no ratification of the distinction above is needed and the
  cardinal rule cannot be weakened — it is a human performing an act a human may
  already perform.
- Mostly already exists: `foreman.md` documents `foreman-runtime --resume` as the manual
  path for a loop the maintainer stopped, and documents the sequence as `--resume` then
  re-arm the cron. Missing are (i) this being written down anywhere as the answer to a
  `state died` row, and (ii) the row naming it. The natural home for (ii) is
  `overseer-tdfe.5`'s note text, which is being changed anyway.
- It composes: if an automatic trigger is later ratified, the trigger is the only new
  thing, because the restore path it fires is this same one.

## The citation repair (criterion 2), and a finding about its size

Criterion 2 names **two** citations. There are **three** — found by grepping the claim
rather than trusting the count:

1. `overseer-lixhd3` deferral **D3** — ledger comment, append-only → corrected by an
   appended comment on that epic.
2. `overseer-lixhd3` deferral **D6** — same comment, same correction.
3. `plan/archive/foreman-picker-mutes-its-own-loop/research/picker-suppresses-scheduled-ticks.md`
   — a **file**, corrected in place in this same change, and the copy a reader is most
   likely to meet, since a research note is what a resuming session is told to read first.

The adjacent-items list in that same note says criterion 8 "explicitly excludes
self-restart". **That reading is correct and was deliberately left alone**, so nobody
"repairs" it later.
