# Plan — cutover-and-shipping

**Owning repo:** `livespec-overseer`. **Status:** OPEN — created 2026-07-23 as
the SUCCESSOR of livespec core's `plan/archive/overseer-productization/`.

**Ledger anchor:** epic `overseer-3wt` (this repo's beads tenant); children
and lanes are READ from the ledger (`list-work-items` / `next`), never stored
here. The epic's COMMENTS carry the thread's evidence journal (Stage-4
proofs, acceptance bases, cut routing) — read them alongside this file. The
CORE-tenant epic `livespec-b1uo` stays in core per its do-not-move ruling.

## Where the thread stands — 2026-07-24, after the proving day

- **The cutover is PROVEN.** This repo's daemon is the acting fleet
  supervisor and both Stage-4 legs are observed: the declare-ready →
  atomic-restart interlock (fleet-pin-propagation, 22:49:57Z) and the
  daemon-INJECTED wrap-up → ready → restart round, twice
  (rop-sweep-fleet-policy 23:31→23:36Z; fabro-ci-image-factoring
  01:08→01:09Z). Verbatim evidence: the Stage-4 comments on `overseer-3wt`.
  This session itself was recycled by the daemon's wind-down — the protocol
  working end to end on its own birth thread.
- **Shipped through the factory and accepted** (evidence on each item):
  entry points (`overseer-m5dtmj`, PR #42), plugin scaffold
  (`overseer-tn3hmi`, PR #46), the `supervise-plan` skill
  (`overseer-myjovi`, PR #49), version-in-header (`overseer-vlu5cd`, PR #51,
  release-please-wired), the telemetry argv fix (`overseer-kfbcv4`, PR #50);
  earlier: bootstrap re-point (`overseer-y8o`), alert edge-triggering
  (`overseer-4dr`), module-doc sweep (`overseer-zvo`).
- **Merged + live + ACCEPTED** (`acceptance → done`, supervisor-discharged
  on independent verification; bases journaled on each item 2026-07-25):
  daemon-log persistence (`overseer-2boaoy`, PR #56 — launch line `2>` →
  `2>>`; bare append, no rotation — flagged; the live-exercise of the
  append completes at the next acting-daemon relaunch), canonical-command +
  adopter install story (`overseer-5aaeyd`, PR #58 — `livespec-overseer:overseer`
  reconciled, D5 boundary documented in README), and the e9j Wave-1 role-key
  backfill (`overseer-3o9`, PR #65 — four keys declared-empty, nothing
  armed; rule-3 two-check proof re-run green). The groomed operator-surface
  queue is fully merged and accepted.
- **Slice-5 ALL THREE charters durable** (via `supervise-plan` / records
  PRs): this thread's charter `plan/cutover-and-shipping/supervisor-handoff.md`
  (PR #54); the fleet-pin-propagation charter at core
  `plan/fleet-pin-propagation/supervisor-handoff.md` (core PR #1717); the
  factory-success-rate-remediation record (three artifacts) at
  `plan/archive/factory-success-rate-remediation/` in the ORCHESTRATOR repo
  (PR #939 — that thread archived there, epic `bd-ib-cvgjop`; the peer
  supervisor concurred on the coordination log 2026-07-24T21:29:40Z). tmp/
  copies retired. `overseer-tvko3z` remaining: the item-text "in core"
  premise correction + the last fleet-pin tmp/-prompt sweep, at the
  needs-human resolve.
- **Factory serialization is RETIRED** (sd8o diagnosis 2026-07-24 ~07:11Z:
  no contended host resource; maintainer relay). Dispatch per the normal
  machinery; still binding forever: prove container ownership by run-config
  argv via an ALL-container scan, `exit 137` is ambiguous, outcomes from
  artifacts never exit codes, timestamps via `date -u`.

## NEXT ACTION (cold-open: execute this from this file alone)

This session was restarted by the acting daemon SPECIFICALLY to load the
pinned livespec plugin build `ba62d8fdd609` (livespec v0.20.2); the prior
process had resolved the stale build `f93ca440b0de` at startup, which made
`/livespec:revise` refuse with `resolve_template.py` exit 78. Do the steps
in order:

1. **VERIFY THE BUILD FIRST — do not ratify on the stale build.** Resolve
   livespec core root by reading THIS project's entry in
   `~/.claude/plugins/installed_plugins.json` (match
   `projectPath == /data/projects/livespec-overseer` — NOT `entries[0]`,
   which is a different project) and run
   `python3 <core-root>/scripts/bin/resolve_template.py --template livespec`.
   It MUST exit `0` and print a template path. If it still reports build
   `f93ca440b0de` / exits 78 after this fresh restart, HALT and report — that
   is a genuine harness resolution bug to escalate, not to force around.

2. **RATIFY BOTH PROPOSALS.** Run `/livespec:revise` and accept BOTH pending
   proposals in `SPECIFICATION/proposed_changes/`:
   `non-interference-attended-skill-carveout.md` (attended-skill carve-out)
   and `supervision-existence-probe-allowance.md` (existence-only discovery
   allowance). The §Non-interference reconciliation repair merged as **PR #70**
   and the INDEPENDENT re-review returned **NO BLOCKERS** on the repaired
   pair — do NOT re-review again unless `/livespec:revise` itself demands it.
   Both proposals edit `spec.md §Non-interference` with disjoint,
   collision-free anchors; the probe proposal also adds one `scenarios.md`
   scenario requiring a `tests/heading-coverage.json` co-edit. This cuts
   `SPECIFICATION/history/v002/`.

3. **BUILD `overseer-6uobos` (Surface A+B).** Preconditions both clear once
   step 2 lands: the existence-probe allowance is ratified, and the fourth
   truth-table cell was DECIDED 2026-07-24 (Surface A as a capture-offer,
   recorded on epic `overseer-3wt`). Per design §11.4 (read it at core
   `plan/archive/plan-skill-supervisor-handoff/design.md:437`): liveness-gated;
   two messages (A: live session + no `supervisor-handoff.md`; B: live
   session + file present + NO supervisor running); edge-triggered per
   episode (reuse the `overseer-4dr` machinery); Surface B proves "running"
   from live process evidence, never a session name. Item is factory-tier:
   `drive --action approve:overseer-6uobos` then
   `drive --action impl:overseer-6uobos` under `overseer-3wt`.

4. **ITEM (5) — RESTART THE ACTING DAEMON** (maintainer-decided RESTART NOW,
   brief 17/18). LAST, high-stakes live fleet op. Pre-baseline captured
   (verify POST-restart against it): **12-repo watch-set** (see
   `~/.livespec-overseer-repos.json`), **single daemon** (a NEW pid, still
   exactly one), **25 tracks discovered**, header renders
   `overseer — <iso> — N track(s) - 0.11.0`. Sequence: (a) post a heads-up
   to the coordination log (`date -u`); (b) stop the acting daemon cleanly
   and relaunch from this repo on latest master via `overseer-start` (two-pane,
   real `$HOME` watch-set) — no `kill-server`, no double-launch (confirm old
   pid gone first); (c) verify each: new daemon healthy + single instance,
   watch-set INTACT (a shrunk set or a second instance = HALT and report),
   header `0.11.0`, and 2boaoy's live-exercise (the new daemon's log APPENDS,
   prior content intact); (d) post a done line. HALT on any anomaly — a
   broken acting daemon is worse than a delayed restart.

### Prepped, maintainer-lane, DO NOT self-start

- **`overseer-tvko3z` remaining** (needs-human resolve): the item-text "in
  core" premise correction + the last fleet-pin tmp/-prompt sweep. Evidence
  + recommendation in `research/slice4-upstream-one-liners-and-unit3-home.md`.
- **Slice 4 (upstream one-liners)** — exact FIND/ADD packets for core
  `NFR:175` and the orchestrator contracts thread-store section are in that
  same research file. File via `/livespec:propose-change` in THOSE repos;
  re-verify FIND anchors first. Coordinate cross-repo.
- **Phase-2 cuts** (`research/phase-2-adopter-shipping.md`) — the
  maintainer's separate decision; do NOT start.

## Rollback — RETIRED 2026-07-25 (maintainer decision)

The maintainer ruled the cutover rollback RETIRED on the basis that
Stage-4 is proven end-to-end twice over (relayed via supervisor brief 17,
2026-07-25T01:12Z). The pre-seed pin is no longer maintained. The
recovery recipes remain in this file's git history (the PR #55 revision)
for forensic reference only.

## Operational map

Daemon: tmux `livespec-overseer:1.1`, stderr log `tmp/overseer/daemon.log`
(truncates on DAEMON restart only). Protocol: `overseer/marker-protocol.md`.
Invariants: `overseer/AGENTS.md`. Design reasoning beside this file:
`research/operator-surface.md`, `research/phase-2-adopter-shipping.md`,
`research/slice4-upstream-one-liners-and-unit3-home.md` (the prepped
maintainer yes/nos), and the durable supervisor charter
`supervisor-handoff.md`. Cross-track
coordination log (historical + still active): livespec core
`tmp/fleet-pin-propagation-supervisor/status.log`. The full cutover-day and
proving-day narrative lives in this file's git history and the epic's
comments; core's `plan/archive/overseer-productization/` is the prehistory.
