# foreman-improvements — brainstorm

Commissioned by the livespec-overseer-foreman operator on a direct maintainer
directive: file all actionable foreman-operation improvements, and any
follow-ups from the just-archived `overseerd-auto-restart` track, into this
plan — deduping against existing items rather than re-filing. This worker
session (renamed `foreman-improvements`, formerly `overseerd-auto-restart`)
holds the same standing authorizations as before: AUTO-REVISE, NO-MAINTAINER-
QUESTIONS (independent-reviewer subagent + ledger record instead), work to
completion with a mechanism always armed, factory dispatch preferred where
dispatch-safe.

## The post-mortem that motivates most of this

`tmp/overseer/foreman/foreman-session-handoff.md`'s "OPERATOR RULES ADDED
2026-08-18 AFTER A REAL FAILURE" section records a real incident: a
consensus-panel verdict was relayed to a worker without its evidence, the
worker's reasonable corroboration request was misread as an authority
challenge and escalated on a paraphrase, and the track stalled for hours
through repeated "STILL" alerts the operator explained away. Separately,
another track's ad-hoc pane-content-hash watch silently died across daemon
bounces and sat "armed" for ~9-12 hours watching a pane that no longer
existed (confirmed directly: `overseer-xkrwm3`'s 2026-08-18 "WATCH-STALENESS
CORRECTION" comment — pane `%48` died with the daemon process across at
least two bounces; the replacement watch now resolves by pane TITLE plus a
`daemon_instance_id` bounce-detection leg).

Five hardening rules were added to the foreman's own operating discipline as
an immediate response (evidence-carrying relays, verbatim-quote rule, the
directive-6 corroboration gate, the STILL-alert re-read rule, and
armed-mechanism validity). Rules recorded only in a handoff file bind nothing
durably — the next foreman that never reads this exact handoff repeats the
failure. That is the throughline for most of these items: turn ad-hoc
operator discipline and one-off session tooling into shipped, mechanical
surfaces.

## Candidate items, deduped against the existing ledger

1. **`overseer-ycdh`** (already filed, loose) — foreman-consensus panel
   evaluations for prose-question workers leave no worker-corroborable
   record; `blocked_session_answer` (the only path that journals a
   `foreman-consensus-act` record) refuses `pane_not_blocked_human`, so a
   prose-question panel's verdict is relayed with nothing mechanically
   producible to back it. This is the ANCHOR mechanical fix for the whole
   incident — ADOPT as a child, do not re-file.

2. **Durable stall + dead-watch detection** (new). Today's tooling is a
   session-scoped scratchpad script (`track-monitor.sh` per the process list
   seen live) doing ad-hoc pane-content hashing. Needs productizing into a
   shipped daemon surface: (a) "pane content unchanged N minutes while the
   row reads `working`" — the STILL-alert pattern that stalled for hours
   because a standing explanation was never re-examined; (b) "watch target no
   longer exists" — a daemon-bounce-invalidated pane-ID watch. Fold in
   `overseer-xkrwm3`'s two freshly-journaled lessons verbatim: key any watch
   on **re-resolvable identity** (pane TITLE, not bare pane ID) plus an
   explicit **`daemon_instance_id`** bounce-detection leg read from
   `~/.livespec-overseer-status.json`, never a bare pane ID alone. Must
   respect invariant 1/2 in `overseer/AGENTS.md` — the daemon owns watching
   mechanically; this is a NEW attention condition inside the existing
   `evaluate()`/attention machinery, not a second daemon or an operator-side
   polling loop.

3. **Promote the 5 operator rules into `prose/foreman.md`** (new). A rule
   that lives only in a handoff file is read once by the session that wrote
   it and never again. Needs a check for whether this is spec-bearing: the
   prose contract at `.claude-plugin/prose/foreman.md` may or may not be
   governed by `SPECIFICATION/` per the livespec doctrine that ratified
   operator-facing behavior routes through `/livespec:propose-change` (see
   `overseer-xkrwm3`'s own front-3 routing precedent — "presumptively
   contract-bearing... routes /livespec:propose-change -> independent Fable
   review -> /livespec:revise"). Check before assuming a plain PR suffices.

4. **`supervisor.py add` cannot set `--epic`/`--ctx-threshold`** (new,
   already documented in `overseer-mgg`'s 2026-08-17 14:41 comment as "a real
   gap in the one-shot CLI, worth its own follow-up"). Hit twice on
   2026-08-17 (once forcing a manual JSONL edit mid-live-verification). Add
   the two flags, or auto-derive `epic` at add-time via the existing
   `epic_from_plan_anchor` path when a matching plan directory exists.

5. **Blocking `AskUserQuestion` escalations freeze the WHOLE foreman loop**
   (new). The foreman's cron-driven tick only fires while its own REPL is
   idle; a blocking picker with no answer for 12 hours froze ALL supervision
   for every track under that foreman, not just the one that raised the
   question. Needs a non-blocking escalation pattern in the operator
   contract: red-block the row + push notification + a scheduled re-check,
   reserving a blocking picker only as a bounded-wait last resort. This is an
   operator-CONTRACT design question (prose, not code) — likely overlaps
   item 3's spec-bearing-ness question and may be worth landing together.

6. **Daemon log redirect is lost across manual bounces** (new, confirmed live
   2026-08-18 per `overseer-xkrwm3`'s WATCH-STALENESS comment: the daemon
   running since 01:50Z writes no `daemon.log` at all — `tmp/overseer/
   daemon.log` stopped being written at 13:01Z the PRIOR day because the
   16:45Z bounce launched `python3 -m overseer.daemon` with no redirect).
   Either the daemon should open its own log file natively (removing the
   redirect dependency entirely — the more robust fix, since it can't be
   forgotten), or the documented bounce procedure in the repo's own
   `CLAUDE.md` daemon-restart ruling must be amended to mandate the redirect
   AND something should verify it (e.g. a doctor/attention check that flags
   a daemon running with no growing log).

7. **Link, do not re-file**: `overseer-6m50` (P1, daemon respawn silently
   fails after a supervisor `ready` is consumed — a DIFFERENT restart-
   interlock defect than `overseer-mgg`'s resume-submit race, per its own
   "Why this is not overseer-bckv" section) and `overseer-a2txsq` (migrate
   this repo's own live foreman session to the canonical
   `livespec-overseer-foreman` reserved topic — filed by this same worker's
   prior `overseerd-auto-restart` track). Both are foreman/restart-assurance
   shaped and arguably belong under this plan's umbrella rather than sitting
   loose. `overseer-l7c6` (Phase E federation) is EXPLICITLY excluded per the
   commissioning directive — it is already captured by `overseer-z5fo4y`'s
   archive handoff and is a deliberately-backlogged future-scope item, not
   an actionable foreman-operation improvement.

## Non-goals

- Re-deriving or second-guessing the resume-submit-integrity epic
  (`overseer-xkrwm3`)'s own scope — cite its lessons, do not duplicate its
  work fronts.
- Building Phase E peer-foreman federation (`overseer-l7c6`) — explicitly
  out of scope per the commissioning directive and the standing prose
  contract's own prohibition.
- Weakening the cardinal rule for any escalation/watch mechanism designed
  here — a non-blocking escalation pattern (item 5) must still never
  authorize a restart on anything but a session's own fresh `ready`; it only
  changes how a HUMAN DECISION gets surfaced, never who may authorize a
  restart.
