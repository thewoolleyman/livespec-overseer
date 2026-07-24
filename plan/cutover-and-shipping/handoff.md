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
- **Merged + live, PARKED AT THE HUMAN ACCEPTANCE VALVE** (`ai-then-human`,
  AI PASS; independent verification journaled on each item 2026-07-24):
  daemon-log persistence (`overseer-2boaoy`, PR #56 — launch line `2>` →
  `2>>`; bare append, no rotation — flagged; effective only on the next
  daemon relaunch) and canonical-command + adopter install story
  (`overseer-5aaeyd`, PR #58 — `livespec-overseer:overseer` reconciled, D5
  boundary documented in README). The groomed operator-surface queue is now
  fully merged.
- **Slice-5 units 1+2 done:** this thread's own charter at
  `plan/cutover-and-shipping/supervisor-handoff.md` (PR #54), and the
  fleet-pin-propagation charter durable at core
  `plan/fleet-pin-propagation/supervisor-handoff.md` (core PR #1717,
  2026-07-24) — both authored via `supervise-plan`. Unit 3
  (factory-success-rate-remediation) HALTED on the skill's precondition 4:
  no `plan/factory-success-rate-remediation/` thread directory exists in
  core — needs an owner decision on that charter's durable home (surfaced
  on `overseer-tvko3z`).
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
2. **Acceptance valves:** `overseer-2boaoy` (PR #56) and `overseer-5aaeyd`
   (PR #58) await the maintainer's `accept:` — ai-then-human policy, AI
   PASS, independent verification journaled on each item (incl. the
   no-rotation flag on 2boaoy). Surface, never self-accept.
3. **`overseer-tvko3z` remaining:** (a) owner decision on the
   factory-success-rate-remediation charter's durable home — no core plan
   thread exists, so `supervise-plan` precondition 4 fails as designed;
   (b) tmp/-copy retirements with the owning tracks' supervisors (the
   fleet-pin-propagation durable copy landed via core PR #1717; adoption
   offer posted in that track's status.log). Cross-repo attended work.
4. **Slice 4 (upstream one-liners)** — core `NFR:175` and orchestrator
   contracts thread-store mentions — may now route via
   `/livespec:propose-change` in THOSE repos (the skill they describe
   exists). Maintainer-lane; coordinate before filing cross-repo.
5. **Maintainer rulings outstanding** (surface, never block): (a) rollback
   UNPIN post-proof — recipes below stay recorded until ruled; (b) a daemon
   restart at their timing — it picks up everything since 22:29Z including
   the version header, and ACTIVATES the merged append-mode log fix
   (PR #56 is effective only on relaunch via `overseer-start`; the running
   daemon still truncates, snapshot already taken:
   `tmp/overseer/daemon.log.snapshot-20260724T083730Z`); (c) the Phase-2 cuts in
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
