# Respect operator-set per-session models: caam must leave a non-default model alone

Maintainer ruling, 2026-08-30, verbatim: "UNLESS WE ARE OUT OF FABLE QUOTA,
if I have a session set to a NON-DEFAULT/NON-AUTO-ASSIGNED model, LEAVE IT
ALONE."

## The behavior today, and why it violates the ruling

`overseer/caam_sessions.enforce_session_models` computes ONE wanted model for
the foreman population and drives the /model picker into ANY pane whose
observed model differs (or reads unknown). An operator who deliberately sets a
session to a non-default model (e.g. flips the foreman to Opus 5 1M for a
long-context task) is yanked back on the next enforcement pass. This was
observed live: the foreman transcript carries dozens of forced "Set model to
Fable 5" entries interleaved with the operator's own picks.

The code already names this gap: `caam_foreman_override.scoped_model_pinned`'s
docstring says per-session model exceptions are "a separate, currently
unspecified surface" whose decision "is left to a follow-up proposal". This
plan IS that follow-up, with the maintainer's ruling as its direction.

## The rule to implement

1. An operator-set, non-default, non-enforcement-assigned per-session model is
   AUTHORITATIVE: enforcement must not re-drive that session to the enforced
   model.
2. The single exception: the Fable (scoped) allowance being spent/unavailable
   on the active account -- then enforcement may move sessions off a model
   that would block them, exactly as it does today for the pinned-model
   warning path.
3. Distinguishing operator-set from enforcement-set is feasible from caam's
   own durable state: `_record_model_set` already records which session
   enforcement itself set, and to what, with a timestamp. A session whose
   observed model differs from both the enforced want AND the last
   enforcement-set record is operator-set. An unknown (None) observed model
   is NOT evidence of an operator choice and must not be treated as one.

## Tiering -- do not file this as one item

- The enforcement contract lives in `SPECIFICATION/spec.md` (operator-pin
  clause, scoped-model clause, rotation triggers) and currently specifies a
  GLOBAL foreman pin only. The per-session respect rule is a spec-tier
  change: route through /livespec:propose-change, decided by the maintainer
  (whose 2026-08-30 ruling above is the direction). Factory and worker
  commits must never touch SPECIFICATION/.
- The implementation is an ordinary stdlib-only change in
  `caam_sessions.py` / `caam_enforcement*.py` with beside-tests, filed
  separately and sequenced AFTER the spec revision lands.

## Coordination -- two in-flight tracks touch the same functions

- `plan/caam-anthropic-loop` is a LIVE plan thread; this thread does not
  reopen or amend it -- it adds a sibling behavior change to the same
  operation.
- `plan/caam-model-set-idempotence` (epic `overseer-o3t75c`) is IN FLIGHT:
  its child `overseer-o3t75c.1` (picker no-op when the wanted model is
  already set; unknown-read handling) was dispatched to the factory on
  2026-08-30 and edits `enforce_session_models` and `drive_model_picker`.
  This plan's implementation child must land AFTER it and rebase on its
  result; the two compose (idempotence stops re-setting an already-correct
  model; this thread stops overriding a deliberately-different one).

## Deferral noted at filing

Daemon-restart model preservation (a restart relaunching a session on a
model other than the one the operator left it on) is the launch-profile
subsystem's concern, already governed by the model-preserving-restarts
lineage and `plan/model-mismatch-veto-residue` -- out of scope here.
