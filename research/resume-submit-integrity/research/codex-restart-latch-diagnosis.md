# Why overseerd never restarts a compacted Codex session — diagnosis and mechanical fix plan

Measured live 2026-08-14 (23:5xZ) against the running daemon (pid 445210,
v0.37.4) and the live example the maintainer named: `fleet-ci-runner-pool`
(Codex, repo `/data/projects/livespec`). Per the operator directive recorded on
the plan epic 2026-08-14T21:45Z, no manual restart, state-file write, or
dashboard-motivated repair was performed; every observation below is read-only.

## The observed facts

1. The track is adopted and healthy at the mechanics level: the daemon table
   reads `warned  fleet-ci-runner-pool (codex)  35%  livespec`. Ctx parsing is
   correct (`signals._CTX_RE` requires the `Ctx:`/`Context` prefix, so the
   newer Codex statusline segment `weekly 78% left` cannot false-match).
2. The injection-stamp sidecar holds an OPEN round for the track:
   `at = 1786647941` (2026-08-13T19:05:41Z), `bands = [50, 40, 30, 20]` (all
   consumed), `voided_at = 1786648937` (2026-08-13T19:22:17Z),
   `session_identity = codex:019ffc6d-5473-70e1-a730-4b784779cecc`.
   So on Aug 13 the escalation DID deliver through every band — the session
   reached ≤20% — and the session DID declare `ready` once, which the daemon
   voided as stale ~17 minutes into the round (busy past the 120s grace: the
   session had resumed work; a correct void per the ratified letter).
3. The Codex session then **auto-compacted**, regaining headroom. The live
   context watch (`/tmp/overseerd-live-context-watch-current.log`) shows it at
   **56%** when the watch started 2026-08-14T05:53Z, then descending
   56 → 48 → 42 → 38 → **35%**, where it has sat idle for ~15 hours.
4. On that second descent it re-crossed the 50 and 40 bands. `maybe_inject`
   computed `due = []` both times — those bands are already in the round's
   durable notified set — so **no wrap-up fired**. No wrap-up means the session
   is never re-told to write `.overseer-state`; no session-written `ready`
   means the cardinal rule (correctly) forbids any restart; and nothing but a
   restart closes a delivered round. The daemon is latched.
5. The latch is invisible: `warned` is not an attention status, so the track
   never entered `NEEDS YOU`. The tmux pane shows Codex's own `Ready`
   indicator, which is an idle-input display and has nothing to do with the
   restart authorization (the absent `.overseer-state` file) — the exact
   confusable distinction the operator asked to surface.

The daemon executed the ratified specification faithfully at every step. The
defect is in the ratified letter itself: `SPECIFICATION/spec.md` §"The
supervision round" — "The restart is the ONLY event that closes a DELIVERED
round. No other daemon behavior — voiding a declaration included — MAY delete
such a round's durable record or reset its notified escalation bands." That
clause was written against a model in which remaining context only ever falls
within a session's lifetime. **Codex auto-compaction (and Claude `/compact`)
violates that monotonicity premise**, and the round model has no
context-recovery transition, so one full escalation permanently exhausts the
daemon's only lever for the rest of the session's (arbitrarily long,
compaction-extended) life.

## Root causes

- **RC1 — no round closure on context recovery.** A delivered round whose
  session climbs back ABOVE the wind-down threshold (compaction) stays open
  with its bands consumed; every later threshold crossing is silent. This is
  the primary latch and it is generic to any compaction-capable runtime, not
  Codex-specific — Codex merely compacts automatically and so hits it first.
- **RC2 — a voided `ready` is never re-solicited.** The void raises the
  certification floor and logs, but the session — which was mid-escalation and
  plainly protocol-aware (it had just declared) — is never told its
  declaration was voided or asked to re-declare when genuinely done; and the
  band at its current context is already consumed, so the standing escalation
  cannot re-prompt either.
- **RC3 — escalation exhaustion has no attention membership.** "Below
  threshold, idle, open round, all due bands consumed, no declaration" is
  precisely "the daemon has no lever left and only a human can move this
  track", yet it renders as plain `warned` outside `NEEDS YOU`. (Adjacent to,
  but distinct from, the ratified v011 restarted-never-worked membership.)

## Mechanical fixes (the plan)

All three fixes contradict or extend the ratified letter, so the route is one
spec-side `/livespec:propose-change` covering the slate, then the ordinary
revise → implementation-gap detection → factory children pipeline that v011
already exercised on this thread:

1. **Recovered-round closure (fixes RC1).** When an act-tick observes a
   delivered round whose session's effective context is ABOVE the wind-down
   threshold, with no outstanding certifying `ready` and no `resume_pending`,
   the daemon closes the round as RECOVERED (clears the stamp record,
   resetting bands for any future round). A later threshold crossing then
   opens a fresh round and the escalation fires again. This preserves the
   cardinal rule untouched — it authorizes a re-WARN, never a restart — and
   preserves "restart is the only closure of a round that is still below
   threshold".
2. **Post-void re-solicitation (fixes RC2).** Voiding a `ready` re-arms
   exactly the band at the session's current effective context (or, if
   band re-arming is judged to contradict at-most-once-per-round too deeply,
   a single dedicated "your ready was voided because you resumed work;
   re-declare when genuinely done" injection, subject to the same paste
   authorization gates as the wrap-up). Bounded: one re-solicitation per
   void, so a declare/void loop cannot spam.
3. **Escalation-exhausted attention membership (fixes RC3).** A new
   daemon-owned `NEEDS YOU` membership: delivered round, effective context
   at/below threshold, session idle past a bounded floor, all due bands
   notified, no declaration on file — report-only, edge-triggered, badge
   semantics per the v011 pattern. Its note must surface the operator-asked
   distinction explicitly: the runtime UI's "Ready" is idle-input display;
   restart authorization is only `<repo>/tmp/overseer/<topic>/.overseer-state`
   containing exactly `ready`, and that file is ABSENT.

**Live acceptance (per the operator directive):** after the fixes deploy and
the daemon is restarted, `fleet-ci-runner-pool` must — with no manual
state-file write and no manual restart — receive a fresh current-session
wrap-up round, autonomously declare, and be restarted by the daemon via
`codex resume` with its canonical UUID and a delivered kick. The stamp record,
daemon log, and successor pane are the evidence surfaces.

## Why pane-scraping at all — doesn't Codex expose an API? (maintainer question, 2026-08-14)

Partly, and the repo already consumes the machine-readable parts it trusts:
session discovery joins `/proc` fds to `~/.codex/sessions/**/rollout-<ts>-<id>.jsonl`
filenames and `~/.codex/session_index.jsonl` (exact, not scraped). What is NOT
consumed is machine-readable session STATE: an earlier cut computed context
from the rollout's `token_count` events and was wrong by 2–4 points against
Codex's own display, because it reimplemented codex-rs's private occupancy
formula (drifts with any Codex release); that code was deliberately removed
(`overseer/.claude/CLAUDE.md`, invariant 6 notes), and the rollout BODY is a
full transcript the daemon must not read as a matter of policy. Codex does
ship a programmatic surface (the `codex app-server` JSON-RPC protocol, and
JSONL event output in exec mode), but the supervised sessions are interactive
TUIs the daemon did not spawn and cannot retroactively attach a control
channel to. So statusline parsing of Codex's OWN rendered number remains the
narrow, fail-closed coupling — it reads what Codex computes rather than
recomputing it. A future front could evaluate driving new Codex tracks
through `codex app-server` to get structured state without scraping; that is
explicitly OUT of scope for this slate (see the scope event) because it is an
architecture change, not the latch fix, and the latch is runtime-generic.

## Predecessor-incarnation findings (foreman relay, 2026-08-14)

The prior Codex incarnation of this track failed procedurally (not on this
diagnosis) in four layers: (1) it obeyed the retired handoff-file shape taught
by the ambient `.ai/` instruction layer until a maintainer intervened; (2) the
Codex skill catalog pointed at a deleted plugin-cache version dir; (3) the
plan prose names package functions (`append_handoff(...)`) with no CLI
wrapper, invocation line, or bootstrap recipe, forcing it to reverse-engineer
`_bootstrap.py` and hand-roll an env-injected heredoc; (4) the write path
silently requires the credential wrapper and emits a non-fatal auto-backup
warning, and `bd comment list` returns a false empty (`bd comments <id>
--json` is the working read-back). Disposition: R1–R4 (plan-verb bin
wrappers + one blessed path + quickstart + failure-mode docs) filed on the
livespec-orchestrator-beads-fabro tenant; R5 (catalog staleness) filed on
livespec-driver-codex; R6 (ambient-instruction contradiction) is already
in-flight under the planning-lane-redesign slate on the livespec tenant and is
cited, not duplicated. One in-scope residue for THIS repo: the mapping-store
row for this very thread still carries a legacy `resume` override naming
`plan/resume-submit-integrity/handoff.md` — a respawned successor would be
pointed at the retired shape — filed as a child here.
