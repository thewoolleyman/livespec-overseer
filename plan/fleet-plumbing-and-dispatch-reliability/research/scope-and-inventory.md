# Scope and inventory

Created 2026-08-19T05:16:23Z by the grooming pass that bucketed every non-done
`livespec-overseer` work-item into a plan. This note is the write-once research
artifact required by the `plan` operation; the durable coordination record is
this thread's plan epic in the beads ledger, and every handoff is a comment on
that epic. Do not author a `handoff.md` here.

## Why this thread exists

Thirteen open work-items are not about the overseer's own behavior at all. They
are defects in the SHARED MACHINERY this repo sits on -- the Fabro dispatcher,
the beads server and its guard wrapper, the release and pin lanes, and plugin-root
resolution. They are grouped because they share a failure signature: **each one
fails in a way that points away from its own fix**, so each costs a fresh
investigation every time it is met. `CLAUDE.md` already carries several
hard-won write-ups of exactly these; this thread is where the write-ups become
repairs.

## The four strands

**Strand 1 -- dispatch claims and retries.** A dispatcher killed by its CALLER
leaves a phantom claim with no reconciliation path: the item sticks at `active`
and `accept:` refuses from `active` (`overseer-1hv`). The orchestrator
re-dispatches a work-item whose run died on a PERMANENT failure category --
nothing consumes fabro's failure category, so a spend-limit failure burns a host
dispatch-cap slot per retry (`overseer-fs4`). A CLOSED cross-repo sibling still
blocks its consumer: the satisfied gate never lifts, the item reads `ready`, and
every dispatch path answers "not in the ready set" (`overseer-lvp`). And the
post-merge janitor's pull of the PRIMARY checkout is unguarded, so one dirty file
there fails EVERY dispatch fleet-wide while the work itself merges fine
(`overseer-6pn`).

**Strand 2 -- the beads tenant.** Writes in this tenant are not backup-exported:
auto-backup warns `command denied to user livespec-overseer` on every write and
still exits 0 (`overseer-n04`) -- a silent durability hole. The guard wrapper
blocks a beads-native `--status open` that a caller legitimately passes, 13
refused operations in three days (`overseer-izh7`).

**Strand 3 -- release, pin and lock lanes.** `uv.lock` trails `pyproject.toml`
after every release with no gate catching it, so any `uv run` dirties a tracked
file (`overseer-l0f`) -- which is one of the ways Strand 1's janitor defect gets
triggered. `livespec-dev-tooling` owns two pin-lane gaps: the release fan-out
skips adopters and pin autodiscovery omits the Claude marketplace ref
(`overseer-mim`). The scheduled-pull lane fired 231 minutes late on 2026-07-27
under an account-wide delay, and the fleet's lag bound is unsound, so a genuine
drop would be silent (`overseer-ye5`). This repo's `host_dispatch_cap` override
must be reverted once the orchestrator deletes the key (`overseer-n11`).

**Strand 4 -- plugin resolution and documentation truth.** `resolve_core_root`
rule 2 misidentifies ANY plugin-shipping repo as livespec core, hard-stopping
every spec-side operation from an affected project (`overseer-af9`) -- the single
highest-blast-radius item in this thread. This repo's hard-coded
`ensure-codex-plugins` body should be replaced with the shared delegation
(`overseer-vfz5v5`). And `CLAUDE.md` dispatch trap B understates its own failure:
the release train is CONTINUOUS, so pinning "the new build" by hand goes stale
mid-session (`overseer-iwu`).

## Requirement carriers admitted to this thread

`overseer-1hv`, `overseer-fs4`, `overseer-lvp`, `overseer-6pn`,
`overseer-iwu`, `overseer-af9`, `overseer-izh7`, `overseer-n04`,
`overseer-l0f`, `overseer-mim`, `overseer-n11`, `overseer-vfz5v5`,
`overseer-ye5`.

The authoritative member list is the ledger -- the parent-child children of this
thread's plan epic -- never this file.

## Cross-repo note, and it is load-bearing

Several of these land in SIBLING repos, not here: the dispatcher and its ranker
in `livespec-orchestrator-beads-fabro`, the pin and release lanes in
`livespec-dev-tooling`. `.livespec.jsonc` lists both as `cross_repo_targets`, so a
GENUINE cross-repo dependency edge is expressible. Two rules apply and both have
already cost work in this fleet: never file thread membership as a `depends_on`
edge (it makes the item permanently undispatchable with `not in the ready set`),
and check that the consuming repo's `cross_repo_targets` actually lists the
sibling before adding a real edge, because an unresolvable sibling fails CLOSED
forever.

## Deliberate non-membership

Anything whose "done" is a change to `overseerd`'s supervision behavior belongs to
`plan/supervision-safety-and-attention-truth`. Anything whose "done" is a corrected
local check or test belongs to `plan/test-and-gate-integrity`.

## Ordering note for the first implementer

`overseer-af9` first: it hard-stops every spec-side operation from any
plugin-shipping repo, so it is both the widest blast radius and a blocker on the
lifecycle skills this thread's own follow-up work needs. `overseer-6pn` and
`overseer-l0f` are a natural pair -- the unguarded janitor pull and the tracked
file that reliably dirties the checkout are two halves of one fleet-wide dispatch
outage.
