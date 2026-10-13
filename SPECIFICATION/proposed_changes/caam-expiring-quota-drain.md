---
topic: caam-expiring-quota-drain
author: claude-opus-5-5
created_at: 2026-10-13T08:57:27Z
---

## Proposal: Expiring-quota drain trigger for scheduled passes

### Target specification files

- SPECIFICATION/spec.md
- SPECIFICATION/scenarios.md

### Summary

Adds a fifth rotation trigger to spec.md §"Account rotation and quota supervision": a scheduled pass on a healthy active account MUST rotate to a live-verified, otherwise-eligible candidate whose weekly window resets strictly sooner than the active account's and within a configurable horizon, while that candidate still holds at least a configurable minimum of its weekly allowance. The trigger is the lowest-precedence trigger, waives only the relative-headroom margin (its comparison dimension is weekly reset time, not headroom), relaxes no floor or disqualifier, cannot oscillate, and names its reason in the switch report. The section also records the decision that candidate ranking does not weight plan capacity. Four scenarios cover rotate, hold, no-reversal and the minimum-quota bound.

### Motivation

On 2026-10-12 (host hp) account anthropic-2 (Max 20x) held 79-80% of its weekly allowance resetting in under 12 hours while the loop sat on anthropic-0 (weekly 41% falling to 16%, resetting in 3d 17h) and printed `hold` on every pass for eleven hours. The quota lapsed unused unless the operator switched by hand, which the Reporting clause forbids the caller to do. Root cause (verified in overseer/caam_anthropic_decide.py `decide`): candidate ranking — which already orders by soonest weekly reset so that 'the most perishable balance is spent first' — is reached only after one of the four existing triggers fires, so the ranking rule cannot act on a healthy active account. contracts.md §"The account-rotation operation" **Mode resolution** says a scheduled pass MUST respect the rotation triggers, so the remedy is a new trigger, which is a specification change (work item overseer-4oavgh, plan caam-expiring-quota-drain; the code half is overseer-pk5itu). The capacity-weighting decision is recorded because on the same day ranking by reset time alone chose a Pro account for a factory workload, which drained from 100% to 7% in thirty minutes; the question was explicitly routed to this specification change.

### Proposed Changes

In SPECIFICATION/spec.md §"Account rotation and quota supervision", insert the following paragraph immediately AFTER the **Rotation triggers.** paragraph:

**Expiring weekly quota MUST be drained.** Leaving weekly allowance unspent forfeits it permanently at that window's reset, and the soonest-weekly-reset ranking below can spend the most perishable balance first only once some trigger fires. An invocation carrying the scheduled marker MUST therefore also rotate when NO other trigger in this section has fired and at least one DRAIN CANDIDATE exists. A DRAIN CANDIDATE is a candidate that (a) is live-verified per the clause below; (b) survives the zero-weekly disqualifier, the cannot-serve-immediately disqualifier, the weekly-reserve exclusion and its own protection floor, exactly as for any other trigger; (c) has a readable weekly reset that is strictly sooner than the active account's weekly reset AND no later than a configurable DRAIN HORIZON from now; (d) holds at least a configurable MINIMUM DRAIN QUOTA of its weekly allowance remaining; and (e) holds a short-window allowance below the rotation threshold, so that the operation never moves onto an account it would immediately have to leave. The drain horizon's default SHOULD be twelve hours and the minimum drain quota's default SHOULD be thirty percent of the weekly allowance. Where the active account's weekly reset cannot be read, the drain trigger MUST NOT fire, because no candidate can be shown to reset sooner. Where an operator pin names the scoped model and the active account is above the scoped-model reserve, a drain candidate MUST additionally hold the scoped allowance above that reserve, so that draining never makes a satisfiable pin unsatisfiable.

The drain trigger MUST be the lowest-precedence trigger: where the short-window threshold, the weekly reserve, a protection floor or the scoped-model reserve fires on the same pass, that trigger and its comparison dimension MUST govern and the drain rule MUST NOT apply. Under the drain trigger the comparison dimension is weekly reset time rather than headroom, so the relative-headroom margin of **Eligibility** MUST NOT apply to a drain candidate; this is the only rule the drain trigger relaxes, and it MUST NOT relax the weekly reserve, any per-account protection floor, the zero-weekly disqualifier or the live-verification rule. Among drain candidates the **Ranking** clause MUST govern unchanged. The drain trigger MUST NOT fire on an invocation without the scheduled marker; such an invocation already rotates under **Mode resolution**.

The drain trigger cannot oscillate: it moves only to an account whose weekly reset is strictly sooner than the active account's, which is a strict order on reset times, so the reverse move can never qualify until a weekly window resets and the order itself changes. A pass that has just rotated for expiring quota MUST therefore hold on the next pass while the new account remains above every other threshold.

A switch made under the drain trigger MUST be reported as such: the switch line MUST name expiring weekly quota as the reason and MUST state the destination's remaining weekly percentage and the time until its weekly reset.

In the same section, append to the **Ranking.** paragraph:

Ranking MUST NOT weight a candidate by its plan capacity or rate-limit tier. Soonest weekly reset is the only perishability order the operation can defend, and every trigger already bounds how far a small account is spent before the operation moves on; a capacity weight would systematically leave a smaller account's perishable balance to lapse.

In SPECIFICATION/scenarios.md, append these scenarios:

## Scenario: A scheduled pass drains weekly quota that resets sooner

Given the active account is above every rotation threshold

And a live-verified candidate's weekly window resets sooner than the active account's and within the drain horizon

And that candidate holds at least the minimum drain quota of its weekly allowance

When a scheduled pass runs

Then the operation switches onto that candidate

And the switch line names expiring weekly quota as the reason, with the candidate's remaining weekly percentage and its time to reset

## Scenario: A scheduled pass holds when no candidate's weekly window resets sooner

Given the active account is above every rotation threshold

And every live-verified candidate's weekly window resets later than the active account's

When a scheduled pass runs

Then the operation holds on the active account

## Scenario: A drain rotation does not reverse on the next pass

Given a scheduled pass has just switched onto an account under the drain trigger

And that account remains above every rotation threshold

When the next scheduled pass runs

Then the operation holds on that account

## Scenario: A candidate below the minimum drain quota does not trigger a drain

Given the active account is above every rotation threshold

And the only candidate whose weekly window resets sooner holds less than the minimum drain quota of its weekly allowance

When a scheduled pass runs

Then the operation holds on the active account

Co-edit tests/heading-coverage.json (outside the spec target) with one entry per new scenario heading, each carrying `"test": "TODO"`, `"work_item": "overseer-pk5itu"` and a reason naming the integration-tier test that work item owns over the shipped rotation pass.

## Proposal: A candidate's near-reset short window is judged on its replenished balance

### Target specification files

- SPECIFICATION/spec.md
- SPECIFICATION/scenarios.md

### Summary

Adds a rule to the **Eligibility** clause: when a candidate's short-window allowance resets within a configurable projection interval, eligibility MUST measure that window at its replenished post-reset balance instead of its snapshot reading. The rule applies to candidates only, under every trigger, and adds one scenario.

### Motivation

On 2026-10-12 at 11:45Z the loop was leaving a drained Pro account and anthropic-2 was the right destination. Eligibility (overseer/caam_decision_protection.py `is_eligible`) demanded a 10-point short-window margin measured on the snapshot; anthropic-2's five-hour window read 8% remaining because it was four minutes from resetting, so it failed the margin and the loop took anthropic-0 instead. The window reset five minutes later, but no trigger re-evaluated the choice for eleven hours. A balance about to replenish was treated as if it would stay at its snapshot value. Part of work item overseer-4oavgh (plan caam-expiring-quota-drain); the code half is overseer-pk5itu.

### Proposed Changes

In SPECIFICATION/spec.md §"Account rotation and quota supervision", append to the **Eligibility.** paragraph:

A candidate whose short-window allowance resets within a configurable PROJECTION INTERVAL MUST be measured, for every eligibility and drain-candidate test in this section, at its projected post-reset balance — a fully replenished short window — rather than at its snapshot reading, because a window about to reset is not about to stay at its snapshot value. The projection interval's default SHOULD be ten minutes, and a configured value of zero MUST restore pure snapshot measurement. The projection MUST apply to candidates only: it MUST NOT suppress or arm a trigger on the active account, and it MUST NOT apply to a candidate whose short-window reset time cannot be read.

In SPECIFICATION/scenarios.md, append:

## Scenario: A candidate whose short window is about to reset is judged on its replenished balance

Given the active account has crossed its short-window rotation threshold

And a live-verified candidate's short-window snapshot reads nearly spent

And that candidate's short window resets within the projection interval

When a scheduled pass evaluates eligibility

Then the candidate is measured at a fully replenished short window

And the operation MAY switch onto it

Co-edit tests/heading-coverage.json (outside the spec target) with one entry for this scenario heading carrying `"test": "TODO"`, `"work_item": "overseer-pk5itu"` and a reason naming the integration-tier test that work item owns.
