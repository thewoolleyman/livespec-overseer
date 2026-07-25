# Plan — cutover-and-shipping

**Owning repo:** `livespec-overseer`. **Status:** **OPEN** — created 2026-07-23
as the SUCCESSOR of livespec core's `plan/archive/overseer-productization/`.

> **THIS THREAD IS NOT DONE AND MUST NOT BE ARCHIVED.** Its cutover +
> daemon-shipping HALF is complete, but its eventual PAYLOAD — Phase 2,
> adopter-family shipping — is NOT built. That payload is epic
> **`overseer-19s`**, an open CHILD of this thread's epic `overseer-3wt`
> (which therefore reads 3/4 complete and is not closeable). The living plan
> is `research/phase-2-adopter-shipping.md`, in THIS thread — do not relocate
> it. See §NEXT ACTION.
>
> Correction of record: supervisor brief 20 (2026-07-25) directed closing the
> epic and archiving this thread; brief 21 WITHDREW that as wrong, on the
> grounds that archiving with Phase 2 undone is archiving incomplete work.
> Nothing was closed or archived — no archive PR, branch, or worktree ever
> existed, and `overseer-3wt` was never closed.

**Ledger anchor:** epic `overseer-3wt` (this repo's beads tenant); children
and lanes are READ from the ledger (`list-work-items` / `next`), never stored
here. The epic's COMMENTS carry the thread's evidence journal (Stage-4
proofs, acceptance bases, cut routing) — read them alongside this file. The
CORE-tenant epic `livespec-b1uo` stays in core per its do-not-move ruling.

## Where the thread stands — 2026-07-25, after the ratify→build→restart run

The thread has TWO halves. **Half one — the cutover and the daemon shipping — is
COMPLETE.** Half two — Phase 2, adopter-family shipping — is **NOT STARTED**, and
is why this thread stays open (§NEXT ACTION).

Half one's cold-open chain is DONE. In order, with evidence:

1. **Build verified NOT stale** — `resolve_template.py` exit 0 on the pinned
   build `ba62d8fdd609`. The exit-78 failure that forced the restart did not
   recur.
2. **BOTH proposals RATIFIED** — `SPECIFICATION/history/v002/` cut (PR #73).
   doctor-static 21/21, `just check` 60/60. `proposed_changes/` is drained to
   its README.
3. **`overseer-6uobos` SHIPPED** — Surface A+B (PR #74 factory, PR #75 review
   fix). Work-item closed `resolution:completed`.
4. **ACTING DAEMON RESTARTED** — new pid, single instance, watch-set intact,
   header now carries `0.11.0`, and `overseer-2boaoy`'s append is live-exercised.

### What the restart proved (2026-07-25T06:57Z)

- **`overseer-2boaoy` live-exercise COMPLETE.** Mechanically, not by eyeball:
  the daemon's stderr fd2 flags went `0100001` (`O_WRONLY|O_LARGEFILE`, **no**
  `O_APPEND` — the old `2>` truncate) → `0102001` (`O_APPEND` set), and the 80
  pre-restart log lines are **byte-identical** with new lines appended below.
  This item's last open thread is closed.
- **`overseer-6uobos` live-exercised on the first post-restart tick**, all three
  classes at once: `02-parameter-store-bootstrap` (homelab) hit the **fourth
  truth-table cell** — live supervisor session + NO `supervisor-handoff.md`,
  both verified directly — and correctly surfaced the **capture offer** rather
  than silent-healthy. That is precisely the track the maintainer's 2026-07-24
  decision existed to stop exempting. `worktree-location-enforcement` fired
  plain Surface A; `console-happy-path-mvp` stayed `blocked:human`, proving the
  supervision surfaces sit BELOW the NEEDS-YOU classes.

### Two baseline corrections — do NOT re-trip on these

- **Tracks are 24, not 25.** The count had already drifted to 24 *before* any
  restart; post-restart is also 24. The older "25" is stale.
- **`livespec-runtime` legitimately contributes 0 tracks.** Its `plan/` holds
  ONLY `archive/`, and discovery excludes archived plans. A naive "has a `plan/`
  dir ⇒ must have rows" check **false-alarms** here — it is NOT a shrunk
  watch-set. Verify per-repo counts against *unarchived* plan dirs.

### Method note for the next daemon restart

`overseer-start` could NOT have done this, for two independent reasons, both
verified in the code:

- It is **idempotent** — `window_pane_titles(pane)` finds the existing
  `overseer-daemon` pane and logs "leaving it", so it never relaunches and
  therefore cannot load new code.
- It splits its **own** `$TMUX_PANE`'s window. The planning session lives in
  `cutover-and-shipping:1.1`, NOT the overseer window, so running it there would
  have spawned a SECOND daemon in the wrong session — the forbidden double-launch.

The working method is the one `overseer/AGENTS.md` sanctions ("kill the daemon
pane and relaunch"): an atomic
`tmux respawn-pane -k -t livespec-overseer:1.1 -c <repo> '.venv/bin/overseerd 2>> tmp/overseer/daemon.log'`.
Note **bare `overseerd` is NOT on the login-shell PATH on this host** (that is
why the acting daemon ran a script path), so `daemon_command()`'s bare
`overseerd` would fail in a pane shell — use `.venv/bin/overseerd`, which is an
editable-install console script resolving to the source tree, so it runs latest
master. Keep the `2>>`.

## Prehistory — 2026-07-24, after the proving day

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
  (PR #54); the fleet-pin-propagation charter at core (landed by core PR #1717
  at `plan/fleet-pin-propagation/`, and since MOVED to
  `plan/archive/fleet-pin-propagation/supervisor-handoff.md` when that thread
  archived — verified 2026-07-25); the
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

## NEXT ACTION — GROOM PHASE 2, THEN BUILD IT

**Phase 2 (adopter-family shipping) is this thread's remaining payload.** It is
epic **`overseer-19s`**, an open child of `overseer-3wt`. Nothing about it is
started, and nothing is in flight.

**The living plan is `research/phase-2-adopter-shipping.md`, beside this file.**
It is a **DRAFT SHAPE**, explicitly not a cut: *"the maintainer owns every cut
below."* Do NOT treat it as a slice list, and do NOT relocate it.

Do this, in order:

1. **GROOM it into buildable, dependency-layered slices under `overseer-19s`.**
   Use `/livespec-orchestrator-beads-fabro:groom` — a read-only drafting
   conversation; the maintainer OWNS the cut and the acceptance, and the
   front-end files NOTHING until approval. The draft's own three OPEN QUESTIONS
   are maintainer calls that likely gate the cut: (a) marketplace hosting — own
   marketplace vs. joining a family one; (b) is the Codex arm in scope for first
   ship (`.livespec.jsonc` declares `codex: exempt` today, though the daemon half
   is already harness-neutral); (c) does "shipped" warrant a SPECIFICATION
   scenario (that would route through `/livespec:propose-change`, spec-side and
   human-gated).
2. **Then build the slices** through the normal machinery (`drive --action
   approve:<id>` then `impl:<id>` for factory-tier work).

**What Phase 2 must NOT redo** — the operator surface is already shipped and
accepted: entry points (`overseer-m5dtmj`), plugin scaffold (`overseer-tn3hmi`),
`supervise-plan` (`overseer-myjovi`), version-in-header (`overseer-vlu5cd`),
canonical-command + adopter install story with the D5 boundary documented in the
README (`overseer-5aaeyd`), daemon-log persistence (`overseer-2boaoy`), and
supervision surfaces A+B (`overseer-6uobos`). Phase 2 starts from a shipped,
Stage-4-proven tool.

**Standing bounds** (from the D-codes on core epic `livespec-b1uo`, which stays
in core): never read the fleet manifest (D5 — the family's own
`~/.livespec-overseer-repos.json` is the ONLY discovery input); never a console
component (D7 peers); no new ledger state; no new store paths.

### Also open, not blocking Phase 2

- **`overseer-fitvmo`** (P2 bug, pending-approval) — `supervise-plan` generated
  prompts must not stall on conflict boundaries. Filed 2026-07-25 by a different
  session; STANDALONE, not a child of this epic. Left deliberately open.
- **7 untied spec→impl gaps.** `detect-impl-gaps --since-version v001` returns 7
  gap-ids from the v002 delta with no work-item tied to any. The revise post-step
  `capture-impl-gaps` was deliberately NOT run to filing — it would have filed 7
  auto-derived items across the groomed queue without consent. Re-run it if you
  want them tracked.
- **`check-no-workflow-edits` copy-drift.** `overseer-6uobos`'s factory run hit
  the known `bd-ib-d6ds` blocker (the default janitor requires this recipe, which
  was missing in 4 of 8 fleet repos including this one) and landed it inline —
  the same authorized remedy rop-sweep used for its 4 mirrors. Each carrying repo
  now hand-rolls its OWN variant. Same copy-drift class as
  `export-ci-telemetry.sh`; single-sourcing into livespec-dev-tooling is
  dev-tooling's call.

### CLOSED — do not re-open these as work

- **Slice 4 (upstream one-liners): needs NO filing.** Verified 2026-07-25 against
  both targets' LIVE RATIFIED spec: livespec core
  `SPECIFICATION/non-functional-requirements.md` and
  `livespec-orchestrator-beads-fabro` `SPECIFICATION/contracts.md` each already
  carry a **"The hosted supervision artifact."** paragraph naming
  `plan/<topic>/supervisor-handoff.md` as a non-owned, realization-agnostic
  artifact — introduced at ratified **core v175** and **orchestrator v048**
  respectively. Filing the prepped FIND/ADD packets would DUPLICATE ratified
  content. The packets in `research/slice4-upstream-one-liners-and-unit3-home.md`
  are now historical; that file's Packet A/B sections are superseded.
- **`overseer-tvko3z`: CLOSED** 2026-07-25. All three supervisor charters are
  durable via their owning repos' PR discipline (livespec-overseer PR #54,
  livespec core PR #1717, orchestrator PR #939); the last tmp/ residue
  (core `tmp/fleet-pin-propagation-supervisor-prompt.md`) was swept after
  verifying section-by-section that nothing durable was lost — it self-declared
  as a superseded pointer and its unique content was volatile live-state that the
  durable copy's `Corrections` records as deliberately left behind. The item's
  "in core" premise was corrected on the item (unit 3's owning repo is the
  orchestrator).

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
