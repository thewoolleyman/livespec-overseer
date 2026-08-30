# The statusline-mismatch veto wedges an unblocked worker: incident and fix shape

Filed 2026-08-30 from a live incident on 2026-08-29 (track
`/data/projects/livespec-console-beads-fabro::test-adequacy-gates`, daemon
instance 6afcf5efb4b64cf38bcf40658cc69921). Full evidence is recorded on
`overseer-lnmgik` (comment stamped 2026-08-30T02:45:34Z); this note carries the
mechanism and the fix shape.

## What happened

The worker declared `ready` twice. Both times the daemon vetoed the restart
with `statusline-model-mismatch` -- recorded baseline 'Opus 5 (1M context)',
rendered 'Opus 4.8 (1M context)' -- "skipping restart and keeping the ready
declaration", re-alerting EVERY TICK (149 lines, 18:07:50Z-19:08:06Z). Each
kept declaration then aged past the 30-minute `READY_ARM_MAX_AGE` and EXPIRED
uncollected (18:37:41Z age 1816s; 19:08:30Z age 1806s). An unblocked worker
was stranded for hours and had to be manually wound down at 02:36:15Z.

## Why it was permanent, not transient

1. The mapping row's profile was INTERNALLY INCONSISTENT: model id
   `claude-opus-4-8[1m]` beside statusline baseline 'Opus 5 (1M context)'.
   Every profile-preserving restart re-asserts the model id, whose fresh
   session renders 'Opus 4.8 (1M context)' -- guaranteed to disagree with the
   recorded baseline forever.
2. `_supervisor_launch_profile_refresh._with_statusline_baseline` PRESERVES a
   stored baseline whenever one exists (by design: the baseline is "the
   original model" so silent conversions are detectable). A wrong baseline
   therefore never converges on reality; there is no repair path in shipped
   code. The row was hand-repaired 2026-08-30T02:44Z via
   `registry.record_model_profile`.
3. The veto (`_supervisor_statusline_model.restart_blocked_by_statusline_mismatch`)
   is RATIFIED surface-and-skip behavior (see `overseer-5a4q`), and it behaved
   as ratified. The defect is the SYSTEM: veto-hold times ready-expiry converts
   "surface and hold" into "silently expire the worker's declaration", and the
   per-tick alert repetition violates the edge-trigger discipline
   (`overseer/AGENTS.md` invariant 10) so the history buries the signal.

## The fix, two carriers

- **Baseline honesty at round open.** When a wrap-up round opens, the pane's
  rendered model is authoritative -- nothing has been restarted yet, so
  whatever the session runs is what operator/enforcement authority left it
  running. Re-baseline `statusline_model` from the live render at round open
  (surfacing the change once when it differs from the stored value), so the
  veto guards exactly the window it can reason about: round-open to ready.
  A permanently-wrong inherited baseline becomes impossible. CONFORMANCE
  CHECK REQUIRED: `SPECIFICATION/contracts.md`'s stale-profile clause governs
  the veto's surface-and-skip; if the contract also pins baseline PROVENANCE
  (adoption-time vs round-open), stop and surface instead of implementing --
  do not let a factory or worker commit touch SPECIFICATION/.
- **A daemon-held veto must not eat the arm window.** While the daemon itself
  is what refuses the restart, the kept declaration must not expire at the
  30-minute max age with only per-tick log lines to show for it: skip (or
  pause) expiry for a declaration held by an active mismatch veto, and make
  the mismatch alert edge-triggered (once per episode, re-armed when the
  disagreement clears) per invariant 10. The cardinal rule is untouched:
  the veto still never restarts on a mismatch; only bookkeeping and alerting
  change.

## Coordination

- `plan/model-mismatch-veto-residue` owns this subsystem's spec/contract
  residue: `overseer-5a4q` (statusline_model key vs contracts.md, spec-tier),
  `overseer-0y69` (pending launch-profile-records-the-launch-model proposal,
  maintainer decision), `overseer-qrfv` (codex wrapper arm),
  `overseer-lnmgik` (live exercise -- Claude arm now answered by this
  incident's evidence; Codex arm still open). This thread deliberately
  decides NOTHING those rows own: which value the record canonically holds is
  `overseer-0y69`; the key's spec legality is `overseer-5a4q`.
- Maintainer-directed 2026-08-30: this plan's children are worked
  INTERACTIVELY in a supervised worker, immediately -- factory dispatch is not
  the route for this thread.
