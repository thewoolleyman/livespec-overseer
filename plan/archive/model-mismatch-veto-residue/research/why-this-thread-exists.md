# The model-preserving-restart veto's residue, after its thread archived incomplete

Opening research note for `plan/model-mismatch-veto-residue`, written by the
`livespec-overseer-grooming` drain pass on 2026-08-23T08:4xZ.

## Why this thread exists

Plan thread `model-preserving-restarts` (ledger anchor `overseer-bc55wx`) reached its archive gate and
its independent leg-2 review returned **INCOMPLETE** (evidence-id
`leg2-independent-review-2026-08-23T04:12Z`). Its owning session did the right thing with that verdict:
it filed four real successor carriers rather than an implicit deferral, and it filed them
deliberately UNPARENTED, because a parent-child child of `overseer-bc55wx` would have been an
undisposed child and would have re-blocked the very archive gate they exist to unblock. Each carrier
names the thread, and the epic's archive record names each carrier, so they are reachable from both
ends.

That was correct filing and it left a real gap: four live rows, one subject, no thread, no driver, and
no next action. This thread is the home. **It does not re-open `overseer-bc55wx`, does not re-parent
anything to it, and does not disturb its archive** -- these rows become children of a NEW anchor, which
is a different parent entirely and re-blocks no gate.

## The population

| item | status | the residual |
|---|---|---|
| `overseer-5a4q` | blocked | shipped `model_profile` rows carry a FOURTH key the ratified contract forbids, and the key is load-bearing for the mismatch veto |
| `overseer-0y69` | blocked | the pending `launch-profile-records-the-launch-model` proposal is neither ratified nor withdrawn, and acceptance property (3) silently depends on it |
| `overseer-qrfv` | ready | the Codex wrapper arm silently drops the recorded model, and no test can catch it because the fabrication moved into the env |
| `overseer-lnmgik` | pending-approval | the LIVE EXERCISE of the mismatch veto across BOTH harnesses, whose trigger landed with no successor |

## The one thing a reader must not get wrong

**`overseer-0y69` is spec-tier and its decision-maker is the maintainer.** Its acceptance is that the
pending proposal is RATIFIED into a spec revision or explicitly WITHDRAWN with the reason recorded.
Neither outcome is available to a factory run: `scripts/check-no-factory-spec-edits.sh` is a hard,
no-escape-hatch gate rejecting any factory-authored commit touching `SPECIFICATION/`. Do not dispatch
it, and do not fold it into a sibling's scope to make that sibling "complete".

It is also the row the other three are shaped around, which is why it is worth naming first. While the
proposal sits pending, the shipped code conforms to the NARROWED guarantee and the live specification
states the UN-NARROWED one, so acceptance property (3) cannot be certified against the spec as
written. `overseer-5a4q`'s forbidden fourth key is a divergence measured against that same
un-narrowed text. Ratifying or withdrawing the proposal does not close `overseer-5a4q`, but it decides
which text `overseer-5a4q` is a divergence FROM.

## Tiers, so nothing is dispatched that cannot be satisfied

- `overseer-0y69` -- spec-tier. Maintainer decision. Never dispatchable.
- `overseer-5a4q` -- read the row before tiering it; whether it is a code fix or a spec reconciliation
  depends on the outcome of `overseer-0y69`.
- `overseer-qrfv` -- the row states dispatch-safe conditionally. Read its own qualifier.
- `overseer-lnmgik` -- a LIVE EXERCISE across both harnesses. Host-tier by construction: a sandboxed
  agent has no live harness pair to exercise and cannot manufacture the observation honestly.

Three of the four are therefore not ordinary factory work, which is the single most important fact
about this thread and the reason it is small.

## Read first

- `plan/archive/model-preserving-restarts/` -- the predecessor thread and its research.
- The leg-2 review evidence on `overseer-bc55wx` (`leg2-independent-review-2026-08-23T04:12Z`).
- `SPECIFICATION/proposed_changes/launch-profile-records-the-launch-model.md` -- the pending proposal.
- `SPECIFICATION/spec.md` clauses (i) and (ii) of the launch-profile section, ratified v018.
