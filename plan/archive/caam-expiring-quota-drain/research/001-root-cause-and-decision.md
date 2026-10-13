# caam-expiring-quota-drain — root cause and decision (2026-10-12)

## What the operator saw

`anthropic-2` (Max 20x) held 79–80% weekly resetting in under 12 hours, with a full
5-hour window, while the loop sat on `anthropic-0` (weekly 41% falling to 16%,
resetting in 3d 17h). Every pass printed `hold`. The quota on `anthropic-2` was
going to lapse unused unless the operator switched by hand, which the operation
contract tells the caller not to do.

The operator's position, and it is correct: this should have been done by the
loop, not offered.

## Root cause — three links, each verified in the code

1. **The optimising step is unreachable on a healthy account.**
   `overseer/caam_anthropic_decide.py` `decide` returns `hold_allowed` whenever
   `triggered()` is false. Candidate selection (`eligible_profiles` →
   `rank_profiles`, which already orders by soonest weekly reset) runs only after
   a trigger fires. The loop is a threshold-escape mechanism with no pass that
   asks "is there a better use of quota right now". The rule "spend the quota that
   expires first" exists and cannot act.

2. **A near-reset window is judged on its snapshot.** At 11:45Z the loop was
   leaving the drained Pro account and `anthropic-2` was the right destination.
   `is_eligible` (`caam_decision_protection.py`) demanded a ≥10-point five-hour
   margin measured on the snapshot. `anthropic-2` read 8% because that window was
   four minutes from resetting, so it failed the margin and the loop took
   `anthropic-0`.

3. **Nothing re-evaluates afterwards.** `anthropic-2`'s window reset five minutes
   later. From then on `anthropic-0` stayed above every threshold, so every pass
   held for the next eleven hours.

## Why this is two work items, not one

`SPECIFICATION/contracts.md`, account-rotation "Mode resolution": a scheduled pass
**MUST respect the rotation triggers**. Draining expiring quota onto a healthy
account is a new trigger, so it is a specification change. The factory is barred
from editing `SPECIFICATION/` (`scripts/check-no-factory-spec-edits.sh`), and a
mixed-tier item cannot be dispatched, so:

- `overseer-4oavgh` — spec: ratify the trigger (maintainer, `propose-change`).
- `overseer-pk5itu` — code: implement it. Blocked on the spec item.

## Proposed rule (for the maintainer to ratify or amend in the spec item)

A scheduled pass also rotates when a live-verified eligible candidate's weekly
window resets sooner than the active account's and within a horizon (suggest 12h),
and that candidate has at least a minimum weekly quota left (suggest 30%).

**No-oscillation argument.** The move is strictly toward a *sooner* weekly reset,
which is a strict order on reset times; the reverse move can never qualify. This is
the same shape of argument `is_eligible` already documents for its antisymmetric
margin.

**Precedence.** Spend-cap, protected-account, scoped-model and weekly-reserve
rules keep priority over the drain.

**Near-reset window.** A candidate whose five-hour window resets within a few
minutes is measured at its projected post-reset balance (link 2).

## Related defect, deliberately not in this plan's code item

`rank_profiles` is capacity-blind. At 11:15Z it ranked the Pro account
(`anthropic-3`, weekly resets 3d 12h) ahead of the Max 20x account
(`anthropic-0`, 3d 17h) on reset time alone; the factory then took it from 100% to
7% in thirty minutes. Whether to weight by plan tier is a policy question, so it is
recorded as a decision the spec item must make, not silently decided in code.

## Not in this plan

- Reviving `anthropic-4` (needs a browser login; the operator chose to leave it
  dark).
- The `spend_capped` fixes, which shipped under `caam-spend-cap-servability`.
