# Release automation gap — terminal SUPERVISOR handoff

## Status: COMPLETE AND ARCHIVED

This is the supervisor-role counterpart to the terminal `handoff.md` beside it.
The thread has no pending supervision, verification, ledger, or archive work.
Do not reopen, redispatch, or resume supervision from this file.

The authoritative completed record is
`plan/archive/release-automation-gap/supervisor-handoff.md` — the full charter as
it stood at archive — together with
`plan/archive/release-automation-gap/research/what-the-fix-taught.md`.

All child items and epic `overseer-oijk3d` are closed. `Release tag` reached
conclusion `success` on `0.17.1` and again on `0.17.2`. The acting overseer
daemon was never stopped or restarted.

If a fresh supervisor session receives this file, its only action is to confirm
the archive exists on a freshly fetched `origin/master`. There is no supervision
to resume.

## Why this file exists at the PRE-ARCHIVE path, deliberately

**It is a tombstone, not a charter**, and it is load-bearing for two distinct
daemon behaviours. Both were measured live on this track on 2026-08-03, after the
archive merged as PR #578.

The daemon computes a supervisor track's task path rather than storing it —
`_supervisor_prompts.py:supervisor_handoff_path` returns
`<repo>/plan/<topic>/supervisor-handoff.md`. Archiving moves the real file to
`plan/archive/<topic>/`, and **nothing updates that computation**. So after an
archive the computed path names a file that does not exist. Two things then go
wrong, and the second is worse than the first:

1. **The idle nudge points at nothing.** `idle_nudge_message` interpolates that
   path, so an idle-but-not-finished supervisor is told *"your task is in
   `<path>`"* for a path that was archived out from under it. Observed on this
   track at 2026-08-03T06:02Z.

2. **RESTART IS REFUSED.** `_supervisor_restart.py` existence-tests the same
   path and, when it is missing, alerts
   `supervisor ready declared but supervisor-handoff.md is missing; not
   restarting` with condition `supervisor-handoff-missing`, then returns without
   restarting. So a supervisor session on an archived thread that declares
   `ready` — which is exactly what a correct wind-down does — cannot be
   restarted, and the operator gets an alert describing a missing file rather
   than a finished thread.

This tombstone satisfies the existence test and gives both paths something true
to read. It does **not** re-open the thread: the daemon is permitted only to ask
whether this file exists, never to open, read, hash, or depend on its content, so
its content is written for the human or agent who follows the nudge.

**The underlying defect is tracked as `overseer-y26`** — archiving a plan thread
leaves the overseer's stored or computed resume path pointing at the moved file.
This file is a per-thread mitigation, not the fix. The fix belongs in the daemon
(follow the move, or treat an archived thread as terminal), and until it lands
**every archived thread that had a supervisor session needs one of these.**

Note the asymmetry that made this easy to miss: the worker-side tombstone
(`handoff.md`, PR #8f5b993) covers the WORKER track's stored resume line, and a
reader could reasonably assume it covered the thread. It does not — the
supervisor path is computed separately and needed its own.

## Deliberately not a charter

This file carries no `ledger_anchor` binding, no bindings table, and no
preconditions, because there is nothing left to supervise and a charter that
looks live invites resumption. The archived charter retains all of that.
