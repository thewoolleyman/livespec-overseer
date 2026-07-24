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
- **Slice-5 unit 1 done:** this thread's own durable supervisor charter
  exists at `plan/cutover-and-shipping/supervisor-handoff.md` (PR #54) —
  also `supervise-plan`'s first live exercise.
- **Factory serialization is RETIRED** (sd8o diagnosis 2026-07-24 ~07:11Z:
  no contended host resource; maintainer relay). Dispatch per the normal
  machinery; still binding forever: prove container ownership by run-config
  argv via an ALL-container scan, `exit 137` is ambiguous, outcomes from
  artifacts never exit codes, timestamps via `date -u`.

## Next actions, in order

1. **Ratification then surfaces.** The spec proposals in
   `SPECIFICATION/proposed_changes/non-interference-attended-skill-carveout.md`
   (attended-skill carve-out + existence-only discovery allowance) await the
   maintainer's `/livespec:revise` pass — being surfaced by the supervisor;
   not this session's to run unprompted. Once RATIFIED, `overseer-6uobos`
   (supervision surfaces A+B; spec-owner recommendations drafted on the
   item, including the fourth-truth-table-cell capture-offer) clears its
   preconditions: approve and dispatch via `drive --action impl:<id>`.
2. **`overseer-5aaeyd`** (canonical-command + adopter install story) sits at
   an auto-policy admission; the dispatcher's own pass flows it — dispatch
   when it shows `ready`.
3. **`overseer-tvko3z` remaining units:** migrate the two livespec-core
   supervisor charters (fleet-pin-propagation,
   factory-success-rate-remediation) out of core's gitignored `tmp/` using
   the `supervise-plan` skill against CORE's PR discipline — cross-repo
   attended work, best coordinated with those tracks' supervisors (unit-1
   precedent and notes on the item).
4. **Slice 4 (upstream one-liners)** — core `NFR:175` and orchestrator
   contracts thread-store mentions — may now route via
   `/livespec:propose-change` in THOSE repos (the skill they describe
   exists). Maintainer-lane; coordinate before filing cross-repo.
5. **Maintainer rulings outstanding** (surface, never block): (a) rollback
   UNPIN post-proof — recipes below stay recorded until ruled; (b) a daemon
   restart at their timing so the acting supervisor picks up the version
   header and everything since 22:29Z (snapshot `tmp/overseer/daemon.log`
   first — it truncates on daemon restart until `overseer-2boaoy` lands;
   that item is `ready`, dispatchable anytime); (c) the Phase-2 cuts in
   `research/phase-2-adopter-shipping.md` (marketplace hosting, Codex arm,
   spec scenario).

## Rollback (pinned until the maintainer unpins)

Kill the daemon and relaunch the byte-identical pre-seed state from EITHER:
`git -C /data/projects/livespec archive f9664481~1 .claude/skills/overseer |
tar -x -C <rescue-dir>`, or this repo at pin `6425828`.

## Operational map

Daemon: tmux `livespec-overseer:1.1`, stderr log `tmp/overseer/daemon.log`
(truncates on DAEMON restart only). Protocol: `overseer/marker-protocol.md`.
Invariants: `overseer/AGENTS.md`. Design reasoning beside this file:
`research/operator-surface.md`, `research/phase-2-adopter-shipping.md`, and
the durable supervisor charter `supervisor-handoff.md`. Cross-track
coordination log (historical + still active): livespec core
`tmp/fleet-pin-propagation-supervisor/status.log`. The full cutover-day and
proving-day narrative lives in this file's git history and the epic's
comments; core's `plan/archive/overseer-productization/` is the prehistory.
