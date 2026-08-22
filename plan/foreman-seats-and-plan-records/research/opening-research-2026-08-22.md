# Seat identity, registry derivation, and plan-record parity

Opening research note for `plan/foreman-seats-and-plan-records`. Ledger anchor `overseer-ow7c`.

Written 2026-08-22 when this thread was cut out of `plan/foreman-improvements`
(anchor `overseer-au3pt3`) by the grooming drain pass, at the maintainer's
direction and on their selected cut.

## Why this thread exists separately, and why it is the awkward one

This cluster is where the blockage in the old junk drawer was concentrated:
**five of the six `blocked` children of `overseer-au3pt3` are here.** That is the
strongest argument for giving it its own thread and its own session — in a
38-child epic those five were invisible, and each one is blocked on a different
thing.

It is also the cluster with the least internal coupling. No `blocks` edge exists
anywhere within it. What holds it together is a shared question: **what is a seat,
what is a plan record, and do the two agree with each other?** Every child is a
place where the answer is currently derived rather than recorded, or recorded in
two places that nothing reconciles.

## What this thread holds

| child | status at cut | scope |
|---|---|---|
| `overseer-2a1` | blocked | `supervise-plan` cannot generate a charter for a new plan thread: 4 of 5 HALT preconditions |
| `overseer-403` | blocked | the plan-thread anchor gate quantifies over LIVE repo state |
| `overseer-bak` | blocked | nothing holds a plan thread's two records in agreement (`handoff.md` vs `supervisor-handoff.md`) |
| `overseer-ng1i` | blocked | `plan_thread_epic_parity`'s reader queries `bd list` without `--all`, so it misses rows |
| `overseer-a2txsq` | blocked | migrate this repo's live foreman session to the canonical reserved topic |
| `overseer-an0d` | ready | a `ForemanSeat` epic has no derivation rule, so a lost operator-seat epic is unrecoverable |
| `overseer-c3mrkc` | ready | backfill or document null supervisor registry epics |
| `overseer-ooro` | backlog | stale running foreman sessions carry the pre-variant register clobber |
| `overseer-7jskz4` | backlog | print attach commands for missing plan-track tmux sessions on every tick |
| `overseer-vx4ky3.7` | ready | seat-model measurement: foreman seats on `claude-sonnet-5` |

`overseer-vx4ky3.7` is a carry-forward: its own epic `overseer-vx4ky3`
(foreman-autonomy-hardening) is **closed and archived**, and the child was
re-parented onto the junk drawer when that happened. It is a seat-identity
measurement, so it lands here rather than staying with the actuator.

## `overseer-bak` is this thread's spine, and it has a live consumer

`overseer-bak` — nothing enforces agreement between a plan thread's two records —
is cited BY NAME in every plan-anchor acceptance field in this repo, as the reason
archive-time record agreement "must be checked by hand". Every anchor in the repo
is currently carrying a manual step that exists because this item is open. That
makes it the highest-leverage child here even though it is P2 and blocked.

Note the recursion, and do not let it become an excuse: this thread's OWN anchor
carries that same clause.

## Explicit deferrals

- **Actuator behaviour** (`foreman-act`, `plan_start`, `work_item_session_start`)
  — deferred to `overseer-au3pt3`. The seam: this thread owns what a seat and a
  plan record ARE; the actuator thread owns the commands that mutate them.
  `overseer-a2txsq` sits close to that line — it is a migration of a seat's
  identity, not a fix to the actuator that performs it.
- **Attention-condition truth and stall clocks** — those live in
  `plan/supervision-safety-and-attention-truth` (`overseer-6tfncs`), which was
  considered as a home for this whole cluster and rejected: it already carries 17
  open children and its subject is acting-safety, not record identity.
- **Track tagged-union modelling** — `plan/track-record-type-safety`
  (`overseer-y3xhlh`) owns that and had zero open children at the cut.

## Read first

- `overseer/AGENTS.md`, the registry and seat sections.
- The plan-anchor acceptance template on any anchor epic, for the `overseer-bak`
  clause this thread is meant to discharge.
- The ledger anchor `overseer-ow7c` and each child's own acceptance field.
