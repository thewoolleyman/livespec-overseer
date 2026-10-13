---
topic: caam-expiring-quota-drain
author: claude-opus-5-5
created_at: 2026-10-13T10:12:07Z
---

## Proposal: Expiring-quota drain trigger for scheduled passes

### Target specification files

- SPECIFICATION/spec.md
- SPECIFICATION/contracts.md
- SPECIFICATION/scenarios.md

### Summary

Adds a lowest-precedence rotation trigger to spec.md §"Account rotation and quota supervision": a scheduled pass with no other trigger fired MUST rotate to a live-verified candidate whose weekly window resets at least one minute sooner than the active account's, provided the candidate is the existing eligibility margin clear of every threshold that could push it straight back off (weekly reserve, its own protection floor, the short-window threshold and, under a scoped pin, the scoped-model reserve) and, if the operation left it on a short-window trigger, that window has since reset. The trigger adds no configuration, preserves the protection ordering, relaxes no floor or disqualifier, and cannot flap for fixed-reset or gradually-replenishing short windows or under jittered reset readings. It amends the two existing sentences that enumerated the margin's exceptions and the scoped allowance's influences, widens the contract's durable-store cost bound to cover the drain's short-window memory, records that ranking does not weight plan capacity, and adds 20 scenarios.

### Motivation

On 2026-10-12 (host hp) account anthropic-2 (Max 20x) held 79-80% of its weekly allowance resetting in under 12 hours while the loop sat on anthropic-0 (weekly 41% falling to 16%, resetting in 3d 17h) and printed `hold` on every pass for eleven hours. The quota lapsed unused unless the operator switched by hand, which the Reporting clause forbids the caller to do. Root cause (verified in overseer/caam_anthropic_decide.py `decide`): candidate ranking — which already orders by soonest weekly reset so that 'the most perishable balance is spent first' — is reached only after one of the existing triggers fires, so it cannot act on a healthy active account. contracts.md §"The account-rotation operation" **Mode resolution** says a scheduled pass MUST respect the rotation triggers, so the remedy is a new trigger (work item overseer-4oavgh, plan caam-expiring-quota-drain; code half overseer-pk5itu).

Design choices settled with the maintainer on 2026-10-13. A fixed horizon (first suggested as 12h) was rejected: at the incident's observed burn of about 2.3 weekly points per hour, 79% needed roughly 34 hours, so a 12h horizon would have caught the account and still let most of it lapse; and spending a sooner-resetting balance first is never worse, because the later-resetting balance keeps. A separate minimum-quota setting and an account-to-account balance gap were rejected as extra configuration that either blocks valuable drains (a 75% active account against an 80% candidate resetting in three hours) or does not address flapping. Flapping is the cost that matters: with Claude a switch to another organization forfeits every live session's prompt cache, so each switch re-reads all context. The rule therefore reuses the existing eligibility margin as a buffer from each threshold, so every drain lands on an account no threshold can push straight back off, and the rule must hold for providers whose short window is not five hours or not a fixed-reset window. Two switches per short-window cycle while a balance drains is acceptable to the maintainer; constant switching is not. Ranking without capacity weighting is recorded because on 2026-10-12 a Pro account chosen by reset time drained from 100% to 7% in thirty minutes and the question was routed here.

A second link of the incident — at 11:45Z the loop rejected anthropic-2 because its five-hour window read 8% remaining four minutes before it reset — is deliberately NOT addressed by projecting a near-reset window as replenished. Projecting over the schedule interval (30 minutes) could move the fleet onto a nearly-spent window up to half an hour early and stall every session on a rate limit, and a shorter interval would need a setting of its own. The drain trigger already closes that case without either: once the window resets, the next scheduled pass finds the account clear of every threshold with a sooner weekly reset and drains onto it, so the cost is at most one pass on the second-best account.

An independent ratification review of the first amended draft found three blockers, all fixed here: the drain's margin waiver and its scoped-pin condition contradicted two unamended sentences ("the one exception" in **Eligibility**, "exactly the three ways" in the scoped-model clause); the claim of at most one return per short-window cycle was false for a provider whose window replenishes gradually, where a margin-clear test alone lets the loop return after every margin's worth of ageing-out; and a drain could move from a healthy unprotected account onto a protected one, against the protection ordering, or land just above a destination's own floor.

A second independent review found three further blockers, fixed here: weekly reset readings jitter at sub-second precision (observed in the operation's own state file, e.g. 2026-08-24T23:59:59.874 vs 2026-08-25T00:00:00.146 for one nominal reset), so two accounts sharing an on-the-hour reset could drain onto each other on nearly every pass — fixed by whole-minute comparison and by never draining back onto an account the drain itself left until a weekly reset of either account has passed, which can never block a legitimate drain because a legitimate reversal requires such a reset anyway; the protected-destination floor test read as subtracting the floor twice; and seven new obligations lacked scenarios.

A third independent review found that truncating to the minute still ordered readings straddling a minute boundary, that the drain-memory condition (g) was stated two ways and could block a legitimate drain, and that four obligations lacked scenarios. Treating readings under a minute apart as one reset makes reversal impossible without an actual weekly reset, so (g) and its stored state were removed rather than repaired.

### Proposed Changes

In SPECIFICATION/spec.md §"Account rotation and quota supervision", make these changes.

1. In the **Eligibility.** paragraph, replace "The scoped-model clause below carves out the one exception to this margin," with "Two clauses carve out exceptions to this margin: the expiring-quota drain above, whose comparison dimension is weekly reset time and which applies the same margin against thresholds instead, and the scoped-model clause below. The scoped-model exception is".

2. In the scoped-model clause, replace "the operation MUST let the scoped allowance influence SELECTION in exactly the three ways below, and MUST NOT let it influence selection in any fourth way." with "the operation MUST let the scoped allowance influence SELECTION in exactly the three ways below and in the drain condition stated under **Expiring weekly quota MUST be drained**, and MUST NOT let it influence selection in any other way."

3. Insert the following paragraphs immediately AFTER the **Rotation triggers.** paragraph:

**Expiring weekly quota MUST be drained.** Leaving weekly allowance unspent forfeits it permanently at that window's reset, and the soonest-weekly-reset ranking below can spend the most perishable balance first only once some trigger fires. An invocation carrying the scheduled marker MUST therefore also rotate when NO other trigger in this section has fired and at least one DRAIN CANDIDATE exists. A DRAIN CANDIDATE is a candidate that (a) is live-verified per the clause below; (b) survives the zero-weekly disqualifier, the cannot-serve-immediately disqualifier and the weekly-reserve exclusion, exactly as for any other trigger; (c) has a readable weekly reset at least one minute sooner than the active account's weekly reset — readings that differ by less than a minute are treated as the same reset, because the provider reports a nominal reset with sub-second jitter that can straddle a minute boundary, and a fixed tolerance of one minute is a property of that reading noise rather than a setting; (d) holds weekly remaining at least the eligibility margin above the weekly reserve and, where it is protected, weekly remaining at least the eligibility margin above its own protection floor; (e) holds a short-window allowance at least the eligibility margin clear of the short-window rotation threshold; (f) where the operation last moved off that account on a short-window trigger, has passed the short-window reset time the provider reported for that account at the moment of the move or, where the provider reported none, has a fully replenished short window — a reported reset time is taken to be the moment that window is fully replenished. A move counts as made on a short-window trigger whenever the short-window threshold was among the triggers that fired on that pass. The operation MUST remember in its durable store each account it moved off on a short-window trigger together with the short-window reset time reported at that moment. Conditions (d) and (e) reuse the configurable margin of **Eligibility** as a buffer from each threshold, and the drain trigger MUST NOT introduce any configuration of its own: no horizon on how soon the candidate's reset must fall, no minimum weekly quota other than the buffer in (d), no required gap between the candidate's balance and the active account's, and no cooldown measured in time. Where the active account's weekly reset cannot be read, the drain trigger MUST NOT fire, because no candidate can be shown to reset sooner. Where an operator pin names the scoped model and the active account is above the scoped-model reserve, a drain candidate MUST additionally hold the scoped allowance at least the eligibility margin above that reserve, so that draining never makes a satisfiable pin unsatisfiable and never lands on an account the scoped-model trigger would move it off at the next pass.

The drain trigger MUST preserve the protection ordering. Because a drain is a voluntary move from an account that need not be left, it MUST NOT move from an unprotected active account onto a protected candidate, and where the active account is protected it MUST NOT select a protected drain candidate while any unprotected drain candidate exists. Within the drain trigger, "eligible" in the protected-account clause means a drain candidate.

The drain trigger MUST be the lowest-precedence trigger: where any other trigger in this section fires on the same pass, that trigger and its comparison dimension MUST govern and the drain rule MUST NOT apply. Under the drain trigger the comparison dimension is weekly reset time rather than headroom, so the relative-headroom comparison against the active account in **Eligibility** MUST NOT apply to a drain candidate; conditions (d) and (e) apply the same margin against thresholds instead. The drain trigger MUST NOT relax the weekly reserve, any per-account protection floor, the zero-weekly disqualifier or the live-verification rule. Among drain candidates the **Ranking** clause MUST govern unchanged, subject to the protection ordering above. The drain trigger MUST NOT fire on an invocation without the scheduled marker; such an invocation already rotates under **Mode resolution**.

The drain trigger MUST NOT flap. It moves only to an account whose weekly reset is at least one minute sooner than the active account's, so jitter in readings of one nominal reset cannot order two accounts, and a move in the reverse direction would require the departed account to reset at least one minute sooner than the destination — which cannot happen until one of their weekly windows actually resets and the order itself changes. No memory of past drains is needed for this. Conditions (d) and (e), and the scoped condition above, keep a drain off any account that the weekly reserve, its own protection floor, the short-window threshold or the scoped-model reserve would move it off at the next pass. Condition (f) bounds the loop in which a short-window trigger moves the operation off a drained account and the drain later returns: the drain MUST NOT return before that account's short window has reset, by the reset time the provider reported or, failing that, by full replenishment, so it causes at most one return to a given account per short-window cycle whether the provider's window resets at a fixed time or replenishes gradually, without the operation assuming the length of that cycle. The return loop ends once the account's weekly remaining falls below the buffer in (d) or its weekly reset passes.

A switch made under the drain trigger MUST be reported as such: the switch line MUST name expiring weekly quota as the reason and MUST state the destination's remaining weekly percentage and the time until its weekly reset.

4. Append to the **Ranking.** paragraph:

Ranking MUST NOT weight a candidate by its plan capacity or rate-limit tier. Soonest weekly reset is the only perishability order the operation can defend, and every trigger already bounds how far a small account is spent before the operation moves on; a capacity weight would systematically leave a smaller account's perishable balance to lapse.

In SPECIFICATION/contracts.md §"The account-rotation operation", in the **Durable store.** paragraph, replace "Concurrent writers MAY overwrite one another, which MUST cost at most a cached reading and MUST NOT be able to corrupt the file." with "Concurrent writers MAY overwrite one another, which MUST cost at most a cached reading, or one premature drain return where the overwritten state was the drain trigger's memory of an account it moved off on a short-window trigger, and MUST NOT be able to corrupt the file."

In SPECIFICATION/scenarios.md, append these scenarios:

## Scenario: A scheduled pass drains weekly quota that resets sooner

Given the active account is unprotected, no operator pin names the scoped model, and the active account is clear of every rotation threshold

And a live-verified, unprotected candidate's weekly window resets sooner than the active account's

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

And no other candidate's weekly window resets sooner than that account's

When the next scheduled pass runs

Then the operation holds on that account

## Scenario: Two accounts sharing a nominal weekly reset do not drain onto each other

Given two accounts report the same nominal weekly reset with readings that differ by less than a minute, including readings on either side of a minute boundary

And the active account is one of them and is clear of every rotation threshold

When scheduled passes run repeatedly

Then the operation does not switch between those two accounts under the drain trigger

## Scenario: A candidate within the margin of the weekly reserve does not attract a drain

Given the active account is clear of every rotation threshold

And the only candidate whose weekly window resets sooner holds weekly remaining less than the eligibility margin above the weekly reserve

When a scheduled pass runs

Then the operation holds on the active account

## Scenario: A candidate within the margin of the short-window threshold does not attract a drain

Given the active account is clear of every rotation threshold

And the only candidate whose weekly window resets sooner holds a short-window allowance less than the eligibility margin clear of the short-window rotation threshold

When a scheduled pass runs

Then the operation holds on the active account

## Scenario: An account left on its short window is not drained back before that window resets

Given a short-window trigger moved the operation off an account whose weekly window resets sooner than the new active account's

And the provider reported a short-window reset time for that account at the moment of the move

And that reset time has not yet passed

When a scheduled pass runs

Then the operation does not switch back onto that account

## Scenario: Without a reported reset, an account left on its short window waits for full replenishment

Given a short-window trigger moved the operation off an account whose weekly window resets sooner than the new active account's

And the provider reported no short-window reset time for that account

And that account's short window is not fully replenished

When a scheduled pass runs

Then the operation does not switch back onto that account

## Scenario: A drain does not move from an unprotected account onto a protected one

Given the active account is unprotected and clear of every rotation threshold

And the only candidate whose weekly window resets sooner is protected

When a scheduled pass runs

Then the operation holds on the active account

## Scenario: A protected drain destination keeps a margin above its own floor

Given the active account is protected and clear of every rotation threshold

And the only candidate whose weekly window resets sooner is protected and holds weekly remaining less than the eligibility margin above its own protection floor

When a scheduled pass runs

Then the operation holds on the active account

## Scenario: A drain keeps a satisfiable scoped pin satisfiable

Given an operator pin names the scoped model and the active account is above the scoped-model reserve

And the only candidate whose weekly window resets sooner holds the scoped allowance less than the eligibility margin above that reserve

When a scheduled pass runs

Then the operation holds on the active account

## Scenario: An unreadable active weekly reset prevents a drain

Given the active account is clear of every rotation threshold

And the active account's weekly reset cannot be read

And a candidate otherwise qualifies as a drain candidate

When a scheduled pass runs

Then the operation holds on the active account

## Scenario: A protected active account drains onto an unprotected candidate before a protected one

Given the active account is protected and clear of every rotation threshold

And two drain candidates reset sooner, one protected with the sooner reset and one unprotected

When a scheduled pass runs

Then the operation switches onto the unprotected candidate

## Scenario: A candidate whose weekly reset cannot be read does not attract a drain

Given the active account is clear of every rotation threshold

And the only other candidate's weekly reset cannot be read

When a scheduled pass runs

Then the operation holds on the active account

## Scenario: A candidate that is not live-verified does not attract a drain

Given the active account is clear of every rotation threshold

And the only candidate whose weekly window resets sooner could not be live-verified during this pass

When a scheduled pass runs

Then the operation holds on the active account

## Scenario: A candidate with no weekly allowance remaining does not attract a drain

Given the active account is clear of every rotation threshold

And the only candidate whose weekly window resets sooner has no weekly allowance remaining

When a scheduled pass runs

Then the operation holds on the active account

## Scenario: A move on several triggers including the short window counts as a short-window move

Given a pass moved the operation off an account on which both the short-window threshold and another trigger fired

And the short-window reset time reported for that account at the move has not yet passed

When a scheduled pass runs

Then the operation does not drain back onto that account

## Scenario: Another trigger on the same pass governs instead of the drain

Given the active account has crossed its short-window rotation threshold

And a candidate's weekly window resets sooner than the active account's

When a scheduled pass runs

Then the candidates are compared on the short-window dimension under the eligibility margin

And the switch line does not name expiring weekly quota as the reason

## Scenario: Ranking ignores plan capacity

Given two eligible candidates on plans of different capacity

And the smaller-capacity candidate's weekly window resets sooner

When the operation ranks them

Then the smaller-capacity candidate ranks first

## Scenario: An invocation without the scheduled marker does not drain

Given the active account is clear of every rotation threshold

And a drain candidate exists

When the operation is invoked without the scheduled marker

Then any switch it makes is the explicit rotate-now request and not a drain

Co-edit tests/heading-coverage.json and tests/heading-coverage-debt.json (outside the spec target) with one entry per new scenario heading, each carrying `"test": "TODO"`, `"work_item": "overseer-pk5itu"` and a reason stating that an integration-tier test over the shipped rotation pass is owed and that work item owns landing it.
