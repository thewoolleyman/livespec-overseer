# unattended-stall-hardening — initial research note

## Problem (measured 2026-08-16/17)

Three stall classes survived every existing supervision layer in this repo, each
costing hours before a human noticed:

1. PICKER STALLS IN UNATTENDED SESSIONS. resume-submit-integrity-supervisor sat
   ~3 hours on an interactive options picker asking permission to run
   /livespec:revise — an action its own charter authorizes ("if the SUPERVISOR
   can perform the unblock, PERFORM IT"). The daemon classified the pane
   blocked:human but nothing measured HOW LONG, so the attention surface showed
   a state, not an emergency. The same excess-deference shape appeared in the
   worker (revise-permission picker) and in the foreman session itself
   (premature escalation instead of panel).

2. UNMONITORED SUPERVISOR HALVES. Supervisor sessions often have no
   mapping-store row, so the daemon snapshot never carries a row for them:
   blocked/human-wait/low-context detection is structurally blind for exactly
   the sessions that answer other sessions' questions. A hand-armed monitor
   watching snapshot rows for a row-less session alerts on nothing forever.

3. SILENCE READ AS HEALTH. .supervisor-state markers carry no freshness;
   foreman-heartbeat-stale exists in the snapshot but is not promoted to the
   operator attention surface. Every watcher that fails silent looks identical
   to a healthy quiet system.

## Mechanical fixes (the plan's scope)

A. Daemon: add picker_open (bool) and stall_seconds (age since the pane last
   changed while blocked:human) to every snapshot row; emit an attention-surface
   row when stall_seconds crosses a threshold; drive the existing nudge
   machinery off that condition for charter-authorized unblocks (re-teach the
   charter clause, never answer content).
B. Daemon: auto-register supervision rows for <topic>-supervisor tmux sessions
   (pair discovery or supervise-plan registering the row at pair start) so both
   halves of every pair are snapshot-tracked with no hand-armed side channels.
C. Supervisor-state freshness: .supervisor-state gains written_at refreshed on
   every supervisor wake; the daemon flags supervisor_state_stale beyond a
   bound as a distress row.
D. Charter gate: extend the prompt-realization detector family so an
   unattended-track charter must carry the perform-the-unblock clause, and an
   interactive picker offered to no human is a detectable defect.
E. Promote foreman-heartbeat-stale to the operator attention surface (NEEDS YOU
   block) so a dead foreman loop is a visible row.

## Evidence anchors

- The 3h supervisor picker stall: spec-side-autonomy-supervisor's analysis,
  2026-08-17; picker text 'How do you want to ratify?'.
- Blind monitor: the foreman session's own b10ijc8p0 monitor (snapshot-row
  distress logic against a row-less topic).
- Related filed items: overseer-xshoch (foreman LLM-tick starvation),
  overseer-xogp6d (janitor snapshot clobber), overseer-za32 (ScheduleWakeup
  background-task reaping), overseer-2ifwfq (mapping-row loss incident).
- Deference-failure precedents: foreman session self-diagnosis 2026-08-16;
  resume-submit-integrity-supervisor Corrections entry C1.
