# overseerd-auto-restart — brainstorm

Commissioned by the livespec-overseer-foreman operator on a direct maintainer
directive (verbatim): "make a new plan (with plan skill), which brainstorms
and implements overseerd based auto-restarting for foreman sessions as well
as supervisor/worker sessions ... auto-revise, and auto-work the track ... no
input should be needed from me on anything." This worker session holds
standing AUTO-REVISE and NO-MAINTAINER-QUESTIONS authorizations for this
track (recorded on the plan epic, not re-litigated here).

## Where auto-restart stands today

`overseerd` already auto-restarts a **tracked plan session** (a Claude or
Codex pane mapped to a `plan/<topic>/` directory) through the cardinal-rule
machinery in `overseer/marker-protocol.md`: the daemon injects an escalating
wrap-up at a context threshold, the session ACKs (`winding-down`) and
eventually declares itself `ready` in `<repo>/tmp/overseer/<topic>/.overseer-state`,
and ONLY that fresh, certified, session-written `ready` authorizes
`Supervisor._do_restart` (`respawn-pane -k` + runtime-appropriate relaunch +
resume-prompt paste). This is invariant 7 in `overseer/AGENTS.md` and must
never be weakened: no timer, no idleness heuristic, no daemon-side judgment
ever substitutes for the session's own declaration.

**What is NOT covered by that machinery today:**

1. **Foreman sessions** (`livespec-overseer-foreman`, one per watched repo).
   These are NOT tracked plan sessions — they have no `plan/<topic>/`
   directory of their own (a foreman supervises OTHER repos' plan tracks; it
   is not itself a plan). `overseer/foreman_runtime.py` gives a foreman a
   `ForemanRuntime.step()` loop with its own heartbeat
   (`tmp/overseer/foreman/heartbeat.json`, read/written by
   `_supervisor_foreman.py`) and a bounded `hard_tick_budget` /
   `converged_ticks` exit condition — so a foreman is EXPECTED to exit
   periodically (context exhaustion, convergence, or a hard tick ceiling) —
   but nothing today RESTARTS it. `_supervisor_foreman.py` currently only
   ever raises `foreman-heartbeat-stale` as a non-blocking attention alert
   (`ATTENTION_STATUSES`/`Supervisor.alert`), which tells a human "the
   foreman's heartbeat lapsed, go look" — it never respawns the pane. Today
   a foreman rotates by a HUMAN- or foreman-authored handoff file under
   `tmp/overseer/foreman/` (`foreman-session-handoff.md` in this repo) that
   the next hand-launched foreman session reads. That is a manual step, and
   it is exactly the gap this track closes.

2. **Supervisor-half sessions with NO recorded plan `epic`.** The
   marker-protocol interlock explicitly refuses to respawn a track whose
   mapping row carries no `epic` (`ready` is preserved, the track is
   surfaced instead) — by design, since the fresh session would have nothing
   to resume. Any session shaped like this (a scratch/investigation session,
   a session whose plan was archived out from under it) is a standing gap in
   auto-restart coverage, structurally distinct from the foreman gap.

3. **Supervisor pair members.** `overseer/marker-protocol.md` documents
   `.supervisor-state`, a freshness marker DISTINCT from `.overseer-state`
   that a supervisor-half session refreshes on every wake; a stale one is
   reported as `supervisor-state-stale`, again non-blocking-alert only, never
   a restart. Whether a supervisor-pair member should get the SAME
   `.overseer-state`-driven restart as an ordinary tracked session (it likely
   already can, if it is itself mapped to a `plan/<topic>/`) or needs its own
   analogous mechanism is a design question for this track.

4. Any other gap the `restart-assurance` line of work (epic `overseer-xkrwm3`,
   ledger item `overseer-mgg`, the resume-submit confirm race — fixed and
   live-verified for BOTH runtimes as of 2026-08-17) left unaddressed. That
   epic hardened the RESTART MECHANICS (submit confirmation, resume_pending
   retries) for tracks that are ALREADY eligible for auto-restart; it did not
   extend eligibility to foreman or epic-less sessions.

## Design direction (to be refined during design phase)

The cardinal rule is repo-wide dogma and applies identically here: whatever
mechanism restarts a foreman session, it must be triggered SOLELY by that
foreman session's own fresh, out-of-band declaration — never inferred from
heartbeat staleness, tick count, or idleness. Heartbeat staleness / hard-tick
exit remain useful as the SUGGESTION to wind down (the daemon-injected
wrap-up analogue), not as the restart trigger itself.

Leading hypothesis: extend the EXISTING `.overseer-state` protocol to a
foreman session by giving it its own per-repo track identity in the daemon's
discovery model (today discovery is keyed on `plan/*/` directories only —
invariant 4 in AGENTS.md — so a foreman, having no plan dir, is invisible to
discovery). Two shapes to weigh:

- (a) Treat each watched repo's foreman as a synthetic "track" with a fixed
  topic name (e.g. `foreman`), discovered by the presence of
  `tmp/overseer/foreman/` rather than `plan/<topic>/`, reusing
  `.overseer-state` under that directory verbatim, and reusing
  `_do_restart`'s Claude arm (a foreman is always Claude, never Codex, per
  its own runtime) with a resume line that points at the foreman's own
  resume surface (`foreman-session-handoff.md` or a ledger-held equivalent)
  instead of a plan epic.
- (b) A parallel, foreman-specific evaluate()/restart branch that shares the
  restart MECHANICS (`respawn-pane -k`, launch command, submit-verify) but
  keeps discovery and state-file plumbing separate from plan-track code, to
  avoid overloading `plan/*/`-shaped assumptions (e.g. `resume plan epic
  <epic> in repository <repo>` literally does not apply to a foreman).

(b) is likely safer given invariant 1 ("the overseer NEVER touches
`plan/`") and invariant 4 (discovery model) — a foreman track is a
genuinely different SHAPE of thing from a plan track (repo-scoped, not
plan-scoped; heartbeat-driven convergence instead of context-threshold
wrap-up), so forcing it through the plan-shaped code path risks exactly the
kind of "reshape this into daemon-side judgment" regression AGENTS.md warns
against. Final call belongs to the design step; record the decision and
reasoning on the plan epic (AUTO-REVISE authorization).

## Non-goals / explicit deferrals to weigh at scope-event time

- Weakening the cardinal rule in ANY way for ANY session shape — never in
  scope, not even for foreman sessions that "should" be safe to force-restart
  because they are merely observational. Off the table categorically.
- Restarting a session with NO recorded resume surface at all (neither a plan
  epic nor a foreman handoff/heartbeat identity) — such a session should
  continue to be surfaced to a human, not guessed at.
- Codex-runtime foreman sessions — foreman today is Claude-only
  (`foreman_runtime.py` has no codex arm); extending Codex support to foreman
  is out of scope unless research shows it already exists.

## Grounding read so far

- `overseer/marker-protocol.md` — full cardinal-rule contract (read in full).
- `overseer/AGENTS.md` (nested `.claude/CLAUDE.md`) — architecture invariants,
  the evaluate() cascade, restart mechanics, the 26-module private-collaborator
  surface (enumerate from the tree, not from any doc list).
- `overseer/_supervisor_foreman.py` — foreman heartbeat read/lapse/alert;
  currently ALERT-ONLY, never a restart trigger.
- `overseer/foreman_runtime.py` — `ForemanRuntime.step()`: heartbeat write,
  hard-tick-budget / converged exit reasons, no restart of its own.
- Ledger: `overseer-mgg` (resume-submit confirm race — CLOSED via live
  verification on both runtimes 2026-08-17), epic `overseer-xkrwm3`
  (resume-submit-integrity), epic `overseer-z5fo4y` (the foreman plan that
  built the heartbeat/attention surfaces this track extends),
  `overseer-cid32m` (supervision opt-out valve, pending — worth checking for
  interaction: an opted-out track must never be swept into foreman
  auto-restart either).

## Next steps

1. Read `overseer/_supervisor_evaluate.py`, `_supervisor_restart.py`,
   `_supervisor_discovery.py`, `_supervisor_attention.py` in full to nail the
   exact seams for a foreman-restart branch.
2. Check `overseer-cid32m` (opt-out valve) for design interaction.
3. Record a scope event (requirements + explicit deferrals) before filing any
   implementation children.
4. File implementation children on this plan's epic; prefer factory dispatch
   for dispatch-safe pieces.
