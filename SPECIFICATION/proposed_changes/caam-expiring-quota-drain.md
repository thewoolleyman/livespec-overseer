---
topic: caam-expiring-quota-drain
author: claude-opus-5-5
created_at: 2026-10-13T09:56:10Z
---

## Proposal: Expiring-quota drain trigger for scheduled passes

### Target specification files

- SPECIFICATION/spec.md
- SPECIFICATION/scenarios.md

### Summary

Adds a lowest-precedence rotation trigger to spec.md §"Account rotation and quota supervision": a scheduled pass with no other trigger fired MUST rotate to a live-verified candidate whose weekly window resets strictly sooner than the active account's, provided that candidate clears every threshold that could immediately push it back off by the existing eligibility margin — its weekly remaining at least the margin above the weekly reserve, and its short-window allowance at least the margin clear of the rotation threshold. The trigger introduces no new configuration: no horizon, no minimum-quota setting, no account-to-account gap. It relaxes no floor or disqualifier, cannot oscillate, bounds the short-window return loop to the provider's own short-window cycle without assuming its length, and names its reason in the switch report. The section also records that ranking does not weight plan capacity. Five scenarios cover rotate, hold, no-reversal, the weekly buffer and the short-window buffer.

### Motivation

On 2026-10-12 (host hp) account anthropic-2 (Max 20x) held 79-80% of its weekly allowance resetting in under 12 hours while the loop sat on anthropic-0 (weekly 41% falling to 16%, resetting in 3d 17h) and printed `hold` on every pass for eleven hours. The quota lapsed unused unless the operator switched by hand, which the Reporting clause forbids the caller to do. Root cause (verified in overseer/caam_anthropic_decide.py `decide`): candidate ranking — which already orders by soonest weekly reset so that 'the most perishable balance is spent first' — is reached only after one of the existing triggers fires, so it cannot act on a healthy active account. contracts.md §"The account-rotation operation" **Mode resolution** says a scheduled pass MUST respect the rotation triggers, so the remedy is a new trigger (work item overseer-4oavgh, plan caam-expiring-quota-drain; code half overseer-pk5itu).

Design choices settled with the maintainer on 2026-10-13. A fixed horizon (first suggested as 12h) was rejected: at the incident's observed burn of about 2.3 weekly points per hour, 79% needed roughly 34 hours, so a 12h horizon would have caught the account and still let most of it lapse; and spending a sooner-resetting balance first is never worse, because the later-resetting balance keeps. A separate minimum-quota setting and an account-to-account balance gap were rejected as extra configuration that either blocks valuable drains (a 75% active account against an 80% candidate resetting in three hours) or does not address flapping. Flapping is the cost that matters: with Claude a switch to another organization forfeits every live session's prompt cache, so each switch re-reads all context. The rule therefore reuses the existing eligibility margin as a buffer from each threshold, so every drain lands on an account no threshold can push straight back off, and the rule must hold for providers whose short window is not five hours or not a fixed-reset window. Two switches per short-window cycle while a balance drains is acceptable to the maintainer; constant switching is not. Ranking without capacity weighting is recorded because on 2026-10-12 a Pro account chosen by reset time drained from 100% to 7% in thirty minutes and the question was routed here.

A second link of the incident — at 11:45Z the loop rejected anthropic-2 because its five-hour window read 8% remaining four minutes before it reset — is deliberately NOT addressed by projecting a near-reset window as replenished. Projecting over the schedule interval (30 minutes) could move the fleet onto a nearly-spent window up to half an hour early and stall every session on a rate limit, and a shorter interval would need a setting of its own. The drain trigger already closes that case without either: once the window resets, the next scheduled pass finds the account clear of every threshold with a sooner weekly reset and drains onto it, so the cost is at most one pass on the second-best account.

### Proposed Changes

In SPECIFICATION/spec.md §"Account rotation and quota supervision", insert the following paragraphs immediately AFTER the **Rotation triggers.** paragraph:

**Expiring weekly quota MUST be drained.** Leaving weekly allowance unspent forfeits it permanently at that window's reset, and the soonest-weekly-reset ranking below can spend the most perishable balance first only once some trigger fires. An invocation carrying the scheduled marker MUST therefore also rotate when NO other trigger in this section has fired and at least one DRAIN CANDIDATE exists. A DRAIN CANDIDATE is a candidate that (a) is live-verified per the clause below; (b) survives the zero-weekly disqualifier, the cannot-serve-immediately disqualifier, the weekly-reserve exclusion and its own protection floor, exactly as for any other trigger; (c) has a readable weekly reset that is strictly sooner than the active account's weekly reset; (d) holds weekly remaining at least the eligibility margin above the weekly reserve; and (e) holds a short-window allowance at least the eligibility margin clear of the short-window rotation threshold. Conditions (d) and (e) reuse the configurable margin of **Eligibility** as a buffer from each threshold, and the drain trigger MUST NOT introduce any configuration of its own: no horizon on how soon the candidate's reset must fall, no minimum weekly quota other than the buffer in (d), and no required gap between the candidate's balance and the active account's. Where the active account's weekly reset cannot be read, the drain trigger MUST NOT fire, because no candidate can be shown to reset sooner. Where an operator pin names the scoped model and the active account is above the scoped-model reserve, a drain candidate MUST additionally hold the scoped allowance above that reserve, so that draining never makes a satisfiable pin unsatisfiable.

The drain trigger MUST be the lowest-precedence trigger: where the short-window threshold, the weekly reserve, a protection floor or the scoped-model reserve fires on the same pass, that trigger and its comparison dimension MUST govern and the drain rule MUST NOT apply. Under the drain trigger the comparison dimension is weekly reset time rather than headroom, so the relative-headroom comparison against the active account in **Eligibility** MUST NOT apply to a drain candidate; conditions (d) and (e) apply the same margin against thresholds instead. The drain trigger MUST NOT relax the weekly reserve, any per-account protection floor, the zero-weekly disqualifier or the live-verification rule. Among drain candidates the **Ranking** clause MUST govern unchanged. The drain trigger MUST NOT fire on an invocation without the scheduled marker; such an invocation already rotates under **Mode resolution**.

The drain trigger MUST NOT flap. It moves only to an account whose weekly reset is strictly sooner than the active account's, which is a strict order on reset times, so it can never move back until a weekly window resets and the order itself changes; a pass that has just rotated for expiring quota therefore holds on the next pass while the new account remains clear of every other threshold. Conditions (d) and (e) ensure that a drain never lands on an account that another trigger would move off at the next pass. Where a short-window trigger has moved the operation off a drained account, condition (e) keeps that account ineligible as a drain candidate until its short window is again a full margin clear of the threshold — for a provider whose short window resets at a fixed time, at that reset; for one whose window replenishes gradually, only once usage has fallen a full margin below the line, never as soon as it dips beneath it. The drain therefore causes at most one return to a given account per short-window cycle of that account's provider, without the operation assuming the length of that cycle, and the return loop ends once the account's weekly remaining falls below the buffer in (d) or its weekly reset passes.

A switch made under the drain trigger MUST be reported as such: the switch line MUST name expiring weekly quota as the reason and MUST state the destination's remaining weekly percentage and the time until its weekly reset.

In the same section, append to the **Ranking.** paragraph:

Ranking MUST NOT weight a candidate by its plan capacity or rate-limit tier. Soonest weekly reset is the only perishability order the operation can defend, and every trigger already bounds how far a small account is spent before the operation moves on; a capacity weight would systematically leave a smaller account's perishable balance to lapse.

In SPECIFICATION/scenarios.md, append these scenarios:

## Scenario: A scheduled pass drains weekly quota that resets sooner

Given the active account is clear of every rotation threshold

And a live-verified candidate's weekly window resets sooner than the active account's

And that candidate is at least the eligibility margin clear of the weekly reserve and of the short-window rotation threshold

When a scheduled pass runs

Then the operation switches onto that candidate

And the switch line names expiring weekly quota as the reason, with the candidate's remaining weekly percentage and its time to reset

## Scenario: A scheduled pass holds when no candidate's weekly window resets sooner

Given the active account is clear of every rotation threshold

And every live-verified candidate's weekly window resets later than the active account's

When a scheduled pass runs

Then the operation holds on the active account

## Scenario: A drain rotation does not reverse on the next pass

Given a scheduled pass has just switched onto an account under the drain trigger

And that account remains clear of every rotation threshold

When the next scheduled pass runs

Then the operation holds on that account

## Scenario: A candidate within the margin of the weekly reserve does not attract a drain

Given the active account is clear of every rotation threshold

And the only candidate whose weekly window resets sooner holds weekly remaining less than the eligibility margin above the weekly reserve

When a scheduled pass runs

Then the operation holds on the active account

## Scenario: An account left on its short window is not drained back until it is a margin clear

Given a short-window trigger has just moved the operation off an account whose weekly window resets sooner than the new active account's

And that account's short-window allowance is below the margin clear of the rotation threshold

When a scheduled pass runs

Then the operation holds on the active account

Co-edit tests/heading-coverage.json (outside the spec target) with one entry per new scenario heading, each carrying `"test": "TODO"`, `"work_item": "overseer-pk5itu"` and a reason stating that an integration-tier test over the shipped rotation pass is owed and that work item owns landing it.
