# Initial review - make-supervisors-reliable (reopened)

## Why this plan was recreated under the same topic slug

The original plan/make-supervisors-reliable/ (epic overseer-ocj2yi) shipped its
deliverable (the supervisor completion gate, SPECIFICATION v013) and was
correctly archived to plan/archive/make-supervisors-reliable/ on 2026-08-14.

The same tmux worker/supervisor session pair (make-supervisors-reliable /
make-supervisors-reliable-supervisor) kept being used afterward for genuinely
unrelated follow-on work discovered during that supervision cycle. That is not
a bare-work-item situation: it was actively driven under a named
supervisor/overseer pair, which requires a live plan for the daemon's registry
mapping, discovery, and GC (archived_or_gone) to track it correctly. Continuing
without one caused the daemon to GC the stale mapping row and drop both
sessions from its tracking entirely (confirmed empty registry row and empty
daemon board for this topic on 2026-08-15).

This plan reuses the "make-supervisors-reliable" topic slug deliberately -
overseer/_registry_discovery.py's archived_or_gone() explicitly supports an
active plan/<topic> reusing a topic name that also exists under
plan/archive/<topic>, checking the active directory first. No tmux session
renaming is needed; the daemon will re-discover this topic and re-derive the
registry epic on next assignment/tick.

## Scope

Follow-on defects discovered while supervising and rechecking the original
plan's own shipped fix (overseer-2vg1):

- overseer-8pwc (P0, in flight as fabro run 01M0266TN9HD at plan creation
  time): overseer-2vg1's ledger-epic fallback calls bare `bd` with no
  credential wrapper, so it silently fails and returns None in the real daemon
  process (which carries no BEADS_*/DOLT_* env). Must be re-verified against
  the daemon's actual bare environment, not a wrapper-prefixed proof.
- Registry rows with epic: null needing a check (not necessarily a fix - null
  may be legitimate): homelab/05-hetzner-fleet-member,
  livespec-overseer/charter-gate-ratchet.

## Explicit deferral

Do not reopen or reference plan/archive/make-supervisors-reliable/ - that
plan's own deliverable is complete and correctly archived. This plan is scoped
only to the follow-on defect chain above.
