---
topic: caam-capacity-aware-rotation
author: claude-opus-5-5
created_at: 2026-10-14T02:32:06Z
---

## Proposal: Rotate off an account that is refusing requests

### Target specification files

- SPECIFICATION/spec.md
- SPECIFICATION/contracts.md
- SPECIFICATION/scenarios.md

### Summary

Adds a refusal trigger: when the active account is observed refusing requests for a usage limit, a scheduled pass rotates off it whatever the usage figures report; the account stays ineligible until that refusal's window resets, so the operation cannot bounce back onto it; the switch line names the refusal.

### Motivation

On 2026-10-13 on host hp the loop held on anthropic-3, a small ($20) plan, while the usage API read 45% short-window remaining at 22:37Z; the account was refusing requests for its session limit at 22:46Z and read 0% at 22:49Z, and the operator had to switch by hand. The same day anthropic-2, downgraded to a small plan, fell about 70 short-window points per 30-minute pass where it had fallen about 10 on a large plan. Every rotation trigger is a percentage of an account's own window checked once per scheduled pass, so a small plan can drain inside one pass, and the operation has no signal for an account that is already refusing. Plan caam-mixed-plan-capacity (epic overseer-4nhrne, spec item overseer-prdmie); evidence in plan/caam-mixed-plan-capacity/research/001-mixed-plan-capacity.md, design and the maintainer's 2026-10-14 ruling (keep v055's capacity-blind ranking, make eligibility capacity-aware) in 002-scope-and-capacity-ruling.md.

### Proposed Changes

In spec.md section "Account rotation and quota supervision", insert the following paragraphs immediately after the **Rotation triggers** paragraph.

**Short-window floor.** Throughout this section the SHORT-WINDOW FLOOR is the short-window remaining at which the short-window threshold in **Rotation triggers** fires, expressed in remaining terms (100 minus that threshold where the threshold is stated as spent). Every clause below that compares a remaining figure with the short-window threshold MUST compare it with this floor.

**An account that is refusing requests MUST be left, and MUST NOT be returned to until its refusal has lapsed.** A refusal for a usage limit is ground truth about an account's allowance; a usage percentage is a report about it, and on 2026-10-13 the report read 45% remaining nine minutes before the account refused. The operation MUST therefore observe, on every pass, the refusal records that tracked sessions' transcripts carry, and MUST treat a USAGE-LIMIT REFUSAL of the active account as a rotation trigger on its own, alongside every trigger in **Rotation triggers**, whatever the usage figures report. A usage-limit refusal is a refusal the provider attributes to a short-window, weekly or rate limit; a rate limit counts as short-window, and where it carries a retry-after interval, the time it was recorded plus that interval MUST be taken as its reported reset time. The operation MUST parse each provider's refusal records into a provider-agnostic refusal carrying the time it was recorded, the window it names and the reset time the provider reported, if any; a provider whose records cannot be parsed MUST contribute no refusals rather than a guessed one. Detecting refusals MUST NOT send any request of its own.

The operation MUST attribute a refusal to the active account only when ALL of these hold: it was recorded by a tracked session of the same provider as the active account; that session authenticates with the host-wide live credential, which the operation MUST establish from the session's agent configuration directory being the host's default directory, the one holding the live credential, so that neither a separately provisioned credential nor the operation's own refresh-maintenance sandbox, whose sessions exercise other accounts' stored credentials and MUST NOT be read for refusals, can contribute; where the record names an account identity, that identity is the active account's stable identifier; it was recorded after the moment the operation last observed that account become active, which the operation MUST keep in its durable store; and its reported reset time does not match, within the one-minute tolerance, the reset time of the same window as last read on any DEPARTED ACCOUNT, since concurrent sessions MAY still be spending a departed account's credential for a while after a switch, and their refusals belong to it. A departed account is one the active account replaced, whatever trigger the departure was made on and whether or not the operation made the switch itself: whenever the operation records an activation time, it MUST store in its durable store the short-window and weekly reset times last read on the account the previous activation time named, and MUST keep that entry until the stored short-window reset time has passed. A refusal that reported no reset time never matches. Two residuals are accepted and not corrected: a lagging session's rate-limit refusal, whose reset is derived from its own retry-after interval, cannot match and MAY be attributed to the new account, bounded by its own short hold; and a genuine refusal of the new account whose reset coincides within a minute with a departed account's is not attributed, which fails safe because every other trigger still applies. Where no activation time is stored, or the stored one names a different account from the active account, the operation MUST record the current pass's time as the active account's activation time and MUST attribute no refusal on that pass rather than guess. A refusal recorded by a credential consumer outside the tracked sessions is outside what the operation can observe and MUST NOT be inferred.

The operation MUST remember each attributed refusal against its account in its durable store, with its window, its reported reset time, and the reset time that window's reading carried when the refusal was attributed. An account is REFUSAL-HELD from the moment a refusal is attributed to it until the reset time that refusal reported has passed, or, where none was reported, until a later reading of the named window shows it fully replenished or shows a reset time more than one minute later than the reset time that window's reading carried when the refusal was attributed. A refusal-held account MUST NOT be selected as a candidate, whether or not it is still the active account, and whatever its readings report. This is what keeps the refusal trigger from oscillating: a lagging reading on an account that has refused cannot attract a return to it until its window has actually reset.

The refusal trigger fires only while the active account is refusal-held. A move made under it on a short-window or rate-limit refusal counts as a short-window move for condition (f) of the expiring-quota drain. When this trigger fires, candidates MUST be compared on the dimension the refusal names, and the active account's headroom on that dimension MUST be taken as zero, since an account that is refusing has none to offer whatever its reading says. For the weekly reserve's release, a refusal-held active account MUST NOT count as an account above the reserve. The trigger MUST NOT relax any per-account protection floor, the zero-weekly disqualifier, the cannot-serve-immediately disqualifier or the live-verification rule. Where no candidate survives those rules, the operation MUST hold and MUST report that the active account is refusing requests and that no account could be selected. A switch made under this trigger MUST be reported as such: the switch line MUST name the refusal as the reason and MUST state when the refusal was recorded.

**Trigger precedence.** Where several triggers fire on one pass, the refusal trigger and its dimension MUST govern; otherwise every other trigger in this section except the drain, including the protected-account floor trigger, governs as already stated; the fast-drain trigger governs only where none of those fires; and the expiring-quota drain remains the lowest. The protection ordering and, where an operator pin names the scoped model, the scoped ordering in **Ranking** MUST apply under every trigger.

In spec.md, in the **Eligibility** paragraph, replace "The margin also makes oscillation impossible, since a switch requires a strict improvement that the reverse move cannot match." with "The margin also makes oscillation impossible, since a switch requires a strict improvement that the reverse move cannot match; under the refusal trigger, where the departing account's headroom is taken as zero, the refusal hold carries that guarantee instead, because a refusal-held account cannot be selected until its window has reset."

In scenarios.md, add these scenarios after "## Scenario: An invocation without the scheduled marker does not drain":

```gherkin
## Scenario: A refusing active account is left whatever its usage reads

Given a tracked session on the host-wide live credential recorded a short-window usage-limit refusal after the active account became active

And the usage API reports the active account's short-window remaining above the short-window floor

And an eligible candidate exists

When a scheduled pass runs

Then the operation rotates off the active account

And the switch line names the refusal as the reason and states when it was recorded

## Scenario: The operation does not return to an account inside its refusal window

Given the operation left an account on the refusal trigger

And the reset time that refusal reported has not passed

And that account's usage reading now shows more headroom than the active account by more than the margin

When a scheduled pass runs

Then that account is not selected

## Scenario: A refusal from another credential or provider is not attributed to the active account

Given a usage-limit refusal was recorded by a session on a separately provisioned credential, a session of another provider, or the refresh-maintenance sandbox

And the active account is clear of every rotation threshold

When a scheduled pass runs

Then the refusal does not trigger rotation

## Scenario: A lagging session's refusal after a switch stays with the account just left

Given the operation just left an account on its short-window threshold

And after the switch a tracked session records a short-window refusal whose reported reset time is within one minute of that account's last-read short-window reset time

When a scheduled pass runs

Then the refusal is not attributed to the new active account

## Scenario: A lagging session's refusal after a hand switch stays with the account left

Given the operator switched the host off an account by hand

And a later pass recorded the new active account's activation time

And afterwards a tracked session records a refusal whose reported reset time is within one minute of the replaced account's last-read reset time for that window

When a scheduled pass runs

Then the refusal is not attributed to the new active account

## Scenario: Reading jitter does not end a hold on a refusal that reported no reset

Given an account is refusal-held on a refusal that reported no reset time

And a later reading of that window shows a reset time less than one minute from the one it showed when the refusal was attributed

When a scheduled pass runs

Then the account remains refusal-held

## Scenario: A refusal recorded before the account became active is not attributed to it

Given a usage-limit refusal was recorded before the active account became active

And the active account is clear of every rotation threshold

When a scheduled pass runs

Then the refusal does not trigger rotation

## Scenario: A refusal whose reset has passed does not trigger rotation

Given the active account recorded a usage-limit refusal whose provider-reported reset time has passed

And the active account is clear of every rotation threshold

When a scheduled pass runs

Then the refusal does not trigger rotation

## Scenario: A refusing account with no selectable candidate holds and says so

Given the active account is refusing requests for a usage limit

And no candidate survives the protection floors, the zero-weekly and cannot-serve-immediately disqualifiers, live verification and the margin

When a scheduled pass runs

Then the operation holds

And it reports that the active account is refusing requests and no account could be selected
```


## Proposal: Rotate off an account that will drain before the next pass

### Target specification files

- SPECIFICATION/spec.md
- SPECIFICATION/contracts.md
- SPECIFICATION/scenarios.md

### Summary

Adds a fast-drain trigger: a scheduled pass rotates when the active account's short-window remaining, projected at its observed burn rate across a configured projection horizon (default the documented 30-minute schedule interval), would reach the short-window floor. A burn rate needs two readings of one window at least half a horizon apart. The schedule itself is unchanged, and the durable-store overwrite bound is extended to the new state.

### Motivation

On 2026-10-13 on host hp the loop held on anthropic-3, a small ($20) plan, while the usage API read 45% short-window remaining at 22:37Z; the account was refusing requests for its session limit at 22:46Z and read 0% at 22:49Z, and the operator had to switch by hand. The same day anthropic-2, downgraded to a small plan, fell about 70 short-window points per 30-minute pass where it had fallen about 10 on a large plan. Every rotation trigger is a percentage of an account's own window checked once per scheduled pass, so a small plan can drain inside one pass, and the operation has no signal for an account that is already refusing. Plan caam-mixed-plan-capacity (epic overseer-4nhrne, spec item overseer-prdmie); evidence in plan/caam-mixed-plan-capacity/research/001-mixed-plan-capacity.md, design and the maintainer's 2026-10-14 ruling (keep v055's capacity-blind ranking, make eligibility capacity-aware) in 002-scope-and-capacity-ruling.md.

### Proposed Changes

In spec.md section "Account rotation and quota supervision", insert the following paragraph immediately after the paragraphs added by the refusal-trigger proposal (or after **Rotation triggers**, with the short-window floor defined there, if that proposal is rejected).

**An account that will reach the floor before the next pass MUST be left now.** The short-window floor protects an account only if the account cannot spend its remaining margin between two passes, and on a small plan under fleet load it can. The operation MUST define a configurable PROJECTION HORIZON, a duration whose default MUST equal the documented interval of the operation's own schedule, because the operation's executable cannot read the schedule it was installed under, duplicate schedules can run closer together, and an unscheduled invocation has no interval at all. The operation MUST keep, in its durable store, a BASELINE READING of the active account's short window: its remaining figure, its provider-reported reset time and the time it was taken. Every pass that reads the active account MUST compute the SHORT-WINDOW BURN RATE as the fall in remaining from the baseline to the current reading divided by the time between them, but only where the two readings are of the same short window (reset times agreeing within the one-minute tolerance defined under **Expiring weekly quota MUST be drained**), the account was continuously the active account between them, and they are at least half the projection horizon apart; otherwise the burn rate is UNKNOWN. A pass MUST replace the baseline with its current reading only when no valid baseline exists — a valid baseline is one taken of the current active account and of the same short window — or the current reading is at least half the projection horizon after it, so that closely spaced passes measure across the older baseline rather than amplifying one percentage step into a large rate. A scheduled pass MUST rotate when the burn rate is known and positive and the active account's short-window remaining, less the burn rate multiplied by the projection horizon, is at or below the short-window floor. Candidates MUST be compared on the short-window dimension under this trigger, whose precedence is stated under **Trigger precedence**. The trigger MUST NOT fire on an invocation without the scheduled marker, which already rotates under **Mode resolution**. It MUST NOT relax the weekly reserve, any per-account protection floor, the zero-weekly disqualifier or the live-verification rule. A move made under it counts as a short-window move for condition (f) of the expiring-quota drain.

Where no candidate survives the other rules, the operation MUST hold and MUST report that the active account is projected to reach the short-window floor and that no account could be selected. The operation MUST NOT shorten or otherwise change its schedule in response to a burn rate. Projecting across a whole horizon already moves the fleet one pass early, and the refusal trigger covers an account whose usage figures lag what it actually spent. A switch made under this trigger MUST be reported as such: the switch line MUST name the projected short-window drain as the reason and MUST state the burn rate and the projected remaining at the end of the horizon.

In contracts.md section "The account-rotation operation", in **Schedule**, append: "The operation's projection horizon defaults to the interval this schedule establishes, 30 minutes, and MUST be configurable independently of it."

In contracts.md, in **Durable store**, replace "Concurrent writers MAY overwrite one another, which MUST cost at most a cached reading, or one premature drain return where the overwritten state was the drain trigger's memory of an account it moved off on a short-window trigger, and MUST NOT be able to corrupt the file." with "Concurrent writers MAY overwrite one another, which MUST cost at most: a cached reading; one premature drain return where the overwritten state was the drain trigger's memory of an account it moved off on a short-window trigger; one pass with an unknown burn rate or a burn rate measured from an older baseline, where the overwritten state was a baseline reading or the time an account was observed to become active; the last known fleet load, which then counts as stale; or a refusal memory, in which case the account loses its refusal hold early, at most one return to that account can follow, and its refusal is then attributed afresh while it is active, holding it again until that refusal's reset; or a departed account's last-read reset times, in which case refusals that departed account's lagging sessions record can be attributed to the account then active, costing one switch off it and that account's refusal hold until the departed window's reset. Losing the time an account was observed to become active MUST cost at most one pass on which no refusal is attributed, because attribution fails closed without it. A write MUST NOT be able to corrupt the file."

In scenarios.md, add these scenarios:

```gherkin
## Scenario: An account projected to reach the floor before the next pass is left

Given the active account's short-window remaining fell from 75% to 36% between a baseline and a reading of the same window one projection horizon apart

And the short-window floor is 15% remaining

And an eligible candidate exists

When a scheduled pass runs

Then the operation rotates off the active account

And the switch line names the projected short-window drain and states the burn rate

## Scenario: A slowly draining account holds

Given the active account's short-window remaining fell from 75% to 65% between a baseline and a reading of the same window one projection horizon apart

And the short-window floor is 15% remaining

When a scheduled pass runs

Then the fast-drain trigger does not fire

## Scenario: Closely spaced readings do not produce a burn rate

Given the active account's baseline reading was taken less than half the projection horizon before the current reading

When a pass runs

Then the burn rate is unknown

And the baseline is not replaced

## Scenario: No burn rate is computed across a short-window reset

Given the active account's baseline and current reading report short-window reset times more than one minute apart

When a scheduled pass runs

Then the burn rate is unknown

And the fast-drain trigger does not fire

## Scenario: No burn rate is computed across a switch

Given the active account became active after its baseline reading was taken

When a scheduled pass runs

Then the burn rate is unknown

And the fast-drain trigger does not fire
```


## Proposal: Do not switch onto an account too small for the current load

### Target specification files

- SPECIFICATION/spec.md
- SPECIFICATION/contracts.md
- SPECIFICATION/scenarios.md

### Summary

Makes eligibility capacity-aware: a candidate that the fleet's current load, scaled to that candidate's capacity, would drain to the short-window floor within the projection horizon is not eligible. The load is remembered across a switch for a bounded time, and ranking is unchanged. The test is released only when the active account is refusing and no candidate passes it.

### Motivation

On 2026-10-13 on host hp the loop held on anthropic-3, a small ($20) plan, while the usage API read 45% short-window remaining at 22:37Z; the account was refusing requests for its session limit at 22:46Z and read 0% at 22:49Z, and the operator had to switch by hand. The same day anthropic-2, downgraded to a small plan, fell about 70 short-window points per 30-minute pass where it had fallen about 10 on a large plan. Every rotation trigger is a percentage of an account's own window checked once per scheduled pass, so a small plan can drain inside one pass, and the operation has no signal for an account that is already refusing. Plan caam-mixed-plan-capacity (epic overseer-4nhrne, spec item overseer-prdmie); evidence in plan/caam-mixed-plan-capacity/research/001-mixed-plan-capacity.md, design and the maintainer's 2026-10-14 ruling (keep v055's capacity-blind ranking, make eligibility capacity-aware) in 002-scope-and-capacity-ruling.md. Observed ratio between Anthropic's large and small plans on the short window: about 7x, not the nominal 20x, so the weights are configurable rather than hardcoded.

### Proposed Changes

In spec.md section "Account rotation and quota supervision", insert the following paragraphs immediately after the **Eligibility** paragraph.

**A candidate MUST be able to carry the current load until the next pass.** Every account has a CAPACITY CLASS, defined under the capacity-reporting clause, and each class MUST carry a configurable relative CAPACITY WEIGHT, set per provider. The operation MUST NOT hardcode a provider's nominal plan multiplier as a weight, because the nominal and observed ratios differ (2026-10-13: about seven to one between Anthropic's large and small plans on the short window, against a nominal twenty). The FLEET LOAD is the active account's short-window burn rate, as defined under the fast-drain clause, multiplied by the active account's capacity weight. Whenever the burn rate is known, the active account's capacity class is known, and the active account is not refusal-held (an account that is refusing spends nothing, so its burn rate understates the load), the operation MUST record the fleet load and the time it was measured in its durable store, and when the burn rate is unknown it MUST use the last recorded fleet load for as long as it is no older than twice the projection horizon, so that the test still applies on the pass after a switch. A candidate's PROJECTED BURN is the fleet load divided by the candidate's capacity weight. A candidate MUST NOT be selected when its short-window remaining, less its projected burn multiplied by the projection horizon, is at or below the short-window floor. This CAPACITY TEST MUST apply to every selection the operation makes, under every trigger including the expiring-quota drain, and to an invocation without the scheduled marker, which MUST use the burn rate or fleet load available to it on that pass. When no fleet load is available, the capacity test MUST NOT exclude any candidate.

Where a capacity class cannot be determined, the operation MUST be conservative toward the candidate and neutral toward the active account. A candidate of unknown class MUST be weighted as the smallest class configured for its provider. An active account of unknown class MUST contribute the weight of the candidate under test, so that candidate's projected burn equals the active account's own burn rate; such a pass MUST NOT record a fleet load. The capacity test MUST NOT relax any other rule.

The capacity test MUST be released only where the active account is refusal-held, on a scheduled pass or an invocation without the scheduled marker alike, and no candidate that survives every other rule passes it. In that case the operation MUST select from the candidates that fail it, ranked by **Ranking** unchanged, because an account that is refusing requests serves nothing, while an account that drains before the next pass still serves until then. Outside that case, where a trigger other than the drain has fired and the capacity test excludes every candidate that survives the other rules, the operation MUST hold and MUST report that no candidate can carry the current load until the next pass; where the drain finds no candidate because of the capacity test, the operation simply holds as for any absent drain candidate. One report line MAY name both the trigger that fired and the capacity test.

In spec.md, in the **Expiring weekly quota MUST be drained** paragraph, in condition (b), after "the weekly-reserve exclusion" insert ", and the capacity test defined under **A candidate MUST be able to carry the current load until the next pass**". The projection horizon is a property of the capacity test and the fast-drain trigger and is not drain configuration.

In contracts.md section "The account-rotation operation", in **Mode resolution**, replace "while still refusing any move that would lose headroom and still refusing an exhausted destination" with "while still refusing any move that would lose headroom, still refusing an exhausted destination, and still refusing a destination that fails the capacity test defined in spec.md section 'Account rotation and quota supervision', except where that section releases the test because the active account is refusal-held".

In contracts.md, add after **Durable store**:

**Capacity weights.** Capacity weights MUST be configurable per provider and capacity class. Only the ratio between two weights of one provider affects a decision. The defaults for the Anthropic provider MUST be `small` 1, `medium` 2 and `large` 7. The medium default is deliberately low, which makes the capacity test stricter for medium accounts, because no medium-class ratio has been measured. A provider added to rotation later MUST state its own defaults.

In scenarios.md, add these scenarios:

```gherkin
## Scenario: A small candidate that the current load would drain is not selected

Given the active account is in the large capacity class with a short-window burn rate of 10 points per projection horizon

And a candidate in the small capacity class holds 50% short-window remaining

And the short-window floor is 15% remaining

And the capacity weights are large 7 and small 1

When the operation selects a destination

Then the small candidate is not selected

## Scenario: A small candidate is selectable under light load

Given the active account is in the large capacity class with a short-window burn rate of 1 point per projection horizon

And a candidate in the small capacity class holds 50% short-window remaining

And the short-window floor is 15% remaining

And the capacity weights are large 7 and small 1

When the operation selects a destination

Then the capacity test does not exclude the small candidate

## Scenario: The capacity test uses the remembered fleet load after a switch

Given the active account's burn rate is unknown because it became active since its baseline

And a fleet load was recorded less than twice the projection horizon ago

When the operation applies the capacity test

Then it uses that recorded fleet load

## Scenario: A candidate of unknown capacity is weighted as the smallest class

Given a candidate whose capacity class cannot be determined

And a fleet load is available

When the operation applies the capacity test

Then the candidate is weighted as the smallest capacity class configured for its provider

## Scenario: The capacity test is released for a refusing account when no candidate passes it

Given the active account is refusing requests for a usage limit

And every candidate that survives the other rules fails the capacity test

When a scheduled pass runs

Then the operation selects among those candidates by soonest weekly reset

## Scenario: The capacity test holds when it excludes every candidate and the active account is not refusing

Given the active account has triggered rotation at its short-window floor

And the capacity test excludes every candidate

When a scheduled pass runs

Then the operation holds

And it reports that no candidate can carry the current load until the next pass
```


## Proposal: Report each account's capacity class from a live read

### Target specification files

- SPECIFICATION/spec.md
- SPECIFICATION/contracts.md
- SPECIFICATION/scenarios.md

### Summary

The account table shows each account's capacity class in provider-agnostic terms with the provider's plan name as detail, read live from the provider rather than from login-time credential fields, and shows unknown when it cannot be read.

### Motivation

On 2026-10-13 on host hp the loop held on anthropic-3, a small ($20) plan, while the usage API read 45% short-window remaining at 22:37Z; the account was refusing requests for its session limit at 22:46Z and read 0% at 22:49Z, and the operator had to switch by hand. The same day anthropic-2, downgraded to a small plan, fell about 70 short-window points per 30-minute pass where it had fallen about 10 on a large plan. Every rotation trigger is a percentage of an account's own window checked once per scheduled pass, so a small plan can drain inside one pass, and the operation has no signal for an account that is already refusing. Plan caam-mixed-plan-capacity (epic overseer-4nhrne, spec item overseer-prdmie); evidence in plan/caam-mixed-plan-capacity/research/001-mixed-plan-capacity.md, design and the maintainer's 2026-10-14 ruling (keep v055's capacity-blind ranking, make eligibility capacity-aware) in 002-scope-and-capacity-ruling.md. The vault's login-time plan fields still read the large plan for anthropic-2 after its downgrade; Anthropic's GET /api/oauth/profile returns the organization's current rate_limit_tier read-only (measured 2026-10-14, recorded in research note 002).

### Proposed Changes

In spec.md §"Account rotation and quota supervision", insert the following paragraph immediately after the **Observation** paragraph:

**Each account's capacity class MUST be observed live and reported.** Two accounts at the same percentage can hold very different absolute headroom, so the operator-facing report MUST show, for every account, its CAPACITY CLASS — one of `small`, `medium` or `large` — with the provider's own plan name as detail, or `unknown` when the class cannot be determined. The operation MUST determine the class on every pass from a read-only provider request that reflects the account's CURRENT plan, made with the same credential the pass uses for that account's usage, and subject to the same **Never refresh** rule. It MUST NOT derive the class from plan fields stored in a credential at login, which do not change when the plan does. A failed or unparseable read, or a provider plan name with no mapping, MUST yield `unknown`; the operation MUST NOT fall back to a stored or guessed class, and an unknown class MUST NOT on its own fail the pass.

In contracts.md §"The account-rotation operation", add after the capacity-weights paragraph:

**Capacity class source.** For the Anthropic provider, the current plan MUST be read from `GET https://api.anthropic.com/api/oauth/profile` with the account's OAuth access token and the `anthropic-beta: oauth-2025-04-20` header, taking `organization.rate_limit_tier`; this read is the only request the capacity source may send, and it MUST be read-only. The mapping MUST be: `default_claude_ai` to `small`, `default_claude_max_5x` to `medium`, and `default_claude_max_20x` to `large`. Any other value MUST map to `unknown`, and the provider value MUST be shown as the plan-name detail. A provider added to rotation later MUST supply its own source and mapping onto the same three classes.

In scenarios.md, add these scenarios:

```gherkin
## Scenario: The account table shows each account's capacity class

Given the provider reports a large plan for one account and a small plan for another

When the operation renders the account table

Then each row shows its capacity class with the provider's plan name as detail

## Scenario: A plan change shows without a fresh login

Given an account's stored login-time credential names a large plan

And the provider's live read reports a small plan for that account

When the operation renders the account table

Then that account's row shows the small capacity class

## Scenario: An unreadable plan shows unknown

Given the live plan read for an account fails

When the operation renders the account table

Then that account's row shows an unknown capacity class

And the pass does not fail on that account
```


## Proposal: Rest the capacity-blind ranking on the rules that bound a small account

### Target specification files

- SPECIFICATION/spec.md

### Summary

Keeps v055's ranking rule (soonest weekly reset, no capacity weight) and rewords only its rationale, whose claim that every trigger already bounds a small account's spend was false until the refusal, fast-drain and capacity-test rules exist.

### Motivation

On 2026-10-13 on host hp the loop held on anthropic-3, a small ($20) plan, while the usage API read 45% short-window remaining at 22:37Z; the account was refusing requests for its session limit at 22:46Z and read 0% at 22:49Z, and the operator had to switch by hand. The same day anthropic-2, downgraded to a small plan, fell about 70 short-window points per 30-minute pass where it had fallen about 10 on a large plan. Every rotation trigger is a percentage of an account's own window checked once per scheduled pass, so a small plan can drain inside one pass, and the operation has no signal for an account that is already refusing. Plan caam-mixed-plan-capacity (epic overseer-4nhrne, spec item overseer-prdmie); evidence in plan/caam-mixed-plan-capacity/research/001-mixed-plan-capacity.md, design and the maintainer's 2026-10-14 ruling (keep v055's capacity-blind ranking, make eligibility capacity-aware) in 002-scope-and-capacity-ruling.md.

### Proposed Changes

In spec.md §"Account rotation and quota supervision", in the **Ranking** paragraph, replace the sentence

"Soonest weekly reset is the only perishability order the operation can defend, and every trigger already bounds how far a small account is spent before the operation moves on; a capacity weight would systematically leave a smaller account's perishable balance to lapse."

with

"Soonest weekly reset is the only perishability order the operation can defend. Capacity governs whether an account can serve the current load, which the capacity test under **Eligibility** decides. How far a small account is spent is bounded by the refusal trigger and the fast-drain trigger, not by ranking. A capacity weight in ranking would systematically leave a smaller account's perishable balance to lapse, and it MUST NOT be reintroduced to compensate for a gap in those rules."

The rule sentence "Ranking MUST NOT weight a candidate by its plan capacity or rate-limit tier." and the scenario "## Scenario: Ranking ignores plan capacity" MUST remain unchanged.
