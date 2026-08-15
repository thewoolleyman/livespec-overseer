# Supervisor Handoff - make-supervisors-reliable (reopened)

Updated: 2026-08-15T07:56:05Z

## Why this file exists again

The original plan/make-supervisors-reliable/ (epic `overseer-ocj2yi`) shipped
its deliverable — the supervisor completion gate, SPECIFICATION v013 — and was
correctly archived to `plan/archive/make-supervisors-reliable/` on 2026-08-14.
Do not reopen or treat that archived plan as unfinished; it is done.

This session's worker/supervisor tmux pair kept being used afterward for
genuinely unrelated follow-on work discovered while rechecking that plan's own
shipped fix. That is not a bare-work-item situation — it was actively driven
under a named supervisor/overseer pair, which requires a live plan for the
daemon's registry mapping, discovery, and GC (`archived_or_gone`) to track it
at all. Without one, the daemon GC'd the stale mapping row and both sessions
fell off its board entirely (confirmed directly: empty registry row, empty
daemon board for this topic, 2026-08-15 ~06:50Z).

Fix: reopened the plan under the SAME topic slug — `archived_or_gone()`
explicitly supports an active `plan/<topic>` winning over a same-named archive
copy, so no tmux session renaming was needed. New epic: **`overseer-cvyfzo`**.
Landed via worktree -> PR #941 -> merge (not a raw primary-checkout edit); the
registry mapping row was also hand-patched directly so daemon tracking resumed
immediately rather than waiting on the PR.

## Current state, as of this handoff

Two things still in flight, neither done:

1. **PR #941** (this reopening itself): open, CI running, not yet merged.
   `mergeable_state: blocked` as of 07:56Z. Re-measure before assuming
   landed: `gh api repos/thewoolleyman/livespec-overseer/pulls/941`.

2. **`overseer-8pwc`** (P0): "overseer-2vg1's ledger-epic fallback calls bare
   `bd` with no credential wrapper, so it silently fails and returns None in
   the real daemon process." Dispatched to the factory (fabro run
   `01M0266TN9HD`), running ~8min as of 07:56Z, not yet terminal. Do NOT
   re-dispatch while this run exists — check `fabro ps -a` first.

   **The verification requirement on this item is the whole point of it and
   must not be skimmed**: its acceptance criteria require the live proof to
   simulate the daemon's OWN bare environment (no `BEADS_*`/`DOLT_*` vars, no
   `with-livespec-env.sh` wrapping the outer invocation). A proof run under
   the credential wrapper does NOT satisfy it — that exact false-positive is
   what produced this item. Check `/proc/<overseerd-pid>/environ` yourself if
   needed to confirm what a real invocation would see, and re-derive the
   daemon's current pid rather than trusting a cached one (it restarts
   periodically, sometimes on a different pane index — resolve it by process,
   `ps ... | grep bin/overseerd` over every tmux pane, never by pane index).

Also lower-priority, not urgent, not part of `overseer-cvyfzo`'s scope, but
worth a look if there's a lull: `homelab/05-hetzner-fleet-member`'s registry
row still has `epic: null` — unchecked whether it has a resolvable ledger
epic or whether null is legitimate there (as it turned out to be for the
sibling `charter-gate-ratchet` row, already checked and confirmed legitimate).

## Next action for whoever reads this next

1. Re-measure PR #941 and the `overseer-8pwc` fabro run fresh — both are
   claims with timestamps above, not live state.
2. If `overseer-8pwc`'s run has landed a PR, verify its live-proof evidence
   actually exercises the daemon's bare environment before accepting it —
   do not accept the run's own "verified" claim without checking what it
   actually proved.
3. Once both are closed/merged with real evidence, append a summary to epic
   `overseer-cvyfzo`'s ledger timeline through the orchestrator's sanctioned
   plan surface (never a direct ledger write, never editing this file's
   sibling `plan/<topic>/handoff.md` — that's the worker's own separate
   artifact) and assess whether this reopened plan is itself complete and
   ready for its own independent-completeness-review + archive cycle.

## Corrections

- **C1 (2026-08-15)** — I (the supervisor) directly called
  `drive.py --action impl:overseer-8pwc` myself instead of handing it to the
  worker session, violating "supervisor, not implementer" and the
  maintainer's explicit "have the worker drive all work" instruction. Caught
  by the maintainer, not by me. Did not kill the resulting in-flight run
  (killing a dispatch caller doesn't kill the run and just creates the
  documented phantom-claim/collision ambiguity) — instead handed monitoring
  and verification of the already-running fabro run to the worker pane
  going forward. Generalize: when investigating a defect turns up the fix
  shape, STOP and hand off before executing it, even mid-investigation.
- **C2 (2026-08-15)** — I told the maintainer this follow-on work "doesn't
  need a plan/epic wrapper at all" because it was a small standalone bug.
  Wrong: the daemon's tracking model doesn't care how small the work is, it
  cares whether a NAMED supervisor/overseer pair is driving it — and one
  was. Reopening this plan (see above) was the actual fix. Generalize: "is
  this substantively plan-shaped work" is the wrong question when a
  supervised tmux pair is already involved; the right question is "is a
  supervisor/overseer pair actively driving this," and if so it needs a
  live plan regardless of scope.
